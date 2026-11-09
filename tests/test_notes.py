"""Notes: saving from a card, writing by hand, grouping by question type, and surviving a deck rebuild."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import notes  # noqa: E402

CARD = {"card_id": "R1.2-T01", "title": "Born-Haber cycles",
        "walkthrough": {"question_type": "Born-Haber: find lattice enthalpy", "careful": "Don't copy the printed sign.",
                        "question_ref": "17M.1.HL.TZ2.16",
                        "steps": {"5_time_efficiency": {"workflow": ["Find the target arrow", "Flip the one against you", "Eliminate"]}}}}


def test_card_gives_type_steps_and_careful():
    e = notes.from_card(CARD, "R1.2")
    assert e["question_type"] == "Born-Haber: find lattice enthalpy"
    assert e["steps"] == ["Find the target arrow", "Flip the one against you", "Eliminate"]
    assert e["careful"] == "Don't copy the printed sign." and e["sub_topic"] == "R1.2"
    assert notes.from_card({"card_id": "x", "title": "No steps at all"}, "R3.1") is None


def test_note_keeps_the_procedure_and_the_tricks_and_they_can_be_searched():
    card = copy.deepcopy(CARD)
    card["walkthrough"].update(procedure=["Read each peak", "Multiply by its fraction"], tricks=["Ar sits nearer the tallest peak"])
    e = notes.from_card(card, "S1.2")
    assert e["steps"] == ["Read each peak", "Multiply by its fraction"] and e["tricks"] == ["Ar sits nearer the tallest peak"]
    data = {"items": {}}
    notes.add(data, e)
    assert "S1.2" in notes.grouped(data, search="tallest peak")
    old_note = {"items": {"x": {"sub_topic": "R1.1", "question_type": "Old", "steps": ["One"]}}}
    assert "R1.1" in notes.grouped(old_note)


def test_rebuilt_deck_reusing_a_card_id_cannot_overwrite_or_claim_an_old_note():
    data = {"items": {}}
    old = notes.from_card(CARD, "R1.2")
    first = notes.add(data, old)
    rebuilt = copy.deepcopy(CARD)
    rebuilt["walkthrough"]["question_type"] = "Bond enthalpy: calculate"
    entry = notes.from_card(rebuilt, "R1.2")
    assert notes.saved_id(data, entry) is None and notes.saved_id(data, old) == first
    second = notes.add(data, entry)
    assert second != first and data["items"][first]["question_type"] == "Born-Haber: find lattice enthalpy"
    assert notes.saved_id(data, entry) == second
    assert notes.add(data, entry) == second and len(data["items"]) == 2


def test_older_card_without_a_worked_question_can_still_be_saved():
    old = {"card_id": "R3.1-T01", "title": "pH vs pOH", "pillars": {"5_time_efficiency": {"workflow": ["pOH first", "Subtract from 14"]}}}
    e = notes.from_card(old, "R3.1")
    assert e["question_type"] == "pH vs pOH" and e["steps"] == ["pOH first", "Subtract from 14"] and e["careful"] == ""


def test_save_and_load_round_trip(tmp_path):
    f = tmp_path / "notes.json"
    assert notes.load(f) == {"items": {}}
    data = notes.load(f)
    nid = notes.add(data, notes.from_card(CARD, "R1.2"), hard=True)
    data["items"][nid]["note"] = "I always forget this −361"
    notes.save(data, f)
    again = notes.load(f)
    assert again["items"][nid]["hard"] is True and "−361" in again["items"][nid]["note"]
    assert not list(tmp_path.glob("*.tmp"))


def test_saved_note_keeps_its_copy_when_the_deck_is_rebuilt():
    data = {"items": {}}
    entry = notes.from_card(copy.deepcopy(CARD), "R1.2")
    nid = notes.add(data, entry)
    rebuilt = copy.deepcopy(CARD)
    rebuilt["walkthrough"]["steps"]["5_time_efficiency"]["workflow"] = ["Something else"]
    assert data["items"][nid]["steps"][0] == "Find the target arrow"


def test_own_note_needs_a_type_and_a_step():
    data = {"items": {}}
    assert notes.add_own(data, "R1.1", "  ", "A step") is None
    assert notes.add_own(data, "R1.1", "Calorimetry", " \n ") is None
    nid = notes.add_own(data, "R1.1", " Calorimetry ", "Find m\n\nUse q = mcΔT\n", "m is the water, not the fuel")
    assert data["items"][nid]["steps"] == ["Find m", "Use q = mcΔT"] and data["items"][nid]["question_type"] == "Calorimetry"
    assert data["items"][nid]["card_id"] is None


def test_grouped_by_sub_topic_and_type_with_hard_ones_first():
    data = {"items": {}}
    a = notes.add_own(data, "R1.2", "Hess cycles", "Easy step")
    b = notes.add_own(data, "R1.2", "Hess cycles", "Hard step")
    data["items"][b]["hard"] = True
    notes.add_own(data, "R1.1", "Calorimetry", "Other step")
    g = notes.grouped(data)
    assert list(g) == ["R1.1", "R1.2"]
    assert [nid for nid, _i in g["R1.2"]["Hess cycles"]] == [b, a]
    assert list(notes.grouped(data, sub_topic="R1.1")) == ["R1.1"]
    assert [nid for nid, _i in notes.grouped(data, only_hard=True)["R1.2"]["Hess cycles"]] == [b]
    assert list(notes.grouped(data, search="other step")) == ["R1.1"]
    assert notes.grouped(data, search="nothing like this") == {}
