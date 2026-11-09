"""
The interactive question card: answers to tap, the 7 tricks built into the question (each opens from basic to more to why), and a
clickable energy cycle. Five tricks help before answering; Markscheme and Syllabus would give too much away, so they wait for the answer.
The page is card_component/index.html: every tap responds instantly with no Streamlit rerun, and only the first answer is sent back.
"""
from __future__ import annotations

import base64
import json
import re
from functools import lru_cache
from pathlib import Path

TILES = [
    ("4_command_terms", "Command term"), ("1_context", "Syllabus"), ("3_novel_application", "Disguise"),
    ("7_elimination", "Eliminate"), ("6_data_booklet", "Data booklet"), ("5_time_efficiency", "Time"),
    ("2_markscheme_logic", "Markscheme"),
]
FIELD_LABELS = {
    "command_term": "Command term", "demands": "It demands", "score_mechanics": "How marks are given", "ao_level": "AO level",
    "syllabus_hook": "Syllabus", "textbook_gap": "Textbook gap", "disguise": "The disguise", "heuristic": "See through it",
    "definitely_wrong": "Definitely wrong", "sections": "Sections", "pattern": "Read this", "memorise": "Memorise (not in booklet)",
    "workflow": "Fastest route", "fat_to_trim": "Skip", "trigger_phrases": "Earns the mark", "trap_boundary": "Mark stops at",
    "delta": "The difference", "evidence_ref": "Markscheme", "avoid": "Avoid",
}
BEFORE_ANSWER = ["4_command_terms", "3_novel_application", "7_elimination", "6_data_booklet", "5_time_efficiency"]
AFTER_ANSWER = ["2_markscheme_logic", "1_context"]
# More of the same trick, from the card's wider evidence across other questions
ALSO = {"3_novel_application": "disguises", "7_elimination": "rules", "2_markscheme_logic": "trap_boundaries"}
_OPTION = re.compile(r"^\s*([A-D])[.)]\s*(.*)$")


def split_options(question: str) -> tuple[str, list[dict]]:
    """Separate an MCQ's stem from its A-D lines. A question without all four options has no tappable answers."""
    stem, options = [], []
    for line in question.splitlines():
        m = _OPTION.match(line)
        if m:
            options.append({"letter": m.group(1), "text": m.group(2).strip()})
        elif not options:
            stem.append(line)
    if [o["letter"] for o in options] != list("ABCD"):
        return question, []
    return "\n".join(stem).strip(), options


def _fields(step: dict) -> list[list[str]]:
    rows = []
    for key, value in step.items():
        if key in {"short", "why", "seconds", "definitely_wrong"} or value in (None, "", []):
            continue
        rows.append([FIELD_LABELS.get(key, key.replace("_", " ")), ", ".join(map(str, value)) if isinstance(value, list) else str(value)])
    return rows


def _chip(key: str, label: str, step: dict) -> str:
    """The button's text: Time and Data booklet can say something useful before they are even tapped."""
    if key == "5_time_efficiency" and step.get("seconds"):
        return f"Time {step['seconds']} s"
    if key == "6_data_booklet" and step.get("sections"):
        return f"{label} §" + ", ".join(map(str, step["sections"]))
    return label


def _command_word(stem: str, step: dict) -> list[str] | None:
    """Split the stem around its command term, so the word itself can be tapped. None when the term isn't in the stem."""
    term = str(step.get("command_term") or "").strip()
    if not term or term.lower() == "none":
        return None
    m = re.search(rf"\b{re.escape(term)}\b", stem, re.I)
    return [stem[:m.start()], m.group(0), stem[m.end():]] if m else None


def remember_points(card: dict) -> list[str]:
    """The moves to keep in your head for this trick: the worked question's workflow, or the card's for older decks."""
    wt = card.get("walkthrough") or {}
    step = wt.get("steps", {}).get("5_time_efficiency") or {}
    return list(wt.get("procedure") or step.get("workflow") or card.get("pillars", {}).get("5_time_efficiency", {}).get("workflow") or [])


def card_data(card: dict, figure_dir: Path, figures: list[str], web_tips: list[dict] | None = None) -> dict:
    wt = card["walkthrough"]
    stem, options = split_options(wt["question"])
    elimination = wt["steps"].get("7_elimination", {}).get("definitely_wrong") or []
    answer = re.match(r"\s*([A-D])\b", wt["answer"]) if options else None
    correct = answer.group(1) if answer else None
    letters = {o["letter"] for o in options}
    for o in options:
        rule = next((x["rule"] for x in elimination if x.get("target", "").strip().rstrip(".)") == o["letter"]), None)
        o["why"] = "" if o["letter"] == correct else rule or ""      # never cross out the right answer, even if a deck says to
    tiles = []
    for key, label in TILES:
        step = wt["steps"].get(key)
        if not step:
            continue
        also = [str(x) for x in (card.get("pillars", {}).get(key, {}).get(ALSO.get(key, ""), []) or [])][:3]
        fields = _fields(step)
        if key == "7_elimination":        # rules about a kind of wrong answer, not one option, have nothing to cross out
            fields += [["Definitely wrong", f"{x.get('target', '')}: {x.get('rule', '')}"] for x in elimination
                       if x.get("target", "").strip().rstrip(".)") not in letters]
        tiles.append({"key": key, "label": label, "chip": _chip(key, label, step), "short": step["short"], "why": step["why"], "fields": fields, "also": also,
                      "seconds": step.get("seconds", 0),
                      "web": [{"tip": w["tip"], "why": w.get("why", ""), "url": w["url"], "domain": w.get("domain", "")}
                              for w in web_tips or [] if w.get("pillar") == key and re.match(r"https?://", w.get("url", ""))]})
    images = []
    for name in figures:
        path = figure_dir / name
        if path.exists():
            images.append("data:image/png;base64," + base64.b64encode(path.read_bytes()).decode())
    return {"stem": stem, "stem_parts": _command_word(stem, wt["steps"].get("4_command_terms", {})), "options": options, "correct": correct,
            "before": BEFORE_ANSWER, "after": AFTER_ANSWER, "key_idea": wt.get("key_idea", ""),
            "answer": wt["answer"], "marks": wt["marks"], "ref": wt["question_ref"], "tiles": tiles, "images": images,
            "diagram": wt.get("diagram"),
            "try_next": wt.get("try_next", []), "evidence": [[e["ref"], e.get("note", "")] for e in card.get("evidence", [])],
            "remember": remember_points(card), "procedure": wt.get("procedure") or [], "tricks": wt.get("tricks") or [],
            "if_lost": wt.get("if_lost") or []}


@lru_cache(maxsize=1)
def _component():
    import streamlit.components.v1 as components
    return components.declare_component("ib_card", path=str(Path(__file__).resolve().parent / "card_component"))


def show_card(data: dict, key: str) -> dict | None:
    """Draw a card (card_component/index.html). Returns what the student did first on it, once they have answered."""
    return _component()(data=data, key=key, default=None)


def variant_data(parent: dict | None, variant: dict, figure_dir: Path, figures: list[str]) -> dict:
    """A past-paper question shown as printed: its own text and key, the parent card's method if it has one, and no question-specific tricks."""
    wt = (parent or {}).get("walkthrough", {})
    images = ["data:image/png;base64," + base64.b64encode((figure_dir / n).read_bytes()).decode() for n in figures if (figure_dir / n).exists()]
    steps = remember_points(parent) if parent else []
    return {"stem": variant["stem"], "stem_parts": None, "options": [{**o, "why": ""} for o in variant["options"]], "correct": variant["correct"],
            "before": [], "after": [], "related": True, "key_idea": "", "answer": "", "marks": 1, "ref": variant["ref"],      # the card's key idea is about its own question
            "tiles": [], "images": images, "diagram": None, "try_next": [], "evidence": [], "remember": steps,
            "procedure": wt.get("procedure") or [], "tricks": wt.get("tricks") or [], "if_lost": steps}
