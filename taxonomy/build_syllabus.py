"""
Build the canonical IB Chemistry syllabus map (first assessment 2025) from the
official Chemistry guide PDF.

Output: data/syllabus/syllabus.json
  {
    "themes":      [{"code": "S1", "title": ...}],
    "sub_topics":  [{"code": "S1.1", "title", "theme", "guiding_question",
                     "sl_hours", "hl_hours", "understandings": [...]}],
    "understandings": {"S1.1.1": {"statement", "skills", "guidance",
                       "linking_questions", "level": "SL|AHL",
                       "data_booklet_mentioned": bool}},
    "command_terms": [{"term", "definition", "ao"}],
    "assessment_objectives": {...}
  }

Every other part of IB-TEE (regex tagging, Chroma metadata, prompts, UI tree)
keys off the codes produced here: "S1.1" / "R2.3" (sub-topic) and
"S1.1.2" (understanding). Bare "1.1" is ambiguous in the 2025 syllabus because
Structure 1.1 and Reactivity 1.1 are different sub-topics.

Usage:
    python -m taxonomy.build_syllabus path/to/Chemistry_Guide_2025.pdf
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber

OUT = Path(__file__).resolve().parents[1] / "data" / "syllabus" / "syllabus.json"

RIGHT_COL_X = 298          # x0 where the "Linking questions" column starts
COL_GAP = 7                # min horizontal gap that separates the two columns
HEADER_MAX_TOP = 70        # running header band ("Syllabus content")
FOOTER_MIN_TOP = 790       # running footer band

PREFIX = {"Structure": "S", "Reactivity": "R"}

THEME_RE = re.compile(r"^(Structure|Reactivity) ([123])\. (.+)$")
SUBTOPIC_RE = re.compile(r"^(Structure|Reactivity) ([123])\.(\d)—(.+)$")
UNDERSTANDING_RE = re.compile(r"^(Structure|Reactivity) ([123])\.(\d)\.(\d+)—(.+)$")
LINK_START_RE = re.compile(
    r"^(Structure|Reactivity|Tool|Inquiry|Nature of science|NOS|TOK)\b[^—]{0,40}—"
)
SKILL_VERBS = {
    "Analyse", "Annotate", "Apply", "Calculate", "Classify", "Compare", "Construct",
    "Contrast", "Convert", "Deduce", "Derive", "Describe", "Determine", "Discuss",
    "Distinguish", "Draw", "Estimate", "Evaluate", "Explain", "Identify", "Interpret",
    "Justify", "Outline", "Perform", "Predict", "Recognize", "Recognise", "Relate",
    "Represent", "Sketch", "Solve", "State", "Suggest", "Understand", "Use", "Write",
}

# Assessment objectives as defined in the guide ("Assessment objectives" section).
ASSESSMENT_OBJECTIVES = {
    "AO1": "Demonstrate knowledge of terminology, facts, concepts, skills, techniques and methodologies",
    "AO2": "Understand and apply knowledge of terminology, facts, concepts, skills, techniques and methodologies",
    "AO3": "Analyse, evaluate and synthesize experimental procedures, primary and secondary data, trends, patterns and predictions",
    "AO4": "Demonstrate the application of skills necessary to carry out insightful and ethical investigations",
}


# --------------------------------------------------------------------------- #
# Low-level: turn each page into (left_line, is_bold) / right_line streams
# --------------------------------------------------------------------------- #
def _page_lines(page):
    words = page.extract_words(extra_attrs=["fontname"], keep_blank_chars=False)
    words = [w for w in words if HEADER_MAX_TOP <= w["top"] < FOOTER_MIN_TOP]
    # group into visual lines (tolerance for sub/superscripts)
    words.sort(key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = []
    # Tight tolerance so left/right column rows that are a few px apart stay
    # separate; sub/superscript fragments (e.g. the "k" in E_k) are folded back
    # into the nearest preceding line afterwards.
    for w in words:
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= 1.5:
            lines[-1].append(w)
        else:
            lines.append([w])
    merged: list[list[dict]] = []
    for ln in lines:
        frag = sum(len(w["text"]) for w in ln) <= 2
        if frag and merged and abs(ln[0]["top"] - merged[-1][0]["top"]) <= 6:
            merged[-1].extend(ln)
        else:
            merged.append(ln)
    lines = merged
    out = []
    for ln in lines:
        ln.sort(key=lambda w: w["x0"])
        left, right = [], []
        in_right = False
        prev_x1 = None
        for w in ln:
            gap = (w["x0"] - prev_x1) if prev_x1 is not None else 999
            if not in_right and w["x0"] >= RIGHT_COL_X and gap > COL_GAP:
                in_right = True
            (right if in_right else left).append(w)
            prev_x1 = w["x1"]
        top = ln[0]["top"]
        if left:
            bold = sum("Bold" in w["fontname"] for w in left) > len(left) / 2
            out.append(("L", top, " ".join(w["text"] for w in left), bold))
        if right:
            out.append(("R", top, " ".join(w["text"] for w in right), False))
    return out


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(" ,", ",").replace(" .", ".").replace(" :", ":")
    return s


# --------------------------------------------------------------------------- #
# State machine over the syllabus-content pages
# --------------------------------------------------------------------------- #
def parse_guide(pdf_path: str | Path) -> dict:
    pdf = pdfplumber.open(str(pdf_path))
    themes, sub_topics, understandings = [], [], {}
    cur_sub = None
    cur_u = None
    hl_mode = False
    started = False
    pending_bold_statement = False

    def close_link_buffer(u):
        if u is not None and u.get("_link_buf"):
            u["linking_questions"].append(_clean(u["_link_buf"]))
            u["_link_buf"] = ""

    for page in pdf.pages:
        text = page.extract_text() or ""
        if not started:
            if "Structure 1.1.1—" in text:
                started = True
            else:
                continue
        # every syllabus page carries the running header "Syllabus content"; the first page
        # without it is the Assessment chapter, which must not leak into the last understanding
        if "Syllabus content" not in text[:150]:
            break

        for side, _top, line, bold in _page_lines(page):
            line = _clean(line)
            if not line or line in {"Syllabus content", "Structure", "Reactivity"}:
                continue
            if re.fullmatch(r"\d+|Chemistry guide|\d+ Chemistry guide|Chemistry guide \d+", line):
                continue

            if side == "R":
                if cur_u is None:
                    continue
                if LINK_START_RE.match(line) or line.startswith("Structure 2 (all)"):
                    close_link_buffer(cur_u)
                    cur_u["_link_buf"] = line
                else:
                    cur_u["_link_buf"] = (cur_u.get("_link_buf", "") + " " + line).strip()
                continue

            # ---------- left column / full width ----------
            m = UNDERSTANDING_RE.match(line)
            if m and bold:
                close_link_buffer(cur_u)
                kind, theme, sub, num, rest = m.groups()
                code = f"{PREFIX[kind]}{theme}.{sub}.{num}"
                cur_u = {
                    "code": code,
                    "sub_topic": f"{PREFIX[kind]}{theme}.{sub}",
                    "statement": rest,
                    "skills": [],
                    "guidance": [],
                    "linking_questions": [],
                    "level": "AHL" if hl_mode else "SL",
                    "_link_buf": "",
                }
                understandings[code] = cur_u
                if cur_sub and cur_sub["code"] == cur_u["sub_topic"]:
                    cur_sub["understandings"].append(code)
                pending_bold_statement = True
                continue

            m = SUBTOPIC_RE.match(line)
            if m and bold:
                close_link_buffer(cur_u)
                kind, theme, sub, title = m.groups()
                cur_sub = {
                    "code": f"{PREFIX[kind]}{theme}.{sub}",
                    "theme": f"{PREFIX[kind]}{theme}",
                    "title": title,
                    "guiding_question": None,
                    "sl_hours": None,
                    "hl_hours": 0,
                    "understandings": [],
                }
                hl_only = "(Additional higher level)" in title
                if hl_only:
                    cur_sub["title"] = title.replace("(Additional higher level)", "").strip()
                cur_sub["hl_only"] = hl_only
                sub_topics.append(cur_sub)
                cur_u = None
                hl_mode = hl_only
                continue

            m = THEME_RE.match(line)
            if m and bold:
                kind, theme, title = m.groups()
                code = f"{PREFIX[kind]}{theme}"
                if not any(t["code"] == code for t in themes):
                    themes.append({"code": code, "title": title, "family": kind})
                continue

            if line.startswith("Guiding question:") and cur_sub:
                cur_sub["guiding_question"] = line.split(":", 1)[1].strip()
                continue
            if line.startswith(("Standard level and higher level:", "Higher level only:")) and cur_sub:
                h = re.search(r"([\d.]+) hour", line)
                cur_sub["sl_hours"] = float(h.group(1)) if h else None
                continue
            if line.startswith("Additional higher level:") and cur_sub:
                close_link_buffer(cur_u)
                h = re.search(r"([\d.]+) hour", line)
                cur_sub["hl_hours"] = float(h.group(1)) if h else 0
                hl_mode = h is not None
                cur_u = None
                continue

            if cur_u is None:
                # guiding question continuation lines etc.
                if cur_sub and cur_sub["guiding_question"] and not cur_sub["understandings"] and not bold:
                    cur_sub["guiding_question"] += " " + line
                continue

            if bold and pending_bold_statement:
                cur_u["statement"] += " " + line
                continue
            pending_bold_statement = False

            first = line.split(" ", 1)[0]
            if first in SKILL_VERBS and not cur_u["guidance"]:
                cur_u["skills"].append(line)
            elif cur_u["skills"] and not cur_u["guidance"] and line[:1].islower():
                cur_u["skills"][-1] += " " + line          # wrapped skill line
            else:
                if cur_u["guidance"] and (line[:1].islower() or cur_u["guidance"][-1][-1:] not in ".?:"):
                    cur_u["guidance"][-1] += " " + line
                else:
                    cur_u["guidance"].append(line)

    close_link_buffer(cur_u)
    for u in understandings.values():
        u.pop("_link_buf", None)
        u["statement"] = _clean(u["statement"])
        blob = " ".join([u["statement"], *u["skills"], *u["guidance"]]).lower()
        u["data_booklet_mentioned"] = "data booklet" in blob

    return {
        "syllabus": "IB DP Chemistry — first assessment 2025",
        "source": Path(pdf_path).name,
        "themes": themes,
        "sub_topics": sub_topics,
        "understandings": understandings,
        "command_terms": parse_command_terms(pdf),
        "assessment_objectives": ASSESSMENT_OBJECTIVES,
    }


def parse_command_terms(pdf) -> list[dict]:
    """Glossary of command terms (appendix). AO level comes from the section header."""
    terms, ao, cur = [], None, None
    on = False
    for page in pdf.pages:
        text = page.extract_text() or ""
        if not on:
            if "Command terms for chemistry" not in text:
                continue
            on = True
        stop = False
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("Bibliography"):
                stop = True
                break
            m = re.match(r"Assessment objective (\d)", line)
            if m:
                ao = f"AO{m.group(1)}"
                continue
            if not ao or line.startswith(("Command term", "Glossary", "Chemistry guide", "Appendices")) \
                    or re.fullmatch(r"\d+", line):
                continue
            m = re.match(r"^([A-Z][a-z]+)\s{1,}(.+)$", line)
            if m and m.group(1) not in {"A", "The", "Graphs", "Diagrams", "Opinions", "ruler",
                                        "Students", "Although", "Command"} and \
                    len(m.group(1)) > 3 and not line.startswith(("Represent", "Give", "Make", "Obtain",
                                                                 "Offer", "Reach", "Propose", "Add",
                                                                 "Provide")):
                cur = {"term": m.group(1), "definition": m.group(2), "ao": ao}
                terms.append(cur)
            elif cur:
                cur["definition"] += " " + line
        if stop:
            break
    # Some terms legitimately start a line with the definition verbs above being wrapped; tidy up
    for t in terms:
        t["definition"] = re.sub(r"\s*\d+ Chemistry guide$", "", _clean(t["definition"]))
    return terms


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    data = parse_guide(argv[1])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    n_sl = sum(u["level"] == "SL" for u in data["understandings"].values())
    print(f"themes={len(data['themes'])} sub_topics={len(data['sub_topics'])} "
          f"understandings={len(data['understandings'])} (SL {n_sl}, AHL "
          f"{len(data['understandings']) - n_sl}) command_terms={len(data['command_terms'])}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main(sys.argv)
