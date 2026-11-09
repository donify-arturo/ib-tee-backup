"""
Real book pages as images, for the Study guide. Rendered from the student's own PDFs on first view, then cached.

    data/books/page_images/<book>/<printed page>.png
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "documents to process"
CACHE = ROOT / "data" / "books" / "page_images"
PDFS = {"companion": DOCS / "Chemistry - Course Companion - Bylikin, Horner, Grant and Tarcy - Oxford 2023.pdf",
        "prepared": DOCS / "Chemistry - IB Prepared - Sergey Bylikin - Oxford 2024.pdf"}
PREPARED_OFFSET = 8          # PDF page number minus printed page number (ingest.prepared_pages)


@lru_cache(maxsize=1)
def companion_offset() -> int:
    """PDF page number minus printed page number, from any extracted chapter."""
    chapter = json.loads((ROOT / "data" / "books" / "companion" / "R1.1.json").read_text(encoding="utf-8"))
    return chapter["pdf_pages"][0] - chapter["printed_pages"][0]


def pdf_index(book: str, printed: int) -> int:
    """0-based index of a printed page in the book's PDF."""
    return printed + (companion_offset() if book == "companion" else PREPARED_OFFSET) - 1


def page_image(book: str, printed: int | str, scale: float = 1.6, cache: Path = CACHE) -> Path | None:
    """PNG of one printed page, or None if the book or page isn't there."""
    try:
        number = int(str(printed).strip())
    except ValueError:
        return None
    out = cache / book / f"{number}.png"
    if out.exists():
        return out
    pdf = PDFS.get(book)
    if not pdf or not pdf.exists():
        return None
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    index = pdf_index(book, number)
    if not 0 <= index < len(doc):
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    doc[index].render(scale=scale).to_pil().save(out)
    return out


def merge_pages(*lists) -> list[int]:
    """Sorted unique page numbers from several lists of strings or ints, skipping anything that isn't a number."""
    pages = set()
    for items in lists:
        for item in items or []:
            try:
                pages.add(int(str(item).strip()))
            except ValueError:
                continue
    return sorted(pages)
