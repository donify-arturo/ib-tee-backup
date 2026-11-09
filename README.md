# IB TEE — IB revision platform (Chemistry HL + Mathematics AI HL)

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt
streamlit run app.py
```

Home, Subjects and Bookmarks are in the left menu; open a subject to see its pages. Mathematics AI HL: topics with a learning
cycle (recall → understand → formulas → calculator → past papers → consolidate), question bank, mixed practice, timed practice
exams, past papers by session, Casio fx-CG50 calculator centre, error log, revision calendar and analytics. Rebuild its data after
changing the Maths PDFs with `python -m ingest.maths_syllabus`, `python -m ingest.maths_papers`, `python -m ingest.maths_calculator`.
See `docs/PROJECT_HANDOVER.md` for the full technical handover and `docs/INTEGRATION_PLAN.md` for the plan and roadmap.

The rest of this file documents the Chemistry pipeline.

# IB-TEE — IB Chemistry Examiner Technique Engine

## Quick start on Windows (no PDF processing needed)

The zip already contains the processed library (`data/chunks`, `data/markdown`), the syllabus map, the
examiner-report analysis and the R3.1 pilot deck, so you can open the app straight away.

1. Install **Python 3.11 or newer** from python.org (tick "Add python.exe to PATH").
2. Open PowerShell in the unzipped `ib_tee` folder:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   streamlit run app.py
   ```
   The app opens in your browser. Ticks on "Mastered" are saved to `data\progress.json`.
3. **Fill the decks with your Pro plan (no API credit):**
   - Install Claude Code (https://claude.com/claude-code), run `claude` once and sign in with your
     **Claude Pro account** (not a Console/API account).
   - Make sure no API key is set, otherwise Claude Code bills the key instead of your plan:
     `Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue`
   - Build one deck from the app's **Build decks** page, or all of them from PowerShell:
     ```powershell
     python -m engine.technique_engine --all --allow-partial --backend claude-cli --model opus
     ```
     Sub-topics run most-evidenced first. If your plan's usage limit is reached the run stops
     cleanly; run the same command after the limit resets and it continues where it left off
     (existing decks are skipped; `--force` regenerates). `--model sonnet` uses less of your limit.
     Each run is logged to `data\reports\engine_log.jsonl`.

## Part 1: Syllabus map + multimodal ingestion pipeline

Turns the uploaded IB Chemistry PDFs into syllabus-tagged chunks ready for the
ChromaDB index (Part 2).

```
guide PDF ──► taxonomy/build_syllabus.py ──► data/syllabus/syllabus.json   (22 sub-topics, 165 understandings,
                                                                             AO levels, 18 command terms)
PDFs ──► LlamaParse (per-source prompts) ──► data/markdown/<doc>.jsonl       (cached per page, resumable)
     ──► splitters (regex sub-topic tagging, wrapper stripping)
     ──► link (question ↔ markscheme, textbook ↔ answers)
     ──► classify (Claude, for questions with no header) ──► data/chunks/<doc>.jsonl
                                                         ──► data/reports/coverage.json, missing_markschemes.csv
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export LLAMA_CLOUD_API_KEY=llx-...      # https://cloud.llamaindex.ai
export ANTHROPIC_API_KEY=sk-ant-...     # classifier (defaults to claude-haiku-5-5; override IBTEE_CLASSIFIER_MODEL)
```

Edit `sources.toml` so `uploads_dir` points at your PDFs.

## Run

```bash
python -m taxonomy.build_syllabus "$UPLOADS/46070285-Chemistry_Guide_2025.pdf"   # once
python -m ingest.pipeline --parser llamaparse --classifier claude                # full run
python -m ingest.pipeline --only oxford_2023_excerpt --force-parse               # re-parse one doc
python -m ingest.pipeline --parser local --classifier lexical                    # offline dev run, no keys
python -m pytest -q tests/
```

LlamaParse output is cached per page in `data/markdown/`. A rerun only parses
pages that aren't in the cache. Delete a doc's `.jsonl`, or pass `--force-parse`,
to pay for it again. Each source picks a LlamaParse tier in
`ingest/profiles.py`: `agentic` for the textbook, official papers, data booklet
and question bank, and `cost_effective` for the clean browser-printed
markschemes and the answers file.

## Sub-topic codes

The 2025 syllabus has both **Structure 1.1** and **Reactivity 1.1**, so the
canonical codes are `S1.1` / `R1.1` (sub-topic) and `R1.2.5` (understanding).
The header regex is `taxonomy.SUBTOPIC_HEADER_RE`. It:

* only matches at the start of a line (after optional `#`, a bullet, `**`, or `RUNNING_HEADER:`);
* checks every code against `syllabus.json`, so `Structure 3.4` and a bare `1.1` are rejected;
* treats linking questions (`Structure 2.2—How do …?`) and Oxford margin tags (`Structure 2.1`, `Structure 3.2 25`) as **cross-links**. These are stored in `cross_links` and never switch the current sub-topic.

## Chunk schema (input to Part 2)

```json
{"id": "9f2c…", "text": "…",
 "metadata": {
   "sub_topic": "R1.2", "understanding": "R1.2.5", "theme": "R1", "sub_topics_all": ["R1.2","S2.1"],
   "source_type": "syllabus|textbook|textbook_answers|past_paper|markscheme|data_booklet",
   "origin": "…", "doc_id": "…", "page_start": 20, "page_end": 21, "printed_page": "405",
   "level": "SL|HL|AHL", "question_ref": "17M.2.HL.TZ2.7", "session": "May 2017", "paper": "2",
   "variant": "TZ2", "syllabus_era": "2025|legacy", "question_type": "mcq|structured",
   "has_markscheme": true, "linked_ids": ["…"], "markscheme_origin": "ib_official|question_bank",
   "cross_links": ["S2.1"], "data_booklet_sections": [12],
   "tag_method": "syllabus|running_header|regex_header|data_booklet_map|ref_link|classifier_llm|classifier_lexical",
   "tag_confidence": 0.98, "legacy_only": false}}
```

Question references follow one canonical format, `{YY}{M|N}.{paper}.{HL|SL}.{TZ|paper-code}.{q}`.
That format is what joins a RevisionHub question (`Question 3 from Paper 1 · HL · May 2024 · TZ1`)
to a question-bank markscheme (`24M.1.HL.TZ1.3`) and to the official PDFs.
November sessions have one time zone (`TZ0`). The May 2025 official PDFs only
carry IB paper codes, so `link_by_content` matches question text across sources
and learns the alias (for example `25M.2.HL.TZ3 → 6221`).

## Coverage from the offline test run (text-only parser)

| | |
|---|---|
| Chunks | 2,326 (165 syllabus, 27 data booklet, 126 textbook, 34 answer sections, 555 questions, 1,419 markschemes) |
| Tagged to a sub-topic | 99.9 %, excluding 818 orphan MCQ answer keys (see below) |
| Official papers (Nov 2024, May 2025) | 159 / 159 questions linked to their markscheme |
| RevisionHub question bank (Reactivity HL) | 56 / 372 questions linked; 316 queued in `missing_markschemes.csv` |
| Textbook ↔ Oxford answers | 43 page-level links |

The local parser loses subscripts ("C H" for C₂H₂), figures and LaTeX. That is
expected; the LlamaParse run is the production output. The local run is there
to check that the splitting, tagging and linking logic is correct against the
real files.

## Examiner reports + macro analysis (input to Part 3)

`ingest/reports.py` cuts the 1,962-page subject-report PDF (sessions 2002–2025; it is parsed with
poppler via `parser = "pdftotext"` in `sources.toml`, since the text layer is clean) into:

| source_type | one chunk per | carries |
|---|---|---|
| `examiner_report` | question commented on | `question_ref`, `pct_correct`, `report_answer`, `popular_distractor` when stated |
| `examiner_finding` | bullet in "areas … difficult / well prepared" | `polarity` = difficult \| well_prepared |
| `examiner_overview` | general comments / recommendations per paper | `overview_kind` |

Comments join to questions and markschemes on the same canonical reference. May 2025 reports
say TZ1/TZ2/TZ3 while the official PDFs only print paper codes, so `learn_report_variant_aliases`
matches them by MCQ letters and wording (learned: 1A TZ2→6213, 1A TZ3→6219, 1B TZ3→6220,
P2 TZ2→6215, P2 TZ3→6221). Each alias carries a `high`/`low` confidence flag. The join
copies `pct_correct` etc. onto the question; untagged comments inherit their sub-topic from the
question they discuss, otherwise the classifier tags them.

```bash
python -m analysis.macro            # → data/reports/macro_by_subtopic.json / .csv
```

Per sub-topic: exam frequency, examiner comments, mean % correct quoted by examiners, hardest
questions, difficult vs well-prepared mentions, recurring error phrases with example sentences,
popular wrong MCQ letters, sessions covered, and a 0–100 priority score. `analysis.macro.context_for("R3.1")`
returns the compact block that the Part 3 prompt will include (Pillars 1, 2 and 7).

Limits: reports only discuss selected questions (often the hardest), so % correct is biased low;
old-syllabus Paper 3 (options) is excluded unless `--include-paper3`; the 2001–2002 November
reports have no per-question headings; the item-statistics tables in 2024+ reports are images and
are not read by the text parser.

## Screenshot pages, cover overrides and duplicates

* Pages with no text layer (screenshots/scans) are OCR'd with tesseract by the local parser
  (`local:tesseract`); LlamaParse reads them with vision. On OCR pages the question splitter repairs
  misread numbers ("413." → 13) and tolerates one lost number.
* `[[source.cover_override]]` in `sources.toml` names a paper whose cover shows no readable code
  (page, session, level, paper, code). The three May 2025 screenshot covers in
  `past_paper_w_markscheme_november_and_may_2025.pdf` were identified by matching their text to
  known variants (6209 P2, 6208 P1B, 6207 P1A).
* From 2025 both sessions have several variants, so November papers keep their paper code as the
  variant (pre-2025 November = `TZ0`).
* The same question or markscheme found twice (another PDF, or a screenshot copy of a text page) is
  kept once, preferring the text-layer copy.

## Part 4 — Study app (`app.py`)

* **Overview**: one periodic-table row per theme; each tile shows cards mastered / total, exam
  priority and a green progress bar. Dashed tiles have no deck yet.
* **Study**: the sub-topic's priority, % correct and progress, then the study queue. Each technique
  card opens into the 7 pillars as tabs plus its evidence. Ticking **Mastered** removes the card from
  the queue into a collapsed "Mastered" section (or shows it inline with the toggle off). Filter by
  paper or search.
* **Missing markschemes**: the gate report: which questions per sub-topic can't feed cards yet, with
  an upload box that saves PDFs to `data\inbox\`.
* **Build decks**: runs the engine through Claude Code for one sub-topic.

## Scanned revision books

Image-only books (`source_type = "scan_book"` in `sources.toml`) are read by two free local OCR engines:

```powershell
python -m ingest.scan_ocr rapid              # every page, CPU, about 5 s per page
python -m ingest.scan_ocr marker --topic 5   # chosen old-syllabus topics, GPU, slow but accurate on formulas
python -m ingest.scan_ocr status             # progress; both are resumable
python -m ingest.scan_preview --topic 5      # dry run of splitting and checks, writes nothing
python -m ingest.pipeline --parser local --classifier lexical   # no API credit
```

Marker needs its own environment (`.venv-marker`, see `requirements-marker.txt`). `ingest/scan_books.py` rates each item
green, amber or red (answer key against the library and examiner reports, Marker against RapidOCR, A-D options, equation
balance, recalculated answers, marks, figures). Only green items reach the decks; the rest are listed in
`data/reports/scan_quality.json`, and reviewed items go in `data/scan_corrections.jsonl`. A library copy with a text layer
wins over a book copy, except a green Marker MCQ repairing library text whose formulas were damaged.

## Part 3 — Technique Engine

```bash
python -m analysis.evidence R3.1                         # evidence pack → data/evidence/R3.1.json
python -m engine.technique_engine --gate-report          # markscheme gate for every sub-topic
python -m engine.technique_engine R3.1                   # pauses if any question lacks a markscheme
python -m engine.technique_engine R3.1 --allow-partial   # skip those questions instead (recorded on the deck)
python -m analysis.render_cards R3.1                     # readable deck → data/techniques/R3.1.md
```

The engine sends a trimmed evidence pack (about 160k characters: up to 120 questions with markschemes
and examiner comments, trap lines, examiner error sentences, findings, syllabus statements and
data-booklet sections) to `claude-fable-5-1` (override with `IBTEE_ENGINE_MODEL`). It forces a tool
schema, so the output is always the deck JSON the UI reads. Deterministic checks then confirm that every
evidence ref exists, that MCQ letters match the key, that cited booklet sections exist, and that
formulas the card says are "in the booklet" really are. Cards with a problem get
`status.needs_review = true`. Re-running keeps each card's `status.mastered` (matched by id, or by a
near-identical title).

`data/techniques/R3.1.json` is the pilot deck (13 cards, 72 evidence refs, all checked), written to
the same schema by hand-mining the R3.1 evidence pack. It is the reference for judging Fable's output.

## Gaps in the current source set

* **The question-bank markscheme files come from a different question selection than the
  question-bank print.** 696 of their 1,258 entries are SL and roughly 45 % of the written ones
  classify as Structure. 818 entries are bare Paper 1 MCQ letters whose questions aren't in the
  uploaded print (Reactivity, HL); they are kept but flagged `orphan_answer_key`. Export the
  markschemes from the same RevisionHub filter as the question print (or upload the matching
  question prints) to close the 316-question gap.
* **No markschemes for 2000–2015 or 2023 questions.** The question-bank markschemes only cover 16N–22N.
* **Nov 2024 papers are old-syllabus papers** (`syllabus_era: legacy`). The first 2025-syllabus exams were May 2025 (Papers 1A, 1B, 2).
* The Oxford excerpt covers Reactivity 1 and the start of Reactivity 2.1 only.

## Files

```
taxonomy/build_syllabus.py   guide PDF → syllabus.json (column-aware: linking questions kept separate)
ingest/taxonomy.py           codes, header regex, cross-link + data-booklet reference detection
ingest/profiles.py           LlamaParse tiers + custom prompts per source type
ingest/parsers.py            LlamaParse (llama-cloud ≥1.0, parse v2 API) + pdfplumber fallback, page cache
ingest/refs.py               canonical question references
ingest/splitters.py          one splitter per source type (wrapper stripping lives here)
ingest/data_booklet_map.py   data booklet section → sub-topics
ingest/link.py               question↔markscheme, content-based variant matching, textbook↔answers, tag propagation
ingest/classify.py           Claude tool-use classifier (prompt-cached syllabus) + lexical fallback
ingest/pipeline.py           CLI
tests/test_ingest.py         regex, reference and splitting tests
```
