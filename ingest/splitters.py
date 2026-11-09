"""
Source-specific splitters: parsed pages → Chunk records with metadata.

Each splitter strips the "question wrapper" noise for its source (browser chrome,
cover pages, licensing boilerplate, answer boxes) and emits units that make
sense for the Technique Engine: one question, one markscheme, one textbook
section, one data-booklet table.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import refs, taxonomy
from .chunking import MAX_CHARS, Chunk, make_id, new_meta, split_long
from .data_booklet_map import DATA_BOOKLET_SECTIONS
from .parsers import Page, strip_browser_chrome
from .scan_books import split_scan_book


@dataclass
class SourceSpec:
    doc_id: str
    path: str
    source_type: str
    origin: str = ""
    profile: str = ""
    scope: list[str] = field(default_factory=list)
    parser: str | None = None
    cover_overrides: list[dict] = field(default_factory=list)   # [{page, session, level, paper, code, markscheme}]
    scan: dict = field(default_factory=dict)                    # scan_book settings from sources.toml


# --------------------------------------------------------------------------- #
# Syllabus guide → one chunk per understanding (from syllabus.json)
# --------------------------------------------------------------------------- #
def split_syllabus(spec: SourceSpec, _pages=None) -> list[Chunk]:
    syl = taxonomy.load_syllabus()
    titles = {s["code"]: s for s in syl["sub_topics"]}
    out = []
    for code, u in syl["understandings"].items():
        sub = titles[u["sub_topic"]]
        parts = [f"{u['sub_topic']} {sub['title']} — {code} ({u['level']})",
                 f"Understanding: {u['statement']}"]
        if u["skills"]:
            parts.append("Skills: " + " ".join(u["skills"]))
        if u["guidance"]:
            parts.append("Guidance: " + " ".join(u["guidance"]))
        if u["linking_questions"]:
            parts.append("Linking questions: " + " | ".join(u["linking_questions"]))
        out.append(Chunk(
            id=make_id(spec.doc_id, code),
            text="\n".join(parts),
            metadata=new_meta(
                sub_topic=u["sub_topic"], understanding=code, source_type="syllabus",
                origin=spec.origin, doc_id=spec.doc_id, level=u["level"],
                cross_links=taxonomy.mentions(" ".join(u["linking_questions"])),
                tag_method="syllabus", tag_confidence=1.0,
            ),
        ))
    return out


# --------------------------------------------------------------------------- #
# Textbook: running-header + in-text header state machine
# --------------------------------------------------------------------------- #
PRINTED_PAGE_RE = re.compile(r"^\s*(?:PRINTED_PAGE:\s*)?(\d{1,4})\s*$")


def _printed_page(pg: Page) -> str | None:
    if pg.printed_page:
        return str(pg.printed_page)
    lines = [l for l in pg.markdown.strip().splitlines() if l.strip()]
    for ln in reversed(lines[-3:]):
        m = PRINTED_PAGE_RE.match(ln)
        if m:
            return m.group(1)
    return None


def split_textbook(spec: SourceSpec, pages: list[Page]) -> list[Chunk]:
    """Walk pages in order; the sub-topic switches only on a non-cross-link header.

    Sections accumulate per sub-topic and are cut into ≤MAX_CHARS chunks on
    headings/paragraphs, so a chunk never spans two sub-topics.
    """
    out: list[Chunk] = []
    cur_sub: str | None = None
    cur_und: str | None = None
    cur_theme: str | None = None
    buf: list[tuple[int, str | None, str]] = []      # (page, printed, line)

    def flush():
        nonlocal buf
        if not buf:
            return
        if len("\n".join(l for _, _, l in buf).strip()) < 40:
            buf = []
            return
        # Pack whole pages into chunks so each chunk knows exactly which (printed) pages it covers —
        # needed to link textbook questions to the answer key by page number.
        blocks: list[tuple[int, str | None, str]] = []
        for page_no, printed_no, line in buf:
            if blocks and blocks[-1][0] == page_no:
                blocks[-1] = (page_no, printed_no, blocks[-1][2] + "\n" + line)
            else:
                blocks.append((page_no, printed_no, line))
        pieces: list[tuple[list[int], list[str], str]] = []
        for page_no, printed_no, text in blocks:
            parts = split_long(text) if len(text) > MAX_CHARS else [text]
            for part in parts:
                if pieces and len(pieces[-1][2]) + len(part) < MAX_CHARS and len(parts) == 1:
                    pg_list, pr_list, t = pieces[-1]
                    pieces[-1] = (pg_list + [page_no], pr_list + ([printed_no] if printed_no else []), t + "\n" + part)
                else:
                    pieces.append(([page_no], [printed_no] if printed_no else [], part))
        for i, (pages_, printed, piece) in enumerate(pieces):
            piece = piece.strip()
            if len(piece) < 40:
                continue
            printed = sorted(set(printed), key=int)
            out.append(Chunk(
                id=make_id(spec.doc_id, pages_[0], cur_sub, i, piece[:60]),
                text=piece,
                metadata=new_meta(
                    sub_topic=cur_sub, understanding=cur_und, theme=cur_theme, source_type="textbook",
                    scope=[cur_theme] if cur_theme and not cur_sub else [],
                    origin=spec.origin, doc_id=spec.doc_id,
                    page_start=min(pages_), page_end=max(pages_),
                    printed_page=printed[0] if printed else None,
                    printed_pages=printed,
                    cross_links=[c for c in taxonomy.mentions(piece) if c != cur_sub],
                    data_booklet_sections=taxonomy.data_booklet_sections(piece),
                    tag_method="running_header" if cur_sub else None,
                    tag_confidence=0.98 if cur_sub else None,
                ),
            ))
        buf = []

    for pg in pages:
        printed = _printed_page(pg)
        lines = pg.markdown.splitlines()
        for idx, ln in enumerate(lines):
            if PRINTED_PAGE_RE.match(ln) and idx >= len(lines) - 3:
                continue                                   # footer page number
            theme = taxonomy.match_theme(ln)
            if theme and theme != cur_theme and (cur_sub is None or not cur_sub.startswith(theme)):
                flush()
                cur_theme, cur_sub, cur_und = theme, None, None   # new theme opener page
            hit = taxonomy.match_header(ln)
            if hit and not hit.is_cross_link:
                cur_theme = hit.sub_topic.split(".")[0]
                if hit.sub_topic != cur_sub:
                    flush()
                    cur_sub, cur_und = hit.sub_topic, hit.understanding
                elif hit.understanding and hit.understanding != cur_und:
                    flush()
                    cur_und = hit.understanding
                if ln.strip().startswith("RUNNING_HEADER") or idx < 2:
                    continue                               # don't repeat the running header in text
            buf.append((pg.page, printed, ln.replace("RUNNING_HEADER: ", "")))
    flush()
    return out


# --------------------------------------------------------------------------- #
# Textbook answers: "Reactivity 1.1 – …" headers, "(page 394)" sections
# --------------------------------------------------------------------------- #
PAGE_REF_RE = re.compile(r"\(pages?\s+(\d{1,4})(?:\s*[–-]\s*(\d{1,4}))?\)")


def split_answers(spec: SourceSpec, pages: list[Page]) -> list[Chunk]:
    out = []
    cur_sub = None
    section, sec_pages, sec_lines, sec_pdf_pages = None, [], [], []

    def flush():
        nonlocal sec_lines, section, sec_pages, sec_pdf_pages
        text = "\n".join(sec_lines).strip()
        if text and section:
            out.append(Chunk(
                id=make_id(spec.doc_id, cur_sub, section),
                text=f"{section}\n{text}",
                metadata=new_meta(
                    sub_topic=cur_sub, source_type="textbook_answers", origin=spec.origin,
                    doc_id=spec.doc_id, page_start=min(sec_pdf_pages), page_end=max(sec_pdf_pages),
                    answers_for_printed_pages=[str(p) for p in sec_pages],
                    tag_method="regex_header" if cur_sub else None,
                    tag_confidence=0.99 if cur_sub else None,
                ),
            ))
        sec_lines, sec_pdf_pages = [], []

    for pg in pages:
        for ln in pg.markdown.splitlines():
            s = ln.strip().lstrip("#").strip()
            if not s or s.startswith("©") or re.fullmatch(r"\d+", s) or s.startswith("Oxford Resources"):
                continue
            hit = taxonomy.match_header(s)
            if hit and not hit.is_cross_link:
                flush(); section = None
                cur_sub = hit.sub_topic
                continue
            m = PAGE_REF_RE.search(s)
            if m and len(s) < 80:
                flush()
                a, b = int(m.group(1)), int(m.group(2) or m.group(1))
                section, sec_pages = s, list(range(a, b + 1))
                continue
            sec_lines.append(ln)
            sec_pdf_pages.append(pg.page)
    flush()
    return out


# --------------------------------------------------------------------------- #
# Data booklet: numbered sections 1–24, sequential
# --------------------------------------------------------------------------- #
DB_SECTION_RE = re.compile(r"^\s*(?:#{1,3}\s*)?(\d{1,2})\.\s+(\S.{3,}?)\s*$")


def split_data_booklet(spec: SourceSpec, pages: list[Page]) -> list[Chunk]:
    out = []
    last = 0
    cur_num, cur_lines, cur_pages = None, [], []

    def is_section_header(n: int, title: str) -> bool:
        # Increasing numbers only (the "Updates" page re-lists old headings), and the title must
        # start like the known section title (letters only, so "1H NMR" ≈ "H NMR").
        def norm(t):
            return re.sub(r"[^a-z]", "", t.lower())[:6]
        known = DATA_BOOKLET_SECTIONS.get(n, {}).get("title", "")
        return n > last and norm(known) == norm(title)

    def flush():
        if cur_num is None:
            return
        info = DATA_BOOKLET_SECTIONS.get(cur_num, {"title": "", "sub_topics": []})
        text = "\n".join(cur_lines).strip()
        subs = info["sub_topics"]
        for i, piece in enumerate(split_long(text, max_chars=6000)):   # keep tables whole
            out.append(Chunk(
                id=make_id(spec.doc_id, cur_num, i),
                text=f"Data booklet section {cur_num}. {info['title']}\n{piece}",
                metadata=new_meta(
                    sub_topic=subs[0] if subs else None, sub_topics_all=list(subs),
                    source_type="data_booklet", origin=spec.origin, doc_id=spec.doc_id,
                    page_start=min(cur_pages), page_end=max(cur_pages),
                    data_booklet_sections=[cur_num],
                    tag_method="data_booklet_map", tag_confidence=1.0 if subs else None,
                ),
            ))

    for pg in pages:
        head = pg.markdown[:400]
        if "Contents" in head or pg.markdown.strip().startswith("Introduction"):
            continue
        for ln in pg.markdown.splitlines():
            if re.search(r"(\. ){3,}|\.{4,}", ln):          # table-of-contents dot leaders
                continue
            if re.fullmatch(r"\s*(Chemistry data booklet\s*\d*|\d+\s*Chemistry data booklet)\s*", ln):
                continue
            m = DB_SECTION_RE.match(ln)
            if m and is_section_header(int(m.group(1)), m.group(2)):
                flush()
                cur_num, cur_lines, cur_pages = int(m.group(1)), [], []
                last = cur_num
                continue
            if cur_num is not None:
                if ln.strip().startswith("Updates to the publication"):
                    break
                cur_lines.append(ln)
                cur_pages.append(pg.page)
    flush()
    return out


# --------------------------------------------------------------------------- #
# RevisionHub question bank
# --------------------------------------------------------------------------- #
QTYPE_RE = re.compile(r"\b(Multiple choice|Short answer|Structured|Long answer|Extended response)\b", re.I)
DIFF_RE = re.compile(r"\b(Easy|Medium|Hard)\b")


def split_question_bank(spec: SourceSpec, pages: list[Page]) -> list[Chunk]:
    out = []
    cur = None

    def flush():
        if not cur:
            return
        body = "\n".join(cur["lines"]).strip()
        q: refs.QRef = cur["ref"]
        parts = split_long(body, max_chars=5000)
        for i, piece in enumerate(parts):
            out.append(Chunk(
                id=make_id(spec.doc_id, q.key, i),
                text=f"[{q.key}] {q.session_label} Paper {q.paper} {q.level} Q{q.question}\n{piece}",
                metadata=new_meta(
                    source_type="past_paper", origin=spec.origin, doc_id=spec.doc_id,
                    page_start=cur["p0"], page_end=cur["p1"], question_ref=q.key,
                    question_part=f"part{i + 1}" if len(parts) > 1 else None,
                    session=q.session_label, paper=q.paper, variant=q.variant, level=q.level,
                    syllabus_era=q.syllabus_era,
                    question_type=cur["qtype"] or ("mcq" if q.paper in {"1", "1A"} else "structured"),
                    difficulty=cur["diff"],
                    data_booklet_sections=taxonomy.data_booklet_sections(piece),
                    scope=spec.scope,
                ),
            ))

    for pg in pages:
        md = strip_browser_chrome(pg.markdown)
        for ln in md.splitlines():
            hit = refs.from_qb_header(ln)
            if hit:
                flush()
                q, _m = hit
                cur = {"ref": q, "lines": [], "p0": pg.page, "p1": pg.page, "qtype": None, "diff": None,
                       "meta_pending": True}
                continue
            if cur is None:
                continue                                    # filter panel before the first question
            if cur["meta_pending"] and (QTYPE_RE.search(ln) or DIFF_RE.search(ln)) and len(ln) < 80:
                t = QTYPE_RE.search(ln)
                d = DIFF_RE.search(ln)
                cur["qtype"] = "mcq" if t and t.group(1).lower() == "multiple choice" else ("structured" if t else None)
                cur["diff"] = d.group(1) if d else None
                cur["meta_pending"] = False
                continue
            cur["meta_pending"] = False
            if ln.strip() in {"Submit", "Ans"}:
                continue
            cur["lines"].append(ln)
            cur["p1"] = pg.page
    flush()
    return out


# --------------------------------------------------------------------------- #
# Question-bank markschemes: blocks keyed by "17M.2.HL.TZ2.7"
# --------------------------------------------------------------------------- #
def split_qb_markschemes(spec: SourceSpec, pages: list[Page]) -> list[Chunk]:
    out = []
    cur = None

    def flush():
        if not cur:
            return
        body = "\n".join(cur["lines"]).strip()
        q: refs.QRef = cur["ref"]
        parts = split_long(body, max_chars=4000)
        for i, piece in enumerate(parts):
            out.append(Chunk(
                id=make_id(spec.doc_id, q.key, cur["occurrence"], i),
                text=f"[MARKSCHEME {q.key}] {q.session_label} Paper {q.paper} {q.level} Q{q.question}\n{piece}",
                metadata=new_meta(
                    source_type="markscheme", origin=spec.origin, doc_id=spec.doc_id,
                    page_start=cur["p0"], page_end=cur["p1"], question_ref=q.key,
                    question_part=f"part{i + 1}" if len(parts) > 1 else None,
                    session=q.session_label, paper=q.paper, variant=q.variant, level=q.level,
                    syllabus_era=q.syllabus_era, markscheme_origin="question_bank",
                    scope=spec.scope,
                ),
            ))

    seen: dict[str, int] = {}
    for pg in pages:
        md = strip_browser_chrome(pg.markdown)
        for ln in md.splitlines():
            if ln.strip() in {"Markschemes", "QuestionBank Test"}:
                continue
            q = refs.from_ms_ref(ln.strip())
            if q:
                flush()
                seen[q.key] = seen.get(q.key, 0) + 1
                cur = {"ref": q, "lines": [], "p0": pg.page, "p1": pg.page, "occurrence": seen[q.key]}
                continue
            if cur:
                cur["lines"].append(ln)
                cur["p1"] = pg.page
    flush()
    return out


# --------------------------------------------------------------------------- #
# Official IB combined PDF: covers → documents → questions / markscheme rows
# --------------------------------------------------------------------------- #
TOPQ_RE = re.compile(r"^\s*\|?\s*(?:Q)?(\d{1,2})\.(?:\s+\S|\s*\||\s*$)")
# OCR'd pages: up to 3 digits so misreads like "413." (= 13.) can be repaired
OCR_TOPQ_RE = re.compile(r"^\s*\|?\s*(\d{1,3})\.(?:\s+\S|\s*\||\s*$)")


def _ocr_fix_number(n: int, expected: int) -> int:
    """Repair common OCR misreads of a question number when it is out of sequence:
    a stray leading digit ("413." → 13, "49." → 19 when 19 is due) or a 1↔4 swap ("45." → 15)."""
    if n == expected:
        return n
    sn, se = str(n), str(expected)
    if len(sn) == len(se) + 1 and sn[1:] == se:
        return expected
    if len(sn) == len(se) and sn[-1] == se[-1] and n > expected + 3 and \
            all(a == b or {a, b} <= {"1", "4", "7"} for a, b in zip(sn, se)):
        return expected
    if len(sn) == 2 and len(se) == 2 and sn[0] == "4" and se[0] == "1" and sn[1] == se[1]:
        return expected
    return n


# markscheme rows sometimes drop the dot: "1   (a)    (i)"
MS_ROW_RE = re.compile(r"^\s*\|?\s*(\d{1,2})(?:\.|\s+(?=\([a-z]\)))")
MCQ_KEY_RE = re.compile(r"(?:^|\s)(?:Q)?(\d{1,2})[.:]\s+([A-D])(?=\s|$)")
BOILERPLATE_RE = re.compile(
    r"©\s*(International Baccalaureate|Organisation du Baccalauréat|Organización del Bachillerato)"
    r"|All rights reserved|Tous droits réservés|Todos los derechos|\[BOILERPLATE\]|Disclaimer: Content used in IB"
    r"|Please do not write on this page", re.I)


def _official_documents(pages: list[Page], overrides: list[dict] | None = None) -> list[dict]:
    forced = {o["page"]: {"paper_code": str(o["code"]), "is_markscheme": bool(o.get("markscheme", False)),
                          "session": o["session"], "level": o["level"], "paper": str(o["paper"]),
                          **({"variant": o["variant"]} if o.get("variant") else {})}
              for o in (overrides or [])}
    docs, cur = [], None
    for pg in pages:
        if pg.page in forced:                       # screenshot cover with no readable paper code
            cur = dict(forced[pg.page], pages=[])
            docs.append(cur)
            continue
        cover = refs.official_cover(pg.markdown)
        is_cover = cover and (pg.markdown.count("\n") < 40 or "Instructions to candidates" in pg.markdown
                              or "Markscheme" in pg.markdown[:300])
        if is_cover and (cur is None or cover["paper_code"] != cur["paper_code"] or
                         cover["is_markscheme"] != cur["is_markscheme"]):
            cur = dict(cover, pages=[])
            docs.append(cur)
            continue
        if cur is not None:
            cur["pages"].append(pg)
    return docs


def split_official(spec: SourceSpec, pages: list[Page]) -> list[Chunk]:
    out = []
    for doc in _official_documents(pages, spec.cover_overrides):
        sess, paper, level, code = doc["session"], doc["paper"], doc["level"], doc["paper_code"]
        # November papers have a single time zone → TZ0 so they join question-bank refs;
        # May 2025 variants are only identifiable by IB paper code.
        # Pre-2025 November sessions had one time zone (TZ0, which is how question banks label them);
        # from 2025 both sessions have several variants, identifiable only by IB paper code.
        single_tz = sess.endswith("N") and int(sess[:2]) < 25
        variant = doc.get("variant") or ("TZ0" if single_tz else code)
        ocr_pages = {p.page for p in doc["pages"] if p.parser.endswith("tesseract")}
        kind = "markscheme" if doc["is_markscheme"] else "past_paper"

        def qref(n: int) -> refs.QRef:
            return refs.QRef(sess, paper, level, variant, n)

        clean_pages = [p for p in doc["pages"] if not BOILERPLATE_RE.search(p.markdown[:300])]
        text_by_page = [(p.page, _strip_official_furniture(p.markdown)) for p in clean_pages]

        if kind == "markscheme" and paper in {"1", "1A"}:
            # MCQ key grid
            joined = "\n".join(t for _, t in text_by_page)
            keys = {int(n): a for n, a in MCQ_KEY_RE.findall(joined)}
            for n in sorted(keys):
                q = qref(n)
                out.append(Chunk(
                    id=make_id(spec.doc_id, q.key, "ms"),
                    text=f"[MARKSCHEME {q.key}] {q.session_label} Paper {paper} {level} Q{n}\nCorrect answer: {keys[n]}",
                    metadata=_official_meta(spec, q, "markscheme", text_by_page[0][0] if text_by_page else None,
                                            code, question_type="mcq", mcq_answer=keys[n]),
                ))
            continue

        # Structured markschemes and all question papers: sequential top-level numbers
        units: dict[int, dict] = {}
        current, expected = None, 1
        is_ocr = bool(ocr_pages)
        # Markschemes open with a numbered list of marking instructions (1.–17.); questions only
        # start after the first "Question | Answers | Notes | Total" table header.
        in_body = kind != "markscheme"
        for pno, text in text_by_page:
            for ln in text.splitlines():
                if not in_body:
                    in_body = bool(re.search(r"Question\W+Answers", ln))
                    continue
                m = (OCR_TOPQ_RE.match(ln) if is_ocr else TOPQ_RE.match(ln)) or \
                    (MS_ROW_RE.match(ln) if kind == "markscheme" else None)
                if m:
                    n = _ocr_fix_number(int(m.group(1)), expected) if is_ocr else int(m.group(1))
                    # OCR can lose a question number entirely: allow skipping ahead by up to 2 so one
                    # unreadable number costs one question, not the rest of the paper
                    if n == expected or (is_ocr and expected < n <= expected + 2):
                        current, expected = n, n + 1
                        units[n] = {"lines": [], "p0": pno, "p1": pno}
                    # n == current → another row of the same question: fall through
                if current is not None:
                    units[current]["lines"].append(ln)
                    units[current]["p1"] = pno
        for n, u in units.items():
            q = qref(n)
            body = "\n".join(u["lines"]).strip()
            parts = split_long(body, max_chars=4000)
            for i, piece in enumerate(parts):
                label = "MARKSCHEME " if kind == "markscheme" else ""
                out.append(Chunk(
                    id=make_id(spec.doc_id, q.key, kind, i),
                    text=f"[{label}{q.key}] {q.session_label} Paper {paper} {level} Q{n}\n{piece}",
                    metadata=_official_meta(
                        spec, q, kind, u["p0"], code, page_end=u["p1"],
                        ocr=bool(ocr_pages & set(range(u["p0"], u["p1"] + 1))),
                        question_part=f"part{i + 1}" if len(parts) > 1 else None,
                        question_type="mcq" if paper in {"1", "1A"} else "structured",
                        data_booklet_sections=taxonomy.data_booklet_sections(piece),
                    ),
                ))
    return out


def _official_meta(spec, q: refs.QRef, kind, page_start, code, page_end=None, **kw) -> dict:
    return new_meta(
        source_type=kind, origin=spec.origin, doc_id=spec.doc_id,
        page_start=page_start, page_end=page_end or page_start, question_ref=q.key,
        session=q.session_label, paper=q.paper, variant=q.variant, level=q.level,
        syllabus_era=q.syllabus_era, paper_code=code,
        markscheme_origin="ib_official" if kind == "markscheme" else None,
        scope=spec.scope, **kw,
    )


def _strip_official_furniture(md: str) -> str:
    keep = []
    for ln in md.splitlines():
        # OCR'd screenshots glue the page header onto the first line: "-8- 8825-6207 16. Which …"
        ln = re.sub(r"^\W*(?:[-–—~]?\s*\d{1,2}\s*[-–—~]\s*)?[38O]?\d{3}\s*[-–]\s*\d{4}M?\b\W*", "", ln)
        ln = re.sub(r"^[\s|\-—=~_.,'\"“”]+(?=\d{1,2}\.\s)", "", ln)   # stray OCR glyphs before "13."
        s = ln.strip()
        if s.startswith("References:"):
            break                                   # source acknowledgements at the end of a paper
        if re.fullmatch(r"[–-]\s*\d+\s*[–-]\s*(\d{4}\s*[–-]\s*\d{4}M?)?", s):     # "– 4 – 8824 – 9541M"
            continue
        if re.fullmatch(r"(Turn over|\d{2}EP\d{2}|\d+ pages|\(continued…?\)|\(Question \d+ continued\))", s):
            continue
        if re.fullmatch(r"\d{4}\s*[–-]\s*\d{4}M?", s):
            continue
        keep.append(ln)
    return "\n".join(keep)


from .reports import split_subject_reports  # noqa: E402

SPLITTERS = {
    "subject_report": split_subject_reports,
    "syllabus": split_syllabus,
    "textbook": split_textbook,
    "textbook_answers": split_answers,
    "data_booklet": split_data_booklet,
    "past_paper": split_question_bank,
    "markscheme": split_qb_markschemes,
    "official_papers": split_official,
    "scan_book": split_scan_book,
}
