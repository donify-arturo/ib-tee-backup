"""
Read-only access to the built Maths AI HL data (see ingest/maths_*.py). Every loader re-reads its file when the file changes.

    data/maths/syllabus.json      topics, 78 sub-topics, study notes, worked-solution chapters
    data/maths/questions.json     347 past-paper questions with parts, markscheme/report text and PDF regions
    data/maths/calculator.json    86 fx-CG50 sheets, their steps and extracted screens
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "maths"
SCREENS = DIR / "calculator_screens"
DIFFICULTIES = ["Basic", "Standard", "Hard HL", "Multi-step"]
DIFFICULTY_NOTE = "Estimated from the question's marks and number of parts, not from IB statistics."


def _mtime(name: str) -> float:
    p = DIR / name
    return p.stat().st_mtime if p.exists() else 0.0


@lru_cache(maxsize=16)
def _load(name: str, stamp: float) -> dict:
    p = DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def syllabus() -> dict:
    return _load("syllabus.json", _mtime("syllabus.json"))


def bank() -> dict:
    return _load("questions.json", _mtime("questions.json"))


def calculator() -> dict:
    return _load("calculator.json", _mtime("calculator.json"))


@lru_cache(maxsize=2)
def _depth(stamp: float) -> dict:
    out: dict = {}
    for p in sorted((DIR / "notes").glob("topic*.json")):
        out.update(json.loads(p.read_text(encoding="utf-8")))
    return out


def depth(code: str) -> dict:
    """The fuller study notes for a sub-topic (data/maths/notes/topic*.json, hand-written for the app): i plain idea, h going deeper,
    q/s/a worked example with why for each step, f {formula name: [variables, when to use it]}."""
    folder = DIR / "notes"
    stamp = max((p.stat().st_mtime for p in folder.glob("topic*.json")), default=0.0)
    return _depth(stamp).get(code, {})


def guide(sid: str) -> dict:
    """What to know about one calculator sheet (data/maths/calculator_guides.json, written for the app; it never gives key presses)."""
    return _load("calculator_guides.json", _mtime("calculator_guides.json")).get(sid, {})


CALC_LEVELS = {1: "Basic", 2: "Standard", 3: "Hard"}


def calc_level(sid: str) -> str:
    return CALC_LEVELS.get(guide(sid).get("lv"), "Standard")


def available() -> dict[str, bool]:
    return {"syllabus": bool(syllabus()), "questions": bool(bank()), "calculator": bool(calculator())}


# ---------------------------------------------------------------- syllabus
def topics() -> list[dict]:
    return syllabus().get("topics", [])


def subtopics() -> list[dict]:
    return syllabus().get("subtopics", [])


def subtopic(code: str) -> dict | None:
    return next((s for s in subtopics() if s["code"] == code), None)


def topic(n: int) -> dict | None:
    return next((t for t in topics() if t["n"] == n), None)


def topic_of(code: str) -> int:
    return int(str(code).split(".")[0])


def sub_title(code: str) -> str:
    s = subtopic(code)
    return s["title"] if s else code


def code_key(code: str) -> tuple[int, int]:
    a, b = str(code).split(".")
    return int(a), int(b)


# ---------------------------------------------------------------- questions
def questions() -> list[dict]:
    return bank().get("questions", [])


@lru_cache(maxsize=2)
def _by_id(stamp: float) -> dict[str, dict]:
    return {q["id"]: q for q in questions()}


def question(qid: str) -> dict | None:
    return _by_id(_mtime("questions.json")).get(qid)


def difficulty(q: dict) -> str:
    marks, parts = q["max_marks"], len(q["parts"])
    if marks >= 14 or parts >= 6:
        return "Multi-step"
    if marks >= 9:
        return "Hard HL"
    if marks >= 6:
        return "Standard"
    return "Basic"


def questions_for(code: str | None = None, topic_n: int | None = None, primary_only: bool = False) -> list[dict]:
    """Questions tagged with a sub-topic (any part, or only its main tag) or belonging to a topic; easiest first."""
    out = []
    for q in questions():
        if code:
            tags = q["subtopics"][:1] if primary_only else q["subtopics"]
            if code not in tags:
                continue
        if topic_n and q["topic"] != topic_n and topic_n not in q.get("cross_topics", []):
            continue
        out.append(q)
    return sorted(out, key=lambda q: (DIFFICULTIES.index(difficulty(q)), q["max_marks"], q["id"]))


def part_subtopic(q: dict, label: str) -> str:
    return q.get("part_subtopics", {}).get(label) or (q["subtopics"][0] if q["subtopics"] else f"{q['topic']}.1")


def session_sort_key(code: str | None) -> tuple:
    if code and re.fullmatch(r"\d\d[MN]", code):
        return (0, -int(code[:2]), code[2] == "M")
    return (1, code or "")


def search(text: str, pool: list[dict] | None = None) -> list[dict]:
    """Questions whose reference, question text or markscheme mention every word of the query."""
    words = [w for w in re.split(r"\s+", text.lower().strip()) if w]
    if not words:
        return pool if pool is not None else questions()
    out = []
    for q in pool if pool is not None else questions():
        blob = (q["id"] + " " + " ".join(p["q_text"] + " " + p["ms_text"] for p in q["parts"])).lower()
        if all(w in blob for w in words):
            out.append(q)
    return out


def snippet(q: dict, n: int = 220) -> str:
    """The start of the question text, tidied for a one-line preview."""
    text = re.sub(r"\s+", " ", q["parts"][0]["q_text"] if q["parts"] else "").strip()
    return text[:n] + ("…" if len(text) > n else "")


# ---------------------------------------------------------------- calculator
def sheets() -> list[dict]:
    return calculator().get("sheets", [])


def sheet(sid: str) -> dict | None:
    return next((s for s in sheets() if s["id"] == sid), None)


def sheets_for(code: str) -> list[dict]:
    return [s for s in sheets() if code in s.get("subtopics", [])]


def screen_path(name: str) -> Path:
    return SCREENS / name


# ---------------------------------------------------------------- worked solutions
def worked_chapters(code: str | None = None) -> list[dict]:
    chapters = syllabus().get("worked_solutions", [])
    return [c for c in chapters if code is None or code in c["subtopics"]]


# ---------------------------------------------------------------- the course book
def book() -> dict:
    return _load("book.json", _mtime("book.json"))


def book_sections(code: str | None = None, topic_n: int | None = None) -> list[dict]:
    """Book sections teaching a sub-topic (or any sub-topic of a topic), in book order."""
    out = []
    for s in book().get("sections", []):
        if code and code not in s["subtopics"]:
            continue
        if topic_n and not any(topic_of(c) == topic_n for c in s["subtopics"]):
            continue
        out.append(s)
    return out


def book_section(code: str) -> dict | None:
    return next((s for s in book().get("sections", []) if s["code"] == code), None)


def book_questions(code: str | None = None, exercise: str | None = None, topic_n: int | None = None) -> list[dict]:
    """Exercise questions from the course book (data/maths/book_questions.json), kept apart from the past-paper bank."""
    out = _load("book_questions.json", _mtime("book_questions.json")).get("questions", [])
    if code:
        out = [q for q in out if code in q["subtopics"]]
    if exercise:
        out = [q for q in out if q["exercise"] == exercise]
    if topic_n:
        out = [q for q in out if any(topic_of(c) == topic_n for c in q["subtopics"])]
    return out


def book_features(kind: str, code: str | None = None, section: str | None = None) -> list[dict]:
    """kind: investigations, inquiry or examples (data/maths/book_investigations.json)."""
    out = _load("book_investigations.json", _mtime("book_investigations.json")).get(kind, [])
    if code:
        out = [f for f in out if code in f["subtopics"]]
    if section:
        out = [f for f in out if f["section"] == section]
    return out


def book_passages(code: str | None = None, section: str | None = None) -> list[dict]:
    """The book's own teaching, passage by passage (data/maths/book_passages.json): real crops, in book order."""
    out = _load("book_passages.json", _mtime("book_passages.json")).get("passages", [])
    if code:
        out = [p for p in out if code in p["subtopics"]]
    if section:
        out = [p for p in out if p["section"] == section]
    return out


def book_corrections(key: str) -> list[dict]:
    """Rows of the publisher's corrections file for "7E.6", "7.Example9" or "7.Investigation2"."""
    return [r for r in _load("book_corrections.json", _mtime("book_corrections.json")).get("rows", []) if r["key"] == key]


def book_example(chapter: int, number: int) -> dict | None:
    return next((f for f in book_features("examples") if f["chapter"] == chapter and f["number"] == number), None)


def connections(code: str) -> list[dict]:
    """The sub-topics linked to this one and the evidence for each (data/maths/connections.json), strongest first."""
    return _load("connections.json", _mtime("connections.json")).get("links", {}).get(code, [])


def connection_map() -> dict:
    return _load("connections.json", _mtime("connections.json"))


def book_review(chapter: int) -> dict | None:
    return next((r for r in _load("book_investigations.json", _mtime("book_investigations.json")).get("reviews", []) if r["chapter"] == chapter), None)


def exercise_pages(ex: str) -> tuple[list[int], list[int], str | None]:
    """(book PDF pages, worked-solution PDF pages, worked-solution doc key) for an exercise such as "7A"."""
    chapter = int(re.match(r"\d+", ex).group(0))
    ch = next((c for c in book().get("chapters", []) if c["n"] == chapter), None)
    book_pages: list[int] = []
    if ch and ex in ch["exercises"]:
        starts = sorted(ch["exercises"].values())
        start = ch["exercises"][ex]
        sec = next((s for s in book().get("sections", []) if s["pdf_start"] <= start <= s["pdf_end"]), None)
        later = [p for p in starts if p > start]
        section_end = sec["pdf_end"] if sec else ch["pdf_end"]
        end = min(later[0], section_end) if later else section_end      # the next exercise may start on the same page
        book_pages = list(range(start, max(start, end) + 1))
    ws = next((c for c in worked_chapters() if c["chapter"] == chapter), None)
    ws_pages: list[int] = []
    if ws and ex in ws["exercises"]:
        start = ws["exercises"][ex]
        later = sorted(p for p in ws["exercises"].values() if p > start)
        end = later[0] if later else ws["last_page"]
        ws_pages = list(range(start, max(start, end) + 1))
    return book_pages, ws_pages, ws["doc"] if ws else None
