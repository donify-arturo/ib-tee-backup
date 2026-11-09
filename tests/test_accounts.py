"""Accounts: passwords, sign-in tokens, whose files a student reads, and the first-run setup. Never touches the real data/."""
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from ibtee import cloud, onboarding, routine, store, users
from maths import schedule

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 9, 12, 0)


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(users, "ACCOUNTS", tmp_path / "accounts.json")
    monkeypatch.setattr(users, "USERS_DIR", tmp_path / "users")
    monkeypatch.setattr(users, "_fails", {})
    return tmp_path


def answers(**over):
    return {"subjects": ["physics", "history"], "courses": [], "school": {str(d): {"start": "08:30", "end": "15:30"} for d in range(5)},
            "activities": [], "weekday_start": "16:00", "weekday_sessions": 2, "weekend_start": "10:00", "weekend_sessions": 1, "minutes": 45} | over


def test_the_first_account_is_the_owner_and_must_be_made_on_the_host(accounts):
    with pytest.raises(users.AccountError):
        users.create("first", "First", "longenough", on_host=False)
    owner = users.create("First", "First", "longenough", on_host=True)
    assert owner["owner"] and owner["onboarded"] and owner["username"] == "first"
    other = users.create("second", "Second", "longenough", on_host=False)
    assert not other["owner"] and not other["onboarded"]


def test_passwords_are_hashed_and_checked(accounts):
    users.create("amy", "Amy", "correct-horse", on_host=True)
    assert "correct-horse" not in users.ACCOUNTS.read_text(encoding="utf-8")
    assert users.verify("AMY ", "correct-horse")["username"] == "amy"
    assert users.verify("amy", "wrong-password") is None
    assert users.verify("nobody", "correct-horse") is None


@pytest.mark.parametrize("username,password", [("a", "longenough"), ("../evil", "longenough"), ("fine", "short")])
def test_bad_usernames_and_short_passwords_are_refused(accounts, username, password):
    with pytest.raises(users.AccountError):
        users.create(username, "Name", password, on_host=True)


def test_repeated_wrong_passwords_lock_the_account_for_a_while(accounts):
    users.create("amy", "Amy", "correct-horse", on_host=True)
    for _ in range(users.MAX_FAILS):
        assert users.verify("amy", "nope", now=1000.0) is None
    with pytest.raises(users.AccountError):
        users.verify("amy", "correct-horse", now=1001.0)
    assert users.verify("amy", "correct-horse", now=1000.0 + users.LOCK_SECONDS + 1)


def test_sign_in_tokens_expire_end_and_are_stored_only_as_hashes(accounts):
    users.create("amy", "Amy", "correct-horse", on_host=True)
    token = users.new_session("amy", now=1000.0)
    assert token not in users.ACCOUNTS.read_text(encoding="utf-8")
    assert users.session_user(token, now=1001.0)["username"] == "amy"
    assert users.session_user(token, now=1000.0 + users.SESSION_DAYS * 86400 + 1) is None
    users.end_session(token)
    assert users.session_user(token, now=1001.0) is None


def test_a_google_identity_keeps_one_account_and_has_no_password(accounts):
    users.create("owner", "Owner", "longenough", on_host=True)
    first, created = users.google_account("sub-1", "Bea.Lopez@example.com", "Bea", on_host=False)
    assert created and not first["owner"] and not first["onboarded"] and first["username"] == "bea.lopez"
    again, created = users.google_account("sub-1", "changed@example.com", "New", on_host=False)
    assert not created and again["id"] == first["id"]
    assert users.verify("bea.lopez", "") is None and users.verify("bea.lopez", "anything-at-all") is None


def test_the_hosted_owner_is_the_configured_email_only(accounts):
    other, _ = users.google_account("s1", "someone@example.com", "S", on_host=False, owner_email="me@example.com")
    assert not other["owner"]
    me, _ = users.google_account("s2", "ME@example.com", "Me", on_host=False, owner_email="me@example.com")
    assert me["owner"] and me["onboarded"]


def test_a_private_list_keeps_others_out_but_never_the_owner(accounts):
    with pytest.raises(users.AccountError):
        users.google_account("s1", "stranger@example.com", "S", on_host=False, owner_email="me@example.com", allowed=["friend@example.com"])
    assert users.google_account("s2", "Friend@example.com", "F", on_host=False, owner_email="me@example.com", allowed=["friend@example.com"])[1]
    assert users.google_account("s3", "me@example.com", "Me", on_host=False, owner_email="me@example.com", allowed=["friend@example.com"])[0]["owner"]


class FakeFirestore:
    """Just the calls ibtee/cloud.py makes."""
    def __init__(self):
        self.docs, self.fail = {}, False

    def collection(self, name, prefix=()):
        store = self

        class Doc:
            def __init__(self, key):
                self.key = key

            def collection(self, sub):
                return store.collection(sub, self.key)

            def set(self, value):
                store.docs[self.key] = value

            def to_dict(self):
                return store.docs[self.key]

        class Coll:
            def document(self, doc_id):
                return Doc((*prefix, name, doc_id))

            def stream(self):
                if store.fail:
                    raise RuntimeError("offline")
                return [Doc(k) for k in store.docs if k[:-1] == (*prefix, name)]
        return Coll()


@pytest.fixture
def firestore(accounts, monkeypatch):
    fake = FakeFirestore()
    monkeypatch.setattr(cloud, "enabled", lambda: True)
    monkeypatch.setattr(cloud, "_client", lambda: fake)
    monkeypatch.setattr(cloud, "_restored", set())
    return fake


def test_a_restart_brings_a_students_work_and_the_accounts_back(firestore, accounts, monkeypatch):
    user, _ = users.google_account("s1", "bea@example.com", "Bea", on_host=False, owner_email="me@example.com")
    folder = accounts / "users" / user["id"]
    monkeypatch.setattr(users, "current", lambda: user)
    store.save_profile({"name": "Bea", "my_subjects": []})
    schedule.save({"sessions": []})
    assert (folder / "maths" / "calendar.json").exists()
    shutil.rmtree(accounts)                                              # the restart
    cloud._restored.clear()
    assert users.google_account("s1", "bea@example.com", "Bea", on_host=False, owner_email="me@example.com") == (user, False)
    users.open_workspace(user)
    assert json.loads((folder / "profile.json").read_text(encoding="utf-8"))["name"] == "Bea"
    assert (folder / "maths" / "calendar.json").exists()


def test_a_failed_restore_is_not_treated_as_done(firestore, accounts):
    firestore.fail = True
    with pytest.raises(RuntimeError):
        cloud.ensure("abc", accounts)
    firestore.fail = False
    cloud.ensure("abc", accounts)
    assert "abc" in cloud._restored


def test_a_stored_path_cannot_write_outside_the_students_folder(firestore, accounts):
    import zlib
    firestore.docs[("ib_tee", "abc", "files", "x")] = {"path": "../../evil.txt", "z": zlib.compress(b"x")}
    (accounts / "a" / "b").mkdir(parents=True)
    cloud.ensure("abc", accounts / "a" / "b")
    assert not (accounts / "evil.txt").exists()


def test_a_new_password_signs_the_account_out_everywhere(accounts):
    users.create("amy", "Amy", "correct-horse", on_host=True)
    token = users.new_session("amy")
    users.set_password("amy", "another-password")
    assert users.session_user(token) is None
    assert users.verify("amy", "another-password")


def test_scoped_keeps_the_owner_in_data_and_moves_students_to_their_own_folder(accounts, monkeypatch):
    real = users.DATA / "maths" / "calendar.json"
    assert users.scoped(real) == real                                    # no student signed in (scripts, tests, the owner)
    monkeypatch.setattr(users, "guest_id", lambda: "abc")
    assert users.scoped(real) == accounts / "users" / "abc" / "maths" / "calendar.json"
    assert users.scoped(accounts / "elsewhere.json") == accounts / "elsewhere.json"
    monkeypatch.setattr(users, "USERS_DIR", users.DATA / "users")
    assert users.scoped(users.scoped(real)) == users.scoped(real)        # scoping twice changes nothing


def test_a_student_starts_blank_never_with_the_owners_week(accounts, monkeypatch):
    monkeypatch.setattr(users, "guest_id", lambda: "abc")
    assert routine.load() == {"days": {}, "tasks": {}}
    assert schedule.ensure_month(NOW)["sessions"] == []
    assert (accounts / "users" / "abc" / "maths" / "calendar.json").exists()


def test_two_students_never_see_each_others_calendar(accounts, monkeypatch):
    monkeypatch.setattr(users, "guest_id", lambda: "one")
    onboarding.finish(answers(), [], NOW)
    assert schedule.load()["sessions"]
    monkeypatch.setattr(users, "guest_id", lambda: "two")
    assert schedule.load() == {}
    assert routine.load() == {"days": {}, "tasks": {}}


def test_routine_keeps_school_and_activities_free_and_takes_subjects_in_turn():
    r = onboarding.build_routine(answers(activities=[{"day": 0, "start": "16:30", "minutes": 60, "title": "Football"}]))
    monday = r["days"]["0"]
    assert [b["title"] for b in monday if b["kind"] != "study"] == ["School", "Football"]
    # 16:00 + 45 min would run into Football (16:30-17:30), so study waits until it ends
    assert [b["start"] for b in monday if b["kind"] == "study"] == ["17:30", "18:25"]
    assert not [b for b in r["days"]["5"] if b["kind"] == "school"]
    every = [b["subject"] for d in range(7) for b in r["days"][str(d)] if b["kind"] == "study"]
    assert every[:4] == ["physics", "history", "physics", "history"]


def test_a_study_block_never_runs_past_the_end_of_the_day():
    r = onboarding.build_routine(answers(weekday_start="21:00", weekday_sessions=5, minutes=60))
    assert [b["start"] for b in r["days"]["0"] if b["kind"] == "study"] == ["21:00"]


def test_maths_rotation_only_for_students_on_the_maths_course():
    without = onboarding.build_routine(answers(subjects=["maths"]))
    assert all(b.get("rotation") is False for b in without["days"]["0"] if b["kind"] == "study")
    with_course = onboarding.build_routine(answers(subjects=["maths"], courses=["maths_ai_hl"]))
    assert all("rotation" not in b for b in with_course["days"]["0"] if b["kind"] == "study")


def test_exams_and_deadlines_reach_the_calendar_and_the_routine_plans_around_them(accounts, monkeypatch):
    monkeypatch.setattr(users, "guest_id", lambda: "abc")
    onboarding.finish(answers(), [
        {"type": "Exam", "title": "Physics P1", "subject": "physics", "date": "2026-11-16", "start": "16:00", "minutes": 120},
        {"type": "Deadline", "title": "History IA", "subject": "history", "date": "2026-11-20", "start": "09:00", "minutes": 120},
    ], NOW)
    cal = schedule.load()
    exam = next(s for s in cal["sessions"] if s.get("my_exam") and s["kind"] == "exam")
    assert exam["date"] == "2026-11-16" and exam["subject"] == "physics"
    deadline = next(s for s in cal["sessions"] if s.get("deadline"))
    assert deadline["title"] == "Deadline: History IA" and deadline["kind"] == "task"
    same_day = [s for s in cal["sessions"] if s["date"] == "2026-11-16" and s["kind"] == "study"]
    assert all(s["start"] >= "18:00" for s in same_day)                  # the routine's 16:00 study slot gave way to the exam


@pytest.mark.parametrize("item,why", [
    ({"type": "Exam", "date": "2026-11-01", "start": "09:00"}, "passed"),
    ({"type": "Deadline", "date": "2026-11-01", "start": "09:00"}, "passed"),
])
def test_the_past_cannot_be_scheduled(item, why):
    with pytest.raises(ValueError, match=why):
        onboarding.add_item({"sessions": []}, {"title": "X", "subject": "general", "minutes": 60} | item, NOW)


def test_two_exams_cannot_overlap():
    cal = {"sessions": []}
    base = {"type": "Exam", "subject": "general", "date": "2026-11-16", "start": "09:00", "minutes": 120}
    onboarding.add_item(cal, base | {"title": "A"}, NOW)
    with pytest.raises(ValueError, match="overlaps"):
        onboarding.add_item(cal, base | {"title": "B", "start": "10:00"}, NOW)


def test_no_page_runs_without_signing_in(accounts):
    from streamlit.testing.v1 import AppTest
    users.create("owner", "Owner", "longenough", on_host=True)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.query_params["p"] = "calendar"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.text_input(key="login_user") is not None
    assert not any("Calendar" == h.value for h in at.title) and not at.sidebar.button


def test_a_new_student_signs_up_sets_up_and_gets_their_own_calendar(accounts, monkeypatch):
    from streamlit.testing.v1 import AppTest
    users.create("owner", "Owner", "longenough", on_host=True)
    monkeypatch.setattr(routine, "ROUTINE", users.DATA / "routine.json")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    at.text_input(key="signup_name").input("Bea")
    at.text_input(key="signup_user").input("bea")
    at.text_input(key="signup_password").input("longenough")
    at.text_input(key="signup_again").input("longenough")
    next(b for b in at.button if b.label == "Create my account").click().run()
    assert not at.exception, [e.message for e in at.exception]
    at.multiselect(key="ob_subject_pick").set_value(["Physics", "History"])
    next(b for b in at.button if b.label == "Next").click().run()
    assert not at.exception, [e.message for e in at.exception]
    next(b for b in at.button if b.label == "Next").click().run()
    assert not at.exception, [e.message for e in at.exception]
    at.text_input(key="ob_item_0_what").input("Physics Paper 1")
    at.date_input(key="ob_item_0_date").set_value(schedule.now_local().date())
    at.text_input(key="ob_item_0_start").input("00:00")
    next(b for b in at.button if b.label == "Add").click().run()         # refused: that time has gone, and the form keeps what was typed
    assert at.error and at.text_input(key="ob_item_0_what").value == "Physics Paper 1"
    at.date_input(key="ob_item_0_date").set_value(date.today() + timedelta(days=7))
    next(b for b in at.button if b.label == "Add").click().run()         # the next press must count
    assert not at.exception, [e.message for e in at.exception]
    assert any("Physics Paper 1" in m.value for m in at.markdown)
    assert at.text_input(key="ob_item_1_what").value == ""               # and only now does the form empty
    at.button(key="ob_finish").click().run()
    assert not at.exception, [e.message for e in at.exception]
    uid = at.session_state[users.SESSION_KEY]["id"]
    assert at.session_state[users.SESSION_KEY]["onboarded"]
    folder = accounts / "users" / uid
    assert (folder / "routine.json").exists() and (folder / "maths" / "calendar.json").exists() and (folder / "profile.json").exists()
    saved = json.loads((folder / "maths" / "calendar.json").read_text(encoding="utf-8"))["sessions"]
    assert any(x["title"] == "Physics Paper 1" and x["kind"] == "exam" for x in saved)
    assert [x for x in saved if x["kind"] == "study"]


def test_timetable_tables_read_blank_cells_the_way_the_editor_sends_them():
    import pandas as pd
    school = pd.DataFrame([{"starts": "8:30", "ends": "15.30"}, {"starts": None, "ends": None}, {"starts": "", "ends": ""},
                           {"starts": "16:00", "ends": "15:00"}, {"starts": "09:00", "ends": "14:00"}, {"starts": "", "ends": ""}, {"starts": "", "ends": ""}])
    got, problems = onboarding.read_school(school)
    assert got == {"0": {"start": "08:30", "end": "15:30"}, "4": {"start": "09:00", "end": "14:00"}} and len(problems) == 1
    rows = pd.DataFrame([{"day": "Tuesday", "start": "18:00", "minutes": 60.0, "what": "Football"},
                         {"day": None, "start": None, "minutes": float("nan"), "what": None},
                         {"day": "Friday", "start": "18:00", "minutes": float("nan"), "what": "Band"}])
    got, problems = onboarding.read_activities(rows)
    assert got == [{"day": 1, "start": "18:00", "minutes": 60, "title": "Football"}] and len(problems) == 1
