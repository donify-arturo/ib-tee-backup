"""
What the student has tried, when each question type should come back, and today's mixed session.

    data/attempts.jsonl    one line per first attempt on a question; only ever appended to
    data/study_plan.json   {"exam": "YYYY-MM-DD" | null, "topics": [...], "size": 10, "hidden": [refs]}

Returns are scheduled by question type and draw a new question each time, because a question stops testing anything once its answer
is remembered. A type's state is worked out from the log rather than stored, so changing the exam date simply re-plans everything.
The gaps, the help rules and the confusable families are judgement built from the research in reports/, not tested values.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from datetime import date, timedelta
from pathlib import Path

from ibtee import users

DATA = Path(__file__).resolve().parent / "data"
ATTEMPTS = DATA / "attempts.jsonl"
PLAN = DATA / "study_plan.json"
DEFAULT_GAP = 7          # no exam date set
AFTER_EXAM_GAP = 14      # keep the skill alive for the final exam
SOLID_NEEDED = 3         # unaided successes on separate days, with no miss since
LAPSE_GRACE = 7          # days a check can be overdue before Mastered is lost
GAP_POINTS = [(7, 3), (14, 4), (35, 8), (70, 12), (200, 21)]     # days to the exam -> days between returns

# Types easily mistaken for each other go side by side, since telling them apart is the skill being practised.
FAMILIES = [
    ("direction", r"combustion data|formation data|bond enthalpy: calculate"),
    ("which equation", r"equation"),
    ("cycles", r"hess|born-haber"),
    ("bond enthalpy", r"bond enthalpy|lattice"),
    ("calorimetry", r"calorimetry|temperature-time"),
    ("energy profile", r"energy profile|exothermic"),
]
# Words suggesting the question needs a figure the text doesn't contain
_NEEDS_FIGURE = re.compile(r"\b(diagram|graph|shown|figure|table|below|above|spectrum|curve|following|apparatus|plot|cycle|profile|this)\b", re.I)
_TAG = re.compile(r"</?[a-z]+>")
_LOST_SUBSCRIPT = re.compile(r"[A-Z][a-z]? \( ?(?:g|l|s|aq) ?\)|\b[A-Z][a-z]? [A-Z][A-Za-z]*\((?:g|l|s|aq)\)")     # "H ( g)", "H O(l)", "CH OH(l)"
_DANGLING = {"step", "of", "the", "a", "an", "and", "to", "in", "at", "by", "for", "with", "from", "forward", "reverse"}
# Checked by hand: lost denominators or garbled symbols that no pattern can spot
HAND_BLOCKED = {"09N.1.HL.TZ0.15", "09M.1.HL.TZ1.14", "17N.1.HL.TZ0.20", "17M.1.HL.TZ2.17"}
_REAL_HELP = "3_novel_application"    # Disguise says what the question really is; command term, booklet and time are allowed in the exam or don't solve it


# --------------------------------------------------------------------------- #
# the log
# --------------------------------------------------------------------------- #
def load_attempts(path: Path = ATTEMPTS) -> list[dict]:
    path = users.scoped(path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:      # a half-written line must not lose the rest of the log
            continue
    return rows


def log_attempt(value: dict, item: dict, path: Path = ATTEMPTS, now: float | None = None) -> bool:
    """Save a first attempt. The card repeats its value on every rerun, so a value already logged is ignored."""
    path = users.scoped(path)
    if not value or not value.get("id") or any(a.get("id") == value["id"] for a in load_attempts(path)):
        return False
    stamp = time.localtime(now if now is not None else time.time())
    row = {**value, "day": time.strftime("%Y-%m-%d", stamp), "time": time.strftime("%H:%M", stamp), **item}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    users.saved(path)
    return True


def load_plan(path: Path = PLAN) -> dict:
    plan = {"exam": None, "topics": ["R1.1", "R1.2"], "size": 10, "hidden": []}
    path = users.scoped(path)
    if path.exists():
        plan.update(json.loads(path.read_text(encoding="utf-8")))
    return plan


def save_plan(plan: dict, path: Path = PLAN) -> None:
    path = users.scoped(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    users.saved(path)


# --------------------------------------------------------------------------- #
# the schedule
# --------------------------------------------------------------------------- #
def outcome(a: dict) -> str:
    """solid: right, sure and unaided. shaky: right but unsure or helped, or some marks. miss: wrong, or the answer was just shown."""
    if a.get("revealed"):
        return "miss"
    if a.get("self") == "some":
        return "shaky"
    if not a.get("correct"):
        return "miss"
    h = a.get("help") or {}
    helped = h.get("hints") or h.get("crossed") or _REAL_HELP in (h.get("chips") or [])
    return "shaky" if helped or a.get("sure") is False else "solid"


def gap_days(days_left: int | None) -> int:
    """Days between returns, scaled from the time left. Equal gaps are fine: expanding ones showed no advantage."""
    if days_left is None:
        return DEFAULT_GAP
    if days_left <= 0:
        return AFTER_EXAM_GAP
    low_d, low_g = GAP_POINTS[0]
    if days_left <= low_d:
        return max(1, round(days_left * low_g / low_d))
    for (d0, g0), (d1, g1) in zip(GAP_POINTS, GAP_POINTS[1:]):
        if days_left <= d1:
            return round(g0 + (g1 - g0) * (days_left - d0) / (d1 - d0))
    return GAP_POINTS[-1][1]


def type_states(attempts: list[dict], exam: date | None) -> dict[tuple, dict]:
    """{(sub_topic, question_type): {sessions, streak, last, due}}. Only a type's first attempt of each day counts."""
    first: dict[tuple, dict[str, dict]] = {}
    for a in attempts:
        if a.get("sub_topic") and a.get("question_type") and a.get("day"):
            first.setdefault((a["sub_topic"], a["question_type"]), {}).setdefault(a["day"], a)
    states = {}
    for key, days in first.items():
        s = {"sessions": 0, "streak": 0, "last": None, "due": None, "solid": []}
        for day_text in sorted(days):
            day = date.fromisoformat(day_text)
            result = outcome(days[day_text])
            gap = gap_days((exam - day).days if exam else None)
            s["sessions"] += 1
            s["last"] = day
            if result == "solid":
                s["streak"] += 1
                s["solid"].append({"day": day, "ref": days[day_text].get("ref"), "mixed": bool(days[day_text].get("mixed"))})
                s["due"] = day + timedelta(days=gap)
            elif result == "shaky":
                s["due"] = day + timedelta(days=max(1, gap // 2))
            else:
                s["streak"] = 0
                s["solid"] = []
                s["due"] = day + timedelta(days=1)
            if exam and day < exam - timedelta(days=1) and s["due"] >= exam:     # one last look the day before
                s["due"] = exam - timedelta(days=1)
        states[key] = s
    return states


def mastery(state: dict | None, questions_available: int, exam: date | None, today: date) -> dict:
    """Mastered is earned: 3 sure, unaided successes on separate days, the last after a real gap, at least one in a mixed session,
    and on 2 different questions when the type has them. A miss restarts the count, and a check left too long overdue loses it.

    {"status": "new" | "practising" | "mastered", "done": n, "needs": [what's left], "check": date of the next check}"""
    if not state:
        return {"status": "new", "done": 0, "needs": [], "check": None}
    solid = state["solid"]
    needs = []
    if len(solid) < SOLID_NEEDED:
        needs.append(f"{SOLID_NEEDED - len(solid)} more without help")
    else:
        wanted = max(2, gap_days((exam - solid[-1]["day"]).days if exam else None) // 2)
        if (solid[-1]["day"] - solid[-2]["day"]).days < wanted:
            needs.append(f"one more after a {wanted}-day gap")
        if not any(x["mixed"] for x in solid):
            needs.append("one in a Today session")
        if questions_available >= 2 and len({x["ref"] for x in solid}) < 2:
            needs.append("a different question")
    overdue = (today - state["due"]).days if state["due"] else 0
    if not needs and overdue > max(LAPSE_GRACE, gap_days((exam - today).days if exam else None)):
        needs.append("a check: this one is long overdue")
    return {"status": "practising" if needs else "mastered", "done": min(len(solid), SOLID_NEEDED), "needs": needs, "check": state["due"]}


def mastery_label(m: dict) -> str:
    if m["status"] == "mastered":
        return f"Mastered · check {m['check'].day} {m['check']:%b}"
    if m["status"] == "new":
        return "New"
    return f"Practising {m['done']}/{SOLID_NEEDED}" + (f" · needs {', '.join(m['needs'])}" if m["done"] >= SOLID_NEEDED else "")


def questions_for(cards: list[dict], variants: dict[str, dict], hidden: set[str]) -> int:
    """How many different questions this type can draw on."""
    own = {c["walkthrough"]["question_ref"] for c in cards}
    extra = {r for c in cards for r in c["walkthrough"].get("try_next", []) if r in variants and r not in hidden}
    return len(own | extra)


def question_types(decks: dict[str, dict]) -> dict[tuple, list[dict]]:
    """{(sub_topic, question_type): [cards]}, for cards with a worked question."""
    out: dict[tuple, list[dict]] = {}
    for code, deck in decks.items():
        for card in deck.get("cards", []):
            wt = card.get("walkthrough")
            if wt and wt.get("question_type"):
                out.setdefault((code, wt["question_type"]), []).append(card)
    return out


def split_due(types: dict[tuple, list], states: dict[tuple, dict], today: date) -> tuple[list[tuple], list[tuple]]:
    """(due, new). Fewest returns first, then longest overdue, so every type gets two looks before any gets a fourth."""
    due = [k for k in types if k in states and states[k]["due"] <= today and states[k]["last"] < today]
    due.sort(key=lambda k: (states[k]["sessions"], states[k]["due"], k))
    return due, sorted(k for k in types if k not in states)


# --------------------------------------------------------------------------- #
# fresh questions
# --------------------------------------------------------------------------- #
def clean_variant(q: dict, has_figure: bool, split_options) -> dict | None:
    """A library question usable as is: four options, a known key, and nothing that needs a figure we can't show."""
    if not q or q.get("mcq_answer") not in tuple("ABCD"):
        return None
    if q["ref"] in HAND_BLOCKED:
        return None
    stem, options = split_options(q.get("question") or "")
    stem = _tidy(re.sub(r"^\s*\d+\s*[.)]\s+(?=\D)", "", stem))     # "14. Which" loses its number; "1.0 g of" must keep it
    options = [{**o, "text": _TAG.sub("", o["text"]).strip()} for o in options]
    if not options or not stem or len({o["text"] for o in options}) < 4 or not all(o["text"] for o in options):
        return None
    if _NEEDS_FIGURE.search(stem) and not has_figure:
        return None
    if _looks_garbled(stem, [o["text"] for o in options]):
        return None
    return {"ref": q["ref"], "stem": stem, "options": options, "correct": q["mcq_answer"]}


def _tidy(text: str) -> str:
    """Remove what extraction leaves behind: table rulers, tags, repeated lines, and stray subscripts on a line of their own."""
    lines: list[str] = []
    for line in _TAG.sub("", text).splitlines():
        line = line.strip()
        if not line or len(line) == 1 or re.fullmatch(r"[:\-\s]+", line) or (lines and lines[-1] == line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _looks_garbled(stem: str, options: list[str]) -> bool:
    """A formula that lost its subscripts, or an option cut off mid-sentence, would teach the wrong thing. Better no question at all."""
    whole = "\n".join([stem, *options])
    if _LOST_SUBSCRIPT.search(whole) or "Ö" in whole:
        return True
    endings = {o.endswith(".") for o in options}
    if len(endings) > 1 and all(len(o.split()) >= 5 for o in options):      # some sentences finished, some not
        return True
    return any(o.split()[-1].rstrip(":;,").lower() in _DANGLING for o in options)


def pick_question(cards: list[dict], variants: dict[str, dict], attempts: list[dict], hidden: set[str], used: set[str]) -> dict:
    """The type's card the first time, then an unseen question, and only then whichever was seen longest ago."""
    # Several cards can draw on parts of one past-paper question, so a card is known by its id and only a fresh question by its ref.
    last_seen: dict[str, str] = {}
    for a in attempts:
        for name in (a.get("card_id"), a.get("ref")):
            if name:
                last_seen[name] = max(last_seen.get(name, ""), a.get("day", ""))
    own_refs = {c["walkthrough"]["question_ref"] for c in cards}
    extra = [r for c in cards for r in c["walkthrough"].get("try_next", []) if r in variants and r not in own_refs]
    candidates = [(c["card_id"], c["walkthrough"]["question_ref"], c, None) for c in cards]
    candidates += [(r, r, cards[0], variants[r]) for r in dict.fromkeys(extra) if r not in hidden]
    open_ones = [x for x in candidates if x[0] not in used] or candidates
    fresh = [x for x in open_ones if x[0] not in last_seen]
    uid, ref, card, variant = fresh[0] if fresh else min(open_ones, key=lambda x: last_seen.get(x[0], ""))
    return {"uid": uid, "ref": ref, "card": card, "variant": variant, "seen_before": uid in last_seen}


# --------------------------------------------------------------------------- #
# today's session
# --------------------------------------------------------------------------- #
def family(question_type: str) -> str:
    text = question_type.lower()
    return next((name for name, pattern in FAMILIES if re.search(pattern, text)), "other")


def mix(keys: list[tuple], seed: str) -> list[tuple]:
    """Up to two neighbours from a confusable family, then a different family, with no topic left to guess from the order."""
    rng = random.Random(seed)
    groups: dict[str, list[tuple]] = {}
    for k in keys:
        groups.setdefault(family(k[1]), []).append(k)
    for g in groups.values():
        rng.shuffle(g)
    names = list(groups)
    rng.shuffle(names)
    out: list[tuple] = []
    while names:
        for name in list(names):
            out += groups[name][:2]
            groups[name] = groups[name][2:]
            if not groups[name]:
                names.remove(name)
    return out


def build_session(decks: dict[str, dict], variants: dict[str, dict], attempts: list[dict], plan: dict, today: date) -> list[dict]:
    exam = date.fromisoformat(plan["exam"]) if plan.get("exam") else None
    types = question_types({c: d for c, d in decks.items() if c in plan["topics"]})
    due, new = split_due(types, type_states(attempts, exam), today)
    chosen = (due + mix(new, today.isoformat()))[:plan["size"]]        # new types spread across families, not the first alphabetically
    hidden, used, session = set(plan.get("hidden", [])), set(), []
    for key in mix(chosen, today.isoformat()):
        picked = pick_question(types[key], variants, attempts, hidden, used)
        used.add(picked["uid"])
        session.append({"sub_topic": key[0], "question_type": key[1], **picked})
    return session
