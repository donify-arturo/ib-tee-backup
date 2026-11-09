"""
The Maths question card and the recall card: the two places the student actually answers.

Question card flow (the app never shows the answer first):
    1. the question as printed (a crop of the original PDF), with space for your answer
    2. optional hints: first a nudge, then the first method line of the markscheme (a hinted attempt is not "unaided")
    3. Show markscheme: each part's markscheme (and the examiners report, when the file has one)
    4. mark yourself part by part; for any lost mark say what kind of mistake it was, which feeds the error log and revision
Modes: practice (topic shown), mixed (topic hidden until marked), review (a retry from the error log), exam (no hints, marked later).
"""
from __future__ import annotations

import re

import streamlit as st

from ibtee import store
from ibtee import theme as T
from maths import data, progress, render

SUBJECT = "maths_ai_hl"
PAST_PAPER = ("Past paper", "acc")          # every question says where it comes from
TEXTBOOK = ("Textbook", "warn")


def show_image(doc: str, regions: list, caption: str | None = None) -> None:
    path = render.crop(doc, regions)
    if path:
        st.image(str(path), width="stretch", caption=caption)
    else:
        st.warning("The original PDF for this piece is missing from `documents to process/MATHS`.")


def first_method_line(ms_text: str) -> str | None:
    """The first line of a markscheme that earns a method mark: the approach, without the final answer."""
    for line in ms_text.splitlines():
        if re.search(r"\(?M1\)?|\(M\d\)", line):
            hint = re.sub(r"\s*\(?[MA]\d\)?(\(?[AMR]\d\)?)*\s*$", "", line).strip()
            if len(hint) > 6:
                return hint
    return None


def labels_for(q: dict, hidden: bool) -> str:
    if hidden:
        return T.chips(PAST_PAPER, (q["id"], "mono"), f"{q['max_marks']} marks", f"Paper {q['paper']}", ("Topic hidden", "acc"))
    diff = data.difficulty(q)
    kind = {"Basic": "ok", "Standard": "warn", "Hard HL": "bad", "Multi-step": "bad"}[diff]
    bits = [PAST_PAPER, (q["id"], "mono"), f"{q['max_marks']} marks", (diff, kind), f"Paper {q['paper']}", q["session"], "Calculator"]
    if not q["has_markscheme"]:
        bits.append(("No markscheme in your files", "bad"))
    return T.chips(*bits)


def bookmark_button(q: dict, key: str) -> None:
    marked = store.is_bookmarked(SUBJECT, q["id"])
    if st.button("Saved" if marked else "Save", key=key, icon=":material/bookmark:" if marked else ":material/bookmark_border:"):
        store.toggle_bookmark(SUBJECT, q["id"], q["id"], f"Past paper · {data.difficulty(q)} · {q['max_marks']} marks")
        st.rerun()


def question_card(q: dict, mode: str = "practice", key: str = "", session: str | None = None, on_done=None) -> dict | None:
    """Draw a question with its whole attempt → hint → markscheme → marking flow. Returns the logged rows once marked."""
    k = f"{key}_{q['id']}"
    state = st.session_state.setdefault(f"qs_{k}", {"revealed": False, "hints": 0, "marked": None})
    if mode == "exam_mark":          # marking a finished practice paper: the markscheme is open and hints no longer make sense
        state["revealed"] = True
    hidden = mode == "mixed" and not state["marked"]

    top = st.columns([0.8, 0.2], vertical_alignment="center")
    top[0].markdown(labels_for(q, hidden), unsafe_allow_html=True)
    with top[1]:
        with st.container(horizontal=True, horizontal_alignment="right"):
            bookmark_button(q, f"bm_{k}")

    with st.container(border=True, key=f"card_q_{k}"):
        show_image(q["doc"], q["q_spans"])
        if q.get("also_in"):
            st.caption("Also in: " + ", ".join(q["also_in"]))

    if mode == "exam":
        return None

    if not state["revealed"]:
        st.text_area("Your answer / working (optional)", key=f"ans_{k}", height=90,
                     placeholder="Work it through on paper first. Key results here help you compare with the markscheme and are kept in your error log.")
        with st.container(border=True, key=f"card_act_{k}"):
            cols = st.columns([0.55, 0.45], vertical_alignment="center")
            cols[0].markdown("<span class='muted'>Work it through on paper first, then check.</span>", unsafe_allow_html=True)
            with cols[1]:
                with st.container(horizontal=True, horizontal_alignment="right"):
                    if mode != "exam" and state["hints"] < 2 and q["has_markscheme"]:
                        if st.button("Hint" if state["hints"] == 0 else "Another hint", key=f"hint_{k}", icon=":material/lightbulb:",
                                     help="A hinted attempt still counts, but not as 'without help' for mastery"):
                            state["hints"] += 1
                            st.rerun()
                    if st.button("Show markscheme", key=f"rev_{k}", type="primary", shortcut="Space" if key.startswith("main") else None):
                        state["revealed"] = True
                        st.rerun()
        if state["hints"]:
            hint_box(q, state["hints"], hidden)
        return None

    # ---- revealed: markscheme per part, then marking
    if state["hints"]:
        hint_box(q, state["hints"], hidden)
    st.markdown('<div class="mshead">Markscheme</div>', unsafe_allow_html=True)
    if not q["has_markscheme"]:
        st.warning("This paper's markscheme file in your folder is a copy of the question paper (HL Geometry & Trigonometry Paper 2), "
                   "so there is no markscheme to show. Mark it against a teacher's or the official markscheme; your marks are self-assessed.")
    for p in q["parts"]:
        label = f"({p['label']})" if p["label"] else "Answer"
        with st.container(border=True, key=f"card_ms_{k}_{p['label']}"):
            st.markdown(f"**{label}** <span class='muted'>· {p['marks'] or '?'} marks"
                        + ("" if hidden else f" · {data.part_subtopic(q, p['label'])} {T.esc(data.sub_title(data.part_subtopic(q, p['label'])))}")
                        + "</span>", unsafe_allow_html=True)
            if p["ms_spans"]:
                show_image(q["doc"], p["ms_spans"])
            if p["report_spans"]:
                with st.expander("Examiners report"):
                    show_image(q["doc"], p["report_spans"])

    if state["marked"]:
        marked_summary(q, state["marked"], mode)
        return state["marked"]
    return marking_form(q, mode, k, state, session, on_done)


def hint_box(q: dict, level: int, hidden: bool) -> None:
    sub = q["subtopics"][0] if q["subtopics"] else None
    if hidden:
        first = "What is the question asking you to find, and what would give it? Name the method (or GDC app) before you calculate."
    else:
        sheets = data.sheets_for(sub) if sub else []
        first = f"This is mainly **{sub} {T.esc(data.sub_title(sub))}**." + (
            f" A calculator sheet that helps: *{T.esc(sheets[0]['title'])}* (Ch {sheets[0]['chapter']} Ex {sheets[0]['example']})." if sheets else "")
    st.markdown(f"<div class='note'><b>Hint 1.</b> {first}</div>", unsafe_allow_html=True)
    if level >= 2:
        line = next((first_method_line(p["ms_text"]) for p in q["parts"] if first_method_line(p["ms_text"])), None)
        st.markdown(f"<div class='note'><b>Hint 2 (from the markscheme's first method mark).</b> {T.esc(line) if line else 'No method line found in the markscheme.'}</div>",
                    unsafe_allow_html=True)


def marking_form(q: dict, mode: str, k: str, state: dict, session: str | None, on_done) -> dict | None:
    st.markdown('<div class="h2">How did you do?</div>', unsafe_allow_html=True)
    st.caption("Award yourself marks part by part, as the markscheme would. For any part that lost marks, say what went wrong: "
               "it goes to your error log and decides what comes back for revision.")
    codes = [s["code"] for s in data.subtopics()]
    with st.form(f"mark_{k}", border=True):
        values = {}
        for p in q["parts"]:
            label = f"({p['label']})" if p["label"] else "Whole question"
            marks = int(p["marks"] or 1)
            c1, c2, c3 = st.columns([0.24, 0.42, 0.34])
            got = c1.number_input(f"{label} marks out of {marks}", min_value=0, max_value=marks, value=marks, step=1, key=f"mk_{k}_{p['label']}")
            mistake = c2.selectbox("If marks were lost: type of mistake", ["—"] + progress.MISTAKES, key=f"mt_{k}_{p['label']}")
            default = data.part_subtopic(q, p["label"])
            concept = c3.selectbox("Concept to revisit", codes, index=codes.index(default) if default in codes else 0, key=f"cn_{k}_{p['label']}",
                                   format_func=lambda c: f"{c} {data.sub_title(c)[:38]}")
            values[p["label"]] = (got, mistake, concept)
        note = st.text_input("Note for your error log (optional)", key=f"nt_{k}", placeholder="e.g. used n instead of n − 1")
        a, b = st.columns(2)
        all_right = a.form_submit_button("Got it all", type="primary", width="stretch")
        save = b.form_submit_button("Save my marks", width="stretch")
    if not (all_right or save):
        return None
    missing = [lab for lab, (got, mistake, _c) in values.items()
               if not all_right and got < int(next(p for p in q["parts"] if p["label"] == lab)["marks"] or 1) and mistake == "—"]
    if missing:
        st.error("Choose the type of mistake for: " + ", ".join(f"({m})" if m else "the question" for m in missing))
        return None
    answer = st.session_state.get(f"ans_{k}", "")
    rows = []
    for p in q["parts"]:
        got, mistake, concept = values[p["label"]]
        if all_right:
            got, mistake = int(p["marks"] or 1), "—"
        rows.append(progress.log_part(q, p, got, "exam" if mode == "exam_mark" else mode, answer=answer, mistake=None if mistake == "—" else mistake, concept=concept,
                                      note=note, helped=state["hints"] > 0, session=session))
    state["marked"] = rows
    if on_done:
        on_done(rows)
    st.rerun()


def marked_summary(q: dict, rows: list[dict], mode: str) -> None:
    got, total = sum(r["awarded"] for r in rows), sum(r["marks"] for r in rows)
    kind = "ok" if got == total else "warn" if got else "bad"
    st.markdown(T.chips((f"{got} / {total} marks", kind), *(f"({r['part']}) {r['mistake']}" for r in rows if r.get("mistake"))), unsafe_allow_html=True)
    if mode == "mixed":
        tags = list(dict.fromkeys(q["subtopics"]))
        st.markdown("<div class='note'><b>This question tested:</b> " + "; ".join(f"{c} {T.esc(data.sub_title(c))}" for c in tags) + "</div>",
                    unsafe_allow_html=True)
        from ibtee import nav
        cols = st.columns(min(3, len(tags)) or 1)
        for i, c in enumerate(tags):
            with cols[i % len(cols)]:
                nav.link(f"Revise {c}", key=f"mxrev_{q['id']}_{c}", width="stretch", s=SUBJECT, p="sub", c=c, v="learn")
    if got < total:
        st.caption("Saved to your error log. The parts you lost come back for a retry tomorrow.")


def reset(key: str, q: dict) -> None:
    st.session_state.pop(f"qs_{key}_{q['id']}", None)


# --------------------------------------------------------------------------- recall cards
def recall_card(card: dict, key: str, show_topic: bool = True) -> str | None:
    """Prompt → think → show answer → rate. Returns the grade once given."""
    st_key = f"rc_{key}_{card['id']}"
    shown = st.session_state.get(st_key)
    with st.container(border=True, key=f"card_rc_{key}_{card['id'].replace('#', '_').replace('.', '_')}"):
        if show_topic:
            st.markdown(f"<div class='kicker'>{card['subtopic']} · {T.esc(data.sub_title(card['subtopic']))}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='h2' style='font-size:1.6rem'>{T.esc(card['q'])}</div>", unsafe_allow_html=True)
        if not shown:
            st.text_input("Your answer (say it or write it before you look)", key=f"rin_{st_key}")
            if st.button("Show answer", key=f"rshow_{st_key}", type="primary"):
                st.session_state[st_key] = True
                st.rerun()
            return None
        st.markdown(f"<div class='note'>{T.esc(card['a'])}</div>", unsafe_allow_html=True)
        st.caption("How well did you recall it?")
        cols = st.columns(4)
        for col, (grade, label, help_) in zip(cols, [("again", "Again", "Didn't know it: back tomorrow"), ("hard", "Hard", "Got it with effort"),
                                                     ("good", "Good", "Recalled it correctly"), ("easy", "Easy", "Instantly, no doubt")]):
            if col.button(label, key=f"r{grade}_{st_key}", width="stretch", help=help_, type="primary" if grade == "good" else "secondary"):
                progress.log({"kind": "recall", "card": card["id"], "subtopic": card["subtopic"], "grade": grade,
                              "typed": st.session_state.get(f"rin_{st_key}", "")})
                st.session_state.pop(st_key, None)
                return grade
    return None
