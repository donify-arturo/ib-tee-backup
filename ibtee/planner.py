"""
The Calendar page (main menu): every subject's sessions, school, routine and events, all editable.

    Calendar  month or week board (ibtee/calendar_view.py): choosing a day shows its tasks at once, without reloading
              "Edit this day" opens the day's editable table below the board
    Routine   the weekly routine from the student's planning PDF, editable; saving refreshes the future routine sessions

Data: data/maths/calendar.json (maths.schedule) and data/routine.json (ibtee.routine).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from ibtee import calendar_view as cv
from ibtee import nav, routine
from ibtee import theme as T

SUBJECT_KEYS = list(routine.SUBJECTS)
SUBJECT_LABELS = {k: v[0] for k, v in routine.SUBJECTS.items()}
LABEL_TO_KEY = {v: k for k, v in SUBJECT_LABELS.items()}
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _schedule():
    from maths import schedule
    return schedule


# --------------------------------------------------------------------------- page
def page(view: str = "month", month_key: str | None = None, day: str | None = None) -> None:
    schedule = _schedule()
    now = schedule.now_local()
    cal = schedule.ensure_month(now)
    T.crumbs("Calendar")
    T.header("Calendar", kicker="All subjects · your weekly routine + revision plan",
             sub=f"Times in Atlantic/Canary · now {now:%a %d %b, %H:%M}. Click a day to see its tasks; tick them off right there.")
    current = view if view in ("routine", "exams") else "calendar"
    labels = {"calendar": "Calendar", "routine": "Weekly routine", "exams": "Exams & deadlines"}
    pick = st.segmented_control("View", list(labels), default=current, format_func=labels.get, key=f"vs_planner_{current}",
                                label_visibility="collapsed")
    if pick and pick != current:
        nav.go(p="calendar", v=pick if pick != "calendar" else "month")
    if current == "routine":
        routine_editor(cal, now)
        return
    if current == "exams":
        from ibtee import onboarding
        onboarding.exams_panel(cal, now)
        return
    first = day or (f"{month_key}-01" if month_key and month_key != now.strftime("%Y-%m") else now.date().isoformat())
    board_section("cal_board", view=view, day=first)


def act(cal: dict, action: dict) -> None:
    """Ticks are saved at once; "open" leaves the calendar for the session's page."""
    schedule = _schedule()
    if action["action"] == "done":
        schedule.update(cal, action["id"], done=bool(action["done"]))
        schedule.save(cal)
    elif action["action"] == "open":
        s = next((x for x in cal["sessions"] if x["id"] == action["id"]), None)
        if not s:
            return
        if routine.subject_of(s) == "maths":
            nav.go(s="maths_ai_hl", p="session", ss=s["id"])
        else:
            page_name, state = chemistry_target(s)
            st.session_state.update(state)
            st.session_state["page"] = page_name
            nav.go(s="chem_hl", p=page_name)


@st.fragment
def board_section(key: str, view: str = "month", day: str | None = None, compact: bool = False) -> None:
    """The board and, under it, the day being edited. A fragment: an action here reruns only this part of the page."""
    from ibtee import store
    schedule = _schedule()
    now = schedule.now_local()
    cal = schedule.load()
    action = cv.new_action(key)                        # handled before drawing, so the board gets fresh data
    if action:
        if action["action"] == "edit":
            if compact:                                # Home has no table: the Calendar page opens on that day's editor
                st.session_state["cal_board_edit"] = action["day"]
                nav.go(p="calendar", m=action["day"][:7], d=action["day"])
            st.session_state[f"{key}_edit"] = action["day"]
        else:
            act(cal, action)
    edit_day = st.session_state.get(f"{key}_edit")
    cv.board(cv.payload(cal, now, store.profile().get("theme", "light"), view=view, day=edit_day or day, edit_day=edit_day, compact=compact), key)
    if edit_day and not compact:
        if st.button("Close the editor", key=f"{key}_close", icon=":material/close:", type="tertiary"):
            del st.session_state[f"{key}_edit"]
            st.rerun(scope="fragment")
        day_editor(cal, edit_day, now)
    if not compact:
        catch_up_panel(cal, now, key)


def catch_up_panel(cal: dict, now: datetime, key: str) -> None:
    """Under the board: missed sessions to move forward, and Maths blocks that have no slot yet."""
    schedule = _schedule()
    missed = routine.missed_work(cal, now)
    if missed:
        with st.expander(f"Missed in the last week: {len(missed)} session{'s' * (len(missed) != 1)} to move", icon=":material/event_repeat:"):
            st.caption("Maths sub-topic blocks go into your next Maths slots, in order. Anything else becomes a “Catch up” to-do on the day you choose. "
                       "Untick what you don't want to move.")
            with st.form(f"{key}_missed", border=False):
                picks = {s["id"]: st.checkbox(f"{date.fromisoformat(s['date']):%a %d %b} {s['start']} · {routine.label(routine.subject_of(s))} · {s['title']}",
                                              value=True, key=f"{key}_m_{s['id']}") for s in missed}
                day = st.date_input("Put the catch-up to-dos on", value=now.date(), min_value=now.date(), format="DD/MM/YYYY", key=f"{key}_m_day")
                go = st.form_submit_button("Move the ticked sessions", type="primary")
            if go:
                done = routine.rescue_missed(cal, {i for i, on in picks.items() if on}, now, day.isoformat())
                schedule.save(cal)
                st.toast(f"Moved {len(done['maths'])} Maths block(s) · {len(done['todos'])} catch-up to-do(s)")
                st.rerun(scope="fragment")
    waiting = cal.get("maths_backlog") or []
    if waiting:
        with st.expander(f"Waiting for a slot: {len(waiting)} Maths block{'s' * (len(waiting) != 1)}", icon=":material/hourglass_top:"):
            st.caption(f"Your Maths slots up to {date.fromisoformat(cal.get('routine_until', now.date().isoformat())):%d %b} are full, so these will fill the next "
                       "ones the calendar creates. To do one sooner, give it its own time here.")
            free = routine.next_free(cal, now)
            for i, b in enumerate(waiting):
                with st.container(border=True, key=f"card_wait_{key}_{i}_{len(waiting)}"):
                    st.markdown(f"**{T.esc(b['title'])}**<br><span class='muted'>{T.esc(b.get('objective') or '')}</span>", unsafe_allow_html=True)
                    a, c, d, e = st.columns([0.34, 0.22, 0.2, 0.24], vertical_alignment="bottom")
                    start_day = date.fromisoformat(free[0]) if free else now.date() + timedelta(days=1)
                    when = a.date_input("Day", value=start_day, min_value=now.date(), format="DD/MM/YYYY", key=f"{key}_w_d_{i}_{len(waiting)}")
                    start = c.text_input("Start", value=free[1] if free else "16:00", key=f"{key}_w_s_{i}_{len(waiting)}")
                    mins = d.number_input("Minutes", min_value=15, max_value=240, value=45, step=15, key=f"{key}_w_m_{i}_{len(waiting)}")
                    if e.button("Put it in the calendar", key=f"{key}_w_b_{i}_{len(waiting)}", width="stretch"):
                        if not TIME.match(start.strip()):
                            st.error("Write the start time as HH:MM, for example 16:30.")
                            continue
                        try:
                            routine.place_backlog(cal, i, when.isoformat(), start.strip(), int(mins), now)
                        except ValueError as err:
                            st.error(str(err))
                            continue
                        schedule.save(cal)
                        st.toast("Added to the calendar")
                        st.rerun(scope="fragment")


# --------------------------------------------------------------------------- the day: everything, editable ("View more")
def day_frame(items: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "id": s["id"], "done": bool(s.get("done")), "start": "" if s["kind"] == "task" else s["start"], "minutes": int(s["minutes"]),
        "subject": SUBJECT_LABELS.get(routine.subject_of(s), "General"), "kind": s["kind"], "title": s["title"],
        "weekly review": bool(s.get("weekly_review")), "note": s.get("note") or s.get("objective") or "",
    } for s in items], columns=["id", "done", "start", "minutes", "subject", "kind", "title", "weekly review", "note"])


def day_editor(cal: dict, iso: str, now: datetime) -> None:
    schedule = _schedule()
    d = date.fromisoformat(iso)
    items = sorted((s for s in cal["sessions"] if s["date"] == iso), key=lambda s: (s["kind"] != "task", s["start"]))
    study = sum(s["minutes"] for s in items if s["kind"] in routine.STUDY_KINDS)
    label = "Today" if d == now.date() else "Past" if d < now.date() else ""
    st.markdown(f'<div class="h2">{d:%A %d %B} <span class="muted" style="font-size:0.95rem;font-weight:400">{label}'
                f'{" · " if label else ""}{study // 60} h {study % 60:02d} min of study · {len(items)} items</span></div>', unsafe_allow_html=True)
    st.caption("Everything planned this day. Edit any cell, tick Done, add a row at the bottom, or select rows and delete them; then Save. "
               "Leave Start empty for a to-do with no fixed time. Rows you edit are kept when your routine is refreshed.")
    df = day_frame(items)
    version = st.session_state.get("day_editor_version", 0)            # a new version after each save, so saved rows are not applied twice
    edited = st.data_editor(
        df, key=f"day_{iso}_{version}", num_rows="dynamic", hide_index=True, width="stretch", height=min(42 + 35 * (len(df) + 1), 760),
        column_config={
            "id": None,
            "done": st.column_config.CheckboxColumn("Done", width="small"),
            "start": st.column_config.TextColumn("Start", help="HH:MM, empty for a to-do", width="small", max_chars=5),
            "minutes": st.column_config.NumberColumn("Min", min_value=0, max_value=720, step=5, width="small"),
            "subject": st.column_config.SelectboxColumn("Subject", options=list(SUBJECT_LABELS.values()), required=True, width="medium"),
            "kind": st.column_config.SelectboxColumn("Type", options=routine.KINDS, required=True, width="small"),
            "title": st.column_config.TextColumn("Task", required=True, width="large"),
            "weekly review": st.column_config.CheckboxColumn("Weekly review", help="Your plan underlines the weekly review sessions", width="small"),
            "note": st.column_config.TextColumn("Notes", width="large"),
        })
    a, b = st.columns([0.25, 0.75], vertical_alignment="center")
    if a.button("Save changes", type="primary", key=f"save_{iso}", width="stretch"):
        problems = save_day(cal, iso, df, edited)
        if problems:
            b.error(" · ".join(problems))
        else:
            schedule.save(cal)
            st.session_state["day_editor_version"] = version + 1
            st.toast("Saved")
            st.rerun(scope="fragment")
    clash = [p for p in schedule.overlaps(cal) if any(s["id"] in p for s in items)]
    if clash:
        b.warning(f"{len(clash)} overlap(s) this day: check the start times and lengths.")


def chemistry_target(s: dict) -> tuple[str, dict]:
    """Where a Chemistry session opens: the Questionbank when its topic has a deck, otherwise the Study guide's questions."""
    from pathlib import Path
    topic = s.get("chem_topic")
    has_deck = bool(topic) and (Path(__file__).resolve().parents[1] / "data" / "techniques" / f"{topic}.json").exists()
    if not topic:
        return "Questionbank", {}
    return ("Questionbank", {"qb_topic": topic}) if has_deck else ("Study guide", {"sg_topic": topic})


def _clean(r: dict) -> dict:
    """A table row with blanks (NaN/None from a new row) turned into sensible values."""
    v = lambda k, default: default if r.get(k) is None or (isinstance(r.get(k), float) and pd.isna(r.get(k))) else r.get(k)
    return {"id": v("id", None), "done": bool(v("done", False)), "start": str(v("start", "")).strip(), "minutes": int(v("minutes", 30)),
            "subject": v("subject", "General"), "kind": v("kind", "study"), "title": str(v("title", "")).strip(),
            "weekly review": bool(v("weekly review", False)), "note": str(v("note", ""))}


def save_day(cal: dict, iso: str, before: pd.DataFrame, after: pd.DataFrame) -> list[str]:
    """Apply the table to the calendar: changed rows are updated (and marked edited), removed rows deleted, new rows added."""
    schedule = _schedule()
    problems = []
    rows = [_clean(r) for r in after.to_dict("records")]
    for i, r in enumerate(rows, 1):
        kind = r.get("kind") or "study"
        start = r["start"]
        if kind != "task" and not TIME.match(start):
            problems.append(f"row {i}: start must be HH:MM (or choose type 'task' for a to-do)")
        if not str(r.get("title") or "").strip():
            problems.append(f"row {i}: the task needs a name")
    if problems:
        return problems
    by_id = {s["id"]: s for s in cal["sessions"] if s["date"] == iso}
    kept, changed_busy = set(), set()
    for r in rows:
        kind = r["kind"]
        start = r["start"] if kind != "task" else "00:00"
        values = {"done": bool(r["done"]), "start": start, "minutes": r["minutes"], "kind": kind,
                  "subject": LABEL_TO_KEY.get(r["subject"], "general"), "title": str(r["title"]).strip(),
                  "weekly_review": bool(r.get("weekly review")), "note": str(r.get("note") or "")}
        rid = r.get("id")
        if isinstance(rid, str) and rid in by_id:
            s = by_id[rid]
            kept.add(rid)
            old = {k: s.get(k) for k in values}
            old["subject"] = routine.subject_of(s)
            old["note"] = s.get("note") or s.get("objective") or ""
            if old != values:
                if values["kind"] == "busy" and (old["start"], old["minutes"], old["kind"]) != (values["start"], values["minutes"], values["kind"]):
                    changed_busy.add(rid)
                s.update(values)
                s.pop("unscheduled", None)
                if (old["start"], old["minutes"], old["title"], old["kind"], old["subject"]) != (values["start"], values["minutes"], values["title"], values["kind"], values["subject"]):
                    s["edited"] = True
        else:
            s = schedule.session(iso, start, values["minutes"], kind, values["title"], values["note"],
                                 [], "Added by hand")
            s.update(values)
            s["edited"] = True
            cal["sessions"].append(s)
    cal["sessions"] = [s for s in cal["sessions"] if s["date"] != iso or s["id"] in kept or s["id"] not in by_id]
    # a new or moved event (type "busy") makes room for itself: overlapping study moves on, it is never lost
    now = schedule.now_local()
    for ev in [s for s in cal["sessions"] if s["date"] == iso and s["kind"] == "busy" and s.get("edited")
               and (s["id"] not in by_id or s["id"] in changed_busy)]:
        routine.clear_for_event(cal, ev, now)
    return []


# --------------------------------------------------------------------------- the weekly routine
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def routine_editor(cal: dict, now: datetime) -> None:
    schedule = _schedule()
    r = routine.load()
    source = r.get("source")
    st.caption((f"From your plan ({source.split('/')[-1]}). " if source else "") + "Change a day, then save: future routine sessions you haven't touched are "
               "rebuilt from it. Sessions you edited, finished, or that carry moved Maths work stay as they are.")
    tabs = st.tabs(DAYS)
    new_days, new_tasks = {}, {}
    for i, tab in enumerate(tabs):
        with tab:
            blocks = r["days"].get(str(i), [])
            df = pd.DataFrame([{"start": b["start"], "minutes": b["minutes"], "subject": SUBJECT_LABELS.get(b["subject"], "General"),
                                "kind": b["kind"], "title": b["title"], "note": b.get("note", ""),
                                "rotation": b.get("rotation", True)} for b in blocks],
                              columns=["start", "minutes", "subject", "kind", "title", "note", "rotation"])
            out = st.data_editor(df, key=f"rt_{i}", num_rows="dynamic", hide_index=True, width="stretch", height=min(42 + 35 * (len(df) + 1), 620), column_config={
                "start": st.column_config.TextColumn("Start", max_chars=5, width="small", required=True),
                "minutes": st.column_config.NumberColumn("Min", min_value=5, max_value=720, step=5, width="small", required=True),
                "subject": st.column_config.SelectboxColumn("Subject", options=list(SUBJECT_LABELS.values()), required=True),
                "kind": st.column_config.SelectboxColumn("Type", options=[k for k in routine.KINDS if k != "task"], required=True, width="small"),
                "title": st.column_config.TextColumn("Block", required=True, width="large"),
                "note": st.column_config.TextColumn("Notes", width="large"),
                "rotation": st.column_config.CheckboxColumn("Maths rotation", help="Maths blocks: fill with the next group of sub-topics", width="small"),
            })
            new_days[str(i)] = [{"start": str(x["start"]).strip(), "minutes": int(x["minutes"] or 0), "kind": x["kind"] or "study",
                                 "subject": LABEL_TO_KEY.get(x["subject"], "general"), "title": str(x["title"] or "").strip(),
                                 "note": str(x["note"] or ""), **({} if x.get("rotation", True) is not False else {"rotation": False})}
                                for x in out.to_dict("records") if str(x.get("title") or "").strip()]
            tasks = r.get("tasks", {}).get(str(i), [])
            st.markdown("<div class='kicker' style='margin-top:0.4rem'>To-dos for this day (no fixed time)</div>", unsafe_allow_html=True)
            tdf = pd.DataFrame([{"title": t["title"], "subject": SUBJECT_LABELS.get(t.get("subject"), "General"), "note": t.get("note", "")} for t in tasks],
                               columns=["title", "subject", "note"])
            tout = st.data_editor(tdf, key=f"rtt_{i}", num_rows="dynamic", hide_index=True, width="stretch", column_config={
                "title": st.column_config.TextColumn("To-do", required=True, width="large"),
                "subject": st.column_config.SelectboxColumn("Subject", options=list(SUBJECT_LABELS.values())),
                "note": st.column_config.TextColumn("Notes", width="large"),
            })
            new_tasks[str(i)] = [{"title": str(x["title"]).strip(), "subject": LABEL_TO_KEY.get(x["subject"], "general"), "note": str(x["note"] or "")}
                                 for x in tout.to_dict("records") if str(x.get("title") or "").strip()]
    bad = [f"{DAYS[int(d)]} {b['start']}" for d, bl in new_days.items() for b in bl if not TIME.match(b["start"])]
    if bad:
        st.error("Start times must be HH:MM: " + ", ".join(bad))
    if st.button("Save routine and refresh the calendar", type="primary", key="rt_save", disabled=bool(bad)):
        r["days"], r["tasks"] = new_days, new_tasks
        routine.save(r)
        removed, added = routine.reapply(cal, now, r)
        schedule.save(cal)
        st.toast(f"Routine saved: {removed} future sessions rebuilt as {added}")
        st.rerun()
