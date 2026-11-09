"""The interactive card's data: tappable options, tricks in the question, and nothing unsafe reaching the page."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from card_ui import TILES, card_data, remember_points, split_options, variant_data  # noqa: E402

QUESTION = "Pick one.\nA. first\nB. second\nC. third\nD. fourth"
STEP = {"short": "Basic line", "why": "The reason", "avoid": "A trap", "seconds": 5}


def card(question=QUESTION, answer="B: because"):
    steps = {key: dict(STEP) for key, _label in TILES}
    steps["7_elimination"]["definitely_wrong"] = [{"target": "A", "rule": "Wrong sign"}]
    steps["1_context"]["textbook_gap"] = "Books differ"
    return {"walkthrough": {"question_ref": "x", "question": question, "marks": 1, "key_idea": "The idea", "steps": steps,
                            "answer": answer, "try_next": []},
            "pillars": {"7_elimination": {"rules": ["Other rule"]}}, "evidence": [{"ref": "x", "note": "n"}]}


def test_options_split_only_when_all_four_exist():
    assert split_options(QUESTION)[0] == "Pick one."
    assert [o["letter"] for o in split_options(QUESTION)[1]] == list("ABCD")
    assert split_options("Explain this.\nA. only one")[1] == []


def test_all_seven_tricks_show_basic_line_and_keep_why_for_last():
    d = card_data(card(), Path("."), [])
    assert [t["label"] for t in d["tiles"]] == [label for _k, label in TILES] and len(d["tiles"]) == 7
    assert all(t["short"] == "Basic line" and t["why"] == "The reason" for t in d["tiles"])
    context = next(t for t in d["tiles"] if t["key"] == "1_context")
    assert ["Textbook gap", "Books differ"] in context["fields"]
    assert not any(k in {"short", "why"} for k, _v in context["fields"])


def test_wrong_option_carries_its_reason_and_correct_letter_is_known():
    d = card_data(card(), Path("."), [])
    assert d["correct"] == "B"
    assert d["options"][0]["why"] == "Wrong sign" and d["options"][1]["why"] == ""
    assert next(t for t in d["tiles"] if t["key"] == "7_elimination")["also"] == ["Other rule"]


def test_answer_giving_tricks_wait_until_the_question_is_answered():
    d = card_data(card(), Path("."), [])
    assert sorted(d["before"] + d["after"]) == sorted(k for k, _label in TILES)
    assert d["after"] == ["2_markscheme_logic", "1_context"] and "7_elimination" in d["before"]


def test_right_answer_is_never_crossed_out():
    c = card()
    c["walkthrough"]["steps"]["7_elimination"]["definitely_wrong"].append({"target": "B", "rule": "Bad rule"})
    assert card_data(c, Path("."), [])["options"][1]["why"] == ""


def test_elimination_rule_without_an_option_letter_stays_readable():
    c = card()
    c["walkthrough"]["steps"]["7_elimination"]["definitely_wrong"].append({"target": "A value above 100", "rule": "Not a percentage"})
    tile = next(t for t in card_data(c, Path("."), [])["tiles"] if t["key"] == "7_elimination")
    assert ["Definitely wrong", "A value above 100: Not a percentage"] in tile["fields"]


def test_time_and_booklet_buttons_say_something_before_a_tap():
    c = card()
    c["walkthrough"]["steps"]["6_data_booklet"]["sections"] = [1, 14]
    chips = {t["key"]: t["chip"] for t in card_data(c, Path("."), [])["tiles"]}
    assert chips["5_time_efficiency"] == "Time 5 s" and chips["6_data_booklet"] == "Data booklet §1, 14"
    assert chips["3_novel_application"] == "Disguise"


def test_command_term_can_be_tapped_in_the_stem():
    c = card("Calculate the enthalpy change.", "It is -10.")
    c["walkthrough"]["steps"]["4_command_terms"]["command_term"] = "calculate"
    assert card_data(c, Path("."), [])["stem_parts"] == ["", "Calculate", " the enthalpy change."]
    c["walkthrough"]["steps"]["4_command_terms"]["command_term"] = "none"
    assert card_data(c, Path("."), [])["stem_parts"] is None


def test_remember_points_come_from_the_workflow():
    c = card()
    c["walkthrough"]["steps"]["5_time_efficiency"]["workflow"] = ["Find the arrow", "Flip it"]
    assert card_data(c, Path("."), [])["remember"] == ["Find the arrow", "Flip it"]
    older = {"pillars": {"5_time_efficiency": {"workflow": ["Base? Find pOH first"]}}}     # decks without a worked question
    assert remember_points(older) == ["Base? Find pOH first"]
    assert remember_points({}) == []


def test_procedure_tricks_and_hints_reach_the_card_and_notes():
    c = card()
    c["walkthrough"].update(procedure=["Step one", "Step two"], tricks=["A trick"], if_lost=["A hint", "Another"])
    d = card_data(c, Path("."), [])
    assert d["procedure"] == ["Step one", "Step two"] and d["tricks"] == ["A trick"] and d["if_lost"] == ["A hint", "Another"]
    assert d["remember"] == ["Step one", "Step two"]


def test_older_card_without_a_procedure_still_works():
    d = card_data(card(), Path("."), [])
    assert d["procedure"] == [] and d["if_lost"] == []


def test_written_question_has_no_options_to_tap():
    d = card_data(card("Explain why the sign flips.", "It reverses."), Path("."), [])
    assert d["options"] == [] and d["correct"] is None and d["answer"] == "It reverses."


def test_card_data_travels_as_json_so_page_text_cannot_become_code():
    d = card_data(card("Pick </script><script>alert(1)</script> one."), Path("."), [])
    assert json.loads(json.dumps(d))["stem"].startswith("Pick")
    page = (Path(__file__).resolve().parents[1] / "card_component" / "index.html").read_text(encoding="utf-8")
    assert "__DATA__" not in page and "streamlit:componentReady" in page and "innerHTML" not in page


def test_question_without_a_related_card_still_shows():
    v = {"ref": "r", "stem": "Which?", "correct": "C", "options": [{"letter": x, "text": x} for x in "ABCD"]}
    d = variant_data(None, v, Path("."), [])
    assert d["correct"] == "C" and d["procedure"] == [] and d["if_lost"] == [] and d["tricks"] == []


def test_fresh_question_uses_its_own_key_and_the_parent_cards_method():
    c = card()
    c["walkthrough"].update(procedure=["Step one", "Step two"], tricks=["A trick"], key_idea="The idea")
    v = {"ref": "19N.1.HL.TZ0.14", "stem": "Which?", "correct": "C", "options": [{"letter": x, "text": x} for x in "ABCD"]}
    d = variant_data(c, v, Path("."), [])
    assert d["correct"] == "C" and d["ref"] == "19N.1.HL.TZ0.14" and d["tiles"] == [] and all(o["why"] == "" for o in d["options"])
    assert d["key_idea"] == ""      # it describes the parent's own question
    assert d["procedure"] == ["Step one", "Step two"] and d["if_lost"] == ["Step one", "Step two"] and d["tricks"] == ["A trick"]
