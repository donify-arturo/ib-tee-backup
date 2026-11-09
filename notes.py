"""
The student's own notes: the steps worth remembering for each type of question, saved from cards or written by hand.

    data/notes.json   {"items": {note_id: {card_id, sub_topic, question_type, steps, careful, ref, hard, note, added}}}

A saved note keeps its own copy of the steps, so rebuilding a deck can't change or lose it.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from card_ui import remember_points

NOTES_FILE = Path(__file__).resolve().parent / "data" / "notes.json"


def load(path: Path = NOTES_FILE) -> dict:
    if not path.exists():
        return {"items": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save(data: dict, path: Path = NOTES_FILE) -> None:
    """Write to a temporary file first, so a crash mid-write can't damage existing notes."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def from_card(card: dict, sub_topic: str) -> dict | None:
    """What a card offers to the notes: its question type, its procedure, its tricks and the step to be careful with."""
    steps = remember_points(card)
    if not steps:
        return None
    wt = card.get("walkthrough") or {}
    return {"card_id": card["card_id"], "sub_topic": sub_topic, "question_type": wt.get("question_type") or card["title"],
            "steps": steps, "tricks": list(wt.get("tricks") or []), "careful": wt.get("careful", ""), "ref": wt.get("question_ref", "")}


def saved_id(data: dict, entry: dict) -> str | None:
    """The note already saved from this card, if any. A rebuilt deck can reuse a card id for another question type."""
    return next((k for k, v in data["items"].items()
                 if v.get("card_id") == entry["card_id"] and v.get("question_type") == entry["question_type"]), None)


def add(data: dict, entry: dict, hard: bool = False) -> str:
    existing = saved_id(data, entry) if entry.get("card_id") else None
    if existing:
        return existing
    note_id = entry.get("card_id") or f"own-{uuid.uuid4().hex[:8]}"
    if note_id in data["items"]:     # never overwrite a note from an older deck
        note_id = f"{note_id}-{uuid.uuid4().hex[:6]}"
    data["items"][note_id] = {**entry, "hard": hard, "note": "", "added": time.strftime("%Y-%m-%d %H:%M")}
    return note_id


def add_own(data: dict, sub_topic: str, question_type: str, steps_text: str, careful: str = "") -> str | None:
    """A note written by hand, one step per line. Needs a question type and at least one step."""
    steps = [s.strip() for s in steps_text.splitlines() if s.strip()]
    if not question_type.strip() or not steps:
        return None
    return add(data, {"card_id": None, "sub_topic": sub_topic, "question_type": question_type.strip(), "steps": steps,
                      "careful": careful.strip(), "ref": ""})


def grouped(data: dict, sub_topic: str | None = None, only_hard: bool = False, search: str = "") -> dict[str, dict[str, list]]:
    """{sub_topic: {question_type: [(note_id, item), ...]}}, hardest first within each type."""
    needle = search.strip().lower()
    out: dict[str, dict[str, list]] = {}
    for note_id, item in data["items"].items():
        if sub_topic and item["sub_topic"] != sub_topic:
            continue
        if only_hard and not item.get("hard"):
            continue
        text = " ".join([item["question_type"], item.get("careful", ""), item.get("note", ""), *item["steps"], *item.get("tricks", [])]).lower()
        if needle and needle not in text:
            continue
        out.setdefault(item["sub_topic"], {}).setdefault(item["question_type"], []).append((note_id, item))
    for types in out.values():
        for rows in types.values():
            rows.sort(key=lambda r: (not r[1].get("hard"), r[1].get("added", "")))
    return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}
