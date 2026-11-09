# IB TEE — notes for Claude Code

Personal IB revision platform with two subjects: **Chemistry HL** (2025 syllabus: past papers, markschemes and examiner reports
turned into "technique cards" per sub-topic) and **Mathematics AI HL** (the student's revision papers, Oxford fx-CG50 calculator
sheets and worked solutions). Streamlit, local JSON files, one user.
The user is a student on Windows with a Claude Pro plan: never use paid API credit unless asked.
Full handover: `docs/PROJECT_HANDOVER.md`; integration decisions and roadmap: `docs/INTEGRATION_PLAN.md`.

## Platform
- `app.py` — the shell: page setup, light/dark theme, left menu (Home · Subjects · Bookmarks · open subject's pages · My subjects), router. Run: `streamlit run app.py`
- Network: `.streamlit/config.toml` keeps the app on this computer (`server.address = "localhost"`). `Open IB TEE on home Wi-Fi.bat` → `run_on_home_wifi.ps1` opens it to other devices only on a Wi-Fi confirmed as home (`data/trusted_wifi.txt`) and refuses school-type networks. Never publish this project: it holds the student's books and personal data, and it can't run on Vercel.
- Look: own "lab notebook" identity (navy sidebar, graph-paper canvas, teal accent, Space Grotesk / Inter / IBM Plex Mono); change it only in `ibtee/theme.py` + `.streamlit/config.toml`.
- Maths is organised per topic: Overview · Topics 1–5 (hubs: Sub-topics, Questions, Calculator, Mistakes, Progress) · Mixed/exams/past papers · Error log · Calculator · Calendar. Views live in the URL (`&v=`).
- Calendar (main menu, `?p=calendar`, `ibtee/planner.py`): one calendar for every subject. The board is a browser component (`calendar_component/index.html`, `ibtee/calendar_view.py`, inside an `st.fragment`): choosing a day, month or Month/Week never reruns Python and the day's tasks show beside the grid; only ticks, Open and "Edit this day" (the editable table under the board) talk to the server. Weekly routine is a separate view. The weekly routine comes from `documents to process/Planning Arturo (Calendar).pdf` → `data/routine.json` (`ibtee/routine.py`) and fills the calendar to the end of next month; edited, done or moved sessions are never regenerated. Sessions live in `data/maths/calendar.json` (kept there for history) with a `subject` field (missing = maths). School 08:30–15:30 Mon–Fri. Events (type `busy`: rehearsals, concerts — choir timetable from `documents to process/Horario Coro .jpeg`) make room for themselves (`routine.clear_for_event`): overlapping routine blocks go, unfinished Maths moves to the next Maths slot after it (displaced work chains forward, overflow waits in `maths_backlog`), other subjects become "Catch up" to-dos. Never overwrite a Maths slot's sub-topics. Under the board, `planner.catch_up_panel` moves missed sessions (`routine.rescue_missed`) and lists Maths blocks waiting in `maths_backlog` (`routine.place_backlog`). Exams: Chemistry test Tue 10 Nov (R1.1–R2.1, time to confirm) with prep sessions (`chem_topic` opens the Questionbank or Study guide); Y13 mocks 26 Nov–1 Dec from `documents to process/MOCK TIMETABLE.jpeg` (`mock: true`; only Arturo's subjects: Spanish A, Psychology, Biology, Maths AI, Chemistry, English A). Mock revision plan 16–30 Nov: routine slots re-assigned per subject (`mock_prep: true`, programme "Mock revision"); IA and Global Issue paused on Sun 22/29 with catch-up to-dos on 2 and 5 Dec.
- `ibtee/` — `theme.py` (design tokens + helpers), `nav.py` (route in the URL: `?s=<subject>&p=<page>`), `store.py` (`data/profile.json`, `data/bookmarks.json`, catalogue), `home.py` (Home, Subjects, Bookmarks).

## Mathematics AI HL
- Build (no API, offline): `python -m ingest.maths_syllabus`, `python -m ingest.maths_papers`, `python -m ingest.maths_calculator`, `python -m ingest.maths_book` (course book in `MATHS/WORKED ANSWERS`) → `data/maths/{syllabus,questions,calculator}.json` + `calculator_screens/`.
- `ingest/maths_tagging.py` keyword rules tag parts with sub-topics; `data/maths/tag_overrides.json` ({"<qid>": ["1.12"]}) wins.
- Questions, markschemes, examiners reports and calculator steps are shown as crops of the original PDFs (`maths/render.py`). Never retype button sequences: the sheets print keys as icons.
- `maths/progress.py` — `data/maths/attempts.jsonl` (append-only: never overwrite or delete), mastery levels (earned, never ticked), recall SRS, retries, error log. `maths/schedule.py` — `data/maths/calendar.json` (Atlantic/Canary; never schedule the past; the current month is planned once, never overwritten). The board is used on Home (compact) and on Calendar. `maths/exams.py` — `data/maths/exams.json`.
- `HL_Geometry_and_Trigonometry_Revision_Paper_2_mark_scheme.pdf` is a copy of the question paper: those 39 questions have no markscheme. There is no Maths guide, formula booklet, Calculus paper or grade boundaries in the folder: the app must not pretend otherwise.
- Study notes in `ingest/maths_syllabus.py` were written for the app (labelled so in the UI); everything else comes from the student's files.
- Textbook, kept in separate sets by `python -m ingest.maths_book_questions` (the PDF is in `MATHS/WORKED ANSWERS/TEXTBOOK`): `book_questions.json` (exercise questions + worked answers, as PDF regions), `book_investigations.json` (investigations, Developing inquiry, worked examples, chapter reviews), `book_notes.json` (the book's own text per section, unabridged). Book questions stay apart from past papers, are logged as `kind: "book"` and never count towards Mastered. Every question shows a Past paper or Textbook label.
- `python -m ingest.maths_book_passages` → `book_passages.json` (the book's teaching cut at its own headings, tagged with sub-topics, shown as crops first in step 2 Learn) and `book_corrections.json` (the publisher's corrections, shown as printed on what they correct). `python -m ingest.maths_connections` → `connections.json`: links between sub-topics, each with its evidence.
- Fuller notes `data/maths/notes/topic1-5.json` (`data.depth`) and calculator guides `data/maths/calculator_guides.json` (`data.guide`) are hand-written for the app and not rebuilt by ingest. Guides explain each procedure but must never give key presses. The PDF text loses minus signs: check values against the screens or work them out.
- `progress.ranked` / `by_connection`: mixed sets lean towards weak sub-topics and the six priority links while keeping topics hidden. `progress.mistake_focus`: what each mistake type should change.

## Chemistry HL
- `chem_app.py` — the Chemistry pages (the original app; `render(page)` is called by the shell). Pages: Overview (Progress), Questionbank (past papers only: filters, flow mode, question headers, Mastered), Study guide (the books), Tips & my notes, Key definitions, Data booklet, Grade boundaries, Missing markschemes, Build decks. Its page lives in `st.session_state["page"]`, mirrored to the URL by `app.resolve_route`.
- `guide_ui.py` — the Study guide page: per syllabus understanding, tabs Learn (`data/guide`, falls back to `data/reference` notes), Book pages (real pages via `book_view.py`, cached in `data/books/page_images`), Worked examples, Try it (book questions, reprints listed apart), Past papers (links to Questionbank cards). Nothing there is scored.
- `engine/guide_builder.py` → `data/guide/<code>.json`: full explanations per understanding from both books (Sonnet via claude-cli; `--force` to rebuild).
- `data/extra_questions.json` — library questions checked by hand and shown in the Questionbank beyond a deck's cards.
- `reference.py` + `engine/reference_builder.py` — grade boundaries from the reports, booklet text, and notes/definitions built from the textbook into `data/reference/`.
- `ingest/book_pages.py` → `data/books/companion/<code>.json`: the full Oxford Course Companion and its answers, split by sub-topic
  (the book's skills chapter goes to `TOOLS.json`). Notes/definitions (`engine/reference_builder.py`) read it, the excerpt is a fallback.
- `ingest/prepared_pages.py` → `data/books/prepared/<code>.json` (+ T1-T3, IA, EXAM): Oxford IB Prepared (OCR text, noisy formulas)
  with its publisher's answers from the .docx files. Private study only: paraphrase, never reprint.
- `engine/foundations_builder.py` → `data/foundations/<code>.json`: the Study guide's questions (both books' practice and worked examples,
  the books' practical items with their answers, the guide's Tool/Inquiry prompts with Claude's answers). Sonnet via claude-cli.
  Never counts towards Mastered. Its `issues` list needs a human look. Book questions stay apart from past papers: items the books
  reprinted from IB papers get `past_paper_ref` (matched to library questions by numbers and wording) and show under their own tab.
  Book content never enters `data/chunks`, decks or the Questionbank. `ingest\after_reset.ps1` waits for a usage reset, builds missing
  Foundations, then runs `fill_decks.ps1` (one copy only).
- `study_plan.py` — first-attempt log, when each question type returns, today's mixed session. Returns use fresh library questions, shown at run time and never copied into decks.
- `card_ui.py` + `card_component/index.html` — the interactive question card (a two-way Streamlit component; tappable answers, the 7 tricks as buttons inside the question: basic, more, why; clickable cycles).
- `engine/technique_engine.py` — builds a deck for a sub-topic. Use `--backend claude-cli` (Claude Code on
  the user's plan), never the API backend by default.
- `analysis/evidence.py` — evidence pack per sub-topic (questions + markschemes + examiner comments).
- `analysis/macro.py` — examiner-report statistics per sub-topic → `data/reports/macro_by_subtopic.json`.
- `ingest/` — PDF pipeline (only needed when new PDFs are added; see README).
- `data/syllabus/syllabus.json` — 22 sub-topics, 165 understandings. Codes are `S1.1`…`R3.4` (never bare `1.1`).
- `data/techniques/<code>.json` — decks the app shows. `R3.1.json` is the hand-checked reference deck:
  match its depth and style.
- `data/progress.json` — hand Mastered ticks, used only by older cards with no worked question; other cards earn Mastered from `data/attempts.jsonl` (`study_plan.mastery`). Never overwrite or delete it.
- `data/attempts.jsonl` — every first attempt, append-only. Never overwrite or delete it. `data/study_plan.json` holds the exam date and session settings.
- `data/notes.json` — the student's own notes (`notes.py`), key steps by question type. Never overwrite or delete it.
- `engine/web_improver.py` + `web_tips.py` — web research per card; `data/web_tips.json` holds tips and the student's accept/reject
  decisions (never overwrite it). Web text is never evidence of what examiners reward; tips reach a card only once accepted.

## Filling decks (main remaining job)
```
python -m engine.technique_engine --all --allow-partial --backend claude-cli --model opus
```
Resumable: skips existing decks; stops cleanly at the plan's usage limit; rerun later to continue.
Check each new deck: `validation_issues` in the JSON should be empty; then `python -m analysis.render_cards <code>`.

## Rules for card content
- Every claim must cite evidence refs that exist in the library (the validator checks).
- Paraphrase markschemes and reports; never copy question text.
- Data booklet: pH, pOH, Kw and n = CV are in section 1; Kw's value in section 2. pH + pOH = 14,
  pKa + pKb = 14, Ka × Kb = Kw and the buffer equation are NOT in the booklet.
- Lewis acid/base belongs to R3.4, not R3.1.

## Tests
`python -m pytest -q tests` (engine tests use a stand-in, no real calls; the 2 CLI tests skip on Windows so a real `claude` is never run;
`tests/test_maths.py` loads every Maths page with AppTest, using a temporary calendar and exams file).
