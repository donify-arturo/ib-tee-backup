"""Dry run of the book splitter and checks on whatever OCR has finished. Writes nothing.

    python -m ingest.scan_preview                    # counts per book
    python -m ingest.scan_preview --show 3           # also print sample chunks
    python -m ingest.scan_preview --topic 5 --flags  # list flagged items for one old-syllabus topic
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from . import scan_books as sb
from . import scan_ocr
from .chunking import Chunk
from .parsers import Page
from .splitters import SourceSpec, SPLITTERS

ROOT = Path(__file__).resolve().parents[1]


def _library() -> list[Chunk]:
    out = []
    for f in sorted((ROOT / "data" / "chunks").glob("*.jsonl")):
        if f.stem.startswith("smash_"):
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = json.loads(line)
                out.append(Chunk(c["id"], c["text"], c["metadata"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--topic", type=int)
    ap.add_argument("--flags", action="store_true")
    a = ap.parse_args()
    book, rapid_all = [], []
    specs = []
    for s in scan_ocr.scan_sources():
        spec = SourceSpec(doc_id=s["doc_id"], path=s["path"], source_type="scan_book", origin=s["origin"], scan=s)
        specs.append(spec)
        marker = scan_ocr.load_ocr(s["doc_id"], "marker")
        rp = scan_ocr.rapid_pages(s)
        merged = {p.page: p for p in rp}
        for n, r in marker.items():
            merged[n] = Page(page=n, markdown=scan_ocr.flatten_markdown(r["markdown"]), parser="local:marker")
        pages = [merged[n] for n in sorted(merged)]
        got = SPLITTERS["scan_book"](spec, pages)
        rapid = SPLITTERS["scan_book"](spec, rp)
        book += got
        rapid_all += rapid
        cov = sb.coverage([spec], lambda _d, pg=pages: pg)
        print(f"{s['doc_id']}: rapid {len(rp)} marker {len(marker)} pages -> "
              f"{Counter(c.metadata['source_type'] for c in got)}")
        print("   coverage", {k: (v if len(str(v)) < 90 else str(v)[:90] + '…') for k, v in cov.get(s["doc_id"], {}).items()})
    kept, report = sb.merge_with_library(_library() + book, rapid_all)
    print(json.dumps({k: report[k] for k in ("checks", "merge", "kept_by_quality", "flags")}, indent=1))
    held = [c for c in kept if c.metadata.get("scan_book") and (a.topic is None or c.metadata["book_topic"] == a.topic)]
    if a.topic is not None:
        print(f"topic {a.topic}:", Counter((c.metadata["source_type"], c.metadata["scan_engine"], c.metadata["scan_quality"]) for c in held))
    if a.flags:
        for c in held:
            if c.metadata["scan_flags"]:
                print(c.metadata["doc_id"], c.metadata["book_q"], c.metadata["question_ref"], c.metadata["source_type"], c.metadata["scan_flags"])
    for c in [x for x in held if x.metadata["scan_engine"] == "marker"][:a.show]:
        print("-----", c.metadata["question_ref"], c.metadata["scan_flags"])
        print(c.text[:700])


if __name__ == "__main__":
    main()
