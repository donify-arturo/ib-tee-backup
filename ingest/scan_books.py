"""
Scanned revision books → question and markscheme chunks, with automatic quality checks.

Book layout: a header such as "Chem 5/Q# 89//IB/Paper 1/2014/s/Time Zone 2/Higher Level/" opens a block; a block holds
one or more original exam questions keyed by their printed numbers. The markscheme section repeats each Q#, which
joins a question to its answers independently of OCR of the question number.

Every chunk gets scan_quality (green | amber | red) and scan_flags:

    red    key_conflict, ref_conflict                 never used
    amber  rapid_only, engines_disagree, bad_options, unbalanced_equation, arithmetic_mismatch,
           needs_figure, figure_undescribed, marks_mismatch, no_markscheme, header_inferred, lost_species,
           unknown_element, lost_operator             held back until reviewed
    green  nothing flagged                            feeds the decks (analysis.evidence reads only these)

Reviewed items go in data/scan_corrections.jsonl: {"doc_id", "book_q", "number", "kind", "text"?, "note"?}. A listed
item becomes green, with its text replaced if "text" is given.

Library policy: a text-layer copy already in the library wins. A book markscheme fills gaps only. A book question
replaces a library copy only for a green Marker MCQ, the same question by wording, whose library formulas are damaged.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from . import refs
from .chunking import Chunk, make_id, new_meta
from .parsers import Page

ROOT = Path(__file__).resolve().parents[1]
CORRECTIONS = ROOT / "data" / "scan_corrections.jsonl"
QUALITY_REPORT = ROOT / "data" / "reports" / "scan_quality.json"

# Old-syllabus topic → 2025 sub-topics the classifier may choose from.
TOPIC_SCOPE = {
    1: ["S1.1", "S1.4", "S1.5", "R2.1"], 2: ["S1.2", "S1.3"], 3: ["S3.1"], 4: ["S2"], 5: ["R1"], 6: ["R2.2"],
    7: ["R2.3"], 8: ["R3.1"], 9: ["R3.2"], 10: ["S3.2", "R3.3", "R3.4"], 11: ["S3.2", "S1"],
}

HEADER_RE = re.compile(r"Q\s*#\s*(\d{1,3})\s*/(.*)$")
_DATE_RE = re.compile(r"(\d{4})\s*/\s*([sSwW])\s*/\s*(TZ\s*[oO0]?\s*SP\b|TZ\s*\d|Time\s*Zone\s*\d|Specimen)", re.I)
_PAPER_RE = re.compile(r"(?:Paper\s*|/\s*P)(\d)\b", re.I)
_HEADER_Q_RE = re.compile(r"/\s*Q\s*(\d{1,2})\b")
_FURNITURE_RE = re.compile(
    r"Patrick Brannac|SmashingScience|Page\s+\d+\s+of\s+\d+|^\s*(?:SMASHING|MASH\w*|PB)\W*$|^\s*Topic\s+(?:Chem\s+)?\d+(?:\s+\d+)?(?:\s+MS)?\s*$|"
    r"^\s*Mark\s*Scheme\b.*$|^[\s.·…_*|-]*$", re.I)
_NUMBER_RE = re.compile(r"^\s*(\d{1,2})\s*[.,](?:\s+(.*))?$")
_KEY_RE = re.compile(r"^\s*(\d{1,2})\s*[.,]?\s*[_\s]*([ABCD])[_\s]*$")
_OPTION_RE = re.compile(r"^\s*([ABCD])\s*[.,)](?:\s|$)", re.M)
_FIGURE_RE = re.compile(r"\b(?:diagram|graph|shown below|figure|sketch|apparatus|curve|profile|cycle below)\b", re.I)


_FORMULA = r"(?:[A-Z][a-z]?\d*|\([A-Z][a-z]?\d*\)\d*)+"
SYMBOLS = {"X", "Y", "Z", "R", "A", "B", "D", "E", "G", "J", "L", "M", "Q", "T"}     # exam placeholders, not misreads


def fix_chem_misreads(text: str) -> str:
    """Corrections with one possible reading: state symbol (1) → (l), and C1 → Cl where carbon-one makes no sense."""
    t = re.sub(rf"(?<![A-Za-z0-9])(\d*{_FORMULA}(?:\d?[+\-])?)\s*\(\s*[1I|]\s*\)", r"\1(l)", text)
    t = re.sub(r"(?<=[A-Za-z0-9)])C1(?=\d?(?:[\s)\-+(,.]|$))", "Cl", t)              # NaC1, HC1, CaC12
    t = re.sub(r"(?<![A-Za-z0-9])C1(?=\s*[-–+(|]|\s*$)", "Cl", t, flags=re.M)         # C1-, C1(g), a table cell
    t = re.sub(r"(?<=[A-Za-z][\-–])C1\b", "Cl", t)                                    # H-C1, Cl-C1
    return t


def lost_species(text: str) -> list[str]:
    """A state symbol with no formula before it: OCR lost a species, as in "2 (aq)"."""
    return [m.group(0).strip() for line in text.splitlines() if re.search(r"→|⇌|->", line)
            for m in re.finditer(r"(?:^|\s\+\s*|[→⇌>]\s*)\d*\s*\(\s*(?:g|s|l|aq)\s*\)", line)]


def unknown_elements(text: str) -> list[str]:
    """Element-like symbols in bonds (H-Bf) or state-labelled formulas that aren't real elements."""
    found = set()
    for a, b in re.findall(r"(?<![A-Za-z0-9])([A-Z][a-z]?)\s*[-–=≡]\s*([A-Z][a-z]?)(?![A-Za-z0-9])", text):
        found.update(x for x in (a, b) if x not in ELEMENTS | SYMBOLS)
    for formula in re.findall(rf"(?<![A-Za-z0-9])\d*({_FORMULA})(?:\d?[+\-])?\s*\(\s*(?:g|s|l|aq)\s*\)", text):
        found.update(e for e in re.findall(r"[A-Z][a-z]?", formula) if e not in ELEMENTS | SYMBOLS)
    return sorted(found)


def parse_header(line: str, default_paper: str) -> dict | None:
    """{'q', 'session', 'variant', 'paper', 'exam_q'} from a Q# header, or {'q', 'session': None} if it can't be read."""
    m = HEADER_RE.search(line)
    if not m:
        return None
    rest = m.group(2)
    date = _DATE_RE.search(rest)
    head = {"q": int(m.group(1)), "session": None, "variant": None, "paper": default_paper, "exam_q": None}
    if not date:
        return head
    paper = _PAPER_RE.search(rest)
    if paper:
        head["paper"] = paper.group(1)
    q = _HEADER_Q_RE.search(rest)
    head["exam_q"] = int(q.group(1)) if q else None
    tz = re.search(r"\d", date.group(3))
    if not tz or re.search(r"SP\b", date.group(3), re.I):      # specimen paper ("Specimen Paper", "TZoSP")
        head.update(session="EXM", variant="TZ0")
        return head
    november = date.group(2).lower() == "w"
    head.update(session=f"{date.group(1)[2:]}{'N' if november else 'M'}",
                variant="TZ0" if november else f"TZ{tz.group(0)}")          # November has one time zone
    return head


def _blocks(pages: list[Page], paper: str, ms_start: int) -> list[dict]:
    blocks: list[dict] = []
    cur = None
    for pg in pages:
        kind = "ms" if pg.page >= ms_start else "q"
        for raw in pg.markdown.splitlines():
            head = parse_header(raw, paper)                 # some headers carry the book's web address: test first
            inferred = False
            if not head and "IB" in raw and _DATE_RE.search(raw) and blocks:
                # OCR garbled the "Q# n" part but the date path survives: Q# runs in order, so take the next one
                head = parse_header(f"Q# {blocks[-1]['q'] + 1}/ {raw}", paper)
                inferred = True
            if not head and _FURNITURE_RE.search(raw):
                continue
            if head:
                match = HEADER_RE.search(raw)
                before = raw[:match.start()] if match else ""
                if cur and _NUMBER_RE.match(before):
                    cur["lines"].append((pg.page, before.strip()))
                cur = {**head, "kind": kind, "lines": [], "p0": pg.page, "engine": set(), "header_inferred": inferred}
                blocks.append(cur)
                tail = raw.split(":o)", 1)[1].strip() if ":o)" in raw else ""      # question text OCR ran into the header
                if tail:
                    cur["lines"].append((pg.page, tail))
                continue
            if cur and cur["kind"] == kind:
                cur["lines"].append((pg.page, fix_chem_misreads(raw.strip())))
        if cur and cur["kind"] == kind:
            cur["engine"].add(pg.parser)
    # A header OCR couldn't read gets its reference from the same Q# in the other section
    by_q = defaultdict(list)
    for b in blocks:
        by_q[b["q"]].append(b)
    for group in by_q.values():
        known = next((b for b in group if b["session"]), None)
        for b in group:
            if known and not b["session"]:
                b.update(session=known["session"], variant=known["variant"], paper=known["paper"])
    return blocks


_SESSION_HEAD_RE = re.compile(r"^\W*HL\s*(?:SECTION\s*)?([AB])?\W*(\d{2})\s*([sSwW])\b(.*)$")
_SESSION_FURNITURE_RE = re.compile(r"^\W*(?:IB HL \d+ EQ\b.*|Page \d+ of \d+.*|PB|TABLE \d+\b.*|DATA BOOKLET.*|Mark\s*Scheme\W*)$", re.I)
_BARE_NUMBER_RE = re.compile(r"^\s*\d{1,2}\s*[a-z]?\s*$")


def session_of(yy: str, season: str) -> tuple[str, str] | None:
    """('10N', 'TZ0') from '10w'. May had one paper before 2009 and two time zones after, which the header doesn't say (variant left empty)."""
    year = int(yy)
    if year >= 90:                # 1999: too old to be useful, and a ref can't name it
        return None
    if season.lower() == "w":
        return f"{yy}N", "TZ0"
    return f"{yy}M", ("TZ0" if year < 9 else "")


def _session_blocks(pages: list[Page], paper: str, ms_start: int) -> list[dict]:
    """Blocks from session headers. The question and markscheme sections list the sessions in the same order, so the nth pairs with the nth."""
    blocks: list[dict] = []
    count = {"q": 0, "ms": 0}
    cur = None
    in_ms = False
    for pg in pages:
        for raw in pg.markdown.splitlines():
            head = _SESSION_HEAD_RE.match(raw)
            # The last question ends on the page where the markschemes begin, so the section starts at its heading
            if pg.page >= ms_start and (pg.page > ms_start or re.search(r"Mark\s*Scheme", raw, re.I)):
                in_ms = True
            kind = "ms" if in_ms else "q"
            if head:
                count[kind] += 1
                found = session_of(head.group(2), head.group(3))
                cur = {"q": count[kind], "exam_q": None, "kind": kind, "lines": [], "p0": pg.page, "engine": set(), "header_inferred": False,
                       "session": found[0] if found else None, "variant": found[1] if found else "", "paper": paper}
                blocks.append(cur)
                tail = head.group(4).strip()
                if tail:
                    cur["lines"].append((pg.page, tail))
                continue
            if _SESSION_FURNITURE_RE.match(raw) or not raw.strip():
                continue
            if cur and cur["kind"] == kind and not (not cur["lines"] and _BARE_NUMBER_RE.match(raw)):      # "HL B 10w" / "4" / "(c) ..."
                cur["lines"].append((pg.page, fix_chem_misreads(raw.strip())))
        if cur:
            cur["engine"].add(pg.parser)
    return blocks


def _items(block: dict) -> list[tuple[int, list[tuple[int, str]]]]:
    """Split a question block into (printed question number, lines). Numbers must rise; a drop means a lost header."""
    items: list[tuple[int, list]] = []
    preamble: list[tuple[int, str]] = []
    shared: set[int] = set()
    for page, line in block["lines"]:
        m = _NUMBER_RE.match(line)
        n = int(m.group(1)) if m else None
        if not n and items:
            # OCR can put the number inside the sentence: "Which statement about 19. this reaction is correct?"
            inline = re.search(rf"(?<=\s){items[-1][0] + 1}\.\s", line)
            if inline:
                n = items[-1][0] + 1
                line = f"{n}. {line[:inline.start()].strip()} {line[inline.end():].strip()}"
        if n and (not items or n > items[-1][0]) and n <= 45:
            items.append((n, [(page, line)]))
        elif items:
            items[-1][1].append((page, line))
        elif block.get("exam_q"):
            items.append((block["exam_q"], [(page, line)]))
        else:
            preamble.append((page, line))                     # an introduction before the first number
            pair = re.search(r"Questions?\s+(\d{1,2})\s+and\s+(\d{1,2})", line)
            if pair:
                shared.update(int(x) for x in pair.groups())
    if preamble and items:
        targets = {n for n, _l in items} & shared or {items[0][0]}
        items = [(n, preamble + lines if n in targets else lines) for n, lines in items]
    return items


def _ms_items(block: dict) -> list[tuple[int, list[tuple[int, str]]]]:
    """Structured markscheme rows repeat the number ("5. b ...", "5. c ..."), so same-number rows stay together."""
    items: dict[int, list] = {}
    cur = None
    for page, line in block["lines"]:
        m = _NUMBER_RE.match(line.replace(" | ", " ", 1))
        if m and int(m.group(1)) <= 45:
            cur = int(m.group(1))
        if cur is None:
            cur = block.get("exam_q")
            if cur is None:
                continue
        items.setdefault(cur, []).append((page, line))
    return sorted(items.items())


def split_scan_book(spec, pages: list[Page]) -> list[Chunk]:
    cfg = spec.scan
    if cfg.get("emit_chunks") is False or not pages:
        return []
    paper = cfg.get("paper", "1")
    ms_start = cfg.get("ms_start") or 10 ** 6
    starts = cfg.get("topic_pages", [])
    engine_of = {p.page: p.parser for p in pages}

    def topic_of(page: int) -> int | None:
        t = sum(page >= s for s in starts)
        return t or None

    by_session = cfg.get("headers") == "session"
    blocks = _session_blocks(pages, paper, ms_start) if by_session else _blocks(pages, paper, ms_start)
    q_topic = {b["q"]: topic_of(b["p0"]) for b in blocks if b["kind"] == "q"}
    q_exam = {b["q"]: b["exam_q"] for b in blocks if b["kind"] == "q" and b["exam_q"]}
    # A question header without "/Q4/" takes its number from the markscheme rows with the same Q#
    ms_number = {}
    for b in blocks:
        if b["kind"] == "ms" and paper != "1":
            numbers = [n for n, _l in _ms_items(b)]
            if numbers:
                ms_number.setdefault(b["q"], numbers[0])
    for b in blocks:
        if b["kind"] == "q" and paper != "1" and not b["exam_q"] and not by_session:
            b["exam_q"] = ms_number.get(b["q"])
    out: list[Chunk] = []
    for b in blocks:
        if by_session:                                 # the table in sources.toml, worked out against the library and examiner reports
            mapped = cfg.get("refs", {}).get(str(b["q"]))
            if not mapped:
                b["session"] = None
                continue
            session, _paper, _level, b["variant"], number = mapped.split(".")
            b["session"], b["exam_q"] = session, int(number)
    for b in blocks:
        if not b["session"]:
            continue                                   # no reference from either section: reported by coverage()
        is_mcq = paper == "1"
        if by_session:
            items = [(b["exam_q"], b["lines"])] if b["lines"] else []
        elif b["kind"] == "q" and not is_mcq and b["exam_q"]:
            items = [(b["exam_q"], b["lines"])] if b["lines"] else []      # the header names the question: table rows can't split it
        elif b["kind"] == "q" or is_mcq:
            items = _items(b)
        else:
            b["exam_q"] = b["exam_q"] or q_exam.get(b["q"])
            items = _ms_items(b)
        topic = q_topic.get(b["q"])
        for number, lines in items:
            q = refs.QRef(b["session"], b["paper"], "HL", b["variant"], number)
            body = "\n".join(l for _p, l in lines).strip()
            used = sorted({p for p, _l in lines})
            base = dict(origin=spec.origin, doc_id=spec.doc_id, page_start=used[0], page_end=used[-1], question_ref=q.key,
                        session=q.session_label, paper=q.paper, variant=q.variant, level="HL", syllabus_era=q.syllabus_era,
                        scope=TOPIC_SCOPE.get(topic, []), scan_book=True, book_q=b["q"], book_topic=topic,
                        classify_group=f"{b['q']}.{number}", header_inferred=b["header_inferred"],
                        scan_engine="marker" if all(engine_of.get(p) == "local:marker" for p in used) else "rapidocr")
            if b["kind"] == "q":
                out.append(Chunk(id=make_id(spec.doc_id, "q", b["q"], number),
                                 text=f"[{q.key}] {q.session_label} Paper {q.paper} HL Q{number}\n{body}",
                                 metadata=new_meta(source_type="past_paper",
                                                   question_type="mcq" if is_mcq else "structured", **base)))
                continue
            key = None
            if is_mcq:
                m = next((k for k in map(_KEY_RE.match, (l for _p, l in lines)) if k), None)
                if not m:
                    continue                           # a number with no readable letter
                key, body = m.group(2), m.group(2)
            meta = new_meta(source_type="markscheme", markscheme_origin="scan_book", **base)
            if key:
                meta["mcq_answer"] = key
            out.append(Chunk(id=make_id(spec.doc_id, "ms", b["q"], number),
                             text=f"[MARKSCHEME {q.key}] {q.session_label} Paper {q.paper} HL Q{number}\n{body}", metadata=meta))
    return out


# --------------------------------------------------------------------------- #
# Checks: pure functions over text
# --------------------------------------------------------------------------- #
ELEMENTS = set("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr "
               "Ag Cd Sn Sb Te I Xe Cs Ba Pt Au Hg Pb Bi".split())
_COEFF = r"(?:[½¼¾]|\d+/\d+|\d*)"
_FRACTIONS = {"½": Fraction(1, 2), "¼": Fraction(1, 4), "¾": Fraction(3, 4)}
_SPECIES = rf"{_COEFF}[A-Z][A-Za-z0-9()]*(?:\d?[+\-])?\s*\(\s*(?:g|s|l|aq)\s*\)"
_EQUATION_RE = re.compile(rf"({_SPECIES}(?:\s*\+\s*{_SPECIES})*)\s*(?:→|⇌|->)\s*({_SPECIES}(?:\s*\+\s*{_SPECIES})*)")


def _atoms(species: str) -> Counter | None:
    s = re.sub(r"\s*\(\s*(?:g|s|l|aq)\s*\)$", "", species.strip())
    s = re.sub(r"\d?[+\-]$", "", s)
    m = re.fullmatch(rf"({_COEFF})((?:[A-Z][a-z]?\d*|\((?:[A-Z][a-z]?\d*)+\)\d*)+)", s)
    if not m:
        return None
    k, total = _FRACTIONS.get(m.group(1)) or Fraction(m.group(1) or 1), Counter()
    for group, times in re.findall(r"\(((?:[A-Z][a-z]?\d*)+)\)(\d*)", m.group(2)):
        for e, n in re.findall(r"([A-Z][a-z]?)(\d*)", group):
            total[e] += int(n or 1) * int(times or 1) * k
    for e, n in re.findall(r"([A-Z][a-z]?)(\d*)", re.sub(r"\([^)]*\)\d*", "", m.group(2))):
        total[e] += int(n or 1) * k
    return total


def equation_issues(text: str) -> list[str]:
    """Equations with state symbols whose atoms don't balance or whose symbols aren't elements."""
    issues = []
    for left, right in _EQUATION_RE.findall(text):
        sides = []
        for side in (left, right):
            total = Counter()
            for sp in re.split(r"\s*\+\s*(?=[\d½¼¾/]*[A-Z])", side):
                a = _atoms(sp)
                if a is None or not set(a) <= ELEMENTS:
                    total = None
                    break
                total.update(a)
            sides.append(total)
        if sides[0] is None or sides[1] is None or sides[0] != sides[1]:
            issues.append(f"{left} → {right}"[:80])
    return issues


_SCI_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[×x]\s*10(?:\^\s*([\-]?\d+)|([1-9]\d?)\b)")
_FACTOR = r"(?:ln\s*)?\d+(?:\.\d+)?"
_UNITS = r"(?:\s*[A-Za-zµ°][A-Za-z]*(?:\s?-?\d)?){0,4}"
_PRODUCT_RE = re.compile(rf"({_FACTOR}{_UNITS}(?:\s*×\s*{_FACTOR}{_UNITS})+)")


def _plain_sci(text: str) -> str:
    def sub(m):
        exp = m.group(2) or m.group(3)
        return f"{float(m.group(1)) * 10 ** int(exp):.10g}"
    return _SCI_RE.sub(sub, text.replace("−", "-").replace("–", "-"))


def arithmetic_issues(text: str) -> list[str]:
    """Multiply out "a × b × ln c" and require the result (±3%) somewhere else in the same answer."""
    plain = _plain_sci(text)
    issues = []
    for m in _PRODUCT_RE.finditer(plain):
        value = 1.0
        for f in re.split(r"×", m.group(1)):
            n = re.search(r"(ln\s*)?(\d+(?:\.\d+)?)", f)
            value *= math.log(float(n.group(2))) if n.group(1) else float(n.group(2))
        rest = plain[:m.start()] + " " + plain[m.end():]
        others = [abs(float(x)) for x in re.findall(r"\d+(?:\.\d+)?(?:e[+\-]?\d+)?", rest)]
        if value and not any(abs(o - abs(value)) / abs(value) <= 0.03 for o in others):
            issues.append(f"{m.group(1).strip()[:60]} = {value:.4g}")
    return issues


def lost_operators(text: str) -> list[str]:
    """Answer options with two numbers and nothing between them: OCR lost the sign, as in "A. -623 286"."""
    return [line.strip() for line in text.splitlines()
            if _OPTION_RE.match(line) and re.search(r"\d\s+[\d(]", _OPTION_RE.sub("", line, count=1))]


def options_ok(text: str) -> bool:
    """Each of A-D exactly once, in order, with nothing long after D (a swallowed next question leaves text there)."""
    labels = _OPTION_RE.findall(text)
    if labels != ["A", "B", "C", "D"]:
        return False
    tail = text[[m.start() for m in _OPTION_RE.finditer(text)][-1]:].splitlines()[1:]
    return sum(len(l) for l in tail) <= 60


def marks_claimed(text: str) -> int:
    return sum(int(x) for x in re.findall(r"\[(\d)\]", re.sub(r"Award\s*\[\d\]", "", text, flags=re.I)))


def marks_awarded(text: str) -> int:
    total = 0
    for line in text.splitlines():
        m = re.search(r"(?:^|\|\s*)(\d)\s*$", line)
        if m:
            total += int(m.group(1))
    return total


def numbers_in(text: str) -> set[str]:
    """Decimals, multi-digit numbers and powers of ten, comparable across engines' notations."""
    t = text.translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")).replace("^", "")
    return set(re.findall(r"\d+\.\d+|\d{2,}", t))


def words_in(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower()))


def overlap(a: str, b: str) -> float:
    wa, wb = words_in(a), words_in(b)
    return len(wa & wb) / max(1, min(len(wa), len(wb)))


def has_damaged_formulas(text: str) -> bool:
    """Library text where a parser pushed subscripts onto their own line: "CO ( g)" followed by "2 2"."""
    return bool(re.search(r"^\s*\d(?:\s+\d)*\s*$", text, re.M) and re.search(r"[A-Z][a-z]?\s+\(\s*(?:g|s|l|aq)\s*\)", text))


def _body(c: Chunk) -> str:
    return c.text.split("\n", 1)[1] if "\n" in c.text else ""


def flags_for(c: Chunk) -> list[str]:
    """Checks that need only the chunk itself."""
    m, body, flags = c.metadata, _body(c), []
    if m["scan_engine"] != "marker":
        flags.append("rapid_only")
    if m.get("header_inferred"):
        flags.append("header_inferred")
    if m["source_type"] == "past_paper":
        if m["question_type"] == "mcq" and not options_ok(body):
            flags.append("bad_options")
        if _FIGURE_RE.search(body):
            flags.append("needs_figure")
        if lost_operators(body):
            flags.append("lost_operator")
    if equation_issues(body):
        flags.append("unbalanced_equation")
    if lost_species(body):
        flags.append("lost_species")
    if unknown_elements(body):
        flags.append("unknown_element")
    if m["source_type"] == "markscheme" and arithmetic_issues(body):
        flags.append("arithmetic_mismatch")
    return flags


def assess(book_chunks: list[Chunk], library: list[Chunk], rapid_chunks: list[Chunk] | None = None) -> dict:
    """Set scan_flags on book chunks. Returns check statistics."""
    lib_key, report_key = {}, {}
    for c in library:
        m, ref = c.metadata, c.metadata.get("question_ref")
        if not ref:
            continue
        if m["source_type"] == "markscheme":
            k = m.get("mcq_answer") or (_body(c).strip() if re.fullmatch(r"[ABCD]", _body(c).strip()) else None)
            if k:
                lib_key[ref] = k
        elif m["source_type"] == "examiner_report" and m.get("report_answer"):
            report_key[ref] = m["report_answer"]
    rapid = {(c.metadata["doc_id"], c.metadata["source_type"], c.metadata["book_q"], c.metadata["question_ref"]): c
             for c in rapid_chunks or []}
    by_q = defaultdict(lambda: defaultdict(list))
    for c in book_chunks:
        by_q[(c.metadata["doc_id"], c.metadata["book_q"])][c.metadata["source_type"]].append(c)

    stats = Counter()
    for c in book_chunks:
        m = c.metadata
        flags = flags_for(c)
        ref = m["question_ref"]
        key = m.get("mcq_answer")
        if key:
            for name, table in (("library", lib_key), ("report", report_key)):
                if ref in table:
                    agree = table[ref] == key
                    stats[f"key_{name}_{'agree' if agree else 'conflict'}"] += 1
                    if not agree:
                        flags.append("key_conflict")
        if m["scan_engine"] == "marker" and rapid_chunks is not None:
            other = rapid.get((m["doc_id"], m["source_type"], m["book_q"], ref))
            if other is None:
                stats["rapid_has_no_copy"] += 1
            elif key:
                if other.metadata.get("mcq_answer") != key:
                    flags.append("engines_disagree")
            elif numbers_in(_body(c)) - numbers_in(_body(other)):
                flags.append("engines_disagree")
        sibs = by_q[(m["doc_id"], m["book_q"])]
        if m["source_type"] == "past_paper":
            ms_refs = {x.metadata["question_ref"] for x in sibs["markscheme"]}
            if ref not in ms_refs and ref not in lib_key:
                flags.append("no_markscheme")
            if ms_refs and {r.rsplit(".", 1)[0] for r in ms_refs} != {ref.rsplit(".", 1)[0]}:
                flags.append("ref_conflict")
            if m["question_type"] == "structured":
                for ms in sibs["markscheme"]:
                    # only Marker keeps the table's marks column apart from the answer text
                    if ms.metadata["question_ref"] == ref and ms.metadata["scan_engine"] == "marker":
                        claimed, awarded = marks_claimed(_body(c)), marks_awarded(_body(ms))
                        if claimed and awarded and claimed != awarded:
                            flags.append("marks_mismatch")
        m["scan_flags"] = sorted(set(flags))
    return dict(stats)


def apply_figures(book_chunks: list[Chunk], library: list[Chunk], figures: list[dict], descriptions: dict[str, dict]) -> dict:
    """Attach diagram crops to their questions. The deck builder reads text, so a book question whose diagram has no
    description waits (figure_undescribed). A described diagram also reaches the library's copy of the same question."""
    stats = Counter()
    questions = [c for c in book_chunks if c.metadata["source_type"] == "past_paper"]
    by_key = {(c.metadata["doc_id"], c.metadata["book_q"], int(c.metadata["question_ref"].rsplit(".", 1)[1])): c for c in questions}
    first_in_block: dict[tuple, Chunk] = {}
    for c in questions:
        first_in_block.setdefault((c.metadata["doc_id"], c.metadata["book_q"]), c)
    lib_q = defaultdict(list)
    for c in library:
        if c.metadata["source_type"] == "past_paper" and c.metadata.get("question_ref"):
            lib_q[c.metadata["question_ref"]].append(c)
    for fig in figures:
        entry = descriptions.get(fig["file"], {})
        if entry.get("numbers"):                             # matched by eye
            targets = [by_key.get((fig["doc_id"], entry["book_q"], n)) for n in entry["numbers"]]
        else:
            targets = [by_key.get((fig["doc_id"], fig["book_q"], fig["number"])) or first_in_block.get((fig["doc_id"], fig["book_q"]))]
        targets = [c for c in targets if c is not None]
        if not targets:
            stats["figure_without_question"] += 1
            continue
        kind = entry.get("kind") or fig["kind"]
        stats[f"attached_{kind}"] += 1
        text = entry.get("description")
        for c in targets:
            m = c.metadata
            m.setdefault("figures", []).append(fig["file"])
            if kind == "table":
                continue
            if not text:
                m["scan_flags"] = sorted({*m["scan_flags"], "figure_undescribed"})
                continue
            stats["described"] += 1
            c.text += f"\n[FIGURE: {text}]"
            m["scan_flags"] = [f for f in m["scan_flags"] if f != "needs_figure"]
            for old in lib_q.get(m["question_ref"], []):
                if overlap(_body(c), _body(old)) >= 0.5 and text not in old.text:
                    old.text += f"\n[FIGURE: {text}]"
                    old.metadata.setdefault("figures", []).append(fig["file"])
                    stats["described_on_library_copy"] += 1
    return dict(stats)


def apply_corrections(book_chunks: list[Chunk], path: Path = CORRECTIONS) -> int:
    if not path.exists():
        return 0
    fixes = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    table = {(f["doc_id"], f["book_q"], f["number"], f["kind"]): f for f in fixes}
    n = 0
    for c in book_chunks:
        m = c.metadata
        kind = "question" if m["source_type"] == "past_paper" else "markscheme"
        f = table.get((m["doc_id"], m["book_q"], int(m["question_ref"].rsplit(".", 1)[1]), kind))
        if not f:
            continue
        if f.get("text"):
            c.text = c.text.split("\n", 1)[0] + "\n" + f["text"]
            if re.fullmatch(r"[ABCD]", f["text"].strip()):
                m["mcq_answer"] = f["text"].strip()
        m["scan_flags"], m["scan_reviewed"] = [], True
        n += 1
    return n


def _grade(flags: list[str]) -> str:
    if {"key_conflict", "ref_conflict"} & set(flags):
        return "red"
    return "amber" if flags else "green"


def merge_with_library(chunks: list[Chunk], rapid_chunks: list[Chunk] | None = None,
                       figures: list[dict] | None = None, descriptions: dict[str, str] | None = None) -> tuple[list[Chunk], dict]:
    """Check the book chunks, then keep only what adds to or repairs the library. Returns (chunks, report)."""
    book = [c for c in chunks if c.metadata.get("scan_book")]
    library = [c for c in chunks if not c.metadata.get("scan_book")]
    stats = assess(book, library, rapid_chunks)
    figure_stats = apply_figures(book, library, figures or [], descriptions or {})
    reviewed = apply_corrections(book)
    for c in book:
        c.metadata["scan_quality"] = _grade(c.metadata["scan_flags"])

    lib_q, lib_ms = defaultdict(list), defaultdict(list)
    for c in library:
        ref = c.metadata.get("question_ref")
        if ref and c.metadata["source_type"] == "past_paper":
            lib_q[ref].append(c)
        elif ref and c.metadata["source_type"] == "markscheme":
            lib_ms[ref].append(c)

    drop: set[str] = set()
    tally = Counter()
    used_refs = set()
    for c in book:
        m, ref = c.metadata, c.metadata["question_ref"]
        if m["source_type"] == "markscheme":
            if ref in lib_ms:
                drop.add(c.id)
                tally["ms_library_already_has"] += 1
            else:
                tally["ms_fills_gap"] += 1
            continue
        if ref not in lib_q:
            tally["question_new"] += 1
            continue
        old = " ".join(_body(x) for x in lib_q[ref])
        same = overlap(_body(c), old) >= 0.6
        if m["question_type"] == "mcq" and m["scan_quality"] == "green" and same and has_damaged_formulas(old) and ref not in used_refs:
            drop.update(x.id for x in lib_q[ref])
            used_refs.add(ref)
            tally["question_repairs_library"] += 1
        else:
            drop.add(c.id)
            tally["question_library_already_has"] += 1
            if not same:
                tally["question_wording_differs"] += 1

    kept = [c for c in chunks if c.id not in drop]
    held = [c for c in kept if c.metadata.get("scan_book")]
    report = {
        "checks": stats, "figures": figure_stats, "reviewed": reviewed, "merge": dict(tally),
        "kept_by_quality": dict(Counter(c.metadata["scan_quality"] for c in held)),
        "flags": dict(Counter(f for c in held for f in c.metadata["scan_flags"])),
        "needs_review": [{"doc_id": c.metadata["doc_id"], "book_q": c.metadata["book_q"], "ref": c.metadata["question_ref"],
                          "kind": c.metadata["source_type"], "page": c.metadata["page_start"], "topic": c.metadata["book_topic"],
                          "flags": c.metadata["scan_flags"]}
                         for c in held if c.metadata["scan_flags"] and c.metadata["scan_flags"] != ["rapid_only"]],
    }
    return kept, report


def coverage(specs, pages_of) -> dict:
    """Per book: Q# gaps, unread headers, and question blocks with no markscheme block."""
    out = {}
    for s in specs:
        cfg = s.scan
        pages = pages_of(s.doc_id)
        if not pages or cfg.get("emit_chunks") is False:
            continue
        blocks = _blocks(pages, cfg.get("paper", "1"), cfg.get("ms_start") or 10 ** 6)
        q = {b["q"] for b in blocks if b["kind"] == "q"}
        ms = {b["q"] for b in blocks if b["kind"] == "ms"}
        seen = sorted(q | ms)
        out[s.doc_id] = {"question_blocks": len(q), "markscheme_blocks": len(ms),
                         "gaps": [n for n in range(seen[0], seen[-1] + 1) if n not in q and n not in ms] if seen else [],
                         "questions_without_markscheme": sorted(q - ms), "markschemes_without_question": sorted(ms - q),
                         "unread_headers": sorted({b["q"] for b in blocks if not b["session"]})}
    return out


def propagate_tags(chunks: list[Chunk]) -> int:
    """A book markscheme takes the tags of the question with the same Q#, so one exam question split across
    old topics (part d in energetics, part a in periodicity) keeps each part under its own sub-topic."""
    questions = {}
    for c in chunks:
        m = c.metadata
        if m.get("scan_book") and m["source_type"] == "past_paper":
            questions[(m["doc_id"], m["book_q"], m["question_ref"])] = c
    n = 0
    for c in chunks:
        m = c.metadata
        if not m.get("scan_book") or m["source_type"] != "markscheme" or m.get("sub_topic"):
            continue
        q = questions.get((m["doc_id"], m["book_q"], m["question_ref"]))
        if q and q.metadata.get("sub_topic"):
            for k in ("sub_topic", "understanding", "theme", "sub_topics_all", "tag_confidence"):
                m[k] = q.metadata.get(k)
            m["tag_method"] = "scan_book_q"
            n += 1
    return n


def write_report(report: dict) -> None:
    QUALITY_REPORT.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
