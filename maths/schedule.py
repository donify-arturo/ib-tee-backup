"""
The revision calendar: editable study sessions with objectives, sub-topics, calculator sheets, questions, breaks and a done tick.

    data/maths/calendar.json   {"tz": "Atlantic/Canary", "created": ..., "sessions": [session, ...]}

A session: {"id", "date": "YYYY-MM-DD", "start": "HH:MM", "minutes", "kind": study|break|mixed|exam|review, "title", "objective",
            "subtopics": [...], "calculator": [sheet ids], "questions": [question ids], "done": bool, "programme": "..."}

Never schedules into the past: when the first programme is created, sessions whose time has gone are not created; their content is
carried into the first free slot of the same programme instead (Friday's Number & Algebra foundations move to Saturday).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from maths import data

DIR = data.DIR
CAL = DIR / "calendar.json"
TZ = "Atlantic/Canary"
DAY_START, DAY_END = "09:00", "22:00"
PROGRAMME = "First revision weekend (6–8 Nov 2026)"

# The student's plan: Friday N&A foundations; Saturday N&A, Functions, Geometry & Trigonometry; Sunday Statistics & Probability,
# then mixed-topic questions and timed exam practice. (day, block title, objective, sub-topics, minutes, kind)
FIRST_PROGRAMME = [
    ("2026-11-06", "Number & Algebra foundations I", "Sequences, standard form and accuracy: recall the formulas, then exam parts", ["1.1", "1.2", "1.3", "1.6"], 70, "study"),
    ("2026-11-06", "Number & Algebra foundations II", "Financial maths in the finance app: interest, depreciation, loans, annuities", ["1.4", "1.7"], 70, "study"),
    ("2026-11-06", "Number & Algebra foundations III", "Exponents, logarithms and systems of equations with the GDC", ["1.5", "1.8", "1.9", "1.10"], 50, "study"),
    ("2026-11-07", "Number & Algebra HL: complex numbers", "Cartesian, polar and Euler forms; equate real and imaginary parts", ["1.11", "1.12", "1.13"], 55, "study"),
    ("2026-11-07", "Number & Algebra HL: matrices and eigenvalues", "Inverses, systems, eigenvalues and diagonalization (Aⁿ = PDⁿP⁻¹)", ["1.14", "1.15"], 55, "study"),
    ("2026-11-07", "Functions: lines, features and models", "Choose and fit models; find key features with G-Solv", ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"], 60, "study"),
    ("2026-11-07", "Functions HL", "Composites, inverses, transformations, logistic and log models, linearizing", ["2.7", "2.8", "2.9", "2.10"], 50, "study"),
    ("2026-11-07", "Geometry & Trigonometry: triangles and 3D", "Trig rules, bearings, arcs, Voronoi diagrams, radians", ["3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8"], 60, "study"),
    ("2026-11-07", "Geometry & Trigonometry HL: vectors and graphs", "Vectors, kinematics, matrix transformations and graph algorithms", ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15", "3.16"], 60, "study"),
    ("2026-11-08", "Statistics & Probability: data and probability", "Descriptive statistics, regression, probability rules and distributions", ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9"], 80, "study"),
    ("2026-11-08", "Statistics & Probability HL: tests and models", "χ², t-tests, Poisson, CLT, confidence intervals, Type I/II, Markov chains", ["4.10", "4.11", "4.12", "4.13", "4.14", "4.15", "4.16", "4.17", "4.18", "4.19"], 80, "study"),
    ("2026-11-08", "Mixed-topic questions", "Recognise the method without being told the topic", [], 60, "mixed"),
    ("2026-11-08", "Timed exam practice (Paper 1 style)", "Full timed mock under exam conditions, then mark it", [], 120, "exam"),
    ("2026-11-08", "Error review", "Go through today's error log and retry what went wrong", [], 40, "review"),
]
BREAK_AFTER = {60: 10, 70: 15, 75: 15, 80: 15, 120: 20}
CATCH_UP_MINUTES = 60               # a programme day that is already over becomes one catch-up block on the next day
LONG_BREAK_AT = "13:30"              # lunch: a block that would start after this gets a 45-minute break first, once a day


def now_local() -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(TZ)).replace(tzinfo=None)


def hm(t: str) -> tuple[int, int]:
    h, m = t.split(":")
    return int(h), int(m)


def at(day: str, t: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), datetime.min.time()).replace(hour=hm(t)[0], minute=hm(t)[1])


def end_of(s: dict) -> datetime:
    return at(s["date"], s["start"]) + timedelta(minutes=int(s["minutes"]))


def round_up(dt: datetime, step: int = 15) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    return dt + timedelta(minutes=(-dt.minute) % step)


def load(path: Path | None = None) -> dict:
    path = path or CAL
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save(cal: dict, path: Path | None = None) -> None:
    path = path or CAL
    path.parent.mkdir(parents=True, exist_ok=True)
    cal["sessions"].sort(key=lambda s: (s["date"], s["start"]))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cal, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def resources(codes: list[str], kind: str, n_questions: int = 4) -> tuple[list[str], list[str]]:
    """(calculator sheet ids, question ids) that suit a block: easiest questions first, one per sub-topic before repeating."""
    sheets: list[str] = []
    for c in codes:
        for s in data.sheets_for(c):
            if s["id"] not in sheets:
                sheets.append(s["id"])
    qs: list[str] = []
    for round_ in range(3):
        for c in codes:
            pool = [q for q in data.questions_for(c, primary_only=True) if q["has_markscheme"] and q["id"] not in qs]
            if len(pool) > round_ and len(qs) < n_questions:
                qs.append(pool[min(round_, len(pool) - 1)]["id"])
    return sheets[:4], qs


def session(day: str, start: str, minutes: int, kind: str, title: str, objective: str = "", codes: list[str] | None = None,
            programme: str = "") -> dict:
    codes = codes or []
    sheets, qs = resources(codes, kind) if kind == "study" else ([], [])
    return {"id": uuid.uuid4().hex[:8], "date": day, "start": start, "minutes": int(minutes), "kind": kind, "title": title,
            "objective": objective, "subtopics": codes, "calculator": sheets, "questions": qs, "done": False, "programme": programme}


def plan_days(blocks: list[tuple], now: datetime, programme: str = PROGRAMME) -> list[dict]:
    """Lay blocks out day by day from DAY_START, with breaks, starting no earlier than now. Blocks of a day that is already over,
    or that cannot start before DAY_END, move to the next planned day (ahead of that day's own blocks)."""
    days = sorted({b[0] for b in blocks})
    carried: list[tuple] = []
    out: list[dict] = []
    for i, day in enumerate(days):
        todo = carried + [b for b in blocks if b[0] == day]
        carried = []
        cursor = max(at(day, DAY_START), round_up(now))
        end = at(day, DAY_END)
        if cursor.date() > date.fromisoformat(day):
            carried = todo
            continue
        lunch_done = cursor >= at(day, "15:00")
        for b in todo:
            _d, title, objective, codes, minutes, kind = b
            late = cursor >= at(day, LONG_BREAK_AT) or (cursor >= at(day, "12:45") and cursor + timedelta(minutes=minutes) > at(day, "14:30"))
            if not lunch_done and late:
                if out and out[-1]["kind"] == "break" and out[-1]["date"] == day:      # the short break becomes lunch
                    cursor -= timedelta(minutes=out.pop()["minutes"])
                out.append(session(day, cursor.strftime("%H:%M"), 45, "break", "Lunch break", programme=programme))
                cursor += timedelta(minutes=45)
                lunch_done = True
            if cursor + timedelta(minutes=minutes) > end:
                carried.append(b)
                continue
            out.append(session(day, cursor.strftime("%H:%M"), minutes, kind, title, objective, codes, programme))
            cursor += timedelta(minutes=minutes)
            brk = BREAK_AFTER.get(minutes, 10)
            if cursor + timedelta(minutes=brk) < end:
                out.append(session(day, cursor.strftime("%H:%M"), brk, "break", "Break", programme=programme))
                cursor += timedelta(minutes=brk)
        if i == len(days) - 1 and carried:     # nothing after the last day: keep them, unscheduled, at the end of it
            for b in carried:
                out.append({**session(day, DAY_END, b[4], b[5], b[1], b[2], b[3], programme), "unscheduled": True})
    # a trailing break at the end of a day is useless
    cleaned = []
    for k, s in enumerate(out):
        nxt = out[k + 1] if k + 1 < len(out) else None
        if s["kind"] == "break" and (nxt is None or nxt["date"] != s["date"]):
            continue
        cleaned.append(s)
    return cleaned


def ensure(now: datetime | None = None, path: Path | None = None) -> dict:
    path = path or CAL
    """The calendar, creating the first programme on first use."""
    cal = load(path)
    if cal.get("sessions") is not None:
        return cal
    now = now or now_local()
    blocks = []
    for day in sorted({b[0] for b in FIRST_PROGRAMME}):
        mine = [b for b in FIRST_PROGRAMME if b[0] == day]
        if at(day, DAY_END) <= now:          # a whole day already gone: its blocks become one catch-up block, not a backlog
            codes = [c for b in mine for c in b[3]]
            blocks.append((day, f"Catch-up: {mine[0][1].rsplit(' ', 1)[0] if len(mine) > 1 else mine[0][1]}",
                           "Missed on " + date.fromisoformat(day).strftime("%A") + ": recall the key formulas, then one question per sub-topic",
                           codes, CATCH_UP_MINUTES, "study"))
        else:
            blocks += mine
    cal = {"tz": TZ, "created": now.strftime("%Y-%m-%d %H:%M"), "programme": PROGRAMME,
           "note": "Created from the plan: Fri Number & Algebra foundations; Sat Number & Algebra, Functions, Geometry & Trigonometry; "
                   "Sun Statistics & Probability, then mixed-topic and timed exam practice. Time already gone when it was created was skipped.",
           "sessions": plan_days(blocks, now)}
    save(cal, path)
    return cal


def status(s: dict, now: datetime) -> str:
    """done | now | upcoming | missed | unscheduled"""
    if s.get("done"):
        return "done"
    if s.get("unscheduled"):
        return "unscheduled"
    start, end = at(s["date"], s["start"]), end_of(s)
    if end <= now:
        return "missed"
    if start <= now < end:
        return "now"
    return "upcoming"


def replan_from_now(cal: dict, now: datetime) -> int:
    """Move every unfinished study block that is missed or unscheduled to the next free time, keeping their order. Returns how many moved."""
    pending = [s for s in cal["sessions"] if s["kind"] != "break" and status(s, now) in ("missed", "unscheduled")]
    if not pending:
        return 0
    keep = [s for s in cal["sessions"] if s not in pending and not (s["kind"] == "break" and status(s, now) in ("missed", "upcoming"))]
    future = sorted((s for s in keep if s["kind"] != "break" and status(s, now) == "upcoming"), key=lambda s: (s["date"], s["start"]))
    blocks = [(now.date().isoformat(), s["title"], s["objective"], s["subtopics"], s["minutes"], s["kind"]) for s in pending]
    blocks += [(s["date"], s["title"], s["objective"], s["subtopics"], s["minutes"], s["kind"]) for s in future]
    rest = [s for s in keep if s not in future]
    old = {(s["title"], s["kind"]): s for s in pending + future}
    new = plan_days(blocks, now, cal.get("programme", PROGRAMME))
    for s in new:          # keep ids, resources and edits of the blocks that moved
        prev = old.get((s["title"], s["kind"]))
        if prev and s["kind"] != "break":
            s.update({k: prev[k] for k in ("id", "calculator", "questions", "objective", "subtopics")})
    cal["sessions"] = rest + new
    return len(pending)


def update(cal: dict, sid: str, **changes) -> None:
    for s in cal["sessions"]:
        if s["id"] == sid:
            s.update(changes)
            s.pop("unscheduled", None) if "start" in changes or "date" in changes else None


def remove(cal: dict, sid: str) -> None:
    cal["sessions"] = [s for s in cal["sessions"] if s["id"] != sid]


def add(cal: dict, day: str, start: str, minutes: int, kind: str, title: str, objective: str, codes: list[str]) -> dict:
    s = session(day, start, minutes, kind, title, objective, codes, cal.get("programme", ""))
    cal["sessions"].append(s)
    return s


def overlaps(cal: dict) -> list[tuple[str, str]]:
    out = []
    ss = sorted((s for s in cal["sessions"] if not s.get("unscheduled") and s["kind"] not in ("school", "task", "break")),
                key=lambda s: (s["date"], s["start"]))
    for a, b in zip(ss, ss[1:]):
        if a["date"] == b["date"] and end_of(a) > at(b["date"], b["start"]):
            out.append((a["id"], b["id"]))
    return out


def next_session(cal: dict, now: datetime, subject: str | None = None) -> dict | None:
    """The next study session (now or upcoming), optionally for one subject. Old sessions without a subject are Maths."""
    live = [s for s in cal.get("sessions", []) if s["kind"] in ("study", "review", "mixed", "exam") and status(s, now) in ("now", "upcoming")
            and (subject is None or (s.get("subject") or "maths") == subject)]
    return min(live, key=lambda s: (s["date"], s["start"])) if live else None


# --------------------------------------------------------------------------- month plan
# After the first weekend, every topic comes back in turn (interleaved, so no topic waits long), Calculus included.
MONTH_PROGRAMME = "Monthly plan"
CHUNKS = {
    1: [["1.1", "1.2", "1.3", "1.6"], ["1.4", "1.5", "1.7", "1.8"], ["1.9", "1.10", "1.11"], ["1.12", "1.13"], ["1.14", "1.15"]],
    2: [["2.1", "2.2", "2.3"], ["2.4", "2.5", "2.6"], ["2.7", "2.8"], ["2.9", "2.10"]],
    3: [["3.1", "3.2", "3.3", "3.4"], ["3.5", "3.6", "3.7", "3.8"], ["3.9", "3.10", "3.11"], ["3.12", "3.13"], ["3.14", "3.15", "3.16"]],
    4: [["4.1", "4.2", "4.3"], ["4.4", "4.5", "4.6"], ["4.7", "4.8", "4.9"], ["4.10", "4.11", "4.12"], ["4.13", "4.14", "4.15"], ["4.16", "4.17", "4.18", "4.19"]],
    5: [["5.1", "5.2", "5.3", "5.4"], ["5.5", "5.6", "5.7", "5.8"], ["5.9", "5.10", "5.11"], ["5.12", "5.13"], ["5.14", "5.15", "5.16"], ["5.17", "5.18"]],
}
WEEKDAY = [("17:30", 60, "study"), ("18:30", 10, "break"), ("18:40", 20, "review")]
SATURDAY = [("10:00", 60, "study"), ("11:00", 15, "break"), ("11:15", 60, "study"), ("12:15", 75, "break"), ("13:30", 60, "mixed")]
SUNDAY = [("10:00", 120, "exam"), ("12:00", 20, "break"), ("12:20", 40, "review")]


def interleaved_chunks(weak: list[str] | None = None) -> list[list[str]]:
    """Sub-topic groups taken from each topic in turn; groups holding weak sub-topics come first."""
    weak = set(weak or [])
    order, i = [], 0
    while any(i < len(c) for c in CHUNKS.values()):
        for t in (1, 2, 3, 4, 5):
            if i < len(CHUNKS[t]):
                order.append(CHUNKS[t][i])
        i += 1
    return sorted(order, key=lambda c: not (set(c) & weak))


def chunk_title(codes: list[str]) -> tuple[str, str]:
    t = data.topic(data.topic_of(codes[0]))
    names = [data.sub_title(c).split(";")[0].split(":")[0] for c in codes]
    return f"{t['title']}: {codes[0]}–{codes[-1]}" if len(codes) > 1 else f"{t['title']}: {codes[0]}", "Recall, learn, then exam questions: " + ", ".join(n[:40] for n in names)


def plan_month(cal: dict, year: int, month: int, now: datetime, weak: list[str] | None = None) -> int:
    """Fill every free day of the month from tomorrow (or today, if the day's slots are still ahead) with the regular plan.
    Days that already hold sessions are left alone. Returns how many study blocks were added."""
    import calendar as _cal
    taken = {s["date"] for s in cal["sessions"]}
    chunks = interleaved_chunks(weak)
    k, added, papers = 0, 0, 0
    for day_n in range(1, _cal.monthrange(year, month)[1] + 1):
        d = date(year, month, day_n)
        iso = d.isoformat()
        if iso in taken or d < now.date():
            continue
        template = SUNDAY if d.weekday() == 6 else SATURDAY if d.weekday() == 5 else WEEKDAY
        if at(iso, template[0][0]) < now:
            continue
        for start, minutes, kind in template:
            if kind == "study":
                codes = chunks[k % len(chunks)]
                k += 1
                title, objective = chunk_title(codes)
                cal["sessions"].append(session(iso, start, minutes, kind, title, objective, codes, MONTH_PROGRAMME))
                added += 1
            elif kind == "exam":
                papers += 1
                cal["sessions"].append(session(iso, start, minutes, kind, f"Timed Paper {1 if papers % 2 else 2} (practice exam)",
                                               "Full paper under exam conditions, then mark it and log every lost mark", [], MONTH_PROGRAMME))
            elif kind == "mixed":
                cal["sessions"].append(session(iso, start, minutes, kind, "Mixed-topic set",
                                               "Questions across the week's topics with the topic hidden", [], MONTH_PROGRAMME))
            elif kind == "review":
                title = "Error review + retries" if d.weekday() == 6 else "Daily recall + retries"
                obj = "Go through this week's error log and retry what went wrong" if d.weekday() == 6 else "Due recall cards, then the question parts due for a retry"
                cal["sessions"].append(session(iso, start, minutes, kind, title, obj, [], MONTH_PROGRAMME))
            else:
                cal["sessions"].append(session(iso, start, minutes, "break", "Lunch break" if minutes >= 45 else "Break", programme=MONTH_PROGRAMME))
    cal.setdefault("planned_months", [])
    if f"{year}-{month:02d}" not in cal["planned_months"]:
        cal["planned_months"].append(f"{year}-{month:02d}")
    return added


def ensure_month(now: datetime | None = None, path: Path | None = None) -> dict:
    """The calendar, filled ahead from the student's weekly routine (ibtee/routine.py). The first time, the Maths-only monthly plan
    this app generated before the routine existed is replaced: its future, untouched, unfinished sessions are removed (the routine's
    Maths slots carry the same sub-topic rotation). The student's own edits and done sessions are never removed."""
    from ibtee import routine
    path = path or CAL
    now = now or now_local()
    cal = ensure(now, path)
    changed = False
    if cal.get("routine_version") != 1:
        for s in cal["sessions"]:
            s.setdefault("subject", "maths")
        cal["sessions"] = [s for s in cal["sessions"] if not (s.get("programme") == MONTH_PROGRAMME and not s.get("done") and not s.get("edited")
                                                               and at(s["date"], s["start"]) >= now)]
        cal["routine_version"] = 1
        changed = True
    if cal.get("routine_until", "") < routine.horizon(now.date()).isoformat():
        routine.apply(cal, now)
        changed = True
    if changed:
        save(cal, path)
    return cal


def month_sessions(cal: dict, year: int, month: int) -> dict[str, list[dict]]:
    prefix = f"{year}-{month:02d}-"
    out: dict[str, list[dict]] = {}
    for s in sorted(cal.get("sessions", []), key=lambda s: (s["date"], s["start"])):
        if s["date"].startswith(prefix):
            out.setdefault(s["date"], []).append(s)
    return out
