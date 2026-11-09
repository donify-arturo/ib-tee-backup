"""
Tips found on the web for a card: stored separately from the decks, checked locally, shown only after the student accepts them.

    data/web_tips.json  {"tips": {tip_id: {card_id, sub_topic, pillar, kind, tip, why, url, domain, status, reasons, warnings,
                                           related, added}},
                         "researched": {card_id: date}}

status: pending (waiting for the student) | accepted | rejected (by the student) | failed (by the local checks).
Web text is a suggestion only: it never counts as evidence of what examiners reward. Only markschemes and reports do that.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from ingest.scan_books import equation_issues, unknown_elements

TIPS_FILE = Path(__file__).resolve().parent / "data" / "web_tips.json"
MAX_WORDS = 30
KINDS = ["mistake", "explanation", "memory_aid", "shortcut"]
PILLARS = ["1_context", "2_markscheme_logic", "3_novel_application", "4_command_terms", "5_time_efficiency", "6_data_booklet", "7_elimination"]

# Sites that host copied exam papers or reports: never a source, however useful the page looks.
BLOCKED = {"scribd.com", "coursehero.com", "studocu.com", "chegg.com", "pdfcoffee.com", "docplayer.net", "yumpu.com", "slideshare.net",
           "ibdocs.re", "exam-mate.com", "iitianacademy.com", "dokumen.pub", "vdoc.pub", "docsity.com"}
OTHER_BOARD = re.compile(r"a-level|alevel|gcse|\bigcse\b|\baqa\b|\bocr\b|edexcel|\bcie\b|cambridge-international|\bap-chem|\bsat\b", re.I)
_BOOKLET_FORMULA = re.compile(r"pH\s*\+\s*pOH|pKa\s*\+\s*pKb|Ka\s*[×x*]\s*Kb|buffer equation", re.I)


def _retry(action, attempts: int = 40, wait: float = 0.05):
    """Windows briefly refuses access to a file while another program is reading or replacing it."""
    for i in range(attempts):
        try:
            return action()
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(wait)


def load(path: Path = TIPS_FILE) -> dict:
    if not path.exists():
        return {"tips": {}, "researched": {}}
    return json.loads(_retry(lambda: path.read_text(encoding="utf-8")))


def save(data: dict, path: Path = TIPS_FILE) -> None:
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _retry(lambda: os.replace(tmp, path))


@contextmanager
def _lock(path: Path, timeout: float = 15.0, stale_after: float = 60.0):
    """Only one writer at a time. A lock left behind by a crash is cleared once it is old."""
    lock = path.with_suffix(".lock")
    start = time.time()
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except (FileExistsError, PermissionError):      # PermissionError: Windows, while the old lock is being deleted
            try:
                if time.time() - lock.stat().st_mtime > stale_after:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.time() - start > timeout:
                raise TimeoutError(f"{path.name} is busy; try again")
            time.sleep(0.05)
    try:
        yield
    finally:
        _retry(lambda: lock.unlink(missing_ok=True))


def update(change, path: Path = TIPS_FILE):
    """Read the file fresh, apply change(data), write it back, all under the lock. A search takes a minute or more, so
    holding on to data loaded earlier would overwrite anything saved in between, including the student's decisions."""
    with _lock(path):
        data = load(path)
        result = change(data)
        save(data, path)
    return result


def domain_of(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_blocked(domain: str) -> bool:
    return any(domain == b or domain.endswith("." + b) for b in BLOCKED)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower()))


def overlap(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / max(1, min(len(wa), len(wb)))


def card_text(card: dict) -> str:
    wt = card.get("walkthrough") or {}
    parts = [card.get("title", ""), wt.get("key_idea", ""), wt.get("careful", "")]
    for step in (wt.get("steps") or {}).values():
        parts += [str(v) for k, v in step.items() if k != "seconds"]
    return " ".join(parts)


def check(tip: dict, card: dict, known_tips: list[str]) -> tuple[list[str], list[str]]:
    """Free local checks. Returns (reasons to fail it, warnings to show the student)."""
    fail, warn = [], []
    text = f"{tip.get('tip', '')} {tip.get('why', '')}"
    url, domain = tip.get("url", ""), domain_of(tip.get("url", ""))
    if not tip.get("tip", "").strip():
        fail.append("empty tip")
    if urlparse(url).scheme not in {"http", "https"} or not domain:
        fail.append("no usable source link")
    elif is_blocked(domain):
        fail.append(f"{domain} hosts copied papers")
    if tip.get("pillar") not in PILLARS:
        fail.append(f"unknown criterion {tip.get('pillar')}")
    if tip.get("kind") not in KINDS:
        fail.append(f"unknown kind {tip.get('kind')}")
    for field in ("tip", "why"):
        if len(tip.get(field, "").split()) > MAX_WORDS:
            fail.append(f"{field} is over {MAX_WORDS} words")
    fail += [f"equation doesn't balance: {e}" for e in equation_issues(text)]
    fail += [f"'{e}' isn't an element" for e in unknown_elements(text)]
    # Conventions from the IB guide and data booklet that web pages often get wrong
    for sentence in re.split(r"(?<=[.;])\s+", text):
        s = sentence.lower()
        if "lattice enthalpy" in s and re.search(r"\b(negative|exothermic)\b", s) and "formation" not in s and "not " not in s:
            fail.append("says lattice enthalpy is negative; the IB defines it as endothermic")
        if re.search(r"bond[- ]breaking\b.*\b(releases?|exothermic)\b|breaking bonds?\b.*\b(releases?|exothermic)\b", s) and "not " not in s:
            fail.append("says bond breaking releases energy")
        if re.search(r"(forming|formation of) bonds?\b.*\b(absorbs?|requires?|endothermic)\b", s) and "not " not in s:
            fail.append("says bond forming takes in energy")
        if _BOOKLET_FORMULA.search(sentence) and re.search(r"\b(in|from) the (data )?booklet\b", s) and not re.search(r"\bnot\b|n't\b", s):
            fail.append("claims a formula is in the data booklet when it isn't")
    if re.search(r"\bPaper 3\b|\bOption [A-D]\b", text):
        fail.append("refers to the old syllabus (Paper 3 or options)")
    if OTHER_BOARD.search(url) or OTHER_BOARD.search(text):
        warn.append("written for another exam board")
    if re.search(r"\bTopic \d+\b", text) or re.search(r"/(ib-)?chemistry-(sl|hl)-20(1|2[0-3])", url):
        warn.append("may be for the old syllabus")
    if tip.get("tip") and overlap(tip["tip"], card_text(card)) >= 0.8:
        fail.append("the card already says this")
    if tip.get("tip") and any(overlap(tip["tip"], other) >= 0.8 for other in known_tips):
        fail.append("already suggested")
    return list(dict.fromkeys(fail)), warn


def related_refs(tip: str, pack: dict | None) -> list[str]:
    """Examiner comments using similar words: a pointer for the student, not proof the tip is right."""
    if not pack:
        return []
    words = _words(tip)
    scored = []
    for e in pack.get("examiner_errors", []):
        shared = words & _words(e["sentence"])
        if len(shared) >= 3 and len(shared) / max(1, len(words)) >= 0.4:
            scored.append((len(shared), e["ref"]))
    return list(dict.fromkeys(ref for _n, ref in sorted(scored, reverse=True)))[:2]


def add_proposals(data: dict, found: list[dict], card: dict, sub_topic: str, pack: dict | None = None) -> Counter:
    """Check what research found and store it, including failures, so the same tip isn't suggested twice."""
    tally = Counter()
    known = [t["tip"] for t in data["tips"].values() if t["card_id"] == card["card_id"]]
    for tip in found:
        fail, warn = check(tip, card, known)
        tip_id = hashlib.sha1(f"{card['card_id']}|{tip.get('tip', '')}".encode()).hexdigest()[:12]
        if tip_id in data["tips"]:
            tally["duplicate"] += 1
            continue
        status = "failed" if fail else "pending"
        data["tips"][tip_id] = {"card_id": card["card_id"], "sub_topic": sub_topic, "pillar": tip.get("pillar"), "kind": tip.get("kind"),
                                "tip": tip.get("tip", ""), "why": tip.get("why", ""), "url": tip.get("url", ""), "domain": domain_of(tip.get("url", "")),
                                "status": status, "reasons": fail, "warnings": warn, "related": related_refs(tip.get("tip", ""), pack),
                                "added": time.strftime("%Y-%m-%d %H:%M")}
        known.append(tip.get("tip", ""))
        tally[status] += 1
    data["researched"][card["card_id"]] = time.strftime("%Y-%m-%d")
    return tally


def set_status(data: dict, tip_id: str, status: str) -> None:
    data["tips"][tip_id]["status"] = status


def accepted_for(data: dict, card_id: str) -> list[dict]:
    return [t for t in data["tips"].values() if t["card_id"] == card_id and t["status"] == "accepted"]


def pending(data: dict) -> list[tuple[str, dict]]:
    return [(i, t) for i, t in data["tips"].items() if t["status"] == "pending"]


def source_scores(data: dict) -> dict[str, dict]:
    """How each site has done so far. Tips you accept raise its score; tips you or the checks reject lower it.
    A tip that merely repeated the card or an earlier tip says nothing about the site, so it isn't counted."""
    table: dict[str, dict] = {}
    for t in data["tips"].values():
        if not t["domain"] or t["status"] == "pending":
            continue
        if t["status"] == "failed" and all(r in {"the card already says this", "already suggested"} for r in t["reasons"]):
            continue
        row = table.setdefault(t["domain"], {"accepted": 0, "rejected": 0})
        row["accepted" if t["status"] == "accepted" else "rejected"] += 1
    for row in table.values():
        row["score"] = round((row["accepted"] + 1) / (row["accepted"] + row["rejected"] + 2), 2)
    return dict(sorted(table.items(), key=lambda kv: (-kv[1]["score"], kv[0])))


def preferred_and_avoided(data: dict) -> tuple[list[str], list[str]]:
    scores = source_scores(data)
    prefer = [d for d, r in scores.items() if r["accepted"] >= 2 and r["score"] >= 0.6]
    avoid = [d for d, r in scores.items() if r["rejected"] >= 3 and r["score"] <= 0.25]
    return prefer, avoid


def next_cards(data: dict, cards: list[tuple[str, dict]], hard_ids: set[str] | None = None, limit: int = 1) -> list[tuple[str, dict]]:
    """Cards to research next: never-researched first, ones you marked hard in your notes first, then by priority."""
    hard_ids = hard_ids or set()
    todo = [(code, c) for code, c in cards if c.get("walkthrough") and c["card_id"] not in data["researched"]]
    todo.sort(key=lambda x: (x[1]["card_id"] not in hard_ids, x[1].get("priority", 9), x[1]["card_id"]))
    return todo[:limit]
