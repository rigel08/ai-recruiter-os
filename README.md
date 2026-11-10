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

## New on the `v2` branch: experienced hiring

Tick **Hiring experienced candidates** and the page changes from campus ranking to checking candidates against a client's requirements.

1. **Paste the job description and press "Fill from the job description".** Required and preferred skills, the experience range, the longest notice period, the CTC budget and the location go into editable boxes, each with the sentence it came from. Anything only hinted at stays out of the box until you choose it.
2. **Edit the boxes.** Only what's in them is checked. An empty box means no limit.
3. **Upload resumes.** Each candidate gets three separate views, never one combined score:
   - **Skills and experience:** required and preferred skills found, and whether the stated experience is in range. Wording overlap with the job description isn't counted.
   - **Client limits:** notice period, CTC and location, each marked Meets, Near match, Does not meet, Unknown or Check by hand, with the reason.
   - **Information on the resume:** phone, experience, notice period, CTC and location, each with the exact line it came from, and what to ask on the call.
4. **Read the "Next step"** for each candidate: Looks ready, Clarify first, Check by hand, Conflicts with a limit or Low skills fit. Nobody is removed or rejected.
5. **Tick two to four candidates** to compare them side by side, and download the CSV.

6. **Record the call.** "Record call answers" on a candidate gives you a message to copy and send yourself, a box to paste their reply into (it fills the answers for you to check), and one row per detail showing what the resume says beside what they said. "Review changes" shows the before and after; nothing applies until you accept. Every value is labelled Resume, Confirmed on call or From recruiter, and the resume's own line is never changed.
7. **Prepare the client submission.** Tick candidates and press "Prepare client submission". You get a drafted profile for each, checks to read before sending (conflicts with the client's limits, unknowns, the same person twice), and an editor for the summary, your remarks, each detail and their order. Phone and email are left out unless you tick the box. Print or save as PDF, copy as text, or download Excel or CSV. Nothing is sent for you.
8. **Save the session.** "Save session" keeps the evaluation, your call notes and the submission in a file on your computer, so each job you're working on can be reopened from "Saved sessions". Resume files themselves aren't kept. Someone who is already in another saved session is flagged as "Seen before".

Things it deliberately doesn't do:
- **Guess.** A missing notice period is "Unknown", not a failure. "Serving notice" never becomes a number of days.
- **Read protected details** such as age, gender or marital status.

With the switch off, the page, the CSV and the API response are the 1.0 ones.

**Where saved sessions live.** One file, `data/workspace.db`, readable only by your user account and ignored by git. It holds candidates' details and your notes, so treat it like the resumes themselves. The part of the app that reads it answers only your own computer, and it is switched off in the Docker image.

Check the extractor against its labelled cases:

```bash
.venv/bin/python -m evals.facts
```

Those cases are synthetic, so they show the rules behave as intended. They don't measure accuracy on real resumes. The plan and current status are in [docs/v2/](docs/v2/README.md).

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

`GET /api/samples` returns the demo job and resumes; `?kind=experienced` returns the experienced-hire set.

Added on `v2`:

| Endpoint | What it does |
|---|---|
| `POST /api/requirements` | JSON `{"job_description": "..."}` in; suggested requirements out, each with its sentence and whether it's explicit or only suggested |
| `POST /api/screenings` with `hiring_mode=experienced` | Also takes `preferred_skills`, `min_experience_years`, `max_experience_years`, `max_notice_days`, `max_ctc_lpa` and `locations`. Each candidate gains an `evaluation` |
| `POST /api/exports/csv` | A screening result in; the CSV file out |
| `POST /api/clarifications/apply` | A result and the recruiter's call answers in; everyone evaluated again, with each value's source in `resolved` |
| `POST /api/clarifications/read-reply` | A candidate's pasted message in; suggested answers out, each with the words it came from |
| `POST /api/submissions/draft` | A result, call answers and chosen candidates in; drafted profiles and pre-submission checks out |
| `POST /api/submissions/export?format=csv\|xlsx\|text` | The finalised submission in; the file out. Contact details are dropped unless `include_contact` is true |
| `/api/workspace/sessions` (GET, POST, PATCH, DELETE) | Saved sessions. Answers only this computer |
| `POST /api/workspace/seen` | Which candidates in a result are also in another saved session | `GET /health` returns `{"status": "ok"}`.

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
