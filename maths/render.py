"""
Pieces of the original PDFs as images: a question, a part's markscheme, a calculator step.

A region list is [[page, top, bottom], ...] in PDF points (from ingest.maths_papers / ingest.maths_calculator). Pages are rendered once
per document and cached; each crop is cached by its regions, so the first view takes a moment and later views are instant.

    data/maths/cache/pages/<doc>/<page>.png
    data/maths/cache/crops/<hash>.png
"""
from __future__ import annotations

import hashlib
import json
import threading
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "maths" / "cache"
SCALE = 2.0            # 144 dpi: sharp enough for subscripts, small enough to load fast
_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def documents() -> dict[str, Path]:
    """doc key -> PDF path, for every document the maths data refers to."""
    out = {}
    q = ROOT / "data" / "maths" / "questions.json"
    if q.exists():
        for d in json.loads(q.read_text(encoding="utf-8"))["report"]["documents"]:
            out[d["key"]] = ROOT / d["file"]
    c = ROOT / "data" / "maths" / "calculator.json"
    if c.exists():
        out["calc"] = ROOT / json.loads(c.read_text(encoding="utf-8"))["file"]
    b = ROOT / "data" / "maths" / "book.json"
    if b.exists():
        book = ROOT / json.loads(b.read_text(encoding="utf-8"))["file"]
        if not book.exists():                 # the student may reorganise the folder: find the same file by name
            book = next((ROOT / "documents to process").rglob(book.name.replace("[", "[[]")), book)
        out["book"] = book
    c2 = ROOT / "data" / "maths" / "book_corrections.json"
    if c2.exists():
        out["corrections"] = ROOT / json.loads(c2.read_text(encoding="utf-8"))["file"]
    s = ROOT / "data" / "maths" / "syllabus.json"
    if s.exists():
        for ch in json.loads(s.read_text(encoding="utf-8")).get("worked_solutions", []):
            out[ch["doc"]] = ROOT / ch["file"]
    return out


def page_png(doc: str, page: int, scale: float = SCALE) -> Path | None:
    out = CACHE / "pages" / doc / f"{page}.png"
    if out.exists():
        return out
    pdf = documents().get(doc)
    if not pdf or not pdf.exists():
        return None
    import pypdfium2 as pdfium
    with _LOCK:              # pdfium is not thread-safe, and Streamlit runs sessions in threads
        if out.exists():
            return out
        pdf_doc = pdfium.PdfDocument(str(pdf))
        if not 0 <= page < len(pdf_doc):
            return None
        out.parent.mkdir(parents=True, exist_ok=True)
        pdf_doc[page].render(scale=scale).to_pil().save(out)
        pdf_doc.close()
    return out


def crop(doc: str, regions: list, x0: float = 40, x1: float | None = None, scale: float = SCALE) -> Path | None:
    """One PNG stacking the regions top to bottom, cut to the text column. None when the PDF is missing."""
    if not regions:
        return None
    key = hashlib.sha1(json.dumps([doc, regions, x0, x1, scale]).encode()).hexdigest()[:20]
    out = CACHE / "crops" / f"{key}.png"
    if out.exists():
        return out
    from PIL import Image
    pieces = []
    for region in regions:                   # [page, top, bottom], or [page, top, bottom, left, right] for a column of the page
        page, top, bottom = region[:3]
        left, right_edge = region[3:5] if len(region) >= 5 else (x0, x1)
        path = page_png(doc, int(page), scale)
        if not path:
            return None
        img = Image.open(path)
        right = img.width - 40 * scale if right_edge is None else right_edge * scale
        box = (int(left * scale), int(max(0, top) * scale), int(right), int(min(img.height / scale, bottom) * scale))
        if box[3] - box[1] > 4:
            pieces.append(img.crop(box))
    if not pieces:
        return None
    width = max(p.width for p in pieces)
    gap = int(6 * scale)
    canvas = Image.new("RGB", (width, sum(p.height for p in pieces) + gap * (len(pieces) - 1)), "white")
    y = 0
    for p in pieces:
        canvas.paste(p, (0, y))
        y += p.height + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    return out
