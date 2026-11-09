"""
Timed practice exams built from the past-paper questions, and their marking.

    data/maths/exams.json   {"exams": [{"id", "paper", "minutes", "target", "qids", "created", "started", "finished", "status",
                                       "topics", "marks": {qid: {part: awarded}}}]}

The revision papers hold real IB questions from 2021–2025, so a mock is made of real exam questions at real exam length. It is not a
real past paper: the question selection is the app's.
"""
from __future__ import annotations

import json
import os
import random
import time
import uuid
from pathlib import Path

from maths import data, progress

DIR = data.DIR
EXAMS = DIR / "exams.json"
FORMATS = {"1": {"minutes": 120, "marks": 110}, "2": {"minutes": 120, "marks": 110}}


def load(path: Path | None = None) -> dict:
    path = path or EXAMS
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"exams": []}


def save(store: dict, path: Path | None = None) -> None:
    path = path or EXAMS
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def build(paper: str, topics: list[int], rows: list[dict], seed: str | None = None, target: int | None = None) -> dict:
    """Pick questions of this paper from the chosen topics, in turn, until the marks reach the target. Untried questions first."""
    target = target or FORMATS[paper]["marks"]
    seed = seed or uuid.uuid4().hex
    pool = [q for q in data.questions() if q["paper"] == paper and q["topic"] in topics and q["has_markscheme"]]
    ordered = progress.pick_unseen(pool, rows, len(pool), seed)
    by_topic: dict[int, list[dict]] = {}
    for q in ordered:
        by_topic.setdefault(q["topic"], []).append(q)
    chosen, total = [], 0
    while total < target and any(by_topic.values()):
        for t in topics:
            if by_topic.get(t) and total < target:
                q = by_topic[t].pop(0)
                if total + q["max_marks"] > target + 8:
                    continue
                chosen.append(q)
                total += q["max_marks"]
    chosen.sort(key=lambda q: (q["max_marks"], q["id"]))         # shorter questions first, as on a real paper
    minutes = round(FORMATS[paper]["minutes"] * total / FORMATS[paper]["marks"])
    return {"id": uuid.uuid4().hex[:8], "paper": paper, "topics": topics, "qids": [q["id"] for q in chosen], "total": total,
            "minutes": minutes, "created": time.strftime("%Y-%m-%d %H:%M"), "started": None, "finished": None, "status": "ready", "marks": {}}


def remaining_seconds(exam: dict, now: float | None = None) -> int:
    if not exam.get("started"):
        return exam["minutes"] * 60
    end = exam["started"] + exam["minutes"] * 60
    return max(0, int(end - (now or time.time())))


def score(exam: dict) -> tuple[int, int]:
    got = sum(sum(v.values()) for v in exam.get("marks", {}).values())
    return got, exam["total"]


def by_topic(exam: dict) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for qid in exam["qids"]:
        q = data.question(qid)
        if not q:
            continue
        got = sum(exam.get("marks", {}).get(qid, {}).values())
        a = out.setdefault(q["topic"], [0, 0])
        a[0] += got
        a[1] += q["max_marks"]
    return out
