"""
Find the diagrams on scanned book pages and attach them to their questions.

    python -m ingest.scan_figures --topic 5        # crops to data/figures/<doc_id>/, index in data/figures/index.jsonl
    python -m ingest.scan_figures --topic 5 --sheet out.png     # contact sheet for checking by eye

A diagram is printed ink that OCR did not read as text, so the question's wording doesn't matter. Answer boxes, rules,
table grids, the footer and the watermark are removed first. Each diagram belongs to the question whose number or Q# header
is nearest above it on the page, or to the last question of the previous page if there is none.

The deck builder reads text only, so a crop needs a description to be useful there: data/figure_descriptions.jsonl holds
{"file": <crop name>, "description": ...}, added to the question as [FIGURE: ...].
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import cv2
import numpy as np

from . import scan_ocr
from .scan_books import HEADER_RE, _NUMBER_RE, parse_header

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "data" / "figures"
INDEX = FIG_DIR / "index.jsonl"
DESCRIPTIONS = ROOT / "data" / "figure_descriptions.jsonl"

INK = 140                  # darker than the pale watermark
FOOTER = 0.885             # fraction of page height: footer and the book's stamp below this
MIN_W, MIN_H = 70, 45      # px at 200 dpi: smaller marks are ticks, underlines or stray text
MIN_INK = 350              # px of ink a real drawing leaves after text is removed
PADDING = 14
LINE_HEIGHT = 30           # px at 200 dpi


def erase_answer_boxes(rgb: np.ndarray) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    """White out rectangles of long rules whose inside holds only dots. Returns the image and the boxes (top, bottom, left, right)."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    ink = (gray < INK).astype(np.uint8)
    h, w = ink.shape
    long_h = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.45), 1)))
    lines: list[int] = []
    for r in np.where(long_h.sum(axis=1) > w * 0.45)[0]:
        if not lines or r - lines[-1] > 6:
            lines.append(int(r))
    out = rgb.copy()
    erased = []
    for top, bottom in zip(lines, lines[1:]):
        if not 50 < bottom - top < h * 0.6:
            continue
        cols = np.where(long_h[top:top + 7].sum(axis=0) > 0)[0]
        if cols.size == 0:
            continue
        left, right = int(cols.min()), int(cols.max())
        walls = ink[top + 8:bottom - 8, :]
        if walls[:, max(0, left - 4):left + 5].max(axis=1).mean() < 0.9 or walls[:, right - 4:min(w, right + 5)].max(axis=1).mean() < 0.9:
            continue
        inner = ink[top + 8:bottom - 8, left + 8:right - 8]
        n, _labels, stats, _c = cv2.connectedComponentsWithStats(inner, connectivity=8)
        if n > 1 and (stats[1:, cv2.CC_STAT_HEIGHT].max() > 7 or stats[1:, cv2.CC_STAT_WIDTH].max() > 9):
            continue                                       # something other than dots is written inside
        out[top - 4:bottom + 5, max(0, left - 5):min(w, right + 6)] = 255
        erased.append((top, bottom, left, right))
    return out, erased


def _is_grid(residual: np.ndarray) -> bool:
    """True if what's left is straight rules only: a table, whose content OCR already read as text.
    Graph paper has rules too, but a curve, a diagonal or plotted points survive removing them."""
    h, w = residual.shape
    horiz = cv2.morphologyEx(residual, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, w // 6), 1)))
    vert = cv2.morphologyEx(residual, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, h // 6))))
    rules = cv2.dilate(horiz | vert, np.ones((5, 5), np.uint8))
    return bool(horiz.any() and vert.any()) and int((residual & (1 - rules)).sum()) < 150


def find_figures(rgb: np.ndarray, text_boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Regions (x0, y0, x1, y1) of ink left after removing text, answer boxes and table grids."""
    clean, _ = erase_answer_boxes(rgb)
    gray = cv2.cvtColor(clean, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    ink = (gray < INK).astype(np.uint8)
    ink[int(h * FOOTER):, :] = 0
    for x0, y0, x1, y1 in text_boxes:
        ink[max(0, y0 - 2):y1 + 2, max(0, x0 - 2):x1 + 2] = 0
    # page-wide rules belong to answer lines or section breaks, never to a drawing
    rules = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.6), 1)))
    ink[rules > 0] = 0
    grouped = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_RECT, (41, 31)))
    n, _labels, stats, _c = cv2.connectedComponentsWithStats(grouped, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, bw, bh, _area = stats[i]
        region = ink[y:y + bh, x:x + bw]
        rows, cols = np.where(region)
        if rows.size < MIN_INK:
            continue
        x0, x1, y0, y1 = x + cols.min(), x + cols.max(), y + rows.min(), y + rows.max()
        if x1 - x0 < MIN_W or y1 - y0 < MIN_H or _is_grid(ink[y0:y1 + 1, x0:x1 + 1]):
            continue
        out.append((int(x0), int(y0), int(x1), int(y1)))
    return sorted(out, key=lambda b: b[1])


_PROSE_RE = re.compile(r"^\s*(?:[A-D]\s*[.,](?:\s|$)|\d{1,2}\s*[.,](?:\s|$)|\([a-z]{1,3}\)(?:\s|$))")


def to_bands(figs: list[tuple[int, int, int, int]], ocr_boxes: list[dict], clean: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Grow each detection to the whole band between the text lines above and below it, so a drawing the detector only
    partly saw is still cropped complete with its labels. Bands that touch become one diagram."""
    h, w = clean.shape[:2]
    prose = sorted(b["y"] for b in ocr_boxes if len(b["t"].strip()) >= 30 or _PROSE_RE.match(b["t"]) or HEADER_RE.search(b["t"]))
    bands: list[list[int]] = []
    for _x0, y0, _x1, y1 in figs:
        top = max((y + LINE_HEIGHT for y in prose if y + LINE_HEIGHT <= y0), default=0)
        bottom = min((y for y in prose if y >= y1), default=int(h * FOOTER))
        bands.append([top, bottom])
    merged: list[list[int]] = []
    for top, bottom in sorted(bands):
        if merged and top <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], bottom)
        else:
            merged.append([top, bottom])
    out = []
    gray = cv2.cvtColor(clean, cv2.COLOR_RGB2GRAY)
    for top, bottom in merged:
        rows, cols = np.where(gray[top:bottom] < INK)
        if rows.size == 0:
            continue
        out.append((int(max(0, cols.min() - PADDING)), int(max(0, top + rows.min() - PADDING)),
                    int(min(w, cols.max() + PADDING)), int(min(h, top + rows.max() + PADDING))))
    return out


def is_table(crop: np.ndarray) -> bool:
    """A ruled table whose cells OCR already read: a few long rules and only small marks (+, -, letters) between them.
    Graph paper has many more rules, and a drawing leaves large shapes behind."""
    ink = (cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY) < INK).astype(np.uint8)
    h, w = ink.shape
    horiz = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(60, w // 3), 1)))
    vert = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(40, h // 3))))
    n_vert = cv2.connectedComponents(cv2.dilate(vert, np.ones((3, 3), np.uint8)))[0] - 1
    n_horiz = cv2.connectedComponents(cv2.dilate(horiz, np.ones((3, 3), np.uint8)))[0] - 1
    if not 2 <= n_vert <= 8 or not 2 <= n_horiz <= 14:
        return False
    rest = ink & (1 - cv2.dilate(horiz | vert, np.ones((5, 5), np.uint8)))
    n, _labels, stats, _c = cv2.connectedComponentsWithStats(rest, connectivity=8)
    return n <= 1 or (stats[1:, cv2.CC_STAT_WIDTH].max() < 60 and stats[1:, cv2.CC_STAT_HEIGHT].max() < 45)


def load_index() -> list[dict]:
    return [json.loads(l) for l in INDEX.read_text(encoding="utf-8").splitlines() if l.strip()] if INDEX.exists() else []


def load_descriptions() -> dict[str, dict]:
    """{file: {"description", optional "book_q" + "numbers" (checked by eye, overrides the automatic match), optional "kind"}}"""
    if not DESCRIPTIONS.exists():
        return {}
    rows = (json.loads(l) for l in DESCRIPTIONS.read_text(encoding="utf-8").splitlines() if l.strip())
    return {r["file"]: r for r in rows}


def write_by_ref(chunks) -> None:
    """question ref → diagram crops, for the app."""
    table: dict[str, list[str]] = {}
    for c in chunks:
        m = c.metadata
        if m["source_type"] == "past_paper" and m.get("figures"):
            table.setdefault(m["question_ref"], [])
            table[m["question_ref"]] += [f for f in m["figures"] if f not in table[m["question_ref"]]]
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "by_ref.json").write_text(json.dumps(table, indent=1), encoding="utf-8")


def text_box_path(doc_id: str) -> Path:
    return scan_ocr.OCR_DIR / f"{doc_id}.textboxes.jsonl"


def anchors(row: dict, paper: str) -> list[tuple[int, int | None, int | None]]:
    """(y, Q#, printed question number) for each header or question number on a page, from the RapidOCR boxes."""
    out = []
    for b in sorted(row["boxes"], key=lambda b: b["y"]):
        t = b["t"].strip()
        head = parse_header(t, paper) if HEADER_RE.search(t) else None
        if head:
            out.append((b["y"], head["q"], head.get("exam_q")))
        elif paper == "1" and b["x"] < 220:
            m = _NUMBER_RE.match(t) or re.fullmatch(r"(\d{1,2})\s*[.,]?", t)
            if m and int(m.group(1)) <= 45:
                out.append((b["y"], None, int(m.group(1))))
    return out


def run(topics: list[int], only: list[str] | None = None) -> list[dict]:
    import pypdfium2
    from PIL import Image
    from rapidocr import RapidOCR

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    engine = RapidOCR()
    index: list[dict] = []
    for src in scan_ocr.scan_sources():
        doc = src["doc_id"]
        if src.get("emit_chunks") is False or (only and doc not in only):
            continue
        pages = sorted({p for t in topics for p in scan_ocr.topic_pages(src, t)})
        ms_start = src.get("ms_start") or 10 ** 6
        pages = [p for p in pages if p < ms_start]          # markscheme tables hold no question diagrams
        cache = {}
        tb = text_box_path(doc)
        if tb.exists():
            cache = {r["page"]: r["boxes"] for r in map(json.loads, tb.read_text(encoding="utf-8").splitlines())}
        ocr = scan_ocr.load_ocr(doc, "rapidocr")
        pdf = pypdfium2.PdfDocument(src["path"])
        out_dir = FIG_DIR / doc
        out_dir.mkdir(exist_ok=True)
        cur_q, cur_n = None, None
        # walk from the first page of the run; a figure at the top of a page continues the previous page's question
        for p in pages:
            rgb = np.asarray(pdf[p - 1].render(scale=scan_ocr.DPI / 72).to_pil().convert("RGB"))
            if p not in cache:
                res = engine(rgb, use_cls=False, use_rec=False)
                boxes = [] if res.boxes is None else [[int(b[:, 0].min()), int(b[:, 1].min()), int(b[:, 0].max()), int(b[:, 1].max())] for b in res.boxes]
                cache[p] = boxes
                with tb.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"page": p, "boxes": boxes}) + "\n")
            clean, _ = erase_answer_boxes(rgb)
            figs = find_figures(rgb, [tuple(b) for b in cache[p]])
            figs = to_bands(figs, ocr[p]["boxes"] if p in ocr else [], clean)
            marks = anchors(ocr[p], src.get("paper", "1")) if p in ocr else []
            for i, box in enumerate(figs):
                q, n = cur_q, cur_n
                for y, aq, an in marks:
                    if y > box[1] + 10:
                        break
                    if aq is not None:
                        q, n = aq, an
                    elif an is not None:
                        n = an
                name = f"p{p:03d}_{i}.png"
                crop = clean[box[1]:box[3], box[0]:box[2]]
                Image.fromarray(crop).save(out_dir / name)
                index.append({"doc_id": doc, "file": f"{doc}/{name}", "page": p, "bbox": box, "book_q": q, "number": n,
                              "kind": "table" if is_table(crop) else "diagram",
                              "topic": sum(p >= s for s in src.get("topic_pages", [])) or None})
            for y, aq, an in marks:
                if aq is not None:
                    cur_q, cur_n = aq, an
                elif an is not None:
                    cur_n = an
        print(f"{doc}: {sum(1 for r in index if r['doc_id'] == doc)} diagrams on {len(pages)} question pages", flush=True)
    with INDEX.open("w", encoding="utf-8") as f:
        for r in index:
            f.write(json.dumps(r) + "\n")
    return index


def contact_sheet(index: list[dict], path: Path, per_row: int = 6, cell: int = 300) -> None:
    from PIL import Image, ImageDraw
    rows = (len(index) + per_row - 1) // per_row
    sheet = Image.new("RGB", (per_row * cell, rows * cell), "white")
    draw = ImageDraw.Draw(sheet)
    for i, r in enumerate(index):
        im = Image.open(FIG_DIR / r["file"]).convert("RGB")
        im.thumbnail((cell - 8, cell - 34))
        x, y = (i % per_row) * cell, (i // per_row) * cell
        sheet.paste(im, (x + 4, y + 28))
        draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline="gray")
        draw.text((x + 5, y + 6), f"{r['doc_id'][6:13]} p{r['page']} Q#{r['book_q']}.{r['number']} {r['kind']}", fill="red")
    sheet.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic", type=int, nargs="*", default=[5])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--sheet", help="write a contact sheet to this path")
    a = ap.parse_args()
    index = run(a.topic, a.only)
    if a.sheet:
        contact_sheet(index, Path(a.sheet))


if __name__ == "__main__":
    main()
