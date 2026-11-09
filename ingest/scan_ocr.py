"""
OCR for the scanned revision books (source_type = "scan_book" in sources.toml).

    python -m ingest.scan_ocr rapid                      # all pages, CPU, about 5 s per page
    python -m ingest.scan_ocr marker --topic 5           # slow, GPU: run with .venv-marker (see marker_worker.py)
    python -m ingest.scan_ocr status

Raw engine output is kept per page in data/ocr/<doc_id>.<engine>.jsonl and is resumable. `merge` rebuilds
data/markdown/<doc_id>.jsonl from it, preferring Marker over RapidOCR for each page; ingest.pipeline does that
on every run, so finished Marker pages replace RapidOCR pages without any re-parsing.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from .parsers import Page, cache_path, _append

ROOT = Path(__file__).resolve().parents[1]
OCR_DIR = ROOT / "data" / "ocr"
DPI = 200
ROW_TOLERANCE = 14        # px at 200 dpi: boxes this close vertically are one printed line
COLUMN_GAP = 300          # px at 200 dpi: answer-key pages have 2-3 columns further apart than this
HEADER_RE = re.compile(r"Q\s*#\s*\d{1,3}")


def scan_sources(manifest: Path = ROOT / "sources.toml") -> list[dict]:
    return [s for s in tomllib.loads(manifest.read_text(encoding="utf-8"))["source"] if s["source_type"] == "scan_book"]


def ocr_path(doc_id: str, engine: str) -> Path:
    return OCR_DIR / f"{doc_id}.{engine}.jsonl"


def load_ocr(doc_id: str, engine: str) -> dict[int, dict]:
    p = ocr_path(doc_id, engine)
    if not p.exists():
        return {}
    rows = (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
    return {r["page"]: r for r in rows}


def topic_pages(src: dict, topic: int) -> list[int]:
    """PDF pages of one old-syllabus topic, questions and markschemes (one page of overlap on each side)."""
    starts = src.get("topic_pages", [])
    if not 1 <= topic <= len(starts):
        return []
    end = starts[topic] if topic < len(starts) else src.get("ms_start", starts[-1] + 1)
    pages = list(range(starts[topic - 1], end + 1))
    ms = src.get("ms_topic_pages", [])
    if 1 <= topic <= len(ms):
        ms_end = ms[topic] if topic < len(ms) else ms[-1] + 1
        pages += list(range(ms[topic - 1], ms_end + 1))
    return pages


def run_rapid(sources: list[dict]) -> None:
    import numpy as np
    import pdfplumber
    from PIL import Image
    from rapidocr import RapidOCR

    OCR_DIR.mkdir(parents=True, exist_ok=True)
    engine = RapidOCR()
    for src in sources:
        done = load_ocr(src["doc_id"], "rapidocr")
        with pdfplumber.open(src["path"]) as pdf, ocr_path(src["doc_id"], "rapidocr").open("a", encoding="utf-8") as out:
            for n, pg in enumerate(pdf.pages, start=1):
                if n in done:
                    continue
                buf = io.BytesIO()
                pg.to_image(resolution=DPI).save(buf, format="PNG")
                buf.seek(0)
                res = engine(np.asarray(Image.open(buf).convert("RGB")))
                boxes = [] if res.txts is None else [
                    {"t": t, "c": round(float(c), 3), "x": round(float(b[0][0])), "y": round(float(b[0][1]))}
                    for t, c, b in zip(res.txts, res.scores, res.boxes)]
                row = {"page": n, "boxes": boxes, "layer": pg.extract_text() or ""}
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                if n % 25 == 0:
                    print(f"  {src['doc_id']}: page {n}/{len(pdf.pages)}", flush=True)
        print(f"rapid  {src['doc_id']} done", flush=True)


def _rows(boxes: list[dict]) -> list[str]:
    """Group boxes into printed lines, top to bottom, left to right."""
    rows: list[list[dict]] = []
    for b in sorted(boxes, key=lambda b: b["y"]):
        if rows and b["y"] - rows[-1][0]["y"] <= ROW_TOLERANCE:
            rows[-1].append(b)
        else:
            rows.append([b])
    return [" ".join(b["t"] for b in sorted(r, key=lambda b: b["x"])) for r in rows]


def _join_wrapped_headers(lines: list[str]) -> list[str]:
    """In a narrow column a header wraps: "T11 Q# 154/" then "IB/2019/s/TZ2/P1/HL". Join it to the line below."""
    out: list[str] = []
    for line in lines:
        if out and HEADER_RE.search(out[-1]) and not re.search(r"\d{4}\s*/", out[-1]) and re.search(r"\d{4}\s*/\s*[sw]", line, re.I):
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def _columns(boxes: list[dict]) -> list[list[dict]]:
    """Answer-key pages: split into columns at the gaps between the question numbers' x positions."""
    xs = sorted(b["x"] for b in boxes if re.fullmatch(r"\d{1,2}\s*[.,]?", b["t"].strip()) or HEADER_RE.search(b["t"]))
    if not xs:
        return [boxes]
    edges = [(a + c) // 2 for a, c in zip(xs, xs[1:]) if c - a > COLUMN_GAP]
    cols: list[list[dict]] = [[] for _ in range(len(edges) + 1)]
    for b in boxes:
        cols[sum(b["x"] >= e for e in edges)].append(b)
    return cols


def rapid_text(row: dict, is_key_page: bool) -> str:
    """Printed-order text. The inserted headers in some books are real text, so prefer that layer over OCR."""
    boxes = row["boxes"]
    lines: list[str] = []
    for col in (_columns(boxes) if is_key_page else [boxes]):
        lines.extend(_join_wrapped_headers(_rows(col)))
    layer_headers = [l.strip() for l in row.get("layer", "").splitlines() if HEADER_RE.search(l)]
    ocr_headers = [i for i, l in enumerate(lines) if HEADER_RE.search(l)]
    if layer_headers and len(layer_headers) == len(ocr_headers):
        for i, h in zip(ocr_headers, layer_headers):
            lines[i] = h
    return "\n".join(lines)


_LATEX = [(r"\\rightleftharpoons|\\rightleftarrows", "⇌"), (r"\\xrightarrow\s*(?:\{([^{}]*)\})?", r" →\1 "),
          (r"\\(?:rightarrow|to|longrightarrow)\b", "→"), (r"\\Delta\b", "Δ"),
          (r"\\times\b", "×"), (r"\\div\b", "÷"), (r"\\checkmark\b", "✓"), (r"\\(?:ln)\b", "ln"), (r"\\(?:log)\b", "log"),
          (r"\^\{?\\(?:circ|ominus|theta|Theta|oplus)\}?", "°"), (r"\\(?:circ|ominus|theta|Theta|oplus)\b", "°"),
          (r"\\pm\b", "±"), (r"\\approx\b", "≈"), (r"\\geq?\b", "≥"), (r"\\leq?\b", "≤"), (r"\\lt\b", "<"), (r"\\gt\b", ">"),
          (r"\\%", "%"), (r"\\[,;:! ]", " "), (r"\\quad\b|\\qquad\b", " "), (r"\\left|\\right", "")]


def flatten_markdown(md: str) -> str:
    """Marker markdown/LaTeX → the flat notation the library uses: CO2(g), Na+(g), mol dm-3, 10^4."""
    def math(m: re.Match) -> str:
        t = m.group(1)
        for pat, rep in _LATEX:
            t = re.sub(pat, rep, t)
        t = re.sub(r"\\(?:text|mathrm|mathbf|textbf|mathit|operatorname)\b\s*", "", t)     # keeps nested {..} content
        t = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", t)
        t = re.sub(r"\b10\s*\^\s*\{?\s*([-−–]?\d+)\s*\}?", r"10^\1", t)     # keep the caret: 10^4, never 104
        t = re.sub(r"_\s*\{([^{}]*)\}|_(\w)", lambda g: g.group(1) or g.group(2), t)
        t = re.sub(r"(?<!10)\^\s*\{([^{}]*)\}|(?<!10)\^([\w+\-−])", lambda g: g.group(1) or g.group(2), t)
        t = re.sub(r"\\[A-Za-z]+", " ", t)                                   # any command not mapped above
        return re.sub(r"[{}]", "", t)
    t = re.sub(r"\$\$?([^$]+)\$\$?", math, md)
    t = re.sub(r"<su[bp]>(.*?)</su[bp]>", r"\1", t)
    t = re.sub(r"</?(?:u|b|i|strong|em|br)\s*/?>", " ", t)
    t = re.sub(r"\*\*|__", "", t)
    t = re.sub(r"^\s*(?:[-*]\s+|#+\s*)", "", t, flags=re.M)
    t = re.sub(r"^\s*\|?\s*:?-{3,}.*$", "", t, flags=re.M)                     # table rulers
    t = re.sub(r"^\s*\|(.*?)\|?\s*$", lambda m: " | ".join(c.strip() for c in m.group(1).split("|") if c.strip()), t, flags=re.M)
    t = re.sub(r"(?<=\S)[ \t]+(?=(?:Topic\s*(?:Chem\s*)?\d*\s*\d*\s*|Chem\s*\d+\s*/\s*|T\d+\s*)?Q\s*#\s*\d)", "\n", t)   # header run into a line
    t = t.replace("−", "-").replace("–", "-")
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def rapid_pages(src: dict) -> list[Page]:
    ms_start = src.get("ms_start") or 10 ** 6
    return [Page(page=n, markdown=rapid_text(r, src.get("paper") == "1" and n >= ms_start), parser="local:rapidocr")
            for n, r in sorted(load_ocr(src["doc_id"], "rapidocr").items())]


def merge(src: dict) -> tuple[int, int]:
    """Rebuild the page cache for one book. Returns (marker pages, rapid pages)."""
    doc_id = src["doc_id"]
    marker, rapid = load_ocr(doc_id, "marker"), load_ocr(doc_id, "rapidocr")
    pages = []
    ms_start = src.get("ms_start") or 10 ** 6
    for n in sorted(set(marker) | set(rapid)):
        if n in marker:
            pages.append(Page(page=n, markdown=flatten_markdown(marker[n]["markdown"]), parser="local:marker"))
        else:
            is_key = src.get("paper") == "1" and n >= ms_start
            pages.append(Page(page=n, markdown=rapid_text(rapid[n], is_key), parser="local:rapidocr"))
    if cache_path(doc_id).exists():
        cache_path(doc_id).unlink()
    _append(doc_id, pages)
    return len(marker), len(rapid)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["rapid", "marker", "merge", "status"])
    ap.add_argument("--only", nargs="*", help="doc_ids")
    ap.add_argument("--topic", type=int, nargs="*", default=[5], help="marker: old-syllabus topics to run (default: 5, energetics)")
    ap.add_argument("--skip", type=int, nargs="*", default=[], help="marker: PDF pages to leave to RapidOCR (a page that stalls Marker)")
    a = ap.parse_args()
    sources = [s for s in scan_sources() if not a.only or s["doc_id"] in a.only]
    if a.command == "rapid":
        run_rapid(sources)
    elif a.command == "marker":
        worker = Path(__file__).with_name("marker_worker.py")
        py = ROOT / ".venv-marker" / "Scripts" / "python.exe"
        for s in sources:
            pages = sorted({p for t in a.topic for p in topic_pages(s, t)} - set(a.skip))
            if pages:
                subprocess.run([str(py), str(worker), s["path"], str(ocr_path(s["doc_id"], "marker")),
                                ",".join(map(str, pages))], check=True)
    elif a.command == "merge":
        for s in sources:
            print(s["doc_id"], "marker/rapid pages:", merge(s))
    else:
        for s in sources:
            want = sorted({p for t in a.topic for p in topic_pages(s, t)})
            have = load_ocr(s["doc_id"], "marker")
            print(f"{s['doc_id']:<28} rapid {len(load_ocr(s['doc_id'], 'rapidocr')):>4}   marker {sum(p in have for p in want)}/{len(want)} of topics {a.topic}")


if __name__ == "__main__":
    sys.exit(main())
