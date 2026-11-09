"""
Maths AI HL revision papers → data/maths/questions.json

    python -m ingest.maths_papers

Reads the IB Questionbank exports in `documents to process/MATHS/REVISION PAPERS`. A markscheme file repeats every question, part by
part, followed by its markscheme and (usually) the examiners report, so it is the main source. A paper whose markscheme file is
missing or is a copy of the question paper is read from the question paper alone and flagged `has_markscheme = false`.

Nothing is retyped: the app shows each piece as a crop of the original PDF page (`maths.render`), so diagrams, tables and notation
look exactly as printed. The text kept here is for search, hints, tagging and the error log.

Layout facts the parser relies on (checked on all 16 files):
    "N. [Maximum mark: M] REF"        question header, leftmost indent
    question text                      next indent (x0 about 84)
    "Markscheme" / "Examiners report"  deeper indent (x0 about 93); the markscheme and report lines share it
    "(a) …[3]", "(a.i) …[3]"           part lines, at the question-text indent
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "documents to process" / "MATHS" / "REVISION PAPERS"
OUT = ROOT / "data" / "maths" / "questions.json"

# doc key -> (topic number, paper, question file, markscheme file)
DOCS = {
    "na_p1": (1, "1", "Number_and_Algebra_Revision_for_HL_paper_1.pdf", "Number_and_Algebra_Revision_for_HL_paper_1_mark_scheme.pdf"),
    "na_p2": (1, "2", "HL_Number_and_Algebra_Revision_Paper_2.pdf", "HL_Number_and_Algebra_Revision_Paper_2_mark_scheme.pdf"),
    "fn_p1": (2, "1", "Functions_Revision_for_Hl_Paper_1.pdf", "Functions_Revision_for_Hl_Paper_1_mark_scheme.pdf"),
    "fn_p2": (2, "2", "HL_Functions_Revision_Paper_2.pdf", "HL_Functions_Revision_Paper_2_mark_scheme.pdf"),
    "gt_p1": (3, "1", "Geometry_and_Trigonometry_Revision_for_Hl_Paper_1.pdf", "Geometry_and_Trigonometry_Revision_for_Hl_Paper_1_mark_scheme.pdf"),
    "gt_p2": (3, "2", "HL_Geometry_and_Trigonometry_Revision_Paper_2.pdf", "HL_Geometry_and_Trigonometry_Revision_Paper_2_mark_scheme.pdf"),
    "sp_p1": (4, "1", "Statistics_and_Probability_Revision_Paper_1HL.pdf", "Statistics_and_Probability_Revision_Paper_1HL_mark_scheme.pdf"),
    "sp_p2": (4, "2", "HL_Statistics_and_Probability_Revision_Paper_2.pdf", "HL_Statistics_and_Probability_Revision_Paper_2_mark_scheme.pdf"),
}
HEADER = re.compile(r"^(\d+)\.\s*\[Maximum mark:\s*(\d+)\]\s*(\S+)?")
REF = re.compile(r"^([0-9A-Z]{3})\.([123])\.(AHL|SL|HL)\.(TZ\d)\.(\d+)$")
PART = re.compile(r"^[−\-–→\s]*\(([a-z])(?:\.([ivx]+))?\)(?:\s|$)")     # "(a) …", and "−(a.ii) →" above a vector arrow
MS_TOTAL = re.compile(r"^\[\d+ marks?\]$")
MARKS_AT_END = re.compile(r"\[(\d+)\]\s*$")
SESSIONS = {"M": "May", "N": "November"}


def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def session_of(code: str) -> str:
    if re.fullmatch(r"\d\d[MN]", code):
        return f"{SESSIONS[code[2]]} 20{code[:2]}"
    return {"EXN": "Exemplar (November)", "EXM": "Exemplar (May)", "SPM": "Specimen paper"}.get(code, code)


def read_lines(pdf_path: Path) -> tuple[list[dict], list[dict]]:
    """All text lines in reading order with their page, and each page's content box (top/bottom of text and images)."""
    import pdfplumber
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    lines, pages = [], []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            found = page.extract_text_lines(keep_blank_chars=False) or []
            tops = [l["top"] for l in found] + [im["top"] for im in page.images]
            bottoms = [l["bottom"] for l in found] + [im["bottom"] for im in page.images]
            pages.append({"width": float(page.width), "height": float(page.height),
                          "top": min(tops) if tops else 0.0, "bottom": max(bottoms) if bottoms else float(page.height)})
            for l in found:
                lines.append({"page": i, "top": float(l["top"]), "bottom": float(l["bottom"]), "x0": float(l["x0"]), "text": l["text"].strip()})
    return lines, pages


def span(lines: list[dict], start: int, end: int, pages: list[dict]) -> list[list[float]]:
    """Page regions [page, top, bottom] covering lines[start] up to (not including) lines[end]; images between them are included."""
    if start >= end:
        return []
    first = lines[start]
    stop = lines[end] if end < len(lines) else None
    out = []
    page, top = first["page"], first["top"] - 2          # tight: the line above is often only 3 pt away
    last_page = stop["page"] if stop else lines[end - 1]["page"]
    while page <= last_page:
        if stop and page == stop["page"]:
            bottom = stop["top"] - 2
        else:
            bottom = pages[page]["bottom"] + 4
        if bottom - top > 6:
            out.append([page, round(max(top, 0), 1), round(min(bottom, pages[page]["height"]), 1)])
        page += 1
        if page <= last_page:
            top = pages[page]["top"] - 4
    return out


def indents(lines: list[dict]) -> tuple[float, float]:
    """(question-text indent, markscheme indent) for one document."""
    q, m = Counter(), Counter()
    for i, l in enumerate(lines):
        if HEADER.match(l["text"]) and i + 1 < len(lines):
            q[round(lines[i + 1]["x0"])] += 1
        if l["text"] in ("Markscheme", "Examiners report"):
            m[round(l["x0"])] += 1
    qi = q.most_common(1)[0][0] if q else 84
    mi = m.most_common(1)[0][0] if m else qi + 9
    return float(qi), float(mi)


def split_questions(lines: list[dict]) -> list[tuple[int, int]]:
    starts = [i for i, l in enumerate(lines) if HEADER.match(l["text"])]
    return [(s, starts[k + 1] if k + 1 < len(starts) else len(lines)) for k, s in enumerate(starts)]


def text_of(lines: list[dict], a: int, b: int) -> str:
    return "\n".join(l["text"] for l in lines[a:b])


def header_info(lines: list[dict], s: int) -> tuple[int, int, str | None, int]:
    """(number, max marks, ref or None, index of the first line after the header)."""
    m = HEADER.match(lines[s]["text"])
    number, marks, ref = int(m.group(1)), int(m.group(2)), m.group(3)
    body = s + 1
    if not ref and body < len(lines) and REF.match(lines[body]["text"]):
        ref, body = lines[body]["text"], body + 1
    if ref and not REF.match(ref):
        ref = None
    return number, marks, ref, body


def part_label(text: str) -> str:
    """The last part marker in a block of question text: '(a) …' then '(a.i) …' gives 'a.i'."""
    label = ""
    for line in text.splitlines():
        m = PART.match(line)
        if m:
            label = m.group(1) + (f".{m.group(2)}" if m.group(2) else "")
    return label


def part_marks(text: str) -> int | None:
    found = [int(m.group(1)) for line in text.splitlines() if (m := MARKS_AT_END.search(line))]
    return found[-1] if found else None


def parse_with_markscheme(lines: list[dict], pages: list[dict]) -> list[dict]:
    """Questions from a markscheme file: alternating runs of question text (Q) and markscheme/report text (M)."""
    q_indent, m_indent = indents(lines)
    threshold = (q_indent + m_indent) / 2
    out = []
    for s, e in split_questions(lines):
        number, marks, ref, body = header_info(lines, s)
        parts, i = [], body
        while i < e:
            # question text run: until a "Markscheme" line
            q_start = i
            while i < e and lines[i]["text"] != "Markscheme":
                i += 1
            if i >= e:          # trailing question text with no markscheme (rare): keep it as context of the last part
                if parts:
                    parts[-1]["q_spans"] += span(lines, q_start, e, pages)
                break
            q_end = i
            # markscheme run: every block ends with its "[n marks]" line. Indentation alone is not enough: the entries of column
            # vectors and matrices sit at the question indent. Without a total line, fall back to the indent rule.
            ms_start = i
            i += 1
            total_at = next((j for j in range(i, e) if MS_TOTAL.match(lines[j]["text"]) or lines[j]["text"] in ("Markscheme", "Examiners report")), None)
            if total_at is not None and MS_TOTAL.match(lines[total_at]["text"]):
                i = total_at + 1
            else:
                while i < e and lines[i]["text"] != "Examiners report" and not (lines[i]["x0"] < threshold and lines[i]["text"] != "Markscheme"):
                    i += 1
            ms_end = i
            rep_start = rep_end = None
            if i < e and lines[i]["text"] == "Examiners report":
                rep_start = i
                i += 1
                while i < e and not (lines[i]["x0"] < threshold):
                    i += 1
                rep_end = i
            q_text = text_of(lines, q_start, q_end)
            part = {
                "label": part_label(q_text),
                "marks": part_marks(q_text),
                "q_text": q_text,
                "ms_text": text_of(lines, ms_start + 1, ms_end),
                "report_text": text_of(lines, rep_start + 1, rep_end) if rep_start is not None else "",
                "q_spans": span(lines, q_start, q_end, pages),
                "ms_spans": span(lines, ms_start + 1, ms_end, pages),
                "report_spans": span(lines, rep_start + 1, rep_end, pages) if rep_start is not None else [],
            }
            if not parts:   # the first part's question text starts just under the header, with the ref line skipped
                part["q_spans"] = span(lines, body, q_end, pages)
            parts.append(part)
        merged = []
        for part in parts:             # "(b) Find" with no marks and no markscheme of its own is context for (b.i), (b.ii)
            if merged and merged[-1]["marks"] is None:
                prev = merged.pop()
                part = {**part, "q_text": prev["q_text"] + chr(10) + part["q_text"], "q_spans": prev["q_spans"] + part["q_spans"],
                        "ms_spans": prev["ms_spans"] + part["ms_spans"], "ms_text": (prev["ms_text"] + chr(10) + part["ms_text"]).strip()}
            merged.append(part)
        parts = merged
        if len(parts) == 1 and parts[0]["marks"] is None:
            parts[0]["marks"] = marks
        out.append({"number": number, "max_marks": marks, "ref": ref, "parts": parts, "has_markscheme": True,
                    "q_spans": [sp for p in parts for sp in p["q_spans"]]})
    return out


def parse_questions_only(lines: list[dict], pages: list[dict]) -> list[dict]:
    """Questions from a question paper (no markscheme): parts split at their markers, answer space left out where it can be."""
    out = []
    for s, e in split_questions(lines):
        number, marks, ref, body = header_info(lines, s)
        starts = [i for i in range(body, e) if PART.match(lines[i]["text"])]
        cuts = [body] + [i for i in starts if i > body]
        parts = []
        for k, a in enumerate(cuts):
            b = cuts[k + 1] if k + 1 < len(cuts) else e
            q_text = text_of(lines, a, b)
            label = part_label(q_text)
            mk = part_marks(q_text)
            if parts and not mk and not label:
                continue
            if parts and parts[-1]["marks"] is None:      # a context part like "(a) Calculate … if he chooses" joins the next one
                prev = parts.pop()
                q_text = prev["q_text"] + "\n" + q_text
                spans = prev["q_spans"] + span(lines, a, b, pages)
            else:
                spans = span(lines, a, b, pages)
            parts.append({"label": label, "marks": mk, "q_text": q_text, "ms_text": "", "report_text": "",
                          "q_spans": spans, "ms_spans": [], "report_spans": []})
        if len(parts) == 1 and parts[0]["marks"] is None:
            parts[0]["marks"] = marks
        out.append({"number": number, "max_marks": marks, "ref": ref, "parts": parts, "has_markscheme": False,
                    "q_spans": [sp for p in parts for sp in p["q_spans"]]})
    return out


def build(docs: dict = DOCS) -> dict:
    from ingest.maths_tagging import tag_question
    questions: dict[str, dict] = {}
    report = {"documents": [], "problems": []}
    for key, (topic, paper, qfile, msfile) in docs.items():
        qpath, mspath = PAPERS / qfile, PAPERS / msfile
        ms_ok = mspath.exists() and qpath.exists() and file_md5(mspath) != file_md5(qpath)
        if mspath.exists() and not ms_ok:
            report["problems"].append(f"{msfile} is an identical copy of {qfile}: no markscheme for this paper")
        source, path = ("ms", mspath) if ms_ok else ("q", qpath)
        lines, pages = read_lines(path)
        parsed = parse_with_markscheme(lines, pages) if ms_ok else parse_questions_only(lines, pages)
        doc_entry = {"key": key, "topic": topic, "paper": paper, "file": str(path.relative_to(ROOT)), "source": source,
                     "questions": len(parsed), "has_markscheme": ms_ok, "pages": [[p["width"], p["height"]] for p in pages]}
        report["documents"].append(doc_entry)
        for q in parsed:
            ref = q["ref"]
            qid = ref or f"{key}.{q['number']}"
            m = REF.match(ref) if ref else None
            sess = m.group(1) if m else None
            entry = {
                "id": qid, "ref": ref, "doc": key, "source": source, "number": q["number"], "topic": topic,
                "paper": m.group(2) if m else paper, "level": m.group(3) if m else "AHL", "session_code": sess,
                "session": session_of(sess) if sess else "Unknown session", "max_marks": q["max_marks"],
                "has_markscheme": q["has_markscheme"], "parts": q["parts"], "q_spans": q["q_spans"],
                "also_in": [],
            }
            if any(not p["marks"] for p in entry["parts"]):
                report["problems"].append(f"{qid}: a part has no mark total")
            if sum(p["marks"] or 0 for p in entry["parts"]) != q["max_marks"]:
                report["problems"].append(f"{qid}: part marks add to {sum(p['marks'] or 0 for p in entry['parts'])}, header says {q['max_marks']}")
            entry.update(tag_question(entry))
            if qid in questions:          # same question in two revision papers: keep the copy with a markscheme
                old = questions[qid]
                keep, other = (old, entry) if old["has_markscheme"] or not entry["has_markscheme"] else (entry, old)
                keep["also_in"] = sorted({*keep["also_in"], other["doc"]})
                questions[qid] = keep
            else:
                questions[qid] = entry
    return {"questions": list(questions.values()), "report": report}


def main() -> None:
    result = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    qs = result["questions"]
    print(f"{len(qs)} questions, {sum(len(q['parts']) for q in qs)} parts, {sum(q['max_marks'] for q in qs)} marks -> {OUT}")
    for d in result["report"]["documents"]:
        print(f"  {d['key']}: {d['questions']} questions ({'markscheme' if d['has_markscheme'] else 'NO markscheme'})")
    print(f"  {len(result['report']['problems'])} problems")
    for p in result["report"]["problems"][:40]:
        print("   -", p)


if __name__ == "__main__":
    main()
