"""
Macro analysis for Part 3: what the examiners' reports say about each syllabus sub-topic,
aggregated across every session, and joined with the questions/markschemes in the library.

    python -m analysis.macro                 # writes data/reports/macro_by_subtopic.{json,csv}
    python -m analysis.macro --include-paper3

Per sub-topic it computes
  exam_frequency          questions in the library (past papers + markschemes) tagged to it
  examiner_comments       per-question report comments tagged to it, and distinct questions they cover
  mean_pct_correct        mean of the "% correct" figures examiners quoted (MCQ and structured)
  hardest                 the lowest-scoring commented questions (ref, %)
  difficult / well_prepared   bullet-point mentions in the "areas … difficult / well prepared" lists
  difficulty_ratio        difficult / (difficult + well_prepared)
  error_signals           recurring phrases from sentences describing mistakes ("did not", "confused" …)
  error_examples          up to 5 short example sentences with their source ref (evidence for Pillar 2)
  popular_distractors     counts of the most popular wrong MCQ letters examiners named
  sessions                distinct sessions with evidence; first and last year
  priority_score          0–100: rank-average of frequency, low % correct and difficulty ratio

`context_for(sub_topic)` returns a compact dict meant to be dropped into the Part 3 prompt.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHUNKS = ROOT / "data" / "chunks"
OUT_JSON = ROOT / "data" / "reports" / "macro_by_subtopic.json"
OUT_CSV = ROOT / "data" / "reports" / "macro_by_subtopic.csv"
SYLLABUS = ROOT / "data" / "syllabus" / "syllabus.json"

ERROR_CUE = re.compile(
    r"\b(did not|didn't|failed to|unable to|confus\w*|incorrect\w*|wrong\w*|forgot|omitt\w*|missed|"
    r"misconception\w*|common error|common mistake|lost (?:the )?marks?|few candidates|many candidates|"
    r"most candidates|weaker candidates|rarely|struggled|careless|mistak\w*)\b", re.I)
STOP = set("""the and for that this with were was are candidates candidate students student many most few some
their they from which what have been not but very also only more than into when then there these those such
question questions answer answers answered part mark marks gave give given often could would should did does
able unable failed fail incorrect incorrectly correct correctly wrong confused confusion common error errors
mistake mistakes lost missed forgot omitted rarely struggled weaker however although while other others well
good poor quite many majority minority number used using use one two three how why whether""".split())


def _load():
    chunks = []
    for f in sorted(CHUNKS.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


def _sentences(text: str) -> list[str]:
    body = text.split("\n", 1)[1] if text.startswith("[") and "\n" in text else text
    body = re.sub(r"\s+", " ", body)
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(«])", body) if 25 <= len(s.strip()) <= 260]


def _bigrams(sentence: str) -> list[str]:
    toks = [t for t in re.findall(r"[a-z][a-z0-9\-]{2,}", sentence.lower()) if t not in STOP]
    return [f"{a} {b}" for a, b in zip(toks, toks[1:])]


def _rank_pct(values: dict[str, float], reverse: bool = False) -> dict[str, float]:
    """Percentile rank 0–1 (1 = most 'priority'); ties share the average rank."""
    items = sorted(values.items(), key=lambda kv: kv[1], reverse=reverse)
    n = max(1, len(items) - 1)
    return {k: i / n for i, (k, _v) in enumerate(items)}


def build(include_paper3: bool = False) -> dict:
    syl = json.loads(SYLLABUS.read_text(encoding="utf-8"))
    titles = {s["code"]: s["title"] for s in syl["sub_topics"]}
    chunks = _load()

    freq: Counter = Counter()
    seen_q: set = set()
    comments: dict[str, list[dict]] = defaultdict(list)
    findings: dict[str, Counter] = defaultdict(Counter)
    finding_examples: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    sessions: dict[str, set] = defaultdict(set)

    for c in chunks:
        m = c["metadata"]
        st = m.get("sub_topic")
        if not st:
            continue
        stype = m["source_type"]
        if stype in {"past_paper", "markscheme"} and m.get("question_ref") and not m.get("orphan_answer_key"):
            key = (m.get("resolved_ref") or m["question_ref"])
            if key not in seen_q:
                seen_q.add(key)
                freq[st] += 1
        elif stype == "examiner_report":
            if m.get("paper") == "3" and not include_paper3:
                continue
            comments[st].append({"text": c["text"], "meta": m})
            if m.get("session"):
                sessions[st].add(m["session"])
        elif stype == "examiner_finding":
            pol = m.get("polarity")
            findings[st][pol] += 1
            if len(finding_examples[st][pol]) < 8:
                finding_examples[st][pol].append(f"{m.get('session')}: {c['text'].split(': ', 1)[-1][:160]}")
            if m.get("session"):
                sessions[st].add(m["session"])

    rows = {}
    for st in sorted(titles, key=lambda c: (c[0] != "S", c)):
        cm = comments.get(st, [])
        pcts = [(x["meta"].get("resolved_ref") or x["meta"].get("report_question_key"), x["meta"]["pct_correct"])
                for x in cm if x["meta"].get("pct_correct") is not None]
        uniq_pct = {}
        for ref, v in pcts:
            uniq_pct.setdefault(ref, v)
        err_sents = []
        for x in cm:
            ref = x["meta"].get("resolved_ref") or x["meta"].get("report_question_key")
            for s in _sentences(x["text"]):
                if ERROR_CUE.search(s):
                    err_sents.append((ref, s))
        grams = Counter(g for _r, s in err_sents for g in set(_bigrams(s)))
        # examples: prefer recent sessions and sentences that contain a top signal
        top = [g for g, n in grams.most_common(12) if n >= 2]
        examples = []
        for ref, s in sorted(err_sents, key=lambda rs: rs[0] or "", reverse=True):
            if any(g in " ".join(_bigrams(s)) for g in top[:6]) and len(examples) < 5:
                examples.append({"ref": ref, "sentence": s[:220]})
        distract = Counter(x["meta"]["popular_distractor"] for x in cm if x["meta"].get("popular_distractor"))
        diff, well = findings[st].get("difficult", 0), findings[st].get("well_prepared", 0)
        years = sorted(int(s.split()[-1]) for s in sessions.get(st, []))
        rows[st] = {
            "sub_topic": st,
            "title": titles[st],
            "exam_frequency": freq.get(st, 0),
            "examiner_comments": len(cm),
            "questions_commented": len({x["meta"].get("report_question_key") for x in cm}),
            "comments_2025_syllabus": sum(1 for x in cm if x["meta"].get("syllabus_era") == "2025"),
            "pct_correct_n": len(uniq_pct),
            "mean_pct_correct": round(statistics.mean(uniq_pct.values()), 1) if uniq_pct else None,
            "hardest": [{"ref": r, "pct_correct": v} for r, v in sorted(uniq_pct.items(), key=lambda kv: kv[1])[:5]],
            "difficult_mentions": diff,
            "well_prepared_mentions": well,
            "difficulty_ratio": round(diff / (diff + well), 2) if (diff + well) else None,
            "difficult_examples": finding_examples[st].get("difficult", [])[:5],
            "well_prepared_examples": finding_examples[st].get("well_prepared", [])[:3],
            "error_signals": [{"phrase": g, "n": n} for g, n in grams.most_common(10) if n >= 2],
            "error_examples": examples,
            "popular_distractors": dict(distract),
            "sessions": len(sessions.get(st, [])),
            "first_year": years[0] if years else None,
            "last_year": years[-1] if years else None,
        }

    # priority: average percentile of (frequency ↑, mean % correct ↓, difficulty ratio ↑);
    # missing metrics fall back to the median so thin evidence doesn't dominate
    def fill(key, default):
        vals = {k: v[key] for k, v in rows.items() if v[key] is not None}
        med = statistics.median(vals.values()) if vals else default
        return {k: (v[key] if v[key] is not None else med) for k, v in rows.items()}
    f_rank = _rank_pct({k: v["exam_frequency"] for k, v in rows.items()})
    p_rank = _rank_pct(fill("mean_pct_correct", 60.0), reverse=True)        # lower % → higher priority
    d_rank = _rank_pct(fill("difficulty_ratio", 0.5))
    for k, v in rows.items():
        v["priority_score"] = round(100 * (f_rank[k] + p_rank[k] + d_rank[k]) / 3)

    return {
        "generated_from": sorted(p.name for p in CHUNKS.glob("*.jsonl")),
        "include_paper3": include_paper3,
        "notes": [
            "Examiner comments cover selected questions only (often the hardest), so % correct is biased low.",
            "Sub-topic tags on report comments come from the question they are linked to when possible, "
            "otherwise from the classifier (keyword fallback in offline runs).",
            "Pre-2025 sessions were examined on the old syllabus; mapping to 2025 sub-topics is by content.",
        ],
        "sub_topics": rows,
    }


def write(result: dict) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    cols = ["sub_topic", "title", "priority_score", "exam_frequency", "examiner_comments", "questions_commented",
            "comments_2025_syllabus", "pct_correct_n", "mean_pct_correct", "difficult_mentions",
            "well_prepared_mentions", "difficulty_ratio", "sessions", "first_year", "last_year",
            "top_error_signals", "hardest_questions"]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(result["sub_topics"].values(), key=lambda r: -r["priority_score"]):
            w.writerow({**{c: r.get(c) for c in cols if c in r},
                        "top_error_signals": "; ".join(e["phrase"] for e in r["error_signals"][:5]),
                        "hardest_questions": "; ".join(f"{h['ref']} ({h['pct_correct']:g}%)" for h in r["hardest"][:3])})


def context_for(sub_topic: str, path: Path = OUT_JSON) -> dict:
    """Compact evidence block for the Part 3 prompt (Pillars 1, 2 and 7)."""
    r = json.loads(path.read_text(encoding="utf-8"))["sub_topics"][sub_topic]
    return {k: r[k] for k in ("sub_topic", "title", "priority_score", "exam_frequency", "mean_pct_correct",
                              "difficulty_ratio", "hardest", "error_signals", "error_examples",
                              "difficult_examples", "popular_distractors")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-paper3", action="store_true",
                    help="include old-syllabus Paper 3 (options) comments; off by default")
    res = build(include_paper3=ap.parse_args().include_paper3)
    write(res)
    top = sorted(res["sub_topics"].values(), key=lambda r: -r["priority_score"])[:8]
    for r in top:
        print(f"{r['sub_topic']:5} {r['priority_score']:>3}  freq={r['exam_frequency']:<4} "
              f"comments={r['examiner_comments']:<4} mean%={r['mean_pct_correct']}  diff_ratio={r['difficulty_ratio']}")
    print(f"wrote {OUT_JSON} and {OUT_CSV}")


if __name__ == "__main__":
    main()
