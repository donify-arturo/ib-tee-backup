"""
Syllabus taxonomy helpers + the sub-topic header regex (Part 1 requirement).

Canonical codes
---------------
  theme         S1 | S2 | S3 | R1 | R2 | R3
  sub_topic     S1.1 ... R3.4        (22 in total)
  understanding S1.1.1 ... R3.4.13   (165 in total)

Why not plain "1.1"?  In the 2025 syllabus "1.1" is ambiguous: Structure 1.1
(particulate nature of matter) and Reactivity 1.1 (measuring enthalpy changes)
are different sub-topics. Every regex below therefore captures the family word
("Structure" / "Reactivity") or its one-letter abbreviation (S / R).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SYLLABUS_JSON = Path(__file__).resolve().parents[1] / "data" / "syllabus" / "syllabus.json"

FAMILY_PREFIX = {"structure": "S", "reactivity": "R", "s": "S", "r": "R"}

# --------------------------------------------------------------------------- #
# Header regex. Matches only at the START of a line, optionally after markdown
# heading hashes, list bullets or the RUNNING_HEADER: tag that the LlamaParse
# prompt asks for.  Examples it matches:
#   "## Reactivity 1.2 Energy cycles in reactions"
#   "RUNNING_HEADER: Reactivity 1.2 Energy cycles in reactions"
#   "Structure 1.1—Introduction to the particulate nature of matter"
#   "Reactivity 1.1 – Measuring enthalpy changes"
#   "Structure 2.2.4—A coordination bond is ..."          (understanding level)
#   "### R2.3 How far?"                                     (abbreviated)
# --------------------------------------------------------------------------- #
SUBTOPIC_HEADER_RE = re.compile(
    r"""^\s*
        (?:\#{1,6}\s*)?                       # markdown heading
        (?:[-*•]\s+)?                          # bullet
        (?:\*\*)?                              # bold
        (?:RUNNING_HEADER:\s*)?
        (?:
            (?P<family>Structure|Reactivity)\s+
          | (?P<abbr>[SR])(?=[123]\.)
        )
        (?P<theme>[123])\.(?P<sub>[1-5])
        (?:\.(?P<und>\d{1,2}))?
        (?![\d.])                              # not 1.23 / 1.2.3.4
        \s*(?:\*\*)?\s*
        (?P<sep>[—–:\-]|\s)?\s*
        (?P<title>.*?)\s*$
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

# Inline mention anywhere in text (used for cross-link metadata, never for state)
SUBTOPIC_MENTION_RE = re.compile(
    r"\b(?P<family>Structure|Reactivity)\s+(?P<theme>[123])\.(?P<sub>[1-5])(?:\.(?P<und>\d{1,2}))?\b"
)

DATA_BOOKLET_SECTION_RE = re.compile(
    r"(?:section|table)\s+(?P<num>\d{1,2})\s+of\s+the\s+(?:chemistry\s+)?data\s+booklet"
    r"|data\s+booklet[,\s]+(?:section|table)\s+(?P<num2>\d{1,2})",
    re.IGNORECASE,
)


THEME_HEADER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:RUNNING_HEADER:\s*)?(?P<family>Structure|Reactivity)\s+(?P<theme>[123])(?![\d.])\s+[A-Z]")


def match_theme(line: str) -> str | None:
    m = THEME_HEADER_RE.match(line)
    return f"{FAMILY_PREFIX[m.group('family').lower()]}{m.group('theme')}" if m else None


@dataclass(frozen=True)
class HeaderHit:
    sub_topic: str
    understanding: str | None
    title: str
    is_cross_link: bool      # "Structure 2.2—How do intermolecular forces …?" style linking question


@lru_cache(maxsize=1)
def load_syllabus(path: str | Path = SYLLABUS_JSON) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Build it first: python -m taxonomy.build_syllabus <Chemistry_Guide_2025.pdf>"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def valid_sub_topics() -> set[str]:
    return {s["code"] for s in load_syllabus()["sub_topics"]}


def valid_understandings() -> set[str]:
    return set(load_syllabus()["understandings"])


def sub_topic_title(code: str) -> str:
    for s in load_syllabus()["sub_topics"]:
        if s["code"] == code:
            return s["title"]
    return ""


def theme_of(code: str | None) -> str | None:
    return code.split(".")[0] if code else None


def _code(m: re.Match) -> tuple[str, str | None]:
    fam = m.group("family") or m.group("abbr")
    prefix = FAMILY_PREFIX[fam.lower()]
    sub = f"{prefix}{m.group('theme')}.{m.group('sub')}"
    und = f"{sub}.{m.group('und')}" if m.group("und") else None
    return sub, und


def match_header(line: str) -> HeaderHit | None:
    """Return a HeaderHit if `line` is a syllabus sub-topic header.

    Rejects codes that don't exist in the syllabus (e.g. "Structure 3.4") and
    marks linking questions (title ends with "?") as cross-links so callers
    don't switch the current sub-topic because of them.
    """
    if len(line) > 220:            # headers are short; long lines are prose
        return None
    m = SUBTOPIC_HEADER_RE.match(line)
    if not m:
        return None
    sub, und = _code(m)
    if sub not in valid_sub_topics():
        return None
    if und and und not in valid_understandings():
        und = None
    title = (m.group("title") or "").strip(" *#")
    # Abbreviated form with no title is too weak a signal ("S1.1" could be a
    # figure label) unless it's a markdown heading.
    if m.group("abbr") and not title and not line.lstrip().startswith("#"):
        return None
    # A bare family word followed by numbers inside a sentence ("Reactivity 1.2 is …")
    # is rejected when the "title" reads like prose (starts lowercase).
    if title and title[0].islower() and not m.group("sep"):
        return None
    # Margin cross-reference tags ("Structure 2.1" alone, or "Structure 3.2 25") have no real
    # title: treat them as cross-links unless the line is an explicit heading/running header.
    explicit = bool(re.match(r"^\s*(#|RUNNING_HEADER:)", line))
    weak_title = len(re.findall(r"[A-Za-z]{2,}", title)) < 2
    return HeaderHit(sub, und, title, is_cross_link=title.endswith("?") or (weak_title and not explicit))


def mentions(text: str) -> list[str]:
    """All sub-topic codes mentioned anywhere in text (deduplicated, ordered)."""
    seen: dict[str, None] = {}
    valid = valid_sub_topics()
    for m in SUBTOPIC_MENTION_RE.finditer(text):
        sub, _ = _code(m)
        if sub in valid:
            seen.setdefault(sub)
    return list(seen)


def data_booklet_sections(text: str) -> list[int]:
    out = []
    for m in DATA_BOOKLET_SECTION_RE.finditer(text):
        n = int(m.group("num") or m.group("num2"))
        if 1 <= n <= 24 and n not in out:
            out.append(n)
    return out


def normalise_code(raw: str) -> str | None:
    """'Reactivity 1.2' | 'R1.2' | 'r1.2.3' -> 'R1.2' (sub-topic level). Bare '1.2' -> None."""
    m = re.match(r"^\s*(Structure|Reactivity|[SR])\s*([123])\.([1-5])", raw, re.IGNORECASE)
    if not m:
        return None
    code = f"{FAMILY_PREFIX[m.group(1).lower()]}{m.group(2)}.{m.group(3)}"
    return code if code in valid_sub_topics() else None
