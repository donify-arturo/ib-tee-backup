"""
PDF → per-page Markdown.

Two interchangeable backends write the same cache format
(data/markdown/<doc_id>.jsonl, one JSON object per page):

    {"page": 12, "markdown": "...", "header": "...", "printed_page": "405",
     "parser": "llamaparse:agentic"}

* LlamaParseParser — the production path. Vision-aware parsing through the
  LlamaCloud API (`pip install "llama-cloud>=1.0"`, env LLAMA_CLOUD_API_KEY).
  Per-source prompts live in ingest/profiles.py.
* LocalParser — offline fallback with pdfplumber. No vision, no LaTeX, loses
  figures, but keeps page order and text so the regex tagging, splitting and
  linking stages can be developed and tested without spending credits.

Parsing is resumable: pages already in the cache are skipped, and LlamaParse
jobs are sent in batches of `batch_pages` so a failure costs one batch.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .profiles import PROFILES, ParseProfile

CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "markdown"


@dataclass
class Page:
    page: int                     # 1-based PDF page index
    markdown: str
    header: str | None = None     # running header if the parser separated it
    printed_page: str | None = None
    parser: str = ""


# --------------------------------------------------------------------------- #
# Cache helpers
# --------------------------------------------------------------------------- #
def cache_path(doc_id: str) -> Path:
    return CACHE_DIR / f"{doc_id}.jsonl"


def load_pages(doc_id: str) -> list[Page]:
    p = cache_path(doc_id)
    if not p.exists():
        return []
    pages = [Page(**json.loads(l)) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return sorted({pg.page: pg for pg in pages}.values(), key=lambda x: x.page)


def _append(doc_id: str, pages: Iterable[Page]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with cache_path(doc_id).open("a", encoding="utf-8") as f:
        for pg in pages:
            f.write(json.dumps(asdict(pg), ensure_ascii=False) + "\n")


def _page_count(pdf_path: Path) -> int:
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        return len(pdf.pages)


def _ranges(pages: list[int], batch: int) -> list[str]:
    """[1,2,3,7,8] -> ['1-3,7-8'] grouped into strings of at most `batch` pages."""
    out, cur = [], []
    for p in pages:
        cur.append(p)
        if len(cur) == batch:
            out.append(cur); cur = []
    if cur:
        out.append(cur)

    def compress(ps):
        parts, start, prev = [], ps[0], ps[0]
        for p in ps[1:]:
            if p == prev + 1:
                prev = p; continue
            parts.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = p
        parts.append(f"{start}-{prev}" if start != prev else str(start))
        return ",".join(parts)

    return [compress(b) for b in out]


# --------------------------------------------------------------------------- #
# LlamaParse (production)
# --------------------------------------------------------------------------- #
class LlamaParseParser:
    def __init__(self, api_key: str | None = None, batch_pages: int = 40, version: str = "latest"):
        from llama_cloud import LlamaCloud  # imported lazily so the local path has no dependency

        key = api_key or os.environ.get("LLAMA_CLOUD_API_KEY")
        if not key:
            raise RuntimeError("Set LLAMA_CLOUD_API_KEY (https://cloud.llamaindex.ai → API keys)")
        self.client = LlamaCloud(api_key=key)
        self.batch_pages = batch_pages
        self.version = version

    def _request_kwargs(self, profile: ParseProfile) -> dict:
        kw: dict = {
            "tier": profile.tier,
            "version": self.version,
            "expand": ["markdown"],
            "output_options": {
                "extract_printed_page_number": True,
                "markdown": {
                    "tables": {
                        "merge_continued_tables": profile.merge_tables,
                        "compact_markdown_tables": True,
                        "markdown_table_multiline_separator": "<br>",
                    },
                },
            },
            "processing_options": {
                "ignore": {"ignore_diagonal_text": profile.ignore_diagonal_text},
                "aggressive_table_extraction": profile.aggressive_tables,
                "specialized_chart_parsing": "agentic" if profile.charts else None,
            },
        }
        if profile.remove_watermark:
            kw["output_options"]["watermark_handling"] = "remove"
        if profile.tier != "fast":
            kw["agentic_options"] = {"custom_prompt": profile.prompt}
        # drop None values the API would reject
        kw["processing_options"] = {k: v for k, v in kw["processing_options"].items() if v is not None}
        return kw

    def parse(self, doc_id: str, pdf_path: Path, profile_name: str, pages: list[int] | None = None,
              force: bool = False) -> list[Page]:
        profile = PROFILES[profile_name]
        total = _page_count(pdf_path)
        wanted = pages or list(range(1, total + 1))
        done = set() if force else {p.page for p in load_pages(doc_id)}
        todo = [p for p in wanted if p not in done]
        if not todo:
            return load_pages(doc_id)

        kwargs = self._request_kwargs(profile)
        for rng in _ranges(todo, self.batch_pages):
            for attempt in range(3):
                try:
                    with open(pdf_path, "rb") as fh:
                        result = self.client.parsing.parse(
                            upload_file=fh,
                            page_ranges={"target_pages": rng},
                            timeout=3600,
                            **kwargs,
                        )
                    break
                except Exception as e:  # network / 5xx: back off and retry the batch
                    if attempt == 2:
                        raise
                    print(f"  [{doc_id}] pages {rng} failed ({e!r}); retrying")
                    time.sleep(10 * (attempt + 1))

            out = []
            for mp in result.markdown.pages if result.markdown else []:
                if not getattr(mp, "success", True):
                    print(f"  [{doc_id}] page {mp.page_number} failed: {getattr(mp, 'error', '')}")
                    continue
                out.append(Page(
                    page=mp.page_number,
                    markdown=mp.markdown or "",
                    header=getattr(mp, "header", None),
                    printed_page=_printed_page(result, mp.page_number),
                    parser=f"llamaparse:{profile.tier}",
                ))
            _append(doc_id, out)
            print(f"  [{doc_id}] parsed pages {rng} ({len(out)} ok)")
        return load_pages(doc_id)


def _printed_page(result, page_number: int) -> str | None:
    try:
        for mp in result.metadata.pages:
            if mp.page_number == page_number:
                return getattr(mp, "printed_page_number", None)
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- #
# Local fallback (pdfplumber) — development / tests only
# --------------------------------------------------------------------------- #
_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}


class LocalParser:
    """Text-only parser. Drops diagonally rotated characters (watermarks)."""

    def parse(self, doc_id: str, pdf_path: Path, profile_name: str, pages: list[int] | None = None,
              force: bool = False) -> list[Page]:
        import logging
        import pdfplumber

        logging.getLogger("pdfminer").setLevel(logging.ERROR)
        if not force and load_pages(doc_id):
            return load_pages(doc_id)
        if force and cache_path(doc_id).exists():
            cache_path(doc_id).unlink()
        out = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, pg in enumerate(pdf.pages, start=1):
                if pages and i not in pages:
                    continue
                chars = pg.chars
                rotated = sum(1 for c in chars if abs(c["matrix"][0]) < 0.05 and abs(c["matrix"][1]) > 0.5)
                if chars and rotated > 0.5 * len(chars):
                    # landscape table (periodic table etc.): pdfplumber reads it backwards; poppler handles rotation
                    text = _pdftotext_page(pdf_path, i)
                else:
                    # drop diagonal (watermark) glyphs only
                    upright = pg.filter(lambda o: o.get("object_type") != "char" or
                                        not (abs(o["matrix"][0]) > 0.05 and abs(o["matrix"][1]) > 0.05))
                    text = upright.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
                for k, v in _LIGATURES.items():
                    text = text.replace(k, v)
                parser = "local:pdfplumber"
                if len(text.strip()) < 30 and pg.images:
                    # screenshot / scanned page with no text layer → OCR it
                    text, parser = _ocr_page(pdf_path, i), "local:tesseract"
                out.append(Page(page=i, markdown=text, parser=parser))
        _append(doc_id, out)
        return load_pages(doc_id)


class PdftotextParser:
    """Fast text-layer parser (poppler). Right for long, text-born PDFs such as the subject
    reports (≈2,000 pages in seconds). Keeps column layout; no figures or tables-as-images."""

    def parse(self, doc_id: str, pdf_path: Path, profile_name: str = "", pages: list[int] | None = None,
              force: bool = False) -> list[Page]:
        import subprocess
        if not force and load_pages(doc_id):
            return load_pages(doc_id)
        if cache_path(doc_id).exists():
            cache_path(doc_id).unlink()
        txt = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True,
                             text=True, timeout=900).stdout
        chunks = txt.split("\f")
        out = [Page(page=i, markdown=t, parser="local:pdftotext")
               for i, t in enumerate(chunks, start=1) if (not pages or i in pages) and t.strip()]
        _append(doc_id, out)
        return load_pages(doc_id)


def _ocr_page(pdf_path: Path, page: int, dpi: int = 200) -> str:
    """OCR one page (tesseract). Local fallback only: LlamaParse handles image pages natively."""
    import subprocess
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as tmp:
            base = f"{tmp}/p"
            subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi), "-gray", "-png",
                            str(pdf_path), base], check=True, capture_output=True, timeout=120)
            png = next(Path(tmp).glob("p*.png"))
            return subprocess.run(["tesseract", str(png), "-", "--psm", "6"], capture_output=True,
                                  text=True, timeout=180).stdout
    except Exception:
        return ""


def _pdftotext_page(pdf_path: Path, page: int) -> str:
    import subprocess
    try:
        return subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf_path), "-"],
                              capture_output=True, text=True, timeout=60).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def get_parser(name: str, **kw):
    if name == "llamaparse":
        return LlamaParseParser(**kw)
    if name == "local":
        return LocalParser()
    if name == "pdftotext":
        return PdftotextParser()
    raise ValueError(f"unknown parser {name!r}")


def strip_browser_chrome(md: str) -> str:
    """Remove print-to-PDF artefacts from browser captures (timestamps, URLs, page counters)."""
    lines = []
    for ln in md.splitlines():
        s = ln.strip()
        if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}", s):        # "2/11/26, 22:04 …"
            continue
        if re.match(r"^(https?://|about:blank)", s):
            continue
        if re.fullmatch(r"\d+/\d+", s):
            continue
        if s in {"Submit", "Ans", "Answer", "Show answer"}:
            continue
        lines.append(ln)
    return "\n".join(lines)
