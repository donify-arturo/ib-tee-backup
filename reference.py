"""
Reference data for the app's menu: book notes and key definitions, the data booklet, grade boundaries, and a question's header facts.

    data/reference/<code>.json    notes and definitions built by engine/reference_builder.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
REFERENCE_DIR = DATA / "reference"
REPORT_PAGES = DATA / "markdown" / "subject_reports_2001_2025.jsonl"
BOOKLET = DATA / "chunks" / "data_booklet_2025.jsonl"

_SESSION = re.compile(r"\b(May|Nov(?:ember)?)\s+(\d{4})\s+subject|subject\s+reports?\s*[–-]\s*(May|Nov(?:ember)?)\s+(\d{4})", re.I)
_VARIANT = re.compile(r"\b(?:TZ|Time\s*zone)\s*(\d)\b", re.I)
_GRADE_ROW = re.compile(r"Grade:?\s+1\s+2\s+3\s+4\s+5\s+6\s+7\s+Mark range:?([^A-Za-z]*)", re.I)
_WORD_NUMBER = {"one": "1", "two": "2", "three": "3"}


def _component(lines: list[str]) -> tuple[str, str] | None:
    """('HL', 'Paper 1A') from the lines above a table. A bare 'Higher level' means the overall grade."""
    useful = [line for line in lines if not re.fullmatch(r"(component )?grade boundaries:?|(hl and sl )?component grade boundaries:?", line, re.I)]
    if not useful:
        return None
    heading = useful[-1]
    text = heading.lower()
    if "overall grade boundaries" in text:
        return None
    if "internal assessment" in text or "practical" in text:
        return "HL/SL", "Internal assessment"
    level = "HL/SL" if "higher" in text and "standard" in text else "HL" if "higher" in text else "SL" if "standard" in text else None
    if not level:
        return None
    paper = re.search(r"paper\s+(one|two|three|[123])", text)
    if paper:
        number = _WORD_NUMBER.get(paper.group(1), paper.group(1))
        section = re.search(r"section\s+([ab])", text)
        return level, f"Paper {number}{section.group(1).upper() if section else ''}"
    return level, "Overall"


def parse_boundaries(pages: list[str]) -> list[dict]:
    """Every grade boundary table in the subject reports. A session's first table for a component wins."""
    rows, seen, session, variant = [], set(), None, ""
    for text in pages:
        found = _SESSION.search(text[:400])
        if found:
            month, year = (found.group(1), found.group(2)) if found.group(1) else (found.group(3), found.group(4))
            session = ("May" if month.lower().startswith("may") else "November", int(year))
            tz = _VARIANT.search(text[:200])
            variant = f"TZ{tz.group(1)}" if tz else ""
        if session is None:
            continue
        for match in _GRADE_ROW.finditer(text):
            before = [line.strip() for line in text[:match.start()].splitlines() if line.strip()]
            component = _component(before)
            numbers = re.findall(r"\d+", match.group(1))
            if not component or len(numbers) < 14:
                continue
            key = (*session, variant, *component)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"month": session[0], "year": session[1], "variant": variant, "level": component[0], "component": component[1],
                         "ranges": [f"{numbers[i]}–{numbers[i + 1]}" for i in range(0, 14, 2)]})
    return rows


def grade_boundaries(path: Path = REPORT_PAGES) -> list[dict]:
    if not path.exists():
        return []
    pages = [json.loads(line).get("markdown", "") for line in path.open(encoding="utf-8")]
    rows = parse_boundaries(pages)
    return sorted(rows, key=lambda r: (-r["year"], r["month"] != "November", r["component"]))


# --------------------------------------------------------------------------- #
# data booklet
# --------------------------------------------------------------------------- #
def _undouble(line: str) -> str:
    """Bold text comes out of the PDF with every letter twice: 'llaattttiiccee' is 'lattice'."""
    def fix(match: re.Match) -> str:
        word = match.group(0)
        pairs = [word[i:i + 2] for i in range(0, len(word), 2)]
        return word[::2] if len(word) >= 4 and len(word) % 2 == 0 and all(p[0] == p[1] for p in pairs) else word
    return re.sub(r"\S+", fix, line)


def clean_booklet_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = _undouble(re.sub(r"\(cid:\d+\)", " ", line)).replace("ÖÖ", "⦵").replace("Ö", "⦵").rstrip()
        if line.strip() and not (lines and lines[-1] == line):
            lines.append(line)
    return "\n".join(lines)


def booklet_sections(path: Path = BOOKLET) -> dict[int, dict]:
    """{section number: {title, text}}, joining sections that span two pages."""
    out: dict[int, dict] = {}
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        text = json.loads(line)["text"]
        head = re.match(r"\s*Data booklet section (\d+)\.\s*([^\n]*)", text)
        if not head:
            continue
        number = int(head.group(1))
        body = clean_booklet_text(text[head.end():])
        if number in out:
            out[number]["text"] += "\n" + body
        else:
            out[number] = {"title": head.group(2).strip(), "text": body}
    return dict(sorted(out.items()))


# --------------------------------------------------------------------------- #
# book notes and definitions
# --------------------------------------------------------------------------- #
def load_reference(code: str, folder: Path | None = None) -> dict | None:
    path = (folder or REFERENCE_DIR) / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def extra_questions(path: Path | None = None) -> list[dict]:
    """Library questions read and checked by hand: [{ref, topic, source, card}]."""
    file = path or DATA / "extra_questions.json"
    return json.loads(file.read_text(encoding="utf-8"))["questions"] if file.exists() else []


def add_extras_to_deck(deck: dict, code: str, extras: list[dict]) -> dict:
    """Checked questions count as more of their card's type, so flow mode can bring them back as fresh questions."""
    for extra in extras:
        if extra["topic"] != code or not extra.get("card"):
            continue
        for card in deck.get("cards", []):
            wt = card.get("walkthrough")
            if wt and card["card_id"] == extra["card"] and extra["ref"] not in wt.setdefault("try_next", []):
                wt["try_next"].append(extra["ref"])
    return deck


# --------------------------------------------------------------------------- #
# question header
# --------------------------------------------------------------------------- #
def difficulty(pct_correct) -> str | None:
    """From the % correct examiners report. Most questions have no figure, and then no difficulty is claimed."""
    try:
        value = float(pct_correct)
    except (TypeError, ValueError):
        return None
    return "Easy" if value >= 75 else "Standard" if value >= 50 else "Hard"


OLD_PAPER = {"1": "1A", "3": "1B"}     # the old multiple-choice paper is today's 1A; the old data and practical paper is closest to 1B


def paper_of(ref: str) -> str:
    """Today's paper name from a question's ref: '1A' from '25M.1A.HL.6207.24' or from an old '14M.1.HL.TZ2.19'."""
    parts = (ref or "").split(".")
    return OLD_PAPER.get(parts[1], parts[1]) if len(parts) > 1 and re.fullmatch(r"\d[AB]?", parts[1]) else ""


def level_of(ref: str) -> str:
    found = re.search(r"\.(HL|SL)\.", ref or "")
    return found.group(1) if found else ""


def header(number: int, ref: str, marks, pct_correct=None) -> dict:
    """What a question's header shows. Nothing here names the topic or the trick, so it gives nothing away."""
    paper = paper_of(ref)
    tags = [t for t in ("Past paper", level_of(ref), f"Paper {paper}" if paper else "", f"{marks} mark" + ("" if marks == 1 else "s")) if t]
    return {"number": number, "tags": tags, "difficulty": difficulty(pct_correct)}
