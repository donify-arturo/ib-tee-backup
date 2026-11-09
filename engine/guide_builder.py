"""
Study guide: a full explanation of each syllabus understanding from the student's two Oxford books, on the Pro plan.

    python -m engine.guide_builder R1.1 R1.2            (builds data/guide/<code>.json; skips built ones unless --force)
    python -m engine.guide_builder R1.1 --from-raw      (re-check the last finished build, with no new call)

For each understanding: an explanation covering everything the books teach about it, key points (the quick summary), formulas,
exam tips (mostly IB Prepared's assessment tips), common mistakes, and the book pages it is on, so the app can show the real pages.
The books are the student's own copies, used privately; explanations follow them closely and keep their numbers and examples.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from engine import foundations_builder as fb
from engine import reference_builder as rb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "guide"
RAW = ROOT / "data" / "reports" / "raw_guide"

_STR = {"type": "string"}
_LIST = {"type": "array", "items": _STR}
SCHEMA = fb._obj({
    "overview": _STR,
    "sections": {"type": "array", "items": fb._obj({
        "understanding": _STR, "title": _STR, "explanation": _STR, "key_points": _LIST,
        "formulas": {"type": "array", "items": fb._obj({"formula": _STR, "meaning": _STR})},
        "exam_tips": _LIST, "mistakes": _LIST, "companion_pages": _LIST, "prepared_pages": _LIST})},
})

PROMPT = """You write the study guide for one IB Chemistry HL sub-topic (2025 syllabus) for one student, from their own two textbooks.
Sub-topic {code} {title}.

The books:
- companion: Oxford Course Companion, the main textbook. Text from two-column pages, so neighbouring columns can be interleaved;
  superscripts are lost ("kJ mol 1" means kJ mol⁻¹). Its sections are often marked with their syllabus code, e.g. "(Reactivity 1.1.2)".
- prepared: Oxford IB Prepared, a revision guide with "Assessment tip" boxes. OCR text: formulas and symbols are often garbled
  ("AH" is ΔH, "dm=3" is dm⁻³). Its pages also include the start of the next chapter: use only what belongs to {code}.
Pages are labelled [companion page N] or [prepared page N]. Work out what each passage means; leave out what you can't read.

Return:
- overview: 2-4 sentences on what this sub-topic is about and how its parts connect, answering the syllabus guiding question.
- sections: one per syllabus understanding below, in order, each with:
  - understanding: its code. title: at most 8 words.
  - explanation: everything the books teach for this understanding, as a clear, complete explanation a student can learn from
    without the book: the ideas and why they are true, every definition, equation and unit, the books' examples and numbers, and
    the HL detail if it is HL. Follow the books closely; organise it better where the extracted text is jumbled. Markdown: short
    paragraphs, **bold** for terms, bullet lists where helpful, no headings, no tables. Typically 200-700 words; longer where the
    books say more. Don't include the books' practice questions or worked examples (the app shows those separately).
  - key_points: 3-7 one-line facts to remember (the quick revision summary).
  - formulas: each equation the student must use, with what it means and its units (empty if none). Say "(in the data booklet)" in
    `meaning` only if the syllabus text below says it is in the booklet.
  - exam_tips: the books' advice for exams on this point (IB Prepared's "Assessment tip" boxes especially), in your words.
  - mistakes: the slips the books warn about (empty if none).
  - companion_pages, prepared_pages: the printed page numbers where each book covers this understanding (empty if it doesn't).

Rules
- Use only the books and syllabus below. Correct nothing silently: if the books disagree, say so.
- Data booklet: pH, pOH, Kw and n = CV are in section 1; Kw's value in section 2. pH + pOH = 14, pKa + pKb = 14, Ka × Kb = Kw and
  the buffer equation are NOT in the booklet.

<syllabus>
{syllabus}
</syllabus>

<book_pages>
{book}
</book_pages>
"""


def check(result: dict, codes: set[str], ch: dict, prep: dict | None) -> list[str]:
    """Problems worth a look: missing or unknown understandings, pages that aren't in the chapters, very short explanations."""
    out = []
    pages = {"companion": {str(p["printed"]) for p in ch["pages"]}, "prepared": {str(p["printed"]) for p in (prep or {}).get("pages", [])}}
    seen = [s.get("understanding") for s in result.get("sections", [])]
    out += [f"no section for {c}" for c in sorted(codes - set(seen))]
    for section in result.get("sections", []):
        code = section.get("understanding")
        if code not in codes:
            out.append(f"section for unknown understanding {code}")
        for book in ("companion", "prepared"):
            wrong = [p for p in section.get(f"{book}_pages", []) if str(p) not in pages[book]]
            if wrong:
                out.append(f"{code}: {book} pages not in the chapter: {', '.join(map(str, wrong[:5]))}")
        if len(re.findall(r"\w+", section.get("explanation", ""))) < 80:
            out.append(f"{code}: explanation is under 80 words")
    return out


def build(code: str, model: str = "sonnet", from_raw: bool = False) -> dict | None:
    ch = fb.chapter(code)
    if not ch:
        print(f"skip {code}: its chapter isn't in data/books/companion")
        return None
    prep = fb.chapter(code, fb.PREPARED)
    title, syllabus, codes = rb.syllabus_text(code)
    syl = json.loads((ROOT / "data" / "syllabus" / "syllabus.json").read_text(encoding="utf-8"))
    guiding = next(s.get("guiding_question", "") for s in syl["sub_topics"] if s["code"] == code)
    raw_path = RAW / f"{code}.json"
    if from_raw:
        result = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        prompt = PROMPT.format(code=code, title=title, syllabus=f"Guiding question: {guiding}\n{syllabus}",
                               book=fb.pages_text(ch, "companion") + "\n\n" + fb.pages_text(prep, "prepared"))
        try:
            result = rb.call_claude(prompt, model, timeout=2400, schema=SCHEMA)
        except RuntimeError as e:
            if re.search(r"usage limit|limit reached|hit your limit|rate.?limit", str(e), re.I):
                raise fb.UsageLimit(str(e)[-300:]) from e
            raise
        RAW.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    result.update(sub_topic=code, title=title, guiding_question=guiding, generated_by=model, issues=check(result, codes, ch, prep))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{code}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    words = sum(len(s.get("explanation", "").split()) for s in result["sections"])
    print(f"{code}: {len(result['sections'])} sections, {words} words of explanation, {len(result['issues'])} issues")
    for issue in result["issues"]:
        print("  !", issue)
    return result


def load(code: str, folder: Path = OUT) -> dict | None:
    path = folder / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--from-raw", action="store_true")
    ap.add_argument("--force", action="store_true", help="rebuild sub-topics that already have a guide")
    a = ap.parse_args()
    for code in a.codes:
        if not (a.force or a.from_raw) and load(code):
            print(f"skip {code}: guide exists (use --force to rebuild)")
            continue
        try:
            build(code, a.model, a.from_raw)
        except fb.UsageLimit as e:
            print(f"STOPPED at {code}: usage limit reached; rerun later to continue. {e}", file=sys.stderr)
            sys.exit(3)
        except Exception as e:
            print(f"FAILED {code}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
