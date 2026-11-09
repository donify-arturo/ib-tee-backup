"""
IB TEE — Chemistry HL pages (the original IB-TEE study dashboard, Part 4). The app shell (app.py) draws the menu and calls render().

    streamlit run app.py

Reads only prebuilt data (no PDFs needed):
    data/syllabus/syllabus.json        syllabus tree
    data/techniques/<sub>.json         technique decks (Part 3)
    data/reports/macro_by_subtopic.json, gate.json
Writes:
    data/progress.json                 hand ticks, only for older cards with no worked question (keyed by card_id)
    data/attempts.jsonl, study_plan.json   first attempts and the exam date (study_plan.py)
"""
from __future__ import annotations

import html
import json
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

import notes
import reference
import study_plan
import web_tips
from ibtee import store, users
from analysis import evidence
import guide_ui
from card_ui import card_data, remember_points, show_card, split_options, variant_data

SUBJECT = "IB Chemistry HL"
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PROGRESS = DATA / "progress.json"
INBOX = DATA / "inbox"

PILLAR_TABS = [
    ("1_context", "Exam context"),
    ("2_markscheme_logic", "Markscheme logic"),
    ("3_novel_application", "Disguises"),
    ("4_command_terms", "Command terms"),
    ("5_time_efficiency", "Time"),
    ("6_data_booklet", "Data booklet"),
    ("7_elimination", "Elimination"),
]
FIELD_LABELS = {
    "ao": "Assessment objective", "papers": "Papers", "syllabus_hook": "Syllabus hook", "textbook_gap": "Textbook gap",
    "trigger_phrases": "Phrases that earn the mark", "trap_boundaries": "Where the mark stops", "delta": "Partial vs full credit",
    "disguises": "How it is disguised", "heuristic": "How to see through it",
    "terms": "Command terms", "score_mechanics": "How marks are given",
    "workflow": "Fastest reliable route", "fat_to_trim": "Skip this",
    "sections": "Sections", "hack": "How to use it",
    "rules": "Definitely-wrong rules",
}

# --------------------------------------------------------------------------- #
# Look: periodic-table tiles, indicator colours
# --------------------------------------------------------------------------- #
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@500;600&family=IBM+Plex+Sans+Condensed:wght@600;700&display=swap');
:root{
  --ink:#1B2A3A; --muted:#5E6E80; --paper:#F5F7FA; --rule:#D5DCE4;
  --structure:#1E6FA8;  /* bromothymol blue */
  --reactivity:#B0256B; /* phenolphthalein pink */
  --mastered:#2E8B57;   /* universal indicator green */
}
html, body, [class*="css"], .stMarkdown, .stText, button, input { font-family:Inter, system-ui, sans-serif; }
h1,h2,h3 { font-weight:500 !important; letter-spacing:-0.02em; }
/* breadcrumb and page title */
.crumbs { color:#737373; font-weight:500; margin-bottom:0.1rem; } .crumbs b { color:#0a0a0a; font-weight:500; }
/* filters */
[data-baseweb="select"] > div { border:2px solid #f0f0f0 !important; border-radius:16px !important; background:#fff !important; min-height:48px; }
h1 { font-size:1.85rem !important; padding-top:0.2rem !important; }
/* flow mode banner */
[class*="st-key-flowbar"] { background:var(--accent-soft, #E3F6F3); border-radius:16px; padding:10px 12px 10px 18px; }
[class*="st-key-flowbar"] p { color:var(--accent, #0E9384); margin:0; }
[class*="st-key-flowbar"] button[kind="primary"] { background:var(--btn, #0F1B2D); border-color:var(--btn, #0F1B2D); border-radius:12px; padding:0 1.3rem; }
[class*="st-key-flowbar"] button[kind="primary"] p { color:var(--btn-ink, #fff); font-weight:600; }
[class*="st-key-flowbar"] button[kind="primary"]:disabled { opacity:0.35; }
[class*="st-key-flowbar"] button[kind="secondary"], [class*="st-key-flowbar"] [data-testid="stPopover"] button { background:transparent; border:0; color:var(--accent, #0E9384); }
/* question card */
[class*="st-key-qcard_"] { border:2px solid #e5e5e5; border-radius:24px; padding:14px 22px 16px; background:#fff; margin-bottom:1.1rem; }
/* definitions */
.defn { border:2px solid #e5e5e5; border-radius:16px; padding:10px 16px; margin-bottom:8px; } .defn summary { cursor:pointer; font-weight:500; color:#0a0a0a; }
.defn p { margin:6px 0 2px; } .defn .must { color:var(--accent, #0E9384); font-size:0.9rem; } .defn .trap { color:var(--bad, #D1435B); font-size:0.9rem; }
.notepts { margin:0 0 0.8rem 1.1rem; padding:0; } .notepts li { margin-bottom:0.25rem; }

/* element tiles */
.ptable { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:10px; margin:0.35rem 0 1rem; max-width:780px; }
@media (max-width: 700px) { .ptable { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
.tile { display:block; text-decoration:none !important; color:var(--ink) !important; background:#fff;
        border:2px solid var(--fam); border-radius:6px; padding:8px 10px 9px; min-height:112px; position:relative; }
.tile:hover, .tile:focus-visible { outline:3px solid var(--fam); outline-offset:1px; }
.tile .num { font-size:0.78rem; color:var(--muted); display:flex; justify-content:space-between; }
.tile .sym { font-family:'IBM Plex Sans Condensed', sans-serif; font-weight:700; font-size:2rem; line-height:1.05;
             color:var(--fam); margin-top:2px; }
.tile .name { font-size:0.74rem; line-height:1.2; margin-top:3px; }
.tile .bar { position:absolute; left:0; bottom:0; height:5px; background:var(--mastered); border-radius:0 0 0 4px; }
.tile.empty { border-style:dashed; opacity:0.62; }
.fam-S { --fam:var(--structure); } .fam-R { --fam:var(--reactivity); }
.rowlabel { font-weight:600; color:var(--muted); margin:0.2rem 0 -0.2rem; font-size:0.9rem; }

/* sub-topic header */
.subhead { display:flex; gap:16px; align-items:center; margin-bottom:0.4rem; }
.subhead .sym { font-family:'IBM Plex Sans Condensed', sans-serif; font-weight:700; font-size:3rem; color:var(--fam);
                border:3px solid var(--fam); border-radius:8px; padding:2px 14px; line-height:1.1; background:#fff; }
.subhead h2 { margin:0; }
.subhead .gq { color:var(--muted); margin:2px 0 0; }

/* cards */
.cardmeta { color:var(--muted); font-size:0.86rem; margin:-0.3rem 0 0.2rem; }
.review { color:#8A5A00; font-size:0.85rem; }
.status { color:var(--muted); font-size:0.85rem; } .status-mastered { color:var(--mastered); font-weight:600; }
[class*="st-key-acts_"] { margin-top:-0.9rem; }
[class*="st-key-acts_"] button { min-height:2rem; padding:0.1rem 0.75rem; }
[class*="st-key-acts_"] button p { font-size:0.85rem; }
.pill-list li { margin-bottom:0.15rem; }
.evidence code { font-size:0.82rem; }
.note-steps { margin:0 0 0.35rem 1.1rem; padding:0; } .note-steps li { margin-bottom:0.1rem; }
.note-careful { background:#FAE9F1; border-radius:6px; padding:5px 10px; font-size:0.92rem; margin-bottom:0.25rem; }
</style>
"""


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
@st.cache_data
def load_syllabus() -> dict:
    return json.loads((DATA / "syllabus" / "syllabus.json").read_text(encoding="utf-8"))


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_deck(code: str) -> dict | None:
    deck = load_json(DATA / "techniques" / f"{code}.json", None)
    return reference.add_extras_to_deck(deck, code, reference.extra_questions()) if deck else None


def load_progress() -> dict:
    return load_json(users.scoped(PROGRESS), {})


def set_mastered(card_id: str, value: bool) -> None:
    prog = load_progress()
    prog[card_id] = {"mastered": value, "updated": time.strftime("%Y-%m-%d %H:%M")}
    path = users.scoped(PROGRESS)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prog, indent=2), encoding="utf-8")
    users.saved(path)


@st.cache_data
def _statuses(stamp: tuple) -> dict:
    """Earned status of every question type. Recalculated whenever the log, the plan, a deck or the date changes."""
    plan = study_plan.load_plan()
    exam = date.fromisoformat(plan["exam"]) if plan["exam"] else None
    today = date.today()
    decks = {p.stem: load_deck(p.stem) for p in (DATA / "techniques").glob("*.json")}
    types = study_plan.question_types(decks)
    variants = fresh_questions(tuple(sorted({k[0] for k in types})))
    states = study_plan.type_states(study_plan.load_attempts(), exam)
    hidden = set(plan.get("hidden", []))
    return {k: study_plan.mastery(states.get(k), study_plan.questions_for(cards, variants, hidden), exam, today) for k, cards in types.items()}


def statuses() -> dict:
    mtime = lambda p: p.stat().st_mtime if p.exists() else 0
    decks = max((mtime(p) for p in (DATA / "techniques").glob("*.json")), default=0)
    return _statuses((users.guest_id(), mtime(users.scoped(study_plan.ATTEMPTS)), mtime(users.scoped(study_plan.PLAN)), decks, date.today().isoformat()))


def card_status(card: dict) -> dict:
    key = (card["card_id"].rsplit("-", 1)[0], card["walkthrough"].get("question_type"))
    return statuses().get(key) or {"status": "new", "done": 0, "needs": [], "check": None}


def is_mastered(card: dict, prog: dict) -> bool:
    if card.get("walkthrough"):      # earned from attempts, never ticked
        return card_status(card)["status"] == "mastered"
    if card["card_id"] in prog:
        return prog[card["card_id"]]["mastered"]
    return bool(card.get("status", {}).get("mastered"))


def deck_progress(code: str, prog: dict) -> tuple[int, int]:
    deck = load_deck(code)
    if not deck:
        return 0, 0
    cards = deck["cards"]
    return sum(is_mastered(c, prog) for c in cards), len(cards)


# --------------------------------------------------------------------------- #
# views
# --------------------------------------------------------------------------- #
def tiles(syl: dict, macro: dict, prog: dict) -> None:
    # one row per theme, like periods of the periodic table
    for theme in syl["themes"]:
        letter = theme["code"][0]
        st.markdown(f'<div class="rowlabel">{theme["code"]} {html.escape(theme["title"])}</div>', unsafe_allow_html=True)
        cells = []
        for s in syl["sub_topics"]:
            if not s["code"].startswith(theme["code"] + "."):
                continue
            done, total = deck_progress(s["code"], prog)
            m = macro.get(s["code"], {})
            pct = int(100 * done / total) if total else 0
            right = f"{done}/{total}" if total else "no deck"
            cells.append(
                f'<a class="tile fam-{letter}{"" if total else " empty"}" href="?topic={s["code"]}" target="_self" '
                f'title="{html.escape(s["title"])} · priority {m.get("priority_score", "–")}">'
                f'<div class="num"><span>{right}</span><span>{m.get("priority_score", "")}</span></div>'
                f'<div class="sym">{s["code"]}</div><div class="name">{html.escape(s["title"])}</div>'
                f'<div class="bar" style="width:{pct}%"></div></a>')
        st.markdown(f'<div class="ptable">{"".join(cells)}</div>', unsafe_allow_html=True)


def overview(syl, macro, prog, gate) -> None:
    st.title("IB Chemistry technique decks")
    st.caption("Each tile is a sub-topic. Top left: cards mastered out of the deck. Top right: exam priority (0–100). "
               "Green bar: progress. Dashed tiles have no deck yet.")
    tiles(syl, macro, prog)

    done = sum(deck_progress(s["code"], prog)[0] for s in syl["sub_topics"])
    total = sum(deck_progress(s["code"], prog)[1] for s in syl["sub_topics"])
    decks = sum(1 for s in syl["sub_topics"] if load_deck(s["code"]))
    c1, c2, c3 = st.columns(3)
    c1.metric("Cards mastered", f"{done} / {total}")
    c2.metric("Sub-topics with a deck", f"{decks} / {len(syl['sub_topics'])}")
    missing = sum(len(r["missing"]) for r in gate)
    c3.metric("Questions waiting for a markscheme", missing)

    st.subheader("Where to focus next")
    rows = []
    for s in syl["sub_topics"]:
        m = macro.get(s["code"], {})
        d, t = deck_progress(s["code"], prog)
        rows.append({"Sub-topic": f'{s["code"]} {s["title"]}', "Priority": m.get("priority_score"),
                     "Mean % correct (examiner reports)": m.get("mean_pct_correct"),
                     "Cards left": str(t - d) if t else "no deck yet"})
    rows.sort(key=lambda r: (-(r["Priority"] or 0)))
    st.dataframe(rows, hide_index=True, use_container_width=True)


def render_field(name: str, value) -> None:
    label = FIELD_LABELS.get(name, name.replace("_", " ").capitalize())
    if isinstance(value, list):
        if not value:
            return
        items = "".join(f"<li>{html.escape(str(v))}</li>" for v in value)
        st.markdown(f"**{label}**<ul class='pill-list'>{items}</ul>", unsafe_allow_html=True)
    elif value not in (None, "", "—"):
        st.markdown(f"**{label}**  \n{html.escape(str(value))}", unsafe_allow_html=True)


def status_line(card: dict) -> None:
    m = card_status(card)
    st.markdown(f"<div class='status status-{m['status']}'>{html.escape(study_plan.mastery_label(m))}</div>",
                unsafe_allow_html=True, width="content")


def card_actions(card: dict, prog: dict, code: str, width: str = "stretch") -> None:
    if card.get("walkthrough"):
        status_line(card)
    else:
        mastered = is_mastered(card, prog)
        new = st.checkbox("Mastered", value=mastered, key=f"m_{card['card_id']}")
        if new != mastered:
            set_mastered(card["card_id"], new)
            st.rerun()
    entry = notes.from_card(card, code)
    if entry:
        data = notes.load()
        saved = notes.saved_id(data, entry)
        if st.button("In my notes" if saved else "Add to notes", key=f"n_{card['card_id']}",
                     type="secondary" if saved else "primary", width=width,
                     help="Remove from your notes" if saved else "Save this question type's key steps to your notes"):
            if saved:
                del data["items"][saved]
            else:
                notes.add(data, entry)
            notes.save(data)
            st.rerun()
    marked = store.is_bookmarked("chem_hl", card["card_id"])
    if st.button("Saved" if marked else "Save", key=f"bm_{card['card_id']}", icon=":material/bookmark:" if marked else ":material/bookmark_border:",
                 width=width, help="Remove from Bookmarks" if marked else "Add to Bookmarks"):
        wt = card.get("walkthrough") or {}
        store.toggle_bookmark("chem_hl", card["card_id"], wt.get("question_ref") or card["card_id"], code)
        st.rerun()


def attempt_item(card: dict, code: str, ref: str, fresh: bool, mixed: bool = False) -> dict:
    return {"sub_topic": code, "question_type": card["walkthrough"].get("question_type", ""), "card_id": card["card_id"], "ref": ref,
            "fresh": fresh, "mixed": mixed}


def card_header(card: dict, number: int, ref: str | None = None) -> dict:
    wt = card["walkthrough"]
    ref = ref or wt["question_ref"]
    own = ref == wt["question_ref"]
    return reference.header(number, ref, wt["marks"] if own else 1, pct_correct().get(ref))


@st.fragment                # saving an attempt redraws this card only, not the whole queue
def card_view(card: dict, prog: dict, code: str, number: int = 1) -> None:
    with st.container(key=f"qcard_{card['card_id']}"):
        wt = card.get("walkthrough")
        if wt:                     # the question comes first: a title would give the trick away before you try it
            data = card_data(card, DATA / "figures", figures_by_ref().get(wt["question_ref"], []),
                             web_tips.accepted_for(web_tips.load(), card["card_id"]))
            value = show_card({**data, "header": card_header(card, number)}, key=f"card_{card['card_id']}")
            if value:           # the page can sit open for hours here, so its timer means nothing
                study_plan.log_attempt({**value, "seconds": None}, attempt_item(card, code, wt["question_ref"], False))
            with st.container(key=f"acts_{card['card_id']}", horizontal=True, horizontal_alignment="right",
                              vertical_alignment="center", gap="small"):
                if card.get("status", {}).get("needs_review"):
                    st.markdown("<div class='review'>Check this card: the engine's validator flagged an issue.</div>",
                                unsafe_allow_html=True, width="stretch")
                card_actions(card, prog, code, width="content")
            return
        top, tick = st.columns([0.8, 0.2])
        with top:
            st.markdown(f"#### {html.escape(card['title'])}", unsafe_allow_html=True)
            st.markdown(f"<div class='cardmeta'>Priority {card['priority']} &nbsp;|&nbsp; "
                        f"{html.escape(card.get('difficulty_signal', ''))} &nbsp;|&nbsp; "
                        f"{', '.join(card.get('understandings', []))}</div>", unsafe_allow_html=True)
            if card.get("status", {}).get("needs_review"):
                st.markdown("<div class='review'>Check this card: the engine's validator flagged an issue.</div>",
                            unsafe_allow_html=True)
        with tick:
            card_actions(card, prog, code)
        with st.expander("Open technique", expanded=False):
            tabs = st.tabs([label for _k, label in PILLAR_TABS] + ["Evidence"])
            for (key, _label), tab in zip(PILLAR_TABS, tabs):
                with tab:
                    for fname, fval in card["pillars"].get(key, {}).items():
                        render_field(fname, fval)
            with tabs[-1]:
                lines = "".join(f"<li><code>{html.escape(e['ref'])}</code> {html.escape(e['kind'])}: "
                                f"{html.escape(e.get('note', ''))}</li>" for e in card.get("evidence", []))
                st.markdown(f"<ul class='evidence'>{lines}</ul>", unsafe_allow_html=True)
                figures = figures_by_ref()
                for ref in dict.fromkeys(e["ref"] for e in card.get("evidence", [])):
                    for name in figures.get(ref, []):
                        if (DATA / "figures" / name).exists():
                            st.image(str(DATA / "figures" / name), caption=f"{ref} (from the scanned book)", width=520)


@st.cache_data
def fresh_questions(codes: tuple[str, ...]) -> dict:
    """Library questions a return can use as they are. Shown from the library at run time, never copied into a deck."""
    figures = figures_by_ref()
    out = {}
    extras = reference.extra_questions()
    for code in {*codes, *(e["source"] for e in extras if e["topic"] in codes)}:
        for q in evidence.build(code)["questions"]:
            variant = study_plan.clean_variant(q, bool(figures.get(q["ref"])), split_options)
            if variant:
                out[q["ref"]] = variant
    return out


@st.cache_data
def pct_correct() -> dict:
    """% correct reported by examiners for each question in a deck's topic."""
    out = {}
    for p in (DATA / "techniques").glob("*.json"):
        for q in evidence.build(p.stem)["questions"]:
            if q.get("pct_correct") is not None:
                out[q["ref"]] = q["pct_correct"]
    return out


def worked_decks(codes: list[str]) -> dict:
    return {c: d for c in codes if (d := load_deck(c)) and any(k.get("walkthrough") for k in d["cards"])}


def plan_controls(plan: dict, decks: dict, titles: dict) -> None:
    today = date.today()
    exam = st.date_input("Exam date", value=date.fromisoformat(plan["exam"]) if plan["exam"] else None,
                         min_value=today - timedelta(days=365), help="Sets how far apart questions come back.")
    topics = st.multiselect("Topics to mix", list(decks), default=[t for t in plan["topics"] if t in decks],
                            format_func=lambda c: f"{c} {titles[c]}")
    size = st.number_input("Questions per session", min_value=3, max_value=30, value=int(plan["size"]))
    changed = {"exam": exam.isoformat() if exam else None, "topics": topics, "size": int(size)}
    if any(plan[k] != v for k, v in changed.items()):
        plan.update(changed)
        study_plan.save_plan(plan)
        st.rerun()


def flow_bar(plan: dict, decks: dict, titles: dict, only: str | None) -> None:
    """The one Start button: mixed questions the schedule picks. A chosen topic narrows it to that topic."""
    today = date.today()
    picked = [only] if only and only in decks else [t for t in plan["topics"] if t in decks]
    types = study_plan.question_types({c: decks[c] for c in picked})
    exam_day = date.fromisoformat(plan["exam"]) if plan["exam"] else None
    attempts = study_plan.load_attempts()
    due, new = study_plan.split_due(types, study_plan.type_states(attempts, exam_day), today)
    earned = sum(statuses().get(k, {}).get("status") == "mastered" for k in types)
    bits = [f"{len(due)} due", f"{len(new)} new", f"{earned} / {len(types)} mastered"]
    if exam_day and exam_day >= today:
        bits.append(f"{(exam_day - today).days} days to the exam")
    with st.container(key="flowbar", horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown(f"Answer in **flow** mode &nbsp;·&nbsp; {' · '.join(bits)}", width="stretch")
        with st.popover("Plan"):
            plan_controls(plan, decks, titles)
        count = min(len(due) + len(new), plan["size"])
        if st.button("Start" if count else "Nothing due", type="primary", disabled=not count, key="flow_start",
                     help="Mixed questions feel harder and same-day scores dip. That is expected, and it is what makes them stick."):
            session_plan = {**plan, "topics": picked}
            st.session_state["today_queue"] = study_plan.build_session(decks, fresh_questions(tuple(picked)), attempts, session_plan, today)
            st.session_state["today_i"] = 0
            st.rerun()


def flow_session(plan: dict) -> None:
    today = date.today()
    queue = st.session_state["today_queue"]
    i = st.session_state["today_i"]
    if i >= len(queue):
        st.success(f"Session done: {len(queue)} questions.")
        if st.button("Back to Questionbank", type="primary"):
            del st.session_state["today_queue"]
            st.rerun()
        return
    item, card = queue[i], queue[i]["card"]
    left, right = st.columns([0.8, 0.2], vertical_alignment="center")
    left.progress(i / len(queue), text=f"Flow mode · {i + 1} of {len(queue)}")
    if right.button("Exit", key="flow_exit", width="stretch"):
        del st.session_state["today_queue"]
        st.rerun()
    with st.container(key=f"qcard_flow_{i}"):
        figures = figures_by_ref().get(item["ref"], [])
        if item["variant"]:
            data = variant_data(card, item["variant"], DATA / "figures", figures)
        else:
            data = card_data(card, DATA / "figures", figures, web_tips.accepted_for(web_tips.load(), card["card_id"]))
        value = show_card({**data, "header": card_header(card, i + 1, item["ref"])}, key=f"today_{today}_{item['uid']}")
        if value:
            study_plan.log_attempt(value, attempt_item(card, item["sub_topic"], item["ref"], not item["seen_before"], mixed=True))
        with st.container(key="acts_today", horizontal=True, horizontal_alignment="right", vertical_alignment="center", gap="small"):
            if value:
                status_line(card)
            if item["variant"] and st.button("Question looks wrong", help="Never show this question again", key="today_bad"):
                plan["hidden"] = sorted({*plan.get("hidden", []), item["ref"]})
                study_plan.save_plan(plan)
                st.session_state["today_i"] = i + 1
                st.rerun()
            if st.button("Next" if value else "Skip", type="primary" if value else "secondary", key=f"today_next_{i}"):
                st.session_state["today_i"] = i + 1
                st.rerun()


@st.cache_data
def figures_by_ref() -> dict:
    path = DATA / "figures" / "by_ref.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


QB_PAGE_SIZE = 12


def card_paper(card: dict) -> list[str]:
    wt = card.get("walkthrough")
    if wt:
        paper = reference.paper_of(wt["question_ref"])
        return [paper] if paper else []
    return card.get("pillars", {}).get("1_context", {}).get("papers") or []


def card_difficulty(card: dict) -> str:
    wt = card.get("walkthrough")
    found = reference.difficulty(pct_correct().get(wt["question_ref"])) if wt else None
    return found or "Unrated"


def card_completion(card: dict, prog: dict) -> str:
    if card.get("walkthrough"):
        return {"new": "New", "practising": "Practising", "mastered": "Mastered"}[card_status(card)["status"]]
    return "Mastered" if is_mastered(card, prog) else "New"


@st.fragment
def extra_view(extra: dict, variant: dict, parent: dict | None, code: str, number: int) -> None:
    """A checked library question: no trick buttons, since those are written for a card's own question."""
    ref = extra["ref"]
    figures = figures_by_ref().get(ref, [])
    with st.container(key=f"qcard_extra_{ref.replace('.', '_')}"):
        data = variant_data(parent, variant, DATA / "figures", figures)
        value = show_card({**data, "header": reference.header(number, ref, 1, pct_correct().get(ref))}, key=f"extra_{ref}")
        if value:
            item = attempt_item(parent, code, ref, False) if parent else {"sub_topic": code, "question_type": "", "card_id": None, "ref": ref, "fresh": False, "mixed": False}
            study_plan.log_attempt({**value, "seconds": None}, item)
        tried = any(a.get("ref") == ref for a in study_plan.load_attempts())
        with st.container(key=f"acts_extra_{ref.replace('.', '_')}", horizontal=True, horizontal_alignment="right", vertical_alignment="center", gap="small"):
            st.markdown(f"<div class='status'>{'Tried' if tried else 'New'}</div>", unsafe_allow_html=True, width="content")
            if st.button("Question looks wrong", help="Never show this question again", key=f"bad_{ref}"):
                plan = study_plan.load_plan()
                plan["hidden"] = sorted({*plan.get("hidden", []), ref})
                study_plan.save_plan(plan)
                st.rerun()


def breadcrumbs(*parts: str) -> None:
    inner = " &nbsp;›&nbsp; ".join(html.escape(p) for p in parts[:-1]) + f" &nbsp;›&nbsp; <b>{html.escape(parts[-1])}</b>"
    st.markdown(f"<div class='crumbs'>{inner}</div>", unsafe_allow_html=True)


def questionbank(codes: list[str], titles: dict, prog: dict) -> None:
    plan = study_plan.load_plan()
    if st.session_state.get("today_queue"):
        flow_session(plan)
        return
    decks = {c: d for c in codes if (d := load_deck(c))}
    if not decks:
        st.info("No decks yet. Build one on the Build decks page.")
        return
    breadcrumbs(SUBJECT, "Questionbank")
    st.title("Questionbank")

    if st.session_state.get("qb_topic") not in ["All topics", *decks]:
        st.session_state["qb_topic"] = next((t for t in plan["topics"] if t in decks), next(iter(decks)))
    variants = fresh_questions(tuple(decks))
    hidden = set(plan.get("hidden", []))
    extras = [e for e in reference.extra_questions() if e["topic"] in decks and e["ref"] in variants and e["ref"] not in hidden]
    count = lambda c: len(decks[c]["cards"]) + sum(e["topic"] == c for e in extras)
    f1, f2, f3, f4 = st.columns([0.4, 0.2, 0.2, 0.2])
    topic = f1.selectbox("Topic", ["All topics", *decks], key="qb_topic",
                         format_func=lambda c: c if c == "All topics" else f"{c} {titles[c]} ({count(c)})")
    pool = [(c, k) for c in (decks if topic == "All topics" else [topic]) for k in decks[c]["cards"]]
    extras = [e for e in extras if topic in ("All topics", e["topic"])]
    papers = sorted({p for _c, k in pool for p in card_paper(k)} | {reference.paper_of(e["ref"]) for e in extras} - {""})
    paper = f2.selectbox("Paper", ["All papers", *papers], format_func=lambda p: p if p == "All papers" else f"Paper {p}")
    level = f3.selectbox("Difficulty", ["All", "Easy", "Standard", "Hard", "Unrated"],
                         help="From the % correct in examiner reports. Many questions have no figure, so they show as Unrated.")
    done = f4.selectbox("Completion", ["All", "New", "Practising", "Mastered"])

    flow_bar(plan, worked_decks(codes), titles, None if topic == "All topics" else topic)

    def keep(k: dict) -> bool:
        return ((paper == "All papers" or paper in card_paper(k)) and (level == "All" or card_difficulty(k) == level)
                and (done == "All" or card_completion(k, prog) == done))

    tried = {a.get("ref") for a in study_plan.load_attempts()}

    def keep_extra(e: dict) -> bool:
        graded = reference.difficulty(pct_correct().get(e["ref"])) or "Unrated"
        return ((paper == "All papers" or paper == reference.paper_of(e["ref"])) and (level == "All" or graded == level)
                and (done == "All" or done == ("Practising" if e["ref"] in tried else "New")))

    cards_by_id = {k["card_id"]: k for _c, k in pool}
    shown = sorted(((c, k) for c, k in pool if keep(k)), key=lambda x: (x[1]["priority"], x[1]["card_id"]))
    shown += [(e["topic"], e) for e in extras if keep_extra(e)]
    if not shown:
        st.info("No questions match these filters.")
        return
    limit = st.session_state.get("qb_limit", QB_PAGE_SIZE)
    for number, (c, k) in enumerate(shown[:limit], start=1):
        if "ref" in k:
            extra_view(k, variants[k["ref"]], cards_by_id.get(k.get("card")), c, number)
        else:
            card_view(k, prog, c, number)
    if len(shown) > limit and st.button(f"Show more ({len(shown) - limit} left)", width="stretch"):
        st.session_state["qb_limit"] = limit + QB_PAGE_SIZE
        st.rerun()


def topic_with_reference(codes: list[str], titles: dict, key: str) -> str:
    built = [c for c in codes if reference.load_reference(c)]
    return st.selectbox("Topic", built + [c for c in codes if c not in built], key=key,
                        format_func=lambda c: f"{c} {titles[c]}" + ("" if c in built else "  (no book pages yet)"))


def definitions_page(codes: list[str], titles: dict) -> None:
    breadcrumbs(SUBJECT, "Key definitions")
    st.title("Key definitions")
    a, b = st.columns([0.55, 0.45])
    with a:
        code = topic_with_reference(codes, titles, "defs_topic")
    search = b.text_input("Search", placeholder="e.g. enthalpy, standard").strip().lower()
    ref = reference.load_reference(code)
    if not ref or not ref.get("definitions"):
        st.info("No definitions for this topic yet: they are built from your textbook's pages.")
        return
    st.caption("Say each one out loud first, then tap it to check.")
    for item in ref["definitions"]:
        if search and search not in json.dumps(item, ensure_ascii=False).lower():
            continue
        must = f"<p class='must'>Must say: {html.escape(', '.join(item['must_say']))}</p>" if item.get("must_say") else ""
        trap = f"<p class='trap'>Trap: {html.escape(item['trap'])}</p>" if item.get("trap") else ""
        st.markdown(f"<details class='defn'><summary>{html.escape(item['term'])}</summary><p>{html.escape(item['definition'])}</p>{must}{trap}</details>",
                    unsafe_allow_html=True)


def booklet_page() -> None:
    breadcrumbs(SUBJECT, "Data booklet")
    st.title("Data booklet")
    sections = reference.booklet_sections()
    if not sections:
        st.info("The data booklet isn't in the library.")
        return
    a, b = st.columns([0.6, 0.4])
    number = a.selectbox("Section", list(sections), format_func=lambda n: f"{n}. {sections[n]['title']}")
    search = b.text_input("Search all sections", placeholder="e.g. lattice, specific heat").strip().lower()
    st.caption("Text taken from the PDF, so tables and formulas can look rough. Use your printed booklet in practice.")
    if search:
        hits = {n: [l for l in s["text"].splitlines() if search in l.lower()] for n, s in sections.items()}
        hits = {n: lines for n, lines in hits.items() if lines or search in sections[n]["title"].lower()}
        if not hits:
            st.info("Nothing found.")
        for n, lines in hits.items():
            st.markdown(f"**{n}. {html.escape(sections[n]['title'])}**", unsafe_allow_html=True)
            if lines:
                st.code("\n".join(lines), language=None)
        return
    st.code(sections[number]["text"], language=None)


def boundaries_page() -> None:
    breadcrumbs(SUBJECT, "Grade boundaries")
    st.title("Grade boundaries")
    rows = grade_boundary_rows()
    if not rows:
        st.info("No grade boundaries were found in the subject reports.")
        return
    a, b = st.columns(2)
    level = a.selectbox("Level", ["HL", "SL"])
    components = [c for c in ["Overall", "Paper 1", "Paper 1A", "Paper 1B", "Paper 2", "Paper 3", "Internal assessment"]
                  if any(r["component"] == c and level in r["level"] for r in rows)]
    component = b.selectbox("Component", components)
    table = [{"Session": f"{r['month']} {r['year']}" + (f" {r['variant']}" if r["variant"] else ""),
              **{str(g): r["ranges"][g - 1] for g in range(7, 0, -1)}}
             for r in rows if r["component"] == component and level in r["level"]]
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption("From the IB subject reports in your library. Papers before May 2025 were set on the old syllabus, with different papers and marks, "
               "so use the newest sessions as your guide.")


@st.cache_data
def grade_boundary_rows() -> list[dict]:
    return reference.grade_boundaries()


def tips_page(syl, codes: list[str], titles: dict) -> None:
    breadcrumbs(SUBJECT, "Tips & my notes")
    if not users.is_owner():                 # web research runs on the owner's plan, and accepted tips reach everyone's cards
        notes_page(syl, codes, titles)
        return
    mine, web = st.tabs(["My notes", "Web tips"])
    with mine:
        notes_page(syl, codes, titles)
    with web:
        web_tips_page(codes)


def missing_page(syl, gate) -> None:
    st.title("Questions waiting for a markscheme")
    st.write("A question only feeds a technique card once its markscheme is in the library. Upload the missing "
             "markschemes here; they are saved to `data/inbox/`. Then add them to `sources.toml` and rerun the pipeline.")
    titles = {s["code"]: s["title"] for s in syl["sub_topics"]}
    for r in sorted(gate, key=lambda r: -len(r["missing"])):
        if not r["missing"]:
            continue
        with st.expander(f'{r["sub_topic"]} {titles[r["sub_topic"]]}: {len(r["missing"])} missing '
                         f'({r["with_markscheme"]} of {r["questions"]} have one)'):
            st.write(", ".join(f"`{x}`" for x in r["missing"]))
    files = st.file_uploader("Upload markscheme PDFs", type=["pdf"], accept_multiple_files=True)
    if files:
        INBOX.mkdir(parents=True, exist_ok=True)
        for f in files:
            (INBOX / f.name).write_bytes(f.getbuffer())
        st.success(f"Saved {len(files)} file(s) to data/inbox/.")


def build_page(syl, gate) -> None:
    st.title("Build decks")
    st.write("Decks are written by Claude Code signed in with your plan, so they use your plan's usage, not API credit. "
             "If you hit your usage limit, run again after it resets: finished decks are kept.")
    titles = {s["code"]: s["title"] for s in syl["sub_topics"]}
    ready = [r for r in sorted(gate, key=lambda r: -r["with_markscheme"]) if r["with_markscheme"] >= 3]
    options = [f'{r["sub_topic"]} {titles[r["sub_topic"]]} ({r["with_markscheme"]} with markschemes)'
               + (" ✓ deck exists" if load_deck(r["sub_topic"]) else "") for r in ready]
    choice = st.selectbox("Sub-topic", options)
    model = st.radio("Model", ["opus", "sonnet"], horizontal=True,
                     help="Opus writes the best decks; Sonnet uses less of your plan's limit.")
    if st.button("Build this deck", type="primary"):
        code = choice.split()[0]
        cmd = [sys.executable, "-m", "engine.technique_engine", code, "--allow-partial",
               "--backend", "claude-cli", "--model", model]
        with st.status(f"Building {code} with Claude Code ({model}). This usually takes a few minutes.",
                       expanded=True) as status:
            env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", env=env)
            st.code((proc.stdout or "") + (proc.stderr or "")[-3000:])
            status.update(label=f"{code}: finished" if proc.returncode == 0 else f"{code}: stopped",
                          state="complete" if proc.returncode == 0 else "error")
    st.caption("To fill every sub-topic in one go, run this in a terminal from the project folder:")
    st.code("python -m engine.technique_engine --all --allow-partial --backend claude-cli --model opus")


# --------------------------------------------------------------------------- #
# app
# --------------------------------------------------------------------------- #
def _set_note(note_id: str, field: str, widget_key: str) -> None:
    data = notes.load()
    if note_id in data["items"]:
        data["items"][note_id][field] = st.session_state[widget_key]
        notes.save(data)


def notes_page(syl, codes: list[str], titles: dict) -> None:
    st.title("My notes")
    st.caption("The key steps for each type of question, so you can revise the ones you find hard.")
    data = notes.load()
    a, b, c = st.columns([0.34, 0.42, 0.24])
    with a:
        pick = st.selectbox("Sub-topic", ["All sub-topics"] + codes, format_func=lambda x: x if x == "All sub-topics" else f"{x} {titles[x]}")
    with b:
        search = st.text_input("Search", placeholder="e.g. arrow, sign, calorimetry")
    with c:
        only_hard = st.toggle("Hard only")
    groups = notes.grouped(data, None if pick == "All sub-topics" else pick, only_hard, search)
    if not data["items"]:
        st.info("Your notes are empty. Open a question in Study and press Add to notes, or write your own below.")
    elif not groups:
        st.info("No notes match. Try clearing the search or the filter.")
    for code, types in groups.items():
        st.subheader(f"{code} {titles.get(code, '')}")
        for qtype, rows in types.items():
            hard = sum(1 for _i, r in rows if r.get("hard"))
            with st.expander(f"{qtype}" + (f"  ·  {hard} hard" if hard else ""), expanded=True):
                for note_id, item in rows:
                    left, right = st.columns([0.78, 0.22])
                    with left:
                        steps = "".join(f"<li>{html.escape(s)}</li>" for s in item["steps"])
                        st.markdown(f"<ol class='note-steps'>{steps}</ol>", unsafe_allow_html=True)
                        if item.get("tricks"):
                            tricks = "".join(f"<li>{html.escape(t)}</li>" for t in item["tricks"])
                            st.markdown(f"<b>Tricks</b><ul class='note-steps'>{tricks}</ul>", unsafe_allow_html=True)
                        if item.get("careful"):
                            st.markdown(f"<div class='note-careful'><b>Be careful:</b> {html.escape(item['careful'])}</div>", unsafe_allow_html=True)
                        if item.get("ref"):
                            st.caption(f"From {item['ref']}")
                    with right:
                        st.checkbox("Hard", value=bool(item.get("hard")), key=f"nh_{note_id}", help="I find this hard to remember",
                                    on_change=_set_note, args=(note_id, "hard", f"nh_{note_id}"))
                        if st.button("Remove", key=f"nr_{note_id}", use_container_width=True):
                            del data["items"][note_id]
                            notes.save(data)
                            st.rerun()
                    st.text_input("My note", value=item.get("note", ""), key=f"nt_{note_id}", placeholder="Add your own reminder",
                                  label_visibility="collapsed", on_change=_set_note, args=(note_id, "note", f"nt_{note_id}"))
    with st.expander("Write your own note", expanded=False):
        with st.form("own_note", clear_on_submit=True):
            code = st.selectbox("Sub-topic", codes, format_func=lambda x: f"{x} {titles[x]}")
            qtype = st.text_input("Type of question", placeholder="Calorimetry: find enthalpy change")
            steps = st.text_area("Steps, one per line", placeholder="Find the mass of water\nUse q = mcΔT\nDivide by moles")
            careful = st.text_input("Be careful with (optional)", placeholder="m is the water, not the fuel")
            if st.form_submit_button("Save note"):
                if notes.add_own(data, code, qtype, steps, careful):
                    notes.save(data)
                    st.rerun()
                else:
                    st.error("Add a type of question and at least one step.")


def web_tips_page(codes: list[str]) -> None:
    st.title("Web tips")
    st.caption("Ideas found online for your cards. Nothing appears on a card until you accept it, and web tips are never treated "
               "as proof of what examiners reward.")
    data = web_tips.load()
    cards = {c["card_id"]: (code, c) for code in codes for c in (load_deck(code) or {}).get("cards", [])}
    labels = dict(PILLAR_TABS)

    todo = [cid for cid, (_code, c) in cards.items() if c.get("walkthrough") and cid not in data["researched"]]
    left, right = st.columns([0.65, 0.35])
    with left:
        pick = st.selectbox("Research a card", ["Next suggested card"] + [i for i, (_s, c) in cards.items() if c.get("walkthrough")], help="Cards you marked Hard in My notes come first.",
                            format_func=lambda x: x if x == "Next suggested card" else f"{x} {cards[x][1]['title']}")
    with right:
        st.write("")
        run = st.button("Search the web", type="primary", use_container_width=True, disabled=not todo and pick == "Next suggested card",
                        help="Uses some of your plan's limit, about a few minutes per card.")
    st.caption(f"{len(data['researched'])} cards researched, {len(todo)} to go.")
    if run:
        cmd = [sys.executable, "-m", "engine.web_improver"] + ([] if pick == "Next suggested card" else ["--card", pick])
        with st.status("Searching the web for this card. This usually takes a few minutes.", expanded=True) as status:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
            st.code((proc.stdout or "") + (proc.stderr or "")[-1500:])
            status.update(label="Finished" if proc.returncode == 0 else "Stopped", state="complete" if proc.returncode == 0 else "error")
        data = web_tips.load()

    waiting = web_tips.pending(data)
    st.subheader(f"Waiting for you ({len(waiting)})")
    if not waiting:
        st.info("Nothing to review. Search the web for a card to find new tips.")
    for tip_id, t in waiting:
        title = cards.get(t["card_id"], (None, {"title": t["card_id"]}))[1]["title"]
        with st.container(border=True):
            st.caption(f"{t['card_id']} {title}  |  {labels.get(t['pillar'], t['pillar'])}  |  {t['kind'].replace('_', ' ')}")
            st.markdown(f"**{html.escape(t['tip'])}**  \n{html.escape(t['why'])}", unsafe_allow_html=True)
            score = web_tips.source_scores(data).get(t["domain"])
            st.markdown(f"Source: <a href='{html.escape(t['url'], quote=True)}' target='_blank' rel='noopener noreferrer'>{html.escape(t['domain'])}</a>"
                        + (f" &nbsp;|&nbsp; {score['accepted']} accepted, {score['rejected']} rejected so far" if score else " &nbsp;|&nbsp; new source"),
                        unsafe_allow_html=True)
            for w in t["warnings"]:
                st.warning(f"This looks {w}: check it fits the IB.", icon=None)
            if t["related"]:
                st.caption("Examiner comments with similar wording, which you can compare: " + ", ".join(t["related"]))
            a, b, _c = st.columns([0.2, 0.2, 0.6])
            if a.button("Accept", key=f"wa_{tip_id}", type="primary", use_container_width=True):
                web_tips.update(lambda d, i=tip_id: web_tips.set_status(d, i, "accepted"))
                st.rerun()
            if b.button("Reject", key=f"wr_{tip_id}", use_container_width=True):
                web_tips.update(lambda d, i=tip_id: web_tips.set_status(d, i, "rejected"))
                st.rerun()

    decided = [(i, t) for i, t in data["tips"].items() if t["status"] in {"accepted", "rejected"}]
    if decided:
        with st.expander(f"Your decisions ({len(decided)})"):
            for tip_id, t in decided:
                a, b = st.columns([0.8, 0.2])
                a.markdown(f"**{t['status'].capitalize()}** ({t['card_id']}, {html.escape(t['domain'])}): {html.escape(t['tip'])}", unsafe_allow_html=True)
                if b.button("Undo", key=f"wu_{tip_id}", use_container_width=True):
                    web_tips.update(lambda d, i=tip_id: web_tips.set_status(d, i, "pending"))
                    st.rerun()
    failed = [t for t in data["tips"].values() if t["status"] == "failed"]
    if failed:
        with st.expander(f"Stopped by the automatic checks ({len(failed)})"):
            for t in failed:
                st.markdown(f"**{html.escape('; '.join(t['reasons']))}** ({html.escape(t['domain'] or 'no source')}): {html.escape(t['tip'])}", unsafe_allow_html=True)
    scores = web_tips.source_scores(data)
    if scores:
        with st.expander(f"How each source has done ({len(scores)})"):
            st.caption("Reliable sources are preferred in later searches, and repeatedly rejected ones are avoided.")
            st.dataframe([{"Source": d, "Accepted": r["accepted"], "Rejected": r["rejected"], "Score": r["score"]} for d, r in scores.items()],
                         hide_index=True, use_container_width=True)


PAGES = ["Progress", "Questionbank", "Study guide", "Tips & my notes", "Key definitions", "Data booklet", "Grade boundaries",
         "Missing markschemes", "Build decks"]
OWNER_PAGES = {"Missing markschemes", "Build decks"}      # adding to the shared library, and spending the owner's Claude plan


def render(page: str) -> None:
    """Draw one Chemistry page. The shell owns page config, theme and the menu."""
    st.markdown(CSS, unsafe_allow_html=True)
    syl = load_syllabus()
    macro = load_json(DATA / "reports" / "macro_by_subtopic.json", {}).get("sub_topics", {})
    gate = load_json(DATA / "reports" / "gate.json", [])
    prog = load_progress()
    codes = [s["code"] for s in syl["sub_topics"]]
    titles = {s["code"]: s["title"] for s in syl["sub_topics"]}

    if page == "Questionbank":
        questionbank(codes, titles, prog)
    elif page in ("Study guide", "Notes", "Foundations"):        # the old names lead here too
        breadcrumbs(SUBJECT, "Study guide")
        guide_ui.study_guide_page(codes, titles, load_deck)
    elif page == "Tips & my notes":
        tips_page(syl, codes, titles)
    elif page == "Key definitions":
        definitions_page(codes, titles)
    elif page == "Data booklet":
        booklet_page()
    elif page == "Grade boundaries":
        boundaries_page()
    elif page == "Progress":
        overview(syl, macro, prog, gate)
    elif page in OWNER_PAGES and not users.is_owner():
        st.info("This page is only for the owner of this IB TEE.")
    elif page == "Missing markschemes":
        missing_page(syl, gate)
    else:
        build_page(syl, gate)
