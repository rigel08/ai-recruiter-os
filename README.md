# AI Recruiter OS

Paste a job description, upload up to 200 resumes, and get a ranked shortlist in seconds. Every candidate gets a suggested next step (Shortlist, Maybe or Not a fit), a one-line reason and interview questions.

Built for campus placement cells and small recruitment teams that still shortlist by hand.

**New here?** Read [docs/how-it-works.md](docs/how-it-works.md) for the full walkthrough.

## Features

- **Reads PDF, DOCX and TXT,** up to 200 files at 5 MB each. Big batches are parsed in parallel: 200 resumes in about 2 seconds on an 8-core laptop.
- **Ranks from 0 to 100.** Must-have skills count for 60%, the job description's other skills for 30%, and overall wording similarity for 10%.
- **Suggests a next step** for each candidate: Shortlist, Maybe or Not a fit, using simple, predictable rules.
- **Applies a CGPA cut-off** if you set one. Resumes with no CGPA are flagged for a person rather than excluded. Strong candidates ruled out only by CGPA are called out.
- **Suggests interview questions** that probe gaps and check claimed skills.
- **Flags files it can't read,** such as scanned images, `.doc` files and damaged files, instead of quietly ranking them last.
- **Matches skills accurately.** "Java" doesn't match "JavaScript", "C++" and "Node.js" match literally, and "eager to excel" isn't read as the skill Excel.
- **Exports** to CSV (protected against spreadsheet formula injection) and copies the shortlisted candidates' emails.
- **Includes a demo:** "Try it with sample data" runs a fictional job and 8 fictional resumes.

**Privacy:** resumes exist only for the length of one request. Nothing is stored.

## Run it locally

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8765
```

Open http://localhost:8765. The interactive API docs are at http://localhost:8765/docs.

## Run the tests

```bash
.venv/bin/python -m pytest -q
```

## Run it with Docker

```bash
docker build -t ai-recruiter-os .
docker run -p 8000:8000 ai-recruiter-os
```

The container listens on `$PORT` if the host sets it (as Render and Railway do), otherwise on 8000. The image hasn't been built yet, because Docker isn't installed on the development machine.

## Outreach dashboard (local only)

A separate, private dashboard for the first customer conversations lives in [outreach/](outreach/README.md). It isn't part of the screening app, isn't in the Docker image, and only answers on this computer:

```bash
.venv/bin/python -m outreach
```

Then open http://127.0.0.1:8770.

## API

`POST /api/screenings` (multipart form):

| Field | Required | Notes |
|---|---|---|
| `job_description` | Yes | 30–20,000 characters |
| `must_haves` | No | Comma- or line-separated skills |
| `min_cgpa` | No | 0–10. Blank means no cut-off |
| `resumes` | Yes | One or more files, up to 200 |

`GET /api/samples` returns the demo job and resumes. `GET /health` returns `{"status": "ok"}`.

## Layout

| Path | What's there |
|---|---|
| `app/main.py` | FastAPI app, the page, and shutting down workers cleanly |
| `app/api/routes/screenings.py` | `POST /api/screenings` and input validation |
| `app/api/routes/samples.py` | `GET /api/samples` |
| `app/services/parsing.py` | PDF, DOCX and TXT to text |
| `app/services/skills.py` | Skill vocabulary and whole-term matching |
| `app/services/scoring.py` | The 0–100 score and its explanation |
| `app/services/academics.py` | Reading the CGPA |
| `app/services/suggestions.py` | Shortlist, Maybe or Not a fit, and interview questions |
| `app/services/screening.py` | Runs a batch: parallel parsing, scoring, sorting |
| `app/schemas/screening.py` | The response shape |
| `app/static/index.html` | The recruiter-facing page |
| `app/samples/` | Fictional demo job and resumes |
| `docs/how-it-works.md` | Full explanation, trade-offs, interview prep |
| `docs/pilot-outreach.md` | Messages and questions for pilot users |

## Next

1. Run the pilot and adjust the rules to what recruiters actually check.
2. Deploy it.
3. Add an optional LLM summary per candidate, with the organisation's consent.
4. Add a per-file time limit and OCR for scanned resumes.
5. Add accounts and saved screenings once someone uses it weekly.
