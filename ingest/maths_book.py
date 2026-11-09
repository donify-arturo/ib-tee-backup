"""
The Oxford Mathematics: applications and interpretation HL course book (2019) → data/maths/book.json

    python -m ingest.maths_book

Indexes the student's PDF so the app can show real book pages: chapters and sections from the table of contents (printed page →
PDF page), where each exercise starts, and which syllabus sub-topics each section teaches. Pages are shown as images of the PDF
(maths/render.py), never retyped. Private study only.

Sub-topics per section: the keyword rules of ingest/maths_tagging.py, run on the section title and its first pages, limited to the
sub-topics the chapter covers (ingest/maths_syllabus.CHAPTERS). Fix a section by hand in SECTION_OVERRIDES.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "documents to process" / "MATHS" / "WORKED ANSWERS"
OUT = ROOT / "data" / "maths" / "book.json"
# Sub-topics checked by hand against the section titles, where the keyword rules missed or over-reached.
SECTION_OVERRIDES: dict[str, list[str]] = {
    "1.1": ["1.1", "1.6"], "1.2": ["3.2", "3.3", "3.4"], "2.1": ["4.1"], "2.2": ["4.3"], "2.3": ["4.2"],
    "3.4": ["3.10", "3.12"], "4.1": ["2.2", "2.3", "2.4", "2.6"], "4.2": ["2.1", "2.5", "2.6"], "5.1": ["4.5"], "6.1": ["2.4", "2.5"],
    "6.2": ["2.5", "2.8", "1.8"], "6.4": ["2.5", "4.13", "2.10"], "7.1": ["1.3", "1.11"], "7.2": ["1.4", "1.7"], "7.3": ["1.5", "2.5", "2.9"], "7.4": ["1.5", "1.9", "1.10"],
    "8.1": ["3.7", "3.8"], "8.2": ["2.9", "3.8"], "8.3": ["1.12"], "8.4": ["1.12", "1.13"], "8.5": ["1.13", "2.9"], "10.1": ["5.1", "5.2", "5.3", "5.4"],
    "10.3": ["5.6", "5.7", "5.10", "5.13"], "11.1": ["5.8", "5.5"], "11.4": ["5.14"], "11.5": ["5.15", "5.16"],
    "12.1": ["3.12", "3.13"], "12.2": ["3.12", "5.13"], "12.3": ["5.17", "1.15"], "12.4": ["5.16", "5.17", "5.18"],
    "13.1": ["4.7"], "13.2": ["4.8"], "13.3": ["4.17"], "13.4": ["4.9", "4.15"], "13.5": ["4.14"], "13.6": ["4.14", "4.15"],
    "14.3": ["4.18", "4.11", "4.16"], "14.6": ["4.12", "4.18"], "15.1": ["3.14"],
}
# Printed pages the contents text garbles (checked against the page headings).
CHAPTER_PRINTED = {12: 533, 13: 570}
SECTION_PRINTED = {"13.1": 572, "13.2": 581, "13.3": 587, "13.4": 593, "13.5": 601, "13.6": 604}
SECTION_TITLES = {"13.1": "Modelling random behaviour", "13.2": "Modelling the number of successes in a fixed number of trials",
                  "13.3": "Modelling the number of successes in a fixed interval", "13.4": "Modelling measurements that are distributed randomly",
                  "13.5": "Mean and variance of transformed or combined random variables", "13.6": "Distributions of combined random variables"}


def find_pdf() -> Path | None:
    hits = [p for p in FOLDER.rglob("*.pdf") if "book" in p.name.lower() and "worked" not in p.name.lower() and "correction" not in p.name.lower()]
    return max(hits, key=lambda p: p.stat().st_size) if hits else None


def page_texts(pdf: Path) -> list[str]:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    out = [doc[i].get_textpage().get_text_range().replace("\r\n", "\n").replace("\r", "\n") for i in range(len(doc))]
    doc.close()
    return out


def printed_offset(texts: list[str]) -> int:
    """PDF index minus printed page number, from pages whose first line is their printed number."""
    votes: dict[int, int] = {}
    for i, t in enumerate(texts[10:200], 10):
        m = re.match(r"\s*/?\s*(\d{1,3})\s*\n", t)
        if m:
            votes[i - int(m.group(1))] = votes.get(i - int(m.group(1)), 0) + 1
    return max(votes, key=votes.get) if votes else 0


def parse_toc(texts: list[str]) -> tuple[list[dict], list[dict]]:
    """Chapters and sections from the contents pages (the first pages that list "1.1 … 4" style entries)."""
    toc = "\n".join(texts[3:9])
    flat = re.sub(r"\s*\n\s*", " ", toc)
    sections = []
    for m in re.finditer(r"(?<![\d.])(\d{1,2})\.(\d)\s+(.+?)\s*\.{0,}\s*(\d{1,3})(?=\s+(?:\d{1,2}\.\d\s|\d{1,2}\s+[A-Z]|Chapter review|Modelling|Paper 3|Digital|Syllabus|Practice|Worked|$))", flat):
        ch, sec, title, page = int(m.group(1)), int(m.group(2)), m.group(3).strip(" .…"), int(m.group(4))
        if ch <= 15 and len(title) > 3 and not any(s["code"] == f"{ch}.{sec}" for s in sections):
            sections.append({"code": f"{ch}.{sec}", "chapter": ch, "title": re.sub(r"\.{2,}.*$", "", title).strip(), "printed": page})
    chapters = []
    for m in re.finditer(r"(?<![\d.])(\d{1,2})\s+([A-Z][A-Za-z ,:’'\-–χ2]+?)\s*(\d{1,3})(?=\s+\1\.1\s)", flat):
        chapters.append({"n": int(m.group(1)), "title": m.group(2).strip(), "printed": int(m.group(3))})
    return chapters, sorted(sections, key=lambda s: (s["chapter"], int(s["code"].split(".")[1])))


def build() -> dict:
    from ingest.maths_syllabus import CHAPTERS
    from ingest.maths_tagging import scores
    pdf = find_pdf()
    if not pdf:
        raise SystemExit(f"No course book PDF found in {FOLDER}")
    texts = page_texts(pdf)
    offset = printed_offset(texts)
    chapters, sections = parse_toc(texts)
    # chapter titles the contents split oddly: take them from the worked-solutions index when missing
    syl = json.loads((ROOT / "data" / "maths" / "syllabus.json").read_text(encoding="utf-8"))
    ws_titles = {c["chapter"]: c["title"] for c in syl.get("worked_solutions", [])}
    known = {c["n"] for c in chapters}
    for n in sorted({s["chapter"] for s in sections} - known):
        first = min(s["printed"] for s in sections if s["chapter"] == n)
        chapters.append({"n": n, "title": ws_titles.get(n, f"Chapter {n}"), "printed": first - 2})
    for c in chapters:
        c["printed"] = CHAPTER_PRINTED.get(c["n"], c["printed"])
    for code, page in SECTION_PRINTED.items():
        sec = next((x for x in sections if x["code"] == code), None)
        if not sec:
            sec = {"code": code, "chapter": int(code.split(".")[0]), "title": SECTION_TITLES[code], "printed": page}
            sections.append(sec)
        sec["printed"], sec["title"] = page, SECTION_TITLES.get(code, sec["title"])
    sections.sort(key=lambda x: (x["chapter"], int(x["code"].split(".")[1])))
    chapters.sort(key=lambda c: c["n"])
    answers = next((i for i, t in enumerate(texts) if i > 700 and re.match(r"\s*/?\s*\d+\s*\nANSWERS", t)), len(texts))
    # exercises: the first page where "Exercise 7A" appears inside its chapter
    starts = {c["n"]: c["printed"] + offset for c in chapters}
    ends = {n: (starts[m] - 1 if (m := next((x for x in sorted(starts) if x > n), None)) else answers - 1) for n in starts}
    for c in chapters:
        c["pdf_start"], c["pdf_end"] = starts[c["n"]], ends[c["n"]]
        c["exercises"] = {}
        for i in range(c["pdf_start"], c["pdf_end"] + 1):
            for m in re.finditer(rf"Exercise ({c['n']}[A-Z])\b", texts[i]):
                c["exercises"].setdefault(m.group(1), i)
        review = next((i for i in range(c["pdf_start"], c["pdf_end"] + 1) if re.search(r"Chapter review", texts[i][:200])), None)
        c["review_page"] = review
    for s in sections:
        s["pdf_start"] = s["printed"] + offset
    for k, s in enumerate(sections):
        nxt = sections[k + 1] if k + 1 < len(sections) and sections[k + 1]["chapter"] == s["chapter"] else None
        ch = next(c for c in chapters if c["n"] == s["chapter"])
        s["pdf_end"] = (nxt["pdf_start"] - 1) if nxt else ((ch["review_page"] - 1) if ch["review_page"] else ch["pdf_end"])
        s["exercises"] = sorted((e for e, p in ch["exercises"].items() if s["pdf_start"] <= p <= s["pdf_end"]))
        allowed = CHAPTERS.get(s["chapter"], [])
        body = "\n".join(texts[s["pdf_start"]:min(s["pdf_end"], s["pdf_start"] + 3) + 1])
        sc = scores(s["title"] + "\n" + s["title"], body)          # the title counts double
        ranked = sorted(((v, c) for c, v in sc.items() if c in allowed), reverse=True)
        top = ranked[0][0] if ranked else 0
        s["subtopics"] = SECTION_OVERRIDES.get(s["code"]) or [c for v, c in ranked if v >= max(4, top * 0.45)][:4]
    return {"file": str(pdf.relative_to(ROOT)), "title": "Mathematics: applications and interpretation HL (Oxford, 2019)",
            "pages": len(texts), "offset": offset, "answers_page": answers, "chapters": chapters, "sections": sections}


def main() -> None:
    book = build()
    OUT.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{book['pages']} pages, offset {book['offset']}, {len(book['chapters'])} chapters, {len(book['sections'])} sections -> {OUT}")
    for s in book["sections"]:
        print(f"  {s['code']:>5} p{s['printed']:>3} (pdf {s['pdf_start']}-{s['pdf_end']}) ex {','.join(s['exercises']) or '-':<14} {s['subtopics']}  {s['title'][:50]}")


if __name__ == "__main__":
    main()
