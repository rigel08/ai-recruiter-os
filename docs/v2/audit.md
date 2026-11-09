# Audit of the 1.0 codebase

Done 10 November 2026 by reading every file under `app/`, `outreach/` and `tests/`, and running the suite: **93 tests pass** (68 screening, 25 outreach) in under a second.

## What exists

| Part | Size | What it does |
|---|---|---|
| `app/` screening app | About 730 lines of Python, one 471-line HTML page | Ranks up to 200 resumes against a job description; Shortlist, Maybe or Not a fit; CGPA cut-off; interview questions; CSV export |
| `outreach/` dashboard | About 860 lines of Python, 650 of JavaScript | Private, local-only tracker for the ten prospects. Separate from `app/`; not in the Docker image |
| `research/market-validation/` | 13 documents | Prospects, competitors, workflow, playbook, gap analysis, verdict |

## What's sound and should be kept

- **Clean layers.** Routes call services; services are pure functions over text; schemas are separate. New stages can be added without touching old ones.
- **Deterministic and fast.** No model calls and no network. The same input always gives the same output, which makes it testable and explainable.
- **Honest failure.** Files it can't read go to "needs a manual look" instead of being ranked last.
- **Careful matching.** Whole-term skills ("Java" isn't "JavaScript"); the first 10-point CGPA only; other scales ignored, not converted.
- **Safe output.** The page inserts text with `textContent`, and the CSV guards against formula injection.
- **Parallel parsing** with recovery if a worker process dies.
- **Nothing stored.** Files live for one request.

## Product gaps (Verified in code)

1. **Built for campus hiring, sold to agencies.** It ranks on skills and CGPA. Agencies hiring experienced people screen on notice period, CTC, experience and location, and 1.0 extracted none of them.
2. **Fixed CSV columns.** Not the client's tracker.
3. **No duplicate detection,** within a batch or across batches.
4. **Skill vocabulary of 93 terms,** tech-heavy. It has "SAP" but no SAP modules, and no Oracle, ServiceNow or Workday.
5. **Ranking quality has never been measured.** There is no labelled set of "a recruiter would shortlist this one".

## Engineering risks (Verified in code)

| Risk | Where | Why it matters |
|---|---|---|
| No access control | `app/main.py` | Anyone with the URL can use a hosted copy |
| No cap on total upload size | `routes/screenings.py` | 200 files of 5 MB is about 1 GB held in memory per request |
| No per-file time limit | `services/screening.py` | One malformed PDF can stall a batch |
| No rate limit; public `/docs` | `app/main.py` | Cheap to abuse |
| Inline script in the page | `app/static/index.html` | Blocks a strict Content Security Policy. The outreach dashboard already does this correctly |
| Docker image never built | `Dockerfile` | Deployment is unproven |
| No CI, linter or type checker | Repository | Fine for one person; a risk once changes come faster |
| Pinned dependencies not checked for advisories | `requirements.txt` | Not checked in this audit |
| PDF text order | `services/parsing.py` | Two-column resumes can come out interleaved, which hurts any line-based extraction |
| Name guess is a heuristic | `services/screening.py` | First short line of words in the top five lines; wrong on some layouts |
| No `.doc`, no scanned PDFs | `services/parsing.py` | Flagged honestly, but not read |

None of these stops a **local** pilot run on the founder's laptop. All of the first four must be fixed before real resumes go through a hosted copy.

## Verdict

The engineering base is worth keeping: don't rewrite it. The product layer on top is aimed at the wrong buyer. 2.0 should add stages to the existing pipeline, keep every 1.0 behaviour and API field as it is, and move the product from "who ranks highest" to "what goes in the client's tracker, and how do we know".
