"""
Turn the textbook pages for a sub-topic into short notes and key definitions, on the Pro plan.

    python -m engine.reference_builder R1.1 R1.2          (builds data/reference/<code>.json)
    python -m engine.reference_builder R1.1 --from-raw    (re-check the last finished build, with no new call)

Skips sub-topics whose book pages aren't in the library. Everything is paraphrased: the pages are a source, not something to reprint.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "chunks"
OUT = ROOT / "data" / "reference"
RAW = ROOT / "data" / "reports" / "raw_reference"
BOOK = CHUNKS / "oxford_2023_excerpt.jsonl"                      # the 94-page excerpt: a fallback only
COMPANION = ROOT / "data" / "books" / "companion"                 # the full Course Companion, by sub-topic (ingest.book_pages)
MAX_WORDS = {"point": 28, "definition": 30, "must_say": 6, "trap": 18, "heading": 8}

_STR = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {"type": "array", "items": {"type": "object", "properties": {
            "heading": _STR, "understanding": _STR, "points": {"type": "array", "items": _STR}},
            "required": ["heading", "understanding", "points"], "additionalProperties": False}},
        "definitions": {"type": "array", "items": {"type": "object", "properties": {
            "term": _STR, "definition": _STR, "must_say": {"type": "array", "items": _STR}, "trap": _STR},
            "required": ["term", "definition", "must_say", "trap"], "additionalProperties": False}},
    },
    "required": ["notes", "definitions"], "additionalProperties": False,
}
PROMPT = """You write revision notes for one IB Chemistry HL student (2025 syllabus), from pages of their textbook.

Return short notes and key definitions for sub-topic {code} {title}.

The book's text was extracted from two-column pages, so sentences from neighbouring columns can be interleaved. Work out what it means,
and never repeat a garbled sentence.

Rules
- Use only the book pages and syllabus below. Do not add chemistry that isn't there, and correct nothing silently: leave out what you can't read.
- Paraphrase in your own plain words. Never reuse more than 6 consecutive words from the book. Skip the book's questions and activities.
- Notes follow the syllabus understandings in order. For each: `heading` (at most 8 words), `understanding` (its code, such as R1.1.4) and
  `points`: 2-5 facts or steps a student must know, at most 28 words each. Include the formulas and units the student needs, in plain text.
- Definitions: every term in these pages that the student must be able to define. `definition` at most 30 words, worded so it would
  earn the mark. `must_say` lists the 1-4 exact words or conditions a marker looks for, at most 6 words each. `trap` is the usual slip, at most 18
  words, or an empty string if the pages show none.
- Data booklet facts: say something is in the booklet only if the syllabus text below says so.

<syllabus>
{syllabus}
</syllabus>

<examiner_comments_on_definitions>
{examiner}
</examiner_comments_on_definitions>

<book_pages>
{book}
</book_pages>
"""


def book_pages(code: str, path: Path = BOOK, folder: Path = COMPANION) -> str:
    """The full book's chapter for this sub-topic, or the excerpt's pages if the chapter hasn't been extracted."""
    chapter = folder / f"{code}.json"
    if chapter.exists():
        pages = json.loads(chapter.read_text(encoding="utf-8"))["pages"]
        return "\n\n".join(f"[page {p['printed']}]\n{p['text']}" for p in pages)
    if not path.exists():
        return ""
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    rows = [r for r in rows if r["metadata"].get("sub_topic") == code]
    return "\n\n".join(f"[page {r['metadata'].get('page_start')}]\n{r['text']}" for r in rows)


def syllabus_text(code: str) -> tuple[str, str, set[str]]:
    syl = json.loads((ROOT / "data" / "syllabus" / "syllabus.json").read_text(encoding="utf-8"))
    sub = next(s for s in syl["sub_topics"] if s["code"] == code)
    codes = [c for c, u in syl["understandings"].items() if u["sub_topic"] == code]
    lines = [f"{c} ({syl['understandings'][c].get('level')}): {syl['understandings'][c]['statement']} "
             f"Guidance: {' '.join(syl['understandings'][c].get('guidance') or [])}" for c in codes]
    return sub["title"], "\n".join(lines), set(codes)


def examiner_comments(code: str) -> str:
    found = []
    with (CHUNKS / "subject_reports_2001_2025.jsonl").open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["metadata"].get("sub_topic") != code:
                continue
            found += [s.strip() for s in re.split(r"(?<=[.!?])\s+", row["text"]) if re.search(r"\bdefin", s, re.I)]
    return "\n".join(dict.fromkeys(found))[:6000]


def check(result: dict, codes: set[str], book: str) -> list[str]:
    """Problems worth a human look: unknown syllabus codes, text too long to revise from, or wording lifted from the book."""
    out = []
    words = re.findall(r"\w+", book.lower())
    lifted = {" ".join(words[i:i + 9]) for i in range(len(words) - 8)}

    def copied(text: str) -> bool:
        w = re.findall(r"\w+", text.lower())
        return any(" ".join(w[i:i + 9]) in lifted for i in range(len(w) - 8))

    for note in result.get("notes", []):
        if note.get("understanding") not in codes:
            out.append(f"note '{note.get('heading')}' cites unknown understanding {note.get('understanding')}")
        if len(note.get("heading", "").split()) > MAX_WORDS["heading"]:
            out.append(f"heading too long: {note['heading'][:40]}")
        for point in note.get("points", []):
            if len(point.split()) > MAX_WORDS["point"]:
                out.append(f"point too long: {point[:50]}")
            if copied(point):
                out.append(f"point copies the book: {point[:50]}")
    seen = set()
    for item in result.get("definitions", []):
        term = item.get("term", "").strip().lower()
        if term in seen:
            out.append(f"definition repeated: {term}")
        seen.add(term)
        if len(item.get("definition", "").split()) > MAX_WORDS["definition"]:
            out.append(f"definition too long: {item.get('term')}")
        if copied(item.get("definition", "")):
            out.append(f"definition copies the book: {item.get('term')}")
    return out


def call_claude(prompt: str, model: str, timeout: int = 1200, schema: dict | None = None) -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code not found on PATH")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC", "CLAUDE"))}    # the plan, never API credit
    schema = json.dumps(schema or SCHEMA, separators=(",", ":"))
    cmd = [exe, "-p", "--model", model, "--effort", "medium", "--output-format", "json", "--json-schema", schema, "--tools", "",
           "--no-session-persistence"]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env)
    raw = (proc.stdout or "").strip()
    out = json.loads(raw.splitlines()[-1]) if raw else {}
    result = out.get("structured_output")
    if not result:
        raise RuntimeError(f"no result: {raw[-400:]} {(proc.stderr or '')[-300:]}")
    return result


def build(code: str, model: str = "sonnet", from_raw: bool = False) -> dict | None:
    book = book_pages(code)
    if not book:
        print(f"skip {code}: its book pages aren't in the library")
        return None
    title, syllabus, codes = syllabus_text(code)
    raw_path = RAW / f"{code}.json"
    if from_raw:
        result = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        result = call_claude(PROMPT.format(code=code, title=title, syllabus=syllabus, examiner=examiner_comments(code), book=book), model)
        RAW.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    result.update(sub_topic=code, title=title, generated_by=model, issues=check(result, codes, book))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{code}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{code}: {len(result['notes'])} note groups, {len(result['definitions'])} definitions, {len(result['issues'])} issues")
    for issue in result["issues"]:
        print("  !", issue)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--from-raw", action="store_true")
    a = ap.parse_args()
    for code in a.codes:
        try:
            build(code, a.model, a.from_raw)
        except Exception as e:                       # keep going with the next sub-topic
            print(f"FAILED {code}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
