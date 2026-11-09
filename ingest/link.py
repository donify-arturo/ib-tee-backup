"""
Cross-document linking:

* past-paper question  <->  markscheme       (canonical QRef key; QB + official)
* textbook section     <->  textbook answers (printed page numbers)
* markscheme inherits sub-topic tags from its question after classification

Also produces the "missing markschemes" queue that Part 3 consumes instead of
interrupting the student on every card.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .chunking import Chunk


def link_questions_to_markschemes(chunks: list[Chunk]) -> dict:
    ms_by_ref: dict[str, list[Chunk]] = defaultdict(list)
    q_by_ref: dict[str, list[Chunk]] = defaultdict(list)
    for c in chunks:
        ref = c.metadata.get("question_ref")
        if not ref:
            continue
        if c.metadata["source_type"] == "markscheme":
            ms_by_ref[ref].append(c)
        elif c.metadata["source_type"] == "past_paper":
            q_by_ref[ref].append(c)

    for ref, qs in q_by_ref.items():
        ms = ms_by_ref.get(ref, [])
        for q in qs:
            q.metadata["has_markscheme"] = bool(ms)
            q.metadata["linked_ids"] = sorted({*q.metadata["linked_ids"], *(m.id for m in ms)})
            q.metadata["markscheme_origins"] = sorted({m.metadata.get("markscheme_origin") or "" for m in ms} - {""})
        for m in ms:
            m.metadata["linked_ids"] = sorted({*m.metadata["linked_ids"], *(q.id for q in qs)})
            m.metadata["has_question"] = True
    for ref, ms in ms_by_ref.items():
        if ref not in q_by_ref:
            for m in ms:
                m.metadata["has_question"] = False

    return {
        "questions": len(q_by_ref),
        "questions_with_markscheme": sum(1 for r in q_by_ref if r in ms_by_ref),
        "markschemes": len(ms_by_ref),
        "markschemes_without_question": sum(1 for r in ms_by_ref if r not in q_by_ref),
    }


def _shingles(text: str) -> set[str]:
    import re
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(toks[i:i + 3]) for i in range(len(toks) - 2)}


def link_by_content(chunks: list[Chunk], threshold: float = 0.35) -> dict[str, str]:
    """Second pass for questions whose ref didn't match because the variant label differs
    (question bank says "May 2025 · TZ3"; the official PDF only has paper code 6221).
    Compare against official question-paper chunks with the same session/paper/level/number
    and adopt the best-overlapping variant's markscheme. Returns learned aliases {TZ3: 6221}."""
    official_q = defaultdict(list)
    ms_by_ref = defaultdict(list)
    for c in chunks:
        m = c.metadata
        if m["source_type"] == "past_paper" and m.get("paper_code"):
            sess, paper, level, _v, q = m["question_ref"].split(".")
            official_q[(sess, paper, level, q)].append(c)
        elif m["source_type"] == "markscheme" and m.get("question_ref"):
            ms_by_ref[m["question_ref"]].append(c)
    aliases: dict[str, str] = {}
    for c in chunks:
        m = c.metadata
        if m["source_type"] != "past_paper" or m.get("has_markscheme") or m.get("paper_code"):
            continue
        sess, paper, level, variant, q = m["question_ref"].split(".")
        cands = official_q.get((sess, paper, level, q), [])
        if not cands:
            continue
        mine = _shingles(c.text)
        scored = sorted(((len(mine & _shingles(o.text)) / max(1, len(mine | _shingles(o.text))), o)
                         for o in cands), key=lambda x: -x[0])
        score, best = scored[0]
        if score < threshold:
            continue
        ms = ms_by_ref.get(best.metadata["question_ref"], [])
        if not ms:
            continue
        aliases[f"{sess}.{paper}.{level}.{variant}"] = best.metadata["variant"]
        m["has_markscheme"] = True
        m["linked_ids"] = sorted({*m["linked_ids"], *(x.id for x in ms), best.id})
        m["markscheme_origins"] = ["ib_official"]
        m["content_link_score"] = round(score, 2)
        for x in ms:
            x.metadata["linked_ids"] = sorted({*x.metadata["linked_ids"], c.id})
    return aliases


def link_textbook_answers(chunks: list[Chunk]) -> int:
    by_page: dict[str, list[Chunk]] = defaultdict(list)
    for c in chunks:
        if c.metadata["source_type"] == "textbook":
            for p in c.metadata.get("printed_pages") or []:
                by_page[p].append(c)
    n = 0
    for a in chunks:
        if a.metadata["source_type"] != "textbook_answers":
            continue
        targets = {t.id: t for p in a.metadata.get("answers_for_printed_pages", []) for t in by_page.get(p, [])}
        for t in targets.values():
            t.metadata["linked_ids"] = sorted({*t.metadata["linked_ids"], a.id})
            t.metadata["has_markscheme"] = True          # textbook-answer key (not an IB markscheme)
            a.metadata["linked_ids"] = sorted({*a.metadata["linked_ids"], t.id})
            if not a.metadata.get("sub_topic") and t.metadata.get("sub_topic"):
                a.metadata["sub_topic"] = t.metadata["sub_topic"]
            n += 1
    return n


def propagate_tags(chunks: list[Chunk]) -> int:
    """Markschemes (and question parts) take the tags of their linked question."""
    by_id = {c.id: c for c in chunks}
    n = 0
    for c in chunks:
        if c.metadata["source_type"] != "markscheme" or c.metadata.get("sub_topic"):
            continue
        for lid in c.metadata["linked_ids"]:
            q = by_id.get(lid)
            if q and q.metadata.get("sub_topic"):
                for k in ("sub_topic", "understanding", "theme", "sub_topics_all", "tag_confidence"):
                    c.metadata[k] = q.metadata.get(k)
                c.metadata["tag_method"] = "ref_link"
                n += 1
                break
    return n


def write_missing_markschemes(chunks: list[Chunk], path: Path) -> int:
    rows = {}
    for c in chunks:
        m = c.metadata
        if m["source_type"] == "past_paper" and not m.get("has_markscheme"):
            rows[m["question_ref"]] = {
                "question_ref": m["question_ref"], "session": m["session"], "paper": m["paper"],
                "level": m["level"], "variant": m["variant"], "sub_topic": m.get("sub_topic") or "",
                "syllabus_era": m.get("syllabus_era"), "doc_id": m["doc_id"], "page": m["page_start"],
            }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["question_ref", "session", "paper", "level", "variant",
                                          "sub_topic", "syllabus_era", "doc_id", "page"])
        w.writeheader()
        for r in sorted(rows.values(), key=lambda r: (r["sub_topic"], r["question_ref"])):
            w.writerow(r)
    return len(rows)


# --------------------------------------------------------------------------- #
# Examiner (subject) reports  <->  questions / markschemes
# --------------------------------------------------------------------------- #
def _content_tokens(text: str) -> set[str]:
    import re
    stop = {"the", "and", "for", "that", "this", "with", "were", "was", "candidates", "students", "many",
            "most", "question", "answer", "answers", "correct", "correctly", "able", "some", "their", "they",
            "from", "which", "what", "have", "been", "not", "but", "very", "few", "well", "part", "mark",
            "marks", "gave", "give", "given", "often", "also", "only", "more", "than", "into", "when"}
    return {t for t in re.findall(r"[a-z][a-z0-9\-]{2,}", text.lower()) if t not in stop}


def learn_report_variant_aliases(chunks: list[Chunk], seed: dict[str, str] | None = None) -> dict[str, str]:
    """Reports label May-2025 variants TZ1/TZ2/TZ3; the official PDFs only carry paper codes
    (6209/6215/6221 …). Score every (report TZ, paper code) pair by MCQ-letter agreement and by
    vocabulary overlap between the report's comment and the official question, then assign
    greedily one code per TZ. `seed` holds aliases already learned elsewhere (link_by_content)."""
    seed = dict(seed or {})
    groups: dict[tuple, list[Chunk]] = defaultdict(list)
    for c in chunks:
        m = c.metadata
        if m["source_type"] == "examiner_report" and m.get("question_ref"):
            sess, paper, level, variant, _q = m["question_ref"].split(".")
            groups[(sess, paper, level, variant)].append(c)
    official_q: dict[tuple, dict[str, dict[int, Chunk]]] = defaultdict(lambda: defaultdict(dict))
    official_ms: dict[tuple, dict[str, dict[int, str]]] = defaultdict(lambda: defaultdict(dict))
    for c in chunks:
        m = c.metadata
        if not m.get("paper_code") or not m.get("question_ref"):
            continue
        sess, paper, level, code, q = m["question_ref"].split(".")
        if code.startswith("TZ"):
            continue
        if m["source_type"] == "past_paper" and not m.get("question_part") or m.get("question_part") == "part1":
            official_q[(sess, paper, level)][code][int(q)] = c
        if m["source_type"] == "markscheme" and m.get("mcq_answer"):
            official_ms[(sess, paper, level)][code][int(q)] = m["mcq_answer"]

    aliases = dict(seed)
    confidence: dict[str, str] = {k: "high" for k in seed}
    for spl in {(s, p, l) for (s, p, l, _v) in groups}:
        codes = set(official_q.get(spl, {})) | set(official_ms.get(spl, {}))
        if not codes:
            continue
        taken = {aliases[f"{spl[0]}.{spl[1]}.{spl[2]}.{v}"] for (s, p, l, v) in groups
                 if (s, p, l) == spl and f"{s}.{p}.{l}.{v}" in aliases}
        scores = []
        for (s, p, l, v), reps in groups.items():
            if (s, p, l) != spl or f"{s}.{p}.{l}.{v}" in aliases:
                continue
            for code in codes - taken:
                score = 0.0
                for r in reps:
                    qn = int(r.metadata["question_ref"].split(".")[-1])
                    letter = r.metadata.get("report_answer")
                    key = official_ms.get(spl, {}).get(code, {}).get(qn)
                    if letter and key:
                        score += 3.0 if letter == key else -3.0
                    oq = official_q.get(spl, {}).get(code, {}).get(qn)
                    if oq is not None:
                        a, b = _content_tokens(r.text), _content_tokens(oq.text)
                        if a and b:
                            score += 10.0 * len(a & b) / len(a | b)
                scores.append((score, f"{s}.{p}.{l}.{v}", code))
        by_grp: dict[str, list[float]] = defaultdict(list)
        for score, grp, _code in scores:
            by_grp[grp].append(score)
        for score, grp, code in sorted(scores, reverse=True):
            if score <= 0.5 or grp in aliases or code in taken:
                continue
            aliases[grp] = code
            taken.add(code)
            others = sorted(by_grp[grp], reverse=True)[1:2]
            # best must clearly beat the runner-up, otherwise the join is kept but flagged
            confidence[grp] = "high" if not others or score >= 1.3 * max(others[0], 0.01) else "low"
    aliases["_confidence"] = confidence           # type: ignore[assignment]
    return aliases


def link_examiner_reports(chunks: list[Chunk], aliases: dict[str, str]) -> dict:
    """Join report comments to questions and markschemes by canonical ref (+ learned aliases).
    Copies the report's statistics onto the question so Part 3 can rank by difficulty."""
    by_ref: dict[str, list[Chunk]] = defaultdict(list)
    for c in chunks:
        m = c.metadata
        if m["source_type"] in {"past_paper", "markscheme"} and m.get("question_ref"):
            by_ref[m["question_ref"]].append(c)
    stats = {"report_comments": 0, "linked_to_question": 0, "linked_to_markscheme_only": 0,
             "answer_conflicts": 0}
    linked_q_refs = set()
    for r in chunks:
        m = r.metadata
        if m["source_type"] != "examiner_report":
            continue
        stats["report_comments"] += 1
        ref = m.get("question_ref")
        if not ref:
            continue
        sess, paper, level, variant, q = ref.split(".")
        targets = list(by_ref.get(ref, []))
        grp = f"{sess}.{paper}.{level}.{variant}"
        alias = aliases.get(grp)
        if alias:
            targets += by_ref.get(f"{sess}.{paper}.{level}.{alias}.{q}", [])
            m["resolved_ref"] = f"{sess}.{paper}.{level}.{alias}.{q}"
            m["alias_confidence"] = aliases.get("_confidence", {}).get(grp, "high")
        if not targets:
            continue
        kinds = {t.metadata["source_type"] for t in targets}
        stats["linked_to_question" if "past_paper" in kinds else "linked_to_markscheme_only"] += 1
        for t in targets:
            tm = t.metadata
            tm["linked_ids"] = sorted({*tm["linked_ids"], r.id})
            tm["has_examiner_report"] = True
            for k in ("pct_correct", "report_answer", "popular_distractor"):
                if k in m and k not in tm:
                    tm[k] = m[k]
            if tm.get("mcq_answer") and m.get("report_answer") and tm["mcq_answer"] != m["report_answer"]:
                tm["report_answer_conflict"] = True
                stats["answer_conflicts"] += 1
            if tm["source_type"] == "past_paper":
                linked_q_refs.add(tm["question_ref"])
        m["linked_ids"] = sorted({*m["linked_ids"], *(t.id for t in targets)})
        m["has_question"] = "past_paper" in kinds
        m["has_markscheme"] = "markscheme" in kinds
    stats["questions_with_report"] = len(linked_q_refs)
    return stats


def propagate_report_tags(chunks: list[Chunk]) -> int:
    """Examiner comments take the sub-topic of the question/markscheme they discuss."""
    by_id = {c.id: c for c in chunks}
    n = 0
    for c in chunks:
        m = c.metadata
        if m["source_type"] != "examiner_report" or m.get("sub_topic"):
            continue
        for lid in m["linked_ids"]:
            t = by_id.get(lid)
            if t is not None and t.metadata.get("sub_topic"):
                for k in ("sub_topic", "understanding", "theme", "sub_topics_all", "tag_confidence", "legacy_only"):
                    m[k] = t.metadata.get(k)
                m["tag_method"] = "ref_link"
                n += 1
                break
    return n
