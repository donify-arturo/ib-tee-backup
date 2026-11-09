"""
The course book's teaching, passage by passage, tagged with sub-topics → data/maths/book_passages.json
The publisher's corrections file, row by row, attached to what it corrects → data/maths/book_corrections.json

    python -m ingest.maths_book_passages        (after ingest.maths_book_questions)

Each chapter is cut at its own headings (sub-headings, Example, Investigation, Developing inquiry, Chapter summary), leaving out only the
exercise questions, which are saved on their own. Nothing is rewritten: only where each passage is on the PDF pages is stored, and the
app shows crops of the student's own copy, side notes included. Private study only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "maths" / "book_passages.json"
CORRECTIONS = ROOT / "data" / "maths" / "book_corrections.json"


def lines_of(ws: list[dict]) -> list[list[dict]]:
    rows: dict[int, list[dict]] = {}
    for w in ws:
        rows.setdefault(round(w["top"] / 4), []).append(w)
    return [sorted(v, key=lambda x: x["x0"]) for _k, v in sorted(rows.items())]


def heading_of(line: list[dict]) -> tuple[str, str] | None:
    """(kind, title) if this line is a heading of the book."""
    big = [w for w in line if w["size"] >= 23.5 and "Symbol" not in w["fontname"]]
    if big and sum(c.isalpha() for w in big for c in w["text"]) >= 3:
        title = " ".join(w["text"] for w in big)
        kind = ("investigation" if title.startswith("Investigation") else "example" if title.startswith("Example") else "inquiry" if title.startswith("Developing inquiry")
                else "summary" if title.startswith("Chapter summary") else "review" if title.startswith("Chapter review") else "note")
        return kind, title
    text = " ".join(w["text"] for w in line)
    if line[0]["text"] == "Exercise" and line[0]["size"] >= 18.5 and re.match(r"Exercise \d+[A-Z]", text):
        return "exercise", text
    return None


def passages_of(pdf, cache: dict, chapter: dict, sections: list[dict], questions: list[dict], score_fn) -> list[dict]:
    from ingest.maths_book_questions import BOTTOM_MARGIN, LEFT, TOP_MARGIN, body, words
    marks: list[dict] = []
    section_top: dict[str, float] = {}
    for p in range(chapter["pdf_start"], chapter["pdf_end"] + 1):
        ws = body(words(pdf, cache, p), LEFT[p % 2])
        for line in lines_of(ws):
            h = heading_of(line)
            if h:
                marks.append({"p": p, "t": line[0]["top"], "kind": h[0], "title": h[1], "size": line[0]["size"]})
                sec = next((s for s in sections if s["pdf_start"] == p), None)
                if sec and line[0]["size"] >= 30 and sec["code"] not in section_top:
                    section_top[sec["code"]] = line[0]["top"]
    marks.sort(key=lambda m: (m["p"], m["t"]))
    # merge headings printed over two lines
    merged: list[dict] = []
    for m in marks:
        if merged and merged[-1]["p"] == m["p"] and m["t"] - merged[-1].get("last_t", merged[-1]["t"]) < 50 and merged[-1]["kind"] == m["kind"] == "note":
            merged[-1]["title"] += " " + m["title"]
            merged[-1]["last_t"] = m["t"]
        else:
            merged.append(m)
    # where an exercise's questions end, the book's text may carry on with no heading
    flow: list[dict] = []
    for m in merged:
        flow.append(m)
        if m["kind"] == "exercise":
            name = m["title"].split()[1].rstrip(".:")
            mine = [s for q in questions if q["exercise"] == name for s in q["spans"]]
            if mine:
                last_page = max(s[0] for s in mine)
                flow.append({"p": last_page, "t": max(s[2] for s in mine if s[0] == last_page) + 4, "kind": "note", "title": "", "size": 0})
    flow.sort(key=lambda m: (m["p"], m["t"]))
    flow.insert(0, {"p": chapter["pdf_start"], "t": TOP_MARGIN, "kind": "note", "title": chapter.get("title", ""), "size": 0})
    out: list[dict] = []
    counts: dict[str, int] = {}
    previous: list[str] = []
    for i, m in enumerate(flow):
        if m["kind"] == "review":             # the review and everything after it is a question set: it has its own view of whole pages
            break
        if m["kind"] == "exercise":
            continue
        nxt = flow[i + 1] if i + 1 < len(flow) else {"p": chapter["pdf_end"], "t": BOTTOM_MARGIN}
        spans, text = [], []
        for p in range(m["p"], nxt["p"] + 1):
            top = m["t"] - 3 if p == m["p"] else TOP_MARGIN
            bottom = nxt["t"] - 4 if p == nxt["p"] else BOTTOM_MARGIN
            ws = [w for w in body(words(pdf, cache, p), LEFT[p % 2]) if top <= w["top"] <= bottom]
            if len(ws) < 3 or bottom - top < 12:
                continue
            spans.append([p, round(top, 1), round(bottom, 1), round(LEFT[p % 2] - 16, 1), round(LEFT[p % 2] + 742, 1)])
            text += [w["text"] for w in ws]
        if not spans:
            continue
        p0, t0 = spans[0][0], spans[0][1]
        section = None
        for s in sections:
            start_top = section_top.get(s["code"], 0)
            if (s["pdf_start"], start_top) <= (p0, t0 + 3):
                section = s
        section = section or sections[0]
        allowed = section["subtopics"]
        blob = " ".join(text)
        if m["kind"] == "summary":
            allowed = list(dict.fromkeys(c for s in sections for c in s["subtopics"]))
        tags = allowed
        if len(allowed) > 1:
            sc = score_fn(m["title"] + "\n" + m["title"], blob)
            ranked = sorted(((sc.get(c, 0), c) for c in allowed), reverse=True)
            hits = [c for v, c in ranked if v >= max(2, ranked[0][0] * 0.5)]
            tags = hits or previous or allowed
        previous = tags
        counts[m["kind"]] = counts.get(m["kind"], 0) + 1
        number = re.search(r"(\d+)\s*$", m["title"])
        title = m["title"] or "Continued"
        out.append({"id": f"{chapter['n']}.P{i}", "kind": m["kind"], "title": title, "number": int(number.group(1)) if number and m["kind"] in ("example", "investigation") else None,
                    "chapter": chapter["n"], "section": section["code"], "spans": spans, "subtopics": tags})
    return out


def corrections(path: Path) -> list[dict]:
    """Rows of the publisher's table: the printed page, what it refers to, and where the row is, so the app can show it as printed."""
    import pdfplumber
    out = []
    columns = None
    chapter = None
    with pdfplumber.open(str(path)) as pdf:
        for p, page in enumerate(pdf.pages):
            ws = sorted(page.extract_words(), key=lambda w: (round(w["top"] / 3), w["x0"]))
            rows = lines_of([{**w, "size": 0, "fontname": ""} for w in ws])
            starts: list[tuple[float, int, str]] = []
            for line in rows:
                text = " ".join(w["text"] for w in line)
                m = re.match(r"Chapter (\d+)\b", text)
                if m and len(line) <= 4:
                    chapter = int(m.group(1))
                names = {w["text"]: w["x0"] for w in line}
                if {"Section", "Page", "Correction"} <= set(names):
                    columns = (names["Page"], names.get("Exercise", names["Page"] + 60), names["Correction"])
                    continue
                if not columns:
                    continue
                page_word = next((w for w in line if abs(w["x0"] - columns[0]) < 28 and w["text"].isdigit()), None)
                if page_word:
                    starts.append((line[0]["top"], int(page_word["text"]), chapter))
            for i, (top, printed, ch) in enumerate(starts):
                bottom = starts[i + 1][0] - 2 if i + 1 < len(starts) else min(float(page.height) - 40, max(w["bottom"] for w in ws))
                ref_words = [w["text"] for w in ws if top - 2 <= w["top"] < bottom and columns[1] - 6 <= w["x0"] < columns[2] - 6]
                ref_text = " ".join(ref_words)
                out.append({"chapter": ch, "printed": printed, "ref": ref_text, "key": key_of(ref_text, ch), "page": p, "top": round(top - 3, 1), "bottom": round(bottom, 1)})
    return out


def key_of(ref: str, chapter: int | None) -> str | None:
    m = re.search(r"(\d+)\s*([A-Za-z])\s*,\s*Q?\s*(\d+)", ref)
    if m:
        letter = m.group(2)
        letter = "I" if letter == "l" else letter.upper()
        return f"{m.group(1)}{letter}.{m.group(3)}"
    m = re.search(r"Example\s+(\d+)", ref)
    if m and chapter:
        return f"{chapter}.Example{m.group(1)}"
    m = re.search(r"Investigation\s+(\d+)", ref)
    if m and chapter:
        return f"{chapter}.Investigation{m.group(1)}"
    return None


def main() -> None:
    import pdfplumber

    from ingest.maths_tagging import scores
    from maths import data, render
    book = data.book()
    questions = data.book_questions()
    result: list[dict] = []
    cache: dict = {}
    with pdfplumber.open(str(render.documents()["book"])) as pdf:
        for chapter in book["chapters"]:
            secs = [s for s in book["sections"] if s["chapter"] == chapter["n"]]
            found = passages_of(pdf, cache, chapter, secs, questions, scores)
            result += found
            print(f"  chapter {chapter['n']}: {len(found)} passages", flush=True)
    # a section's sub-topic must never end up with nothing to read: give it the section's teaching
    for sec in book["sections"]:
        here = [p for p in result if p["section"] == sec["code"]]
        for code in sec["subtopics"]:
            if not any(code in p["subtopics"] for p in here):
                for p in here:
                    if p["kind"] in ("note", "example", "investigation", "summary"):
                        p["subtopics"].append(code)
    OUT.write_text(json.dumps({"passages": result}, ensure_ascii=False, indent=0), encoding="utf-8")
    folder = ROOT / "documents to process" / "MATHS" / "WORKED ANSWERS"
    path = next(folder.rglob("Updates_and_corrections*.pdf"))
    rows = corrections(path)
    CORRECTIONS.write_text(json.dumps({"file": str(path.relative_to(ROOT)), "rows": rows}, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(result)} passages, {len({c for p in result for c in p['subtopics']})} sub-topics; {len(rows)} corrections, {sum(1 for r in rows if r['key'])} tied to a question, example or investigation")


if __name__ == "__main__":
    main()
