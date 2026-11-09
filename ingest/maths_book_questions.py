"""
The course book, saved in separate sets: exercise questions paired with worked answers → data/maths/book_questions.json;
investigations, inquiry boxes, examples, chapter reviews → book_investigations.json; the teaching notes → book_notes.json.

    python -m ingest.maths_book_questions

Stores only where each question and answer is on the PDF pages: the app shows them as crops of the student's own copy and never
retypes them. Private study only. An exercise whose question numbers don't run 1, 2, 3 … is left out and listed in the report (the app
keeps showing it as whole pages), so a bad split can never show the wrong answer under a question.

The book prints exercises in columns whose positions vary from page to page. Question numbers are digits of a fixed size that start a
line. A question ends at the next number below it in its column, and text above a column's first number continues the question before
it. An exercise is rejected if its worked answers go further than the questions found (it was cut short). Sub-topics: the section's,
narrowed by the keyword rules.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "maths" / "book_questions.json"
FEATURES = ROOT / "data" / "maths" / "book_investigations.json"     # investigations, Developing inquiry, worked examples, chapter reviews
NOTES = ROOT / "data" / "maths" / "book_notes.json"                 # the book's own teaching text per section, unabridged; the app shows the real pages
NUMBER_SIZE = (17.9, 18.6)
COLUMN = 369.8                  # distance between the two columns' question numbers
LEFT = {0: 65.9, 1: 131.7}      # the left column's numbers on even / odd PDF pages
TOP_MARGIN, BOTTOM_MARGIN = 72, 1140


def words(pdf, cache: dict, page: int) -> list[dict]:
    if page not in cache:
        cache[page] = pdf.pages[page].extract_words(extra_attrs=["fontname", "size"])
    return cache[page]


def body(ws: list[dict], left: float) -> list[dict]:
    """The page's text without the running head and the vertical tab in the outer margin."""
    return [w for w in ws if TOP_MARGIN < w["top"] < BOTTOM_MARGIN and left - 16 <= w["x0"] <= left + 742]


def heading_top(ws: list[dict], name: str, min_size: float = 18.5) -> float | None:
    """Where the heading "Exercise 7E" is, if it is on this page as a heading rather than a mention in the text."""
    for a, b in zip(ws, ws[1:]):
        if a["text"] == "Exercise" and b["text"].rstrip(".:") == name and a["size"] >= min_size:
            return a["top"]
    return None


def is_stop(w: list[dict], i: int, name: str) -> bool:
    """Does a heading that ends the exercise start at word i? (Big brackets and sigmas in formulas are as large as headings.)"""
    x = w[i]
    letters = sum(c.isalpha() for c in x["text"])
    if x["size"] >= 23.5 and letters >= 3 and "Symbol" not in x["fontname"]:
        return True
    following = " ".join(y["text"] for y in w[i:i + 3])
    return bool(x["size"] >= 18.5 and re.match(r"(Developing inquiry|Investigation|Chapter review|Exercise\d+[A-Z])", following) and not following.startswith(f"Exercise {name}"))


def exercise_extent(pdf, cache: dict, name: str, pages: list[int]) -> tuple[list[tuple[int, float, float]], float] | None:
    """[(page, top, bottom)] the exercise occupies, or None if its heading can't be found."""
    start = next(((p, t) for p in pages if (t := heading_top(words(pdf, cache, p), name)) is not None), None)
    if not start:
        return None
    out = []
    for p in pages[pages.index(start[0]):]:
        ws = sorted(body(words(pdf, cache, p), LEFT[p % 2]), key=lambda w: (round(w["top"] / 3), w["x0"]))
        top = start[1] + 26 if p == start[0] else TOP_MARGIN
        stop = next((w["top"] for i, w in enumerate(ws) if w["top"] > top and is_stop(ws, i, name)), None)
        out.append((p, top, (stop - 4) if stop else BOTTOM_MARGIN))
        if stop:
            break
    return out


def candidates(ws: list[dict], top: float, bottom: float) -> list[dict]:
    """Words that could be a question number: a whole number of the right size that starts its line."""
    out = []
    for w in ws:
        if NUMBER_SIZE[0] <= w["size"] <= NUMBER_SIZE[1] and w["text"].isdigit() and top <= w["top"] <= bottom:
            if not any(abs(o["top"] - w["top"]) < 7 and 0 <= w["x0"] - o["x1"] < 4 for o in ws if o is not w):       # the gap between columns is wider
                out.append(w)
    return out


def end_of_question(page, ws: list[dict], x0: float, x1: float, top: float, bottom: float) -> float:
    """Where a question with no number below it ends. The book's diagrams are part of a full-page picture, so this looks at the rendered
    page: follow what is printed downwards, and stop at a large empty space or at a coloured rule across the column after a gap."""
    import numpy as np
    from PIL import Image

    from maths import render
    path = render.page_png("book", page.page_number - 1)
    img = np.asarray(Image.open(path).convert("RGB"))
    scale = img.shape[1] / float(page.width)
    area = img[int(top * scale):int(bottom * scale), int((x0 + 4) * scale):int((x1 - 24) * scale)]     # not the coloured bar at the page edge
    if not area.size:
        return top
    filled = (area.min(axis=2) < 235).mean(axis=1)
    last, blank = 0, 0
    for row, f in enumerate(filled):
        if f > 0.002:
            if blank > 110 * scale or (f >= 0.98 and blank >= 18 * scale):
                break
            last, blank = row, 0
        else:
            blank += 1
    return top + last / scale


def split_book(pdf, cache: dict, name: str, pages: list[int]) -> tuple[dict[int, list], list[str]]:
    """{question number: [[page, top, bottom, x0, x1], ...]} for one exercise."""
    extent = exercise_extent(pdf, cache, name, pages)
    if not extent:
        return {}, ["heading not found"]
    found: list[dict] = []
    expected = 1
    for p, top, bottom in extent:
        ws = body(words(pdf, cache, p), LEFT[p % 2])
        cand = candidates(ws, top - 3, bottom)
        while True:
            known = [f["x"] for f in found if f["p"] == p]
            hit = sorted((w for w in cand if int(w["text"]) == expected), key=lambda w: (not any(abs(w["x0"] - x) < 6 for x in known), round(w["x0"] / 20), w["top"]))
            if not hit:
                break
            found.append({"p": p, "x": hit[0]["x0"], "t": hit[0]["top"], "n": expected})
            expected += 1
    if not found:
        return {}, ["no question numbers found"]
    limits = {p: (top, bottom) for p, top, bottom in extent}
    out: dict[int, list] = {f["n"]: [] for f in found}

    def band(p: int, x: float) -> tuple[float, float]:
        """The column a number at x belongs to: from just left of it to the next column, or the edge of the text."""
        right_edge = LEFT[p % 2] + 738
        others = [f["x"] for f in found if f["p"] == p and f["x"] > x + 200]
        if others:
            return x - 8, min(others) - 12
        if x > LEFT[p % 2] + 200:
            return x - 8, right_edge
        return x - 8, x + COLUMN - 12

    for f in found:
        p, x, t = f["p"], f["x"], f["t"]
        lo, hi = limits[p]
        x0, x1 = band(p, x)
        below = [g["t"] for g in found if g["p"] == p and abs(g["x"] - x) < 30 and g["t"] > t]
        ws = [w for w in body(words(pdf, cache, p), LEFT[p % 2]) if t - 3 <= w["top"] <= (min(below) if below else hi) and x0 <= w["x0"] < x1 + 20]
        if x <= LEFT[p % 2] + 200 and any(w["x0"] < x1 and w["x1"] > x1 + 20 for w in ws):       # a question printed across both columns
            x1 = LEFT[p % 2] + 738
            below = [g["t"] for g in found if g["p"] == p and g["t"] > t]
        end = min(below) - 5 if below else None
        if end is None:
            end = min(hi, end_of_question(pdf.pages[p], ws, x0, x1, t - 3, hi) + 3)
        out[f["n"]].append([p, round(t - 3, 1), round(end, 1), round(x0, 1), round(x1, 1)])

    # text above a column's first number, and whole columns with no number, continue the question before them
    last_page = max(f["p"] for f in found)
    for p, lo, hi in extent:
        here = [f for f in found if f["p"] == p]
        left = LEFT[p % 2]
        positions: list[float] = []
        for f in sorted(here, key=lambda f: f["x"]):
            if not any(abs(f["x"] - y) < 30 for y in positions):
                positions.append(f["x"])
        if not any(y < left + 200 for y in positions):
            positions.append(left)
        if not any(y > left + 200 for y in positions):
            positions.append(left + COLUMN)
        for x in sorted(positions):
            x0, x1 = band(p, x) if any(abs(f["x"] - x) < 30 for f in here) else (x - 8, x + COLUMN - 12 if x < left + 200 else left + 738)
            mine = [f for f in here if abs(f["x"] - x) < 30]
            first = min(mine, key=lambda f: f["t"]) if mine else None
            top_limit = first["t"] - 5 if first else hi
            ws = [w for w in body(words(pdf, cache, p), left) if lo <= w["top"] <= top_limit and x0 <= w["x0"] < x1]
            if len(ws) < 3:
                continue
            if first:
                owner = first["n"] - 1
            else:
                earlier_col = [f["n"] for f in here if f["x"] < x - 200]
                owner = max(earlier_col) if earlier_col else max((f["n"] for f in found if f["p"] < p), default=0)
            if owner not in out or not out[owner]:
                continue
            tail = out[owner][-1]
            if tail[2] < limits[tail[0]][1] - 100 or (tail[0] == p and tail[4] - tail[3] > 500):     # it had already ended
                continue
            if p > last_page:                                  # after the last number only the question's own lettered parts may follow
                head = min(ws, key=lambda w: (round(w["top"] / 3), w["x0"]))
                if not (NUMBER_SIZE[0] <= head["size"] <= NUMBER_SIZE[1] and re.fullmatch(r"[a-h]|i{1,3}", head["text"])):
                    continue
            start = min(w["top"] for w in ws) - 3
            end = min(top_limit, end_of_question(pdf.pages[p], ws, x0, x1, start, top_limit) + 3)
            out[owner].append([p, round(start, 1), round(end, 1), round(x0, 1), round(x1, 1)])
    return out, []


def answer_page_end(pdf, cache: dict, page: int) -> float:
    """Just above the copyright line at the foot of a worked-solutions page."""
    return min((w["top"] for w in words(pdf, cache, page) if w["text"] == "©"), default=float(pdf.pages[page].height) - 50) - 6


def split_answers(pdf, cache: dict, name: str, pages: list[int]) -> dict[int, list]:
    """{question number: [[page, top, bottom], ...]} in the worked solutions: one column, numbers bold at the left margin."""
    found, on = [], False
    expected_next = 1
    end = None
    for p in pages:
        ws = sorted(words(pdf, cache, p), key=lambda w: (round(w["top"] / 3), w["x0"]))
        for i, w in enumerate(ws):
            if w["text"] == "Exercise" and i + 1 < len(ws) and re.fullmatch(r"\d+[A-Z]", ws[i + 1]["text"].rstrip(".:")):
                if ws[i + 1]["text"].rstrip(".:") == name:
                    on = True
                    found = []
                    expected_next = 1
                elif on:
                    end = (p, w["top"])
                    break
            if on and w["text"] in ("Chapter", "Review", "Exam") and "Bold" in w["fontname"] and w["x0"] < 100:
                end = (p, w["top"])
                break
            if on and "Bold" in w["fontname"] and w["x0"] < 100 and w["text"].rstrip(".").isdigit() and int(w["text"].rstrip(".")) >= expected_next:
                value = int(w["text"].rstrip("."))
                if value - expected_next <= 3:
                    found.append((p, w["top"], value))
                    expected_next = value + 1
        if end:
            break
    out: dict[int, list] = {}
    page_list = [p for p in pages]
    for k, (p, t, value) in enumerate(found):
        stop = found[k + 1][:2] if k + 1 < len(found) else (end or (page_list[-1], answer_page_end(pdf, cache, page_list[-1])))
        spans = []
        for pg in page_list[page_list.index(p):page_list.index(stop[0]) + 1]:
            a = t - 3 if pg == p else 40
            b = min(stop[1] - 4, answer_page_end(pdf, cache, pg)) if pg == stop[0] else answer_page_end(pdf, cache, pg)
            if b - a > 8:
                spans.append([pg, round(a, 1), round(b, 1)])
        out[value] = spans
    return out


def tags(pdf, cache: dict, spans: list, section: dict, score_fn) -> list[str]:
    """The section's sub-topics, narrowed to those the question's own words point to."""
    text = " ".join(w["text"] for s in spans for w in words(pdf, cache, s[0]) if s[1] <= w["top"] <= s[2] and s[3] <= w["x0"] <= s[4])
    allowed = section["subtopics"]
    if len(allowed) <= 1:
        return allowed
    sc = score_fn(text, text)
    ranked = sorted(((sc.get(c, 0), c) for c in allowed), reverse=True)
    top = ranked[0][0]
    return [c for v, c in ranked if v >= max(2, top * 0.6)] or allowed


def is_heading(w: list[dict], i: int) -> bool:
    x = w[i]
    letters = sum(c.isalpha() for c in x["text"])
    following = w[i + 1]["text"] if i + 1 < len(w) else ""
    return bool((x["size"] >= 23.5 and letters >= 3 and "Symbol" not in x["fontname"]) or (x["text"] == "Exercise" and x["size"] >= 18.5 and re.fullmatch(r"\d+[A-Z]", following.rstrip(".:"))))


def features_of(pdf, cache: dict, chapter: dict, sections: list[dict]) -> tuple[list[dict], dict | None]:
    """Investigations, Developing inquiry boxes and worked examples of a chapter (each from its heading to the next heading, at most
    four pages), and the page where its Chapter review starts."""
    found, review = [], None
    pages = range(chapter["pdf_start"], chapter["pdf_end"] + 1)
    heads = {}
    for p in pages:
        ws = sorted(body(words(pdf, cache, p), LEFT[p % 2]), key=lambda w: (round(w["top"] / 3), w["x0"]))
        heads[p] = [(w["top"], i) for i, w in enumerate(ws) if is_heading(ws, i)]
        for i, w in enumerate(ws):
            nxt = ws[i + 1]["text"] if i + 1 < len(ws) else ""
            if w["text"] == "Chapter" and nxt == "review" and w["size"] >= 30 and review is None:
                review = {"page": p, "top": w["top"]}
            kind = ("investigation" if w["text"] == "Investigation" and w["size"] >= 24 and nxt.isdigit() else
                    "example" if w["text"] == "Example" and w["size"] >= 24 and nxt.isdigit() else
                    "inquiry" if w["text"] == "Developing" and nxt == "inquiry" and w["size"] >= 30 else None)
            if kind:
                found.append({"kind": kind, "page": p, "top": w["top"], "number": int(nxt) if nxt.isdigit() else None})
    out = []
    counts: dict[str, int] = {}
    for f in found:
        p, top = f["page"], f["top"]
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
        spans = []
        for pg in range(p, min(p + 4, chapter["pdf_end"] + 1)):
            lo = top - 3 if pg == p else TOP_MARGIN
            stop = next((t for t, _i in heads.get(pg, []) if t > (top + 12 if pg == p else TOP_MARGIN)), None)
            left = LEFT[pg % 2]
            band_words = [w for w in body(words(pdf, cache, pg), left) if lo <= w["top"] <= (stop or BOTTOM_MARGIN)]
            if band_words:
                bottom = (stop - 4) if stop else min(BOTTOM_MARGIN, max(w["bottom"] for w in band_words) + 6)
                spans.append([pg, round(lo, 1), round(bottom, 1), round(left - 16, 1), round(left + 742, 1)])
            if stop:
                break
        section = next((s_ for s_ in reversed(sections) if s_["pdf_start"] <= p), sections[0] if sections else None)
        n = f["number"] or counts[f["kind"]]
        prefix = {"investigation": "Inv", "example": "Ex", "inquiry": "Inq"}[f["kind"]]
        out.append({"id": f"{chapter['n']}.{prefix}{n}", "kind": f["kind"], "number": n, "chapter": chapter["n"], "section": section["code"] if section else None,
                    "subtopics": section["subtopics"] if section else [], "spans": spans})
    return out, review


def review_answers(pdf, doc_key: str, ws_chapter: dict) -> list[int]:
    """The worked-solutions pages of a chapter's review, if the file has one."""
    for p in range(ws_chapter["first_page"], ws_chapter["last_page"] + 1):
        ws = pdf.pages[p].extract_words(extra_attrs=["fontname"])
        for a_, b_ in zip(ws, ws[1:]):
            if a_["text"] == "Chapter" and b_["text"].lower().startswith("review") and "Bold" in a_["fontname"]:
                return list(range(p, ws_chapter["last_page"] + 1))
    return []


def notes_text(pdf, cache: dict, section: dict, skip: dict[int, list]) -> str:
    """The section's own text in full, not summarised, side notes, examples and investigations included; only the exercise questions are left out."""
    lines = []
    for p in range(section["pdf_start"], section["pdf_end"] + 1):
        ws = [w for w in words(pdf, cache, p) if TOP_MARGIN < w["top"] < BOTTOM_MARGIN and 45 < w["x0"] < 868        # side notes included
              and not any(top <= w["top"] <= bottom and left <= w["x0"] <= right for top, bottom, left, right in skip.get(p, []))]
        rows: dict[int, list] = {}
        for w in ws:
            rows.setdefault(round(w["top"] / 4), []).append(w)
        lines += [" ".join(x["text"] for x in sorted(v, key=lambda x: x["x0"])) for _k, v in sorted(rows.items())]
    return "\n".join(lines)


def build() -> dict:
    import pdfplumber

    from ingest.maths_tagging import scores
    from maths import data, render
    docs = render.documents()
    questions, problems, done, partial = [], {}, 0, []
    book_cache: dict = {}
    ws_cache: dict[str, dict] = {}
    ws_open: dict[str, object] = {}
    with pdfplumber.open(str(docs["book"])) as book:
        for section in data.book().get("sections", []):
            for name in section["exercises"]:
                book_pages, ws_pages, ws_doc = data.exercise_pages(name)
                # the last question can run past the page where the next exercise is first mentioned
                pages = book_pages + ([book_pages[-1] + 1] if book_pages[-1] + 1 < len(book.pages) else [])
                spans, why = split_book(book, book_cache, name, pages)
                if why:
                    problems[name] = why[0]
                    continue
                answers: dict[int, list] = {}
                if ws_doc and ws_pages:
                    if ws_doc not in ws_open:
                        ws_open[ws_doc] = pdfplumber.open(str(docs[ws_doc]))
                        ws_cache[ws_doc] = {}
                    answers = split_answers(ws_open[ws_doc], ws_cache[ws_doc], name, ws_pages)
                missing = [n for n in spans if n not in answers]
                if answers and max(answers) > max(spans):
                    problems[name] = f"cut short: {max(spans)} questions found but answers go to {max(answers)}"
                    continue
                if len(missing) > len(spans) / 2:
                    problems[name] = f"worked answers matched for only {len(spans) - len(missing)} of {len(spans)}"
                    continue
                if missing:
                    partial.append(f"{name}: no worked answer found for {missing}")
                done += 1
                for n, sp in spans.items():
                    questions.append({"id": f"{name}.{n}", "exercise": name, "number": n, "section": section["code"], "chapter": section["chapter"], "spans": sp,
                                      "ws_doc": ws_doc if n in answers else None, "ws_spans": answers.get(n, []),
                                      "subtopics": tags(book, book_cache, sp, section, scores)})
                print(f"  {name}: {len(spans)} questions, {len(spans) - len(missing)} with answers", flush=True)
        # investigations, examples, chapter reviews and notes: each saved on its own
        features, reviews, notes = [], [], {}
        for chapter in data.book().get("chapters", []):
            secs = [x for x in data.book()["sections"] if x["chapter"] == chapter["n"]]
            items, review = features_of(book, book_cache, chapter, secs)
            features += items
            if review:
                ws_ch = next((c for c in data.worked_chapters() if c["chapter"] == chapter["n"]), None)
                if ws_ch and ws_ch["doc"] not in ws_open:
                    ws_open[ws_ch["doc"]] = pdfplumber.open(str(docs[ws_ch["doc"]]))
                reviews.append({"chapter": chapter["n"], "pages": list(range(review["page"], chapter["pdf_end"] + 1)), "ws_doc": ws_ch["doc"] if ws_ch else None,
                                "ws_pages": review_answers(ws_open[ws_ch["doc"]], ws_ch["doc"], ws_ch) if ws_ch else []})
            skip: dict[int, list] = {}
            for q in questions:
                if q["chapter"] == chapter["n"]:
                    for sp in q["spans"]:
                        skip.setdefault(sp[0], []).append(tuple(sp[1:5]))
            for sec in secs:
                notes[sec["code"]] = {"title": sec["title"], "chapter": sec["chapter"], "subtopics": sec["subtopics"], "pages": [sec["pdf_start"], sec["pdf_end"]],
                                      "text": notes_text(book, book_cache, sec, skip)}
            print(f"  chapter {chapter['n']}: {len(items)} features", flush=True)
    for f in ws_open.values():
        f.close()
    total = sum(len(s["exercises"]) for s in data.book().get("sections", []))
    return {"questions": questions, "features": features, "reviews": reviews, "notes": notes,
            "report": {"exercises_total": total, "exercises_split": done, "not_split": problems, "partial": partial}}


def main() -> None:
    result = build()
    OUT.write_text(json.dumps({"questions": result["questions"], "report": result["report"]}, ensure_ascii=False, indent=0), encoding="utf-8")
    FEATURES.write_text(json.dumps({"investigations": [f for f in result["features"] if f["kind"] == "investigation"],
                                    "inquiry": [f for f in result["features"] if f["kind"] == "inquiry"],
                                    "examples": [f for f in result["features"] if f["kind"] == "example"],
                                    "reviews": result["reviews"]}, ensure_ascii=False, indent=0), encoding="utf-8")
    NOTES.write_text(json.dumps(result["notes"], ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"features: {len(result['features'])}, reviews: {len(result['reviews'])}, notes sections: {len(result['notes'])}")
    r = result["report"]
    print(f"{len(result['questions'])} questions from {r['exercises_split']} of {r['exercises_total']} exercises -> {OUT}")
    print("not split:", json.dumps(r["not_split"], ensure_ascii=False))
    print("partial:", r["partial"][:40])


if __name__ == "__main__":
    main()
