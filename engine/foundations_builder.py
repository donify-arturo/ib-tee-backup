"""
Foundations: theory practice from the student's two Oxford books, kept apart from exam-style practice, on the Pro plan.

    python -m engine.foundations_builder R1.1 R1.2          (builds data/foundations/<code>.json)
    python -m engine.foundations_builder R1.1 --from-raw    (re-check the last finished build, with no new call)

Sources: the Course Companion (data/books/companion, ingest.book_pages) and IB Prepared (data/books/prepared, ingest.prepared_pages),
each with its publisher's answers. Three parts per sub-topic:
- practice:        both books' practice questions in plain words, same numbers, answered from the books' answers where they exist
- worked:          both books' worked examples as steps to try one at a time
- investigations:  the books' practical items (activities, skills and data-based questions) with the book's answers, then the
                   guide's Tool and Inquiry prompts, whose model answers are Claude's because the IB publishes none

Nothing here counts towards Mastered or flow mode. Every number in a question must appear on the book page it cites (checked).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from engine import reference_builder as rb

ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "data" / "books" / "companion"
PREPARED = ROOT / "data" / "books" / "prepared"
OUT = ROOT / "data" / "foundations"
RAW = ROOT / "data" / "reports" / "raw_foundations"
BOOKS = {"companion": "Course Companion", "prepared": "IB Prepared"}

_STR = {"type": "string"}
_LIST = {"type": "array", "items": _STR}
_SOURCE = {"type": "string", "enum": list(BOOKS)}
_FROM = {"type": "string", "enum": ["book", "claude"]}


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}


SCHEMA = _obj({
    "practice": {"type": "array", "items": _obj({
        "source": _SOURCE, "page": _STR, "understanding": _STR,
        "kind": {"type": "string", "enum": ["calculation", "multiple_choice", "short_answer"]},
        "question": _STR, "options": _LIST, "answer": _STR, "steps": _LIST, "answer_from": _FROM})},
    "worked": {"type": "array", "items": _obj({
        "source": _SOURCE, "page": _STR, "understanding": _STR, "title": _STR, "problem": _STR,
        "steps": {"type": "array", "items": _obj({"hint": _STR, "work": _STR})}})},
    "investigations": {"type": "array", "items": _obj({
        "source": {"type": "string", "enum": [*BOOKS, "guide"]}, "page": _STR, "understanding": _STR, "tag": _STR,
        "prompt": _STR, "model_answer": _LIST, "answer_from": _FROM})},
})

PROMPT = """You turn two textbooks' chapters on one IB Chemistry HL sub-topic (2025 syllabus) into theory practice for one student.
Sub-topic {code} {title}.

The books:
- companion: Oxford Course Companion. Text from two-column pages, so neighbouring columns can be interleaved; superscripts are lost
  ("kJ mol 1" means kJ mol⁻¹). Its answer booklet is below.
- prepared: Oxford IB Prepared. Its text is OCR from scans: formulas, superscripts and symbols are often garbled ("4.18|g'K'" is
  4.18 J g⁻¹ K⁻¹, "AH" is ΔH, "dm=3" is dm⁻³). Its publisher's answers are below, in the same order as its "Practice problems for {code}".
  Its pages also include the start of the next chapter: use only what belongs to {code}.
Work out what each passage means; leave out anything you can't read with confidence. Pages are labelled [companion page N] or [prepared page N].

Return three lists. Every item has `source` (companion or prepared) and `page` (its printed page number, from the label).

1. practice: every question in the companion's "Practice question(s)" boxes and end-of-topic questions, and every prepared "Problem N"
   under "Practice problems for {code}".
   - `question`: in your own plain words, keeping every number, unit, formula and chemical exactly. A multi-part question becomes one
     item per part, each self-contained. If it needs a graph or figure you can't see but the answers give the readings needed (such as an
     extrapolated temperature), state those readings in the question. Otherwise skip a question that needs a figure.
   - `kind` and `options` (the A-D options for multiple choice, rewritten; otherwise an empty list).
   - `answer`: the final answer. If that book's answers have it, use it and set `answer_from` "book"; otherwise work it out and set
     "claude". For multiple choice give the letter and the option. If the book's answer looks wrong, keep it and say why in `steps`.
   - `steps`: 1-5 short steps that reach the answer (an empty list for a one-word recall answer).
2. worked: every companion "Worked example" and every prepared "Example N" with its "Solution". `title` at most 8 words. `problem`
   rewritten in your own words with the same numbers. `steps`: 2-6 items, each with `hint` (what to do next, without the result, at most
   15 words) and `work` (that step done, with units).
3. investigations, in this order:
   a. Every companion "Activity", "Skills question(s)", "Data-based question(s)" and "ATL"/"Approaches to learning" question that its answer
      booklet answers, if it is about practical work, data or reasoning (not a research or poster task). `tag` is its label ("Activity",
      "Skills question"), `model_answer` 2-6 points from the booklet's answer, `answer_from` "book".
   b. One item per Tool or Inquiry prompt in the syllabus text below (marked "Tool" or "Inquiry" in its linking questions). `source` "guide",
      `page` "", `tag` such as "Tool 1, Inquiry 2", `model_answer` 3-6 points a strong student would make, using the book pages where they
      help, `answer_from` "claude".
   `prompt` is always a direct question to the student in your own words.

Rules for all three
- `understanding` is one syllabus code from the list below, such as {code}.2.
- Never reuse more than 8 consecutive words from either book.
- Data booklet: pH, pOH, Kw and n = CV are in section 1; Kw's value in section 2. pH + pOH = 14, pKa + pKb = 14, Ka × Kb = Kw and the
  buffer equation are NOT in the booklet. Say something is in the booklet only if the syllabus text says so.
- Use the book's own constants and keep significant figures sensible.

<syllabus>
{syllabus}
</syllabus>

<companion_answer_booklet>
{answers}
</companion_answer_booklet>

<prepared_answers>
{prepared_answers}
</prepared_answers>

<book_pages>
{book}
</book_pages>
"""

_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


def _words(text: str) -> list[str]:
    """Words of 3+ letters: digits and formula fragments (Ba, OH, aq, g) are left out, since questions must keep the book's
    numbers and equations."""
    return [w for w in re.findall(r"[^\W\d_]{3,}", text.lower())]


def booklet_numbers(path: Path = ROOT / "data" / "chunks" / "data_booklet_2025.jsonl") -> set[str]:
    """Every number in the data booklet: a question may quote booklet values (bond enthalpies, ΔHf) that its page doesn't print."""
    if not path.exists():
        return set()
    return set(_NUMBER.findall(path.read_text(encoding="utf-8")))


def chapter(code: str, folder: Path = COMPANION) -> dict | None:
    path = folder / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def answers_text(ch: dict | None) -> str:
    """The companion's answer blocks, or IB Prepared's answers (one text per sub-topic)."""
    if not ch:
        return ""
    if isinstance(ch.get("answers"), str):
        return ch["answers"]
    return "\n\n".join(f"[{a['kind']} on page {a['page']}]\n{a['text'].lstrip(')').strip()}" for a in ch.get("answers", []))


def pages_text(ch: dict | None, label: str = "") -> str:
    if not ch:
        return ""
    tag = f"{label} page" if label else "page"
    return "\n\n".join(f"[{tag} {p['printed']}]\n{p['text']}" for p in ch["pages"])


def check(result: dict, codes: set[str], ch: dict, prep: dict | None = None) -> list[str]:
    """Problems worth a human look: unknown pages or codes, numbers the cited page doesn't have, wording lifted from a book."""
    out = []
    books = {"companion": ch, "prepared": prep}
    by_page = {name: {str(p["printed"]): p["text"] for p in b["pages"]} for name, b in books.items() if b}
    words = _words(pages_text(ch) + "\n" + pages_text(prep))
    allowed = booklet_numbers() | set(_NUMBER.findall(answers_text(ch) + answers_text(prep)))   # booklet values, answers carried over
    lifted = {" ".join(words[i:i + 9]) for i in range(len(words) - 8)}

    def copied(text: str) -> bool:
        w = _words(text)
        return any(" ".join(w[i:i + 9]) in lifted for i in range(len(w) - 8))

    def numbers_on_page(text: str, pages: dict, page: str) -> list[str]:
        """Numbers in a rewritten question that neither the cited page nor its neighbours contain."""
        nearby = "".join(pages.get(str(int(page) + d), "") for d in (-1, 0, 1)) if page.isdigit() else ""
        have = set(_NUMBER.findall(nearby)) | allowed
        return [n for n in _NUMBER.findall(text) if n not in have and len(n) > 1]

    for kind in ("practice", "worked", "investigations"):
        for i, item in enumerate(result.get(kind, []), 1):
            source = item.get("source", "companion")
            label = f"{kind} {i} ({BOOKS.get(source, source)} p{item.get('page')})"
            if item.get("understanding") not in codes:
                out.append(f"{label}: unknown understanding {item.get('understanding')}")
            if source == "guide":
                continue
            pages = by_page.get(source)
            if pages is None:
                out.append(f"{label}: that book isn't in the library")
                continue
            if str(item.get("page")) not in pages:
                out.append(f"{label}: page not in this chapter")
            text = item.get("question") or item.get("problem") or item.get("prompt") or ""
            if copied(text):
                out.append(f"{label}: copies the book")
            missing = numbers_on_page(text, pages, str(item.get("page")))
            if missing:
                out.append(f"{label}: numbers not on the cited page: {', '.join(missing[:5])}")
    return out


# --------------------------------------------------------------------------- #
# keeping book questions apart from past papers
# --------------------------------------------------------------------------- #
# Books reprint some IB questions without saying so. Those belong to the Questionbank, not to Book practice, so each item is compared
# with every past-paper question in the library. Rewording changes the words but not the numbers, so a match needs shared numbers.
_REAL_NUMBER = re.compile(r"(?<![A-Za-z\d.])[−-]?\d+(?:\.\d+)?(?![A-Za-z\d.])")   # not digits in formulas (CH4, 4NH3, H2O)
_STOP = set("which what with that this from have when then than they their there were will would into each give state using "
            "calculate determine explain following below above shown value values both also only more most such data".split())
_COMMON = {"4.18", "8.31", "6.02", "22.7", "100", "298", "273", "1.00"}  # constants any question may quote: no evidence of a match
_LIBRARY: list[tuple[str, set[str], set[str]]] | None = None


def _fingerprint(text: str) -> tuple[set[str], set[str]]:
    text = text.lower().replace("−", "-")
    numbers = {n.lstrip("-") for n in _REAL_NUMBER.findall(text)}
    words = {w for w in re.findall(r"[a-z]{4,}", text) if w not in _STOP}
    return numbers, words


def past_paper_library(folder: Path = ROOT / "data" / "chunks") -> list[tuple[str, set[str], set[str]]]:
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = []
        for path in folder.glob("*.jsonl"):
            for line in path.open(encoding="utf-8"):
                row = json.loads(line)
                meta = row["metadata"]
                if meta["source_type"] == "past_paper" and meta.get("question_ref"):
                    _LIBRARY.append((meta["question_ref"], *_fingerprint(row["text"])))
    return _LIBRARY


def match_past_paper(text: str, library: list[tuple[str, set[str], set[str]]]) -> tuple[str, bool]:
    """(best library ref, whether it is a confident match). Short wordy questions without numbers rarely match confidently."""
    numbers, words = _fingerprint(text)
    best, best_score, sure = "", 0.0, False
    for ref, lib_numbers, lib_words in library:
        n_hit, w_hit = len(numbers & lib_numbers), len(words & lib_words)
        n_ratio = n_hit / len(numbers) if numbers else 0.0
        w_ratio = w_hit / len(words) if words else 0.0
        score = (n_ratio + w_ratio) / 2 if numbers else w_ratio
        if score <= best_score:
            continue
        best, best_score = ref, score
        distinctive = {n for n in numbers if len(n.replace(".", "")) >= 2 and n not in _COMMON}
        d_hit = len(distinctive & lib_numbers)
        d_ratio = d_hit / len(distinctive) if distinctive else 0.0
        sure = ((d_hit >= 3 and d_ratio >= 0.7 and w_ratio >= 0.4)                            # a question's own data
                or (d_hit >= 4 and d_ratio >= 0.6 and w_ratio >= 0.4)                         # ...when editions round differently
                or (n_hit >= 2 and n_ratio == 1 and d_hit >= 1 and w_ratio >= 0.65)          # every number, most words
                or (not numbers and w_hit >= 10 and w_ratio >= 0.85))                        # wordy, near-identical
    return best, sure


def mark_past_papers(result: dict, library: list | None = None) -> int:
    """Set `past_paper_ref` on practice and worked items reprinted from an IB paper. Later parts of a matched question (same book and
    page, same best match, straight after it) follow it. Returns how many items were marked."""
    library = past_paper_library() if library is None else library
    marked = 0
    for kind in ("practice", "worked"):
        previous = None
        for item in result.get(kind, []):
            text = " ".join([item.get("question") or item.get("problem") or "", *(item.get("options") or [])])
            ref, sure = match_past_paper(text, library)
            follows = (previous is not None and previous.get("past_paper_ref") == ref and previous.get("source") == item.get("source")
                       and previous.get("page") == item.get("page"))
            item["past_paper_ref"] = ref if sure or follows else ""
            marked += bool(item["past_paper_ref"])
            previous = item
    return marked


class UsageLimit(RuntimeError):
    """The plan's usage limit stopped a call: stop the run, and rerun later to continue."""


def build(code: str, model: str = "sonnet", from_raw: bool = False) -> dict | None:
    ch = chapter(code)
    if not ch:
        print(f"skip {code}: its chapter isn't in data/books/companion")
        return None
    prep = chapter(code, PREPARED)
    title, syllabus, codes = rb.syllabus_text(code)
    syl = json.loads((ROOT / "data" / "syllabus" / "syllabus.json").read_text(encoding="utf-8"))
    links = [f"{c} linking questions: {' | '.join(u.get('linking_questions') or [])}" for c, u in syl["understandings"].items()
             if u["sub_topic"] == code and u.get("linking_questions")]
    raw_path = RAW / f"{code}.json"
    if from_raw:
        result = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        prompt = PROMPT.format(code=code, title=title, syllabus=syllabus + "\n" + "\n".join(links), answers=answers_text(ch),
                               prepared_answers=answers_text(prep) or "(none)",
                               book=pages_text(ch, "companion") + "\n\n" + pages_text(prep, "prepared"))
        try:
            result = rb.call_claude(prompt, model, timeout=2400, schema=SCHEMA)
        except RuntimeError as e:
            if re.search(r"usage limit|limit reached|hit your limit|rate.?limit", str(e), re.I):
                raise UsageLimit(str(e)[-300:]) from e
            raise
        RAW.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    result.update(sub_topic=code, title=title, generated_by=model,
                  books=[b for b, have in (("Oxford IB Chemistry Course Companion 2023", ch), ("Oxford IB Prepared Chemistry 2024", prep)) if have],
                  issues=check(result, codes, ch, prep))
    n_past = mark_past_papers(result)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{code}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{code}: {len(result['practice'])} practice, {len(result['worked'])} worked, "
          f"{len(result['investigations'])} investigations, {n_past} from past papers, {len(result['issues'])} issues")
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
    ap.add_argument("--force", action="store_true", help="rebuild sub-topics that already have Foundations")
    a = ap.parse_args()
    for code in a.codes:
        if not (a.force or a.from_raw) and load(code):
            print(f"skip {code}: Foundations exist (use --force to rebuild)")
            continue
        try:
            build(code, a.model, a.from_raw)
        except UsageLimit as e:                      # resumable: finished sub-topics are skipped next time
            print(f"STOPPED at {code}: usage limit reached; rerun later to continue. {e}", file=sys.stderr)
            sys.exit(3)
        except Exception as e:                       # keep going with the next sub-topic
            print(f"FAILED {code}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
