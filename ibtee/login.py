"""
The sign-in screen, and staying signed in across reloads.

Hosted (ib-tee.streamlit.app): Google only, through Streamlit's st.login, which keeps its own sign-in cookie. The [auth] and [access]
settings live in the app's Streamlit Secrets.
On your own computer: username and password. Streamlit forgets its session on every page load, so the browser keeps a random token in a
cookie (only its hash is stored: ibtee/users.py). Streamlit can read cookies but not set them, so a small script on the page writes it.
"""
from __future__ import annotations

import importlib.util
from collections.abc import Mapping

import streamlit as st

from ibtee import cloud, store, users
from ibtee import theme as T

COOKIE = "ibtee_session"
TOKEN_KEY = "_auth_token"
SET_COOKIE, CLEAR_COOKIE = "_auth_set_cookie", "_auth_clear_cookie"


def _write_cookie(value: str, max_age: int) -> None:
    st.iframe(f"<script>window.parent.document.cookie='{COOKIE}={value}; path=/; max-age={max_age}; SameSite=Strict'</script>", height=1)


def _cookie_token() -> str | None:
    try:
        token = st.context.cookies.get(COOKIE)
    except Exception:                    # no browser behind this run (tests)
        return None
    return token if isinstance(token, str) and token else None


def _on_host() -> bool:
    """Is this browser on the computer running the app? Streamlit gives no address for a connection from the same machine."""
    try:
        return st.context.ip_address in (None, "127.0.0.1", "::1")
    except Exception:
        return False


# --------------------------------------------------------------------------- Google
def _google_ready() -> bool:
    try:
        client = str(st.secrets["auth"]["google"]["client_id"])
    except Exception:                    # no secrets file, or no Google section in it
        return False
    return client.endswith(".apps.googleusercontent.com") and importlib.util.find_spec("authlib") is not None


def _google_signed_in() -> bool:
    return _google_ready() and bool(st.user.is_logged_in)


def _access() -> tuple[str | None, list[str] | None]:
    """(the owner's email, the only emails allowed in), from the [access] secrets; no list means any Google account may join."""
    try:
        cfg = st.secrets["access"]
    except Exception:
        return None, None
    return str(cfg.get("owner_email") or "") or None, list(cfg.get("allowed_emails") or []) or None


def _from_google() -> dict:
    """The account behind the Google sign-in. Stops the page with the reason if there can't be one."""
    info = st.user.to_dict()
    owner_email, allowed = _access()
    try:
        if info.get("email_verified") is False:
            raise users.AccountError("Verify your Google email address first.")
        user, created = users.google_account(str(info.get("sub") or ""), str(info.get("email") or ""), str(info.get("name") or ""),
                                             on_host=_on_host(), owner_email=owner_email, allowed=allowed)
    except users.AccountError as err:
        T.apply("light")
        st.error(str(err))
        if st.button("Use another account", key="google_back"):
            st.logout()
        st.stop()
    st.session_state[users.SESSION_KEY] = user
    _open_workspace(user)
    if created:
        _first_profile(user)
    return user


# --------------------------------------------------------------------------- entering and leaving
def _open_workspace(user: dict) -> None:
    """Never carry on without the student's files: a save over empty ones would destroy the real ones."""
    try:
        users.open_workspace(user)
    except Exception as err:
        print(f"Could not restore files for {user['id']}: {err}", flush=True)
        st.error("Your saved work couldn't be loaded just now, so nothing has been changed. Refresh the page in a moment.")
        st.stop()


def setup_problems(secrets) -> list[str]:
    """What is wrong with the Streamlit Secrets, by setting name only: this shows on a public page, so never a value."""
    def filled(s, key: str) -> bool:
        v = str(s.get(key) or "")
        return bool(v) and "CHANGE_ME" not in v

    out = []
    fs = secrets.get("firestore")
    if not isinstance(fs, Mapping):
        out.append("[firestore] section is missing")
    else:
        for key in ("type", "project_id", "private_key_id", "client_email", "client_id", "token_uri"):
            if not filled(fs, key):
                out.append(f"[firestore] {key} is empty")
        if "BEGIN PRIVATE KEY" not in str(fs.get("private_key") or ""):
            out.append("[firestore] private_key is empty or doesn't include the -----BEGIN PRIVATE KEY----- part")
    auth = secrets.get("auth")
    if not isinstance(auth, Mapping):
        return out + ["[auth] section is missing"]
    out += [f"[auth] {key} is empty" for key in ("redirect_uri", "cookie_secret") if not filled(auth, key)]
    google = auth.get("google")
    if not isinstance(google, Mapping):
        return out + ["[auth.google] section is missing"]
    if not filled(google, "client_id") or not str(google.get("client_id")).endswith(".apps.googleusercontent.com"):
        out.append("[auth.google] client_id is empty or doesn't end in .apps.googleusercontent.com")
    out += [f"[auth.google] {key} is empty" for key in ("client_secret", "server_metadata_url") if not filled(google, key)]
    return out


def _show_setup_problems() -> None:
    try:
        problems = setup_problems(st.secrets)
    except Exception:                    # the box isn't valid TOML, or is empty; its error text could quote a value, so it isn't shown
        problems = ["The Secrets box is empty or isn't valid TOML"]
    if problems:
        st.warning("Settings this site can't use yet:\n\n" + "\n".join(f"- {T.esc(p)}" for p in problems))


def _first_profile(user: dict) -> None:
    if not user["owner"]:
        store.save_profile({"name": user["name"], "email": "", "my_subjects": [], "theme": "light"})


def _enter(user: dict, new_account: bool = False) -> None:
    """Password sign-in. Starts from a clean session, so nothing of a previous student's carries over."""
    token = users.new_session(user["username"])
    st.session_state.clear()
    st.session_state[users.SESSION_KEY] = user
    st.session_state[TOKEN_KEY] = token
    st.session_state[SET_COOKIE] = token
    _open_workspace(user)
    if new_account:
        _first_profile(user)
    st.query_params.clear()
    st.rerun()


def sign_out() -> None:
    token = st.session_state.get(TOKEN_KEY)
    if token:
        users.end_session(token)
    google = _google_signed_in()
    st.session_state.clear()
    if google:
        st.logout()                      # removes Streamlit's sign-in cookie and reloads the page
        st.stop()
    st.session_state[CLEAR_COOKIE] = True
    st.query_params.clear()
    st.rerun()


def gate() -> dict:
    """The signed-in account. If there is none, draws the sign-in screen and stops the page, so no page can run without an account."""
    user = users.current()
    if not user:
        token = _cookie_token()
        user = users.session_user(token) if token else None
        if user:
            st.session_state[users.SESSION_KEY] = user
            st.session_state[TOKEN_KEY] = token
        elif _google_signed_in():
            user = _from_google()
    if st.session_state.pop(CLEAR_COOKIE, False):
        _write_cookie("", 0)
    if user:
        _open_workspace(user)
        pending = st.session_state.pop(SET_COOKIE, None)
        if pending:
            _write_cookie(pending, users.SESSION_DAYS * 86400)
        return user
    T.apply("light")
    _screen()
    st.stop()


# --------------------------------------------------------------------------- the screen
def _screen() -> None:
    _, mid, _ = st.columns([0.28, 0.44, 0.28])
    with mid:
        st.markdown('<div class="brand" style="margin:2.5rem 0 1rem 0"><span class="mark">ib</span>ib<i>·</i>tee</div>', unsafe_allow_html=True)
        if cloud.enabled():
            st.markdown('<div class="ptitle">Welcome</div>', unsafe_allow_html=True)
            st.caption("New here? You'll be asked for your subjects, timetable and exam dates, and get a calendar of your own.")
            if not _google_ready():
                st.error("Sign-in isn't set up yet.")
            elif st.button("Continue with Google", key="google_login", icon=":material/login:", type="primary", width="stretch"):
                st.login("google")
            return
        if not users.any_accounts():
            st.markdown('<div class="ptitle">Set up IB TEE</div>', unsafe_allow_html=True)
            if not _on_host():
                st.info("The first account has to be created on the computer running IB TEE.")
                _show_setup_problems()
                return
            st.caption("This first account is yours: it keeps the calendar, progress and notes already on this computer. Anyone who signs up "
                       "afterwards starts with their own empty calendar.")
            _sign_up("Create my account")
            return
        st.markdown('<div class="ptitle">Welcome</div>', unsafe_allow_html=True)
        sign_in, sign_up = st.tabs(["Sign in", "Create an account"])
        with sign_in:
            _sign_in()
        with sign_up:
            st.caption("You'll be asked for your subjects, timetable and exam dates, and get a calendar of your own.")
            _sign_up("Create my account")


def _sign_in() -> None:
    with st.form("login_form", border=False):
        username = st.text_input("Username", key="login_user", autocomplete="username")
        password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
        go = st.form_submit_button("Sign in", type="primary", width="stretch")
    if not go:
        return
    try:
        user = users.verify(username, password)
    except users.AccountError as err:
        st.error(str(err))
        return
    if not user:
        st.error("That username and password don't match.")
        return
    _enter(user)


def _sign_up(label: str) -> None:
    with st.form("signup_form", border=False):
        name = st.text_input("Your name", key="signup_name", autocomplete="name", max_chars=60)
        username = st.text_input("Username", key="signup_user", autocomplete="username", max_chars=30, help="Letters, numbers, dots, dashes or underscores.")
        password = st.text_input(f"Password (at least {users.MIN_PASSWORD} characters)", type="password", key="signup_password", autocomplete="new-password")
        again = st.text_input("Password again", type="password", key="signup_again", autocomplete="new-password")
        go = st.form_submit_button(label, type="primary", width="stretch")
    if not go:
        return
    if password != again:
        st.error("The two passwords are different.")
        return
    try:
        user = users.create(username, name, password, on_host=_on_host())
    except users.AccountError as err:
        st.error(str(err))
        return
    _enter(user, new_account=True)
