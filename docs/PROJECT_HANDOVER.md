# IB TEE: technical handover

*Written 7 November 2026, after the Mathematics AI HL integration; updated 8 November 2026 (see section 8 for what changed). It describes the code as it is in this folder.*

IB TEE is a personal, local, single-user IB revision platform. It started as an IB Chemistry HL “examiner technique engine” and now hosts two subjects behind one shell:

| Subject | Built from | What the student does |
|---|---|---|
| **Chemistry HL** (2025 syllabus) | IB past papers, markschemes, examiner reports and two Oxford books, processed into technique decks | Interactive MCQ technique cards with "7 tricks", a spaced Questionbank, a Study guide from the books, notes, definitions, data booklet, grade boundaries |
| **Mathematics AI HL** | The student's 8 topic revision papers + markschemes (real IB questions 2021–2025), the Oxford fx-CG50 calculator sheets, the Oxford AI HL worked solutions | Topic-by-topic learning cycle, question bank, mixed-topic and timed practice, calculator mastery, error log, spaced repetition, revision calendar, analytics |

---

## 1. Project architecture

### Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ (the `.venv` runs Python 3.14.6) |
| UI | **Streamlit 1.66** (server-rendered Python UI, one script rerun per interaction) |
| Custom UI component | `card_component/index.html`: a bidirectional Streamlit component (plain HTML/JS, no build step) for the Chemistry question card |
| PDF text | `pdfplumber` (text with positions); `pypdfium2` (page rendering to PNG); Pillow (cropping) |
| Charts | Streamlit's built-in charts (Vega-Lite/Altair underneath), pandas for grouping |
| Storage | Plain JSON / JSONL files under `data/`: no database server |
| AI (Chemistry build tools only) | Claude through the **Claude Code CLI** on the student's Pro plan (`--backend claude-cli`); Anthropic API backend exists but is never the default. LlamaParse optional for PDF parsing |
| Tests | pytest, Streamlit `AppTest` for whole-page runs |

There is **no separate backend and no HTTP API**. Streamlit runs the Python script on the server for every interaction; "frontend" and "backend" are the same process. The only browser-side code is the Chemistry card component (it posts the student's first answer back to Python through `Streamlit.setComponentValue`), a small countdown timer for practice exams (`components.html`) and a one-line reload when the theme changes.

### Folder and file map

```
ib_tee/
├─ app.py                     SHELL: page config, theme, left menu, router (Home · Subjects · Bookmarks · My subjects)
├─ chem_app.py                Chemistry HL pages (the original app.py, unchanged logic; main() became render(page))
├─ ibtee/                     PLATFORM (shared by every subject)
│  ├─ theme.py                design system: CSS variables (light/dark), header, crumbs, chips, stat strip, level bars
│  ├─ nav.py                  routing in the URL (?s=<subject>&p=<page>&…), nav buttons
│  ├─ store.py                profile (name, my subjects, theme), bookmarks, subject catalogue
│  └─ home.py                 Home dashboard, Subjects catalogue, Bookmarks
├─ maths/                     MATHEMATICS AI HL runtime
│  ├─ data.py                 read-only loaders for the built JSON (syllabus, questions, calculator)
│  ├─ render.py               crops of the original PDFs as PNG (questions, markschemes, calculator steps), cached
│  ├─ progress.py             attempt log, mastery levels, spaced repetition (recall + retries), error log, mixed sets
│  ├─ schedule.py             sessions in calendar.json (Atlantic/Canary), first weekend programme
│  ├─ exams.py                timed practice papers from real questions
│  ├─ ui_question.py          question card (attempt → hints → markscheme → self-marking) and recall card
│  └─ ui_pages.py             every Maths page + its router
├─ ingest/                    BUILD STEPS (run once, or when PDFs change)
│  ├─ maths_papers.py         revision papers → data/maths/questions.json
│  ├─ maths_tagging.py        keyword rules: question part → syllabus sub-topic
│  ├─ maths_calculator.py     fx-CG50 sheets → data/maths/calculator.json + calculator_screens/*.png
│  ├─ maths_syllabus.py       78 sub-topics with study notes + worked-solutions index → data/maths/syllabus.json
│  └─ pipeline.py, splitters.py, link.py, classify.py, reports.py, scan_*.py, book_pages.py, prepared_pages.py, …   (Chemistry)
├─ engine/                    Chemistry deck/guide builders (Claude via claude-cli)
├─ analysis/                  Chemistry evidence packs, examiner-report statistics, deck rendering
├─ taxonomy/                  Chemistry syllabus builder
├─ guide_ui.py, card_ui.py, study_plan.py, notes.py, reference.py, web_tips.py, book_view.py   (Chemistry runtime)
├─ card_component/index.html  Chemistry interactive question card
├─ data/                      everything the app reads and writes (see §4)
├─ documents to process/      the student's source PDFs (CHEMISTRY/, MATHS/) — never modified
├─ tests/                     pytest (194 tests; Chemistry + tests/test_maths.py)
├─ docs/                      this handover and the integration plan
├─ backups/                   dated copies made before big changes (pre_maths_20261107 = the pre-integration app)
├─ revision dojo information source/   an empty Figma Make (React/Vite) scaffold; not used by the app
└─ .streamlit/config.toml, .claude/launch.json, requirements*.txt, sources.toml, README.md, CLAUDE.md
```

### How data flows

```
documents to process/MATHS/*.pdf ──ingest/maths_*.py──► data/maths/{questions,calculator,syllabus}.json + calculator_screens/
                                                        │
app.py ─► maths/ui_pages.py ─► maths/data.py (read) ────┘
                           ─► maths/render.py ─► crops of the original PDF pages (data/maths/cache/)
                           ─► maths/progress.py ─► data/maths/attempts.jsonl (append) + error_notes.json
                           ─► maths/schedule.py ─► data/maths/calendar.json
                           ─► maths/exams.py    ─► data/maths/exams.json
app.py ─► chem_app.py ─► data/techniques/*.json, data/attempts.jsonl, data/progress.json, data/notes.json, …
app.py ─► ibtee/home.py ─► both attempt logs (read), data/profile.json, data/bookmarks.json
```

### External services and libraries

| Used by | Service / library | Needed to run the app? |
|---|---|---|
| Chemistry build (`engine/*`, `ingest/classify.py`) | Claude Code CLI on the Pro plan (default); Anthropic API (optional); LlamaParse (optional) | **No**: only to rebuild Chemistry content |
| Chemistry OCR (`ingest/scan_ocr.py`) | RapidOCR + onnxruntime; Marker in `.venv-marker` | No |
| Fonts | Google Fonts (Instrument Serif, Inter, JetBrains Mono) | No: system fonts are used offline |
| Maths | nothing external: all Maths content is built locally from the PDFs | — |

---

## 2. Feature inventory

Status: **Full** = works end to end and is tested; **Partial** = works with a stated gap. "Reusable" = can be lifted into another project without the rest.

### Platform

| Feature | What it does / how it is used | Files | Status | Reusable |
|---|---|---|---|---|
| Main menu | Left sidebar: Home, Subjects, Bookmarks, the open subject's pages (Maths: Overview, the five topics, then tools across topics), My subjects, dark-mode switch, user box | `app.py`, `ibtee/theme.py` | Full | Yes (pattern) |
| URL routing | Every page has a URL (`?s=maths_ai_hl&p=q&q=25M.1.AHL.TZ1.3`); buttons change it without reloading, so session state survives | `ibtee/nav.py` | Full | Yes |
| Home dashboard | Greeting, questions answered, accuracy, day streak, last-14-days bars, My subjects, recent attempts across both subjects | `ibtee/home.py` | Full | Yes |
| Subjects catalogue | IB groups 1–5; subjects with content can be added/removed/opened, others say "No content yet" | `ibtee/home.py`, `ibtee/store.py` | Full | Yes |
| Bookmarks | Save on any Maths question or Chemistry card; list newest first; opens the item | `ibtee/store.py`, `ibtee/home.py` | Full | Yes |
| Light / dark mode | Two palettes on the same CSS variables; Streamlit widgets follow after an automatic reload | `ibtee/theme.py`, `app.py` | Full (the Chemistry card iframe stays light) | Yes |

### Mathematics AI HL

| Feature | What it does / how it is used | Files | Status | Reusable |
|---|---|---|---|---|
| Syllabus hierarchy | 5 topics, 78 sub-topics (SL 1.1–1.8 … AHL 5.9–5.18), each with level SL/AHL | `ingest/maths_syllabus.py` → `syllabus.json` | Full (outline transcribed: the guide PDF is not in the folder) | Yes |
| Topic hub | Everything for one topic: sub-topics with levels, its questions (filter by sub-topic), its calculator procedures, its mistakes, its progress | `ui_pages.topic_page` | Full | Yes |
| Sub-topic learning cycle | 1 Recall → 2 Learn (objectives, ideas, steps, formulas in LaTeX, mistakes, examiners' comments, connections, past-paper worked example, textbook worked solutions) → 3 Calculator → 4 Questions (basic to multi-step; toggle for harder & multi-topic) → 5 Review | `maths/ui_pages.py` (`subtopic_page`) | Full | Yes |
| Recall cards + spaced repetition | 3 prompts per sub-topic; type or say the answer, reveal, rate Again/Hard/Good/Easy; SM-2-style intervals worked out from the log | `maths/progress.py` (`card_states`), `ui_question.recall_card` | Full | Yes |
| Daily recall | Due cards first, then new ones from started sub-topics (or the whole syllabus) | `ui_pages.recall_page` | Full | Yes |
| Question bank | Topic → sub-topic → filtered list (paper, difficulty, status) → question; full-text search over questions and markschemes | `ui_pages.qb_*`, `question_list`, `data.search` | Full | Yes |
| Question card | Question as printed (PDF crop), answer box, 2 hints (nudge + first method line of the markscheme), Show markscheme (Space), per-part markscheme + examiners report, self-marking per part, mistake type, concept to revisit, Save | `maths/ui_question.py` | Full | Yes |
| Error log | Every part that lost marks: question, sub-topic, your answer, correct method (markscheme crop), mistake type (7 classes), concept; notes; resolved automatically by a later clean attempt; open mistakes chart; retry queue | `progress.error_log`, `ui_pages.errors_page` | Full | Yes |
| Retries | A miss returns next day; partial/helped in 2 days; clean successes space out 3 → 7 → 14 → 30 days | `progress.part_states`, `due_retries` | Full | Yes |
| Mastery levels | Not started → Learning → Practising → Confident → Mastered, earned from recall, unaided marks and an unfamiliar-context success (see §4) | `progress.level` | Full | Yes |
| Mixed practice | Synoptic (multi-topic) / any / cumulative / weekly topic review; topic hidden until marked, then revealed | `progress.mixed_set`, `ui_pages.mixed_page` | Full | Yes |
| Practice exams | Paper 1 or 2 style from chosen topics, ~110 marks, timer, hidden markschemes until finished, then marking with score by topic | `maths/exams.py`, `ui_pages.exam_page` | Partial: no Paper 3 and no grade (not in the files) | Yes |
| Past papers | Questions grouped by session (21M…25N, specimen/exemplar) and paper | `ui_pages.past_page` | Partial: revision papers contain selected questions, not whole papers | Yes |
| Calculator centre | 86 fx-CG50 sheets filtered by topic, calculator function, exam question type, length, search; step rows with real key icons + extracted screens; practice mode hides each screen until predicted; teacher corrections shown; "choose the procedure" drill | `ingest/maths_calculator.py`, `ui_pages.calc_page`, `sheet_page`, `procedure_drill` | Full | Yes |
| Calendar (all subjects) | Browser board: month/week grid with the chosen day's tasks beside it, no reload on changing day; ticks, Open, editable day table; weekly routine view; events make room for themselves; missed sessions can be moved forward; Maths blocks waiting for a slot are listed and can be placed; Atlantic/Canary, never schedules the past; session page with objective, sub-topics, GDC sheets, questions | `calendar_component/index.html`, `ibtee/calendar_view.py`, `ibtee/planner.py`, `ibtee/routine.py`, `maths/schedule.py`, `ui_pages.session_page` | Full | Yes |
| Analytics | Syllabus map coloured by level, mark rate by topic and by mode, mistakes by type, marks per day, recall rate, weakest sub-topics | `ui_pages.analytics_page` | Full | Yes |
| Course book | The Oxford AI HL book (868 pages) indexed by chapter, 72 sections and their exercises; every sub-topic links to the sections that teach it; reader shows real pages; an exercise opens beside its worked answers (hidden until you try) | `ingest/maths_book.py` → `book.json`, `ui_pages.book_page`, `section_rows` | Full (section ↔ sub-topic map partly hand-checked: `SECTION_OVERRIDES`) | Yes |
| Textbook worked solutions | Oxford AI HL worked-solution pages by chapter/exercise, paired with the book's exercises | `ingest/maths_syllabus.worked_solutions`, `data.exercise_pages` | Full | Yes |
| Month calendar | Visual Monday-first month grid (session bars by kind, today ringed, past faded, done ticks, missed dots); click a day for its editable agenda; month arrows; Agenda list view; on Home as a compact month + today's plan; Calendar in the main menu; the month after the first weekend is planned automatically once (weekday evenings rotate all five topics weakest-first, Saturdays add a mixed set, Sundays a timed paper + error review); "Plan <month>" for later months | `ibtee/calendar_view.py`, `schedule.plan_month`/`ensure_month`, `ui_pages.calendar_page`, `ibtee/home.month_section` | Full | Yes |
| Calendar for all subjects | Main-menu Calendar: Month (coloured by subject, “View more” per day), Week (seven columns with school and routine), Weekly routine (editable per weekday + to-dos). Any day opens one editable table of everything in it (done, start, minutes, subject, type, task, weekly review, notes; add/delete rows). The routine comes from the student's planning PDF and fills the calendar to the end of next month; untouched future routine sessions are rebuilt when the routine changes; unfinished Maths blocks can be carried into the next Maths slots | `ibtee/planner.py`, `ibtee/routine.py` → `data/routine.json` | Full | Yes |
| Cross-links | Question → its sub-topics, topic, GDC procedures, next scheduled session, error log; sub-topic/topic → next calendar session, mistakes; mixed reveal → sub-topics; analytics map and weakest → sub-topics; exam results → topic mistakes; calculator sheet → sub-topics; Home recent attempts → question | `ui_pages.sub_links`, `scheduled_link`, `related_panel` | Full | Yes |

### Chemistry HL (unchanged behaviour, now inside the shell)

| Feature | Files | Status |
|---|---|---|
| Questionbank (technique cards, flow mode, filters, extras, hidden questions) | `chem_app.py`, `card_ui.py`, `card_component/`, `study_plan.py` | Full (decks exist for 12 of 22 sub-topics) |
| Study guide (Learn / Book pages / Worked examples / Try it / Past papers) | `guide_ui.py`, `book_view.py`, `data/guide`, `data/foundations` | Partial: Learn content built for R1.1 only, others fall back to notes |
| Tips & my notes, Web tips | `notes.py`, `web_tips.py`, `engine/web_improver.py` | Full |
| Key definitions, Data booklet, Grade boundaries | `reference.py` | Full |
| Progress overview (periodic-table tiles), Missing markschemes, Build decks | `chem_app.py` | Full |
| Save (bookmark) on cards | `chem_app.card_actions` | Full (new) |

---

## 3. Design system

* **Identity: "lab notebook"** (IB TEE's own, replacing the first RevisionIB-style look on 7 Nov 2026). A deep navy sidebar frames the work (navy in both themes); the canvas is faint graph paper; content sits on white cards with soft shadows; one signal-teal accent for action and progress, amber for "now / due", coral for mistakes. Wordmark: a teal "ib" tile + "ib·tee".
* **Palette** (`ibtee/theme.PALETTES`, exposed as CSS variables):

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` + `--grid` | #F4F6FA + 24px grid lines | #0B1220 | canvas |
| `--side`, `--side2`, `--side-ink` | #0F1B2D, #16253B, #E8EDF5 | #070D18, #101A2C | sidebar, active item, sidebar text |
| `--surface` / `--border` / `--shadow` | #FFFFFF / #E2E7EF / soft two-layer | #121C2E / #22324B | cards, inputs |
| `--ink` / `--muted` / `--faint` | #0F1B2D / #5B6678 / #94A0B2 | #E8EDF5 / #9AA6BA | text |
| `--accent` | #0E9384 (teal) | #2DD4BF | active item bar, codes, numbers, primary hover, progress |
| `--now` | #E7A33E (amber) | #F2B85B | "Now" sessions, topic-hidden chip |
| `--btn` | #0F1B2D | #2DD4BF | primary buttons |
| ok / warn / bad | teal / #B7791F / #D1435B (+ soft backgrounds) | lighter tints | difficulty and score chips |
| Levels | Not started #C7CFDB · Learning #E7A33E · Practising #5B8DEF · Confident #38BFA0 · Mastered #0E7C70 | same | mastery everywhere |
| Subjects | Chemistry #E4572E · Maths #5B6CF0 | same | dots in menus and lists |
| Calendar kinds | study #5B6CF0 · mixed #38BFA0 · exam #E7A33E · review #D1435B · break #C7CFDB | same | session bars |

* **Typography**: Space Grotesk 600 (page titles 2.6rem, section titles 1.45rem, stat values, Streamlit `h1–h3` so Chemistry matches), Inter (body), IBM Plex Mono (kickers, codes, question references, keys). `.streamlit/config.toml` uses the same teal and navy so built-in widgets match.
* **Navigation**: sidebar = Home, Subjects, Bookmarks → the open subject → My subjects → Appearance → user.
  * **Maths is organised per topic**: Overview · Topics 1–5 (each a hub) · Across topics: Mixed, exams & past papers · Error log · Calculator · Revision calendar.
  * **Topic hub** views: Sub-topics · Questions (filter by sub-topic) · Calculator · Mistakes · Progress.
  * **Sub-topic** views: 1 Recall · 2 Learn (objectives, ideas, steps, formulas, mistakes, examiners' comments, connections, worked example, textbook worked solutions) · 3 Calculator · 4 Questions (toggle: harder & multi-topic) · 5 Review.
  * **Overview** views: Today (session, recall, retries, topics) · Progress (analytics) · Find a question (search, all questions).
  * Chemistry menu grouped: Study · Reference · Deck building.
  * Every view is in the URL (`&v=`), so Back returns to the same view; older links (`p=qb`, `qbt`, `qbs`, `topics`, `analytics`) redirect to their new home.
* **Reusable components** (`ibtee/theme.py`): `header`, `crumbs`, `stats_strip`, `chips`, `level_tag`, `level_bar`, `pbar`, `empty`; cards = `st.container(border=True, key="card_…")`; the view switch = `maths.ui_pages.view_switch` (pill segmented control). Maths: `question_card`, `recall_card`, `question_list`, `sheet_row`, `show_image`.
* **Interaction patterns**: attempt before answer, progressive hints, self-marking per part with a required mistake type, topic hidden in mixed mode, keyboard shortcuts (Space = markscheme, → = next question), levels earned not ticked.
* **Responsive**: Streamlit columns stack on phones; under 1100px the question page puts the navigator under the question; stat cards go 2-up under 900px. Checked at 1440px and about 800px.

---

## 4. Data and functionality

### Storage (all under `data/`)

| File | Written by | Rule |
|---|---|---|
| `profile.json` | Home/Subjects/theme | small settings file |
| `bookmarks.json` | Save buttons | `{"items": [{subject, id, label, detail, added}]}` |
| `maths/syllabus.json`, `questions.json`, `calculator.json`, `calculator_screens/` | `ingest/maths_*` | build output; safe to rebuild |
| `maths/attempts.jsonl` | Maths app | **append-only**; never rewrite |
| `maths/error_notes.json` | Error log | `{attempt id: {"note", "resolved"}}` |
| `maths/calendar.json` | Calendar | editable sessions |
| `maths/exams.json` | Practice exams | papers and their marks |
| `maths/tag_overrides.json` (optional) | the student, by hand | `{"<question id>": ["1.12", …]}` beats the keyword tagger |
| `maths/cache/` | `maths/render.py` | page renders and crops; delete freely |
| `attempts.jsonl`, `progress.json`, `notes.json`, `web_tips.json`, `study_plan.json` | Chemistry | never overwrite or delete (see CLAUDE.md) |

### Schemas

**Question** (`questions.json → questions[]`):
```json
{"id": "25M.1.AHL.TZ1.3", "ref": "25M.1.AHL.TZ1.3", "doc": "na_p1", "source": "ms", "number": 3, "topic": 1,
 "paper": "1", "level": "AHL", "session_code": "25M", "session": "May 2025", "max_marks": 8, "has_markscheme": true,
 "parts": [{"label": "a.i", "marks": 3, "q_text": "…", "ms_text": "…", "report_text": "…",
            "q_spans": [[page, top, bottom], …], "ms_spans": […], "report_spans": […]}],
 "q_spans": […], "subtopics": ["1.7", "1.4"], "part_subtopics": {"a.i": "1.7"}, "cross_topics": [],
 "tag_method": "keyword rules (ingest/maths_tagging.py)", "tag_confidence": 0.93, "also_in": []}
```
Spans are PDF regions in points; `maths.render.crop(doc, spans)` turns them into an image. `questions.json → report` lists the source documents and any problems.

**Sub-topic** (`syllabus.json → subtopics[]`): `{code, title, level, objectives[], concepts[], formulas[{name, tex, where, when}], method[], mistakes[], connections[], recall[{q, a}], worked_chapters[]}`; plus `topics[]`, `worked_solutions[{chapter, title, file, doc, first_page, last_page, exercises{}, subtopics[]}]`, `assessment`.

**Calculator sheet** (`calculator.json → sheets[]`): `{id: "7-10", chapter, example, title, sheet_title, problem, text, pages[], steps[{page, top, bottom, text, screen{x0,x1,top,bottom,file}}], topic, subtopics[], apps[], question_type, screens, difficulty, notes[], in_index}`.

**Attempt rows** (`maths/attempts.jsonl`, one JSON object per line; all have `id, ts, day, time, kind`):
* `kind: "part"`: `qid, part, topic, subtopic, marks, awarded, outcome (full|partial|miss), answer, mistake, concept, note, helped, mode (practice|mixed|review|exam), session`
* `kind: "recall"`: `card ("1.2#0"), subtopic, grade (again|hard|good|easy), typed`
* `kind: "calc"`: `sheet, subtopic, correct, mode (pick|steps)`

**Calendar session**: `{id, date, start "HH:MM", minutes, kind (study|break|mixed|exam|review), title, objective, subtopics[], calculator[], questions[], done, programme, unscheduled?}`.

### Progress, scoring and algorithms

* **Marking** is self-assessment against the markscheme, part by part (IB long answers cannot be auto-marked reliably). Losing marks requires a mistake type: Conceptual misunderstanding · Incorrect formula selection · Calculator operation error · Algebraic or numerical error · Misinterpretation of the question · Incomplete mathematical reasoning · Incorrect notation or units.
* **Mastery** (`progress.level`), worked out from the log every time:
  * Not started: nothing done. Learning: recall started or < 2 parts. Practising: ≥ 2 parts.
  * Confident: ≥ 70 % of marks on the last 10 parts, ≥ 3 full-mark parts without hints, recall rated Good/Easy ≥ 70 %.
  * Mastered: Confident **and** unaided successes on two days ≥ 2 days apart, one success in mixed/exam/review mode (topic not given), every recall card recalled well twice, and the last attempt not a miss.
* **Recall scheduling** (`card_states`): first good review 3 days (hard 1, easy 4), second 6 (3/8), then interval × ease (ease 2.5, −0.15 hard, +0.15 easy, floor 1.3); Again resets to 1 day. One review per card per day counts.
* **Retries** (`part_states`): miss → 1 day; partial or hinted → 2 days; clean successes → 3, 7, 14, 30 days.
* **Personalisation**: "Revisit next" = started sub-topics with the most open errors and lowest level; the error log's concept field feeds it.
* **Mixed sets**: least-recently-seen questions, topics taken in turn so the order gives nothing away.
* **Exams**: questions of one paper type from the chosen topics, in turn, untried first, until ≈110 marks; time scaled to marks.
* **Difficulty** (`data.difficulty`): Basic ≤ 5 marks, Standard 6–8, Hard HL 9–13, Multi-step ≥ 14 marks or ≥ 6 parts. An estimate, labelled so.
* **Sub-topic tagging** (`ingest/maths_tagging.py`): weighted regex rules per sub-topic over question text (×2) and markscheme text (×1); primary tag inside the paper's topic unless another topic scores ≥ 1.5× (that is how calculus inside the Functions papers lands in Topic 5); other strong matches become cross-topic tags. Hand overrides in `tag_overrides.json`.
* **Calendar**: the first weekend programme was laid out from 09:00 with breaks; since then `ibtee/routine.py` fills the calendar from the weekly routine to the end of next month. Missed sessions: `routine.rescue_missed` puts Maths sub-topic blocks in the next Maths slots (chain, never overwriting) and turns anything else into a Catch up to-do; overflow waits in `cal["maths_backlog"]`.

### Authentication

None. It is a local single-user app; `profile.json` holds a display name. Do not expose the Streamlit port to a network as it stands.

### AI integrations and prompts

* **Maths: none at runtime or build time.** All Maths content comes from parsing the PDFs plus the study notes in `ingest/maths_syllabus.py` (written for the app and labelled as such in the UI).
* **Chemistry (build time only)**: `engine/technique_engine.py` (deck prompt with a forced tool schema and deterministic validators), `engine/guide_builder.py`, `engine/foundations_builder.py`, `engine/reference_builder.py`, `engine/web_improver.py`, `ingest/classify.py`. Backend `claude-cli` uses Claude Code on the Pro plan; the API backend is opt-in.

---

## 5. Dependencies and setup

### Requirements

Python ≥ 3.11 (tested on 3.14.6). Key versions in `.venv`: streamlit 1.66.1, pdfplumber 0.11.10, pypdfium2 5.14.0, pandas 3.1.0, altair 6.3.0, tzdata 2026.6, pytest 9.2.0; Chemistry-only: anthropic 2.4.0, rapidocr 3.10.0, onnxruntime 1.31.1, llama-cloud (optional). See `requirements.txt`.

### Install and run (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Rebuild the Maths data (only after changing the PDFs; ~1–2 minutes, no API, no internet):

```powershell
python -m ingest.maths_syllabus      # syllabus + worked-solutions index
python -m ingest.maths_papers        # questions, markschemes, tags
python -m ingest.maths_calculator    # calculator sheets + screenshots
python -m pytest -q tests
```

### Environment variables (all optional; placeholders only)

| Variable | Used by | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY=<your-key>` | Chemistry API backend / classifier | **Leave unset** on the Pro plan, otherwise Claude Code bills the key |
| `LLAMA_CLOUD_API_KEY=<your-key>` | Chemistry LlamaParse parsing | only for re-parsing Chemistry PDFs |
| `IBTEE_ENGINE_MODEL`, `IBTEE_CLASSIFIER_MODEL` | Chemistry engine | model overrides |

### Limitations

* Single user, local files, no authentication or sync. Two browser tabs writing at once are safe for append-only logs but the last calendar/exam save wins.
* Streamlit reruns the script per click: big pages (Chemistry Questionbank) take a few seconds on first load; Maths crops render on first view and are cached.
* Self-marking depends on honesty; there is no automatic answer checking for long questions.

---

## 6. Existing problems

| Kind | Problem | Where |
|---|---|---|
| Source data | `HL_Geometry_and_Trigonometry_Revision_Paper_2_mark_scheme.pdf` is a byte-identical copy of the question paper: 39 questions have **no markscheme**. The app says so on each one. | documents to process/MATHS |
| Source data | 25N.2.AHL.TZ0.1 prints parts totalling 15 marks under "[Maximum mark: 19]". | Stats Paper 2 |
| Source data | No Calculus revision papers; Calculus questions only appear inside other papers (about 80 parts). No IB AI guide, formula booklet, grade boundaries or Paper 3 in the folder. | — |
| Approximation | Sub-topic tags are keyword rules (confidence stored per question). Some parts will be mis-tagged; fix with `tag_overrides.json`. | `ingest/maths_tagging.py` |
| Approximation | Difficulty is estimated from marks/parts, not IB statistics. | `maths/data.py` |
| Incomplete | Chemistry decks exist for 12 of 22 sub-topics; Study guide Learn text for R1.1 only (existing roadmap in CLAUDE.md). | data/techniques, data/guide |
| UI | Chemistry's card component (iframe) and its older CSS stay light in dark mode. | `card_component/index.html`, `chem_app.CSS` |
| UI | Theme switch reloads the page (Streamlit sends its theme only at page load). | `app.py` |
| Redundant | `revision dojo information source/` is an empty React scaffold (no app code); `backups/` holds older copies; `research_notes/` and `reports/` are reference material only. | — |
| Architecture | `chem_app.py` (≈900 lines) and `maths/ui_pages.py` (≈700 lines of code) mix page layout and logic; both would be split per page in a larger team. Chemistry keeps its page in `st.session_state["page"]`, bridged to the URL by `app.resolve_route`. | — |
| Architecture | Two attempt logs with different shapes (Chemistry: one row per MCQ first attempt; Maths: one row per marked part). Home normalises them in `ibtee/home.activity`. | — |
| Redesign rather than reuse | Chemistry's `study_plan.py` scheduler is built around deck "question types" and MCQ variants; Maths uses its own per-part scheduler. A future platform should have one spaced-repetition service with subject adapters (see the integration plan). | — |

---

## 7. Integration recommendations (moving to a bigger platform or another environment)

* **Keep unchanged**: the source PDFs; the append-only logs and their meaning; the build/runtime split (`ingest/*` writes JSON, the app only reads it); the "show the original PDF crop, never retype" rule for questions, markschemes and calculator keys; earned mastery.
* **Reuse directly**: `ingest/maths_papers.py`, `maths_calculator.py`, `maths_tagging.py`, `maths_syllabus.py` (pure Python, no Streamlit); `maths/progress.py`, `schedule.py`, `exams.py`, `data.py`, `render.py` (no Streamlit imports: they can sit behind a FastAPI/Flask API unchanged); the JSON schemas in §4; the design tokens in `ibtee/theme.PALETTES`.
* **Modify**: the UI layer (`ui_pages.py`, `ui_question.py`, `ibtee/home.py`, `app.py`) is Streamlit-specific; in a React/Next.js platform, rebuild the screens and keep the same flows and tokens. Move JSON files to SQLite/Postgres tables with the same columns when there is more than one user.
* **New components needed for a full platform**: accounts and auth; a server API; a database; one spaced-repetition service shared by subjects; teacher-verified sub-topic tags; the IB AI guide and formula booklet (to verify outline wording and mark formulas "in booklet"); Paper 3 investigations; grade boundaries; Calculus question sets; optional AI explanations generated from the files (the Chemistry `engine/` pattern).
* **Compatibility problems when moving environments**: Windows paths and file names with spaces (`documents to process/`); `pypdfium2` native wheels; `zoneinfo` needs `tzdata` on Windows; Google Fonts need internet (fallbacks work); Streamlit `st.button(shortcut=…)`, `st.pills`, horizontal containers need Streamlit ≥ 1.5x; the Claude Code CLI must be installed and signed in for Chemistry builds; `.venv-marker` is a separate GPU environment for Marker OCR.

The comparison table, final folder structure and roadmap are in `docs/INTEGRATION_PLAN.md`.

---

## 8. Changes since the first version of this document

| Area | What changed | Where |
|---|---|---|
| One calendar | All subjects in one Calendar page in the main menu; weekly routine from the student's planning PDF; school, choir events, Chemistry test, mocks and mock revision plan | `ibtee/planner.py`, `ibtee/routine.py`, `data/routine.json`, `data/maths/calendar.json` |
| Board | Browser component: choosing a day, month or Month/Week never reruns Python; sends `{n, action: done/open/edit}` | `calendar_component/index.html`, `ibtee/calendar_view.py` |
| Missed and waiting work | Panel under the board | `planner.catch_up_panel`, `routine.missed_work`, `rescue_missed`, `place_backlog`, `next_free` |
| Fuller Maths notes | Plain-language idea, why it works, worked example with a reason per step, variables and conditions per formula. Hand-written for the app; not rebuilt by ingest | `data/maths/notes/topic1-5.json` → `data.depth(code)`: `{i, h, q, s: [[step, why]], a, f: {formula name: [variables, when]}}` |
| Calculator guides | What it does, when, inputs, how to read the result, checks, difficulty, a task and wrong readings for the drill. Never gives key presses | `data/maths/calculator_guides.json` → `data.guide(id)`: `{lv, ask, what, when, in, read, trap: [], check}` |
| Calculator practice | New "read the result" drill, logged as `{kind: "calc", mode: "read"}` | `ui_pages.output_drill` |
| Mixed practice | Synoptic sets take the six priority links in turn; weak sub-topics come up sooner, mastered ones later, with topics still hidden | `progress.CONNECTIONS`, `by_connection`, `ranked`, `subtopic_weights` |
| Mistake advice | Each mistake type leads to a specific next step on the Overview and in the error log | `progress.MISTAKE_ADVICE`, `mistake_focus` |

| Textbook, in separate sets | Exercise questions paired with worked answers (`book_questions.json`); investigations, inquiry boxes, examples, chapter reviews (`book_investigations.json`); the book's own text, unabridged (`book_notes.json`); teaching passages tagged by sub-topic (`book_passages.json`); publisher's corrections (`book_corrections.json`). All shown as crops of the PDF | `ingest/maths_book_questions.py`, `ingest/maths_book_passages.py`, `ui_pages.book_question_flow`, `book_passage_reader`, `book_feature_view` |
| Source labels | Every question shows Past paper or Textbook, in both subjects. Textbook attempts are logged as `kind: "book"` and never count towards Mastered | `ui_question.PAST_PAPER`, `TEXTBOOK`, `reference.header` |
| Connections | Links between sub-topics with their evidence (past-paper questions, textbook passages, calculator sheets, syllabus notes, the six priority links); "How topics connect" page and a Connections view per topic; calculator sheets linked to the book's matching example | `ingest/maths_connections.py` → `connections.json`, `ui_pages.links_page`, `topic_links`, `connection_section` |

Known content problems in the source sheets, followed by the guides: sheet 10-8 says x = 2 where its screen shows x = 3; sheet 11-15 prints 6.08 where its screen shows 5.657; sheet 1-13 calls the angle at B "C".
Chemistry content still to build: see `CLAUDE.md`, "Filling decks".

