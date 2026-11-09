"""
IB-TEE ingestion pipeline (Part 1).

    parse  →  split  →  link  →  classify  →  propagate  →  write

Usage
-----
    # 0. syllabus map (once)
    python -m taxonomy.build_syllabus uploads/Chemistry_Guide_2025.pdf

    # 1. full run with LlamaParse + Claude classifier
    export LLAMA_CLOUD_API_KEY=...  ANTHROPIC_API_KEY=...
    python -m ingest.pipeline --parser llamaparse --classifier claude

    # offline dev run (no API keys, text-only parse, lexical classifier)
    python -m ingest.pipeline --parser local --classifier lexical

    # re-parse one document
    python -m ingest.pipeline --only oxford_2023_excerpt --force-parse

Outputs
-------
    data/markdown/<doc_id>.jsonl         parsed pages (cache; LlamaParse is never re-billed)
    data/chunks/<doc_id>.jsonl           chunks + metadata (input to Part 2)
    data/reports/coverage.json           tagging / linking statistics
    data/reports/missing_markschemes.csv questions without a markscheme (Part 3 queue)
"""
from __future__ import annotations

import argparse
import json
import tomllib
from collections import Counter
from pathlib import Path

from . import classify, link, scan_books, scan_figures, scan_ocr
from .chunking import Chunk
from .parsers import get_parser, load_pages
from .splitters import SPLITTERS, SourceSpec

ROOT = Path(__file__).resolve().parents[1]
CHUNK_DIR = ROOT / "data" / "chunks"
REPORT_DIR = ROOT / "data" / "reports"


def load_manifest(path: Path) -> tuple[dict, list[SourceSpec]]:
    m = tomllib.loads(path.read_text(encoding="utf-8"))
    settings = m.get("settings", {})
    base = Path(settings.get("uploads_dir", "."))
    specs = []
    for s in m["source"]:
        p = Path(s["path"])
        specs.append(SourceSpec(
            doc_id=s["doc_id"], path=str(p if p.is_absolute() else base / p),
            source_type=s["source_type"], origin=s.get("origin", ""),
            profile=s.get("profile", ""), scope=s.get("scope", []),
            parser=s.get("parser"), cover_overrides=s.get("cover_override", []),
            scan=s if s["source_type"] == "scan_book" else {},
        ))
    return settings, specs


def run(args) -> None:
    _settings, specs = load_manifest(Path(args.manifest))
    if args.only:
        wanted = set(args.only)
        specs_to_parse = [s for s in specs if s.doc_id in wanted]
    else:
        specs_to_parse = specs

    # 1. parse (cached). A source may pin its own parser (e.g. parser = "pdftotext" for long text PDFs).
    parsers: dict[str, object] = {}
    for s in specs_to_parse:
        if s.source_type == "syllabus":
            continue                                      # built by taxonomy.build_syllabus
        if s.source_type == "scan_book":
            scan_ocr.merge(s.scan)                        # OCR runs separately (ingest.scan_ocr); Marker pages win
            continue
        if load_pages(s.doc_id) and not args.force_parse:
            continue
        name = s.parser or args.parser
        parsers.setdefault(name, get_parser(name))
        print(f"parse  {s.doc_id}  ({name}, profile={s.profile})")
        parsers[name].parse(s.doc_id, Path(s.path), s.profile, force=args.force_parse)

    # 2. split — always over ALL sources so links are complete
    chunks: list[Chunk] = []
    for s in specs:
        pages = load_pages(s.doc_id) if s.source_type != "syllabus" else None
        if s.source_type != "syllabus" and not pages:
            print(f"skip   {s.doc_id}: not parsed yet")
            continue
        got = SPLITTERS[s.source_type](s, pages)
        print(f"split  {s.doc_id:<32} {len(got):>5} chunks")
        chunks.extend(got)

    # 2b. drop duplicate papers: the same question/markscheme found again (another PDF, or a
    #     screenshot copy of a text page). Chunks of one question are emitted consecutively ("runs");
    #     per (type, ref) keep one run — a text-layer run over an OCR run, otherwise the first.
    runs: dict[tuple, list[list[Chunk]]] = {}
    order: list = []
    last = None
    for c in chunks:
        m = c.metadata
        unit = ((m["source_type"], m["question_ref"]) if m["source_type"] in {"past_paper", "markscheme"}
                and m.get("question_ref") and m.get("paper_code") else None)
        if unit is None:
            order.append(c); last = None
            continue
        if unit != last:
            runs.setdefault(unit, []).append([])
            if len(runs[unit]) == 1:
                order.append(unit)
        runs[unit][-1].append(c)
        last = unit
    deduped: list[Chunk] = []
    n_dup = 0
    for item in order:
        if isinstance(item, Chunk):
            deduped.append(item)
            continue
        cands = runs[item]
        best = next((r for r in cands if not any(x.metadata.get("ocr") for x in r)), cands[0])
        n_dup += sum(len(r) for r in cands if r is not best)
        deduped.extend(best)
    chunks = deduped
    print(f"dedupe {n_dup} duplicate official question/markscheme chunks dropped")

    # 2c. scanned books: run the automatic checks, then keep only what adds to or repairs the library.
    #     Splitting the RapidOCR text as well gives a second reading of every Marker page to compare.
    rapid_chunks = []
    for s in specs:
        if s.source_type == "scan_book" and s.scan.get("emit_chunks") is not False:
            rapid_chunks.extend(SPLITTERS["scan_book"](s, scan_ocr.rapid_pages(s.scan)))
    chunks, scan_report = scan_books.merge_with_library(chunks, rapid_chunks, scan_figures.load_index(), scan_figures.load_descriptions())
    scan_report["coverage"] = scan_books.coverage([s for s in specs if s.source_type == "scan_book"], load_pages)
    scan_books.write_report(scan_report)
    scan_figures.write_by_ref(chunks)
    # Amber/red book items wait for review: they must not change the library's links or tags in the meantime.
    held = [c for c in chunks if c.metadata.get("scan_quality") in {"amber", "red"}]
    chunks = [c for c in chunks if c.metadata.get("scan_quality") not in {"amber", "red"}]

    # 3. link
    qstats = link.link_questions_to_markschemes(chunks)
    aliases = link.link_by_content(chunks)
    qstats["variant_aliases_learned"] = aliases
    n_ans = link.link_textbook_answers(chunks)

    # 3b. examiner reports: learn 2025 TZ→paper-code aliases, then join by ref
    report_aliases = link.learn_report_variant_aliases(chunks, seed=aliases)
    rstats = link.link_examiner_reports(chunks, report_aliases)
    rstats["variant_aliases"] = report_aliases

    # 4. classify untagged units, 5. propagate to linked markschemes and examiner comments
    clf = classify.get_classifier(args.classifier)
    n_cls = classify.classify_chunks(chunks, clf)
    classify.classify_chunks([c for c in held if c.metadata["source_type"] == "past_paper"], clf)
    n_prop = scan_books.propagate_tags(chunks + held)     # a green answer letter takes its held question's sub-topic
    n_prop += link.propagate_tags(chunks)
    n_prop += link.propagate_report_tags(chunks)
    n_cls += classify.classify_chunks(chunks, clf)        # report comments with no linked question
    active = chunks
    chunks = chunks + held

    # 6. write
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    by_doc: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_doc.setdefault(c.metadata["doc_id"], []).append(c)
    for doc_id, cs in by_doc.items():
        with (CHUNK_DIR / f"{doc_id}.jsonl").open("w", encoding="utf-8") as f:
            for c in cs:
                f.write(json.dumps(c.to_json(), ensure_ascii=False) + "\n")

    n_missing = link.write_missing_markschemes(active, REPORT_DIR / "missing_markschemes.csv")
    report = coverage(chunks)
    report.update(linking=qstats, examiner_reports=rstats, textbook_answer_links=n_ans, classified=n_cls, propagated=n_prop,
                  missing_markschemes=n_missing, classifier=args.classifier, parser=args.parser)
    (REPORT_DIR / "coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total_chunks", "orphan_answer_keys", "tagged_pct_excluding_orphan_keys", "by_source_type", "linking",
                                              "examiner_reports",
                                              "missing_markschemes")}, indent=2))


def coverage(chunks: list[Chunk]) -> dict:
    by_type = Counter(c.metadata["source_type"] for c in chunks)
    tagged = [c for c in chunks if c.metadata.get("sub_topic")]
    per_sub = Counter((c.metadata["sub_topic"], c.metadata["source_type"]) for c in tagged)
    table: dict[str, dict] = {}
    for (sub, st), n in per_sub.items():
        table.setdefault(sub, {})[st] = n
    usable = [c for c in chunks if not c.metadata.get("orphan_answer_key")]
    return {
        "total_chunks": len(chunks),
        "orphan_answer_keys": len(chunks) - len(usable),
        "tagged_pct": round(100 * len(tagged) / max(1, len(chunks)), 1),
        "tagged_pct_excluding_orphan_keys": round(100 * len(tagged) / max(1, len(usable)), 1),
        "by_source_type": dict(by_type),
        "untagged_by_source_type": dict(Counter(c.metadata["source_type"] for c in chunks
                                                if not c.metadata.get("sub_topic"))),
        "tag_methods": dict(Counter(c.metadata.get("tag_method") for c in chunks)),
        "per_sub_topic": dict(sorted(table.items())),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(ROOT / "sources.toml"))
    ap.add_argument("--parser", choices=["llamaparse", "local"], default="llamaparse")
    ap.add_argument("--classifier", choices=["claude", "lexical"], default="claude")
    ap.add_argument("--only", nargs="*", help="doc_ids to (re)parse; splitting/linking always covers all")
    ap.add_argument("--force-parse", action="store_true")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
