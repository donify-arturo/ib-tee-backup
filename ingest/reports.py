"""
IB subject (examiner) reports → per-question examiner comments + paper-level findings.

The combined PDF concatenates ~60 reports (2001–2025) in three header styles:
    "May 2025 subject report            Chemistry TZ1"
    "SUBJECT REPORTS – MAY 2002" / "SUBJECT REPORTS – NOV 2005"
    cover pages with "Timezone 2" / "Time zone 1"
Inside a report, sections open with "Higher level paper one", "Standard Level Paper 1 Timezone 1",
"Higher level paper one Section A" (2025 Paper 1A) … and question comments with "Question 7"
(old option papers: "Question F3").

Emitted source types
    examiner_report    one per question (or per part, when long): what candidates did, % correct,
                       the correct MCQ letter and the most popular wrong answer when stated
    examiner_finding   one per bullet in "areas … difficult" / "well prepared" lists (macro signal)
    examiner_overview  paper-level general comments and recommendations
"""
from __future__ import annotations

import re

from . import refs
from .chunking import Chunk, make_id, new_meta, split_long
from .parsers import Page

SESSION_RES = [
    re.compile(r"\b(May|November) (\d{4}) [Ss]ubject [Rr]eport"),
    re.compile(r"SUBJECT REPORTS?\s*[–-]\s*(MAY|NOVEMBER|NOV)\.?\s+(\d{4})", re.I),
]
TZ_LINE_RE = re.compile(r"^\s*(?:Chemistry\s+)?(?:Time ?zone|TZ)\s*([0-9])\s*$", re.I)
# running headers / covers: "May 2025 subject report   Chemistry TZ1", "Group 4 Chemistry TZ2", "Chemistry TZ1 (IBA)"
TZ_HEADER_RE = re.compile(r"\bChemistry\s+(?:TZ|Time ?zone)\s?([0-9])\b", re.I)
PAPER_RE = re.compile(
    r"^\s*(?P<lvl>Higher|Standard)\s+[Ll]evel\s+[Pp]aper\s+(?P<num>one|two|three|1|2|3)\b"
    r"(?:\s+Section\s+(?P<sec>[AB]))?"
    r"(?:[\s,–-]*(?:Time ?zone|TZ)\s*(?P<tz>[0-9]))?\s*$", re.I)
QUESTION_RE = re.compile(r"^\s*Question\s+(?P<opt>[A-H])?(?P<q>\d{1,2})\b\s*(?P<rest>.*)$")
OVERVIEW_RE = re.compile(
    r"^\s*(?P<h>The areas of the programme and examination (?:which|that|in which)"   # heading often wraps
    r"|The strengths and weaknesses of the (?:candidates|students)"
    r"|Recommendations and guidance|Recommendations for the teaching|Further comments|General comments"
    r"|The type of assistance and guidance)", re.I)
END_SECTION_RE = re.compile(r"^\s*(Grade boundaries|Overall grade boundaries|Internal assessment|"
                            r"Higher level and Standard level internal assessment)\b", re.I)
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦\-–*]|)\s+(.*)$")
NUM = {"one": "1", "two": "2", "three": "3"}

PCT_CORRECT_RES = [
    re.compile(r"(\d{1,3}(?:\.\d+)?)\s?%\s*(?:of\s+(?:the\s+)?(?:candidates|students|responses))?[^.%]{0,50}?"
               r"\b(?:correct|right|success|answered correctly|identified|able to)", re.I),
    re.compile(r"\b(?:correct(?:ly)?|success rate|answered correctly)[^.%]{0,40}?(\d{1,3}(?:\.\d+)?)\s?%", re.I),
]
ANSWER_RE = re.compile(r"\bcorrect (?:response|answer|option)\s*(?:,|was|is|:|\()?\s*\(?([A-D])\b")
DISTRACTOR_RE = re.compile(r"\b(?:most )?(?:popular|common|chosen)\s+(?:wrong |incorrect )?"
                           r"(?:answer|response|distractor|option|choice)[^.]{0,25}?\b([A-D])\b", re.I)


def _session(page_text: str) -> str | None:
    for rx in SESSION_RES:
        m = rx.search(page_text)
        if m:
            mon = "M" if m.group(1).lower().startswith("may") else "N"
            return f"{m.group(2)[-2:]}{mon}"
    return None


def _is_cover(page_text: str) -> bool:
    head = page_text[:2500]
    return bool(re.search(r"^\s*Contents\s*$", head, re.M) or
                re.search(r"^\s*(?:CHEMISTRY\s*)?Overall grade boundaries", head, re.M | re.I) or
                re.search(r"^\s*Timezone [0-9]\s*$", head[:400], re.M))


def _stats(text: str) -> dict:
    out: dict = {}
    for rx in PCT_CORRECT_RES:
        m = rx.search(text)
        if m:
            v = float(m.group(1))
            if 0 <= v <= 100:
                out["pct_correct"] = v
                break
    m = ANSWER_RE.search(text)
    if m:
        out["report_answer"] = m.group(1)
    m = DISTRACTOR_RE.search(text)
    if m and m.group(1) != out.get("report_answer"):
        out["popular_distractor"] = m.group(1)
    return out


def split_subject_reports(spec, pages: list[Page]) -> list[Chunk]:
    out: list[Chunk] = []
    st = {"session": None, "tz": None, "level": None, "paper": None, "report": 0}
    block = None          # current unit: dict(kind, lines, p0, p1, q, opt, overview_kind)

    def ref_for(q: int | str) -> refs.QRef | None:
        if not (st["session"] and st["level"] and st["paper"]):
            return None
        tz = st["tz"]
        variant = f"TZ{tz}" if tz not in (None, "0") else "TZ0"
        return refs.QRef(st["session"], st["paper"], st["level"], variant, q if isinstance(q, int) else 0)

    def common_meta(p0, p1):
        sess = st["session"]
        label = f"{'May' if sess.endswith('M') else 'November'} 20{sess[:2]}" if sess else None
        era = "2025" if (st["paper"] in {"1A", "1B"} or (sess and int(sess[:2]) >= 25 and int(sess[:2]) < 90)) else "legacy"
        return dict(origin=spec.origin, doc_id=spec.doc_id, page_start=p0, page_end=p1, session=label,
                    paper=st["paper"], level=st["level"],
                    variant=(f"TZ{st['tz']}" if st["tz"] not in (None, "0") else "TZ0"),
                    syllabus_era=era, report_no=st["report"])

    def flush():
        nonlocal block
        if not block:
            return
        text = "\n".join(block["lines"]).strip()
        b, block = block, None
        if len(text) < (25 if b["kind"] == "question" else 5):     # a one-bullet list can be very short
            return
        meta = common_meta(b["p0"], b["p1"])
        if b["kind"] == "question":
            q = ref_for(b["q"])
            option = b["opt"]
            key = (f"{q.session}.{q.paper}.{q.level}.{q.variant}.{option or ''}{b['q']}" if q else None)
            stats = _stats(text)
            parts = split_long(text, max_chars=3000)
            for i, piece in enumerate(parts):
                out.append(Chunk(
                    id=make_id(spec.doc_id, st["report"], key, b["p0"], i),
                    text=f"[EXAMINER REPORT {key}] {meta['session']} Paper {st['paper']} {st['level']} "
                         f"Q{option or ''}{b['q']}\n{piece}",
                    metadata=new_meta(
                        source_type="examiner_report", question_ref=key if not option else None,
                        report_question_key=key, option_question=bool(option),
                        question_part=f"part{i + 1}" if len(parts) > 1 else None,
                        legacy_paper3=(st["paper"] == "3"), **meta, **stats,
                    ),
                ))
        else:
            kind = b["overview_kind"]
            if kind in {"difficult", "well_prepared"}:
                for j, item in enumerate(_bullets(text)):
                    out.append(Chunk(
                        id=make_id(spec.doc_id, st["report"], st["paper"], st["level"], kind, b["p0"], j),
                        text=f"[EXAMINER FINDING · {kind}] {meta['session']} Paper {st['paper']} {st['level']}: {item}",
                        metadata=new_meta(source_type="examiner_finding", polarity=kind, **meta),
                    ))
            else:
                for i, piece in enumerate(split_long(text)):
                    out.append(Chunk(
                        id=make_id(spec.doc_id, st["report"], st["paper"], st["level"], kind, b["p0"], i),
                        text=f"[EXAMINER OVERVIEW · {kind}] {meta['session']} Paper {st['paper']} {st['level']}\n{piece}",
                        metadata=new_meta(source_type="examiner_overview", overview_kind=kind, **meta),
                    ))

    last_cover = -99
    for pg in pages:
        txt = pg.markdown
        sess = _session(txt)
        cover = _is_cover(txt)
        new_session = bool(sess and sess != st["session"])
        if new_session or cover:
            flush()
            # a cover + contents page pair (or a cover whose session line is on the next page) is ONE report:
            # keep the time zone found on the cover instead of resetting it
            same_report = pg.page - last_cover <= 2 and (st["session"] in (None, sess))
            if not same_report:
                st.update(tz=None, report=st["report"] + 1)
            st.update(session=sess or st["session"], level=None, paper=None)
            if cover:
                last_cover = pg.page
        m = TZ_HEADER_RE.search(txt[:800])
        if m:
            st["tz"] = m.group(1)
        for ln in txt.splitlines():
            s = ln.strip()
            if not s or re.match(r"^(Page \d+ / \d+|© International Baccalaureate|International Baccalaureate)", s) \
                    or re.search(r"(subject report|SUBJECT REPORTS?\s*[–-])", s, re.I) and len(s) < 120:
                continue
            m = TZ_LINE_RE.match(s)
            if m and len(s) < 40:
                st["tz"] = m.group(1)
                continue
            m = PAPER_RE.match(s)
            if m:
                flush()
                num = NUM.get(m.group("num").lower(), m.group("num"))
                if m.group("sec") and num == "1":
                    num += m.group("sec").upper()                   # 2025: Paper 1A / 1B
                st.update(level="HL" if m.group("lvl").lower() == "higher" else "SL", paper=num)
                if m.group("tz"):
                    st["tz"] = m.group("tz")
                continue
            m = re.match(r"^Section\s+([AB])\s*$", s)
            if m and st["paper"] in {"1", "1A", "1B"} and st["session"] and st["session"][:2] >= "25":
                flush()
                st["paper"] = "1" + m.group(1)                     # 2025 reports: "Section A" on its own line
                continue
            if END_SECTION_RE.match(s):
                flush()
                st.update(paper=None)
                continue
            if st["paper"] is None:
                continue                                            # IA, grade boundaries, contents
            m = OVERVIEW_RE.match(s)
            if m:
                flush()
                h = m.group("h").lower()
                kind = ("well_prepared" if h.endswith("in which") else "difficult" if "areas of the programme" in h
                        else "strengths_weaknesses" if "strengths" in h
                        else "recommendations" if ("recommend" in h or "assistance" in h) else "general")
                block = {"kind": "overview", "overview_kind": kind, "lines": [], "p0": pg.page, "p1": pg.page}
                continue
            m = QUESTION_RE.match(s)
            if m and len(s) < 160:
                flush()
                block = {"kind": "question", "q": int(m.group("q")), "opt": m.group("opt"),
                         "lines": [m.group("rest")] if m.group("rest") else [], "p0": pg.page, "p1": pg.page}
                continue
            if block is not None:
                block["lines"].append(s)
                block["p1"] = pg.page
    flush()
    return out


def _bullets(text: str) -> list[str]:
    items: list[str] = []
    for ln in text.splitlines():
        m = BULLET_RE.match(ln)
        if m:
            items.append(m.group(1).strip())
        elif items and ln.strip() and (ln[:1].islower() or not items[-1].rstrip().endswith((".", ";"))):
            items[-1] += " " + ln.strip()
        elif ln.strip() and not items:
            # some reports write the list as plain sentences / comma lists
            items.extend(x.strip() for x in re.split(r";\s*|\.\s+(?=[A-Z])", ln) if len(x.strip()) > 3)
    cleaned = []
    for it in items:
        it = re.sub(r"\s+", " ", it).strip(" ,;")
        # page furniture and the next heading sometimes run into the last bullet of a list
        it = re.split(r"\s*(?:The areas of the programme|The strengths and weaknesses|Group 4 Chemistry|©|"
                      r"Page \d+ /|International Baccalaureate)", it)[0].strip(" ,;")
        it = re.sub(r"^(?:students|candidates)\s+(?:were challenged by questions focusing on|demonstrated a good "
                    r"understanding (?:in|of))\s*:?", "", it, flags=re.I).strip(" ,;:")
        if len(re.findall(r"[A-Za-z]{3,}", it)) < 2:
            continue
        if 3 <= len(it) <= 400 and not it.lower().startswith(("candidates demonstrated", "candidates were challenged")):
            cleaned.append(it)
    return cleaned
