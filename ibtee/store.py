"""
App-wide settings shared by every subject.

    data/profile.json     {"name", "email", "my_subjects": [...], "theme": "light" | "dark"}
    data/bookmarks.json   {"items": [{"subject", "id", "label", "detail", "added"}]}
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "profile.json"
BOOKMARKS = ROOT / "data" / "bookmarks.json"

# The catalogue. Only subjects with content can be opened; the rest are listed so the structure is ready for them.
CATALOGUE = [
    ("Mathematics", "01", [("Mathematics AA", None, None), ("Mathematics AI", "maths_ai_hl", None)]),
    ("Sciences", "02", [("Biology", None, None), ("Chemistry", "chem_hl", None), ("Physics", None, None)]),
    ("Individuals & Societies", "03", [("Economics", None, None), ("History", None, None), ("Psychology", None, None)]),
    ("Language & Literature", "04", [("English Language & Literature", None, None)]),
    ("Language Acquisition", "05", [("English B", None, None), ("Spanish B", None, None)]),
]
SUBJECTS = {
    "maths_ai_hl": {"name": "Mathematics AI HL", "long": "IB Mathematics: Applications & Interpretation (AI) Higher Level (HL)", "level": "HL", "group": "Mathematics"},
    "chem_hl": {"name": "Chemistry HL", "long": "IB Chemistry Higher Level (HL) · 2025 syllabus", "level": "HL", "group": "Sciences"},
}


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def profile(path: Path = PROFILE) -> dict:
    p = {"name": os.environ.get("USERNAME", "Student").title(), "email": "", "my_subjects": ["chem_hl", "maths_ai_hl"], "theme": "light"}
    p.update(_read(path, {}))
    p["my_subjects"] = [s for s in p["my_subjects"] if s in SUBJECTS]
    return p


def save_profile(p: dict, path: Path = PROFILE) -> None:
    _write(path, p)


def bookmarks(path: Path = BOOKMARKS) -> list[dict]:
    return _read(path, {"items": []})["items"]


def is_bookmarked(subject: str, item_id: str, path: Path = BOOKMARKS) -> bool:
    return any(b["subject"] == subject and b["id"] == item_id for b in bookmarks(path))


def toggle_bookmark(subject: str, item_id: str, label: str, detail: str = "", path: Path = BOOKMARKS) -> bool:
    """Add or remove; returns True when the item is now saved."""
    items = bookmarks(path)
    if any(b["subject"] == subject and b["id"] == item_id for b in items):
        items = [b for b in items if not (b["subject"] == subject and b["id"] == item_id)]
        _write(path, {"items": items})
        return False
    items.insert(0, {"subject": subject, "id": item_id, "label": label, "detail": detail, "added": time.strftime("%Y-%m-%d %H:%M")})
    _write(path, {"items": items})
    return True
