"""The Profile page and the account changes behind it. Never touches the real data/."""
import io
import zipfile
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ibtee import login, profile, store, users

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 9)


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(users, "ACCOUNTS", tmp_path / "accounts.json")
    monkeypatch.setattr(users, "USERS_DIR", tmp_path / "users")
    monkeypatch.setattr(users, "_fails", {})
    return tmp_path


@pytest.fixture
def student(accounts):
    users.create("owner", "Owner", "longenough", on_host=True)
    bea = users.create("bea", "Bea", "correct-horse", on_host=True)
    users.set_onboarded("bea")
    store._write(users.USERS_DIR / bea["id"] / "profile.json", {"name": "Bea", "email": "", "my_subjects": ["chem_hl"], "theme": "light"})
    return {**bea, "onboarded": True}


def open_profile(student, token=None):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state[users.SESSION_KEY] = student
    if token:
        at.session_state[login.TOKEN_KEY] = token
    at.query_params["p"] = "profile"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, [e.message for e in at.exception]


def test_a_new_password_needs_the_current_one(student):
    assert users.change_password("bea", "wrong-password", "another-password") is False
    assert users.verify("bea", "correct-horse")
    with pytest.raises(users.AccountError):
        users.change_password("bea", "correct-horse", "short")
    assert users.change_password("bea", "correct-horse", "another-password") is True
    assert users.verify("bea", "another-password")


def test_a_google_account_has_no_password_to_change(accounts):
    users.create("owner", "Owner", "longenough", on_host=True)
    users.google_account("s1", "bea@example.com", "Bea", on_host=False)
    assert users.details("bea")["has_password"] is False
    assert users.change_password("bea", "", "another-password") is False


def test_details_never_include_the_hash(student):
    assert set(users.details("bea")) == {"created", "email", "has_password"}


def test_signing_out_other_devices_keeps_this_one_and_other_students(student):
    here, there, owners = users.new_session("bea"), users.new_session("bea"), users.new_session("owner")
    assert users.other_sessions("bea", here) == 1
    users.end_other_sessions("bea", here)
    assert users.session_user(here) and not users.session_user(there) and users.session_user(owners)
    assert users.other_sessions("bea", here) == 0


def test_rename_refuses_an_empty_name(student):
    assert users.rename("bea", "  Bea Lopez ") == "Bea Lopez"
    with pytest.raises(users.AccountError):
        users.rename("bea", "   ")


def test_the_export_holds_only_this_students_files(accounts, monkeypatch):
    monkeypatch.setattr(users, "guest_id", lambda: "one")
    store.save_profile({"name": "One", "my_subjects": []})
    monkeypatch.setattr(users, "guest_id", lambda: "two")
    store.save_profile({"name": "Two", "my_subjects": []})
    with zipfile.ZipFile(io.BytesIO(profile.export_zip())) as z:
        assert z.namelist() == ["profile.json"]
        assert b"Two" in z.read("profile.json")


def test_longest_streak_finds_the_best_run_anywhere():
    assert profile.longest_streak(set()) == 0
    assert profile.longest_streak({"2026-11-01", "2026-11-02", "2026-11-03", "2026-11-05", "2026-11-05"}) == 3


def test_upcoming_is_real_exams_from_today_soonest_first_not_practice():
    cal = {"sessions": [
        {"date": "2026-11-30", "start": "08:45", "kind": "busy", "title": "MOCK Maths AI", "mock": True},
        {"date": "2026-11-10", "start": "08:30", "kind": "busy", "title": "EXAM Chemistry"},
        {"date": "2026-11-20", "start": "00:00", "kind": "task", "title": "Deadline: IA", "my_exam": True},
        {"date": "2026-11-08", "start": "09:00", "kind": "busy", "title": "EXAM Past", "my_exam": True},
        {"date": "2026-11-28", "start": "09:00", "kind": "exam", "title": "Maths AI: timed practice paper"},
    ]}
    assert [s["title"] for s in profile.upcoming(cal, TODAY)] == ["EXAM Chemistry", "Deadline: IA", "MOCK Maths AI"]
    assert profile.upcoming({}, TODAY) == []


def test_the_page_shows_a_students_own_account_and_saves_a_new_name(student):
    at = open_profile(student)
    assert any("@bea" in m.value for m in at.markdown)
    at.text_input(key="prof_name").input("Bea Lopez")
    click(at, "Save name")
    assert at.session_state[users.SESSION_KEY]["name"] == "Bea Lopez"
    assert store._read(users.USERS_DIR / student["id"] / "profile.json", {})["name"] == "Bea Lopez"
    assert users.session_user(users.new_session("bea"))["name"] == "Bea Lopez"


def test_changing_the_password_keeps_this_browser_signed_in(student):
    old = users.new_session("bea")
    at = open_profile(student, old)
    at.text_input(key="prof_pw_current").input("correct-horse")
    at.text_input(key="prof_pw_new").input("another-password")
    at.text_input(key="prof_pw_again").input("another-password")
    click(at, "Change password")
    assert not users.session_user(old)
    assert users.session_user(at.session_state[login.TOKEN_KEY])["username"] == "bea"


def test_a_wrong_current_password_changes_nothing(student):
    at = open_profile(student, users.new_session("bea"))
    at.text_input(key="prof_pw_current").input("not-the-password")
    at.text_input(key="prof_pw_new").input("another-password")
    at.text_input(key="prof_pw_again").input("another-password")
    click(at, "Change password")
    assert at.error and users.verify("bea", "correct-horse")


def test_the_menu_opens_the_profile(student):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state[users.SESSION_KEY] = student
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    at.button(key="nav_profile").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.query_params["p"] == ["profile"] or at.query_params["p"] == "profile"
    assert at.text_input(key="prof_name").value == "Bea"
