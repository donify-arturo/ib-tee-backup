"""Foundations builder: prompt assembly and the checks on its output. No Claude call is made."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import foundations_builder as fb  # noqa: E402

CHAPTER = {"code": "R1.1", "pages": [{"printed": "395", "text": "A 1.15 g sample of anhydrous lithium chloride was added to water inside a coffee cup calorimeter and warmed the water by 3.80 K."},
                                     {"printed": "396", "text": "Practice questions"}],
           "answers": [{"kind": "practice questions", "page": "396", "text": ")\n1. -14.6 kJ mol-1"}]}
CODES = {"R1.1.1", "R1.1.2", "R1.1.3", "R1.1.4"}


def test_clean_item_has_no_issues():
    result = {"practice": [{"page": "396", "understanding": "R1.1.3", "question": "Find dH when 1.15 g of LiCl heats water by 3.80 K."}],
              "worked": [], "investigations": [{"source": "guide", "page": "", "understanding": "R1.1.3", "tag": "Tool 1", "prompt": "x", "model_answer": ["y"]}]}
    assert fb.check(result, CODES, CHAPTER) == []


def test_flags_wrong_page_unknown_code_and_invented_numbers():
    result = {"practice": [{"page": "500", "understanding": "R1.9.9", "question": "Heat 75.0 g of water."}], "worked": [], "investigations": []}
    issues = fb.check(result, CODES, CHAPTER)
    assert any("page not in this chapter" in i for i in issues)
    assert any("unknown understanding" in i for i in issues)
    assert any("numbers not on the cited page" in i for i in issues)


def test_flags_copied_wording():
    result = {"practice": [], "investigations": [],
              "worked": [{"page": "395", "understanding": "R1.1.3", "problem": "Some anhydrous lithium chloride was added to water inside a coffee cup calorimeter and warmed the water by 3.80 K."}]}
    assert any("copies the book" in i for i in fb.check(result, CODES, CHAPTER))


def test_answer_booklet_text_drops_the_stray_bracket():
    assert fb.answers_text(CHAPTER).startswith("[practice questions on page 396]\n1. -14.6")


def test_real_chapter_prompt_builds_for_r1_2():
    ch = fb.chapter("R1.2")
    assert ch and ch["pages"] and ch["answers"]
    assert "[page " in fb.pages_text(ch)


def test_prepared_items_are_checked_against_their_own_pages():
    prep = {"pages": [{"printed": "97", "text": "Problem 4: 50.0 cm3 of 1.00 mol dm-3 copper sulfate"}], "answers": "73 C at t = 100 s"}
    good = {"practice": [{"source": "prepared", "page": "97", "understanding": "R1.1.4", "question": "50.0 cm3, 1.00 mol dm-3; reading 73 C."}]}
    bad = {"practice": [{"source": "prepared", "page": "395", "understanding": "R1.1.4", "question": "x"}]}
    assert fb.check(good, CODES, CHAPTER, prep) == []
    assert any("page not in this chapter" in i for i in fb.check(bad, CODES, CHAPTER, prep))
    assert any("isn't in the library" in i for i in fb.check(good, CODES, CHAPTER, None))


def test_past_paper_reprints_are_separated_from_book_questions():
    library = [("19M.1.HL.TZ1.14", *fb._fingerprint("When equal masses of X and Y absorb the same amount of energy, their temperatures "
                                                     "rise by 5 C and 10 C respectively. Which is correct? specific heat capacity")),
               ("25M.1A.HL.6219.21", *fb._fingerprint("Burning 0.321 g of methanol warms 200 cm3 of water by 5.00 K; c = 4.18 J g-1 K-1"))]
    result = {"practice": [
        {"source": "companion", "page": "394", "question": "Equal masses of X and Y absorb the same energy; X rises by 5 C and Y by 10 C. "
                                                           "Which is correct about their specific heat capacity?"},
        {"source": "companion", "page": "394", "question": "Using c = 4.18 kJ kg-1 K-1, find the energy to warm 1 kg of water by 1 K."}],
        "worked": []}
    assert fb.mark_past_papers(result, library) == 1
    assert result["practice"][0]["past_paper_ref"] == "19M.1.HL.TZ1.14"
    assert result["practice"][1]["past_paper_ref"] == ""                   # a shared constant is no evidence


def test_formula_digits_are_not_numbers():
    numbers, _ = fb._fingerprint("4NH3(g) + 5O2(g) -> 4NO(g) + 6H2O(l), ΔH = −905 kJ")
    assert numbers == {"905"}
