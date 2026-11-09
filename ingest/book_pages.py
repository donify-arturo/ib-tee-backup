"""
Page text from the full Oxford Course Companion and its answer booklet, by sub-topic, for private revision notes and Foundations.

    python -m ingest.book_pages        (writes data/books/companion/<code>.json with the chapter's pages and answers)

The PDFs are digital, so this needs no OCR. Nothing here is shown to the student: it is the source the builders summarise from.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "documents to process"
BOOK = FOLDER / "Chemistry - Course Companion - Bylikin, Horner, Grant and Tarcy - Oxford 2023.pdf"
ANSWERS = FOLDER / "Chemistry - Course Companion - Bylikin, Horner, Grant and Tarcy - Oxford 2023.pdf ANSWERS.pdf"
OUT = ROOT / "data" / "books" / "companion"

_RUNNING_HEAD = re.compile(r"^\s*(Structure|Reactivity)\s+(\d\.\d)\s+[A-Z]", re.M)
_ANSWER_HEAD = re.compile(r"^\s*(Practice questions?|End of topic questions|Activity|Data-based questions?|Worked examples?|Skills questions?|Approaches to learning (?:questions?|activity)|ATL questions?|Skills|Questions?)\s*\((?:pages?|p\.?)\s*(\d{1,3})", re.I | re.M)
_PRINTED = re.compile(r"(?:^|\n)\s*(\d{1,3})\s*(?:\r?\n|$)")
_CODE = {"Structure": "S", "Reactivity": "R"}


def page_texts(path: Path) -> list[str]:
    doc = pdfium.PdfDocument(str(path))
    return [doc[i].get_textpage().get_text_range().replace("\r\n", "\n").replace("", "fi").replace("", " ").replace("", "ff") for i in range(len(doc))]


def chapter_starts(pages: list[str], first_body_page: int = 12) -> dict[str, int]:
    """First PDF index whose running head names each sub-topic. The contents pages come before first_body_page."""
    starts: dict[str, int] = {}
    for i, text in enumerate(pages):
        if i < first_body_page:
            continue
        head = _RUNNING_HEAD.search(text[:250])
        if head:
            starts.setdefault(_CODE[head.group(1)] + head.group(2), i)
    return starts


_TOOLS_HEAD = re.compile(r"^\s*Tool \d: ", re.M)


def _head(text: str) -> str:
    """A page's running head: the first line that isn't its printed page number."""
    lines = [l.strip() for l in text.splitlines()[:3] if l.strip() and not l.strip().isdigit()]
    return lines[0] if lines else ""


def chapter_end(pages: list[str], code: str, first: int, limit: int) -> int:
    """Last page of a sub-topic: the page before the next chapter, unless the book's skills chapter ("Tools for Chemistry") starts
    first. Running heads can't mark the end themselves: HL pages, theme pages and end-of-topic pages carry other heads."""
    for i in range(first + 1, limit + 1):
        if _head(pages[i]).startswith(("Tool ", "Tools for Chemistry")):
            end = i - 1
            while end > first and _head(pages[end]) == "Introduction":
                end -= 1
            return end
    return limit


def page_offset(pages: list[str]) -> int:
    """PDF index minus printed page number: the most common difference over the book, since printed numbers sit at a page's edge."""
    votes: dict[int, int] = {}
    for i, text in enumerate(pages):
        for number in _PRINTED.findall(text):
            gap = i - int(number)
            if 0 <= gap < 40:
                votes[gap] = votes.get(gap, 0) + 1
    return max(votes, key=votes.get) if votes else 0


def split_answers(pages: list[str]) -> list[dict]:
    """[{kind, page, text}]: each answer block with the printed book page it refers to."""
    blocks: list[dict] = []
    text = "\n".join(re.sub(r"^©[^\n]*\n", "", p) for p in pages)
    marks = list(_ANSWER_HEAD.finditer(text))
    for mark, following in zip(marks, marks[1:] + [None]):
        end = following.start() if following else len(text)
        blocks.append({"kind": mark.group(1).lower(), "page": int(mark.group(2)), "text": text[mark.end():end].strip()})
    return blocks


def build(book: Path = BOOK, answers: Path = ANSWERS, out: Path = OUT) -> dict[str, dict]:
    pages = page_texts(book)
    offset = page_offset(pages)
    starts = chapter_starts(pages)
    order = sorted(starts.items(), key=lambda x: x[1])
    blocks = split_answers(page_texts(answers))
    result = {}
    out.mkdir(parents=True, exist_ok=True)
    tools_start = None
    for (code, first), following in zip(order, order[1:] + [(None, None)]):
        limit = following[1] - 1 if following[1] is not None else min(first + 30, len(pages) - 1)
        last = chapter_end(pages, code, first, limit)
        if last < limit and tools_start is None and _TOOLS_HEAD.search("\n".join(pages[last + 1:limit + 1])[:20000]):
            tools_start, tools_end = last + 1, limit           # the book's skills chapter sits between two sub-topics
        printed = (first - offset, last - offset)
        chapter = {"code": code, "pdf_pages": [first + 1, last + 1], "printed_pages": list(printed),
                   "pages": [{"printed": i - offset, "text": pages[i]} for i in range(first, last + 1)],
                   "answers": [b for b in blocks if printed[0] <= b["page"] <= printed[1]]}
        (out / f"{code}.json").write_text(json.dumps(chapter, ensure_ascii=False), encoding="utf-8")
        result[code] = chapter
        print(code, "pdf", chapter["pdf_pages"], "printed", chapter["printed_pages"], "| answer blocks", len(chapter["answers"]),
              "| chars", sum(len(p["text"]) for p in chapter["pages"]))
    if tools_start is not None:                                # kept apart: lab skills, not a sub-topic's content
        printed = (tools_start - offset, tools_end - offset)
        tools = {"code": "TOOLS", "pdf_pages": [tools_start + 1, tools_end + 1], "printed_pages": list(printed),
                 "pages": [{"printed": i - offset, "text": pages[i]} for i in range(tools_start, tools_end + 1)],
                 "answers": [b for b in blocks if printed[0] <= b["page"] <= printed[1]]}
        (out / "TOOLS.json").write_text(json.dumps(tools, ensure_ascii=False), encoding="utf-8")
        print("TOOLS pdf", tools["pdf_pages"], "printed", tools["printed_pages"], "| answer blocks", len(tools["answers"]))
    return result


if __name__ == "__main__":
    build()
