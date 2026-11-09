"""
First-run setup for a new student (subjects → timetable → exams and deadlines), and the Exams & deadlines view of the Calendar.

The answers become an ordinary weekly routine (ibtee/routine.py) and calendar sessions, so everything stays editable afterwards.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from ibtee import routine, store, users
from ibtee import theme as T

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
NOT_STUDIED = {"general", "life", "school", "choir", "ia", "global_issue"}
STUDY_SUBJECTS = {k: v[0] for k, v in routine.SUBJECTS.items() if k not in NOT_STUDIED}
ALL_SUBJECTS = {k: v[0] for k, v in routine.SUBJECTS.items() if k not in ("life", "school", "choir")}
LABEL_TO_KEY = {v: k for k, v in ALL_SUBJECTS.items()}
PROGRAMME = "My exams and deadlines"
GAP = 10                 # minutes between two study sessions
DAY_END = 22 * 60        # no study session runs past this


def _mins(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:])


def _hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


# --------------------------------------------------------------------------- answers → routine
def build_routine(a: dict) -> dict:
    """a = {"subjects": [keys], "courses": [subject ids], "school": {"0": {"start", "end"}}, "activities": [{"day", "start", "minutes", "title"}],
            "weekday_start", "weekday_sessions", "weekend_start", "weekend_sessions", "minutes"}.
    School and activities are fixed; study sessions fill the free time from the chosen start, taking the subjects in turn over the week."""
    days: dict[str, list[dict]] = {str(d): [] for d in range(7)}
    taken: dict[int, list[tuple[int, int]]] = {d: [] for d in range(7)}
    for d in range(7):
        s = a["school"].get(str(d))
        if s:
            days[str(d)].append(routine.B(s["start"], _mins(s["end"]) - _mins(s["start"]), "school", "school", "School"))
            taken[d].append((_mins(s["start"]), _mins(s["end"])))
    for x in a.get("activities", []):
        days[str(x["day"])].append(routine.B(x["start"], x["minutes"], "routine", "life", x["title"]))
        taken[x["day"]].append((_mins(x["start"]), _mins(x["start"]) + x["minutes"]))
    subjects, length, turn = a["subjects"], a["minutes"], 0
    for d in range(7):
        start, count = (a["weekday_start"], a["weekday_sessions"]) if d < 5 else (a["weekend_start"], a["weekend_sessions"])
        cursor, placed = _mins(start), 0
        while subjects and placed < count and cursor + length <= DAY_END:
            hit = [e for b, e in taken[d] if cursor < e and b < cursor + length]
            if hit:
                cursor = max(hit)
                continue
            key = subjects[turn % len(subjects)]
            block = routine.B(_hhmm(cursor), length, "study", key, routine.label(key))
            if key == "maths" and "maths_ai_hl" not in a["courses"]:     # the sub-topic rotation is the Maths AI HL course
                block["rotation"] = False
            days[str(d)].append(block)
            turn, placed, cursor = turn + 1, placed + 1, cursor + length + GAP
        days[str(d)].sort(key=lambda b: b["start"])
    return {"days": days, "tasks": {}}


def add_item(cal: dict, item: dict, now: datetime) -> dict:
    """Put one exam or deadline on the calendar. An exam takes its time from whatever overlaps it, without losing that work.
    item = {"type": "Exam"|"Deadline", "title", "subject", "date": iso, "start": "HH:MM", "minutes"}. Raises ValueError with the reason."""
    from maths import schedule
    label = f"“{item['title']}”"
    if item["type"] == "Deadline":
        if item["date"] < now.date().isoformat():
            raise ValueError(f"{label}: that date has passed.")
        s = schedule.session(item["date"], "00:00", 0, "task", f"Deadline: {item['title']}", "", [], PROGRAMME)
        s.update({"subject": item["subject"], "edited": True, "my_exam": True, "deadline": True})
        cal["sessions"].append(s)
        return s
    if schedule.at(item["date"], item["start"]) < now:
        raise ValueError(f"{label}: that time has passed.")
    if any(x["kind"] == "exam" for x in routine.clashes(cal, item["date"], item["start"], item["minutes"])):
        raise ValueError(f"{label} overlaps another exam.")
    s = schedule.session(item["date"], item["start"], item["minutes"], "exam", item["title"], "", [], PROGRAMME)
    s.update({"subject": item["subject"], "edited": True, "my_exam": True})
    cal["sessions"].append(s)
    routine.clear_for_event(cal, s, now)
    return s


def finish(a: dict, items: list[dict], now: datetime | None = None) -> None:
    """Save the setup: exams first, so the routine plans around them."""
    from maths import schedule
    now = now or schedule.now_local()
    cal = schedule.ensure_month(now)
    r = build_routine(a)
    for it in items:
        add_item(cal, it, now)
    routine.save(r)
    routine.reapply(cal, now, r)
    schedule.save(cal)
    prof = store.profile()
    prof["my_subjects"] = [s for s in a["courses"] if s in store.SUBJECTS]
    store.save_profile(prof)


# --------------------------------------------------------------------------- reading the tables
def _blank(v) -> bool:
    return v is None or (not isinstance(v, str) and pd.isna(v))


def _text(v) -> str:
    return "" if _blank(v) else str(v).strip()


def _time(raw) -> str:
    """"9:05" and "09:05" both become "09:05"; anything else stays as written and fails the check."""
    t = _text(raw).replace(".", ":")
    return f"0{t}" if re.match(r"^\d:\d\d$", t) else t


def read_school(df: pd.DataFrame) -> tuple[dict, list[str]]:
    school, problems = {}, []
    for d, r in enumerate(df.to_dict("records")):
        start, end = _time(r["starts"]), _time(r["ends"])
        if not start and not end:
            continue
        if not TIME.match(start) or not TIME.match(end) or _mins(end) <= _mins(start):
            problems.append(f"{DAYS[d]}: write school times as HH:MM, ending after they start")
            continue
        school[str(d)] = {"start": start, "end": end}
    return school, problems


def read_activities(df: pd.DataFrame) -> tuple[list[dict], list[str]]:
    out, problems = [], []
    for i, r in enumerate(df.to_dict("records"), 1):
        title, day, start = _text(r["what"]), _text(r["day"]), _time(r["start"])
        if not title and not day and not start:
            continue
        minutes = 0 if _blank(r["minutes"]) else int(r["minutes"])
        if not title or day not in DAYS or not TIME.match(start) or minutes <= 0:
            problems.append(f"Activity row {i}: it needs a day, a start (HH:MM), minutes and a name")
            continue
        out.append({"day": DAYS.index(day), "start": start, "minutes": minutes, "title": title})
    return out, problems


def item_form(key: str, now: datetime) -> dict | None:
    """One exam or deadline, when Add is pressed and it is complete. It keeps what was typed until the caller calls item_added()."""
    version = st.session_state.get(f"{key}_v", 0)
    k = f"{key}_{version}"
    with st.form(k, border=False):
        a, b, c = st.columns([0.26, 0.44, 0.3])
        kind = a.selectbox("Type", ["Exam", "Deadline"], key=f"{k}_type")
        title = b.text_input("What", placeholder="Physics Paper 1", max_chars=80, key=f"{k}_what")
        subject = c.selectbox("Subject", list(ALL_SUBJECTS.values()), index=list(ALL_SUBJECTS).index("general"), key=f"{k}_subject")
        d, e, f, g = st.columns([0.34, 0.22, 0.22, 0.22], vertical_alignment="bottom")
        day = d.date_input("Date", value=now.date() + timedelta(days=1), min_value=now.date(), format="DD/MM/YYYY", key=f"{k}_date")
        start = e.text_input("Start (exams)", value="09:00", max_chars=5, key=f"{k}_start")
        minutes = f.number_input("Minutes (exams)", min_value=5, max_value=480, value=120, step=5, key=f"{k}_minutes")
        go = g.form_submit_button("Add", width="stretch")
    if not go:
        return None
    title, start = title.strip(), _time(start)
    if not title:
        st.error("Write what it is, for example Physics Paper 1.")
        return None
    if kind == "Exam" and not TIME.match(start):
        st.error("Write the start time as HH:MM, for example 09:00.")
        return None
    return {"type": kind, "title": title, "subject": LABEL_TO_KEY[subject], "date": day.isoformat(), "start": start, "minutes": int(minutes)}


def item_added(key: str) -> None:
    """Empty the form (a new key makes a new form) and redraw."""
    st.session_state[f"{key}_v"] = st.session_state.get(f"{key}_v", 0) + 1
    st.rerun()


# --------------------------------------------------------------------------- the three steps
def wizard(user: dict) -> None:
    """Shown instead of the app until the student has finished it."""
    a = st.session_state.setdefault("ob", {})
    step = st.session_state.setdefault("ob_step", 1)
    _, mid, _ = st.columns([0.12, 0.76, 0.12])
    with mid:
        st.markdown(f'<div class="kicker">Step {step} of 3</div>', unsafe_allow_html=True)
        st.progress(step / 3)
        if step == 1:
            _step_subjects(user, a)
        elif step == 2:
            _step_timetable(a)
        else:
            _step_exams(user, a)


def _step_subjects(user: dict, a: dict) -> None:
    T.header(f"Hi {user['name']}, what are you studying?", sub="This sets up your own calendar. You can change all of it later.")
    with st.form("ob_subjects", border=False):
        picked = st.multiselect("Subjects to plan study time for", list(STUDY_SUBJECTS.values()),
                                default=[STUDY_SUBJECTS[k] for k in a.get("subjects", [])], key="ob_subject_pick")
        courses = st.multiselect("Revision courses to add", list(store.SUBJECTS), default=a.get("courses", []), key="ob_course_pick",
                                 format_func=lambda s: store.SUBJECTS[s]["name"], help="The subjects with question banks and notes in this app.")
        go = st.form_submit_button("Next", type="primary")
    if go:
        if not picked:
            st.error("Choose at least one subject.")
            return
        a.update(subjects=[LABEL_TO_KEY[p] for p in picked], courses=courses)
        st.session_state["ob_step"] = 2
        st.rerun()


def _step_timetable(a: dict) -> None:
    T.header("Your timetable", sub="School and regular activities are kept free. Study sessions go around them.")
    school = a.get("school_rows") or [{"day": d, "starts": "08:30" if i < 5 else "", "ends": "15:30" if i < 5 else ""} for i, d in enumerate(DAYS)]
    activities = a.get("activity_rows") or []
    with st.form("ob_timetable", border=False):
        st.markdown('<div class="h2">School hours</div>', unsafe_allow_html=True)
        st.caption("Leave a day empty if you have no school then.")
        school_df = st.data_editor(pd.DataFrame(school, columns=["day", "starts", "ends"]), key="ob_school", hide_index=True, width="stretch", disabled=["day"], column_config={
            "day": st.column_config.TextColumn("Day"),
            "starts": st.column_config.TextColumn("Starts", max_chars=5),
            "ends": st.column_config.TextColumn("Ends", max_chars=5),
        })
        st.markdown('<div class="h2">Regular activities</div>', unsafe_allow_html=True)
        st.caption("Sports, music, work: anything every week. Add a row for each.")
        activity_df = st.data_editor(
            pd.DataFrame(activities, columns=["day", "start", "minutes", "what"]).astype({"day": "object", "start": "object", "minutes": "float", "what": "object"}),
            key="ob_activities", num_rows="dynamic", hide_index=True, width="stretch", height=190, column_config={
                "day": st.column_config.SelectboxColumn("Day", options=DAYS, required=True),
                "start": st.column_config.TextColumn("Start", max_chars=5, help="HH:MM"),
                "minutes": st.column_config.NumberColumn("Minutes", min_value=5, max_value=720, step=5),
                "what": st.column_config.TextColumn("What", width="large"),
            })
        st.markdown('<div class="h2">When you like to study</div>', unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns(5)
        wd_start = c1.text_input("Weekdays from", value=a.get("weekday_start", "17:00"), max_chars=5, key="ob_wd_start")
        wd_n = c2.number_input("Sessions a weekday", 0, 8, value=a.get("weekday_sessions", 2), key="ob_wd_n")
        we_start = c3.text_input("Weekends from", value=a.get("weekend_start", "10:00"), max_chars=5, key="ob_we_start")
        we_n = c4.number_input("Sessions a weekend day", 0, 8, value=a.get("weekend_sessions", 3), key="ob_we_n")
        length = c5.number_input("Minutes each", 15, 180, value=a.get("minutes", 45), step=5, key="ob_len")
        go = st.form_submit_button("Next", type="primary")
    if st.button("Back", key="ob_back_2", type="tertiary"):
        st.session_state["ob_step"] = 1
        st.rerun()
    if go:
        sch, p1 = read_school(school_df)
        act, p2 = read_activities(activity_df)
        starts = {"Weekdays from": _time(wd_start), "Weekends from": _time(we_start)}
        p3 = [f"{k}: write the time as HH:MM" for k, v in starts.items() if not TIME.match(v)]
        if p1 + p2 + p3:
            st.error(" · ".join(p1 + p2 + p3))
            return
        a.update(school=sch, activities=act, weekday_start=starts["Weekdays from"], weekday_sessions=int(wd_n), weekend_start=starts["Weekends from"],
                 weekend_sessions=int(we_n), minutes=int(length), school_rows=school_df.to_dict("records"), activity_rows=activity_df.to_dict("records"))
        st.session_state["ob_step"] = 3
        st.rerun()


def _step_exams(user: dict, a: dict) -> None:
    from maths import schedule
    now = schedule.now_local()
    T.header("Exams and deadlines", sub="Add what you know now, one at a time. You can add more any time on the Calendar.")
    items = a.setdefault("items", [])
    new = item_form("ob_item", now)
    if new:
        try:
            trial = {"sessions": []}                 # the same checks the calendar makes, before it's added to the list
            for it in items + [new]:
                add_item(trial, it, now)
        except ValueError as err:
            st.error(str(err))
        else:
            items.append(new)
            item_added("ob_item")
    for i, it in enumerate(items):
        with st.container(border=True, key=f"card_ob_item_{i}_{len(items)}"):
            x, y = st.columns([0.85, 0.15], vertical_alignment="center")
            when = f"{date.fromisoformat(it['date']):%a %d %b %Y}" + (f" · {it['start']} · {it['minutes']} min" if it["type"] == "Exam" else "")
            x.markdown(f"**{T.esc(it['title'])}**<br><span class='muted'>{it['type']} · {T.esc(ALL_SUBJECTS[it['subject']])} · {when}</span>", unsafe_allow_html=True)
            if y.button("Remove", key=f"ob_rm_{i}_{len(items)}", type="tertiary"):
                items.pop(i)
                st.rerun()
    back, done = st.columns([0.2, 0.8])
    if back.button("Back", key="ob_back_3", type="tertiary"):
        st.session_state["ob_step"] = 2
        st.rerun()
    if not done.button("Finish and open my calendar", key="ob_finish", type="primary"):
        return
    try:
        finish(a, items, now)
    except ValueError as err:
        st.error(str(err))
        return
    users.set_onboarded(user["username"])
    st.session_state[users.SESSION_KEY] = {**user, "onboarded": True}
    for k in ("ob", "ob_step"):
        st.session_state.pop(k, None)
    st.query_params.clear()
    st.query_params["p"] = "calendar"
    st.rerun()


# --------------------------------------------------------------------------- Calendar → Exams & deadlines
def exams_panel(cal: dict, now: datetime) -> None:
    from maths import schedule
    today = now.date().isoformat()
    upcoming = sorted((s for s in cal["sessions"] if (s.get("my_exam") or s.get("mock")) and s["date"] >= today), key=lambda s: (s["date"], s["start"]))
    if not upcoming:
        T.empty("Nothing coming up", "Add your exams and deadlines below.")
    for s in upcoming:
        with st.container(border=True, key=f"card_exam_{s['id']}"):
            a, b = st.columns([0.85, 0.15], vertical_alignment="center")
            when = f"{date.fromisoformat(s['date']):%a %d %b %Y}" + ("" if s["kind"] == "task" else f" · {s['start']} · {s['minutes']} min")
            a.markdown(f"**{T.esc(s['title'])}**<br><span class='muted'>{T.esc(routine.label(routine.subject_of(s)))} · {when}</span>", unsafe_allow_html=True)
            if s.get("my_exam") and b.button("Remove", key=f"exam_rm_{s['id']}", type="tertiary"):
                schedule.remove(cal, s["id"])
                schedule.save(cal)
                st.rerun()
    st.markdown('<div class="h2">Add more</div>', unsafe_allow_html=True)
    new = item_form("exam_add", now)
    if not new:
        return
    try:
        add_item(cal, new, now)
    except ValueError as err:
        st.error(str(err))
        return
    schedule.save(cal)
    st.toast("Added to your calendar")
    item_added("exam_add")
