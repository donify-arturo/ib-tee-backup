"""Grade boundary parsing, booklet clean-up, question headers, and the checks on generated notes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import reference as ref  # noqa: E402
from engine import reference_builder as rb  # noqa: E402

PAGE = """May 2019 subject report        Chemistry

Grade boundaries
Higher level overall
Grade:          1      2      3      4      5      6      7

Mark range:     0-15   16-26  27-39  40-51  52-63  64-75  76-100

Higher level and Standard level internal assessment
Grade:          1      2      3      4      5      6      7

Mark range:     0-3    4-6    7-10   11-13  14-16  17-19  20-24

Standard level paper three
Grade:          1      2      3      4      5      6      7

Mark range:     0-4    5-9    10 - 13   14 - 17   18 - 20   21 - 24   25 - 35
"""


def test_boundaries_are_read_with_session_level_and_component():
    rows = ref.parse_boundaries([PAGE])
    assert [(r["year"], r["month"], r["level"], r["component"]) for r in rows] == [
        (2019, "May", "HL", "Overall"), (2019, "May", "HL/SL", "Internal assessment"), (2019, "May", "SL", "Paper 3")]
    assert rows[0]["ranges"][-1] == "76–100" and rows[2]["ranges"][2] == "10–13" and len(rows[1]["ranges"]) == 7


def test_older_layouts_and_paper_sections_are_read():
    old = """SUBJECT REPORTS – NOV 2005
 Overall grade boundaries
 Higher Level
 Grade: 1 2 3 4 5 6 7
 Mark range: 0 16 17 29 30 42 43 53 54 64 65 75 76 100
 Standard level paper 1
 Component grade boundaries
 Grade: 1 2 3 4 5 6 7
 Mark range:
 0-7 8-12 13-17 18-20 21-23 24-26 27-30
 General comments
 Text 2 3
 """
    rows = ref.parse_boundaries([old])
    assert [(r["year"], r["month"], r["level"], r["component"]) for r in rows] == [(2005, "November", "HL", "Overall"), (2005, "November", "SL", "Paper 1")]
    assert rows[0]["ranges"][0] == "0–16" and rows[1]["ranges"][-1] == "27–30"
    sections = "May 2025 subject report  Chemistry TZ1\nHigher level paper one Section B\nGrade: 1 2 3 4 5 6 7\nMark range: 0-1 2-3 4-5 6-7 8-9 10-11 12-35"
    row = ref.parse_boundaries([sections])[0]
    assert row["component"] == "Paper 1B" and row["variant"] == "TZ1"


def test_session_carries_to_the_next_page_and_first_table_wins():
    rows = ref.parse_boundaries([PAGE, PAGE.replace("0-15", "0-99").replace("May 2019 subject report", "")])
    assert len(rows) == 3 and rows[0]["ranges"][0] == "0–15"


def test_booklet_text_loses_doubled_bold_and_odd_symbols():
    text = ref.clean_booklet_text("∆∆H ÖÖ // kkJJ mmooll−11\nllaattttiiccee\nLi 1049\nLi 1049\n(cid:3)")
    assert "lattice" in text and "⦵" in text and "Ö" not in text and text.count("Li 1049") == 1 and "cid" not in text
    assert ref.clean_booklet_text("Na 930 balloon") == "Na 930 balloon"


def test_real_booklet_sections_join_across_pages():
    sections = ref.booklet_sections()
    assert sections[16]["title"].startswith("Lattice enthalpies") and "930" in sections[16]["text"]
    assert list(sections) == sorted(sections) and len(sections) >= 20


def test_difficulty_only_when_a_figure_exists():
    assert ref.difficulty(80) == "Easy" and ref.difficulty("61") == "Standard" and ref.difficulty(30.0) == "Hard"
    assert ref.difficulty(None) is None and ref.difficulty("n/a") is None


def test_header_names_level_paper_and_marks_but_never_the_topic():
    h = ref.header(3, "25M.1A.HL.6207.24", 1, 40)
    assert h == {"number": 3, "tags": ["Past paper", "HL", "Paper 1A", "1 mark"], "difficulty": "Hard"}
    assert ref.header(1, "18M.2.HL.TZ2.5", 3)["tags"] == ["Past paper", "HL", "Paper 2", "3 marks"]
    assert ref.paper_of("14M.1.HL.TZ2.19") == "1A" and ref.paper_of("19M.3.HL.TZ1.2") == "1B" and ref.paper_of("25N.1B.HL.6208.2") == "1B"
    assert ref.header(1, "odd", 2)["tags"] == ["Past paper", "2 marks"] and ref.header(1, "odd", 2)["difficulty"] is None


def test_notes_check_flags_unknown_codes_length_and_copying():
    book = " ".join(f"word{i}" for i in range(30))
    good = {"notes": [{"heading": "Short", "understanding": "R1.1.1", "points": ["A plain point."]}],
            "definitions": [{"term": "Enthalpy", "definition": "Heat at constant pressure.", "must_say": [], "trap": ""}]}
    assert rb.check(good, {"R1.1.1"}, book) == []
    bad = {"notes": [{"heading": "Short", "understanding": "R9.9.9", "points": ["long " * 40, " ".join(f"word{i}" for i in range(12))]}],
           "definitions": [{"term": "X", "definition": "a", "must_say": [], "trap": ""}, {"term": "x", "definition": "b " * 40, "must_say": [], "trap": ""}]}
    text = " | ".join(rb.check(bad, {"R1.1.1"}, book))
    assert all(s in text for s in ("unknown understanding", "point too long", "copies the book", "repeated", "definition too long"))


def test_checked_questions_join_their_cards_type_and_never_repeat():
    deck = {"cards": [{"card_id": "R1.1-03", "walkthrough": {"try_next": ["a"]}}, {"card_id": "R1.1-04", "walkthrough": {}}]}
    extras = [{"ref": "b", "topic": "R1.1", "card": "R1.1-03"}, {"ref": "a", "topic": "R1.1", "card": "R1.1-03"},
              {"ref": "c", "topic": "R1.1", "card": None}, {"ref": "d", "topic": "R1.2", "card": "R1.1-03"}]
    ref.add_extras_to_deck(deck, "R1.1", extras)
    assert deck["cards"][0]["walkthrough"]["try_next"] == ["a", "b"] and deck["cards"][1]["walkthrough"] == {}


def test_every_checked_question_exists_with_clean_text_and_a_key():
    from analysis import evidence
    from card_ui import split_options
    import study_plan as sp
    extras = ref.extra_questions()
    assert len(extras) == 14
    for e in extras:
        q = next(x for x in evidence.build(e["source"])["questions"] if x["ref"] == e["ref"])
        assert sp.clean_variant(q, True, split_options), e["ref"]


def test_builder_skips_a_topic_without_book_pages_without_any_call(tmp_path, monkeypatch):
    monkeypatch.setattr(rb, "COMPANION", tmp_path)                 # no full-book chapters: only the excerpt is left
    monkeypatch.setattr(rb.book_pages, "__defaults__", (rb.BOOK, tmp_path))
    assert rb.build("S1.1") is None
    assert rb.book_pages("S1.1") == "" and len(rb.book_pages("R1.1")) > 1000


def test_builder_prefers_the_full_book_chapter():
    text = rb.book_pages("S1.1")
    assert "[page " in text and len(text) > 10000
