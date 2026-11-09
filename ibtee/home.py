"""
Platform pages that belong to no single subject: Home, the Subjects catalogue and Bookmarks.
Home reads both subjects' logs: Chemistry's data/attempts.jsonl and Maths' data/maths/attempts.jsonl.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from ibtee import nav, store, users
from ibtee import theme as T

ROOT = Path(__file__).resolve().parents[1]
CHEM_ATTEMPTS = ROOT / "data" / "attempts.jsonl"
SPANISH_DAYS = None


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def activity() -> list[dict]:
    """Both subjects' attempts in one shape: {subject, day, time, ts, label, score, total, correct}."""
    from maths import progress
    out = []
    for a in _jsonl(users.scoped(CHEM_ATTEMPTS)):
        out.append({"subject": "chem_hl", "day": a.get("day", ""), "time": a.get("time", ""), "label": a.get("ref") or a.get("card_id") or "",
                    "detail": a.get("question_type", ""), "score": int(bool(a.get("correct"))), "total": 1, "id": a.get("ref") or ""})
    for r in progress.load():
        if r.get("kind") == "part":
            out.append({"subject": "maths_ai_hl", "day": r["day"], "time": r["time"], "label": f"{r['qid']} ({r['part']})",
                        "detail": r.get("mistake") or r["mode"], "score": r["awarded"], "total": r["marks"], "id": r["qid"]})
    return sorted(out, key=lambda x: (x["day"], x["time"]))


def home_page(today: date) -> None:
    prof = store.profile()
    acts = activity()
    hour = __import__("datetime").datetime.now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 19 else "Good evening"
    st.markdown(f'<div class="kicker">{today:%A, %d %B}</div>', unsafe_allow_html=True)
    top = st.columns([0.75, 0.25], vertical_alignment="bottom")
    with top[0]:
        st.markdown(f'<div class="ptitle">{greet}, {T.esc(prof["name"])}</div>', unsafe_allow_html=True)
        st.markdown('<div class="psub">' + ("Pick a subject and try your first question. It takes two minutes." if not acts
                    else "Carry on where you left off, or start today's recall.") + "</div>", unsafe_allow_html=True)
    with top[1]:
        nav.link("All subjects", key="home_all", icon=":material/library_books:", width="stretch", s="", p="subjects")
    T.rule()
    days = {a["day"] for a in acts}
    from maths import progress
    marks, got = sum(a["total"] for a in acts), sum(a["score"] for a in acts)
    last14 = [sum(1 for a in acts if a["day"] == (today - timedelta(days=i)).isoformat()) for i in range(13, -1, -1)]
    T.stats_strip([("Questions answered", str(len(acts)), "Chemistry questions + Maths parts"),
                   ("Accuracy", f"{100 * got / marks:.0f}%" if marks else "—", "share of marks or answers right"),
                   ("Day streak", str(progress.streak(days, today)), "days in a row")], bars=last14, bars_label=f"{sum(last14)} attempts")
    month_section(today)
    left, right = st.columns([0.62, 0.38], gap="large")
    with left:
        a, b = st.columns([0.7, 0.3], vertical_alignment="bottom")
        a.markdown('<div class="h2">My subjects</div>', unsafe_allow_html=True)
        with b:
            nav.link("Manage", key="home_manage", kind="tertiary", p="subjects")
        mine = prof["my_subjects"]
        if not mine:
            T.empty("No subjects yet", "Add the IB subjects you're taking. They'll show up here and in the sidebar.")
            nav.link("Choose subjects", key="home_choose", kind="primary", icon=":material/arrow_forward:", p="subjects")
        for sid in mine:
            info = store.SUBJECTS[sid]
            with st.container(border=True, key=f"card_my_{sid}"):
                c1, c2 = st.columns([0.75, 0.25], vertical_alignment="center")
                c1.markdown(f'<div class="kicker"><span class="dot" style="--c:{T.SUBJECT_COLOURS[sid]}"></span>{T.esc(info["group"])}</div>'
                            f'<div class="rowtitle" style="font-size:1.25rem">{T.esc(info["name"])}</div><div class="rowdesc">{T.esc(subject_line(sid))}</div>',
                            unsafe_allow_html=True)
                with c2:
                    nav.link("Open", key=f"home_open_{sid}", kind="primary", width="stretch", s=sid)
    with right:
        a, b = st.columns([0.6, 0.4], vertical_alignment="bottom")
        a.markdown('<div class="h2">Recent attempts</div>', unsafe_allow_html=True)
        with b:
            nav.link("Bookmarks", key="home_bm", kind="tertiary", p="bookmarks")
        with st.container(border=True, key="card_recent"):
            if not acts:
                st.markdown("<span class='muted'>Questions you mark will appear here, so you can jump straight back in.</span>", unsafe_allow_html=True)
            for i, a_ in enumerate(reversed(acts[-8:])):
                c1, c2 = st.columns([0.75, 0.25], vertical_alignment="center")
                ok = "ok" if a_["score"] == a_["total"] else "warn" if a_["score"] else "bad"
                c1.markdown(f"<span class='dot' style='--c:{T.SUBJECT_COLOURS[a_['subject']]}'></span> <span class='mono'>{T.esc(a_['label'])}</span>"
                            f"<div class='rowdesc'>{a_['day']} {a_['time']} · {T.esc(a_['detail'])[:40]}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(T.chips((f"{a_['score']}/{a_['total']}", ok)), unsafe_allow_html=True)
                    if a_["subject"] == "maths_ai_hl":
                        nav.link("Open", key=f"recent_{i}_{a_['id']}", kind="tertiary", s="maths_ai_hl", p="q", q=a_["id"])


def month_section(today: date) -> None:
    """This month and the chosen day's tasks. Choosing a day is instant; Edit opens that day on the Calendar page."""
    from ibtee import planner, routine
    from ibtee import calendar_view as cv
    from maths import schedule
    now = schedule.now_local()
    cal = schedule.ensure_month(now)
    planner.board_section("home_board", compact=True)
    nxt = schedule.next_session(cal, now)
    a, b = st.columns([0.7, 0.3], vertical_alignment="center")
    if nxt and routine.subject_of(nxt) == "maths":
        with a:
            nav.link(f"Next: {date.fromisoformat(nxt['date']):%a %d} {nxt['start']} · {cv.short(nxt['title'])[:40]}", key="home_next", kind="primary",
                     s="maths_ai_hl", p="session", ss=nxt["id"])
    elif nxt:
        a.caption(f"Next: {date.fromisoformat(nxt['date']):%a %d} {nxt['start']} · {routine.label(routine.subject_of(nxt))}: {cv.short(nxt['title'])}")
    with b:
        nav.link("Open calendar", key="home_cal", kind="tertiary", p="calendar")


def subject_line(sid: str) -> str:
    if sid == "maths_ai_hl":
        from maths import data
        return f"{len(data.topics())} topics · {len(data.subtopics())} sub-topics · {len(data.questions())} questions · {len(data.sheets())} calculator sheets"
    syl = ROOT / "data" / "syllabus" / "syllabus.json"
    n = len(json.loads(syl.read_text(encoding="utf-8"))["sub_topics"]) if syl.exists() else 0
    decks = len(list((ROOT / "data" / "techniques").glob("*.json")))
    return f"{n} sub-topics · {decks} technique decks · study guide, definitions, data booklet"


def subjects_page() -> None:
    prof = store.profile()
    T.header("Subjects", kicker="Catalogue", sub="Add the subjects you take. Subjects with content open straight away; the others are listed for later.")
    st.markdown(f"**{len(prof['my_subjects'])} added**", unsafe_allow_html=True)
    T.rule()
    groups = store.CATALOGUE
    for row in (groups[:3], groups[3:]):
        cols = st.columns(3, gap="large")
        for col, (group, num, items) in zip(cols, row):
            with col:
                st.markdown(f"<div style='border-top:2px solid var(--ink);padding-top:8px;display:flex;justify-content:space-between'>"
                            f"<span class='kicker' style='color:var(--ink)'>{T.esc(group)}</span><span class='kicker'>Group {num}</span></div>", unsafe_allow_html=True)
                for name, sid, _ in items:
                    a, b = st.columns([0.62, 0.38], vertical_alignment="center")
                    a.markdown(f"<span class='dot' style='--c:{T.SUBJECT_COLOURS.get(sid, '#B8B2A7')}'></span> {T.esc(name)}", unsafe_allow_html=True)
                    with b:
                        if not sid:
                            st.markdown("<span class='muted' style='font-size:0.8rem'>No content yet</span>", unsafe_allow_html=True)
                            continue
                        added = sid in prof["my_subjects"]
                        c1, c2 = st.columns(2)
                        if c1.button("HL ✓" if added else "+ HL", key=f"add_{sid}", type="primary" if added else "secondary",
                                     help="Remove from My subjects" if added else "Add to My subjects"):
                            prof["my_subjects"] = [x for x in prof["my_subjects"] if x != sid] if added else prof["my_subjects"] + [sid]
                            store.save_profile(prof)
                            st.rerun()
                        with c2:
                            nav.link("Open", key=f"open_{sid}", s=sid)
        st.write("")


def bookmarks_page() -> None:
    items = store.bookmarks()
    T.header("Bookmarks", kicker="Saved questions", sub=f"{len(items)} saved question{'s' if len(items) != 1 else ''}, newest first.")
    T.rule()
    if not items:
        T.empty("Nothing saved", "Press Save on any question to keep it here.")
        return
    for b in items:
        with st.container(border=True, key=f"card_bmk_{b['subject']}_{b['id'].replace('.', '_')}"):
            c1, c2, c3 = st.columns([0.6, 0.25, 0.15], vertical_alignment="center")
            c1.markdown(f"<span class='dot' style='--c:{T.SUBJECT_COLOURS.get(b['subject'], '#999')}'></span> <span class='mono'>{T.esc(b['label'])}</span>"
                        f"<div class='rowdesc'>{T.esc(store.SUBJECTS.get(b['subject'], {}).get('name', b['subject']))} · saved {b['added']}</div>", unsafe_allow_html=True)
            c2.markdown(f"<span class='muted'>{T.esc(b.get('detail', ''))}</span>", unsafe_allow_html=True)
            with c3:
                if st.button("Open", key=f"bmo_{b['subject']}_{b['id']}", width="stretch"):
                    if b["subject"] == "maths_ai_hl":
                        st.session_state["q_list"] = {"ids": [x["id"] for x in items if x["subject"] == "maths_ai_hl"], "label": "Bookmarks", "back": {"p": "bookmarks"}}
                        nav.go(s="maths_ai_hl", p="q", q=b["id"])
                    else:
                        st.session_state["qb_topic"] = b.get("detail") or None
                        st.session_state["page"] = "Questionbank"
                        nav.go(s="chem_hl", p="Questionbank")
