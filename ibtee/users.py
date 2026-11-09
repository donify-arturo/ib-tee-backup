"""
Accounts, and whose files a page reads.

    data/accounts.json        {"users": {username: {id, name, salt, hash, owner, onboarded, created}},
                               "sessions": {sha256(token): {"user": username, "expires": unix time}}}
    data/users/<id>/...       everything personal to one student, laid out exactly as under data/

The first account is the owner: it must be created on the computer running the app, and it keeps the original files in data/ where
they are, so nothing is moved. Everyone else's personal files go through scoped(). Books, past papers and decks stay shared.
Passwords are stored only as scrypt hashes, and the browser's sign-in cookie only as a hash of it. Neither file is backed up to git.

Forgotten password:  python -m ibtee.users reset <username>
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path

from ibtee import cloud

DATA = Path(__file__).resolve().parents[1] / "data"
ACCOUNTS = DATA / "accounts.json"
USERS_DIR = DATA / "users"
SYSTEM = "_system"                   # the Firestore owner of accounts.json
SESSION_KEY = "auth_user"            # st.session_state: the signed-in account (public fields only)
SESSION_DAYS = 30
MIN_PASSWORD = 8
USERNAME = re.compile(r"^[a-z0-9._-]{3,30}$")
MAX_FAILS, LOCK_SECONDS = 5, 300

_lock = threading.RLock()
_fails: dict[str, list[float]] = {}  # username -> times of recent wrong passwords
_DUMMY_SALT = b"\0" * 16


class AccountError(ValueError):
    """The message is shown to the student."""


# --------------------------------------------------------------------------- the file
def _load() -> dict:
    cloud.ensure(SYSTEM, ACCOUNTS.parent)
    try:
        return json.loads(ACCOUNTS.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"users": {}, "sessions": {}}


def _save(db: dict) -> None:
    ACCOUNTS.parent.mkdir(parents=True, exist_ok=True)
    tmp = ACCOUNTS.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ACCOUNTS)
    if cloud.enabled():
        cloud.push(SYSTEM, "accounts.json", ACCOUNTS)


def _hash(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32).hex()


def _public(username: str, u: dict) -> dict:
    return {"id": u["id"], "username": username, "name": u["name"], "owner": bool(u.get("owner")), "onboarded": bool(u.get("onboarded"))}


def clean_username(username: str) -> str:
    return (username or "").strip().lower()


def any_accounts() -> bool:
    return bool(_load()["users"])


# --------------------------------------------------------------------------- accounts
def _check_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AccountError(f"Use a password of at least {MIN_PASSWORD} characters.")


def create(username: str, name: str, password: str, on_host: bool) -> dict:
    """A new account. The first one becomes the owner, and must be made on the computer running the app (on_host)."""
    username, name = clean_username(username), (name or "").strip()
    if not USERNAME.match(username):
        raise AccountError("Usernames are 3–30 characters: letters, numbers, dots, dashes or underscores.")
    if not name:
        raise AccountError("Write the name you'd like to be called.")
    _check_password(password)
    salt = secrets.token_bytes(16)
    hashed = _hash(password, salt)
    with _lock:
        db = _load()
        if username in db["users"]:
            raise AccountError("That username is taken.")
        owner = not db["users"]
        if owner and not on_host:
            raise AccountError("The first account has to be created on the computer running IB TEE.")
        u = {"id": uuid.uuid4().hex, "name": name[:60], "salt": salt.hex(), "hash": hashed, "owner": owner, "onboarded": owner,
             "created": time.strftime("%Y-%m-%d %H:%M")}
        db["users"][username] = u
        _save(db)
    return _public(username, u)


def verify(username: str, password: str, now: float | None = None) -> dict | None:
    """The account if the password is right, else None. Raises AccountError after too many wrong tries."""
    username, now = clean_username(username), now if now is not None else time.time()
    with _lock:
        recent = [t for t in _fails.get(username, []) if now - t < LOCK_SECONDS]
        _fails[username] = recent
    if len(recent) >= MAX_FAILS:
        raise AccountError("Too many wrong tries. Wait five minutes and try again.")
    u = _load()["users"].get(username)
    # an unknown username costs the same time as a wrong password, so it can't be told apart
    has_password = bool(u and u.get("hash"))         # Google accounts have none
    got = _hash(password or "", bytes.fromhex(u["salt"]) if has_password else _DUMMY_SALT)
    if has_password and hmac.compare_digest(got, u["hash"]):
        with _lock:
            _fails.pop(username, None)
        return _public(username, u)
    with _lock:
        _fails.setdefault(username, []).append(now)
    return None


def google_account(sub: str, email: str, name: str, on_host: bool, owner_email: str | None = None, allowed: list[str] | None = None) -> tuple[dict, bool]:
    """The account for this Google identity, creating it the first time. Returns (account, was it just created). Matched on Google's
    permanent id, never the email. With owner_email (the hosted app) the owner is that address; otherwise the first account, on the host.
    With allowed, only those addresses (and the owner) may use the app."""
    if not sub:
        raise AccountError("Google didn't say who you are. Try again.")
    address = (email or "").strip().lower()
    is_owner_email = bool(owner_email) and address == owner_email.strip().lower()
    if allowed and not is_owner_email and address not in {a.strip().lower() for a in allowed}:
        raise AccountError("This IB TEE is private, and that Google account isn't on its list.")
    with _lock:
        db = _load()
        for username, u in db["users"].items():
            if u.get("google_sub") == sub:
                return _public(username, u), False
        no_owner = not any(u.get("owner") for u in db["users"].values())
        if owner_email:
            owner = is_owner_email and no_owner
        else:
            owner = not db["users"]
            if owner and not on_host:
                raise AccountError("The first account has to be created on the computer running IB TEE.")
        base = re.sub(r"[^a-z0-9._-]", "", address.split("@")[0])[:26]
        base = base if len(base) >= 3 else "student"
        username, n = base, 2
        while username in db["users"]:
            username, n = f"{base}{n}", n + 1
        u = {"id": uuid.uuid4().hex, "name": ((name or "").strip() or username)[:60], "salt": "", "hash": "", "google_sub": sub, "email": address,
             "owner": owner, "onboarded": owner, "created": time.strftime("%Y-%m-%d %H:%M")}
        db["users"][username] = u
        _save(db)
    return _public(username, u), True


def set_password(username: str, password: str) -> None:
    """Change a password and sign that account out everywhere."""
    username = clean_username(username)
    _check_password(password)
    salt = secrets.token_bytes(16)
    hashed = _hash(password, salt)
    with _lock:
        db = _load()
        if username not in db["users"]:
            raise AccountError("No account with that username.")
        db["users"][username].update(salt=salt.hex(), hash=hashed)
        db["sessions"] = {k: v for k, v in db["sessions"].items() if v["user"] != username}
        _save(db)


def change_password(username: str, current: str, new: str) -> bool:
    """False if the current password is wrong (it counts towards the lock, like a wrong sign-in). Signs the account out everywhere."""
    _check_password(new)
    if not verify(username, current):
        return False
    set_password(username, new)
    return True


def set_onboarded(username: str) -> None:
    with _lock:
        db = _load()
        db["users"][username]["onboarded"] = True
        _save(db)


def rename(username: str, name: str) -> str:
    """The name the student is called by; returns it as stored."""
    name = (name or "").strip()[:60]
    if not name:
        raise AccountError("Write the name you'd like to be called.")
    with _lock:
        db = _load()
        db["users"][clean_username(username)]["name"] = name
        _save(db)
    return name


def details(username: str) -> dict:
    """What the Profile page shows that the session doesn't hold. Never the hash."""
    u = _load()["users"].get(clean_username(username)) or {}
    return {"created": u.get("created", ""), "email": u.get("email", ""), "has_password": bool(u.get("hash"))}


# --------------------------------------------------------------------------- staying signed in
def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session(username: str, now: float | None = None) -> str:
    now = now if now is not None else time.time()
    token = secrets.token_urlsafe(32)
    with _lock:
        db = _load()
        db["sessions"] = {k: v for k, v in db["sessions"].items() if v["expires"] > now}
        db["sessions"][_token_key(token)] = {"user": username, "expires": now + SESSION_DAYS * 86400}
        _save(db)
    return token


def session_user(token: str, now: float | None = None) -> dict | None:
    now = now if now is not None else time.time()
    db = _load()
    s = db["sessions"].get(_token_key(token))
    if not s or s["expires"] <= now or s["user"] not in db["users"]:
        return None
    return _public(s["user"], db["users"][s["user"]])


def end_session(token: str) -> None:
    with _lock:
        db = _load()
        if db["sessions"].pop(_token_key(token), None):
            _save(db)


def other_sessions(username: str, token: str | None, now: float | None = None) -> int:
    """How many other browsers are signed in to this account."""
    now = now if now is not None else time.time()
    keep = _token_key(token) if token else None
    return sum(1 for k, v in _load()["sessions"].items() if v["user"] == username and v["expires"] > now and k != keep)


def end_other_sessions(username: str, token: str | None) -> None:
    """Sign this account out of every browser except the one holding token."""
    keep = _token_key(token) if token else None
    with _lock:
        db = _load()
        db["sessions"] = {k: v for k, v in db["sessions"].items() if v["user"] != username or k == keep}
        _save(db)


# --------------------------------------------------------------------------- whose files
def current() -> dict | None:
    """The signed-in account, or None outside the app (build scripts, plain tests)."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        return None
    import streamlit as st
    return st.session_state.get(SESSION_KEY)


def guest_id() -> str | None:
    """The folder id of a signed-in student who isn't the owner; None for the owner (and for scripts), who use data/ itself."""
    u = current()
    return u["id"] if u and not u.get("owner") else None


def is_owner() -> bool:
    u = current()
    return bool(u and u.get("owner"))


def scoped(path: Path) -> Path:
    """Where a personal file under data/ lives for whoever is signed in. Paths outside data/ (a test's temporary file) are left alone."""
    uid = guest_id()
    if uid is None:
        return path
    try:
        rel = Path(path).relative_to(DATA)
    except ValueError:
        return path
    return path if rel.parts[:1] == ("users",) else USERS_DIR / uid / rel


def _folder(user: dict) -> Path:
    return DATA if user.get("owner") else USERS_DIR / user["id"]


def open_workspace(user: dict) -> None:
    """On the hosted app, bring this student's files back after a restart. Raises if it can't."""
    cloud.ensure(user["id"], _folder(user))


def saved(path: Path) -> None:
    """Call after writing a personal file: on the hosted app it is copied to Firestore. A failure is shown, never hidden."""
    u = current()
    if not u or not cloud.enabled():
        return
    try:
        cloud.push(u["id"], Path(path).relative_to(_folder(u)).as_posix(), path)
    except ValueError:                # not inside this student's folder (a test's temporary file)
        return
    except Exception as err:
        print(f"Could not back up {path}: {err}", flush=True)
        import streamlit as st
        st.warning("That change couldn't be saved online and may be lost if the app restarts. Try again in a moment.")


if __name__ == "__main__":
    import getpass
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != "reset":
        sys.exit("Usage: python -m ibtee.users reset <username>")
    try:
        set_password(sys.argv[2], getpass.getpass("New password: "))
    except AccountError as err:
        sys.exit(str(err))
    print("Password changed. That account has been signed out everywhere.")
