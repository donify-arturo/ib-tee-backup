"""
How the 78 sub-topics connect, from evidence in the student's own files → data/maths/connections.json

    python -m ingest.maths_connections          (after ingest.maths_book_passages)

Evidence for a link between two sub-topics: different parts of one past-paper question test them; one textbook passage teaches both; one
calculator procedure serves both; textbook questions combine them; the syllabus notes link them; both belong to one of the student's six
priority links. A link needs more than a single weak signal, because question tags come from keyword rules.
"""
from __future__ import annotations

import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "maths" / "connections.json"
KEEP = 10


def build() -> dict:
    from maths import data, progress
    ev: dict[tuple[str, str], dict] = defaultdict(lambda: {"syllabus": False, "past": [], "passages": [], "sheets": [], "book_questions": 0, "priority": []})

    def pair(a: str, b: str) -> dict:
        return ev[(a, b) if data.code_key(a) <= data.code_key(b) else (b, a)]

    for s in data.subtopics():
        for c in s["connections"]:
            if c != s["code"]:
                pair(s["code"], c)["syllabus"] = True
    for q in data.questions():
        for a, b in itertools.combinations(sorted(set(q["part_subtopics"].values())), 2):
            if q["id"] not in pair(a, b)["past"]:
                pair(a, b)["past"].append(q["id"])
    for p in data.book_passages():
        for a, b in itertools.combinations(p["subtopics"], 2):
            e = pair(a, b)
            if p["section"] not in e["passages"]:
                e["passages"].append(p["section"])
    for sh in data.sheets():
        for a, b in itertools.combinations(sh["subtopics"], 2):
            pair(a, b)["sheets"].append(sh["id"])
    for q in data.book_questions():
        for a, b in itertools.combinations(q["subtopics"], 2):
            pair(a, b)["book_questions"] += 1
    for name, codes, _need in progress.CONNECTIONS:
        for a, b in itertools.combinations(sorted(codes), 2):
            pair(a, b)["priority"].append(name)

    def score(e: dict) -> float:
        return 3 * e["syllabus"] + 2 * len(e["past"]) + 2 * len(e["passages"]) + 2 * len(e["sheets"]) + min(e["book_questions"], 4) * 0.5 + (1 if e["priority"] else 0)

    def real(e: dict) -> bool:
        return e["syllabus"] or len(e["past"]) >= 2 or bool(e["passages"]) or bool(e["sheets"]) or (len(e["past"]) == 1 and (e["book_questions"] >= 1 or bool(e["priority"]))) or e["book_questions"] >= 3

    links: dict[str, list] = {s["code"]: [] for s in data.subtopics()}
    matrix: dict[str, dict[str, int]] = {str(t["n"]): {str(u["n"]): 0 for u in data.topics()} for t in data.topics()}
    for (a, b), e in ev.items():
        if not real(e):
            continue
        row = {**e, "score": round(score(e), 1)}
        links[a].append({"code": b, **row})
        links[b].append({"code": a, **row})
        x, y = str(data.topic_of(a)), str(data.topic_of(b))
        if x != y:
            matrix[x][y] += 1
            matrix[y][x] += 1
    for code in links:
        links[code] = sorted(links[code], key=lambda r: (-r["score"], data.code_key(r["code"])))[:KEEP]
    priority = []
    for name, codes, _need in progress.CONNECTIONS:
        qids = [q["id"] for q in data.questions() if name in progress.connections_of(q)]
        sections = sorted({p["section"] for p in data.book_passages() if set(p["subtopics"]) & codes}, key=lambda s: [int(x) for x in s.split(".")])
        priority.append({"name": name, "subtopics": sorted(codes, key=data.code_key), "questions": qids, "sections": sections})
    return {"links": links, "topics": matrix, "priority": priority}


def main() -> None:
    result = build()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=0), encoding="utf-8")
    n = sum(len(v) for v in result["links"].values()) // 2
    cross = sum(1 for k, v in result["links"].items() for r in v if r["code"].split(".")[0] != k.split(".")[0]) // 2
    print(f"{n} links shown ({cross} between different topics); fewest for one sub-topic: {min((len(v), k) for k, v in result['links'].items())}")
    print({p["name"][:28]: len(p["questions"]) for p in result["priority"]})
    print("topics", result["topics"])


if __name__ == "__main__":
    main()
