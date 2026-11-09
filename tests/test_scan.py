"""Scanned-book splitting and the automatic checks, including planted errors the checks must catch.
Uses made-up question text, no real OCR."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import scan_books as sb  # noqa: E402
from ingest import scan_ocr  # noqa: E402
from ingest.chunking import Chunk, new_meta  # noqa: E402
from ingest.parsers import Page  # noqa: E402
from ingest.splitters import SourceSpec  # noqa: E402


def spec(paper="1"):
    return SourceSpec(doc_id="book", path="", source_type="scan_book", origin="test",
                      scan={"paper": paper, "ms_start": 3, "topic_pages": [1]})


def pages(q_text, ms_text, parser="local:marker"):
    return [Page(page=1, markdown=q_text, parser=parser), Page(page=3, markdown=ms_text, parser=parser)]


MCQ = """Chem 5/Q# 7//IB/Paper 1/2014/w/Time Zone 0/Higher Level/
14. Which reaction is exothermic?
A. one
B. two
C. three
D. four
15. Which value is largest?
A. 1.5
B. 2.5
C. 3.5
D. 4.5
Patrick Brannac www.SmashingScience.org Page 1 of 9"""
KEY = "Q# 7/ IB/Paper 1/2014/w/TZ0/HL\n14. B\n15. C"


# ---------------- headers ----------------
def test_header_variants():
    h = sb.parse_header("Chem 5/Q# 89//IB/Paper 1/2014/s/Time Zone 2/Higher Level/", "1")
    assert (h["q"], h["session"], h["variant"], h["paper"]) == (89, "14M", "TZ2", "1")
    h = sb.parse_header("Topic Chem 5 Q# 81/ IB Chem/2018/w/TZ 0/Paper 2/Higher Level/Q4/ www.SmashingScience.org :o)", "2")
    assert (h["session"], h["variant"], h["paper"], h["exam_q"]) == ("18N", "TZ0", "2", 4)
    h = sb.parse_header("T3 Q# 40/IB Chem/2015/w/TZ2/P1/HL", "1")
    assert (h["session"], h["variant"]) == ("15N", "TZ0")          # November has a single time zone
    h = sb.parse_header("T3 Q# 39/ IB Chem/2016/s/Specimen Paper/P1/HL", "1")
    assert h["session"] == "EXM"
    assert sb.parse_header("14. Which reaction?", "1") is None


# ---------------- splitting ----------------
def test_mcq_split_and_join():
    chunks = sb.split_scan_book(spec(), pages(MCQ, scan_ocr.flatten_markdown(KEY)))
    q = {c.metadata["question_ref"]: c for c in chunks if c.metadata["source_type"] == "past_paper"}
    ms = {c.metadata["question_ref"]: c for c in chunks if c.metadata["source_type"] == "markscheme"}
    assert set(q) == {"14N.1.HL.TZ0.14", "14N.1.HL.TZ0.15"} == set(ms)
    assert ms["14N.1.HL.TZ0.15"].metadata["mcq_answer"] == "C"
    assert "Brannac" not in q["14N.1.HL.TZ0.15"].text
    assert q["14N.1.HL.TZ0.14"].metadata["scope"] == sb.TOPIC_SCOPE[1]


def test_header_with_web_address_is_not_treated_as_footer():
    q = ("Topic Chem 5 4 Q# 59/ IB Chem/2019/s/TZ1/Paper 1/Higher Level/Page 4. www.SmashingScience.org :o)\n"
         "14. Which is correct?\nA. one\nB. two\nC. three\nD. four")
    chunks = sb.split_scan_book(spec(), pages(q, "T5 Q# 59/ IB/2019/s/TZ1/P1/HL/Page 4.\n14. A"))
    assert {c.metadata["question_ref"] for c in chunks} == {"19M.1.HL.TZ1.14"}
    assert {c.metadata["source_type"] for c in chunks} == {"past_paper", "markscheme"}


def test_unambiguous_misreads_are_corrected():
    assert sb.fix_chem_misreads("H2O(1) → H2O(s)") == "H2O(l) → H2O(s)"
    assert sb.fix_chem_misreads("2H2O2(1) → 2H2O(1) + O2(g)") == "2H2O2(l) → 2H2O(l) + O2(g)"
    assert sb.fix_chem_misreads("NaC1(s) → Na+(g) + C1-(g)") == "NaCl(s) → Na+(g) + Cl-(g)"
    assert sb.fix_chem_misreads("CaC12(s) and H-C1 < H-I") == "CaCl2(s) and H-Cl < H-I"
    assert sb.fix_chem_misreads("C1-C1 | 242") == "Cl-Cl | 242"
    # readings that must stay as printed
    assert sb.fix_chem_misreads("C12H22O11(aq)") == "C12H22O11(aq)"
    assert sb.fix_chem_misreads("Reaction (1) is faster") == "Reaction (1) is faster"
    assert sb.fix_chem_misreads("Section 1 and C2H6") == "Section 1 and C2H6"


def test_equations_with_fractions_are_read_correctly():
    for good in ("½Br2(l) → Br(g)", "SiH4(g) → SiH3(g) + ½H2(g)", "¼SiH4(g) → ¼Si(g) + H(g)", "½Cl2(g) → Cl(g)",
                 "H2(g) + ½O2(g) → H2O(l)", "C2H6(g) + 7/2O2(g) → 2CO2(g) + 3H2O(l)"):
        assert sb.equation_issues(good) == [], good
    assert sb.equation_issues("½Br2(l) → 2Br(g)")
    assert sb.equation_issues("H2(g) + ½O2(g) → 2H2O(l)")


def test_planted_lost_operator_in_an_option():
    assert sb.lost_operators("16. Which?\nA. -623 286\nB. -623 + 572") == ["A. -623 286"]
    assert sb.lost_operators("16. Which?\nA. -623 - 286\nB. 2.5 × 100.0\nC. 25 °C\nD. 4 cm3") == []
    assert sb.lost_operators("Heated 2 100 times with no options") == []


def test_planted_lost_species_and_unknown_element():
    assert sb.lost_species("H2O2(aq) + 2H+(aq) + 2 (aq) → I2(aq) + 2H2O(l)")
    assert sb.lost_species("H2O2(aq) + 2H+(aq) + 2I-(aq) → I2(aq) + 2H2O(l)") == []
    assert sb.unknown_elements("H-I < H-Bf < H-Cl < H-F") == ["Bf"]
    assert sb.unknown_elements("H-I < H-Br < H-Cl < H-F") == []
    assert sb.unknown_elements("X-Y bonds and Xq2(g)") == ["Xq"]
    assert sb.unknown_elements("CO2(g) + H2O(l)") == []


def test_question_number_inside_a_sentence_starts_the_next_question():
    q = ("Chem 5/Q# 7//IB/Paper 1/2014/w/Time Zone 0/Higher Level/\n18. First question?\nA. a\nB. b\nC. c\nD. d\n"
         "The change is positive. Which statement about 19. this reaction is correct?\nA. e\nB. f\nC. g\nD. h")
    chunks = sb.split_scan_book(spec(), [Page(page=1, markdown=q, parser="local:marker")])
    assert [c.metadata["question_ref"] for c in chunks] == ["14N.1.HL.TZ0.18", "14N.1.HL.TZ0.19"]
    assert all(sb.options_ok(c.text.split("\n", 1)[1]) for c in chunks)
    assert "The change is positive" in chunks[1].text and "The change is positive" not in chunks[0].text


def test_shared_introduction_goes_to_both_questions():
    q = ("Chem 5/Q# 7//IB/Paper 1/2014/w/Time Zone 0/Higher Level/\n"
         "Questions 14 and 15 are about an experiment.\n14. First?\nA. a\nB. b\nC. c\nD. d\n15. Second?\nA. a\nB. b\nC. c\nD. d\n16. Third?\nA. a\nB. b\nC. c\nD. d")
    chunks = sb.split_scan_book(spec(), [Page(page=1, markdown=q, parser="local:marker")])
    has_intro = {c.metadata["question_ref"][-2:]: "about an experiment" in c.text for c in chunks}
    assert has_intro == {"14": True, "15": True, "16": False}


def test_structured_header_without_number_takes_it_from_markscheme():
    q = "Topic Chem 5 Q# 8/ IB Chem/2015/s/TZ2/Paper 2 Section A/Higher Level/\nA student did an experiment. [2]"
    ms = "Topic Chem 5 Q# 8/ IB Chem/2015/s/TZ2/P2/Higher Level/\n3. | a | answer | 2"
    chunks = sb.split_scan_book(spec("2"), pages(q, ms))
    assert sorted((c.metadata["source_type"], c.metadata["question_ref"]) for c in chunks) == [
        ("markscheme", "15M.2.HL.TZ2.3"), ("past_paper", "15M.2.HL.TZ2.3")]


def _figure_chunks():
    chunks = sb.split_scan_book(spec(), pages(MCQ, KEY))
    sb.assess(chunks, [], chunks)
    return chunks


FIG = {"doc_id": "book", "book_q": 7, "number": 14, "file": "book/p001_0.png", "kind": "diagram"}


def test_undescribed_diagram_holds_question_back():
    chunks = _figure_chunks()
    sb.apply_figures(chunks, [], [FIG], {})
    q = next(c for c in chunks if c.metadata["question_ref"].endswith(".14") and c.metadata["source_type"] == "past_paper")
    assert q.metadata["figures"] == ["book/p001_0.png"] and "figure_undescribed" in q.metadata["scan_flags"]
    other = next(c for c in chunks if c.metadata["question_ref"].endswith(".15") and c.metadata["source_type"] == "past_paper")
    assert "figures" not in other.metadata


def test_described_diagram_reaches_question_and_library_copy():
    chunks = _figure_chunks()
    same = Chunk(id="lib", text="[14N.1.HL.TZ0.14] x\nWhich reaction is exothermic?\nA. one\nB. two",
                 metadata=new_meta(source_type="past_paper", question_ref="14N.1.HL.TZ0.14", doc_id="lib", linked_ids=[]))
    stats = sb.apply_figures(chunks, [same], [FIG], {"book/p001_0.png": {"description": "Enthalpy profile, products below reactants."}})
    q = next(c for c in chunks if c.metadata["question_ref"].endswith(".14") and c.metadata["source_type"] == "past_paper")
    assert "[FIGURE: Enthalpy profile" in q.text and "figure_undescribed" not in q.metadata["scan_flags"]
    assert "[FIGURE: Enthalpy profile" in same.text and same.metadata["figures"] == ["book/p001_0.png"]
    assert stats["described_on_library_copy"] == 1


def test_match_checked_by_eye_overrides_automatic_one():
    chunks = _figure_chunks()
    sb.apply_figures(chunks, [], [FIG], {"book/p001_0.png": {"description": "Shared apparatus.", "book_q": 7, "numbers": [14, 15]}})
    q = [c for c in chunks if c.metadata["source_type"] == "past_paper"]
    assert all("[FIGURE: Shared apparatus.]" in c.text for c in q)


def test_table_crop_needs_no_description():
    chunks = _figure_chunks()
    sb.apply_figures(chunks, [], [{**FIG, "kind": "table"}], {})
    q = next(c for c in chunks if c.metadata["question_ref"].endswith(".14") and c.metadata["source_type"] == "past_paper")
    assert q.metadata["figures"] and "figure_undescribed" not in q.metadata["scan_flags"]


def test_figure_detector_on_drawn_shapes():
    import cv2
    import numpy as np
    from ingest import scan_figures as sf
    page = np.full((2339, 1654, 3), 255, np.uint8)
    cv2.line(page, (300, 1100), (300, 500), (0, 0, 0), 3)            # axis
    cv2.line(page, (300, 1100), (1100, 1100), (0, 0, 0), 3)          # axis
    cv2.ellipse(page, (700, 800), (300, 200), 0, 180, 360, (0, 0, 0), 3)   # a curve
    assert sf.find_figures(page, [])
    box = np.full((2339, 1654, 3), 255, np.uint8)                    # an empty answer box with dotted lines
    cv2.rectangle(box, (100, 500), (1500, 900), (0, 0, 0), 3)
    for y in (600, 700, 800):
        for x in range(150, 1450, 20):
            cv2.circle(box, (x, y), 1, (0, 0, 0), -1)
    assert sf.find_figures(box, []) == []


def test_stray_topic_footer_is_removed():
    q = MCQ.replace("D. four\n", "D. four\nTopic Chem 5 4\n")
    chunks = sb.split_scan_book(spec(), pages(q, KEY))
    assert not any("Topic Chem" in c.text for c in chunks)
    assert sb.options_ok(next(c for c in chunks if c.metadata["question_ref"].endswith(".14")).text.split("\n", 1)[1])


def test_book_answer_letter_does_not_shift_library_question_tag():
    from ingest.classify import _text_for
    book = Chunk(id="b", text="[MARKSCHEME x]\nB", metadata=new_meta(scan_book=True))
    own = Chunk(id="m", text="library markscheme", metadata=new_meta())
    lib_q = Chunk(id="q", text="library question", metadata=new_meta(linked_ids=["b", "m"]))
    text = _text_for(lib_q, {"b": book, "m": own, "q": lib_q})
    assert "library markscheme" in text and "MARKSCHEME x" not in text
    book_q = Chunk(id="bq", text="book question", metadata=new_meta(scan_book=True, linked_ids=["b"]))
    assert "MARKSCHEME x" in _text_for(book_q, {"b": book, "bq": book_q})


def test_specimen_label_variants():
    for rest in ("2016/s/TZoSP/Paper 2 Section A/Higher Level/Q7/", "2016/s/TZ0SP/Paper 2/Higher Level/"):
        h = sb.parse_header(f"Topic Chem 1 Q# 15/ IB Chem/{rest}", "2")
        assert (h["session"], h["variant"], h["paper"]) == ("EXM", "TZ0", "2")


def test_garbled_header_takes_next_q_number_and_is_held_back():
    q = ("Topic Chem 5 Q# 82/ IB Chem/2018/w/TZ 0/Paper 2/Higher Level/Q1/\nFirst question. [1]\n"
         "Topic 3. | 33/ IB Chem/2018/s/TZ 1/Paper 2/Higher Level/Q3/ www.SmashingScience.org :o) This question is about ethene. [2]")
    chunks = sb.split_scan_book(spec("2"), [Page(page=1, markdown=q, parser="local:marker")])
    c = next(x for x in chunks if x.metadata["question_ref"] == "18M.2.HL.TZ1.3")
    assert c.metadata["book_q"] == 83 and "ethene" in c.text
    assert "header_inferred" in sb.flags_for(c)


def test_structured_question_uses_header_number_over_table_rows():
    q = ("Topic Chem 5 Q# 8/ IB Chem/2018/w/TZ 0/Paper 2/Higher Level/Q5/\nThe results were:\n1. | 0.05 | 0.10\n2. | 0.10 | 0.20\n(b) State it. [1]")
    chunks = sb.split_scan_book(spec("2"), [Page(page=1, markdown=q, parser="local:marker")])
    assert [c.metadata["question_ref"] for c in chunks] == ["18N.2.HL.TZ0.5"]


def test_marker_flattening_leftover_commands():
    t = scan_ocr.flatten_markdown(r"$CH_2(g) \xrightarrow{\text{Step 1}} CH_3(g)$ and $\unknownthing x$")
    assert "\\" not in t and "→" in t and "Step 1" in t


def test_unread_header_recovers_reference_from_other_section():
    broken = MCQ.replace("2014/w/Time Zone 0", "2O14/w/Tme")
    chunks = sb.split_scan_book(spec(), pages(broken, KEY))
    assert {c.metadata["question_ref"] for c in chunks} == {"14N.1.HL.TZ0.14", "14N.1.HL.TZ0.15"}


def test_structured_rows_group_by_number():
    q = "Topic Chem 5 Q# 8/ IB Chem/2018/w/TZ 0/Paper 2/Higher Level/Q5/\n5. A question.\n(b) State it. [1]\n(c) Calculate it. [2]"
    ms = "Topic Chem 5 Q# 8/ IB Chem/2018/w/TZ 0/P2/Higher Level/\n5. | b | answer | 1\n5. | c | working | 2"
    chunks = sb.split_scan_book(spec("2"), pages(q, ms))
    m = next(c for c in chunks if c.metadata["source_type"] == "markscheme")
    assert m.metadata["question_ref"] == "18N.2.HL.TZ0.5"
    assert sb.marks_awarded(m.text.split("\n", 1)[1]) == 3 == sb.marks_claimed(chunks[0].text)


def test_options_check_catches_swallowed_question():
    good = "18. Which?\nA. one\nB. two\nC. three\nD. four"
    assert sb.options_ok(good)
    assert not sb.options_ok(good.replace("C. three\n", ""))
    assert not sb.options_ok(good + "\nWhat is the temperature rise?\nB. 278 K")
    assert not sb.options_ok(good + "\nWhat is the temperature rise when energy is supplied to water in a beaker? It is long.")


def test_marker_flattening_nested_units():
    t = scan_ocr.flatten_markdown(r"capacity $4.2 \mathrm{J g^{-1} K^{-1}}$")
    assert "mathrm" not in t and "J g-1 K-1" in t


def test_marker_flattening():
    t = scan_ocr.flatten_markdown(r"- A.  $NaCl(s) \rightarrow Na^{+}(g) + Cl^{-}(g)$ and $CO_2(g)$, $\Delta G^{\circ} = -4.7 \times 10^4 \text{ J}$, Fe <sup>2+</sup>")
    assert "NaCl(s) → Na+(g) + Cl-(g)" in t and "CO2(g)" in t and "10^4" in t and "Fe 2+" in t and t.startswith("A.")


def test_answer_key_joins_wrapped_headers_within_their_own_column():
    def box(t, x, y):
        return {"t": t, "c": .99, "x": x, "y": y}
    row = {"boxes": [box("T11 Q# 154/", 80, 100), box("IB/2019/s/TZ2/P1/HL/Page 12.", 80, 140), box("38.", 80, 190), box("B", 200, 190),
                     # a date in the next column at the same height must not attach to the first header
                     box("T11 Q# 160/ IB", 800, 95), box("Chem/2017/w/TZ0/P1/HL", 800, 135), box("39.", 800, 190), box("D", 920, 190)]}
    assert scan_ocr.rapid_text(row, True).splitlines() == [
        "T11 Q# 154/ IB/2019/s/TZ2/P1/HL/Page 12.", "38. B", "T11 Q# 160/ IB Chem/2017/w/TZ0/P1/HL", "39. D"]


def test_answer_key_columns_from_boxes():
    def box(t, x, y):
        return {"t": t, "c": .99, "x": x, "y": y}
    row = {"boxes": [box("Q# 7/ IB/Paper 1/2014/w/TZ0/HL", 80, 100), box("14.", 80, 150), box("B", 200, 152),
                     box("Q# 8/ IB/Paper 1/2013/w/TZ0/HL", 600, 100), box("3.", 600, 150), box("D", 720, 150)]}
    assert scan_ocr.rapid_text(row, True).splitlines() == ["Q# 7/ IB/Paper 1/2014/w/TZ0/HL", "14. B", "Q# 8/ IB/Paper 1/2013/w/TZ0/HL", "3. D"]


# ---------------- planted errors: each check must catch its own ----------------
def test_planted_power_of_ten():
    good = "ΔG = -8.31 J K-1 mol-1 × 1000 K × ln 280\nΔG = -4.7 × 10^4 J"
    assert sb.arithmetic_issues(good) == []
    assert sb.arithmetic_issues(good.replace("10^4", "10^2"))
    assert sb.arithmetic_issues(good.replace("8.31", "3.31"))


def test_planted_formula_errors():
    assert sb.equation_issues("H2(g) + Cl2(g) → 2HCl(g)") == []
    assert sb.equation_issues("NaCl(s) → Na+(g) + Cl-(g)") == []
    assert sb.equation_issues("CaCO3(s) → CaO(s) + CO2(g)") == []
    assert sb.equation_issues("H2(g) + Cl12(g) → 2HCl(g)")
    assert sb.equation_issues("H2(g) + Cl2(g) → 2HC1(g)")
    assert sb.equation_issues("C2H4(g) + H2(g) → C2H8(g)")


def _lib_key(ref, letter):
    return Chunk(id="lib" + ref, text=f"[MARKSCHEME {ref}] x\n{letter}",
                 metadata=new_meta(source_type="markscheme", question_ref=ref, doc_id="lib", linked_ids=[]))


def test_planted_wrong_answer_is_caught_and_library_wins():
    chunks = sb.split_scan_book(spec(), pages(MCQ, KEY))
    kept, report = sb.merge_with_library(chunks + [_lib_key("14N.1.HL.TZ0.14", "D")], chunks)
    assert report["checks"]["key_library_conflict"] == 1
    assert not any(c.metadata.get("scan_book") and c.metadata["source_type"] == "markscheme"
                   and c.metadata["question_ref"].endswith(".14") for c in kept)   # book copy dropped, library copy kept


def test_grades():
    assert sb._grade(["key_conflict"]) == "red"
    assert sb._grade(["ref_conflict", "rapid_only"]) == "red"
    assert sb._grade(["rapid_only"]) == "amber"
    assert sb._grade([]) == "green"


def test_planted_missing_option_and_two_engines():
    broken = MCQ.replace("C. three\n", "")
    chunks = sb.split_scan_book(spec(), pages(broken, KEY))
    sb.assess(chunks, [], chunks)
    assert "bad_options" in next(c for c in chunks if c.metadata["question_ref"].endswith(".14")).metadata["scan_flags"]

    ms = "Topic Chem 5 Q# 8/ IB Chem/2018/w/TZ 0/P2/Higher Level/\n5. | c | value is 4.7 × 10^4 J | 2"
    q = "Topic Chem 5 Q# 8/ IB Chem/2018/w/TZ 0/Paper 2/Higher Level/Q5/\n5. Calculate it. [2]"
    marker = sb.split_scan_book(spec("2"), pages(q, ms))
    rapid = sb.split_scan_book(spec("2"), pages(q, ms.replace("10^4", "10²"), parser="local:rapidocr"))
    sb.assess(marker, [], rapid)
    assert "engines_disagree" in next(c for c in marker if c.metadata["source_type"] == "markscheme").metadata["scan_flags"]


def test_rapid_only_and_figure_are_held_back():
    chunks = sb.split_scan_book(spec(), pages(MCQ.replace("Which reaction is exothermic?", "What does the diagram show?"), KEY, parser="local:rapidocr"))
    sb.assess(chunks, [], None)
    q = next(c for c in chunks if c.metadata["question_ref"].endswith(".14") and c.metadata["source_type"] == "past_paper")
    assert {"rapid_only", "needs_figure"} <= set(q.metadata["scan_flags"])


def test_damaged_library_text_is_repaired_only_by_same_question():
    chunks = sb.split_scan_book(spec(), pages(MCQ, KEY))
    damaged = Chunk(id="old", text="[14N.1.HL.TZ0.15] x\nWhich value is largest?\nCO ( g) → CO ( s)\n2 2\nA. 1.5\nB. 2.5",
                    metadata=new_meta(source_type="past_paper", question_ref="14N.1.HL.TZ0.15", doc_id="lib", linked_ids=[]))
    other = Chunk(id="other", text="[14N.1.HL.TZ0.14] x\nDescribe titration colours entirely unrelated\nCO ( g)\n2 2",
                  metadata=new_meta(source_type="past_paper", question_ref="14N.1.HL.TZ0.14", doc_id="lib", linked_ids=[]))
    kept, report = sb.merge_with_library(chunks + [damaged, other], chunks)
    ids = {c.id for c in kept}
    assert "old" not in ids and "other" in ids
    assert report["merge"]["question_repairs_library"] == 1 and report["merge"]["question_wording_differs"] == 1


def test_correction_clears_flags(tmp_path):
    chunks = sb.split_scan_book(spec(), pages(MCQ, KEY, parser="local:rapidocr"))
    sb.assess(chunks, [], None)
    f = tmp_path / "fix.jsonl"
    f.write_text('{"doc_id":"book","book_q":7,"number":14,"kind":"markscheme","text":"A"}\n', encoding="utf-8")
    assert sb.apply_corrections(chunks, f) == 1
    m = next(c for c in chunks if c.metadata["source_type"] == "markscheme" and c.metadata["question_ref"].endswith(".14"))
    assert m.metadata["mcq_answer"] == "A" and m.metadata["scan_flags"] == []


def session_pages():
    from ingest.parsers import Page
    return [
        Page(page=1, markdown="Topic 5 HIGHER Level"),
        Page(page=2, markdown="IB HL 5 EQ Paper 2 s99 to s13 incl W\nHL SECTION A 11w\n1. (a) Define enthalpy. [2]\nPage 2 of 9\nPB"),
        Page(page=3, markdown="HL B 12s\n6\n(d) Calculate Q. [2]\nHL SECTION A.99w\n2. Too old."),
        Page(page=4, markdown="Mark Scheme\nHL SECTION A 11w\n1. (a) heat at constant pressure; [2]"),
        Page(page=5, markdown="HL B 12s\n6. (d) 42 kJ; [2]\nHL SECTION A.99w\n2. old answer"),
    ]


def test_session_headers_become_refs_and_pair_with_their_markschemes():
    from ingest import scan_books as sb
    blocks = sb._session_blocks(session_pages(), "2", 4)
    assert [(b["kind"], b["session"], b["variant"]) for b in blocks] == [
        ("q", "11N", "TZ0"), ("q", "12M", ""), ("q", None, ""), ("ms", "11N", "TZ0"), ("ms", "12M", ""), ("ms", None, "")]
    assert [b["q"] for b in blocks] == [1, 2, 3, 1, 2, 3]
    assert all("Page 2" not in l and l != "PB" for b in blocks for _p, l in b["lines"])


def test_session_book_takes_each_code_from_the_checked_table():
    from types import SimpleNamespace
    from ingest import scan_books as sb
    table = {"1": "11N.2.HL.TZ0.1", "2": "12M.2.HL.TZ2.6"}
    spec = SimpleNamespace(doc_id="t5", origin="book", scan={"paper": "2", "ms_start": 4, "headers": "session", "topic_pages": [1, 1, 1, 1, 2], "refs": table})
    chunks = sb.split_scan_book(spec, session_pages())
    found = sorted((c.metadata["source_type"], c.metadata["question_ref"]) for c in chunks)
    assert found == [("markscheme", "11N.2.HL.TZ0.1"), ("markscheme", "12M.2.HL.TZ2.6"), ("past_paper", "11N.2.HL.TZ0.1"), ("past_paper", "12M.2.HL.TZ2.6")]
    body = next(c.text for c in chunks if c.metadata["source_type"] == "past_paper" and "12M" in c.metadata["question_ref"])
    assert "\n6\n" not in body and "(d) Calculate Q" in body
    spec.scan["refs"] = {"1": "11N.2.HL.TZ0.1"}
    assert {c.metadata["question_ref"] for c in sb.split_scan_book(spec, session_pages())} == {"11N.2.HL.TZ0.1"}


def test_last_question_on_the_page_where_markschemes_start_stays_a_question():
    from ingest import scan_books as sb
    from ingest.parsers import Page
    pages = [Page(page=1, markdown="HL B 00s"), Page(page=2, markdown="7. The enthalpy diagram.\nIB HL 5 EQ Paper 2 Mark Scheme\nHL SECTION A 11w\n1. (a) answer;")]
    blocks = sb._session_blocks(pages, "2", 2)
    assert [(b["kind"], [l for _p, l in b["lines"]]) for b in blocks] == [("q", ["7. The enthalpy diagram."]), ("ms", ["1. (a) answer;"])]
