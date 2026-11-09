"""
Everything the student has done in Maths, and what it means: mastery levels, spaced repetition, the error log.

    data/maths/attempts.jsonl     one line per marked question part, recall card or calculator drill; only ever appended to
    data/maths/error_notes.json   the student's own notes on error-log entries {attempt id: {"note": ..., "resolved": bool}}

All states (levels, due dates, the error log) are worked out from the log, never stored, so the rules can change without losing data.

Mastery is earned, never ticked: a sub-topic is only "Mastered" after independent recall, unaided success on exam questions on
separate days, and success on a question met in mixed or timed practice (an unfamiliar context).
"""
from __future__ import annotations

import json
import os
import random
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from maths import data

DIR = data.DIR
ATTEMPTS = DIR / "attempts.jsonl"
NOTES = DIR / "error_notes.json"

LEVELS = ["Not started", "Learning", "Practising", "Confident", "Mastered"]
MISTAKES = [
    "Conceptual misunderstanding", "Incorrect formula selection", "Calculator operation error", "Algebraic or numerical error",
    "Misinterpretation of the question", "Incomplete mathematical reasoning", "Incorrect notation or units",
]
GRADES = {"again": 0, "hard": 1, "good": 2, "easy": 3}
RETRY_GAPS = [1, 3, 7, 14, 30]          # days before a question part comes back after 0, 1, 2… clean successes
CONFIDENT_RATE = 0.7


# --------------------------------------------------------------------------- log
def load(path: Path = ATTEMPTS) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:          # a half-written line must not lose the rest
            continue
    return rows


def log(row: dict, path: Path = ATTEMPTS, now: float | None = None) -> dict:
    stamp = now if now is not None else time.time()
    lt = time.localtime(stamp)
    full = {"id": uuid.uuid4().hex[:12], "ts": round(stamp, 1), "day": time.strftime("%Y-%m-%d", lt), "time": time.strftime("%H:%M", lt), **row}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(full, ensure_ascii=False) + "\n")
    return full


def log_part(q: dict, part: dict, awarded: int, mode: str, answer: str = "", mistake: str | None = None, concept: str | None = None,
             note: str = "", helped: bool = False, session: str | None = None, path: Path = ATTEMPTS, now: float | None = None) -> dict:
    marks = int(part.get("marks") or 0) or 1
    awarded = max(0, min(int(awarded), marks))
    return log({"kind": "part", "qid": q["id"], "part": part["label"], "topic": q["topic"],
                "subtopic": data.part_subtopic(q, part["label"]), "marks": marks, "awarded": awarded,
                "outcome": "full" if awarded == marks else "partial" if awarded else "miss",
                "answer": answer.strip(), "mistake": mistake if awarded < marks else None,
                "concept": concept or data.part_subtopic(q, part["label"]), "note": note.strip(), "helped": bool(helped),
                "mode": mode, "session": session}, path=path, now=now)


def load_notes(path: Path = NOTES) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save_notes(notes: dict, path: Path = NOTES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(notes, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def parts(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("kind") == "part"]


# --------------------------------------------------------------------------- recall cards (spaced repetition)
def recall_cards(code: str) -> list[dict]:
    s = data.subtopic(code)
    return [{"id": f"{code}#{i}", "subtopic": code, **c} for i, c in enumerate(s["recall"])] if s else []


def all_recall_cards() -> list[dict]:
    return [c for s in data.subtopics() for c in recall_cards(s["code"])]


def card_states(rows: list[dict]) -> dict[str, dict]:
    """SM-2 style: {card id: {reps, interval, ease, due, last, lapses, good}} from the recall log. Only the first review a day counts."""
    states: dict[str, dict] = {}
    seen: set[tuple] = set()
    for r in rows:
        if r.get("kind") != "recall" or (r["card"], r["day"]) in seen:
            continue
        seen.add((r["card"], r["day"]))
        s = states.setdefault(r["card"], {"reps": 0, "interval": 0, "ease": 2.5, "due": None, "last": None, "lapses": 0, "good": 0})
        g = GRADES.get(r.get("grade"), 0)
        day = date.fromisoformat(r["day"])
        if g == 0:
            s["reps"], s["interval"], s["lapses"] = 0, 1, s["lapses"] + 1
            s["ease"] = max(1.3, s["ease"] - 0.2)
        else:
            s["good"] += g >= 2
            s["reps"] += 1
            if s["reps"] == 1:
                s["interval"] = 1 if g == 1 else 3 if g == 2 else 4
            elif s["reps"] == 2:
                s["interval"] = 3 if g == 1 else 6 if g == 2 else 8
            else:
                s["interval"] = max(s["interval"] + 1, round(s["interval"] * (s["ease"] * (0.8 if g == 1 else 1.0 if g == 2 else 1.3))))
            s["ease"] = max(1.3, s["ease"] + {1: -0.15, 2: 0.0, 3: 0.15}[g])
        s["last"] = day
        s["due"] = day + timedelta(days=s["interval"])
    return states


def due_cards(rows: list[dict], today: date, codes: list[str] | None = None, include_new_from: list[str] | None = None, limit: int = 20) -> list[dict]:
    """Cards due today (most overdue first), then new cards from sub-topics the student has started."""
    states = card_states(rows)
    pool = [c for c in all_recall_cards() if codes is None or c["subtopic"] in codes]
    due = sorted((c for c in pool if c["id"] in states and states[c["id"]]["due"] <= today), key=lambda c: states[c["id"]]["due"])
    new = [c for c in pool if c["id"] not in states and (include_new_from is None or c["subtopic"] in include_new_from)]
    return (due + new)[:limit]


# --------------------------------------------------------------------------- question parts: retries
def part_states(rows: list[dict]) -> dict[tuple, dict]:
    """{(qid, part): {tries, clean, last, due, last_outcome}}: a miss comes back tomorrow, each clean success spaces it out."""
    states: dict[tuple, dict] = {}
    for r in sorted(parts(rows), key=lambda r: r["ts"]):
        key = (r["qid"], r["part"])
        s = states.setdefault(key, {"tries": 0, "clean": 0, "last": None, "due": None, "last_outcome": None, "subtopic": r["subtopic"]})
        day = date.fromisoformat(r["day"])
        s["tries"] += 1
        if r["outcome"] == "full" and not r.get("helped"):
            s["clean"] += 1
            gap = RETRY_GAPS[min(s["clean"], len(RETRY_GAPS) - 1)]
        elif r["outcome"] == "full":
            gap = 2
        elif r["outcome"] == "partial":
            s["clean"] = 0
            gap = 2
        else:
            s["clean"] = 0
            gap = 1
        s["last"], s["last_outcome"], s["due"] = day, r["outcome"], day + timedelta(days=gap)
    return states


def due_retries(rows: list[dict], today: date) -> list[tuple]:
    """Question parts that went wrong (or were helped) and are due again, oldest first. Clean, unaided parts never need a retry."""
    st = part_states(rows)
    return sorted((k for k, s in st.items() if s["due"] <= today and (s["last_outcome"] != "full" or s["clean"] == 0)),
                  key=lambda k: st[k]["due"])


# --------------------------------------------------------------------------- mastery
def subtopic_stats(code: str, rows: list[dict]) -> dict:
    mine = [r for r in parts(rows) if r["subtopic"] == code]
    cards = recall_cards(code)
    cs = card_states(rows)
    recall_rows = [r for r in rows if r.get("kind") == "recall" and r["card"].split("#")[0] == code]
    recent = mine[-10:]
    marks = sum(r["marks"] for r in recent)
    clean = [r for r in mine if r["outcome"] == "full" and not r.get("helped")]
    return {
        "parts": len(mine), "questions": len({r["qid"] for r in mine}),
        "rate": (sum(r["awarded"] for r in recent) / marks) if marks else None,
        "clean": len(clean), "clean_days": sorted({r["day"] for r in clean}),
        "unfamiliar_clean": sum(1 for r in clean if r.get("mode") in ("mixed", "exam", "review")),
        "last_outcome": mine[-1]["outcome"] if mine else None,
        "recall_reviews": len(recall_rows),
        "recall_good_rate": (sum(1 for r in recall_rows if GRADES.get(r["grade"], 0) >= 2) / len(recall_rows)) if recall_rows else None,
        "cards": len(cards), "cards_secure": sum(1 for c in cards if cs.get(c["id"], {}).get("good", 0) >= 2),
        "mistakes": [r["mistake"] for r in mine if r.get("mistake")],
        "calc": sum(1 for r in rows if r.get("kind") == "calc" and r.get("subtopic") == code and r.get("correct")),
    }


def level(code: str, rows: list[dict]) -> dict:
    """{"level": one of LEVELS, "index": 0-4, "needs": [what is still missing for the next level], "stats": ...}"""
    s = subtopic_stats(code, rows)
    if not s["parts"] and not s["recall_reviews"]:
        return {"level": LEVELS[0], "index": 0, "needs": ["start with the recall questions"], "stats": s}
    if s["parts"] < 2:
        return {"level": LEVELS[1], "index": 1, "needs": ["try at least two past-paper parts"], "stats": s}
    confident_needs = []
    if (s["rate"] or 0) < CONFIDENT_RATE:
        confident_needs.append(f"score {int(CONFIDENT_RATE * 100)}%+ on your last 10 parts (now {int((s['rate'] or 0) * 100)}%)")
    if s["clean"] < 3:
        confident_needs.append(f"{3 - s['clean']} more full-mark parts without hints")
    if s["recall_good_rate"] is None or s["recall_good_rate"] < CONFIDENT_RATE:
        confident_needs.append("recall the formulas and methods reliably")
    if confident_needs:
        return {"level": LEVELS[2], "index": 2, "needs": confident_needs, "stats": s}
    mastered_needs = []
    days = [date.fromisoformat(d) for d in s["clean_days"]]
    if len(days) < 2 or (days[-1] - days[0]).days < 2:
        mastered_needs.append("succeed again on another day, at least 2 days later")
    if s["unfamiliar_clean"] < 1:
        mastered_needs.append("solve one in mixed or timed practice, where the topic is not given")
    if s["cards"] and s["cards_secure"] < s["cards"]:
        mastered_needs.append(f"recall every card twice ({s['cards_secure']}/{s['cards']} secure)")
    if s["last_outcome"] == "miss":
        mastered_needs.append("fix your last miss")
    if mastered_needs:
        return {"level": LEVELS[3], "index": 3, "needs": mastered_needs, "stats": s}
    return {"level": LEVELS[4], "index": 4, "needs": [], "stats": s}


def all_levels(rows: list[dict]) -> dict[str, dict]:
    return {s["code"]: level(s["code"], rows) for s in data.subtopics()}


def topic_progress(levels: dict[str, dict], topic_n: int) -> float:
    """0-1: average level across the topic's sub-topics (Mastered = 1)."""
    codes = [c for c in levels if data.topic_of(c) == topic_n]
    return sum(levels[c]["index"] for c in codes) / (4 * len(codes)) if codes else 0.0


# --------------------------------------------------------------------------- error log
def error_log(rows: list[dict], notes: dict | None = None) -> list[dict]:
    """Every part that lost marks, newest first, with whether a later clean attempt has fixed it."""
    notes = notes if notes is not None else load_notes()
    ps = parts(rows)
    out = []
    for i, r in enumerate(ps):
        if r["outcome"] == "full":
            continue
        later = [x for x in ps[i + 1:] if x["qid"] == r["qid"] and x["part"] == r["part"]]
        fixed = any(x["outcome"] == "full" and not x.get("helped") for x in later)
        n = notes.get(r["id"], {})
        out.append({**r, "fixed": fixed, "resolved": bool(n.get("resolved")) or fixed, "my_note": n.get("note", "")})
    return sorted(out, key=lambda r: -r["ts"])


def mistake_counts(errors: list[dict], open_only: bool = False) -> dict[str, int]:
    out = {m: 0 for m in MISTAKES}
    for e in errors:
        if e.get("mistake") in out and not (open_only and e["resolved"]):
            out[e["mistake"]] += 1
    return out


def book_states(rows: list[dict]) -> dict[str, str]:
    """Textbook questions: the latest self-check per question (right, partly, wrong). They never count towards a level."""
    return {r["qid"]: r["result"] for r in rows if r.get("kind") == "book"}


# What each kind of mistake should change: (advice, the sub-topic step to open, the button's verb).
MISTAKE_ADVICE = {
    "Conceptual misunderstanding": ("The idea itself is shaky, so more questions won't fix it yet. Read Learn again and explain it aloud before you retry.", "learn", "Re-learn"),
    "Incorrect formula selection": ("Compare the “use it when” line of each formula, then decide which one applies before you write anything.", "learn", "Formulas in"),
    "Calculator operation error": ("Step through the calculator procedure in practice mode until the screens are predictable, and check the settings first.", "calculator", "Calculator for"),
    "Algebraic or numerical error": ("Slow down on the working: one line per step, keep full accuracy until the end, then redo the retries.", "questions", "Questions on"),
    "Misinterpretation of the question": ("Before calculating, underline the command term and what is being asked for. Mixed practice trains exactly this.", "questions", "Questions on"),
    "Incomplete mathematical reasoning": ("Compare your working with the markscheme's method and reasoning marks: write down every line that earns one.", "questions", "Questions on"),
    "Incorrect notation or units": ("Check every final answer for units, rounding (3 s.f. unless told otherwise) and notation before moving on.", "review", "Review"),
}


def mistake_focus(rows: list[dict], topic_n: int | None = None, k: int = 2) -> list[dict]:
    """The student's most common open mistake types, what to do about each, and the sub-topics where they happen most."""
    groups: dict[str, list[dict]] = {}
    for e in error_log(rows):
        if not e["resolved"] and e.get("mistake") in MISTAKE_ADVICE and (topic_n is None or e["topic"] == topic_n):
            groups.setdefault(e["mistake"], []).append(e)
    out = []
    for mistake, errs in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:k]:
        tally: dict[str, int] = {}
        for e in errs:
            code = e.get("concept") or e["subtopic"]
            tally[code] = tally.get(code, 0) + 1
        codes = sorted(tally, key=lambda c: (-tally[c], data.code_key(c)))[:3]
        advice, view, verb = MISTAKE_ADVICE[mistake]
        out.append({"mistake": mistake, "count": len(errs), "advice": advice, "view": view, "verb": verb, "codes": codes})
    return out


# --------------------------------------------------------------------------- today
def weak_subtopics(levels: dict[str, dict], rows: list[dict], k: int = 3) -> list[str]:
    """Started sub-topics with the most open errors and lowest levels: what personalised revision should revisit."""
    errors = [e for e in error_log(rows) if not e["resolved"]]
    count: dict[str, int] = {}
    for e in errors:
        count[e["concept"] or e["subtopic"]] = count.get(e["concept"] or e["subtopic"], 0) + 1
    started = [c for c, l in levels.items() if 0 < l["index"] < 4]
    return sorted(set(started) | set(count), key=lambda c: (-count.get(c, 0), levels.get(c, {"index": 0})["index"], data.code_key(c)))[:k]


def streak(days: set[str], today: date) -> int:
    n, d = 0, today
    if d.isoformat() not in days:
        d -= timedelta(days=1)          # today not done yet: the streak still counts up to yesterday
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def pick_unseen(pool: list[dict], rows: list[dict], n: int, seed: str) -> list[dict]:
    """n questions from the pool, never-tried first, then least recently tried; reproducible for a given seed."""
    last: dict[str, float] = {}
    for r in parts(rows):
        last[r["qid"]] = max(last.get(r["qid"], 0), r["ts"])
    rng = random.Random(seed)
    fresh = [q for q in pool if q["id"] not in last]
    rng.shuffle(fresh)
    old = sorted((q for q in pool if q["id"] in last), key=lambda q: last[q["id"]])
    return (fresh + old)[:n]


# The six links the student asked mixed practice to favour: (name, sub-topics, how many of them a question must touch).
CONNECTIONS = [
    ("Sequences, finance, exponentials and logarithms", {"1.2", "1.3", "1.4", "1.5", "1.7", "1.9", "1.11", "2.5", "2.9", "2.10"}, 2),
    ("Functions, modelling, regression and statistics", {"2.5", "2.6", "2.9", "2.10", "4.3", "4.4", "4.13"}, 2),
    ("Trigonometry, vectors and 3D geometry", {"3.1", "3.2", "3.3", "3.8", "3.10", "3.11", "3.12", "3.13"}, 2),
    ("Matrices, graph theory and Markov chains", {"1.14", "1.15", "3.9", "3.14", "3.15", "3.16", "4.19"}, 2),
    ("Probability distributions, hypothesis tests and confidence intervals", {"4.7", "4.8", "4.9", "4.11", "4.14", "4.15", "4.16", "4.17", "4.18"}, 2),
    ("Complex numbers and polar/exponential forms", {"1.12", "1.13"}, 1),
]


def connections_of(q: dict) -> list[str]:
    """Which of the six priority links this question combines."""
    tags = set(q["subtopics"])
    return [name for name, codes, need in CONNECTIONS if len(tags & codes) >= need]


def subtopic_weights(rows: list[dict]) -> dict[str, float]:
    """How much each sub-topic needs to come back: open mistakes and a low mark rate raise it, Mastered lowers it. 1.0 is neutral."""
    if not rows:
        return {}
    out: dict[str, float] = {}
    for s in data.subtopics():
        st = subtopic_stats(s["code"], rows)
        weight = 1.0 + (2.0 * (1 - st["rate"]) if st["rate"] is not None else 0.0)
        if level(s["code"], rows)["level"] == "Mastered":
            weight *= 0.3
        out[s["code"]] = weight
    for e in error_log(rows):
        if not e["resolved"]:
            code = e.get("concept") or e["subtopic"]
            out[code] = out.get(code, 1.0) + 3.0
    return out


def ranked(pool: list[dict], rows: list[dict], seed: str) -> list[dict]:
    """The pool in the order to use it: unseen questions first; within that, a weighted draw so weak sub-topics come up sooner and more
    often and mastered ones later, while staying varied. Reproducible for a given seed."""
    weights = subtopic_weights(rows)
    seen = {r["qid"] for r in parts(rows)}
    rng = random.Random(seed)
    def key(q: dict) -> tuple:
        w = max((weights.get(c, 1.0) for c in q["subtopics"]), default=1.0)
        return (q["id"] in seen, -(rng.random() ** (1 / w)))
    return sorted(pick_unseen(pool, rows, len(pool), seed), key=key)


def by_connection(ordered: list[dict], n: int, seed: str) -> list[dict]:
    """n questions, taking the six priority links in turn before anything else; shuffled so the order gives nothing away."""
    rng = random.Random(seed)
    names = [c[0] for c in CONNECTIONS]
    rng.shuffle(names)
    buckets = {name: [q for q in ordered if name in connections_of(q)] for name in names}
    out: list[dict] = []
    used: set[str] = set()
    while len(out) < n and any(q["id"] not in used for b in buckets.values() for q in b):
        for name in names:
            q = next((x for x in buckets[name] if x["id"] not in used), None)
            if q and len(out) < n:
                out.append(q)
                used.add(q["id"])
    out += [q for q in ordered if q["id"] not in used][:n - len(out)]
    rng.shuffle(out)
    return out


def mixed_set(rows: list[dict], n: int, seed: str, scope: str = "all", codes: list[str] | None = None) -> list[dict]:
    """Questions for mixed practice. scope: "synoptic" (questions spanning several topics, the six priority links first), "cumulative"
    (sub-topics already studied), or "all". Weak sub-topics come up sooner. Topics are taken in turn so the order gives nothing away."""
    pool = [q for q in data.questions() if q["has_markscheme"]]
    if scope == "synoptic":
        pool = [q for q in pool if q.get("cross_topics")]
    elif scope == "cumulative" and codes:
        pool = [q for q in pool if set(q["subtopics"]) & set(codes)]
    if scope == "synoptic":
        return by_connection(ranked(pool, rows, seed), n, seed)
    by_topic: dict[int, list[dict]] = {}
    for q in ranked(pool, rows, seed):
        by_topic.setdefault(q["topic"], []).append(q)
    order = list(by_topic)
    random.Random(seed).shuffle(order)
    out: list[dict] = []
    while len(out) < n and any(by_topic.values()):
        for t in order:
            if by_topic[t] and len(out) < n:
                out.append(by_topic[t].pop(0))
    return out


def daily_minutes(rows: list[dict]) -> dict[str, int]:
    """Rough activity per day: marks attempted plus recall cards."""
    out: dict[str, int] = {}
    for r in rows:
        out[r["day"]] = out.get(r["day"], 0) + (r.get("marks", 1) if r.get("kind") == "part" else 1)
    return out


def now_local(tz: str = "Atlantic/Canary") -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(tz))
