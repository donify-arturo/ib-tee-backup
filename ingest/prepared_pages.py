"""
Page text from Oxford "IB Prepared: Chemistry" (2024) and its online answers, by sub-topic, for Foundations.

    python -m ingest.prepared_pages     (writes data/books/prepared/<code>.json, plus T1-T3, IA and EXAM)

The PDF's text layer is OCR, so formulas and superscripts are often garbled: builders must read through that, and every number
they keep is checked against these pages. The answers come from the publisher's Word files (practice problems, exam papers).
The book's licence excludes text and data mining; the student chose to use their own copy anyway, for private study only.
Nothing is reprinted: builders paraphrase and cite page numbers.
"""
from __future__ import annotations

import html
import json
import re
import zipfile
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "documents to process"
BOOK = FOLDER / "Chemistry - IB Prepared - Sergey Bylikin - Oxford 2024.pdf"
ANSWERS = FOLDER / "IB PREPARED" / "ANSWERS" / "IB-Prepared-Chemistry-Practice-Problems-Answers.docx"
EXAM_ANSWERS = FOLDER / "IB PREPARED" / "ANSWERS" / "IB-Prepared-Chemistry-Practice-Exam-Papers-Answers.docx"
OUT = ROOT / "data" / "books" / "prepared"
OFFSET = 8                       # PDF page number minus printed page number (printed page 93 is PDF page 101)

# Printed start pages, from the contents page. Each part runs to the next part's first page (one page of overlap, since
# chapters start mid-page).
STARTS = [("S1.1", 2), ("S1.2", 5), ("S1.3", 8), ("S1.4", 14), ("S1.5", 19), ("S2.1", 23), ("S2.2", 27), ("S2.3", 47), ("S2.4", 50),
          ("S3.1", 57), ("S3.2", 71), ("R1.1", 93), ("R1.2", 99), ("R1.3", 107), ("R1.4", 114), ("R2.1", 121), ("R2.2", 127),
          ("R2.3", 139), ("R3.1", 145), ("R3.2", 161), ("R3.3", 177), ("R3.4", 179), ("T1", 187), ("T2", 205), ("T3", 209),
          ("IA", 229), ("EXAM", 235), ("INDEX", 244)]

_THEME = re.compile(r"^(Structure|Reactivity|Tool)\s*(\d)\s*[—–-]")
_SUB = re.compile(r"^(\d)\.(\d)\s+[A-Za-z]")


def page_texts(path: Path = BOOK) -> list[str]:
    doc = pdfium.PdfDocument(str(path))
    return [doc[i].get_textpage().get_text_range().replace("\r\n", "\n") for i in range(len(doc))]


def docx_paragraphs(path: Path) -> list[str]:
    """Plain text of each non-empty paragraph, table cells included, in document order. Images (structures, graphs) are lost."""
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    out = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para))).strip()
        if text:
            out.append(text)
    return out


def split_answers(paragraphs: list[str]) -> dict[str, str]:
    """{'R1.1': text}: the answers file is grouped under theme headings ('Reactivity 1—...') and sub-topic headings ('1.1 ...')."""
    out: dict[str, list[str]] = {}
    theme, code = None, None
    for line in paragraphs:
        head = _THEME.match(line)
        if head:
            theme, code = {"Structure": "S", "Reactivity": "R", "Tool": "T"}[head.group(1)] + head.group(2), None
            if theme.startswith("T"):
                code = theme
            continue
        sub = _SUB.match(line)
        if sub and theme and not theme.startswith("T") and sub.group(1) == theme[1] and len(line) < 90:
            code = f"{theme}.{sub.group(2)}"
            continue
        if code:
            out.setdefault(code, []).append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def build(book: Path = BOOK, out: Path = OUT) -> dict[str, dict]:
    pages = page_texts(book)
    answers = split_answers(docx_paragraphs(ANSWERS)) if ANSWERS.exists() else {}
    exam = "\n".join(docx_paragraphs(EXAM_ANSWERS)) if EXAM_ANSWERS.exists() else ""
    out.mkdir(parents=True, exist_ok=True)
    result = {}
    for (code, first), (_, following) in zip(STARTS, STARTS[1:]):
        printed = list(range(first, following + 1)) if code != "EXAM" else list(range(first, following))
        part = {"code": code, "book": "Oxford IB Prepared Chemistry 2024", "printed_pages": [printed[0], printed[-1]],
                "pages": [{"printed": n, "text": pages[n + OFFSET - 1]} for n in printed if 0 <= n + OFFSET - 1 < len(pages)],
                "answers": answers.get(code, "") if code != "EXAM" else exam}
        (out / f"{code}.json").write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")
        result[code] = part
        print(f"{code:<5} printed {part['printed_pages']} | answers {len(part['answers']):>6} chars | "
              f"practice header {'yes' if re.search(r'Practice problems for', ''.join(p['text'] for p in part['pages'])) else 'no'}")
    return result


if __name__ == "__main__":
    build()
