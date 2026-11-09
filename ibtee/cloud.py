"""
Keeps personal files safe on Streamlit Community Cloud, whose disk is erased at every restart.

The app goes on reading and writing its ordinary files. On the hosted app, each save is also copied to Firestore
(ib_tee/<owner>/files/<path>, compressed), and after a restart a student's files are brought back the first time they are needed.
Without a [firestore] section in the Streamlit secrets (running on your own computer, tests) none of this happens.
"""
from __future__ import annotations

import threading
import time
import zlib
from functools import lru_cache
from pathlib import Path, PurePosixPath

_lock = threading.RLock()
_restored: set[str] = set()          # whose files this server has already brought back


def config() -> dict | None:
    """The service-account key, if it has really been filled in."""
    try:
        import streamlit as st
        cfg = dict(st.secrets["firestore"])
    except Exception:                # no secrets file, or no such section
        return None
    return cfg if "BEGIN PRIVATE KEY" in str(cfg.get("private_key", "")) else None


def enabled() -> bool:
    return config() is not None


@lru_cache(maxsize=1)
def _client():
    from google.cloud import firestore
    from google.oauth2 import service_account
    cfg = config()
    return firestore.Client(project=cfg["project_id"], credentials=service_account.Credentials.from_service_account_info(cfg))


def _files(owner: str):
    return _client().collection("ib_tee").document(owner).collection("files")


def _doc_id(rel: str) -> str:
    return rel.replace("/", "~")     # a Firestore id can't hold "/"


def push(owner: str, rel: str, path: Path) -> None:
    """Copy one saved file up. A Firestore field holds 1 MiB; compressed, that is several MiB of these text files."""
    _files(owner).document(_doc_id(rel)).set({"path": rel, "z": zlib.compress(Path(path).read_bytes(), 9), "updated": time.time()})


def ensure(owner: str, folder: Path) -> None:
    """Bring this owner's files back once per server start. On failure it raises and tries again next time: carrying on with empty
    files would let the next save overwrite the real ones."""
    if not enabled() or owner in _restored:
        return
    with _lock:
        if owner in _restored:
            return
        for doc in _files(owner).stream():
            d = doc.to_dict()
            rel = PurePosixPath(d["path"])
            if rel.is_absolute() or ".." in rel.parts:
                continue
            target = Path(folder) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zlib.decompress(d["z"]))
        _restored.add(owner)
