"""
The student's weekly routine (from documents to process/Planning Arturo (Calendar).pdf), turned into calendar sessions.

    data/routine.json   {"days": {"0": [block, ...], ... "6": [...]}, "tasks": {"0": [task, ...]}, "source": ...}
    block = {"start": "HH:MM", "minutes": n, "kind": "school|routine|study|review|busy", "subject": key, "title": str, "note": str}
    task  = {"title": str, "subject": key, "note": str}            (no fixed time: a to-do for that day)

The routine fills the calendar ahead (apply()); every generated session can be edited or deleted on its own, and edited ones are
never regenerated. Changing the routine re-creates only future, untouched, unfinished routine sessions (reapply()).
Maths slots carry the Maths sub-topic rotation (maths.schedule.interleaved_chunks), so the Maths learning content stays attached.
"""
from __future__ import annotations

import calendar as _cal
import copy
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from ibtee import users

ROOT = Path(__file__).resolve().parents[1]
ROUTINE = ROOT / "data" / "routine.json"
PROGRAMME = "Weekly routine"
SOURCE = "documents to process/Planning Arturo (Calendar).pdf"

# key -> (label, colour)
SUBJECTS = {
    "maths": ("Maths", "#5B6CF0"), "chemistry": ("Chemistry", "#E4572E"), "biology": ("Biology", "#2FA35F"),
    "english": ("English", "#C9A227"), "psychology": ("Psychology", "#9B59D0"), "spanish": ("Spanish (Lengua)", "#E0709B"),
    "ia": ("IA", "#0E9384"), "global_issue": ("Global Issue", "#3A8DB8"), "choir": ("Choir", "#7C6FB0"),
    "physics": ("Physics", "#2563EB"), "history": ("History", "#A16207"), "economics": ("Economics", "#15803D"), "geography": ("Geography", "#0F766E"),
    "business": ("Business", "#B45309"), "computer_science": ("Computer Science", "#4F46E5"), "french": ("French", "#DB2777"), "art": ("Visual Arts", "#C026D3"),
    "tok": ("TOK", "#475569"), "ee": ("Extended Essay", "#0369A1"),
    "general": ("General", "#64748B"), "life": ("Life", "#94A3B8"), "school": ("School", "#CBD5E1"),
}
KINDS = ["study", "review", "mixed", "exam", "busy", "school", "routine", "break", "task"]
STUDY_KINDS = {"study", "review", "mixed", "exam"}
SHOWN_IN_MONTH = STUDY_KINDS | {"busy"}


def B(start, minutes, kind, subject, title, note=""):
    return {"start": start, "minutes": minutes, "kind": kind, "subject": subject, "title": title, "note": note}


def _weekday(s1, s2, long_):
    """A school day: the PDF's afternoon model with that day's two 30-min sessions and the 45-min one."""
    return [
        B("08:30", 420, "school", "school", "School"),
        B("13:00", 30, "study", "maths", "Maths at lunch: review this week's lessons and exercises",
          "Lunch break (1 h): 30 min of it. PDF: 'Todos los días patio repaso-ejercicios de Mates de lo que se está dando esa semana'") | {"rotation": False},
        B("15:30", 20, "routine", "life", "Travel home"),
        B("16:00", 60, "routine", "life", "Rest + get ready to study", "Descanso + activación para el estudio"),
        B("17:00", 15, "review", "general", "Mental review of today's lessons", "Repaso mental de lo dado en el día"),
        {**s1, "start": "17:15", "minutes": 30},
        {**s2, "start": "17:45", "minutes": 30},
        B("18:15", 60, "routine", "life", "Exercise (strength / walk-run) + shower / meditate",
          "Phone only during exercise breaks: calls/messages"),
        *([{**x, "start": t, "minutes": m} for x, t, m in long_]),
        B("20:00", 60, "routine", "life", "Dinner + podcast / music"),
        B("21:00", 60, "review", "chemistry", "Daily Chemistry review", "Repaso diario química"),
        B("22:00", 60, "routine", "life", "No phone or PC: music, composing, reading, meditation, wind down"),
    ]


def S(subject, title, note=""):
    return {"kind": "study", "subject": subject, "title": title, "note": note}


DEFAULT = {
    "source": SOURCE,
    "days": {
        "0": _weekday(S("biology", "Biology (short)", "Biología corta"), S("english", "English (long)", "Inglés larga"),
                      [(S("maths", "Maths"), "19:15", 45)]),
        "1": _weekday(S("psychology", "Psychology"), S("chemistry", "Chemistry"), [(S("maths", "Maths"), "19:15", 45)]),
        "2": _weekday(S("english", "English"), S("biology", "Biology"), [(S("spanish", "Spanish (Lengua)"), "19:15", 45)]),
        "3": _weekday(S("chemistry", "Chemistry"), S("maths", "Maths"),
                      [(S("biology", "Biology (short)", "Biolog corta"), "19:15", 22), (S("psychology", "Psychology (short)", "Psic corta"), "19:37", 23)]),
        "4": _weekday(S("chemistry", "Chemistry"), S("maths", "Maths"), [({"kind": "routine", "subject": "choir", "title": "Choir", "note": "Coro"}, "19:15", 45)]),
        "5": [
            B("10:00", 120, "routine", "choir", "Choir, then rest", "Mañana: Coro - descanso (times approximate)"),
            B("16:00", 90, "study", "english", "English literature", "Tarde 16:00-20:30: Inglés 1,5 h literatura"),
            B("17:30", 90, "study", "english", "English language", "Inglés 1,5 h lengua"),
            B("19:00", 90, "study", "spanish", "Spanish (Lengua)", "Lengua 1,5 h"),
        ],
        "6": [
            B("08:30", 60, "study", "maths", "Maths", "Mañana 8:30-13:30"),
            B("09:30", 60, "study", "chemistry", "Chemistry"),
            B("10:30", 60, "study", "biology", "Biology"),
            B("11:30", 120, "study", "ia", "IA (internal assessments)"),
            B("16:00", 120, "study", "global_issue", "Global Issue (if not done in the week)", "Tarde: Global Issue?"),
            B("18:00", 120, "routine", "life", "Walk / meet friends", "Paseo (quedar amigos?)"),
        ],
    },
    "tasks": {
        "0": [{"title": "Global Issue: 2 h this week in free periods at school", "subject": "global_issue", "note": "Hacer en el colegio en ratos libres"}],
        "6": [{"title": "Review last week", "subject": "general", "note": "Análisis semana pasada"},
              {"title": "Plan next week: check calendar events and deadlines", "subject": "general", "note": "Programar semana siguiente"},
              {"title": "House jobs: washing, tidy room, help at home", "subject": "life", "note": "Tareas casa"},
              {"title": "Calls / messages (during gym time): Alex, Félix, Mavi, Miriam, SL", "subject": "life", "note": "Llamadas/wasaps"}],
    },
}


def load(path: Path | None = None) -> dict:
    path = users.scoped(path or ROUTINE)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"days": {}, "tasks": {}} if users.guest_id() else copy.deepcopy(DEFAULT)       # DEFAULT is the owner's own week


def save(routine: dict, path: Path | None = None) -> None:
    path = users.scoped(path or ROUTINE)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(routine, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    users.saved(path)


def label(subject: str | None) -> str:
    return SUBJECTS.get(subject or "maths", (subject or "", ""))[0]


def colour(subject: str | None) -> str:
    return SUBJECTS.get(subject or "maths", ("", "#94A3B8"))[1]


def subject_of(s: dict) -> str:
    """Sessions made before subjects existed are all Maths."""
    return s.get("subject") or "maths"


def horizon(today: date) -> date:
    """The routine is kept filled to the end of next month."""
    y, m = (today.year + (today.month == 12), today.month % 12 + 1)
    return date(y, m, _cal.monthrange(y, m)[1])


def _overlaps(a_start: datetime, a_min: int, b_start: datetime, b_min: int) -> bool:
    return a_start < b_start + timedelta(minutes=b_min) and b_start < a_start + timedelta(minutes=a_min)


def apply(cal: dict, now: datetime, until: date | None = None, routine: dict | None = None) -> int:
    """Create routine sessions from now to `until`. A block is skipped when it is already there, when its time has passed, or when it
    would overlap something planned on purpose (a special programme, an event, or anything added or edited by hand)."""
    from maths import schedule
    routine = routine or load()
    until = until or horizon(now.date())
    have = {s.get("tpl") for s in cal["sessions"] if s.get("tpl")}
    fixed = [s for s in cal["sessions"] if s.get("programme") != PROGRAMME or s.get("edited")]
    by_day: dict[str, list[dict]] = {}
    for s in fixed:
        by_day.setdefault(s["date"], []).append(s)
    chunks = schedule.interleaved_chunks()
    k = int(cal.get("maths_rotation", 0))
    added = 0
    d = now.date()
    while d <= until:
        iso = d.isoformat()
        for i, b in enumerate(routine["days"].get(str(d.weekday()), [])):
            key = f"{iso}|{i}|{b['start']}|{b['title']}"
            start = schedule.at(iso, b["start"])
            if key in have or start < now:
                continue
            clash = [x for x in by_day.get(iso, []) if not x.get("unscheduled") and x["kind"] not in ("break", "task", "school")
                     and _overlaps(start, b["minutes"], schedule.at(x["date"], x["start"]), int(x["minutes"]))]
            if clash and b["kind"] != "school":
                continue
            codes, title, objective = [], b["title"], b.get("note", "")
            backlog = None
            if b["subject"] == "maths" and b["kind"] == "study" and b.get("rotation", True):
                if cal.get("maths_backlog"):                # work moved out of earlier slots comes first
                    backlog = cal["maths_backlog"].pop(0)
                    codes, title, objective = backlog["subtopics"] or [], backlog["title"], backlog["objective"] or ""
                else:
                    codes = chunks[k % len(chunks)]
                    k += 1
                    title, objective = schedule.chunk_title(codes)
                    title = f"Maths · {title}"
            s = schedule.session(iso, b["start"], b["minutes"], b["kind"], title, objective, codes, PROGRAMME)
            if backlog:
                s.update({"calculator": backlog.get("calculator") or s["calculator"], "questions": backlog.get("questions") or s["questions"],
                          "moved_from": backlog.get("moved_from"), "edited": bool(backlog.get("moved_from"))})
            s.update({"subject": b["subject"], "tpl": key, "note": b.get("note", ""), "rotation": b.get("rotation", True)})
            cal["sessions"].append(s)
            added += 1
        for j, t in enumerate(routine.get("tasks", {}).get(str(d.weekday()), [])):
            key = f"{iso}|task{j}|{t['title']}"
            if key in have or d < now.date():
                continue
            s = schedule.session(iso, "00:00", 0, "task", t["title"], t.get("note", ""), [], PROGRAMME)
            s.update({"subject": t.get("subject", "general"), "tpl": key, "note": t.get("note", "")})
            cal["sessions"].append(s)
            added += 1
        d += timedelta(days=1)
    cal["maths_rotation"] = k
    cal["routine_until"] = until.isoformat()
    return added


def reapply(cal: dict, now: datetime, routine: dict) -> tuple[int, int]:
    """After the routine changes: drop future routine sessions nobody touched, then fill again. Returns (removed, added)."""
    keep, removed = [], 0
    for s in cal["sessions"]:
        future = s["date"] > now.date().isoformat() or (s["date"] == now.date().isoformat() and s["start"] > now.strftime("%H:%M"))
        if s.get("programme") == PROGRAMME and future and not s.get("done") and not s.get("edited") and not s.get("moved_from"):
            removed += 1
            continue
        keep.append(s)
    cal["sessions"] = keep
    return removed, apply(cal, now, routine=routine)


PAYLOAD = ("title", "objective", "subtopics", "calculator", "questions", "moved_from")


def _payload(s: dict) -> dict:
    return {k: copy.deepcopy(s.get(k)) for k in PAYLOAD}


def maths_slots(cal: dict, now: datetime) -> list[dict]:
    """Future, unfinished routine Maths slots that carry sub-topic work (not the lunch review), in time order."""
    from maths import schedule
    return sorted((s for s in cal["sessions"] if s.get("programme") == PROGRAMME and subject_of(s) == "maths" and s["kind"] == "study"
                   and s.get("rotation", True) and not s.get("done") and schedule.status(s, now) == "upcoming"),
                  key=lambda s: (s["date"], s["start"]))


def carry_into_maths_slots(cal: dict, displaced: list[dict], now: datetime) -> list[tuple[dict, dict]]:
    """Put unfinished Maths blocks into later routine Maths slots without losing anything: each block goes to the first slot after
    its own time, and whatever that slot held moves on to the next slot, in a chain. What no slot can hold any more waits in
    cal["maths_backlog"] and fills the next Maths slots the routine creates. The originals are removed. Returns (old, slot) pairs."""
    from collections import deque
    from maths import schedule
    pending = sorted(displaced, key=lambda o: (o["date"], o["start"]))
    when = lambda x: schedule.at(x["date"], x["start"])
    slots = [s for s in maths_slots(cal, now) if pending and when(s) > when(pending[0])]
    bumped: deque = deque()
    pairs = []
    for slot in slots:
        bumped.append(_payload(slot))
        d = next((o for o in pending if when(o) < when(slot)), None)
        if d:
            pending.remove(d)
            slot.update({k: copy.deepcopy(d.get(k)) for k in ("objective", "subtopics", "calculator", "questions")})
            slot["title"] = d["title"] if d["title"].startswith("Maths · ") else f"Maths · {d['title']}"
            slot["moved_from"] = d.get("moved_from") or f"{d['date']} {d['start']}"
            pairs.append((d, slot))
        else:
            slot.update(bumped.popleft())
        slot["edited"] = True
    cal.setdefault("maths_backlog", [])
    cal["maths_backlog"] = list(bumped) + cal["maths_backlog"]
    for d in pending:                                  # no later slot at all (end of the filled calendar): keep it for later
        cal["maths_backlog"].append(_payload(d) | {"title": d["title"], "moved_from": f"{d['date']} {d['start']}"})
    gone = {id(o) for o in displaced}
    cal["sessions"] = [s for s in cal["sessions"] if id(s) not in gone]
    return pairs


def clear_for_event(cal: dict, ev: dict, now: datetime, catch_up_day: str | None = None) -> dict:
    """Make room for an event (rehearsal, concert…): overlapping routine blocks (rest, exercise, mental review) are removed;
    overlapping unfinished study sessions are kept, never lost: Maths goes to the next Maths slots, any other subject becomes a
    "Catch up" to-do on catch_up_day (default: the event's own day). School and to-dos are left alone.
    Returns {"removed": [...], "maths": [(old, slot)], "todos": [...]}."""
    from maths import schedule
    start, mins = schedule.at(ev["date"], ev["start"]), int(ev["minutes"])
    hit = [s for s in cal["sessions"] if s is not ev and s["date"] == ev["date"] and s["kind"] not in ("school", "task", "busy")
           and not s.get("done") and _overlaps(start, mins, schedule.at(s["date"], s["start"]), int(s["minutes"]))]
    removed = [s for s in hit if s["kind"] in ("routine", "break") or (s["kind"] == "review" and subject_of(s) == "general")]
    study = [s for s in hit if s not in removed]
    maths = [s for s in study if subject_of(s) == "maths"]
    others = [s for s in study if s not in maths]
    gone = {id(s) for s in removed + others}
    cal["sessions"] = [s for s in cal["sessions"] if id(s) not in gone]
    pairs = carry_into_maths_slots(cal, maths, now) if maths else []
    left = [o for o in maths if o not in [p[0] for p in pairs]]
    todos = []
    for s in others + left:
        t = schedule.session(catch_up_day or ev["date"], "00:00", 0, "task", f"Catch up: {s['title']} ({s['minutes']} min)",
                             s.get("objective", ""), s.get("subtopics", []), "Added by hand")
        t.update({"subject": subject_of(s), "edited": True,
                  "note": f"Moved from {s['date']} {s['start']} because of {ev['title']}", "moved_from": f"{s['date']} {s['start']}"})
        cal["sessions"].append(t)
        todos.append(t)
    return {"removed": removed, "maths": pairs, "todos": todos}


def is_habit(s: dict) -> bool:
    """Daily routine blocks (mental review, daily Chemistry review, lunch review): skipping one leaves nothing to catch up on."""
    return s.get("programme") == PROGRAMME and not s.get("edited") and (s["kind"] == "review" or not s.get("rotation", True))


def missed_work(cal: dict, now: datetime, days: int = 7) -> list[dict]:
    """Study sessions of the last `days` days that ended without being ticked, oldest first. Daily habits are left out."""
    from maths import schedule
    since = (now.date() - timedelta(days=days)).isoformat()
    return sorted((s for s in cal["sessions"] if s["kind"] in STUDY_KINDS and s["date"] >= since and not is_habit(s)
                   and schedule.status(s, now) == "missed"), key=lambda s: (s["date"], s["start"]))


def rescue_missed(cal: dict, ids: set[str], now: datetime, day: str) -> dict:
    """Move the chosen missed sessions forward without losing them: Maths sub-topic blocks go into the next Maths slots (never over
    what those slots hold: see carry_into_maths_slots); anything else becomes a "Catch up" to-do on `day`.
    Returns {"maths": [(old, slot)], "todos": [...]}."""
    from maths import schedule
    chosen = [s for s in missed_work(cal, now, days=3650) if s["id"] in ids]
    maths = [s for s in chosen if subject_of(s) == "maths" and s["kind"] == "study" and s.get("subtopics")]
    others = [s for s in chosen if s not in maths]
    pairs = carry_into_maths_slots(cal, maths, now) if maths else []
    gone = {id(s) for s in others}
    cal["sessions"] = [s for s in cal["sessions"] if id(s) not in gone]
    todos = []
    for s in others:
        t = schedule.session(day, "00:00", 0, "task", f"Catch up: {s['title']} ({s['minutes']} min)", s.get("objective", ""), s.get("subtopics", []),
                             "Added by hand")
        t.update({"subject": subject_of(s), "edited": True, "note": f"Missed on {s['date']} at {s['start']}", "moved_from": f"{s['date']} {s['start']}"})
        if s.get("chem_topic"):
            t["chem_topic"] = s["chem_topic"]
        cal["sessions"].append(t)
        todos.append(t)
    return {"maths": pairs, "todos": todos}


def clashes(cal: dict, day: str, start: str, minutes: int) -> list[dict]:
    """What is already planned at that time (to-dos and breaks take no time on the calendar)."""
    from maths import schedule
    at = schedule.at(day, start)
    return [s for s in cal["sessions"] if s["date"] == day and s["kind"] not in ("task", "break") and not s.get("unscheduled")
            and _overlaps(at, minutes, schedule.at(s["date"], s["start"]), int(s["minutes"]))]


def next_free(cal: dict, now: datetime, minutes: int = 45, horizon_days: int = 60) -> tuple[str, str] | None:
    """The first free time from tomorrow: after school on weekdays, from 09:00 at weekends, ending by 21:30."""
    for i in range(1, horizon_days):
        d = now.date() + timedelta(days=i)
        hour, minute = (16, 0) if d.weekday() < 5 else (9, 0)
        t = datetime(d.year, d.month, d.day, hour, minute)
        while t + timedelta(minutes=minutes) <= datetime(d.year, d.month, d.day, 21, 30):
            if not clashes(cal, d.isoformat(), f"{t:%H:%M}", minutes):
                return d.isoformat(), f"{t:%H:%M}"
            t += timedelta(minutes=15)
    return None


def place_backlog(cal: dict, index: int, day: str, start: str, minutes: int, now: datetime) -> dict:
    """Give a waiting Maths block its own time. Raises ValueError (with the reason) if the time has passed or is taken."""
    from maths import schedule
    waiting = cal.get("maths_backlog") or []
    if not 0 <= index < len(waiting):
        raise ValueError("That block is no longer waiting.")
    if schedule.at(day, start) < now:
        raise ValueError("That time has already passed.")
    busy = clashes(cal, day, start, minutes)
    if busy:
        raise ValueError("That time is taken by: " + ", ".join(f"{b['start']} {b['title']}" for b in busy[:3]))
    b = waiting.pop(index)
    title = b["title"] if b["title"].startswith("Maths · ") else f"Maths · {b['title']}"
    s = schedule.session(day, start, minutes, "study", title, b.get("objective") or "", b.get("subtopics") or [], "Added by hand")
    s.update({"subject": "maths", "edited": True, "moved_from": b.get("moved_from"), "calculator": b.get("calculator") or s["calculator"],
              "questions": b.get("questions") or s["questions"]})
    cal["sessions"].append(s)
    return s
