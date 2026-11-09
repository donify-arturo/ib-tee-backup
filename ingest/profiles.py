"""
LlamaParse profiles: one per kind of source. The custom prompts are where the
"don't lose formatting" requirement is enforced — chemistry notation, figure
descriptions, and the markscheme conventions that Pillar 2 (trigger phrases /
trap boundaries) depends on.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParseProfile:
    tier: str                         # fast | cost_effective | agentic | agentic_plus
    prompt: str
    ignore_diagonal_text: bool = False
    remove_watermark: bool = False
    merge_tables: bool = True
    aggressive_tables: bool = False
    charts: bool = False


COMMON = """\
This is IB Diploma Programme Chemistry material (2025 syllabus). Output clean GitHub-flavoured Markdown.
Chemistry notation must survive exactly:
- Formulae and ions with <sub>/<sup>: H<sub>2</sub>SO<sub>4</sub>, Fe<sup>3+</sup>, SO<sub>4</sub><sup>2−</sup>.
- Keep state symbols (s), (l), (g), (aq); arrows → and ⇌; the standard-state symbol ⦵ (ΔH⦵, E⦵); units such as kJ mol<sup>−1</sup>.
- Write mathematical expressions and equations in LaTeX between $…$ (inline) or $$…$$ (display).
- For every diagram, graph, spectrum, apparatus drawing or structural formula, insert a block
  [FIGURE: <what it shows; axis labels and units; key values, peaks, trends; for structures give a condensed/skeletal description and any curly-arrow movements>].
- Never invent content that is not on the page. Do not summarise; transcribe.
"""

PROFILES: dict[str, ParseProfile] = {
    # Oxford course book: diagonal "Evaluation Copy Only" watermark on every page.
    "textbook": ParseProfile(
        tier="agentic",
        ignore_diagonal_text=True,
        remove_watermark=True,
        charts=True,
        prompt=COMMON + """
This is a textbook page. Ignore the diagonal "Oxford University Press Evaluation Copy Only" watermark completely.
- First line of every page: the running header exactly as printed, prefixed with "RUNNING_HEADER: "
  (e.g. "RUNNING_HEADER: Reactivity 1.2 Energy cycles in reactions").
- Last line of every page: "PRINTED_PAGE: <number printed on the page>".
- Section headings as "## ", sub-headings as "### ".
- Keep each worked example, practice question, activity, "Data-based question", ATL, TOK and
  "Linking questions" box as its own "### <label>" block, labelled exactly as in the book.
- Linking questions (e.g. "Structure 2.2—How do intermolecular forces …?") stay as written, one per line.
""",
    ),
    # Oxford answers PDF (clean Word export)
    "textbook_answers": ParseProfile(
        tier="cost_effective",
        prompt=COMMON + """
These are textbook answers. Keep each topic heading (e.g. "Reactivity 1.1 – Measuring enthalpy changes") as "## <heading>".
Keep every section label that cites a book page (e.g. "Practice questions (page 394)") as "### <label>" verbatim.
Keep question numbers and sub-labels (1., a., b., i.) at the start of lines.
""",
    ),
    # IB official PDFs: question papers + markschemes in one combined file.
    "ib_official": ParseProfile(
        tier="agentic",
        aggressive_tables=True,
        charts=True,
        prompt=COMMON + """
The file combines official IB question papers and their markschemes.
COVER PAGES: transcribe identifiers verbatim on separate lines, e.g.
  "PAPER_CODE: 2225 – 6221M", "Markscheme", "May 2025", "Chemistry", "Higher level", "Paper 2".
Skip the copyright/licensing boilerplate pages entirely (output "[BOILERPLATE]").
MARKSCHEMES:
- Output one Markdown table per question with columns: Question | Answers | Notes | Total.
- Put the full question label in the first column (e.g. "1. (a) (ii)").
- Preserve EXACTLY: every tick ✓ (one per marking point), text inside «guillemets», "OR", "AND",
  "ALTERNATIVE 1/2", "ECF", "OWTTE", "[max]", "Accept …", "Do not accept …", "Award [n] …".
- Underlined words are essential for the mark: wrap them as <u>word</u>.
- Multiple-choice answer grids: output one line per question as "Q<n>: <letter>" (skip "–" entries).
QUESTION PAPERS:
- Question numbers ("1.", "(a)", "(i)") at the start of lines; keep mark allocations like "[2]".
- Multiple-choice options as separate lines "A. …", "B. …", "C. …", "D. …".
- Ignore "Please do not write on this page", barcodes and answer-box lines.
""",
    ),
    # RevisionHub question bank prints (browser print-to-PDF)
    "question_bank": ParseProfile(
        tier="agentic",
        charts=True,
        prompt=COMMON + """
This is a browser print of an online question bank. Remove all website chrome: print timestamps,
URLs, page counters, filter panels, navigation tabs, and buttons such as "Submit", "Ans", "Formula Booklet".
Keep each question header line verbatim on its own line, e.g.
  "Question 3 from Paper 1 · HL · May 2024 · TZ1"
followed by its type/difficulty line (e.g. "Multiple choice · Medium") and the full question.
Multiple-choice options as separate lines "A. …" to "D. …". Keep sub-part labels (a), (b), (i), (ii).
""",
    ),
    "question_bank_markscheme": ParseProfile(
        tier="cost_effective",
        prompt=COMMON + """
These are markschemes printed from an online question bank. Remove print timestamps, URLs and page counters.
- Each question reference code (e.g. "17M.2.HL.TZ2.7", "19N.1.SL.TZ0.12", "EXM.2.HL.TZ0.3") goes on its own line
  prefixed with "MS_REF: ".
- Keep part labels (a.i., b(ii)., c.) at the start of lines.
- Preserve EXACTLY: [✔] / ✓ ticks, «guillemets», "OR", "AND", "Accept …", "Do not accept …",
  "Award [n max] …", "Note:", "[3 marks]". Wrap underlined words as <u>word</u>.
""",
    ),
    "data_booklet": ParseProfile(
        tier="agentic",
        aggressive_tables=True,
        prompt=COMMON + """
This is the IB Chemistry data booklet. Each numbered section heading becomes "## <n>. <title>"
(e.g. "## 12. Bond enthalpies or average bond enthalpies at 298.15 K").
Output every table as a complete Markdown table with all rows and columns; merge tables that continue across pages.
The periodic table: output as a table with columns Z | Symbol | Name | Relative atomic mass | Group | Period.
Equations section: one equation per line in LaTeX with its description.
""",
    ),
}
