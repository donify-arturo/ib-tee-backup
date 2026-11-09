"""
Canonical past-paper question references, so a question from one PDF can be
joined to its markscheme in another.

Canonical form:  {YY}{M|N}.{paper}.{HL|SL}.{variant}.{question}
    17M.2.HL.TZ2.7      May 2017, Paper 2, HL, time zone 2, Q7
    19N.1.SL.TZ0.12     November sessions have a single zone → TZ0
    25M.1B.HL.6221.3    2025 official PDFs: variant = IB paper code (no TZ printed)
    EXM.2.HL.TZ0.3      specimen paper

Sources:
    RevisionHub question header  "Question 3 from Paper 1 · HL · May 2024 · TZ1"
    Question-bank markscheme     "17M.2.HL.TZ2.7"
    Official cover page          "2225 – 6221M … Markscheme May 2025 … Higher level Paper 2"
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MONTH = {"may": "M", "november": "N", "nov": "N", "october": "N"}   # Nov-session papers can be dated late October

QB_HEADER_RE = re.compile(
    r"Question\s+(?P<q>\d{1,2})\s+from\s+Paper\s+(?P<paper>[123][ABab]?)\s*[·•|]\s*(?P<level>HL|SL)\s*[·•|]\s*"
    r"(?P<month>May|November|Nov)\s+(?P<year>(?:19|20)\d{2})(?:\s*[·•|]\s*(?P<tz>TZ\d))?",
    re.IGNORECASE,
)

MS_REF_RE = re.compile(
    r"^\s*(?:MS_REF:\s*)?(?P<sess>\d{2}[MN]|EXM|SPM)\.(?P<paper>[123][AB]?)\.(?P<level>HL|SL)\."
    r"(?P<tz>TZ\d)\.(?P<q>\d{1,2})\s*$",
    re.MULTILINE,
)

OLD_CODE_RE = re.compile(
    r"(?P<mon>[MN])(?P<yy>\d{2})/4/CHEMI/(?P<lvl>[HS])P(?P<kind>M|1|2|3)/ENG/TZ(?P<tz>\d)(?:/XX)?(?P<ms>/M)?")

OFFICIAL_CODE_RE = re.compile(r"(?:PAPER_CODE:\s*)?(?P<code>\d{4})\s*[–-]\s*(?P<num>\d{4})(?P<m>M?)\b")


@dataclass(frozen=True)
class QRef:
    session: str          # "17M", "24N", "EXM"
    paper: str            # "1", "2", "1A", "1B"
    level: str            # "HL" | "SL"
    variant: str          # "TZ0", "TZ1", "TZ2" or an IB paper code like "6221"
    question: int

    @property
    def key(self) -> str:
        return f"{self.session}.{self.paper}.{self.level}.{self.variant}.{self.question}"

    @property
    def year(self) -> int | None:
        return 2000 + int(self.session[:2]) if self.session[:2].isdigit() else None

    @property
    def session_label(self) -> str:
        if not self.year:
            return "Specimen"
        return f"{'May' if self.session.endswith('M') else 'November'} {self.year}"

    @property
    def syllabus_era(self) -> str:
        """'2025' for papers written to the current guide (first exams May 2025), else 'legacy'.
        November 2024 is still the old syllabus."""
        if self.paper.upper() in {"1A", "1B"}:
            return "2025"
        y = self.year
        return "2025" if y and y >= 2025 else "legacy"


def from_qb_header(text: str) -> tuple[QRef, re.Match] | None:
    m = QB_HEADER_RE.search(text)
    if not m:
        return None
    yy = m.group("year")[-2:]
    sess = f"{yy}{MONTH[m.group('month').lower()]}"
    tz = (m.group("tz") or "TZ0").upper()
    return QRef(sess, m.group("paper").upper(), m.group("level").upper(), tz, int(m.group("q"))), m


def from_ms_ref(line: str) -> QRef | None:
    m = MS_REF_RE.match(line)
    if not m:
        return None
    return QRef(m.group("sess"), m.group("paper").upper(), m.group("level"), m.group("tz"), int(m.group("q")))


def official_cover(text: str) -> dict | None:
    """Parse an official IB cover page → {'paper_code','is_markscheme','session','level','paper'}.

    Two layouts: current ("2225 – 6221M … Markscheme May 2025 … Higher level Paper 2") and the
    pre-2016 code line ("M09/4/CHEMI/SPM/ENG/TZ2/XX/M … May 2009 … Standard Level Paper 1")."""
    old = OLD_CODE_RE.search(text[:400])
    if old:
        pap = re.search(r"\bPaper\s+([123])\b", re.sub(r"\s+", " ", text[:800]), re.I)
        return {
            "paper_code": old.group(0).split("/XX")[0],
            "is_markscheme": bool(old.group("ms")) or old.group("kind") == "M",
            "session": f"{old.group('yy')}{old.group('mon')}",
            "level": "HL" if old.group("lvl") == "H" else "SL",
            "paper": pap.group(1) if pap else (old.group("kind") if old.group("kind") != "M" else "1"),
            "variant": f"TZ{old.group('tz')}",
        }
    head = re.sub(r"\s+", " ", text[:600])
    m = OFFICIAL_CODE_RE.search(head) or OFFICIAL_CODE_RE.search(re.sub(r"\s+", " ", text))
    sess = re.search(r"\b(May|November|October)\s+(20\d{2})\b", head)
    lvl = re.search(r"\b(Higher|Standard) level\b", head, re.I)
    pap = re.search(r"\bPaper\s+([123][ABab]?)\b(?:\s*[–-]\s*Section\s+([AB]))?", head)
    if not (m and sess and lvl and pap):
        return None
    paper = pap.group(1).upper()
    if pap.group(2) and paper == "1":
        paper += pap.group(2)                     # "Paper 1 – Section B" → 1B
    return {
        "paper_code": m.group("num"),
        "is_markscheme": bool(m.group("m")) or "Markscheme" in head,
        "session": f"{sess.group(2)[-2:]}{MONTH[sess.group(1).lower()]}",
        "level": "HL" if lvl.group(1).lower() == "higher" else "SL",
        "paper": paper,
    }
