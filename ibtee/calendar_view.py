"""
The calendar board (calendar_component/index.html): month or week grid with the chosen day's tasks beside it. Choosing a day, a month
or Month/Week happens in the browser, so nothing reloads; only ticking a task, opening one or editing a day talks to Python.
Used on Home (compact) and on the calendar page (full).
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

import streamlit as st

from ibtee import routine
from ibtee import theme as T

BUSY = "#334155"


def dot_colour(s: dict) -> str:
    """Sessions are coloured by subject; events (rehearsals, concerts) are dark."""
    return BUSY if s["kind"] == "busy" else routine.colour(routine.subject_of(s))


def short(title: str) -> str:
    return title.replace("Number & Algebra", "N&A").replace("Geometry & Trigonometry", "Geo & Trig").replace("Statistics & Probability", "Stats & Prob")


def payload(cal: dict, now: datetime, mode: str = "light", view: str = "month", day: str | None = None, edit_day: str | None = None,
            compact: bool = False, can_edit: bool = True) -> dict:
    """Everything the board needs, sent once: it then works without the server."""
    from maths import schedule
    rows = []
    for s in cal["sessions"]:
        subject = routine.subject_of(s)
        study = s["kind"] in routine.STUDY_KINDS
        rows.append({"id": s["id"], "date": s["date"], "start": s["start"], "minutes": int(s["minutes"]), "kind": s["kind"], "title": s["title"],
                     "short": short(s["title"]), "detail": s.get("note") or s.get("objective") or "", "done": bool(s.get("done")),
                     "colour": dot_colour(s), "label": routine.label(subject), "status": schedule.status(s, now) if study else "",
                     "minor": int(s["kind"] == "review" or not s.get("rotation", True)),
                     "can_open": study and subject in ("maths", "chemistry")})
    return {"sessions": rows, "palette": T.PALETTES[mode if mode in T.PALETTES else "light"], "today": now.date().isoformat(), "view": view,
            "day": day, "edit_day": edit_day, "compact": compact, "can_edit": can_edit}


@lru_cache(maxsize=1)
def _component():
    import streamlit.components.v1 as components
    return components.declare_component("ib_calendar", path=str(Path(__file__).resolve().parents[1] / "calendar_component"))


def board(data: dict, key: str) -> dict | None:
    return _component()(data=data, key=key, default=None)


def new_action(key: str) -> dict | None:
    """The board's latest action, once: a component repeats its value on every rerun."""
    value = st.session_state.get(key)
    if not isinstance(value, dict) or st.session_state.get(f"{key}_seen") == value.get("n"):
        return None
    st.session_state[f"{key}_seen"] = value.get("n")
    return value
