"""
Part 3 — the 7-Pillar Technique Engine (Claude Fable 5.1).

    python -m engine.technique_engine R3.1                 # gate check, then generate
    python -m engine.technique_engine R3.1 --allow-partial # skip questions with no markscheme
    python -m engine.technique_engine --gate-report        # markscheme gate for every sub-topic

Flow per sub-topic
  1. evidence pack   analysis.evidence.build(sub_topic)  (questions + markschemes + examiner comments,
                     trap lines, findings, syllabus statements, data-booklet sections, macro row)
  2. markscheme gate a question may only feed a card if its markscheme is in the library. If any
                     selected question lacks one, the engine PAUSES (MarkschemeMissing) and lists the
                     refs so the UI can ask the student to upload them. --allow-partial drops those
                     questions instead and records them on the deck.
  3. synthesis       one Fable call with a forced tool schema → cards (same schema as data/techniques)
  4. validation      deterministic: every evidence ref must exist, every card needs ≥2 refs (or one
                     markscheme ref), MCQ letters must match the key, booklet sections must exist and
                     formulas the card says are "in the booklet" must appear in that section's text
  5. merge + save    keeps each card's `status.mastered` from the previous deck (by card_id/title)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import evidence as evidence_mod  # noqa: E402
from ingest.scan_books import equation_issues, numbers_in  # noqa: E402

TECH_DIR = ROOT / "data" / "techniques"
MODEL = os.environ.get("IBTEE_ENGINE_MODEL", "claude-fable-5-1")

PILLARS = {
    "1_context": "Syllabus-to-Exam Contextual Bridge: AO level, which papers test it, the syllabus hook, and the textbook gap between how books teach it and how exams test it.",
    "2_markscheme_logic": "Markscheme Logic & Trigger Phrases: the exact phrases that earn marks, the trap boundaries (what is NOT accepted, mark caps, ECF rules) and the delta analysis between partial and full credit.",
    "3_novel_application": "Novel Application Deconstruction: how the idea is disguised in unfamiliar contexts and the mental heuristic that unmasks it.",
    "4_command_terms": "Command Term Strategy & Score Mechanics: the command terms used and how marks are allocated for them.",
    "5_time_efficiency": "Time-Efficiency & Marks-per-Minute Heuristics: the shortest reliable workflow and the fat to trim.",
    "6_data_booklet": "Data Booklet Pattern Hacks: bypass memorization through the booklet's tables and trends; say explicitly when something is NOT in the booklet.",
    "7_elimination": "Instant Elimination Heuristics: 'definitely wrong' rules that need no calculation.",
}

SYSTEM = f"""You are the IB-TEE Technique Engine: an experienced IB Chemistry examiner who turns past questions,
markschemes and examiner reports into non-repetitive technique cards for one syllabus sub-topic (2025 syllabus).

A technique card captures ONE recurring pattern — a trick, trap or method that appears across several
questions — not one question. Merge questions that test the same pattern into one card. 8–15 cards per
sub-topic is typical; fewer is fine when the evidence is thin.

Balance the deck like the exam. When the pack has usable written questions (Paper 2 or 1B, with markschemes), at least a third of
the cards use one, and give those `marks` above 1 where the markscheme does. Use no more than a third of the cards on one family
of questions: spread them across the sub-topic's understandings, including practical and data work where the pack has it.

Fill all 7 pillars for every card:
{chr(10).join(f"- {k}: {v}" for k, v in PILLARS.items())}

Hard rules
1. Evidence only. Every claim about what examiners reward or penalize must come from the evidence pack.
   Cite refs in `evidence` (kind = mcq | question | markscheme | examiner). Each card needs ≥2 refs, or one
   markscheme ref. Never invent a ref.
2. Only questions whose markscheme is present may support a trap boundary or an answer. Examiner comments
   may support misconceptions on their own.
3. Paraphrase. Quote at most a few words of a markscheme or report when the exact wording is the point
   (e.g. "small amounts"). Never copy question text.
4. Data booklet: only say something is in the booklet if it appears in the section text provided; otherwise
   say it is NOT in the booklet and must be memorised.
5. Chemistry must be correct at IB level. If an elimination rule has exceptions, state them.
6. Pre-2025 questions were set on the old syllabus: use them for patterns, and prefer 2025-era evidence
   for exam format (Paper 1A/1B/2) and difficulty signals.
7. Priority 1 = highest value: frequent in exams AND low % correct or repeatedly flagged by examiners.

Every card also teaches its pattern through one worked question, in `walkthrough`. The student sees this on an interactive
card first, so it must feel instant: each pillar is a button inside the question, opening from basic to more to why.
Be brief. Short plain sentences; no padding.
- Choose the question from the pack that best shows the pattern and has BOTH its question text and its markscheme present;
  prefer one with examiner evidence. Set `question_ref` to it. Never reconstruct a question from a markscheme.
  Skip a question that needs a diagram or data missing from its text: the student must be able to solve it from the card.
- `question`: rewrite the setup in your own words with the same chemistry and values. Give an MCQ's options on their own
  lines as "A. ...". Never copy the original wording. If the pack has a [FIGURE: ...] description, say what it shows.
- `key_idea`: the single idea that solves it, in at most 15 words. This shows next to the answer.
- `procedure`: the plain standard method, in order, that works on any question of this type: 2-6 steps of at most 12 words
  each. No shortcuts here. A student who has never seen this topic should be able to follow it.
- `tricks`: 1-3 faster ways or checks for someone who already knows the procedure, at most 15 words each. A trick with
  exceptions must say when it fails, such as "Fails if a species is not gaseous."
- `if_lost`: 2-4 questions that nudge a stuck student towards the first step, from easiest to most specific, at most 15
  words each. They appear before the answer, so they must never give the answer, its value or its letter.
- `question_type`: a name for this type of question, at most 8 words, the same across similar cards, such as
  "Born-Haber: find lattice enthalpy". The student's notes are grouped by it.
- `careful`: the one step most easily got wrong on this type, at most 12 words. It goes in the student's notes next
  to the workflow, so write the workflow as 2-5 steps of at most 8 words each that work on any question of this type.
- `steps` has one entry per pillar, about THIS question, never general advice. In each:
  `short` is the basic level, visible on the tile: at most 12 words, and it must make sense alone.
  `why` is the deepest level: at most 35 words on why the trick works.
  `avoid` is the tempting wrong move (use what examiners reported when the pack has it, and name the ref).
  `seconds` is an honest time. Every other field is the "more" level: at most 35 words each.
- `diagram`: only when the question shows an energy cycle, give it as data so the student can click it: `levels` (`id`,
  `label`, `x0` and `x1` as fractions of the width), `arrows` (`id`, `name`, `from`, `to`, `value`, `x`, `short`, `why`, and
  `target` true on the one being asked for), `route` (level ids from the target's start to its end) and `unit`. Omit it otherwise.
  - 4_command_terms: `command_term` (the syllabus term, or "none" for an MCQ stem), `demands` (what it requires here),
    `score_mechanics` (how these marks are given: per point, for working, all or nothing).
  - 1_context: `ao_level` (AO1, AO2 or AO3), `syllabus_hook` (the understanding code, such as R1.2.5, and what it says),
    `textbook_gap` (how textbooks teach this compared with how this question tests it).
  - 3_novel_application: `disguise` (what makes this look unfamiliar), `heuristic` (the mental check that unmasks it).
  - 7_elimination: `definitely_wrong`, a list of `target` and `rule` pairs: what can be ruled out WITHOUT calculating. For an MCQ
    the target is an option letter, and never the correct one. For a structured question it is a kind of answer, such as
    a positive value for an exothermic change.
  - 6_data_booklet: `sections` (numbers, or empty if none help), `pattern` (the table or trend to read instead of
    memorising), `memorise` (what this needs that is NOT in the booklet; required when `sections` is empty).
  - 5_time_efficiency: `workflow` (2 to 4 moves of at most 6 words each, such as "Flip the one against you": these become
    the student's things to remember, so make them memorable), `fat_to_trim` (what to skip on this question).
  - 2_markscheme_logic: `trigger_phrases` (what earns the marks), `trap_boundary` (where the mark stops), `delta` (the
    exact difference between partial and full credit, or between the right and tempting answer for an MCQ), `evidence_ref`
    (the markscheme it comes from).
- `answer` must agree with the markscheme; for an MCQ start with the correct letter.
- `try_next`: up to 3 other refs from the pack with markschemes, of the SAME question type, solved by the same `procedure`. They come
  back as fresh questions on later days, shown as printed: prefer MCQs whose formulas and options are intact in the pack's text and
  which need no diagram.
Return the deck with the `emit_technique_deck` tool."""

# Order the student works through them in the exam: read, recognise, rule out, look up, solve, check against the marks.
STEP_ORDER = ["4_command_terms", "1_context", "3_novel_application", "7_elimination", "6_data_booklet", "5_time_efficiency",
              "2_markscheme_logic"]
_STR = {"type": "string"}
_STRS = {"type": "array", "items": _STR}


def _step(**fields) -> dict:
    return {"type": "object",
            "properties": {"short": _STR, "why": _STR, "avoid": _STR, "seconds": {"type": "integer", "minimum": 1}, **fields},
            "required": ["short", "why", "avoid", "seconds", *fields]}


STEP_SCHEMAS = {
    "4_command_terms": _step(command_term=_STR, demands=_STR, score_mechanics=_STR),
    "1_context": _step(ao_level=_STR, syllabus_hook=_STR, textbook_gap=_STR),
    "3_novel_application": _step(disguise=_STR, heuristic=_STR),
    "7_elimination": _step(definitely_wrong={"type": "array", "items": {
        "type": "object", "properties": {"target": _STR, "rule": _STR}, "required": ["target", "rule"]}}),
    "6_data_booklet": _step(sections={"type": "array", "items": {"type": "integer"}}, pattern=_STR, memorise=_STR),
    "5_time_efficiency": _step(workflow=_STRS, fat_to_trim=_STR),
    "2_markscheme_logic": _step(trigger_phrases=_STRS, trap_boundary=_STR, delta=_STR, evidence_ref=_STR),
}
_NUM = {"type": "number"}
DIAGRAM_SCHEMA = {
    "type": "object",
    "properties": {
        "type": _STR, "unit": _STR, "route": _STRS,
        "levels": {"type": "array", "items": {"type": "object", "properties": {"id": _STR, "label": _STR, "x0": _NUM, "x1": _NUM},
                                              "required": ["id", "label", "x0", "x1"]}},
        "arrows": {"type": "array", "items": {"type": "object", "properties": {
            "id": _STR, "name": _STR, "from": _STR, "to": _STR, "value": _NUM, "x": _NUM, "short": _STR, "why": _STR, "target": {"type": "boolean"}},
            "required": ["id", "name", "from", "to", "value", "x", "short", "why"]}},
    },
    "required": ["unit", "route", "levels", "arrows"],
}
WALKTHROUGH_SCHEMA = {
    "type": "object",
    "properties": {
        "question_ref": _STR, "question": _STR, "marks": {"type": "integer", "minimum": 1}, "key_idea": _STR,
        "question_type": _STR, "careful": _STR, "procedure": _STRS, "tricks": _STRS, "if_lost": _STRS,
        "steps": {"type": "object", "properties": STEP_SCHEMAS, "required": STEP_ORDER, "additionalProperties": False},
        "answer": _STR, "try_next": _STRS, "diagram": DIAGRAM_SCHEMA,
    },
    "required": ["question_ref", "question", "marks", "key_idea", "question_type", "careful", "procedure", "tricks", "if_lost", "steps", "answer", "try_next"],
}
MAX_WORDS = {"short": 12, "why": 35, "key_idea": 15, "question_type": 8, "careful": 12, "workflow_step": 8, "procedure": 12, "tricks": 15, "if_lost": 15, "other": 35}

CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "card_id": {"type": "string", "description": "sub-topic code + -T + two digits, e.g. R3.1-T01"},
        "title": {"type": "string"},
        "understandings": {"type": "array", "items": {"type": "string"}},
        "priority": {"type": "integer", "minimum": 1, "maximum": 10},
        "walkthrough": WALKTHROUGH_SCHEMA,
        "pillars": {
            "type": "object",
            "properties": {
                "1_context": {"type": "object", "properties": {
                    "ao": {"type": "string"}, "papers": {"type": "array", "items": {"type": "string"}},
                    "syllabus_hook": {"type": "string"}, "textbook_gap": {"type": "string"}},
                    "required": ["ao", "papers", "syllabus_hook", "textbook_gap"]},
                "2_markscheme_logic": {"type": "object", "properties": {
                    "trigger_phrases": {"type": "array", "items": {"type": "string"}},
                    "trap_boundaries": {"type": "array", "items": {"type": "string"}},
                    "delta": {"type": "string"}}, "required": ["trigger_phrases", "trap_boundaries", "delta"]},
                "3_novel_application": {"type": "object", "properties": {
                    "disguises": {"type": "array", "items": {"type": "string"}}, "heuristic": {"type": "string"}},
                    "required": ["disguises", "heuristic"]},
                "4_command_terms": {"type": "object", "properties": {
                    "terms": {"type": "array", "items": {"type": "string"}}, "score_mechanics": {"type": "string"}},
                    "required": ["terms", "score_mechanics"]},
                "5_time_efficiency": {"type": "object", "properties": {
                    "workflow": {"type": "array", "items": {"type": "string"}}, "fat_to_trim": {"type": "string"}},
                    "required": ["workflow", "fat_to_trim"]},
                "6_data_booklet": {"type": "object", "properties": {
                    "sections": {"type": "array", "items": {"type": "integer"}}, "hack": {"type": "string"}},
                    "required": ["sections", "hack"]},
                "7_elimination": {"type": "object", "properties": {
                    "rules": {"type": "array", "items": {"type": "string"}}}, "required": ["rules"]},
            },
            "required": list(PILLARS),
        },
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "ref": {"type": "string"}, "kind": {"type": "string", "enum": ["mcq", "question", "markscheme", "examiner"]},
            "note": {"type": "string"}}, "required": ["ref", "kind", "note"]}},
        "difficulty_signal": {"type": "string"},
    },
    "required": ["card_id", "title", "understandings", "priority", "walkthrough", "pillars", "evidence", "difficulty_signal"],
}
TOOL = {
    "name": "emit_technique_deck",
    "description": "Return the technique cards for this sub-topic.",
    "input_schema": {"type": "object", "properties": {
        "cards": {"type": "array", "items": CARD_SCHEMA},
        "cross_links": {"type": "array", "items": {"type": "object", "properties": {
            "sub_topic": {"type": "string"}, "note": {"type": "string"}}, "required": ["sub_topic", "note"]}},
    }, "required": ["cards"]},
}


class MarkschemeMissing(Exception):
    def __init__(self, sub_topic: str, refs: list[str]):
        self.sub_topic, self.refs = sub_topic, refs
        super().__init__(f"{sub_topic}: {len(refs)} question(s) have no markscheme: {', '.join(refs[:12])}"
                         f"{' …' if len(refs) > 12 else ''}. Upload them, or rerun with --allow-partial.")


# --------------------------------------------------------------------------- #
# 1–2. evidence + gate
# --------------------------------------------------------------------------- #
def gate(pack: dict) -> list[str]:
    """Question refs (with question text) that lack a markscheme."""
    return [q["ref"] for q in pack["questions"] if q["question"] and not q["has_markscheme"]]


def compact_pack(pack: dict, allow_partial: bool, max_examiner: int = 160, max_questions: int = 120,
                 max_text: int = 1500) -> dict:
    """Trim the pack to what the model needs, within a sensible token budget."""
    keep_q = []
    for q in pack["questions"]:
        if q["question"] and not q["has_markscheme"] and not allow_partial:
            continue                                   # the gate has already stopped us in this case
        if q["question"] and not q["has_markscheme"]:
            continue                                   # partial mode: drop unanswered questions
        keep_q.append({k: q[k] for k in ("ref", "session", "paper", "level", "era", "mcq_answer", "pct_correct",
                                         "popular_distractor") if q.get(k) is not None}
                      | {"question": (q["question"] or "")[:max_text] or None,
                         "markscheme": (q["markscheme"] or "")[:max_text] or None,
                         "examiner": [e[:600] for e in (q["examiner"] or [])][:2] or None})
    # pack.questions is already ordered by usefulness (2025 era, question+markscheme, examiner evidence)
    keep_q = keep_q[:max_questions]
    seen, errors = set(), []
    for e in sorted(pack["examiner_errors"], key=lambda e: e["ref"], reverse=True):   # recent first
        k = e["sentence"][:70].lower()
        if k not in seen:
            seen.add(k)
            errors.append(e)
    return {
        "sub_topic": pack["sub_topic"], "title": pack["title"], "guiding_question": pack["guiding_question"],
        "understandings": pack["understandings"],
        "command_terms": pack["command_terms"],
        "data_booklet_sections": pack["data_booklet"],
        "macro": {k: pack["macro"].get(k) for k in ("priority_score", "exam_frequency", "mean_pct_correct",
                                                     "difficulty_ratio", "hardest", "error_signals")},
        "questions": keep_q,
        "trap_lines": pack["trap_lines"][:200],
        "examiner_errors": errors[:max_examiner],
        "findings": {k: v[:40] for k, v in pack["findings"].items()},
    }


# --------------------------------------------------------------------------- #
# 3. synthesis
# --------------------------------------------------------------------------- #
def synthesize(compact: dict, client=None, model: str = MODEL) -> dict:
    import anthropic
    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=32000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "emit_technique_deck"},
        messages=[{"role": "user", "content":
                   f"Build the technique deck for {compact['sub_topic']} {compact['title']}.\n\n"
                   f"<evidence_pack>\n{json.dumps(compact, ensure_ascii=False)}\n</evidence_pack>"}],
    )
    block = next(b for b in resp.content if getattr(b, "type", "") == "tool_use")
    return dict(block.input)


class UsageLimitReached(Exception):
    """Claude Code reported that the plan's usage limit is reached: stop and resume later."""


LOG = ROOT / "data" / "reports" / "engine_log.jsonl"


def synthesize_cli(compact: dict, model: str = "opus", effort: str = "high", timeout: int = 1800, focus: str = "") -> dict:
    """Run the synthesis through Claude Code (`claude -p`).

    Signed in with a Pro/Max plan, this draws on the plan's usage limits, not API credit.
    Unset ANTHROPIC_API_KEY first, or Claude Code will bill the API key instead."""
    import shutil
    import subprocess
    import time

    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code not found on PATH. Install it (https://claude.com/claude-code) and run `claude` once to sign in.")
    env = dict(os.environ)
    if env.pop("ANTHROPIC_API_KEY", None):
        print("  note: ignoring ANTHROPIC_API_KEY so Claude Code uses your plan, not API credit")
    # Instructions travel on stdin, not as arguments: on Windows `claude` may be a .cmd wrapper and
    # cmd.exe mangles long quoted arguments. The schema argument is compact JSON with no spaces and
    # none of cmd.exe's special characters (& | < > ^ %).
    prompt = (f"<instructions>\n{SYSTEM}\n</instructions>\n\n"
              f"Build the technique deck for {compact['sub_topic']} {compact['title']}. Use only the evidence pack "
              f"below and return the deck as JSON matching the schema.{focus}\n\n<evidence_pack>\n"
              f"{json.dumps(compact, ensure_ascii=False)}\n</evidence_pack>")
    def strip_descriptions(node):
        if isinstance(node, dict):
            return {k: strip_descriptions(v) for k, v in node.items() if k != "description"}
        if isinstance(node, list):
            return [strip_descriptions(v) for v in node]
        return node
    schema = json.dumps(strip_descriptions(TOOL["input_schema"]), separators=(",", ":"), ensure_ascii=True)
    assert not re.search(r"[&|<>^%\s]", schema), "schema must be shell-safe"
    cmd = [exe, "-p", "--model", model, "--effort", effort, "--output-format", "json",
           "--json-schema", schema, "--tools", "", "--no-session-persistence"]
    for attempt in range(2):
        t0 = time.time()
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                              timeout=timeout, env=env)
        raw = (proc.stdout or "").strip()
        try:
            out = json.loads(raw.splitlines()[-1] if raw else "{}")
        except json.JSONDecodeError:
            out = {"is_error": True, "result": raw[-2000:]}
        msg = json.dumps(out)[:4000] + (proc.stderr or "")[-2000:]
        if re.search(r"usage limit|rate limit|limit reached|resets? at|out of (?:extra )?usage", msg, re.I) and \
                (out.get("is_error") or proc.returncode):
            raise UsageLimitReached(msg[:500])
        deck = out.get("structured_output")
        if deck is None and isinstance(out.get("result"), str):
            m = re.search(r"\{.*\}", out["result"], re.S)          # fallback: JSON inside the text result
            if m:
                try:
                    deck = json.loads(m.group(0))
                except json.JSONDecodeError:
                    deck = None
        _log({"sub_topic": compact["sub_topic"], "backend": "claude-cli", "model": model, "attempt": attempt + 1,
              "seconds": round(time.time() - t0), "ok": bool(deck and deck.get("cards")),
              "usage": out.get("usage"), "cost_usd_equivalent": out.get("total_cost_usd"),
              "error": None if deck else msg[:300]})
        if deck and deck.get("cards"):
            return deck
    raise RuntimeError(f"Claude Code returned no deck for {compact['sub_topic']}: {msg[:400]}")


def _log(row: dict) -> None:
    import datetime
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row["at"] = datetime.datetime.now().isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


# --------------------------------------------------------------------------- #
# 4. deterministic validation
# --------------------------------------------------------------------------- #
IN_BOOKLET_RE = re.compile(r"(?:section|sections)\s+(\d{1,2})", re.I)


def clean_steps(deck: dict) -> list[str]:
    """Keep only real pillars in each card's steps, so a stray field can't break the checks or the card. A lost pillar is then reported as missing."""
    dropped = []
    for card in deck.get("cards", []):
        steps = (card.get("walkthrough") or {}).get("steps")
        if not isinstance(steps, dict):
            continue
        for key in list(steps):
            if key not in STEP_ORDER or not isinstance(steps[key], dict):
                dropped.append(f"{card.get('card_id')}: {key}")
                del steps[key]
    return dropped


def too_long(wt: dict) -> list[str]:
    """The card must read at a glance: basic lines stay short and nothing turns into a paragraph."""
    out = []
    if len((wt.get("key_idea") or "").split()) > MAX_WORDS["key_idea"]:
        out.append(f"key idea is over {MAX_WORDS['key_idea']} words")
    for field in ("question_type", "careful"):
        if len((wt.get(field) or "").split()) > MAX_WORDS[field]:
            out.append(f"{field} is over {MAX_WORDS[field]} words")
    workflow = ((wt.get("steps") or {}).get("5_time_efficiency") or {}).get("workflow") or []
    if len(workflow) > 5:
        out.append("workflow has more than 5 steps, too many to remember")
    out += [f"workflow step '{s[:30]}' is over {MAX_WORDS['workflow_step']} words" for s in workflow if len(s.split()) > MAX_WORDS["workflow_step"]]
    for pillar, step in (wt.get("steps") or {}).items():
        for field, value in step.items():
            if isinstance(value, str) and len(value.split()) > MAX_WORDS.get(field, MAX_WORDS["other"]):
                out.append(f"{pillar} {field} is over {MAX_WORDS.get(field, MAX_WORDS['other'])} words")
    return out


def guidance_issues(wt: dict) -> list[str]:
    """The procedure, tricks and I'm-lost hints: present, short, and the hints must not give the answer away."""
    out = []
    for field, low, high in (("procedure", 2, 6), ("tricks", 1, 3), ("if_lost", 2, 4)):
        items = wt.get(field) or []
        if not low <= len(items) <= high:
            out.append(f"{field} needs {low}-{high} items, has {len(items)}")
        out += [f"{field} item '{x[:30]}' is over {MAX_WORDS[field]} words" for x in items if len(x.split()) > MAX_WORDS[field]]
    given = numbers_in(wt.get("question", ""))
    secret = numbers_in(wt.get("answer", "")) - given
    for hint in wt.get("if_lost") or []:
        if re.search(r"\b(?:answer|option|choose|pick)\s+(?:is\s+)?[A-D]\b", hint) or secret & numbers_in(hint):
            out.append(f"hint gives the answer away: {hint[:50]}")
    return out


def diagram_issues(diagram: dict | None) -> list[str]:
    """A clickable cycle is re-typed data, so its numbers must add up: the route must really total the target's value."""
    if not diagram:
        return []
    levels = {l["id"] for l in diagram.get("levels", [])}
    arrows = diagram.get("arrows", [])
    out = [f"diagram arrow {a['id']} joins a level that doesn't exist" for a in arrows if a["from"] not in levels or a["to"] not in levels]
    targets = [a for a in arrows if a.get("target")]
    if len(targets) != 1:
        return out + ["diagram needs exactly one target arrow"]
    target, route, total = targets[0], diagram.get("route", []), 0.0
    if not route or route[0] != target["from"] or route[-1] != target["to"]:
        out.append("diagram route doesn't run from the target's start to its end")
    for a, b in zip(route, route[1:]):
        leg = next((x for x in arrows if not x.get("target") and {x["from"], x["to"]} == {a, b}), None)
        if leg is None:
            out.append(f"diagram route has no arrow from {a} to {b}")
            return out
        total += leg["value"] if leg["from"] == a else -leg["value"]
    if abs(total - target["value"]) > 0.5:
        out.append(f"diagram route totals {total:g}, but the target says {target['value']:g}")
    return out


def walkthrough_issues(wt: dict | None, known: dict, command_terms: set[str] | None = None, codes: set[str] | None = None) -> list[str]:
    """Checks for the worked question: real ref with a markscheme, correct answer, not copied, and all 7 pillars
    delivered with their own specifics, checked against the syllabus and markscheme where that's possible."""
    if not wt:
        return ["no step-by-step walkthrough"]
    out = []
    q = known.get(wt.get("question_ref"))
    if q is None:
        return [f"walkthrough cites unknown ref {wt.get('question_ref')}"]
    if not q["has_markscheme"]:
        out.append(f"walkthrough question {wt['question_ref']} has no markscheme")
    if not q.get("question"):
        out.append(f"walkthrough question {wt['question_ref']} has no question text, so it was reconstructed")
    if re.search(r"not in the (?:available )?(?:text|pack)|not available here|not shown here|(?:from|in) the (?:figure in the )?paper\b|inferred from",
                 f"{wt.get('question', '')} {wt.get('answer', '')}", re.I):
        out.append("needs a diagram or data the card doesn't have, so it can't be solved from the card")
    steps = wt.get("steps") or {}
    key = q.get("mcq_answer")
    out += too_long(wt) + diagram_issues(wt.get("diagram")) + guidance_issues(wt)
    if not wt.get("key_idea"):
        out.append("walkthrough has no key idea")
    if not wt.get("question_type"):
        out.append("walkthrough has no question type")
    if not wt.get("careful"):
        out.append("walkthrough has no careful step")
    for pillar in STEP_ORDER:
        step = steps.get(pillar)
        if not step:
            out.append(f"walkthrough is missing {pillar}")
            continue
        for field in STEP_SCHEMAS[pillar]["required"]:
            if step.get(field) in (None, "") and not (pillar == "6_data_booklet" and field in {"sections", "pattern", "memorise"}):
                out.append(f"{pillar} has no {field}")
    if key:
        letter = re.match(r"\s*([A-D])\b", wt.get("answer", ""))
        if not letter:
            out.append("MCQ walkthrough answer doesn't start with a letter")
        elif letter.group(1) != key:
            out.append(f"walkthrough answers {letter.group(1)}, key is {key}")

    command = steps.get("4_command_terms") or {}
    term = (command.get("command_term") or "").strip().lower()
    if command_terms and not key and term not in command_terms:
        out.append(f"'{command.get('command_term')}' is not a syllabus command term")

    context = steps.get("1_context") or {}
    if context and not re.fullmatch(r"AO[123]", (context.get("ao_level") or "").strip()):
        out.append(f"'{context.get('ao_level')}' is not an AO level")
    hook = re.findall(r"\b[SR]\d\.\d\.\d+\b", context.get("syllabus_hook") or "")
    if context and not hook:
        out.append("syllabus hook has no understanding code")
    elif codes and not set(hook) <= codes:
        out.append(f"syllabus hook cites {sorted(set(hook) - codes)}, which this sub-topic doesn't have")

    wrong = (steps.get("7_elimination") or {}).get("definitely_wrong")
    if steps.get("7_elimination") and not wrong:
        out.append("elimination rules nothing out")
    for item in wrong or []:
        target = item.get("target", "").strip().rstrip(".)")
        if key and target == key:
            out.append(f"elimination rules out the correct answer {key}")
        elif key and target not in {"A", "B", "C", "D"}:
            out.append(f"MCQ elimination target '{item.get('target')}' is not an option letter")

    booklet = steps.get("6_data_booklet") or {}
    out += [f"data booklet section {s} does not exist" for s in booklet.get("sections") or [] if s not in range(1, 25)]
    if booklet.get("sections") and not booklet.get("pattern"):
        out.append("data booklet step names sections but no pattern to read")
    if steps.get("6_data_booklet") and not booklet.get("sections") and not booklet.get("memorise"):
        out.append("data booklet step gives no section and nothing to memorise")

    if steps.get("5_time_efficiency"):
        moves = steps["5_time_efficiency"].get("workflow") or []
        if len(moves) < 2:
            out.append("workflow has fewer than 2 moves")
        if len(moves) > 4:
            out.append("workflow has more than 4 moves to remember")
        out += [f"workflow move '{m}' is over 6 words" for m in moves if len(m.split()) > 6]

    logic = steps.get("2_markscheme_logic") or {}
    if logic:
        source = known.get(logic.get("evidence_ref"))
        if not source or not source["has_markscheme"]:
            out.append(f"markscheme step cites {logic.get('evidence_ref')}, which has no markscheme in the pack")
        if not logic.get("trigger_phrases"):
            out.append("markscheme step has no trigger phrases")
        elif not key and source and source.get("markscheme"):      # an MCQ key is only a letter, so nothing to compare
            printed = set(re.findall(r"[a-z]{4,}", source["markscheme"].lower()))
            said = set(re.findall(r"[a-z]{4,}", " ".join(logic["trigger_phrases"]).lower()))
            numbers = numbers_in(" ".join(logic["trigger_phrases"])) & numbers_in(source["markscheme"])     # a value can be what earns the mark
            if said and not said & printed and not numbers:
                out.append("trigger phrases share no words with the markscheme")

    stem = lambda t: re.split(r"\n\s*A[.)]\s", t or "", maxsplit=1)[0].lower()      # options may match; the wording may not
    if q.get("question") and SequenceMatcher(None, stem(wt.get("question")), stem(q["question"])).ratio() > 0.8:
        out.append("walkthrough question copies the original wording")
    text = "\n".join([wt.get("question", ""), wt.get("answer", "")] + [str(s.get("short", "")) for s in steps.values()])
    out += [f"walkthrough equation doesn't balance: {e}" for e in equation_issues(text)]
    out += [f"walkthrough tries {ref}, which isn't in the pack with a markscheme" for ref in wt.get("try_next", [])
            if not known.get(ref, {}).get("has_markscheme")]
    return out


def validate(deck: dict, pack: dict) -> list[dict]:
    """Return a list of issues; each card also gets status.needs_review when it has one."""
    known = {q["ref"]: q for q in pack["questions"]}
    booklet = {d["section"]: d["text"].lower() for d in pack["data_booklet"]}
    terms = {t["term"].lower() for t in pack["command_terms"]}
    codes = {u["code"] for u in pack["understandings"]}
    issues = []
    for card in deck["cards"]:
        cid = card["card_id"]
        issues += [{"card": cid, "issue": i} for i in walkthrough_issues(card.get("walkthrough"), known, terms, codes)]
        ev = card.get("evidence", [])
        if len(ev) < 2 and not any(e["kind"] == "markscheme" for e in ev):
            issues.append({"card": cid, "issue": "fewer than 2 evidence refs and no markscheme ref"})
        for e in ev:
            q = known.get(e["ref"])
            if q is None:
                issues.append({"card": cid, "issue": f"unknown ref {e['ref']}"})
                continue
            if e["kind"] in {"mcq", "markscheme"} and not q["has_markscheme"]:
                issues.append({"card": cid, "issue": f"{e['ref']} cited as {e['kind']} but has no markscheme"})
            # an MCQ note that names a letter must agree with the key
            m = re.search(r"\b(?:answer|key|correct)\s*(?:is|=|:)?\s*([A-D])\b", e.get("note", ""))
            if e["kind"] == "mcq" and m and q.get("mcq_answer") and m.group(1) != q["mcq_answer"]:
                issues.append({"card": cid, "issue": f"{e['ref']} note says {m.group(1)}, key is {q['mcq_answer']}"})
        db = card["pillars"]["6_data_booklet"]
        for s in db.get("sections", []):
            if s not in booklet and s not in range(1, 25):
                issues.append({"card": cid, "issue": f"data booklet section {s} does not exist"})
        # formulas the card claims are printed in the booklet must be there (checked per sentence;
        # a sentence that says "not", "memorise" or "yours to remember" is a negative claim)
        for sentence in re.split(r"(?<=[.;:])\s+", db.get("hack", "")):
            positive = re.search(r"\b(?:is|are) (?:printed |given |listed )?in (?:the )?(?:data )?booklet|"
                                 r"section \d+ (?:gives|lists|prints|has)|\(section \d+\)", sentence, re.I)
            negative = re.search(r"\bnot\b|n't\b|memoris|memoriz|yours to remember|derive", sentence, re.I)
            if not positive or negative:
                continue
            for formula in re.findall(r"(pKa\s*\+\s*pKb|pH\s*\+\s*pOH|Ka\s*[×x*]\s*Kb|pH\s*=\s*pKa)", sentence):
                if not any(formula.lower().replace(" ", "") in t.replace(" ", "") for t in booklet.values()):
                    issues.append({"card": cid, "issue": f"'{formula}' claimed to be in the booklet but is not"})
    flagged = {i["card"] for i in issues}
    for card in deck["cards"]:
        card.setdefault("status", {"mastered": False})
        card["status"]["needs_review"] = card["card_id"] in flagged
    return issues


# --------------------------------------------------------------------------- #
# 5. merge with the previous deck (keep the student's progress) and save
# --------------------------------------------------------------------------- #
def merge_status(new: dict, old: dict | None) -> None:
    if not old:
        return
    prev = old.get("cards", [])
    for card in new["cards"]:
        match = next((c for c in prev if c["card_id"] == card["card_id"]), None) or \
            max(prev, key=lambda c: SequenceMatcher(None, c["title"], card["title"]).ratio(), default=None)
        if match and (match["card_id"] == card["card_id"] or
                      SequenceMatcher(None, match["title"], card["title"]).ratio() > 0.75):
            card.setdefault("status", {})["mastered"] = match.get("status", {}).get("mastered", False)


def add_prompt(skills: str, deck: dict) -> str:
    """Ask only for the named skills: the deck's other cards stay exactly as they are."""
    types = "; ".join(sorted({c["walkthrough"]["question_type"] for c in deck["cards"] if c.get("walkthrough")}))
    return (f"\n\nThis deck already exists and is being topped up. Build ONLY one card for each of these skills: {skills}. "
            f"Ignore the rules on how many cards a deck has and how it is balanced. The existing cards already cover: {types}. "
            f"If the pack has no usable question with a markscheme for a skill, leave that skill out rather than reconstructing one.")


def merge_added(deck: dict, added: dict, sub_topic: str) -> list[str]:
    """Append new cards with the next free ids. Existing cards are left alone. Returns the new ids."""
    numbers = [int(c["card_id"].rsplit("-", 1)[1]) for c in deck["cards"]]
    next_number = max(numbers, default=0) + 1
    ids = []
    for card in added.get("cards", []):
        card["card_id"] = f"{sub_topic}-{next_number:02d}"
        ids.append(card["card_id"])
        deck["cards"].append(card)
        next_number += 1
    return ids


def add_cards(sub_topic: str, skills: str, model: str | None = None, effort: str = "high", from_raw: bool = False) -> dict:
    """Top up a deck on the Pro plan. The finished build is saved first, so a problem afterwards can't waste it."""
    pack = evidence_mod.build(sub_topic)
    path = TECH_DIR / f"{sub_topic}.json"
    deck = json.loads(path.read_text(encoding="utf-8"))
    raw_path = ROOT / "data" / "reports" / "raw_decks" / f"{sub_topic}.add.json"
    if from_raw:
        added = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        added = synthesize_cli(compact_pack(pack, True), model=model or "opus", effort=effort, focus=add_prompt(skills, deck))
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(added, ensure_ascii=False), encoding="utf-8")
    dropped = clean_steps(added)
    if dropped:
        print("  dropped stray fields:", "; ".join(dropped))
    ids = merge_added(deck, added, sub_topic)
    for card in deck["cards"]:
        card.setdefault("status", {})["needs_review"] = False
    deck["validation_issues"] = validate(deck, pack)
    path.write_text(json.dumps(deck, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"added {ids}; {len(deck['cards'])} cards, {len(deck['validation_issues'])} validation issues")
    return deck


def run(sub_topic: str, allow_partial: bool = False, client=None, dry_run: bool = False,
        backend: str = "api", model: str | None = None, effort: str = "high", from_raw: bool = False) -> dict:
    pack = evidence_mod.build(sub_topic)
    missing = gate(pack)
    if missing and not allow_partial:
        raise MarkschemeMissing(sub_topic, missing)
    compact = compact_pack(pack, allow_partial)
    if dry_run:
        return {"compact_chars": len(json.dumps(compact, ensure_ascii=False)), "questions": len(compact["questions"]),
                "examiner_errors": len(compact["examiner_errors"]), "missing_markschemes": missing}
    raw_path = ROOT / "data" / "reports" / "raw_decks" / f"{sub_topic}.json"
    if from_raw:                    # check a finished build again, without paying for a new one
        deck = json.loads(raw_path.read_text(encoding="utf-8"))
        generated_by = f"claude-code:{model or 'opus'}"
    elif backend == "claude-cli":
        deck = synthesize_cli(compact, model=model or "opus", effort=effort)
        generated_by = f"claude-code:{model or 'opus'}"
    else:
        deck = synthesize(compact, client=client, model=model or MODEL)
        generated_by = model or MODEL
    if not from_raw:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(deck, ensure_ascii=False), encoding="utf-8")
    dropped = clean_steps(deck)
    if dropped:
        print("  dropped stray fields:", "; ".join(dropped))
    deck.update(sub_topic=sub_topic, title=pack["title"], schema_version=2, generated_by=generated_by,
                excluded_no_markscheme=missing,
                evidence_base={k: pack["stats"][k] for k in ("questions", "questions_with_markscheme", "era_2025",
                                                              "trap_lines", "examiner_error_sentences")})
    issues = validate(deck, pack)
    deck["validation_issues"] = issues
    path = TECH_DIR / f"{sub_topic}.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    merge_status(deck, old)
    TECH_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(deck, indent=2, ensure_ascii=False), encoding="utf-8")
    return deck


def gate_report(save: bool = True) -> list[dict]:
    syl = json.loads((ROOT / "data" / "syllabus" / "syllabus.json").read_text(encoding="utf-8"))
    rows = []
    for s in syl["sub_topics"]:
        pack = evidence_mod.build(s["code"])
        rows.append({"sub_topic": s["code"], "questions": pack["stats"]["questions"],
                     "with_markscheme": pack["stats"]["questions_with_markscheme"], "missing": gate(pack)})
    if save:                                           # the app reads this; no PDFs needed at runtime
        out = ROOT / "data" / "reports" / "gate.json"
        out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


def run_all(backend: str, model: str | None, effort: str, allow_partial: bool, force: bool,
            only: list[str] | None = None) -> None:
    """Fill every sub-topic, most-evidenced first; resumable (skips existing decks unless --force)."""
    rows = sorted(gate_report(), key=lambda r: -r["with_markscheme"])
    for r in rows:
        sub = r["sub_topic"]
        if only and sub not in only:
            continue
        if (TECH_DIR / f"{sub}.json").exists() and not force:
            print(f"skip   {sub}: deck exists (use --force to regenerate)")
            continue
        if r["with_markscheme"] < 3:
            print(f"skip   {sub}: only {r['with_markscheme']} question(s) with markschemes")
            continue
        print(f"build  {sub} ({r['with_markscheme']} questions with markschemes) …", flush=True)
        try:
            deck = run(sub, allow_partial=allow_partial, backend=backend, model=model, effort=effort)
        except MarkschemeMissing as e:
            print(f"PAUSED {e}")
            continue
        except UsageLimitReached as e:
            print(f"STOP   usage limit reached during {sub}. Run the same command again after your limit resets "
                  f"— finished decks are kept.\n       {str(e)[:200]}")
            return
        except Exception as e:                         # keep going with the next sub-topic
            print(f"FAIL   {sub}: {e}")
            continue
        print(f"done   {sub}: {len(deck['cards'])} cards, {len(deck['validation_issues'])} validation issues")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sub_topic", nargs="?")
    ap.add_argument("--allow-partial", action="store_true", help="skip questions with no markscheme instead of pausing")
    ap.add_argument("--dry-run", action="store_true", help="build the evidence pack and gate only; no API call")
    ap.add_argument("--gate-report", action="store_true")
    ap.add_argument("--all", action="store_true", help="fill every sub-topic (resumable)")
    ap.add_argument("--force", action="store_true", help="with --all: regenerate decks that already exist")
    ap.add_argument("--from-raw", action="store_true", help="re-check the last finished build in data/reports/raw_decks, with no new call")
    ap.add_argument("--backend", choices=["api", "claude-cli"], default="api",
                    help="api = Anthropic API key (paid credit); claude-cli = Claude Code signed in with your plan")
    ap.add_argument("--model", help="api: model id (default claude-fable-5-1); claude-cli: alias such as opus/sonnet/fable")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--add", help="top up an existing deck on the Pro plan: only cards for these skills; every other card is kept")
    a = ap.parse_args()
    if a.add:
        try:
            add_cards(a.sub_topic, a.add, model=a.model, effort=a.effort, from_raw=a.from_raw)
        except UsageLimitReached as e:
            print(f"STOP — usage limit reached; try again after it resets. {str(e)[:200]}")
            sys.exit(3)
        return
    if a.all:
        run_all(a.backend, a.model, a.effort, a.allow_partial, a.force,
                only=[a.sub_topic] if a.sub_topic else None)
        return
    if a.gate_report:
        for r in gate_report():
            print(f"{r['sub_topic']:5} questions={r['questions']:<4} with_ms={r['with_markscheme']:<4} missing={len(r['missing'])}")
        return
    try:
        out = run(a.sub_topic, allow_partial=a.allow_partial, dry_run=a.dry_run,
                  backend=a.backend, model=a.model, effort=a.effort, from_raw=a.from_raw)
    except MarkschemeMissing as e:
        print(f"PAUSED — {e}")
        sys.exit(2)
    except UsageLimitReached as e:
        print(f"STOP — usage limit reached; try again after it resets. {str(e)[:200]}")
        sys.exit(3)
    if a.dry_run:
        print(json.dumps(out, indent=2))
    else:
        print(f"{len(out['cards'])} cards, {len(out['validation_issues'])} validation issues → data/techniques/{a.sub_topic}.json")


if __name__ == "__main__":
    main()
