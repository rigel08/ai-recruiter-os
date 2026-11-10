# Session progress report

Snapshot taken Tuesday 10 November 2026, 06:16 IST, by inspecting the repository, running the tests and calling the running app. No code was changed to produce it.

## The short version

- **One 2.0 feature is built: facts with evidence (M1).** Everything else on the 2.0 list is either the unchanged 1.0 behaviour or not started.
- **Six of the ten features asked about have no 2.0 code at all.** Four of them (candidate comparison, vacancy management, dashboard, PDF export) are not on the roadmap either, because the 2.0 brief that presumably defines them never reached this session.
- **All work is committed** on branch `v2` at `00520d2`. This report file is the only uncommitted change.
- **137 tests pass, none fail.** The app starts and works in the browser.
- **Nothing has been measured on real resumes.** Every accuracy check uses synthetic data written alongside the rules.

## 1. Overall progress

**Completed**

| Item | State |
|---|---|
| Git repository, `v1-baseline` tag on `main`, `v2` branch | Done |
| 2.0 plan: audit, innovation strategy, architecture, roadmap | Written (documents, not functionality) |
| M1: extraction of 7 fields with evidence quotes and an "ask on the call" list | Built, tested, checked in the browser |
| M1 audit and four bug fixes | Done ([m1-audit.md](m1-audit.md)) |
| Experienced-hire sample set (6 fictional resumes) | Done |
| Labelled test set (75 synthetic cases) and report script | Done |

Earlier in the same session, before the baseline commit: the market research in `research/market-validation/` and the local outreach dashboard in `outreach/`.

**Partially implemented**

- **CSV export:** works with the new columns, but is built in the page's JavaScript and has no automated test.
- **Candidate evaluation:** the 1.0 skill score and Shortlist, Maybe, Not a fit. It ignores every extracted fact.
- **Job description parsing:** 1.0 finds skills in the job description. It doesn't read limits such as notice period, budget, location or years.

**Not started**

Client requirements (M2), the call sheet as a printable page (M2), client tracker templates and XLSX (M4), duplicate detection (M4), message intake (M5), experience from dates and the optional model pass (M6), hosting and access control (M7), candidate comparison, client submission generator, vacancy management, a product dashboard, PDF export.

## 2. Feature-by-feature status

| Feature | Status | What exists | What's missing |
|---|---|---|---|
| Resume extraction | **Built (M1)** | Phone, total experience, notice period, current CTC, expected CTC, current location, preferred location. Rule-based, Indian formats | Current employer, designation, relevant experience, education, experience from dates. Not run on real resumes. PDF and DOCX extraction rely on the 1.0 parser and were not re-checked with real files |
| Evidence traceability | **Built (M1)** | Every fact carries the exact resume line. Two tests prove quotes are verbatim and each value can be re-read from its quote | No line number or page reference. No highlighting in the original file. Skill matches and the score have no quotes |
| Job description parsing | **1.0 only** | Skills found by vocabulary; must-haves typed by the recruiter | No reading of notice, budget, location or years from the job description |
| Client requirements | **Not started** | Only the 1.0 minimum CGPA and must-have skills | Limits on notice, CTC, location, years; pass, near-miss, ask. This is M2 |
| Candidate evaluation | **1.0 only** | Score: 60% must-haves, 30% other skills, 10% wording overlap. Three decisions | Facts don't affect score or rank. Limit-breaking text can raise the score slightly (see section 4) |
| Candidate comparison | **Not started** | A ranked table | No side-by-side view. Not on the roadmap |
| Client submission generator | **Not started** | A fixed-column CSV | No client templates, no XLSX, no formatted profile. Roadmap M4 and M7 |
| Vacancy management | **Not started** | Nothing: the app keeps no data between requests | Needs storage design. Not on the roadmap |
| Dashboard | **Not started** | None for the product. The outreach dashboard is a separate sales tool and doesn't count | Not on the roadmap |
| CSV/PDF exports | **CSV built, PDF not started** | 13-column 1.0 CSV unchanged; 23-column CSV with the switch on (facts, ask, notes, evidence) | No automated test for CSV. No PDF export at all |

## 3. Technical changes

Compared with `main` (`v1-baseline`): **28 files changed, 2,005 lines added, 19 removed. No files deleted.**

**Created (21)**

- `app/services/facts.py` (495 lines): the extractor
- `app/samples/experienced/`: one job description and six resumes
- `evals/`: `__init__.py`, `facts/__init__.py`, `facts/__main__.py`, `facts/run.py`, `facts/gold.json`
- `tests/test_facts.py` (34 tests), `tests/test_facts_eval.py` (5 tests)
- `docs/v2/`: `README.md`, `audit.md`, `innovation-strategy.md`, `architecture.md`, `roadmap.md`, `m1-audit.md`

**Modified (7)**

- `app/schemas/screening.py`: new `Fact` and `CandidateFacts` models; new fields on existing models
- `app/services/screening.py`: calls the extractor; adds coverage counts
- `app/api/routes/samples.py`: `kind` parameter
- `app/static/index.html`: the switch, the facts column, evidence list, extra CSV columns
- `tests/test_api.py`: 5 new tests
- `README.md`, `.dockerignore`

**Architecture**

- One new pipeline stage, "extract facts", between parsing and ranking. It is additive: ranking code is untouched.
- The planned stages (limits, de-duplication, templates, intake, model layer) exist only in [architecture.md](architecture.md).

**APIs and components**

- **No new endpoints.**
- `POST /api/screenings` response gains `facts` and `to_ask` per candidate and `fact_coverage` overall. All 1.0 fields are unchanged.
- `GET /api/samples` accepts `?kind=experienced`. Default behaviour is unchanged.
- One new page control: "Hiring experienced candidates". With it off, the page and CSV match 1.0.

**Database and persistence**

- **None for the screening app.** It is still stateless.
- The outreach dashboard's SQLite file (`outreach/data/outreach.db`) is unchanged by 2.0 work and is git-ignored.
- The browser remembers the switch position in local storage.

## 4. Testing

| Measure | Result |
|---|---|
| Tests passing | 137 |
| Tests failing | 0 |
| Tests before 2.0 | 93 (68 screening, 25 outreach) |
| New tests | 44: `test_facts.py` 34, `test_facts_eval.py` 5, `test_api.py` 5 |
| Labelled set | 75 synthetic cases: 62 expected values found, 0 missed, 0 wrong |

**Checked by hand in the browser**

- Switch off: same 7 columns and 13-column CSV as 1.0, with the campus sample.
- Switch on, experienced sample: facts column, "ask on the call", evidence list (27 items, all with text), coverage line.
- CSV with the switch on: 23 columns on every row, number columns numeric only, byte-order mark present.
- Light and dark mode; no console errors; no sideways page scroll at phone width.
- A live call to the running server returned the expected counts at the time of this report.

**Not checked**

- Real resumes of any kind.
- PDF or DOCX uploads through the page since the 2.0 changes (the 1.0 API tests still cover parsing).
- Safari or Firefox. Opening the CSV in Excel or Google Sheets.
- The Docker image (never built).

**Known bugs and limitations**

1. **Facts don't affect ranking.** Tanvi scores 85 and ranks second with no facts found. Lakshmi (90 days, 26 LPA, Chennai) is shortlisted against a job that states 60 days, 24 LPA and Hyderabad.
2. **Limit-breaking text can raise the score.** Adding a 90-day notice period, 40 LPA and Delhi to Tanvi's resume moved her from 85 to 86, through the 10% wording-overlap part.
3. **A known miss:** Imran's "Location: Hyderabad" is skipped because a bare "Location:" is trusted only in the first 12 lines.
4. **Experience can be per skill.** "4 years of experience in Node.js, 2 years in Java" returns 4, flagged for confirmation.
5. **"Serving notice" has no day count,** even when a last working day is given.
6. **Phone numbers:** Indian mobiles only.
7. **Two-column PDFs** may come out with lines interleaved, which would hurt line-based rules. Untested.
8. **The page's rendering and CSV code has no automated tests.**
9. **No access control, upload size cap, per-file time limit or rate limit.** Acceptable on a laptop; not for a hosted copy.
10. **The sample set has no unreadable file and nobody in "Not a fit".**
11. **The server doesn't reload Python changes by itself.** Restart it after editing `app/`.

## 5. Git status

| Item | Value |
|---|---|
| Current branch | `v2` |
| Latest commit | `00520d2` (`00520d276c97d995f4657df2a35373399f8a736a`), "M1 audit fixes…", 10 Nov 05:28 |
| Other branches and tags | `main` at `0a60f50`, tagged `v1-baseline` |
| Uncommitted changes before this report | None: the working tree was clean |
| Uncommitted changes now | This file only |
| Stashes | None |
| Remote | **None.** The repository exists only on this laptop |

All code and earlier documents are committed. **They are not backed up anywhere.** `research/` and `outreach/seed/` contain named business contacts, so use a private remote if you add one.

Commits on `v2`, oldest first: `0a60f50` baseline, `c437ba1` plan, `ab7a1a6` M1, `00520d2` M1 audit fixes.

## 6. Application status

**It starts and works.** Both servers were answering at 06:16.

| App | Start command (from the repository root) | URL |
|---|---|---|
| Screening app | `.venv/bin/uvicorn app.main:app --port 8765` | http://localhost:8765 |
| Outreach dashboard | `.venv/bin/python -m outreach` | http://127.0.0.1:8770 |

The screening app currently running was started by this session's preview and may stop when the session ends. Use the command above to start it again.

**What you can do in the browser today**

1. Paste a job description, type must-have skills, upload up to 200 PDF, DOCX or TXT resumes, and get a ranked list with Shortlist, Maybe or Not a fit.
2. Tick "Hiring experienced candidates" to see each resume's phone, experience, notice period, CTC and location, the exact line each came from, and what to ask on the call.
3. Press "Try it with sample data" for a demo: campus resumes with the switch off, experienced resumes with it on. `http://localhost:8765/?demo=1` runs it straight away.
4. Download the CSV, or copy shortlisted emails.

**What you can't do:** set client limits, compare candidates side by side, save a vacancy, produce a client-format tracker or a PDF, or see any history.

**Outreach dashboard records at 06:16:** 10 researched, 7 marked contacted, 0 replies, 0 calls booked. Those entries are yours; this session sent nothing and can't tell whether the 7 were real sends.

## 7. Remaining work before 13:30

About 7 hours remain. **This session was never told what the 13:30 deadline requires,** so "must" below is a recommendation, not a known requirement.

**Should be done first**

1. Back up the repository to a private remote or another disk. It has one copy.
2. Commit this report.
3. Share the 2.0 brief, so the next session builds what it asks for.

**Realistic in the time (my estimate, not a measurement)**

- **M2 core:** fields for maximum notice, CTC cap, locations and minimum years; pass, near-miss or ask per candidate; shown in the table and the CSV; tests and a browser check. This removes known bugs 1 and 2 from any demo.
- **Small fixes:** the bare "Location:" miss; two more samples (an unreadable file and a clear "Not a fit").

**Postpone**

- Vacancy management and a product dashboard: both need storage design, which doesn't exist yet.
- Client submission generator, XLSX and PDF export: gated on seeing a real client tracker.
- Candidate comparison view.
- WhatsApp intake, the model layer, hosting and access control.

Trying to touch all ten features in 7 hours would produce mock-ups, not working features.

## 8. Honest completion assessment

**Yardstick:** 100% means an agency could rely on the feature for a live requirement today. Percentages are my judgement. Documents and plans count for nothing here.

| Feature | Implemented in code | Automated tests | Checked in browser | Completion |
|---|---|---|---|---:|
| Resume extraction | 7 fields, rules | Yes, synthetic only | Yes, 6 text samples | 45% |
| Evidence traceability | Quotes for all facts | Yes | Yes | 70% |
| Job description parsing | 1.0 skills only | 1.0 tests | Yes | 15% |
| Client requirements | No (1.0 CGPA and must-haves only) | No | No | 5% |
| Candidate evaluation | 1.0 skill score; facts unused | 1.0 tests | Yes | 30% |
| Candidate comparison | Ranked table only | No | No | 10% |
| Client submission generator | Fixed CSV only | No | CSV by hand | 10% |
| Vacancy management | No | No | No | 0% |
| Dashboard | No | No | No | 0% |
| CSV export | Yes | **No** | Yes, by hand | 75% |
| PDF export | No | No | No | 0% |

**Overall 2.0 against these ten features: roughly 20 to 25%.** One feature is solid, two lean on 1.0, and the rest are not built.

**Why the two highest numbers aren't higher**

- **Extraction, 45%:** zero real resumes tested, five common tracker fields missing, and PDF layout risk unmeasured.
- **Traceability, 70%:** a quote is shown but not located (no line or page), and nothing outside the seven facts has evidence.

## To resume safely in another session

1. `cd ~/ai-recruiter-os`, confirm `git status` is clean and the branch is `v2` at `00520d2` (or later if this report was committed).
2. Run `.venv/bin/python -m pytest -q` and expect 137 passed.
3. Read [README.md](README.md) in this folder, then [m1-audit.md](m1-audit.md), then [roadmap.md](roadmap.md).
4. Start at M2. Do not change `app/services/scoring.py` or `suggestions.py` behaviour for 1.0 inputs: the 1.0 tests pin it.
