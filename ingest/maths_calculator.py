"""
Oxford fx-CG50 GDC sheets (Maths AI HL) → data/maths/calculator.json + the calculator screenshots as PNG files.

    python -m ingest.maths_calculator

The sheets are the source of truth for button sequences. Their key presses are printed with a key-icon font, which comes out of the
text layer as stray letters ("Press p 1" is MENU 1), so button sequences are never retyped: every step is shown as a crop of the
original page (keys and all), and each calculator screenshot is extracted as its own image.

    data/maths/calculator.json                 sheets, steps, topics, teacher notes
    data/maths/calculator_screens/<id>_<n>.png the screenshots, cut from a 3x render of the page
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "documents to process" / "MATHS" / "CALCULATOR INSTRUCTIONS" / "Oxford_fxCG50_AI_HL_Chapters1-14_With_Master_Index (1).pdf"
OUT = ROOT / "data" / "maths" / "calculator.json"
SCREENS = ROOT / "data" / "maths" / "calculator_screens"
SHEET_HEAD = re.compile(r"^Chapter (\d+)\s*/\s*Example (\w+)$")
INDEX_ROW = re.compile(r"^Ch (\d+) / Ex (\w+) (.+?) (\d+)$")
TOPIC_ROW = re.compile(r"^TOPIC (\d) - (.+)$")
NOTE_ROW = re.compile(r"^Ch (\d+) / Ex (\w+)\s*[|-]\s*(.+)$")
SCREEN_MIN_W, SCREEN_MIN_H = 100, 50          # points: the calculator screenshots are 135 x 70; key/formula images are much smaller
SPLIT_X = 372                                  # instructions on the left, screens from about x = 377
APPS = [   # (label, pattern in the sheet text)
    ("Run-Matrix", r"Run-Matrix"), ("Statistics (List Editor)", r"List Editor|STAT\b|Statistics"),
    ("Graph & G-Solv", r"graph screen|G-Solv|equation entry screen|DRAW"), ("Table", r"\bTABLE\b|table of values"),
    ("Financial", r"finance app|Financial|TVM"), ("Equation solver", r"EQUA|Simultaneous|Polynomial|SolveN|Solver"),
    ("Recursion / sequences", r"sequence entry screen|Recursion|RECUR"), ("Distributions", r"\bDIST\b|Bpd|Bcd|Npd|Ncd|Pcd|Ppd|InvN"),
    ("Hypothesis tests & intervals", r"\bTEST\b|INTR|confidence interval|χ|chi|t-test|p-value"),
    ("Matrices", r"Mat\s*[A-Z]|MATRIX|matrix"), ("Complex numbers", r"complex|Complex"),
    ("Calculus (d/dx, ∫dx)", r"d/dx|∫|dy/dx|integral|derivative|gradient"),
]
QUESTION_TYPE_FIXES = {"8-9": "Complex numbers", "9-13": "Matrices and Markov chains", "10-21": "Calculus: gradients, areas, volumes", "14-2": "Hypothesis tests and confidence intervals", "14-3": "Hypothesis tests and confidence intervals", "14-5": "Hypothesis tests and confidence intervals", "14-13": "Hypothesis tests and confidence intervals", "14-14": "Hypothesis tests and confidence intervals", "14-15": "Hypothesis tests and confidence intervals", "14-16": "Hypothesis tests and confidence intervals"}   # sheets whose title misleads the rules below
QUESTION_TYPES = [  # exam question type, matched on the sheet title
    ("Finance: interest, loans, annuities", r"finance|interest|loan|inflation|rent"),
    ("Sequences and series", r"sequence|series"),
    ("Regression and correlation", r"regression|line of best fit|Spearman|correlation"),
    ("Probability distributions", r"binomial|Poisson|normal|probabilit|central limit|parameter"),
    ("Hypothesis tests and confidence intervals", r"test|confidence|Type I|goodness|independence|paired|estimating"),
    ("Solving equations and intersections", r"intersection|equation|solving|straight line"),
    ("Graphs: max/min, sketching, modelling", r"minimum|maximum|sketching|graphing|modelling|piecewise|turning|concavity|cubic|power"),
    ("Matrices and Markov chains", r"matri|transition|state vector|diagonal"),
    ("Complex numbers", r"complex"),
    ("Calculus: gradients, areas, volumes", r"gradient|area|volume|integral|limit|derivative|kinematics|velocity"),
    ("Differential equations (Euler)", r"Euler"),
    ("Statistics: averages and spread", r"central tendency|dispersion|histogram"),
    ("Trigonometry and geometry", r"trigonometr|sine rule|cosine rule|Voronoi|exact values"),
]
# Each sheet's syllabus sub-topics (AI HL guide numbering), decided from its title and checked against the master index topic.
SUBTOPICS = {
    "1-7": ["3.2", "3.3"], "1-9": ["3.2"], "1-13": ["3.2"], "2-2": ["4.3"], "2-3": ["4.3"], "2-5": ["4.2"], "2-9": ["4.4"],
    "3-1": ["2.1"], "3-2": ["2.1", "1.8"], "3-4": ["3.6"], "3-14c": ["3.6", "2.4"], "4-2": ["2.5"], "4-4": ["2.5", "2.1"],
    "4-7": ["2.5"], "4-8": ["2.9"], "4-13": ["1.2"], "4-14": ["1.2"], "4-18": ["1.2"], "4-20": ["4.4"], "6-9": ["2.4", "2.5"],
    "6-10": ["2.5", "4.13"], "6-11": ["2.5", "4.13"], "7-2": ["1.3"], "7-5": ["1.3"], "7-6": ["1.3"], "7-7": ["1.4"], "7-8": ["1.4", "1.7"],
    "7-9": ["1.4"], "7-10": ["1.7"], "7-12": ["2.9"], "7-14": ["2.9", "4.13"], "8-2": ["3.8"], "8-4": ["2.9", "4.13"], "8-5a": ["1.12"],
    "8-8": ["1.13"], "8-9": ["1.13"], "8-10": ["1.12", "1.13"], "9-4": ["1.14"], "9-5": ["1.14", "1.8"], "9-10": ["4.19"], "9-11": ["4.19"],
    "9-13": ["1.15"], "10-2": ["5.1"], "10-8": ["5.1", "5.3"], "10-9": ["5.6"], "10-10": ["5.6", "5.7"], "10-19": ["5.10"],
    "10-21": ["5.13"], "11-2": ["5.5"], "11-3": ["5.5", "5.12"], "11-4": ["5.1"], "11-12": ["5.5", "5.11"], "11-14": ["5.12"],
    "11-15": ["5.12"], "11-16": ["5.12"], "11-17": ["5.12"], "11-18": ["5.12"], "11-21": ["5.13"], "11-25": ["5.16"], "12-6": ["5.16"],
    "13-4": ["4.8"], "13-5": ["4.8"], "13-6": ["4.17"], "13-7": ["4.8", "4.17"], "13-8": ["4.17"], "13-9": ["4.9"], "13-11": ["4.9"],
    "13-12": ["4.9"], "13-18": ["4.15"], "14-1": ["4.10"], "14-2": ["4.18"], "14-3": ["4.18"], "14-5": ["4.18"], "14-6": ["4.18"],
    "14-7": ["4.11"], "14-8": ["4.16"], "14-9": ["4.11"], "14-10": ["4.11"], "14-11": ["4.11"], "14-12": ["4.11"], "14-13": ["4.11", "4.17"],
    "14-14": ["4.11", "4.8"], "14-15": ["4.11", "4.14"], "14-16": ["4.11", "4.14"], "14-18": ["4.18"], "14-19": ["4.18"],
}


def page_data(pdf) -> list[dict]:
    out = []
    for i, page in enumerate(pdf.pages):
        lines = [{"top": float(l["top"]), "bottom": float(l["bottom"]), "x0": float(l["x0"]), "text": l["text"].strip()}
                 for l in (page.extract_text_lines() or []) if l["top"] >= 0 and l["x0"] >= 0]     # template text left off the page
        screens = sorted(({"x0": float(im["x0"]), "x1": float(im["x1"]), "top": float(im["top"]), "bottom": float(im["bottom"])}
                          for im in page.images if im["x1"] - im["x0"] >= SCREEN_MIN_W and im["bottom"] - im["top"] >= SCREEN_MIN_H),
                         key=lambda s: s["top"])
        out.append({"index": i, "width": float(page.width), "height": float(page.height), "lines": lines, "screens": screens})
    return out


def parse_index(pages: list[dict]) -> dict[str, dict]:
    """Sheet id -> {"topic": n, "index_title": ...} from the master index, by syllabus topic (its first part)."""
    out, topic = {}, None
    for p in pages[:7]:
        for l in p["lines"]:
            if "BY OXFORD CHAPTER" in l["text"] and p["index"] >= 3:
                return out
            if m := TOPIC_ROW.match(l["text"]):
                topic = int(m.group(1))
            elif (m := INDEX_ROW.match(l["text"])) and topic:
                out.setdefault(f"{m.group(1)}-{m.group(2)}", {"topic": topic, "index_title": m.group(3), "index_page": int(m.group(4))})
    return out


def teacher_notes(pages: list[dict]) -> dict[str, list[str]]:
    """Sheet id -> teacher notes, from the notes pages at the end and the correction boxes printed on sheets."""
    notes: dict[str, list[str]] = {}
    for p in pages:
        texts = [l["text"] for l in p["lines"]]
        if not texts:
            continue
        head = texts[0]
        if head.startswith("TEACHER NOTES"):
            chapter = re.search(r"CHAPTER (\d+)$", head)
            current, buf = None, []
            for t in texts[1:]:
                m = NOTE_ROW.match(t) or (re.match(r"^Example (\w+) - (.+)$", t) if chapter else None)
                if m:
                    if current:
                        notes.setdefault(current, []).append(" ".join(buf))
                    sid = f"{m.group(1)}-{m.group(2)}" if m.re is NOTE_ROW else f"{chapter.group(1)}-{m.group(1)}"
                    current, buf = sid, [(m.group(3) if m.re is NOTE_ROW else m.group(2)).strip() + ":"]
                elif current and not re.match(r"^(Original|Oxford|Verify|Teacher check|For review)", t):
                    buf.append(t)
            if current:
                notes.setdefault(current, []).append(" ".join(buf))
        for k, t in enumerate(texts):
            if m := re.match(r"^TEACHER CORRECTION \| Chapter (\d+), Example (\w+)", t):
                body = []
                for u in texts[k + 1:]:
                    if u.startswith("©") or re.fullmatch(r"\d+", u):
                        break
                    body.append(u)
                notes.setdefault(f"{m.group(1)}-{m.group(2)}", []).insert(0, "Correction printed on the sheet: " + " ".join(body))
    return notes


def build() -> dict:
    import pdfplumber
    import pypdfium2 as pdfium
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    with pdfplumber.open(str(PDF)) as pdf:
        pages = page_data(pdf)
    index = parse_index(pages)
    notes = teacher_notes(pages)
    sheets: dict[str, dict] = {}
    order = []
    for p in pages:
        texts = [l["text"] for l in p["lines"]]
        if len(texts) < 3 or not texts[0].startswith("GDC skills"):
            continue
        m = SHEET_HEAD.match(texts[1])
        if not m:
            continue
        sid = f"{m.group(1)}-{m.group(2)}"
        title = texts[2]
        body = [l for l in p["lines"][3:] if not l["text"].startswith("©") and not l["text"].startswith("TEACHER CORRECTION")]
        while body and re.fullmatch(r"\d+", body[-1]["text"]):      # the sheet's page number
            body.pop()
        content_top = p["lines"][2]["bottom"] + 4
        content_bottom = (body[-1]["bottom"] + 6) if body else content_top + 10
        corr = next((l for l in p["lines"] if l["text"].startswith("TEACHER CORRECTION")), None)
        if corr:
            content_bottom = max(content_bottom, max(l["bottom"] for l in p["lines"] if l["top"] >= corr["top"] and not l["text"].startswith("©")
                                                     and not re.fullmatch(r"\d+", l["text"])) + 6)
        sheet = sheets.get(sid)
        if not sheet:
            sheet = sheets[sid] = {"id": sid, "chapter": int(m.group(1)), "example": m.group(2), "title": title, "pages": [], "steps": [],
                                   "problem": "", "text": ""}
            order.append(sid)
            first_press = next((i for i, l in enumerate(body) if l["text"].startswith("Press")), len(body))
            sheet["problem"] = "\n".join(l["text"] for l in body[:first_press])
        sheet["pages"].append(p["index"])
        sheet["text"] += "\n".join(l["text"] for l in body) + "\n"
        # step rows: cut the page midway between screenshots, so each row holds one screen and the instructions beside it
        screens = p["screens"]
        cuts = [content_top]
        for a, b in zip(screens, screens[1:]):
            cuts.append((a["bottom"] + b["top"]) / 2)
        cuts.append(content_bottom)
        for k in range(len(cuts) - 1):
            top, bottom = cuts[k], cuts[k + 1]
            if bottom - top < 8:
                continue
            screen = screens[k] if k < len(screens) else None
            row_text = "\n".join(l["text"] for l in body if top <= (l["top"] + l["bottom"]) / 2 < bottom and l["x0"] < SPLIT_X)
            sheet["steps"].append({"page": p["index"], "top": round(top, 1), "bottom": round(bottom, 1), "text": row_text,
                                   "screen": None if not screen else {k2: round(v, 1) for k2, v in screen.items()}})
    # screenshots as their own files, cut from a 3x render so they stay crisp when enlarged
    SCREENS.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(PDF))
    renders: dict[int, object] = {}
    for sid in order:
        n = 0
        for step in sheets[sid]["steps"]:
            s = step["screen"]
            if not s:
                continue
            n += 1
            name = f"{sid}_{n}.png"
            out = SCREENS / name
            if not out.exists():
                if step["page"] not in renders:
                    renders = {step["page"]: doc[step["page"]].render(scale=3).to_pil()}
                img = renders[step["page"]]
                img.crop((int(s["x0"] * 3), int(s["top"] * 3), int(s["x1"] * 3), int(s["bottom"] * 3))).save(out, optimize=True)
            step["screen"]["file"] = name
    doc.close()
    for sid in order:
        sh = sheets[sid]
        info = index.get(sid, {})
        sh["sheet_title"] = sh["title"]
        sh["title"] = info.get("index_title") or sh["title"]      # the index names the four finance sheets apart
        sh["topic"] = info.get("topic") or (int(SUBTOPICS[sid][0].split(".")[0]) if sid in SUBTOPICS else None)
        sh["subtopics"] = SUBTOPICS.get(sid, [])
        sh["apps"] = [label for label, pat in APPS if re.search(pat, sh["text"] + " " + sh["title"])]
        sh["question_type"] = QUESTION_TYPE_FIXES.get(sh["id"]) or next((label for label, pat in QUESTION_TYPES if re.search(pat, sh["title"], re.I)), "Other")
        n_screens = sum(1 for s in sh["steps"] if s["screen"])
        sh["screens"] = n_screens
        sh["difficulty"] = "Short" if n_screens <= 4 else "Medium" if n_screens <= 8 else "Long"
        sh["notes"] = notes.get(sid, [])
        sh["in_index"] = sid in index
    return {"file": str(PDF.relative_to(ROOT)), "source": "Oxford IB Diploma Programme Mathematics AI HL, GDC skills sheets for Casio fx-CG50 (© Oxford University Press 2019), with teacher notes",
            "calculator": "Casio fx-CG50", "sheets": [sheets[s] for s in order],
            "unmatched_notes": sorted(set(notes) - set(sheets)), "missing_from_pdf": sorted(set(index) - set(sheets))}


def main() -> None:
    result = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    sheets = result["sheets"]
    print(f"{len(sheets)} sheets, {sum(s['screens'] for s in sheets)} screenshots, {sum(len(s['notes']) for s in sheets)} teacher notes -> {OUT}")
    print("no topic:", [s["id"] for s in sheets if not s["topic"]], "| no sub-topic:", [s["id"] for s in sheets if not s["subtopics"]])
    print("notes for missing sheets:", result["unmatched_notes"], "| index rows without a sheet:", result["missing_from_pdf"])


if __name__ == "__main__":
    main()
