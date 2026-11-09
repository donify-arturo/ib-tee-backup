"""The attempt log, when question types come back, fresh questions, and how a session is mixed."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import study_plan as sp  # noqa: E402
from card_ui import split_options  # noqa: E402

TODAY = date(2026, 11, 10)
KEY = ("R1.1", "Calorimetry: find molar enthalpy change")


def attempt(day, correct=True, sure=True, key=KEY, ref="x", **extra):
    return {"id": f"{day}{ref}", "day": str(day), "sub_topic": key[0], "question_type": key[1], "ref": ref, "correct": correct, "sure": sure, **extra}


def card(cid, qtype, ref, try_next=()):
    return {"card_id": cid, "walkthrough": {"question_type": qtype, "question_ref": ref, "try_next": list(try_next)}}


def test_log_appends_and_ignores_the_value_the_card_repeats(tmp_path):
    f = tmp_path / "attempts.jsonl"
    v = {"id": "a1", "answer": "B", "correct": True, "sure": True, "help": {}}
    item = {"sub_topic": "R1.1", "question_type": "T", "ref": "r", "card_id": "c"}
    assert sp.log_attempt(v, item, f) is True and sp.log_attempt(v, item, f) is False
    assert sp.log_attempt({"id": "a2", "correct": False}, item, f) is True
    rows = sp.load_attempts(f)
    assert [r["id"] for r in rows] == ["a1", "a2"] and rows[0]["question_type"] == "T" and rows[0]["day"]
    assert sp.log_attempt(None, item, f) is False


def test_a_half_written_line_does_not_lose_the_log(tmp_path):
    f = tmp_path / "attempts.jsonl"
    f.write_text('{"id": "a1"}\n{"id": "a', encoding="utf-8")
    assert [r["id"] for r in sp.load_attempts(f)] == ["a1"]


def test_logging_keeps_existing_lines(tmp_path):
    f = tmp_path / "attempts.jsonl"
    f.write_text(json.dumps({"id": "old"}) + "\n", encoding="utf-8")
    sp.log_attempt({"id": "new"}, {}, f)
    assert [r["id"] for r in sp.load_attempts(f)] == ["old", "new"]


def test_outcome_counts_only_sure_unaided_success_as_solid():
    assert sp.outcome({"correct": True, "sure": True, "help": {"chips": ["5_time_efficiency", "6_data_booklet"]}}) == "solid"
    assert sp.outcome({"correct": True, "sure": False}) == "shaky"
    assert sp.outcome({"correct": True, "sure": True, "help": {"hints": 1}}) == "shaky"
    assert sp.outcome({"correct": True, "sure": True, "help": {"crossed": 2}}) == "shaky"
    assert sp.outcome({"correct": True, "sure": True, "help": {"chips": ["3_novel_application"]}}) == "shaky"
    assert sp.outcome({"correct": False, "sure": True}) == "miss"
    assert sp.outcome({"correct": False, "revealed": True}) == "miss"
    assert sp.outcome({"correct": True, "self": "all", "sure": None}) == "solid"
    assert sp.outcome({"correct": False, "self": "some", "sure": None}) == "shaky"


def test_gap_scales_with_the_time_left():
    assert sp.gap_days(7) == 3 and sp.gap_days(35) == 8 and sp.gap_days(70) == 12
    assert sp.gap_days(2) == 1 and sp.gap_days(500) == 21
    assert sp.gap_days(None) == sp.DEFAULT_GAP and sp.gap_days(0) == sp.AFTER_EXAM_GAP


def test_miss_comes_back_tomorrow_and_solid_after_a_gap():
    exam = TODAY + timedelta(days=35)
    assert sp.type_states([attempt(TODAY, correct=False)], exam)[KEY]["due"] == TODAY + timedelta(days=1)
    s = sp.type_states([attempt(TODAY)], exam)[KEY]
    assert s["due"] == TODAY + timedelta(days=8) and s["streak"] == 1
    assert sp.type_states([attempt(TODAY, sure=False)], exam)[KEY]["due"] == TODAY + timedelta(days=4)


def test_only_the_first_attempt_of_a_day_counts_and_a_miss_resets_the_streak():
    day2 = TODAY + timedelta(days=1)
    s = sp.type_states([attempt(TODAY), attempt(TODAY, correct=False, ref="y"), attempt(day2)], None)[KEY]
    assert s["sessions"] == 2 and s["streak"] == 2
    assert sp.type_states([attempt(TODAY), attempt(day2, correct=False)], None)[KEY]["streak"] == 0


def test_last_look_falls_before_the_exam():
    exam = TODAY + timedelta(days=4)
    assert sp.type_states([attempt(TODAY)], exam)[KEY]["due"] <= exam - timedelta(days=1)


def test_changing_the_exam_date_replans_without_touching_the_log():
    log = [attempt(TODAY)]
    assert sp.type_states(log, TODAY + timedelta(days=7))[KEY]["due"] != sp.type_states(log, TODAY + timedelta(days=70))[KEY]["due"]


def run_of_solids(gaps=(5, 5), refs=("a", "b", "c"), mixed=(False, True, False)):
    days = [TODAY - timedelta(days=sum(gaps))]
    for g in gaps:
        days.append(days[-1] + timedelta(days=g))
    return [attempt(d, ref=r, mixed=m) for d, r, m in zip(days, refs, mixed)]


def status(log, available=3, exam=None, today=TODAY):
    return sp.mastery(sp.type_states(log, exam).get(KEY), available, exam, today)


def test_mastered_is_earned_by_three_unaided_days_with_gap_variety_and_mixing():
    m = status(run_of_solids())
    assert m["status"] == "mastered" and m["done"] == 3 and m["needs"] == []
    assert m["check"] == TODAY + timedelta(days=sp.DEFAULT_GAP)
    assert sp.mastery_label(m) == "Mastered · check 17 Nov"


def test_new_and_practising_labels():
    assert status([])["status"] == "new" and sp.mastery_label(status([])) == "New"
    m = status(run_of_solids()[:2])
    assert m["status"] == "practising" and sp.mastery_label(m) == "Practising 2/3"


def test_mastered_needs_each_part_of_the_rule():
    assert "one more after a 3-day gap" in status(run_of_solids(gaps=(5, 1)))["needs"]
    assert "one in a Today session" in status(run_of_solids(mixed=(False, False, False)))["needs"]
    assert "a different question" in status(run_of_solids(refs=("a", "a", "a")))["needs"]
    label = sp.mastery_label(status(run_of_solids(mixed=(False, False, False))))
    assert label == "Practising 3/3 · needs one in a Today session"


def test_a_type_with_only_one_question_can_still_be_mastered():
    assert status(run_of_solids(refs=("a", "a", "a")), available=1)["status"] == "mastered"


def test_help_or_doubt_does_not_count_and_a_miss_restarts():
    log = run_of_solids()
    log[2]["sure"] = False
    assert status(log)["status"] == "practising" and status(log)["done"] == 2
    log = run_of_solids()
    log.append(attempt(TODAY + timedelta(days=1), correct=False, ref="d"))
    assert status(log, today=TODAY + timedelta(days=1))["done"] == 0
    assert status(log, today=TODAY + timedelta(days=1))["status"] == "practising"


def test_mastered_lapses_when_a_check_is_left_too_long():
    due = TODAY + timedelta(days=sp.DEFAULT_GAP)
    assert status(run_of_solids(), today=due + timedelta(days=sp.DEFAULT_GAP))["status"] == "mastered"
    late = status(run_of_solids(), today=due + timedelta(days=sp.DEFAULT_GAP + 1))
    assert late["status"] == "practising" and "long overdue" in late["needs"][0]


def test_questions_available_counts_own_and_clean_fresh_questions():
    cards = [card("a", "T", "own", ["v1", "v2", "bad"]), card("b", "T", "own2", ["v1"])]
    assert sp.questions_for(cards, {"v1": {}, "v2": {}}, set()) == 4
    assert sp.questions_for(cards, {"v1": {}, "v2": {}}, {"v2"}) == 3


def test_due_lists_fewest_returns_first_and_skips_what_was_done_today():
    types = {KEY: [], ("R1.2", "A"): [], ("R1.2", "B"): [], ("R1.2", "New"): []}
    states = {KEY: {"sessions": 3, "due": TODAY, "last": TODAY - timedelta(days=5)},
              ("R1.2", "A"): {"sessions": 1, "due": TODAY, "last": TODAY - timedelta(days=5)},
              ("R1.2", "B"): {"sessions": 1, "due": TODAY, "last": TODAY}}
    due, new = sp.split_due(types, states, TODAY)
    assert due == [("R1.2", "A"), KEY] and new == [("R1.2", "New")]


def test_clean_variant_needs_key_options_and_no_missing_figure():
    q = {"ref": "r", "question": "14. Which is right?\nA. 1\nB. 2\nC. 3\nD. 4", "mcq_answer": "C"}
    v = sp.clean_variant(q, False, split_options)
    assert v["stem"] == "Which is right?" and v["correct"] == "C" and len(v["options"]) == 4
    assert sp.clean_variant({**q, "mcq_answer": None}, False, split_options) is None
    assert sp.clean_variant({**q, "question": "Which is right?"}, False, split_options) is None
    pictured = {**q, "question": "What does the graph show?\nA. 1\nB. 2\nC. 3\nD. 4"}
    assert sp.clean_variant(pictured, False, split_options) is None and sp.clean_variant(pictured, True, split_options)
    assert sp.clean_variant({**q, "question": "Which?\nA. 1\nB. 1\nC. 3\nD. 4"}, False, split_options) is None


def test_garbled_questions_are_refused_and_leftovers_are_tidied():
    good = {"ref": "r", "mcq_answer": "A"}
    opts = "\nA. one\nB. two\nC. three\nD. four"
    lost = [
        "Which is formation?\nA. C(g) + 2H ( g) → X\nB. two\nC. three\nD. four",
        "Which is combustion?\nA. C H (l) → X\nB. two\nC. three\nD. four",
        "Which is formation?\nA. H O(l)\nB. two\nC. three\nD. four",
        "Which gives ∆HÖ of a compound?" + opts,
        "Which is right?\nA. This sentence is complete and ends here.\nB. So does this complete one too here.\nC. And so does this complete one here.\nD. But this last one stops at a pressure of 100",
        "Which step?\nA. Step X: first; Step\nB. two\nC. three\nD. four",
    ]
    for text in lost:
        assert sp.clean_variant({**good, "question": text}, False, split_options) is None, text
    v = sp.clean_variant({**good, "question": "Pick one in kJ mol\nr\n:--- :---\nSame line\nSame line\nA. one</p>\nB. two\nC. three\nD. four"}, False, split_options)
    assert v["stem"] == "Pick one in kJ mol\nSame line" and v["options"][0]["text"] == "one"
    assert sp.clean_variant({**good, "ref": "09N.1.HL.TZ0.15", "question": "Pick." + opts}, False, split_options) is None


def test_a_stem_starting_with_a_decimal_keeps_its_number():
    good = {"ref": "r", "mcq_answer": "A"}
    opts = "\nA. one\nB. two\nC. three\nD. four"
    assert sp.clean_variant({**good, "question": "1.0 g of salt dissolves. Which?" + opts}, False, split_options)["stem"].startswith("1.0 g")
    assert sp.clean_variant({**good, "question": "14. Which?" + opts}, False, split_options)["stem"] == "Which?"
    assert sp.clean_variant({**good, "ref": "17N.1.HL.TZ0.20", "question": "Which?" + opts}, False, split_options) is None


def test_new_types_spread_across_families_instead_of_the_first_alphabetically():
    calorimetry = [card(f"c{i}", f"Calorimetry: {i}", f"rc{i}") for i in range(8)]
    decks = {"R1.1": {"cards": calorimetry}, "R1.2": {"cards": [card("h", "Hess's law: x", "rh"), card("b", "Identify the lattice enthalpy equation", "rb")]}}
    s = sp.build_session(decks, {}, [], {"exam": None, "topics": ["R1.1", "R1.2"], "size": 4, "hidden": []}, TODAY)
    assert sum(x["question_type"].startswith("Calorimetry") for x in s) == 2 and {x["sub_topic"] for x in s} == {"R1.1", "R1.2"}


def test_question_starts_with_the_card_then_goes_fresh_then_oldest():
    c = card("c1", "T", "own", ["v1", "v2", "missing"])
    variants = {"v1": {"ref": "v1"}, "v2": {"ref": "v2"}}
    assert sp.pick_question([c], variants, [], set(), set())["ref"] == "own"
    seen = [{"card_id": "c1", "ref": "own", "day": "2026-11-01"}]
    p = sp.pick_question([c], variants, seen, set(), set())
    assert p["ref"] == "v1" and p["variant"] == {"ref": "v1"} and p["seen_before"] is False
    all_seen = seen + [{"ref": "v1", "day": "2026-11-03"}, {"ref": "v2", "day": "2026-11-02"}]
    p = sp.pick_question([c], variants, all_seen, set(), set())
    assert p["ref"] == "own" and p["seen_before"] is True


def test_hidden_and_already_used_questions_are_skipped_but_a_type_never_comes_up_empty():
    c = card("c1", "T", "own", ["v1"])
    variants = {"v1": {"ref": "v1"}}
    assert sp.pick_question([c], variants, [{"card_id": "c1", "ref": "own", "day": "2026-11-01"}], {"v1"}, set())["ref"] == "own"
    assert sp.pick_question([c], variants, [], set(), {"c1"})["ref"] == "v1"
    assert sp.pick_question([c], variants, [], {"v1"}, {"c1"})["ref"] == "own"


def test_cards_sharing_one_past_paper_question_stay_separate():
    a, b = card("a", "Type A", "same"), card("b", "Type B", "same")
    log = [{"card_id": "a", "ref": "same", "day": "2026-11-01"}]
    p = sp.pick_question([b], {}, log, set(), {"a"})
    assert p["uid"] == "b" and p["seen_before"] is False
    decks = {"R1.2": {"cards": [a, b]}}
    s = sp.build_session(decks, {}, [], {"exam": None, "topics": ["R1.2"], "size": 5, "hidden": []}, TODAY)
    assert sorted(x["uid"] for x in s) == ["a", "b"]


def test_mix_keeps_confusable_neighbours_and_uses_every_type_once():
    keys = [("R1.2", "Enthalpy change from combustion data"), ("R1.2", "Enthalpy change from formation data"), ("R1.1", "Calorimetry: a"),
            ("R1.1", "Calorimetry: b"), ("R1.1", "Calorimetry: c"), ("R1.2", "Hess's law: x"), ("R1.2", "Born-Haber: y")]
    out = sp.mix(keys, "2026-11-10")
    assert sorted(out) == sorted(keys) and out == sp.mix(keys, "2026-11-10")
    assert abs(out.index(keys[0]) - out.index(keys[1])) == 1
    assert sp.family("Bond enthalpy: calculate ΔH") == "direction" and sp.family("Identify the lattice enthalpy equation") == "which equation"


def test_session_puts_due_before_new_and_respects_size_and_topics():
    decks = {"R1.1": {"cards": [card("a", "Calorimetry: a", "ra"), card("b", "Calorimetry: b", "rb"), card("c", "Calorimetry: c", "rc")]},
             "S1.2": {"cards": [card("s", "Other", "rs")]}}
    log = [attempt(TODAY - timedelta(days=3), correct=False, key=("R1.1", "Calorimetry: b"), ref="rb")]
    plan = {"exam": None, "topics": ["R1.1"], "size": 2, "hidden": []}
    s = sp.build_session(decks, {}, log, plan, TODAY)
    assert len(s) == 2 and ("Calorimetry: b" in [x["question_type"] for x in s]) and all(x["sub_topic"] == "R1.1" for x in s)


def test_plan_defaults_and_saving(tmp_path):
    f = tmp_path / "plan.json"
    assert sp.load_plan(f)["exam"] is None and sp.load_plan(f)["topics"] == ["R1.1", "R1.2"]
    sp.save_plan({**sp.load_plan(f), "exam": "2026-12-01"}, f)
    assert sp.load_plan(f)["exam"] == "2026-12-01" and not list(tmp_path.glob("*.tmp"))
