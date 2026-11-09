"""Run: python -m pytest -q tests/"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import refs, taxonomy  # noqa: E402
from ingest.chunking import split_long  # noqa: E402


# ---------------- sub-topic header regex ----------------
def h(line):
    return taxonomy.match_header(line)


def test_full_headers():
    assert h("Reactivity 1.2 Energy cycles in reactions").sub_topic == "R1.2"
    assert h("## Reactivity 1.2 Energy cycles in reactions").sub_topic == "R1.2"
    assert h("RUNNING_HEADER: Structure 2.2 The covalent model").sub_topic == "S2.2"
    assert h("Structure 1.1—Introduction to the particulate nature of matter").sub_topic == "S1.1"
    assert h("Reactivity 1.1 – Measuring enthalpy changes").sub_topic == "R1.1"


def test_structure_and_reactivity_1_1_are_different():
    assert h("Structure 1.1—Introduction to the particulate nature of matter").sub_topic == "S1.1"
    assert h("Reactivity 1.1—Measuring enthalpy changes").sub_topic == "R1.1"


def test_understanding_level():
    hit = h("Reactivity 1.2.5—A Born–Haber cycle is an application of Hess’s law")
    assert (hit.sub_topic, hit.understanding) == ("R1.2", "R1.2.5")


def test_abbreviated_heading():
    assert h("### R2.3 How far? The extent of chemical change").sub_topic == "R2.3"
    assert h("S1.1") is None                      # bare abbreviation is too weak


def test_rejections():
    assert h("Structure 3.4 Something") is None   # no such sub-topic
    assert h("1.1 Introduction") is None          # bare number is ambiguous
    assert h("Reactivity 1.23 blah blah") is None
    assert h("The data in Reactivity 1.2 shows") is None   # not at line start


def test_cross_links_do_not_switch_state():
    assert h("Structure 2.2—How do intermolecular forces influence the type of mixture?").is_cross_link
    assert h("Structure 2.1").is_cross_link       # margin tag in the Oxford book
    assert h("Structure 3.2 25").is_cross_link    # margin tag + page number
    assert not h("## Structure 2.1 The ionic model").is_cross_link


def test_mentions_and_booklet_sections():
    assert taxonomy.mentions("see Structure 2.2 and Reactivity 3.1 for more") == ["S2.2", "R3.1"]
    assert taxonomy.data_booklet_sections("Use section 14 of the data booklet.") == [14]
    assert taxonomy.normalise_code("Reactivity 1.2") == "R1.2"
    assert taxonomy.normalise_code("1.2") is None


# ---------------- question references ----------------
def test_qb_header_refs():
    q, _ = refs.from_qb_header("Question 3 Question 3 from Paper 1 · HL · May 2024 · TZ1")
    assert q.key == "24M.1.HL.TZ1.3" and q.syllabus_era == "legacy"
    q, _ = refs.from_qb_header("Question 2 from Paper 1 · HL · November 2024")
    assert q.key == "24N.1.HL.TZ0.2"
    q, _ = refs.from_qb_header("Question 5 from Paper 2 · HL · May 2025 · TZ3")
    assert q.key == "25M.2.HL.TZ3.5" and q.syllabus_era == "2025"


def test_ms_refs():
    assert refs.from_ms_ref("17M.2.HL.TZ2.7").key == "17M.2.HL.TZ2.7"
    assert refs.from_ms_ref("MS_REF: 19N.1.SL.TZ0.12").key == "19N.1.SL.TZ0.12"
    assert refs.from_ms_ref("EXM.2.HL.TZ0.3").session_label == "Specimen"
    assert refs.from_ms_ref("17M.2.HL.TZ2.7 extra") is None


def test_official_cover():
    c = refs.official_cover("8824 – 9541M\nMarkscheme\nNovember 2024\nChemistry\nHigher level\nPaper 2\n20 pages")
    assert c == {"paper_code": "9541", "is_markscheme": True, "session": "24N", "level": "HL", "paper": "2"}
    c = refs.official_cover("Chemistry\nHigher level\nPaper 1B\n16 May 2025\nInstructions to candidates\n" + "x\n" * 30 + "2225 – 6220")
    assert c["paper_code"] == "6220" and not c["is_markscheme"] and c["paper"] == "1B"


def test_split_long_respects_limit():
    text = "\n\n".join(f"para {i} " + "x" * 500 for i in range(10))
    parts = split_long(text, 1200)
    assert all(len(p) <= 1500 for p in parts) and len(parts) >= 4


# ---------------- subject reports ----------------
from ingest import reports  # noqa: E402
from ingest.parsers import Page  # noqa: E402
from ingest.splitters import SourceSpec  # noqa: E402


def test_report_session_and_headings():
    assert reports._session("May 2025 subject report     Chemistry TZ1") == "25M"
    assert reports._session("SUBJECT REPORTS – NOV 2005") == "05N"
    m = reports.PAPER_RE.match("Higher level paper one Section A")
    assert m and m.group("sec") == "A"
    assert reports.PAPER_RE.match("Standard Level Paper 1 Timezone 1").group("tz") == "1"
    assert reports.PAPER_RE.match("Higher level paper one                     16") is None   # contents line
    assert reports.QUESTION_RE.match("Question F3 (a)").group("opt") == "F"


def test_report_stats():
    s = reports._stats("The correct response, D, was chosen by 56% of candidates. The most popular wrong answer was B.")
    assert s["report_answer"] == "D" and s["pct_correct"] == 56.0 and s["popular_distractor"] == "B"


def _rep_pages():
    return [
        Page(1, "Chemistry\nTimezone 2\nTo protect the integrity\n"),
        Page(2, "May 2024 subject report   Chemistry\nContents\nGrade boundaries 3\n"),
        Page(3, "May 2024 subject report   Chemistry\nHigher level paper one\n"
                "The areas of the programme and examination which appeared difficult for the\nstudents\n"
                "• SN1 reactions and leaving groups\n"
                "The areas of the programme and examination in which students appeared well\nprepared\n"
                "• Voltaic cells\n"
                "Question 16\nOver 65% of candidates answered correctly; the correct response, C, was popular.\n"
                "Question 17\nMany candidates confused the bond enthalpy with the lattice enthalpy here.\n"),
    ]


def test_report_split_end_to_end():
    out = reports.split_subject_reports(SourceSpec("r", "", "subject_report", "test"), _rep_pages())
    q = [c for c in out if c.metadata["source_type"] == "examiner_report"]
    f = [c for c in out if c.metadata["source_type"] == "examiner_finding"]
    assert [c.metadata["question_ref"] for c in q] == ["24M.1.HL.TZ2.16", "24M.1.HL.TZ2.17"]
    assert q[0].metadata["pct_correct"] == 65.0 and q[0].metadata["report_answer"] == "C"
    assert {c.metadata["polarity"] for c in f} == {"difficult", "well_prepared"}


def test_old_ib_code_cover():
    c = refs.official_cover("M09/4/CHEMI/SPM/ENG/TZ2/XX/M\nMARKSCHEME\nMay 2009\nCHEMISTRY\nStandard Level\nPaper 1")
    assert (c["session"], c["level"], c["paper"], c["variant"], c["is_markscheme"]) == ("09M", "SL", "1", "TZ2", True)
