"""
IB TEE — personal IB revision platform.

    streamlit run app.py

The shell: page setup, light/dark theme, the left menu (Home · Subjects · Bookmarks · My subjects with each subject's own pages) and
the router. Subjects live in their own modules and share the design system in ibtee/:

    chem_app.py        Chemistry HL (technique decks, Questionbank, Study guide, notes, definitions, booklet, boundaries)
    maths/ui_pages.py  Mathematics AI HL (topics and learning cycle, question bank, mixed, exams, past papers, calculator,
                       error log, revision calendar, analytics)
"""
from __future__ import annotations

import streamlit as st

from ibtee import home, login, nav, onboarding, store, users
from ibtee import theme as T

st.set_page_config(page_title="IB TEE", page_icon=":material/school:", layout="wide", initial_sidebar_state="expanded")

CHEM_NAV = [("Progress", "Overview", ":material/grid_view:"), ("Questionbank", "Question bank", ":material/quiz:"),
            ("Study guide", "Study guide", ":material/menu_book:"), ("Tips & my notes", "Tips & my notes", ":material/edit_note:"),
            ("Key definitions", "Key definitions", ":material/translate:"), ("Data booklet", "Data booklet", ":material/table_chart:"),
            ("Grade boundaries", "Grade boundaries", ":material/grading:"), ("Missing markschemes", "Missing markschemes", ":material/help:"),
            ("Build decks", "Build decks", ":material/build:")]
CHEM_GROUPS = {"Progress": "Study", "Data booklet": "Reference", "Missing markschemes": "Deck building"}   # sub-headings above these entries


def resolve_route() -> dict:
    """The route from the URL, plus the Chemistry app's own ways of moving between its pages (session state, ?topic= tiles)."""
    r = nav.route()
    if st.query_params.get("topic"):                     # a tile on the Chemistry Overview page
        st.session_state["qb_topic"] = st.query_params["topic"]
        st.session_state["page"] = "Questionbank"
        return {"s": "chem_hl", "p": "Questionbank"}
    if not r.get("s") and not r.get("p") and st.session_state.get("page"):      # an older link or a test that only sets the page
        return {"s": "chem_hl", "p": st.session_state["page"]}
    if r.get("s") == "chem_hl":
        url_page = r.get("p")
        if url_page and url_page != st.session_state.get("_chem_url"):
            st.session_state["page"] = url_page                              # the URL changed: follow it
        st.session_state["_chem_url"] = url_page
        page = st.session_state.setdefault("page", "Questionbank")
        if page != url_page:                                                 # the page changed itself (e.g. Study guide → Questionbank)
            st.query_params["s"], st.query_params["p"] = "chem_hl", page
            st.session_state["_chem_url"] = page
        r["p"] = page
    return r


def sidebar(r: dict, prof: dict, user: dict) -> None:
    from maths import ui_pages as M
    s, p = r.get("s"), r.get("p")
    with st.sidebar:
        st.markdown('<div class="brand"><span class="mark">ib</span>ib<i>·</i>tee</div>', unsafe_allow_html=True)
        nav.link("Home", key="nav_home", icon=":material/home:", width="stretch", kind="primary" if not s and p in (None, "home") else "secondary")
        nav.link("Subjects", key="nav_subjects", icon=":material/library_books:", width="stretch", kind="primary" if not s and p == "subjects" else "secondary", p="subjects")
        nav.link("Bookmarks", key="nav_bm", icon=":material/bookmark:", width="stretch", kind="primary" if not s and p == "bookmarks" else "secondary", p="bookmarks")
        nav.link("Calendar", key="nav_cal", icon=":material/calendar_month:", width="stretch",
                 kind="primary" if p == "calendar" or (s == "maths_ai_hl" and p == "session") else "secondary", p="calendar")
        if s == "maths_ai_hl":
            active = M.active_key(r)
            st.markdown(f'<div class="navhead"><span class="dot" style="--c:{T.SUBJECT_COLOURS[s]}"></span>Mathematics AI HL</div>', unsafe_allow_html=True)
            for heading, items in M.nav_groups():
                if heading:
                    st.markdown(f'<div class="navsub">{heading}</div>', unsafe_allow_html=True)
                for key, label, icon, target in items:
                    nav.link(label, key=f"nav_m_{key}", icon=icon, width="stretch", kind="primary" if active == key else "secondary", s=s, **target)
        elif s == "chem_hl":
            st.markdown(f'<div class="navhead"><span class="dot" style="--c:{T.SUBJECT_COLOURS[s]}"></span>Chemistry HL</div>', unsafe_allow_html=True)
            import chem_app
            for key, label, icon in CHEM_NAV:
                if key in chem_app.OWNER_PAGES and not users.is_owner():
                    continue
                if key in CHEM_GROUPS:
                    st.markdown(f'<div class="navsub">{CHEM_GROUPS[key]}</div>', unsafe_allow_html=True)
                if st.button(label, key=f"nav_c_{key}", icon=icon, width="stretch", type="primary" if p == key else "secondary"):
                    st.session_state["page"] = key
                    st.session_state.pop("today_queue", None)
                    nav.go(s="chem_hl", p=key)
        st.markdown('<div class="navhead">My subjects</div>', unsafe_allow_html=True)
        for sid in prof["my_subjects"]:
            if sid != s:
                nav.link(store.SUBJECTS[sid]["name"], key=f"nav_my_{sid}", icon=":material/circle:", width="stretch", s=sid)
        if not prof["my_subjects"]:
            nav.link("+ Add your subjects", key="nav_add", kind="tertiary", p="subjects")
        st.markdown('<div class="navhead">Account</div>', unsafe_allow_html=True)
        # a new key on each page, so the menu closes after taking the student somewhere
        with st.popover(prof["name"] or "Profile", icon=":material/account_circle:", width="stretch", key=f"account_menu_{s}_{p}_{r.get('v')}"):
            st.caption(f"Signed in as @{user['username']}")
            nav.link("My profile", key="nav_profile", icon=":material/person:", width="stretch", p="profile")
            nav.link("Exams & deadlines", key="nav_exams", icon=":material/event:", width="stretch", p="calendar", v="exams")
            nav.link("Weekly routine", key="nav_routine", icon=":material/schedule:", width="stretch", p="calendar", v="routine")
            dark = st.toggle("Dark mode", value=prof.get("theme") == "dark", key="theme_toggle")
            if st.button("Sign out", key="nav_sign_out", icon=":material/logout:", width="stretch", type="tertiary"):
                login.sign_out()
        if dark != (prof.get("theme") == "dark"):
            prof["theme"] = "dark" if dark else "light"
            store.save_profile(prof)
            # Streamlit sends its own theme only when a page loads, so reload once to switch the built-in widgets too
            import streamlit.components.v1 as components
            components.html("<script>window.parent.location.reload()</script>", height=0)


def main() -> None:
    user = login.gate()                                                     # nothing below runs without an account
    if not user["onboarded"]:
        T.apply(store.profile().get("theme", "light"))
        with st.sidebar:
            if st.button("Sign out", key="ob_sign_out", icon=":material/logout:", width="stretch"):
                login.sign_out()
        onboarding.wizard(user)
        return
    prof = store.profile()
    try:
        st._config.set_option("theme.base", prof.get("theme", "light"))     # Streamlit's own widgets follow the chosen theme
    except Exception:
        pass
    T.apply(prof.get("theme", "light"))
    r = resolve_route()
    sidebar(r, prof, user)
    s, p = r.get("s"), r.get("p")
    if s == "maths_ai_hl":
        from maths import ui_pages
        ui_pages.render(r)
    elif s == "chem_hl":
        import chem_app
        chem_app.render(r["p"])
    elif p == "calendar":
        from ibtee import planner
        planner.page(r.get("v") or "month", r.get("m"), r.get("d"))
    elif p == "subjects":
        home.subjects_page()
    elif p == "bookmarks":
        home.bookmarks_page()
    elif p == "profile":
        from ibtee import profile
        profile.page(user)
    else:
        from maths.schedule import now_local
        home.home_page(now_local().date())


main()
