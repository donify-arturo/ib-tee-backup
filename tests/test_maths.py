"""Maths AI HL: data integrity, mastery rules, spaced repetition, error log, calendar, exams, bookmarks, and every page loading."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from ibtee import store, theme
from ingest import maths_tagging
from maths import data, exams, progress, schedule

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- data
def test_syllabus_has_78_subtopics_in_5_topics():
    assert [t["n"] for t in data.topics()] == [1, 2, 3, 4, 5]
    assert len(data.subtopics()) == 78
    for s in data.subtopics():
        assert s["recall"] and s["objectives"] and s["method"], s["code"]
        assert all(data.subtopic(c) for c in s["connections"])


def test_question_bank_is_consistent():
    qs = data.questions()
    assert len(qs) > 300
    assert len({q["id"] for q in qs}) == len(qs)
    for q in qs:
        assert q["parts"] and q["q_spans"], q["id"]
        assert q["subtopics"] or q["id"] == "EXM.2.AHL.TZ0.5"
        if q["has_markscheme"]:
            assert all(p["ms_spans"] for p in q["parts"]), q["id"]
            reported = any(p.startswith(q["id"]) for p in data.bank()["report"]["problems"])     # e.g. 25N.2.AHL.TZ0.1: the source prints 15 of 19
            assert reported or sum(p["marks"] for p in q["parts"]) == q["max_marks"], q["id"]
    # the duplicate Geometry Paper 2 "markscheme" is reported, and those questions say they have none
    assert any("identical copy" in p for p in data.bank()["report"]["problems"])
    assert all(not q["has_markscheme"] for q in qs if q["doc"] == "gt_p2")


def test_calculator_sheets_have_screens_and_topics():
    sheets = data.sheets()
    assert len(sheets) == 86
    assert all(s["topic"] in (1, 2, 3, 4, 5) and s["subtopics"] for s in sheets)
    files = [st["screen"]["file"] for s in sheets for st in s["steps"] if st.get("screen")]
    assert len(files) > 600 and all(data.screen_path(f).exists() for f in files[:50])
    assert any(s["notes"] for s in sheets if s["id"] == "13-18")       # the teacher's correction 0.117 -> 0.0117


def test_tagger_puts_calculus_in_topic_5_and_finance_in_1_4():
    q = {"id": "x", "topic": 2, "parts": [{"label": "a", "q_text": "A particle moves in a straight line with velocity, v = 3t. Find the acceleration and the displacement.",
                                           "ms_text": ""}]}
    assert maths_tagging.tag_question(q)["part_subtopics"]["a"] == "5.13"
    q = {"id": "y", "topic": 1, "parts": [{"label": "a", "q_text": "Interest is compounded monthly at 3% per annum.", "ms_text": ""}]}
    assert maths_tagging.tag_question(q)["part_subtopics"]["a"] == "1.4"


# ---------------------------------------------------------------- progress
def _part(qid, part, sub, awarded, marks, day, mode="practice", helped=False, mistake=None, ts=0.0):
    return {"id": f"{qid}{part}{day}{ts}", "kind": "part", "qid": qid, "part": part, "topic": int(sub.split(".")[0]), "subtopic": sub,
            "concept": sub, "marks": marks, "awarded": awarded, "outcome": "full" if awarded == marks else "partial" if awarded else "miss",
            "mode": mode, "helped": helped, "mistake": mistake, "day": day, "time": "10:00", "ts": ts or date.fromisoformat(day).toordinal()}


def _recall(card, grade, day):
    return {"kind": "recall", "card": card, "subtopic": card.split("#")[0], "grade": grade, "day": day, "ts": 0}


def test_mastery_needs_recall_unaided_success_on_two_days_and_an_unfamiliar_context():
    sub = "1.2"
    assert progress.level(sub, [])["level"] == "Not started"
    rows = [_part("Q1", "a", sub, 3, 3, "2026-11-01"), _part("Q2", "a", sub, 3, 3, "2026-11-01"), _part("Q3", "a", sub, 2, 2, "2026-11-01")]
    assert progress.level(sub, rows)["level"] == "Practising"          # no recall yet
    rows += [_recall(f"{sub}#{i}", "good", d) for i in range(3) for d in ("2026-11-01", "2026-11-04")]
    lv = progress.level(sub, rows)
    assert lv["level"] == "Confident" and any("another day" in n for n in lv["needs"]) and any("mixed" in n for n in lv["needs"])
    rows += [_part("Q4", "a", sub, 4, 4, "2026-11-04", mode="mixed")]
    assert progress.level(sub, rows)["level"] == "Mastered"
    rows += [_part("Q5", "a", sub, 0, 3, "2026-11-05", mistake="Incorrect formula selection")]
    assert progress.level(sub, rows)["level"] != "Mastered"            # a fresh miss takes it away


def test_hinted_full_marks_do_not_count_as_unaided():
    rows = [_part(f"Q{i}", "a", "1.3", 2, 2, "2026-11-01", helped=True) for i in range(4)]
    assert progress.subtopic_stats("1.3", rows)["clean"] == 0


def test_recall_intervals_grow_and_again_resets():
    rows = [_recall("1.1#0", "good", "2026-11-01"), _recall("1.1#0", "good", "2026-11-04")]
    s = progress.card_states(rows)["1.1#0"]
    assert s["interval"] == 6 and s["due"] == date(2026, 11, 10)
    rows.append(_recall("1.1#0", "again", "2026-11-10"))
    assert progress.card_states(rows)["1.1#0"]["interval"] == 1


def test_missed_parts_come_back_tomorrow_and_fixes_resolve_the_error():
    rows = [_part("Q1", "b", "1.7", 0, 2, "2026-11-07", mistake="Calculator operation error", ts=1)]
    assert progress.due_retries(rows, date(2026, 11, 7)) == []
    assert progress.due_retries(rows, date(2026, 11, 8)) == [("Q1", "b")]
    errs = progress.error_log(rows, notes={})
    assert len(errs) == 1 and not errs[0]["resolved"]
    rows.append(_part("Q1", "b", "1.7", 2, 2, "2026-11-08", mode="review", ts=2))
    assert progress.error_log(rows, notes={})[0]["fixed"]
    assert progress.due_retries(rows, date(2026, 11, 9)) == []


def test_log_part_appends_without_touching_earlier_lines(tmp_path):
    path = tmp_path / "a.jsonl"
    path.write_text('{"kind": "recall", "card": "1.1#0", "grade": "good", "day": "2026-11-01"}\n', encoding="utf-8")
    q = data.questions()[0]
    progress.log_part(q, q["parts"][0], 0, "practice", mistake="Algebraic or numerical error", path=path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["outcome"] == "miss"


def test_mixed_set_takes_topics_in_turn():
    qs = progress.mixed_set([], 8, "seed", "all")
    assert len(qs) == 8 and len({q["topic"] for q in qs[:4]}) == 4


# ---------------------------------------------------------------- calendar
def test_calendar_never_schedules_the_past_and_keeps_the_weekend_plan(tmp_path):
    now = datetime(2026, 11, 7, 12, 5)
    cal = schedule.ensure(now, tmp_path / "c.json")
    ss = cal["sessions"]
    assert all(schedule.at(s["date"], s["start"]) >= now for s in ss if not s.get("unscheduled"))
    assert not any(s["date"] == "2026-11-06" for s in ss)
    sat = [s for s in ss if s["date"] == "2026-11-07" and s["kind"] != "break"]
    assert sat[0]["title"].startswith("Catch-up") and any("Geometry" in s["title"] for s in sat)
    sun = [s["kind"] for s in ss if s["date"] == "2026-11-08" and s["kind"] != "break"]
    assert sun[:2] == ["study", "study"] and "mixed" in sun and "exam" in sun
    assert not schedule.overlaps(cal)


def test_replan_moves_missed_sessions_to_the_future(tmp_path):
    cal = schedule.ensure(datetime(2026, 11, 7, 12, 5), tmp_path / "c.json")
    later = datetime(2026, 11, 7, 16, 0)
    missed = [s for s in cal["sessions"] if s["kind"] != "break" and schedule.status(s, later) == "missed"]
    assert missed
    assert schedule.replan_from_now(cal, later) == len(missed)
    assert not [s for s in cal["sessions"] if s["kind"] != "break" and schedule.status(s, later) == "missed"]


def test_routine_fills_the_calendar_from_the_plan_once_and_never_the_past(tmp_path, monkeypatch):
    from ibtee import routine
    monkeypatch.setattr(routine, "ROUTINE", tmp_path / "routine.json")
    now = datetime(2026, 11, 7, 12, 5)
    cal = schedule.ensure_month(now, tmp_path / "c.json")
    days = schedule.month_sessions(cal, 2026, 11)
    assert "2026-11-06" not in days and "2026-11-30" in days
    assert all(schedule.at(s["date"], s["start"]) >= now for ss in days.values() for s in ss if s["kind"] != "task")
    monday = [(s["start"], s.get("subject"), s["kind"]) for s in days["2026-11-09"]]
    assert ("08:30", "school", "school") in monday and ("17:15", "biology", "study") in monday and ("19:15", "maths", "study") in monday
    assert ("21:00", "chemistry", "review") in monday                     # daily Chemistry review
    studied = {c for ss in days.values() for s in ss for c in s["subtopics"]}
    assert any(c.startswith("5.") for c in studied)                        # Calculus is in the Maths rotation
    lunch = next(s for s in days["2026-11-09"] if s["start"] == "13:00")
    assert lunch["subtopics"] == [] and lunch["subject"] == "maths"        # the lunch review is not a rotation slot
    assert not schedule.overlaps(cal)
    n = len(cal["sessions"])
    assert len(schedule.ensure_month(now, tmp_path / "c.json")["sessions"]) == n     # never filled twice


def test_unfinished_maths_moves_into_the_next_maths_slots(tmp_path, monkeypatch):
    from ibtee import routine
    monkeypatch.setattr(routine, "ROUTINE", tmp_path / "routine.json")
    now = datetime(2026, 11, 7, 12, 5)
    cal = schedule.ensure_month(now, tmp_path / "c.json")
    old = schedule.session("2026-11-07", "10:00", 60, "study", "Functions HL", "obj", ["2.7"])
    cal["sessions"].append(old)
    (o, slot), = routine.carry_into_maths_slots(cal, [old], datetime(2026, 11, 7, 20, 50))
    assert slot["date"] == "2026-11-08" or slot["date"] >= "2026-11-09"
    assert slot["subtopics"] == ["2.7"] and slot["moved_from"] == "2026-11-07 10:00" and old not in cal["sessions"]
    removed, added = routine.reapply(cal, now, routine.load())
    assert slot in cal["sessions"]                                         # moved work survives a routine refresh


def test_day_editor_updates_adds_and_deletes(tmp_path, monkeypatch):
    import pandas as pd
    from ibtee import planner, routine
    monkeypatch.setattr(routine, "ROUTINE", tmp_path / "routine.json")
    cal = schedule.ensure_month(datetime(2026, 11, 7, 12, 5), tmp_path / "c.json")
    iso = "2026-11-10"
    items = sorted((s for s in cal["sessions"] if s["date"] == iso), key=lambda s: (s["kind"] != "task", s["start"]))
    before = planner.day_frame(items)
    after = before.copy()
    after.loc[after["start"] == "17:15", ["done", "title"]] = [True, "Psychology: IA reading"]
    after = after[after["start"] != "22:00"]
    after = pd.concat([after, pd.DataFrame([{"id": None, "done": None, "start": "16:30", "minutes": None, "subject": "Biology",
                                             "kind": "study", "title": "Biology flashcards", "weekly review": None, "note": None}])])
    assert planner.save_day(cal, iso, before, after) == []
    day = {s["start"]: s for s in cal["sessions"] if s["date"] == iso}
    assert day["17:15"]["done"] and day["17:15"]["title"] == "Psychology: IA reading" and day["17:15"]["edited"]
    assert "22:00" not in day and day["16:30"]["subject"] == "biology" and day["16:30"]["minutes"] == 30
    bad = after.copy()
    bad.loc[bad["start"] == "16:30", "start"] = "4pm"
    assert planner.save_day(cal, iso, planner.day_frame(items), bad)


def test_book_index_covers_the_syllabus_and_pairs_exercises():
    covered = {c for s in data.book()["sections"] for c in s["subtopics"]}
    assert covered == {s["code"] for s in data.subtopics()}
    book_pages, ws_pages, doc = data.exercise_pages("7E")
    assert book_pages and ws_pages and doc == "ws7"


# ---------------------------------------------------------------- exams, store, theme
def test_exam_is_built_to_exam_length_from_one_paper():
    e = exams.build("1", [1, 2, 3, 4], [], seed="t")
    qs = [data.question(q) for q in e["qids"]]
    assert all(q["paper"] == "1" for q in qs)
    assert 100 <= e["total"] <= 118 and e["minutes"] >= 110


def test_bookmarks_toggle(tmp_path):
    p = tmp_path / "b.json"
    assert store.toggle_bookmark("maths_ai_hl", "Q1", "Q1", path=p)
    assert store.is_bookmarked("maths_ai_hl", "Q1", path=p)
    assert not store.toggle_bookmark("maths_ai_hl", "Q1", "Q1", path=p)


def test_dollar_signs_never_open_latex():
    assert "$" not in theme.esc("$100000 and $150000")


# ---------------------------------------------------------------- every page loads
ROUTES = [{}, {"p": "subjects"}, {"p": "bookmarks"}] + [{"s": "maths_ai_hl", "p": p} for p in
         ["overview", "topics", "recall", "qb", "search", "mixed", "exams", "past", "calc", "errors", "calendar", "analytics"]] + [
    {"s": "maths_ai_hl", "p": "topic", "t": "5"}, {"s": "maths_ai_hl", "p": "sub", "c": "1.15"}, {"s": "maths_ai_hl", "p": "qbs", "c": "4.11"},
    {"s": "maths_ai_hl", "p": "q", "q": "25M.1.AHL.TZ1.3"}, {"s": "maths_ai_hl", "p": "sheet", "sh": "7-10"},
    {"s": "maths_ai_hl", "p": "pastset", "sess": "24N", "pp": "2"},
    {"s": "maths_ai_hl", "p": "calendar", "v": "agenda"}, {"s": "maths_ai_hl", "p": "calendar", "m": "2026-12"},
    {"s": "maths_ai_hl", "p": "calendar", "m": "2026-11", "d": "2026-11-15"}, {"s": "maths_ai_hl", "p": "topic", "t": "4", "v": "book"},
    {"s": "maths_ai_hl", "p": "book", "bs": "7.2"}, {"s": "maths_ai_hl", "p": "book", "bs": "7.2", "bx": "7E"}, {"s": "maths_ai_hl", "p": "book", "bs": "7.2", "bx": "inv"}, {"s": "maths_ai_hl", "p": "book", "bs": "7.2", "bx": "examples"}, {"s": "maths_ai_hl", "p": "book", "bs": "7.2", "bx": "review"},
    {"s": "maths_ai_hl", "p": "sub", "c": "1.7", "v": "learn"}, {"s": "maths_ai_hl", "p": "overview", "v": "progress"},
    {"s": "maths_ai_hl", "p": "links"}, {"s": "maths_ai_hl", "p": "topic", "t": "1", "v": "links"}, {"s": "maths_ai_hl", "p": "sheet", "sh": "7-9"},
    {"p": "calendar"}, {"p": "calendar", "v": "week", "d": "2026-11-10"}, {"p": "calendar", "v": "routine"},
    {"p": "calendar", "m": "2026-11", "d": "2026-11-12"}]


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: "&".join(f"{k}={v}" for k, v in r.items()) or "home")
def test_page_loads(route, monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(schedule, "CAL", tmp_path / "cal.json")         # never create or change the real calendar
    from ibtee import routine
    monkeypatch.setattr(routine, "ROUTINE", tmp_path / "routine.json")
    monkeypatch.setattr(exams, "EXAMS", tmp_path / "exams.json")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["auth_user"] = {"id": "owner", "username": "owner", "name": "Owner", "owner": True, "onboarded": True}
    for k, v in route.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, [e.message for e in at.exception]


def test_an_event_makes_room_and_never_loses_study(tmp_path, monkeypatch):
    from ibtee import routine
    monkeypatch.setattr(routine, "ROUTINE", tmp_path / "routine.json")
    now = datetime(2026, 11, 7, 21, 0)
    cal = schedule.ensure_month(now, tmp_path / "c.json")
    ev = schedule.session("2026-11-10", "16:30", 240, "busy", "Pre-general", "", [], "Choir")
    ev.update({"subject": "choir", "edited": True})
    cal["sessions"].append(ev)
    r = routine.clear_for_event(cal, ev, now, catch_up_day="2026-11-14")
    day = [s for s in cal["sessions"] if s["date"] == "2026-11-10"]
    assert not [s for s in day if s is not ev and s["kind"] != "school" and s["kind"] != "task"
                and schedule.at(s["date"], s["start"]) < schedule.at("2026-11-10", "20:30") and schedule.end_of(s) > schedule.at("2026-11-10", "16:30")]
    assert {t["subject"] for t in r["todos"]} == {"psychology", "chemistry"} and all(t["date"] == "2026-11-14" for t in r["todos"])
    assert r["maths"] and r["maths"][0][1]["date"] > "2026-11-10"          # the Maths block moved to a later Maths slot
    assert any(s["title"] == "Daily Chemistry review" for s in day)         # after the event: untouched
    n = len(cal["sessions"])
    routine.apply(cal, now)
    assert len(cal["sessions"]) == n                                        # the routine does not refill the event's time


def test_board_payload_holds_every_task_and_ticks_save(tmp_path, monkeypatch):
    from ibtee import calendar_view as cv, planner, routine
    monkeypatch.setattr(routine, "ROUTINE", tmp_path / "routine.json")
    monkeypatch.setattr(schedule, "CAL", tmp_path / "c.json")
    now = datetime(2026, 11, 7, 12, 5)
    cal = schedule.ensure_month(now)
    data = cv.payload(cal, now, day="2026-11-09")
    assert len(data["sessions"]) == len(cal["sessions"]) and data["today"] == "2026-11-07"
    row = next(r for r in data["sessions"] if r["date"] == "2026-11-09" and r["start"] == "19:15")
    assert row["can_open"] and row["colour"] and row["label"] == "Maths" and row["status"] == "upcoming"
    planner.act(cal, {"action": "done", "id": row["id"], "done": True})
    assert next(s for s in schedule.load()["sessions"] if s["id"] == row["id"])["done"]


# ---------------------------------------------------------------- fuller notes, calculator guides
def test_every_subtopic_has_fuller_notes_with_a_reason_for_each_step():
    for s in data.subtopics():
        d = data.depth(s["code"])
        assert d["i"] and d["h"] and d["q"] and d["a"], s["code"]
        assert d["s"] and all(step and why for step, why in d["s"]), s["code"]
        for f in s["formulas"]:
            where, when = d["f"][f["name"]]
            assert where and when, (s["code"], f["name"])


def test_every_calculator_sheet_has_a_guide_and_no_guide_gives_key_presses():
    press = __import__("re").compile(r"\b((?i:press)|SHIFT|EXE|ALPHA)\b")
    for sh in data.sheets():
        g = data.guide(sh["id"])
        assert g["lv"] in (1, 2, 3) and all(g[k] for k in ("ask", "what", "when", "in", "read", "check")), sh["id"]
        assert not press.search(" ".join(g[k] for k in ("what", "when", "in", "read", "check"))), sh["id"]
        assert len(set([g["read"], *g["trap"]])) == 1 + len(g["trap"])
    assert sum(bool(data.guide(s["id"])["trap"]) for s in data.sheets()) >= 75


def test_sequence_sheets_are_not_labelled_complex_numbers():
    assert "Complex numbers" not in data.sheet("4-13")["apps"] and "Complex numbers" in data.sheet("8-9")["apps"]
    assert data.sheet("10-21")["question_type"].startswith("Calculus")


# ---------------------------------------------------------------- mixed practice and mistakes
def test_synoptic_sets_take_the_six_links_in_turn():
    qs = progress.mixed_set([], 12, "seed", "synoptic")
    met = {name for q in qs for name in progress.connections_of(q)}
    assert len(qs) == 12 and len(met) >= 5


def test_weak_subtopics_come_up_more_and_mastered_ones_less():
    weak = "1.7"
    rows = [_part("X", "a", weak, 0, 4, "2026-11-01", mistake="Calculator operation error", ts=1)]
    pool = [q for q in data.questions() if q["has_markscheme"] and q["subtopics"]]
    hits = sum(weak in q["subtopics"] for seed in range(30) for q in progress.ranked(pool, rows, str(seed))[:10])
    base = sum(weak in q["subtopics"] for seed in range(30) for q in progress.ranked(pool, [], str(seed))[:10])
    assert hits > base


def test_mistake_type_changes_the_advice():
    rows = [_part(f"Q{i}", "a", "1.7", 0, 2, "2026-11-01", mistake="Calculator operation error", ts=i + 1) for i in range(3)]
    rows.append(_part("Q9", "a", "2.1", 0, 2, "2026-11-01", mistake="Conceptual misunderstanding", ts=9))
    focus = progress.mistake_focus(rows)
    assert focus[0]["mistake"] == "Calculator operation error" and focus[0]["view"] == "calculator" and focus[0]["codes"] == ["1.7"]
    assert focus[1]["view"] == "learn"


# ---------------------------------------------------------------- missed work and waiting blocks
def _cal(tmp_path, monkeypatch):
    from ibtee import routine
    monkeypatch.setattr(routine, "ROUTINE", tmp_path / "routine.json")
    return schedule.ensure_month(datetime(2026, 11, 7, 12, 5), tmp_path / "c.json")


def test_missed_sessions_move_forward_and_nothing_is_lost(tmp_path, monkeypatch):
    from ibtee import routine
    cal = _cal(tmp_path, monkeypatch)
    later = datetime(2026, 11, 10, 22, 30)
    maths = schedule.session("2026-11-09", "16:00", 45, "study", "Functions HL", "obj", ["2.7"])
    exam = schedule.session("2026-11-09", "16:45", 60, "exam", "Timed paper", "obj", [])
    chem = schedule.session("2026-11-09", "07:00", 30, "study", "Chemistry R1.3", "obj", [])
    chem.update({"subject": "chemistry", "chem_topic": "R1.3"})
    cal["sessions"] += [maths, exam, chem]
    found = {s["id"] for s in routine.missed_work(cal, later)}
    assert {maths["id"], exam["id"], chem["id"]} <= found
    assert not any(routine.is_habit(s) for s in routine.missed_work(cal, later))
    done = routine.rescue_missed(cal, {maths["id"], exam["id"], chem["id"]}, later, "2026-11-11")
    assert len(done["maths"]) == 1 and done["maths"][0][1]["subtopics"] == ["2.7"]
    assert {t["title"] for t in done["todos"]} == {"Catch up: Timed paper (60 min)", "Catch up: Chemistry R1.3 (30 min)"}
    assert all(t["date"] == "2026-11-11" and t["kind"] == "task" for t in done["todos"]) and maths not in cal["sessions"]
    assert next(t for t in done["todos"] if "Chemistry" in t["title"])["chem_topic"] == "R1.3"


def test_a_waiting_block_gets_its_own_time_only_if_it_is_free(tmp_path, monkeypatch):
    from ibtee import routine
    cal = _cal(tmp_path, monkeypatch)
    now = datetime(2026, 11, 7, 12, 5)
    cal["maths_backlog"] = [{"title": "Functions: 2.1", "objective": "o", "subtopics": ["2.1"], "calculator": ["3-1"], "questions": [], "moved_from": None}]
    with pytest.raises(ValueError):
        routine.place_backlog(cal, 0, "2026-11-09", "09:00", 45, now)     # school
    with pytest.raises(ValueError):
        routine.place_backlog(cal, 0, "2026-11-01", "09:00", 45, now)     # the past
    assert len(cal["maths_backlog"]) == 1
    day, start = routine.next_free(cal, now)
    s = routine.place_backlog(cal, 0, day, start, 45, now)
    assert s["subtopics"] == ["2.1"] and s["calculator"] == ["3-1"] and s["title"] == "Maths · Functions: 2.1" and not cal["maths_backlog"]
    assert not schedule.overlaps(cal)


# ---------------------------------------------------------------- the textbook, kept apart
def test_book_questions_are_separate_paired_and_every_subtopic_is_reachable():
    qs = data.book_questions()
    assert len(qs) > 800 and len({q["id"] for q in qs}) == len(qs)
    assert not {q["id"] for q in qs} & {q["id"] for q in data.questions()}
    assert all(q["spans"] and q["subtopics"] and all(len(s) == 5 for s in q["spans"]) for q in qs)
    with_answer = [q for q in qs if q["ws_spans"]]
    assert len(with_answer) / len(qs) > 0.98 and all(q["ws_doc"] for q in with_answer)
    for ex in {q["exercise"] for q in qs}:                                    # numbers run 1, 2, 3 … so answers can't slip
        numbers = sorted(q["number"] for q in qs if q["exercise"] == ex)
        assert numbers == list(range(1, len(numbers) + 1)), ex


def test_investigations_and_notes_are_saved_on_their_own():
    assert len(data.book_features("investigations")) > 120 and len(data.book_features("examples")) > 200
    assert all(f["spans"] for f in data.book_features("investigations"))
    notes = json.loads((data.DIR / "book_notes.json").read_text(encoding="utf-8"))
    assert len(notes) == len(data.book()["sections"]) and all(n["text"].strip() for n in notes.values())


def test_every_question_says_where_it_comes_from():
    from maths import ui_question
    q = data.questions()[0]
    assert "Past paper" in ui_question.labels_for(q, hidden=False) and "Past paper" in ui_question.labels_for(q, hidden=True)
    from reference import header
    assert "Past paper" in header(1, q["id"], 2)["tags"]


def test_book_attempts_never_change_a_level():
    rows = [{"kind": "book", "qid": "7E.1", "subtopic": "1.4", "result": "right", "day": "2026-11-08", "ts": 1}]
    assert progress.book_states(rows) == {"7E.1": "right"} and progress.level("1.4", rows)["level"] == "Not started"


def test_every_subtopic_can_read_the_book_or_is_covered_by_its_section():
    passages = data.book_passages()
    assert len(passages) > 400 and all(p["spans"] and p["subtopics"] for p in passages)
    covered = {c for p in passages for c in p["subtopics"]}
    assert len(covered) >= 75
    assert {p["kind"] for p in passages} >= {"note", "example", "investigation", "summary"}


def test_connections_have_evidence_and_join_topics():
    m = data.connection_map()
    assert all(m["links"][s["code"]] for s in data.subtopics())
    for code, rows in m["links"].items():
        for r in rows:
            assert r["syllabus"] or r["past"] or r["passages"] or r["sheets"] or r["book_questions"], (code, r["code"])
    assert sum(1 for k, v in m["links"].items() for r in v if data.topic_of(r["code"]) != data.topic_of(k)) > 50
    assert len(m["priority"]) == 6 and all(p["questions"] and p["sections"] for p in m["priority"])


def test_calculator_sheets_find_their_textbook_example():
    from maths import ui_pages
    assert data.book_example(7, 9)["section"] == "7.2" and ui_pages.example_sheet(7, 9)["id"] == "7-9"


def test_corrections_are_attached_to_what_they_correct():
    rows = json.loads((data.DIR / "book_corrections.json").read_text(encoding="utf-8"))["rows"]
    assert len(rows) > 100 and sum(1 for r in rows if r["key"]) > 50
    assert any(r["key"] == "1D.6" for r in rows) and data.book_corrections("1D.6")

