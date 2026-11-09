"""
The Study guide page: the student's two books, one syllabus understanding at a time.

    Learn            explanation, key points, formulas, exam tips, mistakes   (data/guide, engine.guide_builder;
                                                                              falls back to the short notes in data/reference)
    Book pages       the real pages, rendered from the PDFs                    (book_view)
    Worked examples  step by step                                              (data/foundations)
    Try it           the books' own questions, then the ones they reprinted from IB papers
    Past papers      the Questionbank cards that practise this understanding   (data/techniques)

Exam practice and Mastered stay in the Questionbank: nothing here is scored.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import streamlit as st

import book_view
import reference
from engine import foundations_builder, guide_builder

BOOK_NAMES = foundations_builder.BOOKS
SYLLABUS = Path(__file__).resolve().parent / "data" / "syllabus" / "syllabus.json"


def _syllabus() -> dict:
    return json.loads(SYLLABUS.read_text(encoding="utf-8"))


def _book(item: dict) -> str:
    return BOOK_NAMES.get(item.get("source", "companion"), "IB guide")


def _book_question(title: str, q: dict) -> None:
    with st.container(border=True):
        st.caption(f"{title} · {_book(q)} p{q['page']}")
        st.markdown(html.escape(q["question"]), unsafe_allow_html=True)
        for opt in q.get("options") or []:
            st.markdown(f"- {html.escape(opt)}", unsafe_allow_html=True)
        with st.expander("Check my answer"):
            st.markdown(f"**{html.escape(q['answer'])}**", unsafe_allow_html=True)
            for n, step in enumerate(q.get("steps") or [], 1):
                st.markdown(f"{n}. {html.escape(step)}", unsafe_allow_html=True)
            if q.get("answer_from") == "claude":
                st.caption("The book's answers don't cover this one, so this answer was worked out by Claude.")


def _worked(examples: list[dict], key_base: str) -> None:
    if not examples:
        st.info("The books have no worked example for this point.")
        return
    hints = st.toggle("Show hints", value=True, key=f"{key_base}_hints")
    for i, ex in enumerate(examples, 1):
        key = f"{key_base}_{i}"
        shown = st.session_state.get(key, 0)
        with st.container(border=True):
            also = f" · from past paper {ex['past_paper_ref']}" if ex.get("past_paper_ref") else ""
            st.caption(f"Textbook · Worked example {i} · {_book(ex)} p{ex['page']}{also}")
            st.markdown(f"**{html.escape(ex['title'])}**  \n{html.escape(ex['problem'])}", unsafe_allow_html=True)
            for n, step in enumerate(ex["steps"], 1):
                if n <= shown:
                    st.markdown(f"{n}. {html.escape(step['work'])}", unsafe_allow_html=True)
                elif n == shown + 1:
                    if hints:
                        st.markdown(f"{n}. *{html.escape(step['hint'])}*", unsafe_allow_html=True)
                    break
            a, b = st.columns(2)
            if shown < len(ex["steps"]) and a.button("Reveal step", key=f"{key}_next", width="stretch"):
                st.session_state[key] = shown + 1
                st.rerun()
            if shown and b.button("Start again", key=f"{key}_reset", width="stretch"):
                st.session_state[key] = 0
                st.rerun()


def _learn(section: dict | None, notes: list[dict]) -> None:
    if section:
        st.markdown(section["explanation"])
        if section.get("key_points"):
            st.markdown("**Remember**")
            st.markdown("".join(f"- {p}\n" for p in section["key_points"]))
        if section.get("formulas"):
            st.markdown("**Formulas**")
            st.markdown("".join(f"- `{f['formula']}`: {f['meaning']}\n" for f in section["formulas"]))
        if section.get("exam_tips"):
            st.markdown("**Exam tips**")
            st.markdown("".join(f"- {t}\n" for t in section["exam_tips"]))
        if section.get("mistakes"):
            st.markdown("**Watch out**")
            st.markdown("".join(f"- {m}\n" for m in section["mistakes"]))
        return
    if notes:
        st.info("The full explanation for this topic isn't built yet, so here are its short notes. The Book pages tab has the book itself.")
        for group in notes:
            st.markdown(f"**{html.escape(group['heading'])}**", unsafe_allow_html=True)
            st.markdown("".join(f"- {p}\n" for p in group["points"]))
    else:
        st.info("No explanation for this point yet. The Book pages tab has the book itself.")


def _book_pages(pages: dict[str, list[int]], key: str) -> None:
    books = [b for b in ("companion", "prepared") if pages.get(b)]
    if not books:
        st.info("No book pages are linked to this point yet.")
        return
    book = st.radio("Book", books, horizontal=True, key=f"{key}_book", format_func=lambda b: BOOK_NAMES[b],
                    label_visibility="collapsed") if len(books) > 1 else books[0]
    numbers = pages[book]
    number = st.select_slider("Page", numbers, key=f"{key}_{book}_page") if len(numbers) > 1 else numbers[0]
    image = book_view.page_image(book, number)
    if image:
        st.image(str(image), caption=f"{BOOK_NAMES[book]}, page {number}", width="stretch")
    else:
        st.warning(f"Page {number} of {BOOK_NAMES[book]} couldn't be opened. Is the PDF still in `documents to process`?")


def study_guide_page(codes: list[str], titles: dict, load_deck) -> None:
    st.title("Study guide")
    syl = _syllabus()
    guides = {c: guide_builder.load(c) for c in codes}
    def label(c: str) -> str:
        return f"{c} {titles[c]}" + ("" if guides[c] else "  (short notes only)")
    if st.session_state.get("sg_topic") not in codes:            # open on the topic being practised in the Questionbank
        st.session_state["sg_topic"] = st.session_state.get("qb_topic") if st.session_state.get("qb_topic") in codes else codes[0]
    code = st.selectbox("Topic", codes, key="sg_topic", format_func=label)
    guide = guides[code]
    fd = foundations_builder.load(code) or {"practice": [], "worked": [], "investigations": []}
    ref = reference.load_reference(code) or {"notes": []}
    deck = load_deck(code) or {"cards": []}
    understandings = [u for u, info in syl["understandings"].items() if info["sub_topic"] == code]
    sections = {s["understanding"]: s for s in (guide or {}).get("sections", [])}

    if guide and guide.get("overview"):
        st.caption(guide.get("guiding_question", ""))
        st.markdown(guide["overview"])
    options = understandings + (["investigations"] if fd["investigations"] else [])
    names = {u: f"{u} · {sections[u]['title']}" if u in sections else f"{u} · {syl['understandings'][u]['statement'][:60]}"
             for u in understandings}
    names["investigations"] = "Investigations (practical work)"
    if st.session_state.get("sg_section") not in options:
        st.session_state["sg_section"] = options[0]
    a, b, c = st.columns([0.76, 0.12, 0.12], vertical_alignment="bottom")
    i = options.index(st.session_state["sg_section"])
    # The buttons are drawn before the selectbox (columns keep them on the right), so a click can still set its value.
    if b.button("Back", key="sg_prev", width="stretch", disabled=i == 0):
        st.session_state["sg_section"] = options[max(i - 1, 0)]
        st.rerun()                                       # redraw so Back/Next are enabled for the new section
    if c.button("Next", key="sg_next", width="stretch", disabled=i == len(options) - 1):
        st.session_state["sg_section"] = options[min(i + 1, len(options) - 1)]
        st.rerun()
    current = a.selectbox("Section", options, key="sg_section", format_func=names.get)

    if current == "investigations":
        st.caption("Practical and data questions from your books, with the books' answers, then the IB guide's Tool and Inquiry prompts. "
                   "The guide publishes no answers to those, so their model answers are Claude's.")
        for n, item in enumerate(fd["investigations"], 1):
            with st.container(border=True):
                where = f"{_book(item)} p{item['page']}" if item.get("page") else _book(item)
                st.caption(f"{item['tag']} · {where} · {item['understanding']}")
                st.markdown(html.escape(item["prompt"]), unsafe_allow_html=True)
                st.text_area("My reasoning", key=f"sg_inq_{code}_{n}", height=90, label_visibility="collapsed",
                             placeholder="Write your plan here first")
                with st.expander("The book's answer" if item.get("answer_from") == "book" else "Model answer (Claude, not examiners)"):
                    st.markdown("".join(f"- {html.escape(p)}\n" for p in item["model_answer"]), unsafe_allow_html=True)
        return

    info = syl["understandings"][current]
    st.markdown(f"**Syllabus{' (HL)' if info.get('level') == 'HL' else ''}:** {html.escape(info['statement'])}", unsafe_allow_html=True)
    section = sections.get(current)
    here = lambda items: [x for x in items if x.get("understanding") == current]
    worked = here(fd["worked"])
    own = [q for q in here(fd["practice"]) if not q.get("past_paper_ref")]
    reprinted = [q for q in here(fd["practice"]) if q.get("past_paper_ref")]
    cards = [card for card in deck["cards"] if current in (card.get("understandings") or [])]
    pages = {"companion": book_view.merge_pages((section or {}).get("companion_pages"),
                                                [x["page"] for x in worked + own + reprinted if x.get("source") == "companion"]),
             "prepared": book_view.merge_pages((section or {}).get("prepared_pages"),
                                               [x["page"] for x in worked + own + reprinted if x.get("source") == "prepared"])}
    n_pages = len(pages["companion"]) + len(pages["prepared"])
    learn, book_tab, worked_tab, try_tab, past_tab = st.tabs(
        ["Learn", f"Book pages ({n_pages})", f"Worked examples ({len(worked)})", f"Try it ({len(own) + len(reprinted)})",
         f"Past papers ({len(cards)})"])
    with learn:
        _learn(section, [g for g in ref["notes"] if g.get("understanding") == current])
    with book_tab:
        _book_pages(pages, f"sg_pages_{code}_{current}")
    with worked_tab:
        _worked(worked, f"sg_step_{code}_{current}")
    with try_tab:
        if not own and not reprinted:
            st.info("The books have no practice question for this point.")
        for n, q in enumerate(own, 1):
            _book_question(f"Textbook question {n}", q)
        if reprinted:
            st.markdown("**Reprinted from IB past papers**")
            st.caption("The books took these from real exams. The Questionbank has them with markschemes and examiner comments.")
            for q in reprinted:
                _book_question(f"Past paper {q['past_paper_ref']}", q)
    with past_tab:
        if not cards:
            st.info("No Questionbank card practises this point yet." + ("" if deck["cards"] else " This topic's deck isn't built yet."))
        else:
            st.caption("Exam questions on this point are practised in the Questionbank, where they count towards Mastered.")
            for card in cards:
                st.markdown(f"- {html.escape(card['title'])}", unsafe_allow_html=True)
            if st.button("Practise these in the Questionbank", key="sg_to_qb", type="primary"):
                st.session_state["qb_topic"] = code
                st.session_state["page"] = "Questionbank"
                st.rerun()
