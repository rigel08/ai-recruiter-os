# Session progress report

Snapshot taken Tuesday 10 November 2026, after the M2 session. It replaces the earlier snapshot from the same day (in git history at `6acdd9f`).

## The short version

- **M2 is built and working:** requirements are read from the job description for the recruiter to edit, and every candidate is checked against them on three separate dimensions.
- **273 tests pass, none fail** (137 before this session).
- **Checked in the browser** with the switch off and on, including real PDF and DOCX uploads, unreadable files, edited requirements, comparison, CSV and phone width.
- **Still true:** nothing has been tried on real resumes or real job descriptions. All data is synthetic.
- **Not built:** typing call answers back in, client tracker templates, PDF export, vacancy management, a product dashboard, storage of any kind, hosting.

## 1. What existed before this session

Branch `v2` at `00520d2`, 137 tests passing:
- The 1.0 screening app (skills and CGPA ranking for campus hiring).
- M1: seven facts extracted from each resume with the exact source line, and an "ask on the call" list.
- The local outreach dashboard and the market research.

Its known weakness: facts didn't affect evaluation at all. A resume with no facts ranked second, and a candidate who broke every client limit stayed shortlisted.

## 2. What this session added

**M1 fixes (commit `8eee1c3`)**

| Issue | Fix |
|---|---|
| A bare "Location:" lower down was missed | Accepted when a neighbouring line is another personal detail (CTC, notice, phone). A past job's location is still ignored |
| Per-skill experience figures gave a misleading total | "4 years in Node.js, 2 years in Java" now returns no total and goes on the ask list. A stated total still wins. A labelled total no longer reads across a full stop (a bug found on the way) |
| Serving notice | Confirmed it never becomes a number of days; now tagged so the evaluation says "check by hand" |
| Two-column PDFs came out interleaved | Reproduced with a test PDF (the notice period was lost and the name read as "Divya Rao Summary"). Pages saved row by row are now read column by column, with guards for label/value rows and right-aligned dates |
| Unreadable files | `.doc` and photo uploads now say what to do. Damaged, scanned and oversized files already had clear messages |
| Ranges | Notice and CTC ranges keep both ends, so "18–24 LPA" against a 20 LPA budget is a near match, not a failure |

**M2 backend (commit `d622062`)**

- **Job-description reader** (`POST /api/requirements`): required skills, preferred skills, minimum and maximum experience, longest notice period, CTC budget, locations and other stated conditions. Each value carries its sentence and is marked `explicit` or `suggested`. Vague wording ("around", "preferred", only mentioned) is never treated as a hard requirement.
- **Evaluation** (`hiring_mode=experienced` on `POST /api/screenings`): each candidate gets
  - **skills and experience fit:** 70% required skills, 30% preferred skills, no wording-overlap part; plus an experience check
  - **client limits:** notice, CTC and location, each Meets, Near match, Does not meet, Unknown or Check by hand, with a reason that states the numbers
  - **information:** how many of six tracker fields the resume states
  - **next step:** Looks ready, Clarify first, Check by hand, Conflicts with a limit or Low skills fit. It reports the most serious finding and never hides a conflict
- **Order** follows the next step. Nobody is removed or rejected.
- **CSV on the server** (`POST /api/exports/csv`), so it's covered by tests.
- **City list** of about 40 Indian cities with alternative names and some localities.
- **Two more sample resumes:** a strong candidate who breaks every limit, and a low skills fit.

**M2 frontend (commit `1a4bfe3`)**

- A "Client requirements" block with "Fill from the job description". Explicit values go into editable boxes with their source sentence. Suggested values stay out until the recruiter clicks "Use it".
- Results show Next step, Skills and experience, Client limits and Information on the resume as separate columns. Tabs filter by next step.
- Tick two to four candidates for a side-by-side table.

## 3. Files

Since the `m2-start` tag: **24 files changed, 2,521 lines added, 147 removed. None deleted.** Documentation changes are on top of that.

**Created (12)**
- Code: `app/services/requirements.py`, `evaluation.py`, `locations.py`, `export.py`; `app/api/routes/requirements.py`, `exports.py`; `app/schemas/requirements.py`
- Samples: `app/samples/experienced/resumes/rohit_verma.txt`, `neha_kapoor.txt`
- Tests: `tests/test_requirements.py`, `test_evaluation.py`, `test_export.py`

**Modified**
- `app/services/facts.py`, `parsing.py`, `screening.py`
- `app/api/routes/screenings.py`, `app/main.py`, `app/schemas/screening.py`
- `app/static/index.html`
- `tests/test_api.py`, `test_facts.py`, `test_parsing.py`, `helpers.py`
- `evals/facts/gold.json`
- `README.md`, `docs/v2/README.md`, `docs/v2/roadmap.md`, this file

**Untouched:** `app/services/scoring.py`, `suggestions.py`, `skills.py`, `academics.py` (the 1.0 ranking), and everything under `outreach/`.

**Persistence:** still none in the screening app. No database was added.

## 4. Tests

| Measure | Result |
|---|---|
| Passing | **273** |
| Failing | **0** |
| Before this session | 137 |
| New this session | 136 |
| Labelled extraction set | 81 synthetic cases: 68 expected values found, 0 missed, 0 wrong |

| File | Tests | Covers |
|---|---:|---|
| `test_evaluation.py` (new) | 60 | Notice, CTC, location and experience statuses; ranges; conflicts; serving notice; the three dimensions; next step; order |
| `test_requirements.py` (new) | 38 | Skill, experience, notice, pay and location wording; explicit against suggested; ambiguous and silent job descriptions; the API |
| `test_export.py` (new) | 7 | Campus CSV matches 1.0 byte for byte; experienced CSV; formula guard; endpoint errors |
| `test_api.py` | 35 (16 new) | Experienced sample end to end; recruiter edits; validation; campus result pinned to the `v1-baseline` tag; unreadable files |
| `test_facts.py` | 43 (9 new) | Regression tests for each M1 fix |
| `test_parsing.py` | 14 (6 new) | Two-column PDFs; `.doc` and photo messages |
| Others | 76 | Unchanged 1.0 and outreach tests |

**V1 regression:** a test runs the campus sample and compares names, decisions and scores with the output of the code at the `v1-baseline` tag. They match.

## 5. Browser checks done

All with synthetic data, in the app's built-in browser:

| Check | Result |
|---|---|
| Switch off, campus sample | Same 7 columns, tabs and counts as 1.0. No requirements block |
| Switch on, experienced sample | Requirements filled from the job description with source sentences; 8 candidates in 5 next-step groups |
| Editing requirements | Changed notice to 30, CTC to 20, locations to "Hyderabad, Pune"; results followed the edited values |
| Real file uploads through the form | A PDF, a DOCX and a two-column PDF were read correctly |
| Unreadable files | `.doc`, damaged PDF, empty PDF and `.jpg` each listed under "Need a manual look" with a reason |
| Evidence | "Where each value came from" shows the exact resume line per fact |
| Missing information | Shown as Unknown with "ask on the call", not as a failure |
| Comparison | One ticked: prompt for another. Three ticked: side-by-side table |
| CSV | Downloaded from the server: byte-order mark, 27 columns, one row per file including unreadable ones |
| Validation | Minimum above maximum experience shows a plain message; out-of-range numbers are blocked by the browser |
| Phone width (375 px) | No sideways page scroll. The results table scrolls inside its own box |
| Console | No errors, apart from the expected 422 from the deliberate validation test |

**Not checked:** light mode after the M2 changes, Safari or Firefox, opening the CSV in Excel or Google Sheets, the operating system's file picker (files were attached by script, the same path drag-and-drop uses), the Docker image.

## 6. Known bugs and limitations

1. **No real data.** Extraction, the job-description reader and the two-column fix have only seen synthetic text I wrote.
2. **Skills are keyword presence.** No depth, recency or years per skill. The vocabulary is 93 skills; others must be typed, and typed skills match literally.
3. **The job-description reader is rule-based.** Unusual wording is missed, and the recruiter fills the box by hand. Experience per skill in a job description ("3+ years in Spring") is not modelled.
4. **Near-match margins are fixed choices:** 15 days on notice, 10% on CTC, 6 months on experience. They aren't editable in the page.
5. **Location list is small.** A place not on it is sent for a manual check. Localities are mapped for Hyderabad mainly.
6. **Answers from the call can't be entered.** An "Unknown" stays unknown until the resume changes.
7. **Other stated conditions** (shifts, degree, days in office) are listed for the recruiter but not checked.
8. **The 1.0 `decision` and `score` fields are still in the API response in experienced mode,** for compatibility. The page doesn't show them there, and they still include wording overlap.
9. **Two-column detection is a heuristic.** It needs at least six lines with a wide gap, on at least half the page, with prose on the right. Other layouts (three columns, sidebars with short lines) fall back to the old behaviour.
10. **Phone width** needs sideways scrolling inside the results table.
11. **The page's JavaScript has no automated tests.** The CSV and all evaluation logic moved to the server and are tested; rendering was checked by hand.
12. **No access control, upload cap, time limit or rate limit.** Fine on a laptop, not for a hosted copy.
13. **Phone numbers:** Indian mobiles only.

## 7. Features still not implemented

- Typing call answers back in and re-evaluating (M2b)
- A printable call sheet (M2b)
- Client tracker templates and XLSX export (M4)
- Duplicate detection (M4)
- SAP and Oracle skill packs (M4)
- WhatsApp or message intake (M5)
- Experience worked out from job dates; any language-model layer (M6)
- Hosting, access codes, storage, submission memory (M7)
- PDF export, vacancy management, a product dashboard: not on the roadmap

## 8. Honest completion assessment

**Yardstick:** 100% means an agency could rely on it for a live requirement today. My judgement; documents don't count.

| Feature | In code | Automated tests | Checked in browser | Before | Now |
|---|---|---|---|---:|---:|
| Resume extraction | 7 fields, rules, column-aware PDFs | Yes, synthetic | Yes, incl. PDF and DOCX | 45% | 55% |
| Evidence traceability | Quotes for facts; reasons for every check | Yes | Yes | 70% | 75% |
| Job description parsing | Skills, experience, notice, CTC, location, other | Yes, synthetic | Yes | 15% | 55% |
| Client requirements | Editable, explicit against suggested, validated | Yes | Yes | 5% | 65% |
| Candidate evaluation | Three dimensions, five statuses, next step | Yes | Yes | 30% | 60% |
| Candidate comparison | Side by side for 2 to 4 | No (page code) | Yes | 10% | 50% |
| Client submission generator | Wider CSV only | Yes | Yes | 10% | 15% |
| Vacancy management | No | No | No | 0% | 0% |
| Dashboard | No | No | No | 0% | 0% |
| CSV export | Server-built, both modes | Yes | Yes | 75% | 85% |
| PDF export | No | No | No | 0% | 0% |

What holds every number below 100: no real resumes or job descriptions, and no pilot.

## 9. Git

| Item | Value |
|---|---|
| Branch | `v2` |
| Commits this session | `6acdd9f` checkpoint, `8eee1c3` M1 fixes, `d622062` M2 backend, `1a4bfe3` M2 frontend, then a documentation commit containing this file |
| Tags | `v1-baseline` (1.0), `m2-start` (before this session's code) |
| Remote | **None.** The repository exists only on this laptop |

Run `git log --oneline -6` for the exact latest hash.

## 10. How to run it

From the repository root:

```bash
.venv/bin/uvicorn app.main:app --port 8765
```

Open http://localhost:8765. Tick "Hiring experienced candidates", then press "Try it with sample data".

```bash
.venv/bin/python -m pytest -q
```

Expect 273 passed.

```bash
.venv/bin/python -m outreach
```

The outreach dashboard, at http://127.0.0.1:8770. Unchanged this session.

The server doesn't reload Python changes by itself. Restart it after editing anything under `app/`.

## 11. Best next milestone

**M2b: let the recruiter enter what the candidate said on the call, and re-evaluate.**

Today the tool says "Unknown: ask on the call" and then can't hear the answer. Adding an editable value beside each missing or unclear fact, marked "entered by recruiter" and kept apart from resume evidence, closes the loop from resume to submission. It needs no storage and no new dependency, and it is the step that turns the evaluation into something a recruiter can finish a submission with.

## To resume safely

1. `cd ~/ai-recruiter-os`, check `git status` is clean and the branch is `v2`.
2. Run the tests and expect 273 passed.
3. Read [roadmap.md](roadmap.md), then sections 6 and 11 above.
4. Don't change `app/services/scoring.py` or `suggestions.py` for 1.0 inputs: `test_campus_result_is_unchanged_by_m2` and `test_campus_csv_matches_the_1_0_file_exactly` pin them.
