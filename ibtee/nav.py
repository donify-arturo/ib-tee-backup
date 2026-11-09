"""
Where the student is, kept in the URL (?s=maths_ai_hl&p=sub&c=1.2), so a page can be reloaded, bookmarked or opened in a new tab.
Buttons change the route without a page reload, so session state (an open markscheme, a running mixed set) survives navigation.
"""
from __future__ import annotations

import streamlit as st

KEYS = ("s", "p", "t", "c", "q", "sh", "ex", "ss", "sess", "pp", "v", "m", "d", "bs", "bx", "pg")


def route() -> dict:
    qp = st.query_params
    return {k: qp.get(k) for k in KEYS if qp.get(k) not in (None, "")}


def go(**target) -> None:
    """Replace the route and rerun. Keys left out are cleared."""
    st.query_params.clear()
    for k, v in target.items():
        if v not in (None, ""):
            st.query_params[k] = str(v)
    st.rerun()


def link(label: str, key: str, icon: str | None = None, kind: str = "secondary", width: str = "content", help: str | None = None,
         disabled: bool = False, shortcut: str | None = None, **target) -> None:
    """A button that goes somewhere."""
    if st.button(label, key=key, icon=icon, type=kind, width=width, help=help, disabled=disabled, shortcut=shortcut):
        go(**target)
