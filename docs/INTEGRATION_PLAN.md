# Integration plan: IB Chemistry app + IB Maths AI HL platform → IB TEE

*7 November 2026. Decisions taken before the build, and how they were carried out.*

## What was compared

* **Existing application**: the Streamlit IB Chemistry HL app (`app.py` → now `chem_app.py`), its decks, scheduler (`study_plan.py`), card component, notes, references and build engine.
* **New requirements**: the Maths AI HL revision platform brief (syllabus hierarchy, learning cycle A–E, calculator mastery, topic past papers, mixed practice, error log, spaced repetition, 3-day calendar, analytics, dark/light, desktop/tablet), and the main menu shown in the RevisionIB-style screenshots (Home · Subjects · Bookmarks · My subjects → Overview · Question bank · Practice exams · Past papers).
* **Resources in the folder**: 8 Maths AI HL revision papers (4 topics × Paper 1/2) with 7 genuine markschemes (one is a duplicate of its question paper), the Oxford fx-CG50 GDC sheets (Chapters 1–14, 86 sheets, master index by syllabus topic, teacher errata), Oxford AI HL worked solutions (Chapters 1–15) and their corrections list. **Not in the folder**: the IB AI guide, the formula booklet, grade boundaries, Calculus papers, Paper 3.

## Comparison table

| Existing functionality | New requirement | Integration decision |
|---|---|---|
| Streamlit app, single subject, sidebar menu of pages | One platform, main menu like the screenshots, several subjects | **Modify**: new shell `app.py` (Home, Subjects, Bookmarks, My subjects, per-subject menus); Chemistry moved to `chem_app.py` with its logic unchanged |
| Chemistry CSS (blue accent, periodic-table tiles) | Clean, minimal academic workspace, dark and light | **Replace** the shell styling with `ibtee/theme.py` (one token set, two palettes); **keep** Chemistry's tiles and card styles inside its pages |
| Chemistry syllabus (`data/syllabus/syllabus.json`, 22 sub-topics) | Maths AI HL hierarchy, 5 topics, original numbering | **New** `data/maths/syllabus.json` (78 sub-topics, SL/AHL); same idea, separate file per subject |
| Chemistry Questionbank: technique cards from decks, MCQ tapping, flow mode | Topic → sub-topic → past-paper questions, attempt before answer, hints, markscheme | **New** Maths question card: Maths questions are long-answer with diagrams, so they are shown as crops of the original PDFs and self-marked per part. The Chemistry card stays for MCQs. The list/filter/navigator layout follows the screenshots |
| `card_component` 7 tricks (command term, disguise, eliminate…) | Hints without giving the answer | **Reuse the principle** (help before the answer, harder help later, help is recorded) in a simpler two-level hint |
| `study_plan.py`: first-attempt log, returns by question type, earned Mastered (3 unaided successes on separate days, one mixed) | Spaced repetition; mastery needs recall + application + unfamiliar questions; 5 levels | **Reuse the rules, re-implement for Maths** in `maths/progress.py`: same "earned, never ticked" philosophy and mixed-session requirement, extended with recall cards and 5 levels. Both logs stay append-only |
| Chemistry flow mode (mixed questions, confusable families) | Mixed-topic bank with topics hidden | **Modify**: Maths mixed practice takes topics in turn and hides the topic until marked; synoptic / cumulative / weekly-review scopes |
| Chemistry notes (`notes.py`: key steps per question type, Hard flag) | Error log with mistake types and concepts | **New** Maths error log (attempt log + `error_notes.json`); Chemistry notes kept as they are |
| `reference.py` definitions, data booklet, grade boundaries | Formula sheets, calculator procedures | **New** formula sheets (LaTeX) per sub-topic; data booklet/boundaries stay Chemistry-only (no Maths booklet or boundaries in the files) |
| `book_view.py` (real book pages cached as PNG) | Use the student's resources, not summaries | **Reuse the pattern** in `maths/render.py` (render once, cache, crop regions) for questions, markschemes, calculator steps and worked solutions |
| `engine/*` (Claude-built decks and guides) | Study content per sub-topic | **Not used for Maths yet**: notes written into `ingest/maths_syllabus.py` so the app works now without spending plan usage; the engine pattern is the route for richer explanations later |
| Progress overview (tiles, priorities) | Dashboard with syllabus progress, analytics | **New** Maths overview + analytics; Home aggregates both subjects |
| — | Calculator mastery centre | **New**: extracted 644 screenshots + step crops with key icons; filters by topic/function/question type/length; practice mode; procedure drill |
| — | Practice exams with timer | **New** `maths/exams.py` |
| — | Revision calendar (Fri–Sun, Atlantic/Canary, editable, no past sessions) | **New** `maths/schedule.py` |
| — | Bookmarks across subjects | **New** `ibtee/store.py`; Save added to Chemistry cards too |
| Chemistry tests (175) | Test the main workflows | **Keep all passing**; add `tests/test_maths.py` (15 logic tests + 21 page-load tests) |

## Unified architecture (final folder structure)

```
app.py                  shell + router  ─┬─ ibtee/ (theme, nav, store, home)      platform, shared
                                         ├─ chem_app.py + guide_ui, card_ui, …    Chemistry HL
                                         └─ maths/ (data, render, progress,        Mathematics AI HL
                                                    schedule, exams, ui_question, ui_pages)
ingest/maths_*.py       build steps → data/maths/*.json         (Chemistry build steps: ingest/, engine/, analysis/, taxonomy/)
data/                   profile.json, bookmarks.json, maths/…, Chemistry files
docs/                   PROJECT_HANDOVER.md, INTEGRATION_PLAN.md
tests/                  test_maths.py + Chemistry tests
```

Adding a third subject = a package like `maths/` with a `render(route)` function and a `NAV` list, a build step in `ingest/`, an entry in `ibtee/store.SUBJECTS` and `CATALOGUE`, and three lines in `app.py`.

## Roadmap

**Done (this integration)**: shell and design system; Maths data pipeline (347 questions, 1,342 parts, 86 calculator sheets, 644 screens, 15 worked-solution chapters, 78 sub-topics); every Maths page listed in the handover; calendar seeded for 6–8 Nov 2026; Chemistry kept working; 194 tests passing.

**Next (in order of value for the student)**
1. Use it: the revision weekend. Fix any wrong sub-topic tag by adding it to `data/maths/tag_overrides.json` and re-running `python -m ingest.maths_papers`.
2. Add the missing Geometry & Trigonometry Paper 2 markscheme PDF (replace the duplicate file, then re-run `ingest.maths_papers`).
3. Add the IB AI guide and formula booklet to `documents to process/MATHS/`: check sub-topic wording and mark formulas "in the booklet".
4. Add Calculus revision papers (Paper 1 and 2) so Topic 5 gets its own question bank; add their entries to `DOCS` in `ingest/maths_papers.py`.
5. Optional richer explanations per sub-topic built from the worked solutions and markschemes with Claude Code on the plan (same pattern as `engine/guide_builder.py`), shown in the Understand tab.
6. One shared spaced-repetition service for both subjects (Chemistry `study_plan.py` and `maths/progress.py` behind one interface), so Home can show a single "today" queue.

**Later, for a multi-user platform**: API layer (FastAPI) over the non-UI modules, database (same schemas), accounts, a React front end using the same design tokens, teacher review of tags and notes.
