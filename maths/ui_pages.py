"""
Mathematics AI HL pages. The shell (app.py) draws the menu and calls render(route).

Routes (?s=maths_ai_hl&p=...): overview · topics · topic&t= · sub&c= · recall · qb · qbt&t= · qbs&c= · q&q= · search · mixed ·
exams · exam&ex= · past · pastset&sess=&pp= · calc · sheet&sh= · errors · calendar · session&ss= · analytics
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components

from ibtee import nav, store, users
from ibtee import theme as T
from maths import data, exams, progress, schedule
from maths import render as pdf
from maths.ui_question import PAST_PAPER, TEXTBOOK, question_card, recall_card, reset, show_image

S = "maths_ai_hl"
NAME = "Mathematics AI HL"
TOPIC_ICONS = {1: ":material/pin:", 2: ":material/show_chart:", 3: ":material/change_history:", 4: ":material/bar_chart:", 5: ":material/functions:"}
PRACTICE_VIEWS = [("mixed", "Mixed practice"), ("exams", "Practice exams"), ("past", "Past papers")]
DOT = T.SUBJECT_COLOURS[S]


def nav_groups() -> list[tuple]:
    """The Maths menu: Overview, the five topics, then the tools that work across topics. (key, label, icon, route)."""
    return [
        (None, [("overview", "Overview", ":material/home:", {"p": "overview"})]),
        ("Topics", [(f"topic{t['n']}", f"{t['n']} · {t['title']}", TOPIC_ICONS.get(t["n"], ":material/circle:"), {"p": "topic", "t": t["n"]})
                    for t in data.topics()]),
        ("Across topics", [("practice", "Mixed, exams & past papers", ":material/timer:", {"p": "mixed"}),
                           ("links", "How topics connect", ":material/hub:", {"p": "links"}),
                           ("errors", "Error log", ":material/report:", {"p": "errors"}),
                           ("calc", "Calculator", ":material/calculate:", {"p": "calc"})]),
    ]


def active_key(r: dict) -> str:
    """Which menu entry a route belongs to."""
    p = r.get("p") or "overview"
    if p in ("topic", "qbt"):
        return f"topic{r.get('t', 1)}"
    if p == "book" and data.book_section(r.get("bs", "")):
        sec = data.book_section(r["bs"])
        return f"topic{data.topic_of(sec['subtopics'][0])}" if sec["subtopics"] else "overview"
    if p in ("sub", "qbs") and r.get("c"):
        return f"topic{data.topic_of(r['c'])}"
    if p == "q" and data.question(r.get("q", "")):
        return f"topic{data.question(r['q'])['topic']}"
    if p in ("mixed", "exams", "exam", "past", "pastset"):
        return "practice"
    if p in ("calendar", "session"):
        return "calendar"            # lives in the main menu (no Maths entry is highlighted)
    return {"sheet": "calc", "errors": "errors", "calc": "calc", "links": "links"}.get(p, "overview")


def view_switch(options: list[tuple[str, str]], current: str, key: str, **route) -> None:
    """The one way to switch views inside a page. The view is kept in the URL (&v=), so Back returns to it."""
    labels = dict(options)
    pick = st.segmented_control("View", [k for k, _ in options], default=current, format_func=lambda k: labels[k],
                                key=f"vs_{key}_{current}", label_visibility="collapsed")
    if pick and pick != current:
        nav.go(**route, v=pick)


def sub_links(codes: list[str], key: str, view: str = "learn", per_row: int = 3) -> None:
    """Buttons to sub-topic pages: the standard way to jump from anything to the sub-topic it is about."""
    codes = [c for c in dict.fromkeys(codes) if data.subtopic(c)]
    if not codes:
        return
    cols = st.columns(min(per_row, len(codes)))
    for i, c in enumerate(codes):
        with cols[i % len(cols)]:
            nav.link(f"{c} {data.sub_title(c)[:34]}", key=f"sl_{key}_{c}", width="stretch", s=S, p="sub", c=c, v=view)


def next_scheduled(codes: list[str]) -> dict | None:
    """The next calendar session (not done, not past) that covers any of these sub-topics."""
    now = schedule.now_local()
    cal = schedule.load()
    live = [x for x in cal.get("sessions", []) if set(x.get("subtopics", [])) & set(codes) and not x.get("done")
            and schedule.status(x, now) in ("now", "upcoming")]
    return min(live, key=lambda x: (x["date"], x["start"])) if live else None


def scheduled_link(codes: list[str], key: str) -> None:
    nxt = next_scheduled(codes)
    if nxt:
        nav.link(f"In your calendar: {date.fromisoformat(nxt['date']):%a %d %b} {nxt['start']}", key=f"sched_{key}",
                 icon=":material/calendar_month:", kind="tertiary", p="calendar", m=nxt["date"][:7], d=nxt["date"])


def mistake_focus_panel(key: str, topic_n: int | None = None) -> None:
    """What your most common open mistakes mean you should do next."""
    for i, f in enumerate(progress.mistake_focus(rows(), topic_n)):
        st.markdown(f"**{T.esc(f['mistake'])}** <span class='muted'>· {f['count']} open</span><br>{T.esc(f['advice'])}", unsafe_allow_html=True)
        cols = st.columns(3)
        for col, c in zip(cols, f["codes"]):
            with col:
                nav.link(f"{f['verb']} {c}", key=f"{key}_{i}_{c}", width="stretch", help=data.sub_title(c), s=S, p="sub", c=c, v=f["view"])


def rows() -> list[dict]:
    if "_m_rows" not in st.session_state or st.session_state.get("_m_rows_at") != _attempts_mtime():
        st.session_state["_m_rows"] = progress.load()
        st.session_state["_m_rows_at"] = _attempts_mtime()
    return st.session_state["_m_rows"]


def _attempts_mtime() -> float:
    path = users.scoped(progress.ATTEMPTS)
    return path.stat().st_mtime if path.exists() else 0.0


def levels() -> dict[str, dict]:
    stamp = _attempts_mtime()
    if st.session_state.get("_m_lv_at") != stamp:
        st.session_state["_m_lv"] = progress.all_levels(rows())
        st.session_state["_m_lv_at"] = stamp
    return st.session_state["_m_lv"]


def missing_data() -> bool:
    have = data.available()
    if all(have.values()):
        return False
    st.error("Some Maths data hasn't been built yet: " + ", ".join(k for k, v in have.items() if not v)
             + ". Run `python -m ingest.maths_syllabus`, `python -m ingest.maths_papers` and `python -m ingest.maths_calculator`.")
    return not have["syllabus"]


def today() -> date:
    return schedule.now_local().date()


def back(label: str, key: str, **target) -> None:
    nav.link(label, key=key, icon=":material/arrow_back:", kind="tertiary", **target)


# =========================================================================== overview
def overview(view: str = "today") -> None:
    T.crumbs("Subjects", NAME)
    T.header(NAME, kicker="IB Mathematics: Applications & Interpretation (AI) Higher Level (HL)", dot=DOT,
             sub=f"{len(data.topics())} topics · {len(data.subtopics())} sub-topics · {len(data.questions())} past-paper questions · {len(data.sheets())} calculator sheets")
    rs, lv, now = rows(), levels(), schedule.now_local()
    ps = progress.parts(rs)
    marks = sum(r["marks"] for r in ps)
    days = {r["day"] for r in rs}
    act = progress.daily_minutes(rs)
    T.stats_strip([("Parts marked", str(len(ps)), f"{len({r['qid'] for r in ps})} questions"),
                   ("Mark rate", f"{100 * sum(r['awarded'] for r in ps) / marks:.0f}%" if marks else "—", "all marked parts"),
                   ("Day streak", str(progress.streak(days, now.date())), "days in a row")],
                  bars=[act.get((now.date() - timedelta(days=i)).isoformat(), 0) for i in range(13, -1, -1)], bars_label=f"{len(rs)}")

    view = view if view in ("today", "progress", "questions") else "today"
    view_switch([("today", "Today"), ("progress", "Progress"), ("questions", "Find a question")], view, "ov", s=S, p="overview")
    if view == "progress":
        analytics_page(embedded=True)
        return
    if view == "questions":
        qb_page(embedded=True)
        return
    left, right = st.columns([0.58, 0.42], gap="large")
    with left:
        st.markdown('<div class="h2">Today</div>', unsafe_allow_html=True)
        due_cards = progress.due_cards(rs, now.date(), include_new_from=[c for c, l in lv.items() if l["index"] > 0])
        retries = progress.due_retries(rs, now.date())
        cal = schedule.ensure()
        nxt = schedule.next_session(cal, now, subject="maths")
        with st.container(border=True, key="card_today"):
            if nxt:
                st_ = schedule.status(nxt, now)
                st.markdown(f"<div class='kicker'>{'Now' if st_ == 'now' else 'Next'} · {date.fromisoformat(nxt['date']):%a %d %b} {nxt['start']} · {nxt['minutes']} min</div>"
                            f"<div class='rowtitle'>{T.esc(nxt['title'])}</div><div class='rowdesc'>{T.esc(nxt['objective'])}</div>", unsafe_allow_html=True)
                nav.link("Open this session", key="ov_sess", kind="primary", icon=":material/play_arrow:", s=S, p="session", ss=nxt["id"])
            else:
                st.markdown("No planned session ahead. Add one in the revision calendar.")
            T.rule()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**{len(due_cards)}** recall cards due")
                nav.link("Daily recall", key="ov_recall", icon=":material/psychology:", disabled=not due_cards, s=S, p="recall")
            with c2:
                st.markdown(f"**{len(retries)}** question parts to retry")
                nav.link("Retry mistakes", key="ov_retry", icon=":material/replay:", disabled=not retries, s=S, p="errors")
            weak = progress.weak_subtopics(lv, rs)
            if weak:
                st.markdown("**Revisit next** (most open mistakes, lowest level):")
                sub_links(weak, "ov_weak", view="learn")
            if progress.mistake_focus(rs):
                T.rule()
                st.markdown("**What your mistakes say to do**")
                mistake_focus_panel("ov_focus")
    with right:
        st.markdown('<div class="h2">Syllabus progress</div>', unsafe_allow_html=True)
        with st.container(border=True, key="card_sylprog"):
            for t in data.topics():
                counts = {l: 0 for l in progress.LEVELS}
                for c in t["subtopics"]:
                    counts[lv[c]["level"]] += 1
                st.markdown(f"<div style='display:flex;justify-content:space-between'><span>{t['n']} · {T.esc(t['title'])}</span>"
                            f"<span class='muted'>{counts['Mastered']}/{len(t['subtopics'])} mastered</span></div>{T.level_bar(counts)}",
                            unsafe_allow_html=True)
            st.markdown(" ".join(T.level_tag(l) for l in progress.LEVELS), unsafe_allow_html=True)

    st.markdown('<div class="h2" style="margin-top:1.2rem">Topics</div>', unsafe_allow_html=True)
    topic_rows()


# =========================================================================== topics
def topic_rows() -> None:
    """The five topics as rows: progress by level, counts, Open."""
    lv = levels()
    for t in data.topics():
        counts = {l: 0 for l in progress.LEVELS}
        for c in t["subtopics"]:
            counts[lv[c]["level"]] += 1
        nq = len(data.questions_for(topic_n=t["n"]))
        with st.container(key=f"card_topic_{t['n']}", border=True):
            a, b, c = st.columns([0.1, 0.65, 0.25], vertical_alignment="center")
            a.markdown(f"<div class='bignum'>0{t['n']}</div>", unsafe_allow_html=True)
            b.markdown(f"<div class='rowtitle'>{T.esc(t['title'])}</div><div class='rowdesc'>"
                       + " · ".join(T.esc(data.sub_title(x)).split(":")[0][:34] for x in t["subtopics"][:6]) + " …</div>"
                       + T.level_bar(counts), unsafe_allow_html=True)
            with c:
                st.markdown(f"<div style='text-align:right'><b>{len(t['subtopics'])}</b> sub-topics<br><span class='muted'>{nq} questions · "
                            f"{counts['Mastered']} mastered</span></div>", unsafe_allow_html=True)
                nav.link("Open", key=f"tp_{t['n']}", width="stretch", s=S, p="topic", t=t["n"])


TOPIC_VIEWS = [("subtopics", "Sub-topics"), ("book", "Textbook"), ("questions", "Questions"), ("calculator", "Calculator"), ("links", "Connections"), ("mistakes", "Mistakes"), ("progress", "Progress")]


def topic_page(n: int, view: str = "subtopics") -> None:
    """Everything for one topic in one place: its sub-topics, questions, calculator procedures, mistakes and progress."""
    t = data.topic(n)
    if not t:
        st.error("Unknown topic.")
        return
    T.crumbs("Subjects", NAME, t["title"])
    lv = levels()
    counts = {l: 0 for l in progress.LEVELS}
    for c in t["subtopics"]:
        counts[lv[c]["level"]] += 1
    T.header(t["title"], kicker=f"{NAME} · Topic {n}", dot=DOT,
             sub=f"{len(t['subtopics'])} sub-topics · {len(data.questions_for(topic_n=n))} questions · "
                 f"{sum(1 for x in data.sheets() if x['topic'] == n)} calculator procedures · {counts['Mastered']} mastered")
    st.markdown(T.level_bar(counts), unsafe_allow_html=True)
    if n == 5:
        st.info("Your revision papers have no Calculus paper, so Calculus questions here are only the ones found inside the other papers "
                "(for example kinematics in Functions). The calculator sheets and textbook worked solutions do cover Calculus.")
    view = view if view in dict(TOPIC_VIEWS) else "subtopics"
    scheduled_link(t["subtopics"], f"tp{n}")
    view_switch(TOPIC_VIEWS, view, f"tp{n}", s=S, p="topic", t=n)
    if view == "questions":
        book_here = data.book_questions(topic_n=n)
        labels = {"past": f"Past papers ({len(data.questions_for(topic_n=n))})", "book": f"Textbook questions ({len(book_here)})"}
        source = st.segmented_control("Source", list(labels), default="past", format_func=labels.get, key=f"tq_src_{n}", label_visibility="collapsed") or "past"
        if source == "book":
            book_question_flow(book_here, f"tqb_{n}")
            return
        codes = ["all"] + t["subtopics"]
        pick = st.selectbox("Sub-topic", codes, key=f"tq_sub_{n}", format_func=lambda c: "All sub-topics" if c == "all" else f"{c} {data.sub_title(c)}")
        pool = data.questions_for(topic_n=n) if pick == "all" else data.questions_for(pick)
        question_list(pool, ctx=t["title"] if pick == "all" else f"{pick} {data.sub_title(pick)}", key=f"tq_{n}_{pick}")
    elif view == "book":
        sections = data.book_sections(topic_n=n)
        st.caption(f"{len(sections)} sections of your Oxford AI HL course book teach this topic. Read a section, or open an exercise beside its worked answers.")
        section_rows(sections, f"tp{n}")
    elif view == "calculator":
        calc_page(topic_n=n, embedded=True)
    elif view == "links":
        topic_links(n)
    elif view == "mistakes":
        errors_page(topic_n=n, embedded=True)
    elif view == "progress":
        analytics_page(topic_n=n, embedded=True)
    else:
        for code in t["subtopics"]:
            s_ = data.subtopic(code)
            l = lv[code]
            nq = len(data.questions_for(code))
            with st.container(key=f"card_sub_{code.replace('.', '_')}", border=True):
                a, b, c, d = st.columns([0.08, 0.6, 0.2, 0.12], vertical_alignment="center")
                a.markdown(f"<div class='rowcode'>{code}</div>", unsafe_allow_html=True)
                b.markdown(f"<div class='rowtitle'>{T.esc(s_['title'])}</div><div class='rowdesc'>{s_['level']} · {T.level_tag(l['level'])}"
                           + (f" · next: {T.esc(l['needs'][0])}" if l["needs"] else "") + "</div>", unsafe_allow_html=True)
                c.markdown(f"<div style='text-align:right'>{nq} questions<br><span class='muted'>{len(data.sheets_for(code))} GDC sheets</span></div>",
                           unsafe_allow_html=True)
                with d:
                    nav.link("Study", key=f"sb_{code}", width="stretch", s=S, p="sub", c=code)


# =========================================================================== sub-topic learning cycle
SUB_VIEWS = [("recall", "1 · Recall"), ("learn", "2 · Learn"), ("calculator", "3 · Calculator"), ("questions", "4 · Questions"), ("review", "5 · Review")]


def subtopic_page(code: str, view: str = "recall") -> None:
    """The learning cycle in five steps: recall what you know; learn it (ideas, steps, formulas, worked examples); the calculator;
    past-paper questions (basic to multi-step and mixed); then review."""
    s = data.subtopic(code)
    if not s:
        st.error("Unknown sub-topic.")
        return
    t = data.topic(data.topic_of(code))
    T.crumbs("Subjects", NAME, t["title"], code)
    back(t["title"], "bk_topic", s=S, p="topic", t=t["n"])
    T.header(f"{code} {s['title']}", kicker=f"{NAME} · {t['title']} · {s['level']}", dot=DOT)
    l = levels()[code]
    scheduled_link([code], f"sub{code}")
    st.markdown(f"{T.level_tag(l['level'])} &nbsp; <span class='muted'>{'Next: ' + T.esc('; '.join(l['needs'])) if l['needs'] else 'Mastered: keep it alive with the spaced checks.'}</span>",
                unsafe_allow_html=True)
    view = view if view in dict(SUB_VIEWS) else "recall"
    view_switch(SUB_VIEWS, view, f"sub{code}", s=S, p="sub", c=code)
    if view == "learn":
        stage_understand(s)
    elif view == "calculator":
        stage_calculator(code)
    elif view == "questions":
        stage_papers(code)
    elif view == "review":
        stage_consolidate(code)
    else:
        stage_recall(code)


def notes_label() -> None:
    st.caption("Study notes written for IB TEE from the IB AI syllabus (not taken from your files). Check them against your textbook; "
               "the questions, markschemes and calculator steps on the other tabs come from your own files.")


def stage_recall(code: str) -> None:
    st.markdown("Before reading anything, test what you already remember. Say or write the answer, then reveal it and rate yourself honestly.")
    cards = progress.recall_cards(code)
    states = progress.card_states(rows())
    i = st.session_state.get(f"rc_i_{code}", 0) % max(1, len(cards))
    st.caption(f"Card {i + 1} of {len(cards)}")
    card = cards[i]
    stt = states.get(card["id"])
    if stt:
        st.caption(f"Seen {stt['reps']}× · next review {stt['due']:%a %d %b}")
    if recall_card(card, key=f"sub_{code}", show_topic=False):
        st.session_state[f"rc_i_{code}"] = i + 1
        st.rerun()


PASSAGE_KINDS = {"note": "Notes", "example": "Worked example", "investigation": "Investigation", "inquiry": "Developing inquiry skills", "summary": "Chapter summary"}


def stage_understand(s: dict) -> None:
    """Step 2: the book's own passages on this sub-topic, as printed; then the short summary written for the app; then how it connects."""
    passages = data.book_passages(s["code"])
    if passages:
        labels = {"book": f"From your textbook ({len(passages)} passages)", "summary": "Summary written for this app"}
        pick = st.segmented_control("Source", list(labels), default="book", format_func=labels.get, key=f"learn_src_{s['code']}", label_visibility="collapsed") or "book"
        if pick == "book":
            book_passage_reader(passages, f"bp_{s['code'].replace('.', '_')}")
        else:
            stage_summary(s)
    else:
        stage_summary(s)
    connection_section(s["code"])


def example_sheet(chapter: int, number: int) -> dict | None:
    """The calculator sheet for this textbook example: the sheets are numbered by the book's chapter and example."""
    return next((x for x in data.sheets() if x["chapter"] == chapter and re.fullmatch(rf"{number}[a-z]?", str(x["example"]))), None)


def corrections_panel(key: str | None) -> None:
    """What the publisher's corrections file says about this question, example or investigation, as printed."""
    for r in data.book_corrections(key) if key else []:
        st.warning("Your book's corrections file lists a change for this one:")
        show_image("corrections", [[r["page"], r["top"], r["bottom"]]])


def book_passage_reader(passages: list[dict], key: str) -> None:
    """One passage of the book at a time, exactly as printed."""
    pick_key = f"{key}_pick"
    st.session_state.setdefault(pick_key, 0)
    st.session_state[pick_key] = min(st.session_state[pick_key], len(passages) - 1)

    def move(step: int) -> None:
        st.session_state[pick_key] += step

    st.selectbox("Passage", range(len(passages)), key=pick_key, format_func=lambda i: f"{i + 1}. {PASSAGE_KINDS[passages[i]['kind']]}: {passages[i]['title'][:70]} · section {passages[i]['section']}")
    i = st.session_state[pick_key]
    p = passages[i]
    st.markdown(T.chips(TEXTBOOK, (PASSAGE_KINDS[p["kind"]], "mono"), f"Chapter {p['chapter']}", f"Section {p['section']}", f"{i + 1} of {len(passages)}"), unsafe_allow_html=True)
    with st.container(border=True, key=f"card_psg_{key}_{p['id'].replace('.', '_')}"):
        show_image("book", p["spans"])
    st.caption("Exactly as printed in your textbook, side notes included. Private study only.")
    if p["kind"] in ("example", "investigation") and p.get("number"):
        corrections_panel(f"{p['chapter']}.{'Example' if p['kind'] == 'example' else 'Investigation'}{p['number']}")
        sheet = example_sheet(p["chapter"], p["number"]) if p["kind"] == "example" else None
        if sheet:
            nav.link(f"Calculator steps for this example: {sheet['title'][:44]}", key=f"{key}_sheet_{p['id']}", icon=":material/calculate:", kind="tertiary", s=S, p="sheet", sh=sheet["id"])
    a, b = st.columns(2)
    a.button("Previous", key=f"{key}_prev", disabled=i == 0, width="stretch", on_click=move, args=(-1,))
    b.button("Next", key=f"{key}_next", type="primary", disabled=i + 1 >= len(passages), width="stretch", on_click=move, args=(1,))


def connection_reasons(r: dict) -> str:
    bits = []
    if r["past"]:
        bits.append(f"{len(r['past'])} past-paper question{'s' * (len(r['past']) != 1)} combine{'s' * (len(r['past']) == 1)} them")
    if r["passages"]:
        bits.append("taught together in textbook section " + ", ".join(r["passages"][:3]))
    if r["sheets"]:
        bits.append(f"same calculator procedure ({r['sheets'][0]})")
    if r["book_questions"]:
        bits.append(f"{r['book_questions']} textbook question{'s' * (r['book_questions'] != 1)} touch both")
    if r["syllabus"]:
        bits.append("linked in the syllabus notes")
    if r["priority"]:
        bits.append("one of your six priority links")
    return " · ".join(bits)


def connection_row(code: str, r: dict, key: str, show_from: bool = False) -> None:
    with st.container(border=True, key=f"card_lk_{key}_{code.replace('.', '_')}_{r['code'].replace('.', '_')}"):
        a, b, c = st.columns([0.62, 0.17, 0.21], vertical_alignment="center")
        lead = f"{code} {T.esc(data.sub_title(code))[:34]} ↔ " if show_from else ""
        a.markdown(f"<div class='rowtitle'>{lead}{r['code']} {T.esc(data.sub_title(r['code']))[:52]}</div><div class='rowdesc'>{T.esc(connection_reasons(r))}</div>", unsafe_allow_html=True)
        with b:
            nav.link("Study", key=f"lk_st_{key}_{code}_{r['code']}", width="stretch", s=S, p="sub", c=r["code"], v="learn")
        with c:
            if r["past"]:
                nav.link("Combined question", key=f"lk_q_{key}_{code}_{r['code']}", width="stretch", help="A past-paper question that uses both", s=S, p="q", q=r["past"][0])


def connection_section(code: str) -> None:
    links = data.connections(code)
    if not links:
        return
    st.markdown("#### How this connects")
    st.caption("Worked out from your own files. Question links come from keyword tags, so a link can occasionally be loose.")
    other = [r for r in links if data.topic_of(r["code"]) != data.topic_of(code)]
    same = [r for r in links if data.topic_of(r["code"]) == data.topic_of(code)]
    for title, group in (("Other topics", other), ("Same topic", same)):
        if group:
            st.markdown(f"<div class='kicker' style='margin-top:0.6rem'>{title}</div>", unsafe_allow_html=True)
            for r in group[:6]:
                connection_row(code, r, "sub")


def topic_links(n: int) -> None:
    """A topic's strongest links to the other four topics."""
    t = data.topic(n)
    rows_ = sorted(((c, r) for c in t["subtopics"] for r in data.connections(c) if data.topic_of(r["code"]) != n), key=lambda x: -x[1]["score"])
    st.caption("The strongest links from this topic to the others, from your past papers, textbook and calculator sheets.")
    if not rows_:
        st.info("No links found yet.")
    for c, r in rows_[:20]:
        connection_row(c, r, f"tp{n}", show_from=True)


def links_page() -> None:
    import pandas as pd
    T.crumbs("Subjects", NAME, "How topics connect")
    T.header("How topics connect", kicker=NAME, dot=DOT, sub="Your six priority links, and how often each pair of topics meets in your files. Topics are visible here on purpose; Mixed practice keeps them hidden.")
    m = data.connection_map()
    if not m:
        st.error("The connections haven't been built. Run `python -m ingest.maths_connections`.")
        return
    st.markdown('<div class="h2" style="font-size:1.6rem">Your six priority links</div>', unsafe_allow_html=True)
    pick = st.selectbox("Link", m["priority"], key="lk_pick", format_func=lambda p: f"{p['name']} ({len(p['questions'])} past-paper questions)")
    sub_links(pick["subtopics"], f"lkp_{pick['name'][:8]}", view="learn")
    source = {"past": f"Past papers ({len(pick['questions'])})", "book": f"Textbook sections ({len(pick['sections'])})"}
    choice = st.segmented_control("Source", list(source), default="past", format_func=source.get, key=f"lk_src_{pick['name'][:8]}", label_visibility="collapsed") or "past"
    if choice == "past":
        question_list([data.question(q) for q in pick["questions"]], ctx=pick["name"][:40], key=f"lkq_{pick['name'][:8]}", page_size=8)
    else:
        section_rows([data.book_section(c) for c in pick["sections"]], f"lks_{pick['name'][:8]}")
    T.rule()
    st.markdown('<div class="h2" style="font-size:1.6rem">Links between topics</div>', unsafe_allow_html=True)
    names = {str(t["n"]): t["title"] for t in data.topics()}
    df = pd.DataFrame({names[y]: {names[x]: (m["topics"][x][y] if x != y else None) for x in names} for y in names})
    st.dataframe(df, width="stretch")
    st.caption("How many sub-topic links join each pair of topics.")


def stage_summary(s: dict) -> None:
    notes_label()
    st.markdown("#### Learning objectives")
    st.markdown("\n".join(f"- {o}" for o in s["objectives"]))
    d = data.depth(s["code"])
    if d.get("i"):
        st.markdown("#### The idea in plain words")
        st.markdown(f"<div class='note'>{T.esc(d['i'])}</div>", unsafe_allow_html=True)
    st.markdown("#### Essential ideas")
    for i, c in enumerate(s["concepts"], 1):
        st.markdown(f"{i}. {c}")
    if d.get("h"):
        st.markdown("#### Going deeper: why it works")
        st.markdown(T.esc(d["h"]), unsafe_allow_html=True)
    st.markdown("#### Step by step")
    st.markdown("\n".join(f"{i}. {m}" for i, m in enumerate(s["method"], 1)))
    st.markdown("#### Formulas")
    stage_formulas(s, label=False)
    if d.get("s"):
        st.markdown("#### Worked example, and why each step")
        with st.container(border=True, key=f"card_worked_{s['code'].replace('.', '_')}"):
            st.markdown(f"**{T.esc(d['q'])}**", unsafe_allow_html=True)
            st.caption("Try it first, then read on.")
            for i, (step, why) in enumerate(d["s"], 1):
                st.markdown(f"{i}. {T.esc(step)}<br><span class='muted'>Why: {T.esc(why)}</span>", unsafe_allow_html=True)
            st.markdown(f"**Answer:** {T.esc(d['a'])}", unsafe_allow_html=True)
    st.markdown("#### Common examination mistakes")
    st.markdown("\n".join(f"- {m}" for m in s["mistakes"]))
    reports = [(q, p) for q in data.questions_for(s["code"], primary_only=True) for p in q["parts"] if p["report_text"].strip()][:3]
    if reports:
        with st.expander(f"What examiners wrote about this sub-topic ({len(reports)} report extracts from your files)"):
            for q, p in reports:
                st.markdown(f"**{q['id']} ({p['label']})**")
                show_image(q["doc"], p["report_spans"])
    worked = [q for q in data.questions_for(s["code"], primary_only=True) if q["has_markscheme"]][:1]
    if worked:
        q = worked[0]
        st.markdown("#### Worked example from a past paper")
        st.caption("Read the question, decide your first step, then open the markscheme and check why each step earns its mark.")
        show_image(q["doc"], q["q_spans"])
        with st.expander("Markscheme, part by part"):
            for p in q["parts"]:
                st.markdown(f"**({p['label']})**" if p["label"] else "**Answer**")
                show_image(q["doc"], p["ms_spans"])
    sections = data.book_sections(s["code"])
    if sections:
        st.markdown("#### Your textbook")
        st.caption("The Oxford AI HL course book sections that teach this, with their exercises beside the worked answers.")
        section_rows(sections, f"learn_{s['code']}")
    chapters = data.worked_chapters(s["code"])
    if chapters:
        st.markdown("#### Worked solutions by chapter")
        st.caption("Your Oxford AI HL worked-solutions files. To try the book's questions one at a time, use step 4 · Questions, then Textbook questions.")
        ch = st.selectbox("Chapter", chapters, key=f"wsch_{s['code']}", format_func=lambda c: f"Chapter {c['chapter']}: {c['title']}")
        pages = list(range(ch["first_page"], ch["last_page"] + 1))
        ex = st.selectbox("Exercise", ["Start of chapter"] + list(ch["exercises"]), key=f"wsex_{s['code']}")
        start = ch["first_page"] if ex == "Start of chapter" else ch["exercises"][ex]
        page = st.number_input("Page in this file", min_value=1, max_value=len(pages), value=pages.index(start) + 1, key=f"wspg_{s['code']}_{ex}")
        path = pdf.page_png(ch["doc"], pages[int(page) - 1])
        if path:
            st.image(str(path), width="stretch")


def stage_formulas(s: dict, label: bool = True) -> None:
    if label:
        notes_label()
    if not s["formulas"]:
        st.info("This sub-topic is mostly method rather than formulas: see Understand and Calculator.")
    for f in s["formulas"]:
        with st.container(border=True, key=f"card_f_{s['code'].replace('.', '_')}_{abs(hash(f['name'])) % 10**6}"):
            st.markdown(f"**{T.esc(f['name'])}**", unsafe_allow_html=True)
            st.latex(f["tex"])
            where, when = data.depth(s["code"]).get("f", {}).get(f["name"], [f["where"], ""])
            if where:
                st.markdown(f"<span class='muted'>Variables:</span> {T.esc(where)}", unsafe_allow_html=True)
            if when:
                st.markdown(f"<span class='muted'>Use it:</span> {T.esc(when)}", unsafe_allow_html=True)
    st.caption("The IB formula booklet is not in your folder, so the app does not say which of these are in it. Check against your booklet.")


def stage_calculator(code: str) -> None:
    sheets = data.sheets_for(code)
    if not sheets:
        st.info("None of your Oxford fx-CG50 sheets is about this sub-topic. Its questions are solved by hand, or with general tools "
                "(graph, table, solver) shown in other sub-topics' sheets.")
        return
    st.markdown("Procedures from your Oxford Casio fx-CG50 sheets. Open one to step through it with the real calculator screens.")
    for sh in sheets:
        sheet_row(sh, f"sc_{code}")


def stage_papers(code: str) -> None:
    """Step 4: past papers and the textbook's questions, investigations and examples, each in its own set."""
    sets = {"past": (f"Past papers ({len(data.questions_for(code))})", None), "book": (f"Textbook questions ({len(data.book_questions(code))})", data.book_questions(code))}
    inv = data.book_features("investigations", code) + data.book_features("inquiry", code)
    examples = data.book_features("examples", code)
    if inv:
        sets["inv"] = (f"Textbook investigations ({len(inv)})", inv)
    if examples:
        sets["ex"] = (f"Textbook worked examples ({len(examples)})", examples)
    pick = st.segmented_control("Source", list(sets), default="past", format_func=lambda k: sets[k][0], key=f"src_{code}", label_visibility="collapsed") or "past"
    if pick == "book":
        book_question_flow(data.book_questions(code), f"bq_{code}")
        return
    if pick in ("inv", "ex"):
        book_feature_view(sets[pick][1], f"bf_{pick}_{code}")
        return
    st.markdown("Past-paper questions on this sub-topic, from basic application to multi-step HL. Attempt before you look.")
    harder = st.toggle("Only harder HL and multi-topic questions", key=f"hard_{code}")
    qs = data.questions_for(code)
    if harder:
        qs = [q for q in qs if data.difficulty(q) in ("Hard HL", "Multi-step") or q.get("cross_topics")]
    st.caption(data.DIFFICULTY_NOTE + " Tags come from keyword rules, so a question may only touch this sub-topic in one part.")
    if not qs:
        st.info("No question in your revision papers is tagged with this sub-topic.")
        return
    question_list(qs, ctx=f"{code} {'harder' if harder else 'questions'}", key=f"sp_{code}_{harder}")


def stage_consolidate(code: str) -> None:
    open_errors = [e for e in progress.error_log(rows()) if not e["resolved"] and (e["concept"] == code or e["subtopic"] == code)]
    if open_errors:
        nav.link(f"{len(open_errors)} open mistake(s) on this sub-topic: see them in the topic's Mistakes", key=f"cons_err_{code}",
                 icon=":material/report:", kind="tertiary", s=S, p="topic", t=data.topic_of(code), v="mistakes")
    st.markdown("Finish the session with a short recall test, then see what to revise again.")
    st_ = progress.subtopic_stats(code, rows())
    l = levels()[code]
    c1, c2, c3 = st.columns(3)
    c1.metric("Parts marked", st_["parts"])
    c2.metric("Recent mark rate", f"{100 * st_['rate']:.0f}%" if st_["rate"] is not None else "—")
    c3.metric("Recall cards secure", f"{st_['cards_secure']}/{st_['cards']}")
    mine = [r for r in progress.parts(rows()) if r["subtopic"] == code]
    good = sorted({f"{r['qid']} ({r['part']})" for r in mine if r["outcome"] == "full"})
    bad = [r for r in mine if r["outcome"] != "full"]
    st.markdown("**What you understood:** " + (", ".join(good[-8:]) if good else "nothing marked full yet."))
    st.markdown("**What you struggled with:** " + ("; ".join(f"{r['qid']} ({r['part']}): {r.get('mistake') or 'marks lost'}" for r in bad[-6:]) if bad else "no lost marks recorded."))
    retries = [k for k in progress.due_retries(rows(), today() + timedelta(days=30)) if progress.part_states(rows())[k]["subtopic"] == code]
    st.markdown("**Revise again:** " + ("; ".join(l["needs"]) if l["needs"] else "nothing new: it comes back on its spaced check.")
                + (f" · {len(retries)} part(s) queued for retry." if retries else ""))
    st.markdown("#### Quick recall test")
    cards = progress.recall_cards(code)
    j = st.session_state.get(f"cons_{code}", 0)
    if j < len(cards):
        if recall_card(cards[j], key=f"cons_{code}", show_topic=False):
            st.session_state[f"cons_{code}"] = j + 1
            st.rerun()
    else:
        st.success("Recall test done.")
        if st.button("Test again", key=f"cons_again_{code}"):
            st.session_state[f"cons_{code}"] = 0
            st.rerun()


# =========================================================================== textbook
def section_rows(sections: list[dict], key: str) -> None:
    """Book sections as rows: title, pages, sub-topics, Read, and one button per exercise."""
    for sec in sections:
        with st.container(border=True, key=f"card_bk_{key}_{sec['code'].replace('.', '_')}"):
            a, b = st.columns([0.78, 0.22], vertical_alignment="center")
            a.markdown(f"<div class='rowtitle'><span class='mono' style='color:var(--accent)'>{sec['code']}</span> &nbsp;{T.esc(sec['title'])}</div>"
                       f"<div class='rowdesc'>Book pages {sec['printed']}–{sec['printed'] + sec['pdf_end'] - sec['pdf_start']} · "
                       + " · ".join(f"{c} {T.esc(data.sub_title(c))[:32]}" for c in sec["subtopics"]) + "</div>", unsafe_allow_html=True)
            with b:
                nav.link("Read", key=f"bkr_{key}_{sec['code']}", icon=":material/menu_book:", width="stretch", s=S, p="book", bs=sec["code"])
            if sec["exercises"]:
                with st.container(horizontal=True, gap="small"):
                    st.markdown("<span class='muted' style='font-size:0.85rem'>Exercises + worked answers:</span>", unsafe_allow_html=True)
                    for ex in sec["exercises"]:
                        nav.link(ex, key=f"bkx_{key}_{ex}", kind="tertiary", s=S, p="book", bs=sec["code"], bx=ex)


def page_viewer(doc: str, pages: list[int], key: str, label: str, printed_offset: int | None = None) -> None:
    """One PDF page at a time with previous/next and a page box. printed_offset turns PDF pages into printed page numbers."""
    if not pages:
        st.caption(f"No {label.lower()} pages found.")
        return
    i = min(st.session_state.get(f"pv_{key}", 0), len(pages) - 1)
    a, b, c = st.columns([0.2, 0.6, 0.2], vertical_alignment="center")
    if a.button("", key=f"pvp_{key}", icon=":material/chevron_left:", disabled=i == 0, width="stretch"):
        st.session_state[f"pv_{key}"] = i - 1
        st.rerun()
    shown = pages[i] - printed_offset if printed_offset is not None else i + 1
    b.markdown(f"<div style='text-align:center' class='muted'>{label} · {'page ' + str(shown) if printed_offset is not None else f'{i + 1} of {len(pages)}'}"
               f"{f' ({i + 1}/{len(pages)})' if printed_offset is not None else ''}</div>", unsafe_allow_html=True)
    if c.button("", key=f"pvn_{key}", icon=":material/chevron_right:", disabled=i + 1 >= len(pages), width="stretch"):
        st.session_state[f"pv_{key}"] = i + 1
        st.rerun()
    path = pdf.page_png(doc, pages[i])
    if path:
        st.image(str(path), width="stretch")
    else:
        st.warning("This PDF is missing from documents to process/MATHS/WORKED ANSWERS.")


def book_page(code: str, ex: str | None = None) -> None:
    """The textbook section as real pages; an exercise opens beside its worked answers."""
    bk = data.book()
    sec = data.book_section(code)
    if not bk or not sec:
        st.error("The course book index hasn't been built. Run `python -m ingest.maths_book`.")
        return
    topic_n = data.topic_of(sec["subtopics"][0]) if sec["subtopics"] else 1
    t = data.topic(topic_n)
    T.crumbs("Subjects", NAME, t["title"], "Textbook", sec["code"])
    back(t["title"] + " · textbook", "bk_book", s=S, p="topic", t=topic_n, v="book")
    T.header(f"{sec['code']} {sec['title']}", kicker=f"Textbook · Oxford AI HL · chapter {sec['chapter']}", dot=DOT,
             sub=f"Book pages {sec['printed']}–{sec['printed'] + sec['pdf_end'] - sec['pdf_start']}. Your own copy, shown as pages: private study only.")
    sub_links(sec["subtopics"], f"bk_{code}", view="learn")
    features = data.book_features("investigations", section=code) + data.book_features("inquiry", section=code)
    examples = data.book_features("examples", section=code)
    review = data.book_review(sec["chapter"])
    views = [("read", "Read the section")] + [(x, f"Exercise {x}") for x in sec["exercises"]]
    views += ([("inv", f"Investigations ({len(features)})")] if features else []) + ([("examples", f"Worked examples ({len(examples)})")] if examples else [])
    views += [("review", f"Chapter {sec['chapter']} review")] if review else []
    current = ex if ex in dict(views) else "read"
    labels = dict(views)
    pick = st.segmented_control("View", [k for k, _ in views], default=current, format_func=lambda k: labels[k],
                                key=f"vs_book_{code}_{current}", label_visibility="collapsed")
    if pick and pick != current:
        nav.go(s=S, p="book", bs=code, bx=None if pick == "read" else pick)
    offset = bk["offset"]
    if current == "read":
        page_viewer("book", list(range(sec["pdf_start"], sec["pdf_end"] + 1)), f"sec_{code}", "Book", printed_offset=offset)
        return
    if current in ("inv", "examples"):
        book_feature_view(features if current == "inv" else examples, f"bkf_{current}_{code}")
        return
    if current == "review":
        st.markdown(T.chips(TEXTBOOK, (f"Chapter {sec['chapter']} review", "mono")), unsafe_allow_html=True)
        left, right = st.columns(2, gap="medium")
        with left:
            page_viewer("book", review["pages"], f"rev_{sec['chapter']}", "Book", printed_offset=offset)
        with right:
            st.markdown("<div class='mshead'>Worked answers</div>", unsafe_allow_html=True)
            if not review["ws_pages"]:
                st.caption("The worked-solutions file has no separate section for this review.")
            elif st.session_state.get(f"show_rev_{sec['chapter']}"):
                page_viewer(review["ws_doc"], review["ws_pages"], f"revws_{sec['chapter']}", "Worked answers")
            elif st.button("Show worked answers", key=f"show_rev_btn_{sec['chapter']}", type="primary"):
                st.session_state[f"show_rev_{sec['chapter']}"] = True
                st.rerun()
        return
    split = data.book_questions(exercise=current)
    if split and not st.toggle("Show the whole pages instead", key=f"bk_pages_{current}"):
        book_question_flow(split, f"bke_{current}", exercises=False)
        return
    book_pages, ws_pages, ws_doc = data.exercise_pages(current)
    st.markdown(T.chips(TEXTBOOK, (f"Exercise {current}", "mono")), unsafe_allow_html=True)
    st.caption("Try the exercise on the left first; the worked answers on the right are the book's own solutions.")
    a, b = st.columns(2, gap="medium")
    with a:
        st.markdown(f"<div class='mshead'>Exercise {current}</div>", unsafe_allow_html=True)
        page_viewer("book", book_pages, f"ex_{current}", "Book", printed_offset=offset)
    with b:
        st.markdown("<div class='mshead'>Worked answers</div>", unsafe_allow_html=True)
        if st.session_state.get(f"show_ws_{current}"):
            page_viewer(ws_doc, ws_pages, f"ws_{current}", "Worked answers")
        else:
            st.markdown("<div class='note'>Hidden until you have tried the exercise.</div>", unsafe_allow_html=True)
            if st.button("Show worked answers", key=f"show_ws_btn_{current}", type="primary"):
                st.session_state[f"show_ws_{current}"] = True
                st.rerun()


# =========================================================================== textbook questions and investigations
FEATURE_NAMES = {"investigation": "Investigation", "inquiry": "Developing inquiry skills", "example": "Worked example"}


def feature_label(f: dict) -> str:
    number = f" {f['number']}" if f["kind"] != "inquiry" else ""
    return f"{FEATURE_NAMES[f['kind']]}{number} · chapter {f['chapter']} · section {f['section']}"


def book_feature_view(items: list[dict], key: str) -> None:
    """The book's investigations or worked examples, as printed."""
    if not items:
        st.info("The textbook has none of these for this part.")
        return
    f = st.selectbox("Choose one", items, key=f"{key}_pick", format_func=feature_label)
    st.markdown(T.chips(TEXTBOOK, (FEATURE_NAMES[f["kind"]], "mono"), f"Chapter {f['chapter']}", f"Section {f['section']}"), unsafe_allow_html=True)
    with st.container(border=True, key=f"card_{key}_{f['id'].replace('.', '_')}"):
        show_image("book", f["spans"])
    if f["kind"] in ("example", "investigation"):
        corrections_panel(f"{f['chapter']}.{'Example' if f['kind'] == 'example' else 'Investigation'}{f['number']}")
    sheet = example_sheet(f["chapter"], f["number"]) if f["kind"] == "example" else None
    if sheet:
        nav.link(f"Calculator steps for this example: {sheet['title'][:44]}", key=f"{key}_sheet", icon=":material/calculate:", kind="tertiary", s=S, p="sheet", sh=sheet["id"])
    if f["kind"] != "example":
        st.caption("As printed in your textbook. The book has no marked answers for these, so nothing here is scored.")


def book_question_flow(qs: list[dict], key: str, exercises: bool = True) -> None:
    """One textbook question at a time: try it, reveal the book's worked answer, say how it went. Never counts towards Mastered."""
    if not qs:
        st.info("No textbook exercise question is linked to this part. The book's pages are under Learn.")
        return
    states = progress.book_states(rows())
    a, b = st.columns(2)
    names = list(dict.fromkeys(q["exercise"] for q in qs))
    ex = a.selectbox("Exercise", ["All"] + names, key=f"{key}_ex", format_func=lambda n: "All exercises" if n == "All" else f"Exercise {n}") if exercises and len(names) > 1 else "All"
    show = b.selectbox("Show", ["All", "Not tried yet", "Not right yet"], key=f"{key}_show")
    shown = [q for q in qs if (ex == "All" or q["exercise"] == ex) and (show == "All" or (show == "Not tried yet" and q["id"] not in states)
                                                                        or (show == "Not right yet" and states.get(q["id"]) in ("partly", "wrong")))]
    done = sum(1 for q in qs if states.get(q["id"]) == "right")
    st.caption(f"{done} of {len(qs)} right so far. These are your textbook's own questions, kept apart from past papers; they don't count towards Mastered.")
    if not shown:
        st.success("Nothing left in this list.")
        return
    state_key = f"{key}_i_{ex}_{show}"
    i = min(st.session_state.get(state_key, 0), len(shown) - 1)
    q = shown[i]
    status = {"right": ("Got it", "ok"), "partly": ("Partly", "warn"), "wrong": ("Not yet", "bad")}.get(states.get(q["id"]))
    st.markdown(T.chips(TEXTBOOK, (f"Exercise {q['exercise']} · Question {q['number']}", "mono"), f"Section {q['section']}", f"{i + 1} of {len(shown)}", *((status,) if status else ())),
                unsafe_allow_html=True)
    with st.container(border=True, key=f"card_bq_{key}_{q['id'].replace('.', '_')}"):
        show_image("book", q["spans"])
    corrections_panel(q["id"])
    reveal = f"{key}_show_{q['id']}"
    if st.session_state.get(reveal):
        st.markdown("<div class='mshead'>Worked answer (from your book's worked solutions)</div>", unsafe_allow_html=True)
        if q["ws_spans"]:
            with st.container(border=True, key=f"card_ba_{key}_{q['id'].replace('.', '_')}"):
                show_image(q["ws_doc"], q["ws_spans"])
        else:
            st.warning("No worked answer for this question could be matched in your worked-solutions files.")
        sub_links(q["subtopics"], f"{key}_subs_{q['id']}", view="learn")
        cols = st.columns(3)
        for col, (result, label) in zip(cols, [("right", "Got it"), ("partly", "Partly"), ("wrong", "Not yet")]):
            if col.button(label, key=f"{key}_{result}_{q['id']}", width="stretch", type="primary" if result == "right" else "secondary"):
                progress.log({"kind": "book", "qid": q["id"], "exercise": q["exercise"], "subtopic": q["subtopics"][0] if q["subtopics"] else None, "result": result})
                st.session_state.pop(reveal, None)
                if show == "All":
                    st.session_state[state_key] = min(i + 1, len(shown) - 1)
                st.rerun()
    elif st.button("Show worked answer", key=f"{key}_rev_{q['id']}", type="primary"):
        st.session_state[reveal] = True
        st.rerun()
    c1, c2 = st.columns(2)
    if c1.button("Previous", key=f"{key}_prev", disabled=i == 0, width="stretch"):
        st.session_state[state_key] = i - 1
        st.rerun()
    if c2.button("Next", key=f"{key}_next", disabled=i + 1 >= len(shown), width="stretch"):
        st.session_state[state_key] = i + 1
        st.rerun()


# =========================================================================== daily recall
def recall_page() -> None:
    T.crumbs("Subjects", NAME, "Daily recall")
    back("Overview", "bk_ov", s=S, p="overview")
    T.header("Daily recall", kicker=NAME, dot=DOT, sub="Cards due today, most overdue first, then new cards from sub-topics you have started.")
    lv = levels()
    started = [c for c, l in lv.items() if l["index"] > 0]
    scope = st.radio("Cards from", ["Started sub-topics", "Whole syllabus"], horizontal=True, key="rc_scope")
    due = progress.due_cards(rows(), today(), include_new_from=started if scope == "Started sub-topics" else None, limit=25)
    if not due:
        T.empty("Nothing due", "Every card you have started is scheduled for later. Start a sub-topic's Recall stage to add new cards.")
        return
    st.caption(f"{len(due)} cards in this session")
    nav.link(f"Revise {due[0]['subtopic']} {data.sub_title(due[0]['subtopic'])[:40]}", key="rc_sub", kind="tertiary",
             icon=":material/school:", s=S, p="sub", c=due[0]["subtopic"], v="learn")
    if recall_card(due[0], key="daily"):
        st.rerun()


# =========================================================================== question bank
def qb_page(embedded: bool = False) -> None:
    if not embedded:
        T.crumbs("Subjects", NAME, "Question bank")
        T.header("Question bank", kicker=NAME, dot=DOT, sub=f"{len(data.topics())} topics · {len(data.questions())} questions from your HL revision papers (IB 2021–2025)")
    else:
        st.caption(f"{len(data.questions())} past-paper questions from your HL revision papers (IB 2021–2025). Search them all, or open a topic's questions. "
                   f"The {len(data.book_questions())} textbook questions are kept apart, in each sub-topic's Questions step.")
    with st.form("qb_search", border=False):
        a, b = st.columns([0.8, 0.2], vertical_alignment="bottom")
        text = a.text_input("Search questions and markschemes", placeholder="e.g. eigenvalue, annuity, 23M.1, Voronoi")
        if b.form_submit_button("Search", width="stretch", type="primary") and text.strip():
            st.session_state["qb_query"] = text.strip()
            nav.go(s=S, p="search")
    T.rule()
    for t in data.topics():
        qs = data.questions_for(topic_n=t["n"])
        subs = sorted({c for q in qs for c in q["subtopics"] if data.topic_of(c) == t["n"]}, key=data.code_key)
        with st.container(key=f"card_qbt_{t['n']}", border=True):
            a, b, c = st.columns([0.1, 0.68, 0.22], vertical_alignment="center")
            a.markdown(f"<div class='bignum'>0{t['n']}</div>", unsafe_allow_html=True)
            b.markdown(f"<div class='rowtitle'>{T.esc(t['title'])}</div><div class='rowdesc'>" +
                       " · ".join(T.esc(data.sub_title(x).split(';')[0].split(':')[0][:40]) for x in subs[:6]) + "</div>", unsafe_allow_html=True)
            with c:
                st.markdown(f"<div style='text-align:right'><b>{len(qs)}</b> questions<br><span class='muted'>{len(subs)} sub-topics</span></div>", unsafe_allow_html=True)
                nav.link("Open", key=f"qbt_{t['n']}", width="stretch", s=S, p="topic", t=t["n"], v="questions")
    problems = data.bank().get("report", {}).get("problems", [])
    if problems:
        with st.expander("Notes on your source files"):
            st.markdown("\n".join(f"- {p}" for p in problems))


def question_list(qs: list[dict], ctx: str, key: str, page_size: int = 12) -> None:
    """Filters + a preview of each question; Open goes to the full question view with the list as its navigator."""
    f1, f2, f3 = st.columns([0.3, 0.45, 0.25])
    paper = f1.selectbox("Type", ["All papers", "Paper 1", "Paper 2"], key=f"{key}_paper")
    diffs = f2.pills("Difficulty", data.DIFFICULTIES, selection_mode="multi", key=f"{key}_diff")
    done = f3.selectbox("Status", ["All", "Not tried", "Lost marks", "Full marks"], key=f"{key}_done")
    last = {}
    for r in progress.parts(rows()):
        last.setdefault(r["qid"], []).append(r)
    def status(q):
        rs = last.get(q["id"])
        if not rs:
            return "Not tried"
        return "Full marks" if all(r["outcome"] == "full" for r in rs[-len(q["parts"]):]) else "Lost marks"
    shown = [q for q in qs if (paper == "All papers" or q["paper"] == paper[-1]) and (not diffs or data.difficulty(q) in diffs)
             and (done == "All" or status(q) == done)]
    with st.container(border=True, key=f"card_cnt_{key}"):
        st.markdown(f"**{len(shown)}** of {len(qs)} questions", unsafe_allow_html=True)
    limit = st.session_state.get(f"{key}_lim", page_size)
    for i, q in enumerate(shown[:limit], 1):
        with st.container(border=True, key=f"card_ql_{key}_{q['id'].replace('.', '_')}"):
            a, b = st.columns([0.8, 0.2], vertical_alignment="center")
            a.markdown(f"<span class='muted mono'>{i}</span> &nbsp;" + T.chips(PAST_PAPER, (q["id"], "mono"), f"{q['max_marks']} marks",
                       (data.difficulty(q), {"Basic": "ok", "Standard": "warn"}.get(data.difficulty(q), "bad")), f"Paper {q['paper']}", status(q))
                       .replace('<div class="chips">', '<span class="chips" style="display:inline-flex">').replace("</div>", "</span>")
                       + f"<div class='rowdesc'>{T.esc(data.snippet(q))}</div>", unsafe_allow_html=True)
            with b:
                if st.button("Open", key=f"open_{key}_{q['id']}", width="stretch"):
                    st.session_state["q_list"] = {"ids": [x["id"] for x in shown], "label": ctx, "back": dict(nav.route())}
                    nav.go(s=S, p="q", q=q["id"])
    if len(shown) > limit and st.button(f"Show more ({len(shown) - limit} left)", key=f"{key}_more", width="stretch"):
        st.session_state[f"{key}_lim"] = limit + page_size
        st.rerun()


def search_page() -> None:
    T.crumbs("Subjects", NAME, "Question bank", "Search")
    back("Find a question", "bk_qb2", s=S, p="overview", v="questions")
    text = st.text_input("Search", value=st.session_state.get("qb_query", ""), key="qb_query_in")
    st.session_state["qb_query"] = text
    found = data.search(text)
    T.header(f"“{text}”" if text else "Search", kicker=f"{NAME} · Question bank", dot=DOT, sub=f"{len(found)} questions mention every word")
    if found:
        question_list(found, ctx=f"Search: {text}", key="search")


def question_page(qid: str) -> None:
    q = data.question(qid)
    if not q:
        st.error(f"Question {qid} isn't in the bank.")
        return
    ctx = st.session_state.get("q_list") or {"ids": [qid], "label": q["id"], "back": {"s": S, "p": "qb"}}
    if qid not in ctx["ids"]:
        ctx = {"ids": [qid], "label": q["id"], "back": {"s": S, "p": "qb"}}
    t = data.topic(q["topic"])
    T.crumbs("Subjects", NAME, t["title"], ctx["label"][:40])
    main, side = st.columns([0.72, 0.28], gap="large")
    with main:
        if st.button(ctx["label"][:60], key="q_back", icon=":material/arrow_back:", type="tertiary"):
            nav.go(**ctx["back"])
        mode = "review" if ctx.get("review") else "practice"
        question_card(q, mode=mode, key="main")
        state = st.session_state.get(f"qs_main_{qid}", {})
        if state.get("marked"):
            i = ctx["ids"].index(qid)
            if i + 1 < len(ctx["ids"]):
                nav.link("Next question", key="q_next_after", kind="primary", icon=":material/arrow_forward:", shortcut="Right", s=S, p="q", q=ctx["ids"][i + 1])
        history(qid)
    with side:
        related_panel(q)
        i = ctx["ids"].index(qid)
        with st.container(border=True, key="card_qnav"):
            a, b, c = st.columns([0.6, 0.2, 0.2], vertical_alignment="center")
            a.markdown(f"**Question {i + 1}** <span class='muted'>of {len(ctx['ids'])}</span>", unsafe_allow_html=True)
            with b:
                nav.link("", key="q_prev", icon=":material/chevron_left:", disabled=i == 0, s=S, p="q", q=ctx["ids"][max(0, i - 1)])
            with c:
                nav.link("", key="q_nxt", icon=":material/chevron_right:", disabled=i + 1 >= len(ctx["ids"]), s=S, p="q", q=ctx["ids"][min(len(ctx['ids']) - 1, i + 1)])
            lo = max(0, min(i - 6, len(ctx["ids"]) - 14))
            with st.container(horizontal=True, gap="small"):
                for j, other in enumerate(ctx["ids"][lo:lo + 14], lo):
                    oq = data.question(other)
                    if not oq:
                        continue
                    nav.link(f"{j + 1} · {other}", key=f"q_go_{other}", kind="primary" if other == qid else "secondary", width="stretch",
                             help=f"{oq['max_marks']} marks · {data.difficulty(oq)}", s=S, p="q", q=other)
        with st.container(border=True, key="card_keys"):
            st.markdown("<div class='kicker'>Shortcuts</div>"
                        "<div style='display:flex;justify-content:space-between'><span>Show markscheme</span><span class='kbd'>Space</span></div>"
                        "<div style='display:flex;justify-content:space-between'><span>Next question</span><span class='kbd'>→</span></div>",
                        unsafe_allow_html=True)


def related_panel(q: dict) -> None:
    """Everything connected to this question: its sub-topics, its topic, the calculator procedure, when it is scheduled."""
    marked = st.session_state.get(f"qs_main_{q['id']}", {}).get("marked")
    with st.container(border=True, key="card_related"):
        st.markdown("<div class='kicker'>Related</div>", unsafe_allow_html=True)
        for c in q["subtopics"][:4]:
            nav.link(f"{c} {data.sub_title(c)[:30]}", key=f"rel_{c}", icon=":material/school:", width="stretch", s=S, p="sub", c=c, v="learn")
        t = data.topic(q["topic"])
        nav.link(f"Topic: {t['title']}", key="rel_topic", icon=TOPIC_ICONS.get(t["n"]), width="stretch", s=S, p="topic", t=t["n"])
        sheets = [x for c in q["subtopics"][:2] for x in data.sheets_for(c)][:2]
        for sh in sheets:
            nav.link(f"GDC: {sh['title'][:30]}", key=f"rel_sh_{sh['id']}", icon=":material/calculate:", width="stretch", s=S, p="sheet", sh=sh["id"])
        for sec in data.book_sections(q["subtopics"][0])[:1] if q["subtopics"] else []:
            nav.link(f"Textbook {sec['code']}: {sec['title'][:24]}", key=f"rel_bk_{sec['code']}", icon=":material/menu_book:", width="stretch", s=S, p="book", bs=sec["code"])
        scheduled_link(q["subtopics"][:2], f"rel_{q['id']}")
        if marked and any(r["outcome"] != "full" for r in marked):
            nav.link("See it in the error log", key="rel_err", icon=":material/report:", kind="tertiary", s=S, p="errors")


def history(qid: str) -> None:
    mine = [r for r in progress.parts(rows()) if r["qid"] == qid]
    with st.expander(f"Your attempts  {len({r['ts'] // 60 for r in mine}) if mine else 0}" + (f" · last {mine[-1]['day']}" if mine else "")):
        if not mine:
            st.caption("No attempts yet.")
        for r in reversed(mine[-20:]):
            st.markdown(f"{r['day']} {r['time']} · ({r['part']}) {r['awarded']}/{r['marks']} · {r['mode']}"
                        + (f" · {r['mistake']}" if r.get("mistake") else "") + (" · with hints" if r.get("helped") else ""))
        if mine and st.button("Try it again now", key=f"again_{qid}"):
            reset("main", data.question(qid))
            st.rerun()


# =========================================================================== practice: mixed, exams, past papers
PRACTICE_INTRO = {
    "mixed": "Questions from different topics with the topic hidden. Recognising which method a question needs is the skill being trained.",
    "exams": "Timed papers built from real IB questions at exam length (Paper 1 and 2: 120 min, 110 marks). Mark them against the markscheme afterwards.",
    "past": "Your revision papers hold real IB questions. Here they are grouped by the exam they first appeared in.",
}


def practice_head(view: str) -> None:
    """One page, three views: the practice that works across topics."""
    T.crumbs("Subjects", NAME, "Practice", dict(PRACTICE_VIEWS)[view])
    T.header("Practice", kicker=NAME, dot=DOT, sub="Across all topics: mixed questions, timed papers and past-paper sessions.")
    labels = dict(PRACTICE_VIEWS)
    pick = st.segmented_control("View", [k for k, _ in PRACTICE_VIEWS], default=view, format_func=lambda k: labels[k],
                                key=f"vs_practice_{view}", label_visibility="collapsed")
    if pick and pick != view:
        nav.go(s=S, p=pick)
    st.caption(PRACTICE_INTRO[view])
def mixed_page() -> None:
    practice_head("mixed")
    run = st.session_state.get("mixed_run")
    if not run:
        lv = levels()
        studied = [c for c, l in lv.items() if l["index"] > 0]
        with st.container(border=True, key="card_mixed_setup"):
            scope = st.radio("Questions from", ["Synoptic: questions that combine topics", "Any topic", "Cumulative: sub-topics you have studied",
                                                "Weekly topic review"], key="mx_scope")
            topic_n = None
            if scope.startswith("Weekly"):
                topic_n = st.selectbox("Topic", [t["n"] for t in data.topics()], format_func=lambda n: data.topic(n)["title"], key="mx_topic")
            n = st.slider("Number of questions", 3, 15, 6, key="mx_n")
            if scope.startswith("Cumulative") and not studied:
                st.info("You haven't started any sub-topic yet, so a cumulative test would be empty. Choose another option.")
            if st.button("Start", type="primary", key="mx_start", disabled=scope.startswith("Cumulative") and not studied):
                seed = f"{time.time()}"
                if scope.startswith("Weekly"):
                    pool = [q for q in data.questions_for(topic_n=topic_n) if q["has_markscheme"]]
                    qs = progress.ranked(pool, rows(), seed)[:n]
                else:
                    kind = "synoptic" if scope.startswith("Synoptic") else "cumulative" if scope.startswith("Cumulative") else "all"
                    qs = progress.mixed_set(rows(), n, seed, kind, studied)
                st.session_state["mixed_run"] = {"ids": [q["id"] for q in qs], "i": 0, "id": seed[-8:], "scope": scope}
                st.rerun()
        st.caption("All from past papers. Topics stay hidden until you have marked a question; then the app shows what it tested. Sub-topics you struggle with come up more often, "
                   "ones you have mastered less.")
        return
    ids, i = run["ids"], run["i"]
    if i >= len(ids):
        done = [r for r in progress.parts(rows()) if r.get("session") == run["id"]]
        got, tot = sum(r["awarded"] for r in done), sum(r["marks"] for r in done)
        st.success(f"Set finished: {got}/{tot} marks." if tot else "Set finished.")
        by = {}
        for r in done:
            by.setdefault(data.topic(r["topic"])["title"], [0, 0])
            by[data.topic(r["topic"])["title"]][0] += r["awarded"]
            by[data.topic(r["topic"])["title"]][1] += r["marks"]
        for k, (a, b) in by.items():
            st.markdown(f"- {k}: {a}/{b}")
        met = sorted({name for qid in ids for name in progress.connections_of(data.question(qid))})
        if met:
            st.caption("Links between topics in this set: " + "; ".join(met))
        if st.button("New set", type="primary", key="mx_new"):
            del st.session_state["mixed_run"]
            st.rerun()
        return
    st.progress(i / len(ids), text=f"Question {i + 1} of {len(ids)} · {run['scope'].split(':')[0]}")
    q = data.question(ids[i])
    question_card(q, mode="mixed", key=f"mx{run['id']}", session=run["id"])
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("End set", key="mx_end"):
            run["i"] = len(ids)
            st.rerun()
        marked = st.session_state.get(f"qs_mx{run['id']}_{q['id']}", {}).get("marked")
        if st.button("Next" if marked else "Skip", key=f"mx_next_{i}", type="primary" if marked else "secondary"):
            run["i"] += 1
            st.rerun()


# =========================================================================== practice exams
def exams_page() -> None:
    practice_head("exams")
    store_ = exams.load()
    with st.container(border=True, key="card_newexam"):
        st.markdown('<div class="h2" style="font-size:1.6rem">New practice paper</div>', unsafe_allow_html=True)
        a, b = st.columns([0.3, 0.7])
        paper = a.selectbox("Paper", ["1", "2"], format_func=lambda p: f"Paper {p} style", key="ex_paper")
        tps = b.multiselect("Topics", [t["n"] for t in data.topics()][:4], default=[1, 2, 3, 4], key="ex_topics",
                            format_func=lambda n: data.topic(n)["title"], help="There are no Calculus revision papers in your folder.")
        full = st.toggle("Full length (110 marks)", value=True, key="ex_full")
        target = None if full else st.slider("Marks", 20, 100, 50, step=5, key="ex_marks")
        if st.button("Build paper", type="primary", disabled=not tps, key="ex_build"):
            e = exams.build(paper, tps, rows(), target=target)
            store_["exams"].insert(0, e)
            exams.save(store_)
            nav.go(s=S, p="exam", ex=e["id"])
        st.caption("Paper 3 (extended investigation questions) is not in your files, so it cannot be simulated.")
    if store_["exams"]:
        st.markdown('<div class="h2">Your papers</div>', unsafe_allow_html=True)
        for e in store_["exams"]:
            got, tot = exams.score(e)
            with st.container(border=True, key=f"card_ex_{e['id']}"):
                a, b, c = st.columns([0.5, 0.3, 0.2], vertical_alignment="center")
                a.markdown(f"**Paper {e['paper']}** · {', '.join(data.topic(t)['title'] for t in e['topics'])}<br><span class='muted'>{e['created']} · "
                           f"{len(e['qids'])} questions · {e['total']} marks · {e['minutes']} min</span>", unsafe_allow_html=True)
                b.markdown({"ready": "Not started", "running": "In progress", "marking": "Waiting to be marked", "done": f"**{got}/{tot}** ({100 * got / max(1, tot):.0f}%)"}[e["status"]],
                           unsafe_allow_html=True)
                with c:
                    nav.link("Open", key=f"exo_{e['id']}", width="stretch", s=S, p="exam", ex=e["id"])


def timer(seconds_left: int, key: str) -> None:
    components.html(f"""
<div id="t" style="font-family:'IBM Plex Mono',monospace;font-size:28px;font-weight:600;text-align:center;padding:6px;border:1px solid #E2E7EF;border-radius:12px;background:#fff;color:#0F1B2D">--:--</div>
<script>
var end = Date.now() + {seconds_left} * 1000;
function tick() {{
  var s = Math.max(0, Math.round((end - Date.now()) / 1000));
  var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  var el = document.getElementById('t');
  el.textContent = (h ? h + ':' : '') + String(m).padStart(2, '0') + ':' + String(x).padStart(2, '0');
  el.style.color = s < 300 ? '#D1435B' : '#0F1B2D';
  if (s > 0) setTimeout(tick, 500); else el.textContent = 'Time is up';
}}
tick();
</script>""", height=60)


def exam_page(eid: str) -> None:
    store_ = exams.load()
    e = next((x for x in store_["exams"] if x["id"] == eid), None)
    if not e:
        st.error("This paper no longer exists.")
        return
    T.crumbs("Subjects", NAME, "Practice exams", f"Paper {e['paper']} · {e['created']}")
    back("Practice exams", "bk_ex", s=S, p="exams")
    T.header(f"Practice Paper {e['paper']}", kicker=f"{NAME} · {e['total']} marks · {e['minutes']} minutes", dot=DOT)
    if e["status"] == "ready":
        st.markdown(f"{len(e['qids'])} questions, {e['total']} marks, **{e['minutes']} minutes**. Calculator allowed. "
                    "Hints and markschemes stay hidden until you finish.")
        if st.button("Start the clock", type="primary", key="ex_go"):
            e["status"], e["started"] = "running", time.time()
            exams.save(store_)
            st.rerun()
        return
    if e["status"] == "running":
        left = exams.remaining_seconds(e)
        a, b = st.columns([0.7, 0.3], vertical_alignment="center")
        a.markdown(f"Started {datetime.fromtimestamp(e['started']):%H:%M}. Write your answers on paper.")
        with b:
            timer(left, eid)
        for n, qid in enumerate(e["qids"], 1):
            q = data.question(qid)
            st.markdown(f"<div class='h2' style='font-size:1.5rem'>Question {n} <span class='muted' style='font-size:1rem'>[{q['max_marks']} marks]</span></div>", unsafe_allow_html=True)
            with st.container(border=True, key=f"card_exq_{eid}_{n}"):
                show_image(q["doc"], q["q_spans"])
        if st.button("Finish and mark", type="primary", key="ex_finish", width="stretch"):
            e["status"], e["finished"] = "marking", time.time()
            exams.save(store_)
            st.rerun()
        return
    used = (e["finished"] - e["started"]) / 60 if e.get("finished") and e.get("started") else None
    got, tot = exams.score(e)
    marked = [qid for qid in e["qids"] if qid in e.get("marks", {})]
    st.markdown(f"Time used: **{used:.0f} of {e['minutes']} min**" if used else "", unsafe_allow_html=True)
    T.stats_strip([("Score", f"{got}/{tot}", f"{len(marked)} of {len(e['qids'])} questions marked"),
                   ("Percentage", f"{100 * got / max(1, tot):.0f}%", "of the marks in this paper"),
                   ("Questions", str(len(e["qids"])), f"Paper {e['paper']} style")])
    st.caption("No grade is shown: Maths AI grade boundaries are not in your files.")
    bt = exams.by_topic(e)
    if marked:
        cols = st.columns(len(bt))
        for col, (t, (a_, b_)) in zip(cols, bt.items()):
            with col:
                nav.link(f"{data.topic(t)['title']}: {a_}/{b_}", key=f"exr_{t}", width="stretch", help="Open this topic's mistakes",
                         s=S, p="topic", t=t, v="mistakes")
    for n, qid in enumerate(e["qids"], 1):
        q = data.question(qid)
        done = e.get("marks", {}).get(qid)
        with st.expander(f"Question {n} · {qid} · " + (f"{sum(done.values())}/{q['max_marks']}" if done else f"to mark ({q['max_marks']} marks)"), expanded=not done and qid == next((x for x in e["qids"] if x not in e.get("marks", {})), None)):
            def saved(rows_, qid=qid):
                st_ = exams.load()
                ex = next(x for x in st_["exams"] if x["id"] == eid)
                ex.setdefault("marks", {})[qid] = {r["part"]: r["awarded"] for r in rows_}
                if all(x in ex["marks"] for x in ex["qids"]):
                    ex["status"] = "done"
                exams.save(st_)
            if done:
                st.caption("Marked. Open the question bank to try it again later.")
            else:
                question_card(q, mode="exam_mark", key=f"ex{eid}", session=f"exam-{eid}", on_done=saved)


# =========================================================================== past papers
def past_page() -> None:
    practice_head("past")
    st.caption("These are the questions your revision papers selected from each exam, not complete papers.")
    groups: dict[tuple, list] = {}
    for q in data.questions():
        groups.setdefault((q["session_code"], q["paper"]), []).append(q)
    codes = sorted({k[0] for k in groups}, key=data.session_sort_key)
    with st.container(border=True, key="card_past"):
        hdr = st.columns([0.4, 0.2, 0.2, 0.2])
        for h, txt in zip(hdr, ["SESSION", "PAPER 1", "PAPER 2", "MARKS"]):
            h.markdown(f"<span class='kicker'>{txt}</span>", unsafe_allow_html=True)
        for code in codes:
            cols = st.columns([0.4, 0.2, 0.2, 0.2], vertical_alignment="center")
            sample = next(q for k, qs in groups.items() if k[0] == code for q in qs)
            cols[0].markdown(f"**{sample['session']}** <span class='muted mono'>{code}</span>", unsafe_allow_html=True)
            for col, paper in zip(cols[1:3], ["1", "2"]):
                qs = groups.get((code, paper), [])
                with col:
                    nav.link(f"{len(qs)} questions", key=f"pp_{code}_{paper}", disabled=not qs, s=S, p="pastset", sess=code, pp=paper)
            cols[3].markdown(str(sum(q["max_marks"] for k, qs in groups.items() if k[0] == code for q in qs)))


def pastset_page(code: str, paper: str) -> None:
    qs = sorted((q for q in data.questions() if q["session_code"] == code and q["paper"] == paper), key=lambda q: q["number"] if not q["ref"] else int(q["ref"].split(".")[-1]))
    if not qs:
        st.error("No questions for this session.")
        return
    T.crumbs("Subjects", NAME, "Past papers", f"{qs[0]['session']} Paper {paper}")
    back("Past papers", "bk_pp", s=S, p="past")
    T.header(f"{qs[0]['session']} · Paper {paper}", kicker=NAME, dot=DOT, sub=f"{len(qs)} questions · {sum(q['max_marks'] for q in qs)} marks")
    question_list(qs, ctx=f"{qs[0]['session']} P{paper}", key=f"ps_{code}_{paper}")


# =========================================================================== calculator centre
def sheet_row(sh: dict, key: str) -> None:
    with st.container(border=True, key=f"card_sh_{key}_{sh['id']}"):
        a, b = st.columns([0.82, 0.18], vertical_alignment="center")
        a.markdown(f"<div class='rowtitle'>{T.esc(sh['title'])}</div>" + T.chips((f"Ch {sh['chapter']} / Ex {sh['example']}", "mono"),
                   *sh["apps"][:3], data.calc_level(sh["id"]), *(("Teacher note", "warn"),) * bool(sh["notes"]))
                   + f"<div class='rowdesc'>{' · '.join(f'{c} {T.esc(data.sub_title(c))[:40]}' for c in sh['subtopics'])}</div>", unsafe_allow_html=True)
        with b:
            nav.link("Open", key=f"{key}_{sh['id']}", width="stretch", s=S, p="sheet", sh=sh["id"])


def calc_page(topic_n: int | None = None, embedded: bool = False) -> None:
    cdata = data.calculator()
    if not embedded:
        T.crumbs("Subjects", NAME, "Calculator")
        T.header("Calculator mastery", kicker=f"{NAME} · {cdata.get('calculator', 'GDC')}", dot=DOT,
                 sub="Every procedure from your Oxford fx-CG50 sheets, with the original key presses and the real calculator screens.")
    if not cdata:
        st.error("The calculator sheets haven't been extracted. Run `python -m ingest.maths_calculator`.")
        return
    browse, drill, reading = st.tabs(["Procedures", "Practice: choose the procedure", "Practice: read the result"])
    with browse:
        f1, f2, f3, f4 = st.columns(4)
        tp = topic_n if topic_n else f1.selectbox("Syllabus topic", ["All"] + [t["n"] for t in data.topics()], key="cc_topic",
                                                   format_func=lambda n: n if n == "All" else data.topic(n)["title"])
        apps = sorted({a for s in data.sheets() for a in s["apps"]})
        app = f2.selectbox("Calculator function", ["All"] + apps, key="cc_app")
        qtypes = sorted({s["question_type"] for s in data.sheets()})
        qt = f3.selectbox("Exam question type", ["All"] + qtypes, key="cc_qt")
        df = f4.selectbox("Difficulty", ["All", "Basic", "Standard", "Hard"], key="cc_level", help="Judged per procedure for this app, not IB data")
        text = st.text_input("Search", key="cc_q", placeholder="e.g. inverse normal, intersect, PMT").lower().strip()
        shown = [s for s in data.sheets() if (tp == "All" or s["topic"] == tp) and (app == "All" or app in s["apps"])
                 and (qt == "All" or s["question_type"] == qt) and (df == "All" or data.calc_level(s["id"]) == df)
                 and (not text or text in (s["title"] + " " + s["text"]).lower())]
        st.caption(f"{len(shown)} of {len(data.sheets())} sheets")
        for t in data.topics():
            mine = [s for s in shown if s["topic"] == t["n"]]
            if mine:
                st.markdown(f"<div class='kicker' style='margin-top:1rem'>Topic {t['n']} · {T.esc(t['title'])}</div>", unsafe_allow_html=True)
                for sh in mine:
                    sheet_row(sh, "cc")
    with drill:
        procedure_drill()
    with reading:
        output_drill()


def procedure_drill() -> None:
    """A real task from one sheet; pick which procedure solves it. Then the screen it ends on."""
    import random
    sheets = [s for s in data.sheets() if s["problem"].strip()]
    seed = st.session_state.setdefault("drill_seed", int(time.time()))
    rng = random.Random(seed)
    target = rng.choice(sheets)
    others = [s for s in sheets if s["title"] != target["title"] and s["question_type"] != target["question_type"]]
    options = rng.sample(others, 3) + [target]
    rng.shuffle(options)
    st.markdown("Read the task and choose the calculator procedure you would use. (Tasks and procedures are from your Oxford sheets.)")
    with st.container(border=True, key="card_drill"):
        st.markdown(f"<div class='kicker'>Task</div>", unsafe_allow_html=True)
        st.markdown(T.esc(data.guide(target["id"]).get("ask") or target["problem"][:700]).replace("\n", "<br>"), unsafe_allow_html=True)
    pick = st.radio("Procedure", options, key=f"drill_pick_{seed}", index=None, format_func=lambda s: f"{s['title']}  ({', '.join(s['apps'][:2])})")
    if pick is not None:
        right = pick["id"] == target["id"] or pick["title"] == target["title"]
        if not st.session_state.get(f"drill_logged_{seed}"):
            progress.log({"kind": "calc", "sheet": target["id"], "subtopic": target["subtopics"][0] if target["subtopics"] else None,
                          "correct": right, "mode": "pick"})
            st.session_state[f"drill_logged_{seed}"] = True
        (st.success if right else st.error)(("Right. " if right else f"Not quite: the sheet is “{target['title']}”. ")
                                            + f"Calculator functions used: {', '.join(target['apps']) or 'see the sheet'}.")
        last = [x for x in target["steps"] if x.get("screen")]
        if last:
            st.image(str(data.screen_path(last[-1]["screen"]["file"])), caption="The screen this procedure ends on", width=360)
        a, b = st.columns(2)
        with a:
            nav.link("Open the procedure", key="drill_open", s=S, p="sheet", sh=target["id"])
        if b.button("Next task", type="primary", key="drill_next"):
            st.session_state["drill_seed"] = seed + 1
            st.rerun()


def output_drill() -> None:
    """A real result from one sheet: pick what it means. Interpreting output, not pressing keys."""
    import random
    sheets = [s for s in data.sheets() if data.guide(s["id"]).get("trap") and any(x.get("screen") for x in s["steps"])]
    seed = st.session_state.setdefault("read_seed", int(time.time()))
    rng = random.Random(seed)
    target = rng.choice(sheets)
    g = data.guide(target["id"])
    options = [g["read"], *g["trap"]]
    rng.shuffle(options)
    st.markdown("Look at where the procedure ends and choose the correct reading of the result.")
    with st.container(border=True, key="card_read"):
        st.markdown("<div class='kicker'>Task</div>", unsafe_allow_html=True)
        st.markdown(T.esc(g["ask"]), unsafe_allow_html=True)
        last = [x for x in target["steps"] if x.get("screen")][-1]
        st.image(str(data.screen_path(last["screen"]["file"])), caption="The last screen of this procedure in your Oxford sheet", width=360)
    pick = st.radio("What does it tell you?", options, key=f"read_pick_{seed}", index=None)
    if pick is not None:
        right = pick == g["read"]
        if not st.session_state.get(f"read_logged_{seed}"):
            progress.log({"kind": "calc", "sheet": target["id"], "subtopic": target["subtopics"][0] if target["subtopics"] else None, "correct": right, "mode": "read"})
            st.session_state[f"read_logged_{seed}"] = True
        (st.success if right else st.error)(("Right. " if right else "Not quite. ") + g["read"])
        st.caption(f"Check every time: {g['check']}")
        a, b = st.columns(2)
        with a:
            nav.link("Open the procedure", key="read_open", s=S, p="sheet", sh=target["id"])
        if b.button("Next result", type="primary", key="read_next"):
            st.session_state["read_seed"] = seed + 1
            st.rerun()


def sheet_page(sid: str) -> None:
    sh = data.sheet(sid)
    if not sh:
        st.error("Unknown calculator sheet.")
        return
    T.crumbs("Subjects", NAME, "Calculator", sh["title"][:40])
    back("Calculator", "bk_cc", s=S, p="calc")
    T.header(sh["title"], kicker=f"Casio fx-CG50 · Oxford Ch {sh['chapter']} / Example {sh['example']}", dot=DOT)
    st.markdown(T.chips(*sh["apps"], sh["question_type"], data.calc_level(sid), f"{sh['screens']} screens")
                , unsafe_allow_html=True)
    sub_links(sh["subtopics"], f"sh_{sid}", view="calculator")
    for n in sh["notes"]:
        st.warning(f"Teacher note: {n}")
    g = data.guide(sid)
    with st.container(border=True, key=f"card_guide_{sid.replace('-', '_')}"):
        st.markdown("<div class='kicker'>About this procedure · notes written for this app; the key presses below are only from your sheets</div>", unsafe_allow_html=True)
        for label, field in (("What it does", "what"), ("When to use it in an exam", "when"), ("What you need to enter", "in"),
                             ("How to read the result", "read"), ("Common mistakes and settings to check", "check")):
            st.markdown(f"**{label}:** {T.esc(g.get(field, ''))}", unsafe_allow_html=True)
    number = re.match(r"\d+", str(sh["example"]))
    example = data.book_example(sh["chapter"], int(number.group(0))) if number else None
    if example:
        with st.expander(f"The same example in your textbook (chapter {sh['chapter']}, example {number.group(0)})", icon=":material/menu_book:"):
            st.markdown(T.chips(TEXTBOOK, ("Worked example", "mono"), f"Section {example['section']}"), unsafe_allow_html=True)
            show_image("book", example["spans"])
    practice = st.toggle("Practice mode: predict each screen before revealing it", key=f"pm_{sid}")
    steps = sh["steps"]
    if not practice:
        for i, stp in enumerate(steps):
            show_image("calc", [[stp["page"], stp["top"], stp["bottom"]]])
    else:
        i = st.session_state.get(f"pmi_{sid}", 0)
        i = min(i, len(steps) - 1)
        stp = steps[i]
        st.progress((i + 1) / len(steps), text=f"Step {i + 1} of {len(steps)}")
        a, b = st.columns([0.6, 0.4])
        with a:
            show_image("calc", [[stp["page"], stp["top"], stp["bottom"]]], ) if not stp.get("screen") else \
                st.image(str(pdf.crop("calc", [[stp["page"], stp["top"], stp["bottom"]]], x0=60, x1=372)), width="stretch")
        with b:
            if stp.get("screen"):
                if st.session_state.get(f"pms_{sid}_{i}"):
                    st.image(str(data.screen_path(stp["screen"]["file"])), width="stretch")
                elif st.button("Reveal the screen", key=f"pmr_{sid}_{i}", type="primary"):
                    st.session_state[f"pms_{sid}_{i}"] = True
                    st.rerun()
        c1, c2 = st.columns(2)
        if c1.button("Previous step", key=f"pmp_{sid}", disabled=i == 0, width="stretch"):
            st.session_state[f"pmi_{sid}"] = i - 1
            st.rerun()
        if c2.button("Next step" if i + 1 < len(steps) else "Done", key=f"pmn_{sid}", type="primary", width="stretch"):
            if i + 1 < len(steps):
                st.session_state[f"pmi_{sid}"] = i + 1
            else:
                progress.log({"kind": "calc", "sheet": sid, "subtopic": sh["subtopics"][0] if sh["subtopics"] else None, "correct": True, "mode": "steps"})
                st.session_state[f"pmi_{sid}"] = 0
                st.toast("Procedure practised")
            st.rerun()
    screens = [s for s in steps if s.get("screen")]
    if screens:
        with st.expander(f"All {len(screens)} calculator screens"):
            cols = st.columns(4)
            for j, s_ in enumerate(screens):
                cols[j % 4].image(str(data.screen_path(s_["screen"]["file"])), caption=f"Screen {j + 1}", width="stretch")
    related = [q for c in sh["subtopics"][:1] for q in data.questions_for(c, primary_only=True) if q["has_markscheme"]][:5]
    if related:
        st.markdown('<div class="h2" style="font-size:1.6rem">Past-paper questions to use it on</div>', unsafe_allow_html=True)
        question_list(related, ctx=sh["title"][:40], key=f"shq_{sid}", page_size=5)


# =========================================================================== error log
def errors_page(topic_n: int | None = None, embedded: bool = False) -> None:
    if not embedded:
        T.crumbs("Subjects", NAME, "Error log")
        T.header("Error log", kicker=NAME, dot=DOT, sub="Every part that lost marks, with what kind of mistake it was. It drives your retries and what comes back.")
    errs = [e for e in progress.error_log(rows()) if topic_n is None or e["topic"] == topic_n]
    retries = [k for k in progress.due_retries(rows(), today()) if topic_n is None or (data.question(k[0]) or {}).get("topic") == topic_n]
    if retries:
        with st.container(border=True, key="card_retry"):
            a, b = st.columns([0.7, 0.3], vertical_alignment="center")
            a.markdown(f"**{len(retries)}** question parts are due for a retry today.")
            if b.button("Retry them", type="primary", key="err_retry", width="stretch"):
                ids = list(dict.fromkeys(k[0] for k in retries))
                st.session_state["q_list"] = {"ids": ids, "label": "Retries due", "back": {"s": S, "p": "errors"}, "review": True}
                for qid in ids:
                    reset("main", data.question(qid))
                nav.go(s=S, p="q", q=ids[0])
    if not errs:
        T.empty("No errors logged", "Mark a question with lost marks and it appears here, with its mistake type and the concept to revisit.")
        return
    counts = progress.mistake_counts(errs, open_only=True)
    st.markdown('<div class="h2" style="font-size:1.6rem">Open mistakes by type</div>', unsafe_allow_html=True)
    if any(counts.values()):
        import pandas as pd
        st.bar_chart(pd.Series(counts, name="open mistakes").rename_axis("type"), horizontal=True, height=260, color="#D1435B")
    else:
        st.caption("All resolved.")
    if progress.mistake_focus(rows(), topic_n):
        with st.container(border=True, key=f"card_focus_{topic_n or 'all'}"):
            st.markdown("<div class='kicker'>What to do about them</div>", unsafe_allow_html=True)
            mistake_focus_panel(f"el_focus_{topic_n or 'all'}", topic_n)
    f1, f2, f3 = st.columns(3)
    show = f1.selectbox("Show", ["Open", "Resolved", "All"], key="el_show")
    mt = f2.selectbox("Mistake type", ["All"] + progress.MISTAKES, key="el_type")
    tp = topic_n if topic_n else f3.selectbox("Topic", ["All"] + [t["n"] for t in data.topics()], key="el_topic", format_func=lambda n: n if n == "All" else data.topic(n)["title"])
    notes = progress.load_notes()
    shown = [e for e in errs if (show == "All" or (show == "Open") != e["resolved"]) and (mt == "All" or e.get("mistake") == mt)
             and (tp == "All" or e["topic"] == tp)]
    st.caption(f"{len(shown)} entries")
    for e in shown[:60]:
        q = data.question(e["qid"])
        part = next((p for p in q["parts"] if p["label"] == e["part"]), None) if q else None
        title = f"{e['day']} · {e['qid']} ({e['part']}) · {e['awarded']}/{e['marks']} · {e.get('mistake') or 'no type'}" + (" · fixed" if e["fixed"] else "")
        with st.expander(title):
            st.markdown(T.chips(PAST_PAPER, data.topic(e["topic"])["title"], f"{e['subtopic']} {data.sub_title(e['subtopic'])[:40]}",
                                (f"Revisit {e['concept']}", "acc"), e["mode"], *(("with hints", "warn"),) * bool(e.get("helped"))), unsafe_allow_html=True)
            if e.get("answer"):
                st.markdown(f"**Your answer:** {T.esc(e['answer'])}", unsafe_allow_html=True)
            if e.get("note"):
                st.markdown(f"**Note at the time:** {T.esc(e['note'])}", unsafe_allow_html=True)
            if q and part:
                a, b = st.columns(2)
                with a:
                    st.markdown("<div class='mshead'>Question</div>", unsafe_allow_html=True)
                    show_image(q["doc"], part["q_spans"] or q["q_spans"])
                with b:
                    st.markdown("<div class='mshead'>Correct answer and method</div>", unsafe_allow_html=True)
                    if part["ms_spans"]:
                        show_image(q["doc"], part["ms_spans"])
                    else:
                        st.caption("No markscheme in your files for this paper.")
            n = notes.get(e["id"], {})
            new_note = st.text_input("My note", value=n.get("note", ""), key=f"eln_{e['id']}", placeholder="What will you do differently?")
            res = st.checkbox("Resolved", value=e["resolved"], key=f"elr_{e['id']}", disabled=e["fixed"], help="Ticked automatically once you get it right without help")
            c1, c2 = st.columns(2)
            if (new_note != n.get("note", "") or res != bool(n.get("resolved"))) and not e["fixed"]:
                notes[e["id"]] = {"note": new_note, "resolved": res}
                progress.save_notes(notes)
            with c1:
                if st.button("Retry this question", key=f"elq_{e['id']}"):
                    st.session_state["q_list"] = {"ids": [e["qid"]], "label": "Error log", "back": {"s": S, "p": "errors"}, "review": True}
                    reset("main", q)
                    nav.go(s=S, p="q", q=e["qid"])
            with c2:
                nav.link(f"Revise {e['concept']}", key=f"elc_{e['id']}", s=S, p="sub", c=e["concept"])


# =========================================================================== calendar


def session_page(sid: str) -> None:
    cal = schedule.ensure()
    s = next((x for x in cal["sessions"] if x["id"] == sid), None)
    if not s:
        st.error("This session no longer exists.")
        return
    now = schedule.now_local()
    T.crumbs("Calendar", f"{date.fromisoformat(s['date']):%a %d %b}", s["title"][:40])
    back(f"Calendar · {date.fromisoformat(s['date']):%A %d %B}", "bk_cal", p="calendar", m=s["date"][:7], d=s["date"])
    T.header(s["title"], kicker=f"{date.fromisoformat(s['date']):%A %d %b} · {s['start']}–{schedule.end_of(s):%H:%M} · {s['minutes']} min", dot=DOT, sub=T.esc(s["objective"]))
    status = schedule.status(s, now)
    st.markdown(T.chips(status.capitalize(), s["kind"]), unsafe_allow_html=True)
    if s["kind"] == "mixed":
        st.markdown("Run a mixed set: the topic of each question stays hidden until you have marked it.")
        nav.link("Go to mixed practice", key="ss_mx", kind="primary", s=S, p="mixed")
    elif s["kind"] == "exam":
        st.markdown("Build a full Paper 1 style practice paper and start the clock.")
        nav.link("Go to practice exams", key="ss_ex", kind="primary", s=S, p="exams")
    elif s["kind"] == "review":
        nav.link("Open the error log", key="ss_er", kind="primary", s=S, p="errors")
    if s["subtopics"]:
        st.markdown('<div class="h2" style="font-size:1.6rem">1 · Recall and revise these sub-topics</div>', unsafe_allow_html=True)
        lv = levels()
        cols = st.columns(3)
        for i, c in enumerate(s["subtopics"]):
            with cols[i % 3]:
                with st.container(border=True, key=f"card_ssub_{sid}_{c.replace('.', '_')}"):
                    st.markdown(f"**{c}** {T.esc(data.sub_title(c))}<br>{T.level_tag(lv[c]['level'])}", unsafe_allow_html=True)
                    nav.link("Study", key=f"ss_sub_{c}", width="stretch", s=S, p="sub", c=c)
    if s["calculator"]:
        st.markdown('<div class="h2" style="font-size:1.6rem">2 · Calculator practice</div>', unsafe_allow_html=True)
        for shid in s["calculator"]:
            sh = data.sheet(shid)
            if sh:
                sheet_row(sh, f"ss_{sid}")
    if s["questions"]:
        st.markdown('<div class="h2" style="font-size:1.6rem">3 · Past-paper questions</div>', unsafe_allow_html=True)
        qs = [data.question(q) for q in s["questions"] if data.question(q)]
        question_list(qs, ctx=s["title"][:40], key=f"ssq_{sid}", page_size=6)
    sections = list({x["code"]: x for c in s["subtopics"] for x in data.book_sections(c)}.values())
    if sections:
        st.markdown('<div class="h2" style="font-size:1.6rem">Textbook for this session</div>', unsafe_allow_html=True)
        section_rows(sections[:6], f"ss_{sid}")
    T.rule()
    if st.button("Mark session complete" if not s["done"] else "Completed ✓", key="ss_done", type="primary", disabled=s["done"]):
        schedule.update(cal, sid, done=True)
        schedule.save(cal)
        st.rerun()


# =========================================================================== analytics
def analytics_page(topic_n: int | None = None, embedded: bool = False) -> None:
    if not embedded:
        T.crumbs("Subjects", NAME, "Analytics")
        T.header("Performance analytics", kicker=NAME, dot=DOT, sub="Where you stand across the syllabus, and what kind of mistakes cost you marks.")
    rs, lv = rows(), levels()
    ps = [r for r in progress.parts(rs) if topic_n is None or r["topic"] == topic_n]
    st.markdown('<div class="h2" style="font-size:1.6rem">Syllabus map</div>', unsafe_allow_html=True)
    st.markdown(" ".join(T.level_tag(l) for l in progress.LEVELS), unsafe_allow_html=True)
    for t in [x for x in data.topics() if topic_n is None or x["n"] == topic_n]:
        cells = "".join(f'<a class="cell" href="?s={S}&p=sub&c={c}&v=learn" target="_self" style="--lc:{T.LEVEL_COLOURS[lv[c]["level"]]};text-decoration:none" title="{T.esc(data.sub_title(c))}: {lv[c]["level"]}">{c}<small>{lv[c]["level"]}</small></a>'
                        for c in t["subtopics"])
        st.markdown(f"<div class='kicker'>{t['n']} · {T.esc(t['title'])} · {100 * progress.topic_progress(lv, t['n']):.0f}%</div><div class='grid'>{cells}</div>", unsafe_allow_html=True)
    if not ps:
        T.empty("No marked questions yet", "Charts appear once you have marked some past-paper parts.")
        return
    import pandas as pd
    df = pd.DataFrame(ps)
    df["topic_name"] = df["topic"].map(lambda n: data.topic(n)["title"])
    a, b = st.columns(2)
    with a:
        st.markdown("**Mark rate by topic**")
        g = df.groupby("topic_name")[["awarded", "marks"]].sum()
        st.bar_chart((100 * g["awarded"] / g["marks"]).rename("% of marks"), height=240)
    with b:
        st.markdown("**Mistakes by type (all time)**")
        m = df[df["mistake"].notna()]["mistake"].value_counts()
        if len(m):
            st.bar_chart(m, horizontal=True, height=240)
        else:
            st.caption("No mistakes logged.")
    c, d = st.columns(2)
    with c:
        st.markdown("**Marks attempted per day**")
        st.bar_chart(df.groupby("day")["marks"].sum(), height=220)
    with d:
        st.markdown("**Mark rate by mode**")
        g2 = df.groupby("mode")[["awarded", "marks"]].sum()
        st.bar_chart((100 * g2["awarded"] / g2["marks"]).rename("% of marks"), height=220)
    st.caption("Mixed and exam modes test unfamiliar recognition; a gap between practice and mixed rates shows what still depends on knowing the topic in advance.")
    rec = [r for r in rs if r.get("kind") == "recall" and (topic_n is None or data.topic_of(r["subtopic"]) == topic_n)]
    if rec:
        good = sum(1 for r in rec if progress.GRADES.get(r["grade"], 0) >= 2)
        st.markdown(f"**Recall:** {len(rec)} reviews, {100 * good / len(rec):.0f}% recalled well.")
    worst = sorted(((c, l["stats"]["rate"]) for c, l in lv.items() if (topic_n is None or data.topic_of(c) == topic_n) and l["stats"]["parts"] >= 2 and l["stats"]["rate"] is not None), key=lambda x: x[1])[:6]
    if worst:
        st.markdown("**Weakest sub-topics (recent mark rate):** " + " · ".join(f"{c} {100 * r:.0f}%" for c, r in worst))
        sub_links([c for c, _ in worst], f"an_weak_{topic_n}", view="questions")


# =========================================================================== router
def render(r: dict) -> None:
    if missing_data():
        return
    p = r.get("p", "overview")
    v = r.get("v")
    pages = {"recall": recall_page, "search": search_page, "mixed": mixed_page, "exams": exams_page, "past": past_page,
             "calc": calc_page, "errors": errors_page, "links": links_page}
    if p in pages:
        pages[p]()
    elif p == "book":
        book_page(r.get("bs", "1.1"), r.get("bx"))
    elif p == "calendar":                 # the Calendar is now one page for every subject (main menu)
        from ibtee import planner
        planner.page(v or "month", r.get("m"), r.get("d"))
    elif p in ("overview", "topics"):
        overview(v or "today")
    elif p == "analytics":
        overview("progress")
    elif p == "qb":
        overview("questions")
    elif p == "topic":
        topic_page(int(r.get("t", 1)), v or "subtopics")
    elif p == "qbt":                      # older links: a topic's questions
        topic_page(int(r.get("t", 1)), "questions")
    elif p == "sub":
        subtopic_page(r.get("c", "1.1"), v or "recall")
    elif p == "qbs":                      # older links: a sub-topic's questions
        subtopic_page(r.get("c", "1.1"), "questions")
    elif p == "q":
        question_page(r.get("q", ""))
    elif p == "exam":
        exam_page(r.get("ex", ""))
    elif p == "pastset":
        pastset_page(r.get("sess", ""), r.get("pp", "1"))
    elif p == "sheet":
        sheet_page(r.get("sh", ""))
    elif p == "session":
        session_page(r.get("ss", ""))
    else:
        overview()
