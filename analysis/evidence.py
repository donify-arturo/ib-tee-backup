"""
Evidence pack for one sub-topic: everything the Technique Engine (Part 3) needs, pulled from the
chunk library and grouped by question so a question, its markscheme and the examiners' comment
travel together.

    python -m analysis.evidence R3.1            # → data/evidence/R3.1.json

Pack layout
  sub_topic, title, understandings[]          syllabus statements, skills, guidance (Pillar 1)
  command_terms[]                             AO-tagged command-term definitions (Pillar 4)
  data_booklet[]                              mapped data-booklet sections (Pillar 6)
  questions[]                                 one entry per question_ref:
        question text, markscheme text (or null), mcq_answer, examiner comment(s),
        pct_correct, popular_distractor, era, paper, marks, has_markscheme
  trap_lines[]                                markscheme notes that define mark boundaries
                                              ("Do not accept…", "Award [1 max]…", "Accept…") with refs (Pillar 2)
  examiner_errors[]                           sentences from comments that describe mistakes (Pillars 2, 3)
  findings{difficult[], well_prepared[]}      paper-level bullets
  macro{}                                     the sub-topic's row from macro_by_subtopic.json
  missing_markschemes[]                       question refs with no markscheme (the Part 3 gate queue)
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from .macro import ERROR_CUE, _sentences

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "chunks"
OUT = ROOT / "data" / "evidence"
SYLLABUS = ROOT / "data" / "syllabus" / "syllabus.json"
MACRO = ROOT / "data" / "reports" / "macro_by_subtopic.json"

TRAP_RE = re.compile(
    r"(Do not (?:accept|award|allow|penali[sz]e)[^\n]*|Award \[\d+(?:\s*max)?\][^\n]*|\[\d+\s*max\][^\n]*|"
    r"Accept [^\n]*|Allow [^\n]*|Ignore [^\n]*|[^\n]*\bECF\b[^\n]*|[^\n]*\bOWTTE\b[^\n]*|"
    r"(?:M\d|M\s?\d) (?:must|only|requires)[^\n]*|[^\n]*\bmust (?:refer|include|mention|state)[^\n]*)", re.I)


def _load_chunks():
    for f in sorted(CHUNKS.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                if c["metadata"].get("scan_quality", "green") == "green":      # amber/red book items wait for review
                    yield c


def _body(text: str) -> str:
    return text.split("\n", 1)[1].strip() if text.startswith("[") and "\n" in text else text.strip()


def build(sub_topic: str, include_secondary: bool = True) -> dict:
    syl = json.loads(SYLLABUS.read_text(encoding="utf-8"))
    sub = next(s for s in syl["sub_topics"] if s["code"] == sub_topic)
    chunks = list(_load_chunks())
    by_id = {c["id"]: c for c in chunks}

    def in_scope(m):
        if m.get("sub_topic") == sub_topic:
            return True
        return include_secondary and sub_topic in (m.get("sub_topics_all") or [])[1:]

    questions: dict[str, dict] = {}
    for c in chunks:
        m = c["metadata"]
        if m["source_type"] not in {"past_paper", "markscheme", "examiner_report"} or not in_scope(m):
            continue
        ref = m.get("resolved_ref") or m.get("question_ref") or m.get("report_question_key")
        if not ref:
            continue
        q = questions.setdefault(ref, {
            "ref": ref, "session": m.get("session"), "paper": m.get("paper"), "level": m.get("level"),
            "era": m.get("syllabus_era"), "primary": m.get("sub_topic") == sub_topic,
            "question": [], "markscheme": [], "examiner": [], "mcq_answer": None,
            "pct_correct": None, "popular_distractor": None, "linked_ids": set(),
        })
        q["primary"] = q["primary"] or m.get("sub_topic") == sub_topic
        q["linked_ids"].update(m.get("linked_ids", []))
        part = (m.get("question_part") or "", _body(c["text"]))
        if m["source_type"] == "past_paper":
            q["question"].append(part)
        elif m["source_type"] == "markscheme":
            q["markscheme"].append(part)
            q["mcq_answer"] = q["mcq_answer"] or m.get("mcq_answer")
        else:
            q["examiner"].append(_body(c["text"]))
        for k in ("pct_correct", "popular_distractor"):
            if m.get(k) is not None and q[k] is None:
                q[k] = m[k]

    # pull in linked items the classifier tagged elsewhere (same question, different chunk)
    for q in questions.values():
        for lid in list(q["linked_ids"]):
            c = by_id.get(lid)
            if not c:
                continue
            m, body = c["metadata"], _body(c["text"])
            if m["source_type"] == "markscheme" and not q["markscheme"]:
                q["markscheme"].append((m.get("question_part") or "", body))
                q["mcq_answer"] = q["mcq_answer"] or m.get("mcq_answer")
            elif m["source_type"] == "past_paper" and not q["question"]:
                q["question"].append((m.get("question_part") or "", body))
            elif m["source_type"] == "examiner_report" and body not in q["examiner"]:
                q["examiner"].append(body)

    out_q = []
    for q in questions.values():
        ms_text = "\n".join(t for _p, t in sorted(q["markscheme"])) or None
        if ms_text and re.fullmatch(r"(?:Correct answer:\s*)?[A-D]", ms_text.strip()):
            q["mcq_answer"] = q["mcq_answer"] or ms_text.strip()[-1]
        out_q.append({
            "ref": q["ref"], "session": q["session"], "paper": q["paper"], "level": q["level"], "era": q["era"],
            "primary": q["primary"],
            "question": "\n".join(t for _p, t in sorted(q["question"])) or None,
            "markscheme": ms_text, "mcq_answer": q["mcq_answer"],
            "has_markscheme": bool(ms_text or q["mcq_answer"]),
            "examiner": q["examiner"] or None,
            "pct_correct": q["pct_correct"], "popular_distractor": q["popular_distractor"],
        })
    # most useful first: 2025 era, has question+markscheme, primary tag, examiner evidence
    out_q.sort(key=lambda x: (x["era"] != "2025", not (x["question"] and x["has_markscheme"]),
                              not x["primary"], not x["examiner"], x["ref"]))

    traps, seen = [], set()
    for q in out_q:
        for line in TRAP_RE.findall(q["markscheme"] or ""):
            line = re.sub(r"\s+", " ", line).strip(" .")
            key = line.lower()
            if 8 <= len(line) <= 220 and key not in seen:
                seen.add(key)
                traps.append({"ref": q["ref"], "rule": line})

    errors = []
    for q in out_q:
        for txt in q["examiner"] or []:
            for s in _sentences("x\n" + txt):
                if ERROR_CUE.search(s):
                    errors.append({"ref": q["ref"], "pct_correct": q["pct_correct"], "sentence": s[:260]})

    findings = defaultdict(list)
    for c in chunks:
        m = c["metadata"]
        if m["source_type"] == "examiner_finding" and m.get("sub_topic") == sub_topic:
            findings[m["polarity"]].append(f"{m.get('session')}: {c['text'].split(': ', 1)[-1]}")

    und = [{"code": code, "level": syl["understandings"][code]["level"],
            "statement": syl["understandings"][code]["statement"],
            "skills": syl["understandings"][code]["skills"],
            "guidance": syl["understandings"][code]["guidance"],
            "data_booklet_mentioned": syl["understandings"][code]["data_booklet_mentioned"]}
           for code in sub["understandings"]]
    db = []
    for c in chunks:
        m = c["metadata"]
        if m["source_type"] == "data_booklet" and sub_topic in (m.get("sub_topics_all") or []):
            db.append({"section": m["data_booklet_sections"][0], "text": c["text"][:1500]})

    macro = json.loads(MACRO.read_text(encoding="utf-8"))["sub_topics"].get(sub_topic, {}) if MACRO.exists() else {}
    return {
        "sub_topic": sub_topic, "title": sub["title"], "guiding_question": sub.get("guiding_question"),
        "hl_only": sub.get("hl_only", False), "understandings": und,
        "command_terms": syl["command_terms"], "data_booklet": db,
        "questions": out_q, "trap_lines": traps, "examiner_errors": errors,
        "findings": dict(findings), "macro": macro,
        "missing_markschemes": [q["ref"] for q in out_q if q["question"] and not q["has_markscheme"]],
        "stats": {
            "questions": sum(1 for q in out_q if q["question"]),
            "questions_with_markscheme": sum(1 for q in out_q if q["question"] and q["has_markscheme"]),
            "markscheme_only": sum(1 for q in out_q if not q["question"] and q["has_markscheme"]),
            "with_examiner_comment": sum(1 for q in out_q if q["examiner"]),
            "era_2025": sum(1 for q in out_q if q["era"] == "2025"),
            "trap_lines": len(traps), "examiner_error_sentences": len(errors),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sub_topic")
    ap.add_argument("--primary-only", action="store_true")
    a = ap.parse_args()
    pack = build(a.sub_topic, include_secondary=not a.primary_only)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{a.sub_topic}.json"
    path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(pack["stats"], indent=2))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
