"""
The Profile page (?p=profile): how the student's revision is going, what is coming up, and their account and data.
The menu that leads here is at the bottom of the sidebar (app.py).
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from ibtee import home, login, nav, routine, store, users
from ibtee import theme as T

UPCOMING = 4

# Every personal file (the same list users.scoped() serves), as it lies under data/. Add new personal files here so they are exported too.
PERSONAL = ["profile.json", "bookmarks.json", "routine.json", "progress.json", "attempts.jsonl", "study_plan.json", "notes.json",
            "maths/calendar.json", "maths/exams.json", "maths/attempts.jsonl", "maths/error_notes.json"]


# --------------------------------------------------------------------------- what the page works out
def export_zip() -> bytes:
    """A zip of the signed-in student's own files, laid out as under data/. Built during the page run, where users.scoped() knows who is asking."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in PERSONAL:
            path = users.scoped(users.DATA / Path(rel))
            if path.exists():
                z.write(path, rel)
    return buffer.getvalue()


def longest_streak(days: set[str]) -> int:
    dates = sorted({date.fromisoformat(d) for d in days if d})
    best = run = 0
    for i, d in enumerate(dates):
        run = run + 1 if i and d - dates[i - 1] == timedelta(days=1) else 1
        best = max(best, run)
    return best


def is_real_exam(s: dict) -> bool:
    """An exam or deadline the student must sit or hand in, not timed practice (which has kind "exam" too)."""
    return bool(s.get("my_exam") or s.get("mock") or s.get("title", "").startswith("EXAM "))


def upcoming(cal: dict, today: date) -> list[dict]:
    first = today.isoformat()
    return sorted((s for s in cal.get("sessions", []) if is_real_exam(s) and s["date"] >= first), key=lambda s: (s["date"], s["start"]))


def in_days(day: str, today: date) -> str:
    n = (date.fromisoformat(day) - today).days
    return "Today" if n == 0 else "Tomorrow" if n == 1 else f"In {n} days"


def subject_summary(acts: list[dict], sid: str) -> str:
    mine = [a for a in acts if a["subject"] == sid]
    if not mine:
        return "Nothing answered yet"
    marks, got = sum(a["total"] for a in mine), sum(a["score"] for a in mine)
    accuracy = f" · {100 * got / marks:.0f}% right" if marks else ""
    return f"{len(mine)} answered{accuracy} · last studied {mine[-1]['day']}"


# --------------------------------------------------------------------------- the page
def page(user: dict) -> None:
    from maths import progress, schedule
    today = schedule.now_local().date()
    prof, account, acts = store.profile(), users.details(user["username"]), home.activity()
    since = f" · member since {date.fromisoformat(account['created'][:10]):%B %Y}" if account["created"] else ""
    T.header(prof["name"], kicker="Profile", sub=f"@{T.esc(user['username'])}{since}")
    T.rule()
    exams = upcoming(schedule.load(), today)
    days = {a["day"] for a in acts if a["day"]}
    week = [(today - timedelta(days=i)).isoformat() for i in range(7)]
    before = [(today - timedelta(days=i)).isoformat() for i in range(7, 14)]
    this_week, last_week = sum(a["day"] in week for a in acts), sum(a["day"] in before for a in acts)
    T.stats_strip([("Next exam", in_days(exams[0]["date"], today) if exams else "—", _short(exams[0]) if exams else "nothing on the calendar"),
                   ("Last 7 days", str(this_week), f"answered, {last_week} the week before"),
                   ("Day streak", str(progress.streak(days, today)), f"best so far: {longest_streak(days)}"),
                   ("All time", str(len(acts)), "Chemistry questions + Maths parts")])
    left, right = st.columns([0.58, 0.42], gap="large")
    with left:
        _coming_up(exams, today)
        _subjects(prof, acts)
    with right:
        _details(user, prof, account)
        if account["has_password"]:
            _security(user)
        _your_data(user, today)


def _short(s: dict) -> str:
    return s["title"].removeprefix("EXAM ").removeprefix("MOCK ")


def _heading(title: str, label: str, key: str, **target) -> None:
    a, b = st.columns([0.7, 0.3], vertical_alignment="bottom")
    a.markdown(f'<div class="h2">{T.esc(title)}</div>', unsafe_allow_html=True)
    with b:
        nav.link(label, key=key, kind="tertiary", **target)


def _coming_up(exams: list[dict], today: date) -> None:
    _heading("Coming up", "All exams", "prof_exams", p="calendar", v="exams")
    if not exams:
        T.empty("Nothing coming up", "Add your exams and deadlines on the Calendar.")
        return
    with st.container(border=True, key="card_prof_upcoming"):
        for s in exams[:UPCOMING]:
            when = f"{date.fromisoformat(s['date']):%a %d %b}" + ("" if s["kind"] == "task" else f" · {s['start']}")
            soon = s["date"] <= (today + timedelta(days=3)).isoformat()
            a, b = st.columns([0.72, 0.28], vertical_alignment="center")
            a.markdown(f"**{T.esc(_short(s))}**<div class='rowdesc'>{T.esc(routine.label(routine.subject_of(s)))} · {when}</div>", unsafe_allow_html=True)
            b.markdown(T.chips((in_days(s["date"], today), "warn" if soon else "")), unsafe_allow_html=True)
        if len(exams) > UPCOMING:
            st.caption(f"and {len(exams) - UPCOMING} more")


def _subjects(prof: dict, acts: list[dict]) -> None:
    _heading("My subjects", "Manage", "prof_manage", p="subjects")
    if not prof["my_subjects"]:
        T.empty("No subjects yet", "Add the IB subjects you're taking.")
    for sid in prof["my_subjects"]:
        with st.container(border=True, key=f"card_prof_{sid}"):
            a, b = st.columns([0.75, 0.25], vertical_alignment="center")
            a.markdown(f"<span class='dot' style='--c:{T.SUBJECT_COLOURS[sid]}'></span> **{T.esc(store.SUBJECTS[sid]['name'])}**"
                       f"<div class='rowdesc'>{T.esc(subject_summary(acts, sid))}</div>", unsafe_allow_html=True)
            with b:
                nav.link("Open", key=f"prof_open_{sid}", width="stretch", s=sid)


def _details(user: dict, prof: dict, account: dict) -> None:
    st.markdown('<div class="h2">Your details</div>', unsafe_allow_html=True)
    with st.form("prof_details"):
        name = st.text_input("Name", value=prof["name"], max_chars=60, key="prof_name")
        if account["email"]:
            st.caption(f"Signed in with Google as {T.esc(account['email'])}")
        go = st.form_submit_button("Save name")
    if not go or name.strip() == prof["name"]:
        return
    try:
        prof["name"] = users.rename(user["username"], name)
    except users.AccountError as err:
        st.error(str(err))
        return
    store.save_profile(prof)
    st.session_state[users.SESSION_KEY] = {**user, "name": prof["name"]}
    st.toast("Name saved")
    st.rerun()


def _security(user: dict) -> None:
    st.markdown('<div class="h2">Password</div>', unsafe_allow_html=True)
    with st.form("prof_password", clear_on_submit=True):
        current = st.text_input("Current password", type="password", key="prof_pw_current", autocomplete="current-password")
        new = st.text_input(f"New password (at least {users.MIN_PASSWORD} characters)", type="password", key="prof_pw_new", autocomplete="new-password")
        again = st.text_input("New password again", type="password", key="prof_pw_again", autocomplete="new-password")
        go = st.form_submit_button("Change password")
    if go:
        if new != again:
            st.error("The two new passwords are different.")
            return
        try:
            changed = users.change_password(user["username"], current, new)
        except users.AccountError as err:
            st.error(str(err))
            return
        if not changed:
            st.error("That isn't your current password.")
            return
        login.renew_session(user["username"])
        st.toast("Password changed. Any other devices have been signed out.")
        st.rerun()
    token = st.session_state.get(login.TOKEN_KEY)
    others = users.other_sessions(user["username"], token)
    if others and st.button(f"Sign out {others} other device{'s' if others != 1 else ''}", key="prof_sign_out_others", icon=":material/devices:"):
        users.end_other_sessions(user["username"], token)
        st.toast("Other devices signed out")
        st.rerun()


def _your_data(user: dict, today: date) -> None:
    st.markdown('<div class="h2">Your data</div>', unsafe_allow_html=True)
    st.caption("A copy of your calendar, routine, attempts, notes and bookmarks. Books and past papers aren't included.")
    st.download_button("Download my data", data=export_zip(), file_name=f"ib-tee-{user['username']}-{today.isoformat()}.zip", mime="application/zip",
                       key="prof_export", icon=":material/download:", on_click="ignore", width="stretch")
