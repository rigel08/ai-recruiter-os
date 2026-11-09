# How AI Recruiter OS works

This guide explains the whole project: what it does, how each part works, why it's built this way, and how to talk about it in an interview.

## What it does, in one paragraph

A recruiter pastes a job description, optionally types must-have skills and a minimum CGPA, and uploads up to 200 resumes. In a couple of seconds they get back:
- every candidate ranked from 0 to 100
- a suggested next step for each (Shortlist, Maybe or Not a fit)
- a one-line reason, plus warnings worth double-checking
- suggested interview questions
- a CSV to download

Files it can't read go to a "needs a manual look" list instead of being quietly ranked last. Nothing is saved.

## The journey of one screening

```
Browser (app/static/index.html)
  │  POST /api/screenings: job description, must-haves, min CGPA, files
  ▼
API route (app/api/routes/screenings.py)
  │  validates the input, reads each file (capped at 5 MB)
  ▼
screen() (app/services/screening.py)
  │  1. turns must-haves into skill terms           → skills.py
  │  2. finds the other skills in the job description → skills.py
  │  3. parses every file into text, in parallel     → parsing.py
  │  4. for each resume:
  │       score it                                    → scoring.py
  │       read its CGPA                               → academics.py
  │       suggest a next step and questions           → suggestions.py
  │  5. sorts: Shortlist, then Maybe, then Not a fit; by score within each
  ▼
JSON response (app/schemas/screening.py) → the browser draws the table
```

## Each part, explained

### 1. Reading files: `parsing.py`

- **PDF:** uses the `pypdf` library to pull out the text layer. Many "protected" PDFs only block printing, so it tries an empty password before giving up.
- **DOCX:** a `.docx` file is a zip archive, and the text lives in `word/document.xml`. The code unzips it with Python's built-in `zipfile` and collects the `<w:t>` text elements, so no extra library is needed. It checks the unzipped size first, so a tiny malicious file can't expand into gigabytes (a "zip bomb").
- **TXT:** decoded as UTF-8.
- **Anything else,** including old `.doc` files, raises `UnreadableDocument` with a message written for a recruiter, not a programmer.

If a PDF yields almost no text (under 100 characters), it's almost certainly a scanned image, so it's flagged for a person.

### 2. Finding skills: `skills.py`

This is the part most likely to come up in an interview, because naive matching gets it badly wrong.

- **The vocabulary:** about 100 skills, each with other spellings. "Postgres" counts as PostgreSQL, and "ReactJS" counts as React.
- **Whole terms only:** each skill becomes a regular expression with "edges" on both sides: `(?<![A-Za-z0-9+#.])` before and `(?![A-Za-z0-9+#])` after. That's why "Java" doesn't match inside "JavaScript", and "C++", "C#" and "Node.js" match exactly.
- **Ordinary words:** "Excel", "Swift", "Spark" and a few others only count when capitalised, so "eager to excel" isn't read as Microsoft Excel. The case rule is per spelling, so "Microsoft Excel" still matches in any case.
- **Spacing:** "Power BI" also matches "Power\n BI", because any run of whitespace counts as one space.
- **Recruiter's terms:** a must-have typed by the recruiter that isn't in the vocabulary, like "Kafka Streams", is matched as typed, ignoring case.

### 3. Scoring: `scoring.py`

The score has three parts:

| Part | Weight | What it measures |
|---|---|---|
| Must-haves | 60% | Share of the recruiter's must-haves found on the resume |
| Other skills | 30% | Share of the job description's other skills found on the resume |
| Similarity | 10% | How closely the resume's wording matches the job description |

If a part doesn't apply (for example, no must-haves were typed), it's dropped and the other weights are scaled up to fill 100.

**Similarity** uses cosine similarity, a standard way to compare two texts:
1. Count how often each meaningful word appears in each text, ignoring filler words like "the" and "experience".
2. Treat each text as an arrow pointing in the direction of its words.
3. Measure how closely the two arrows point the same way: 1 means the same words in the same proportions, 0 means nothing in common.

It's a tie-breaker, which is why it gets only 10%.

`explain()` turns the numbers into a sentence like "Has 2 of 3 must-haves; missing FastAPI."

### 4. Reading the CGPA: `academics.py`

Two regular expressions catch the common ways people write it: "CGPA: 8.2", "CGPA 8.20 / 10", "C.G.P.A - 7.9", "8.5 CGPA" and "CPI 8.45". It deliberately ignores:
- 4-point GPAs like "3.6/4" (there's no reliable conversion, so it doesn't guess)
- percentages
- SGPA (a single semester's grade)

When there are several, it takes the first, because resumes usually list the degree first.

### 5. Suggestions: `suggestions.py`

These rules are simple on purpose, so a recruiter can predict and trust them:

| Situation | Suggestion |
|---|---|
| CGPA found and below the cut-off | Not a fit |
| Has every must-have | Shortlist |
| Missing exactly one of two or more must-haves | Maybe |
| Missing more than that | Not a fit |
| No must-haves given | Score 60+ is Shortlist, 35–59 is Maybe, below 35 is Not a fit |

There are also two warnings:
- **"No CGPA found":** when a cut-off is set but the resume has no CGPA. The candidate isn't excluded; a person checks.
- **"Would be shortlisted on skills. Only the CGPA cut-off rules them out":** so a recruiter who might relax the cut-off sees who they'd gain.

**Interview questions** ask about gaps first ("The role needs Python. What's your experience with it?"), then check that claimed skills are real ("Walk me through a project where you used SQL…"). The wording varies so the questions don't read like a form.

### 6. Speed: parallel parsing in `screening.py`

Reading a PDF is CPU-heavy pure-Python work. Python's Global Interpreter Lock (GIL) means threads can't run Python code on several cores at once. So for batches of 12 or more, the files are split across a pool of worker **processes**, one per core, up to 8.

- **Measured result:** 200 copies of your real resume took 7.8 seconds in one process and 2.2 seconds in parallel, 3.6× faster with identical results.
- **Small batches skip the pool,** because starting workers costs more than it saves.
- **If a worker crashes,** the pool is reset and that batch finishes in the main process, so the recruiter still gets results.
- **Workers return plain values** (`(text, None)` or `(None, reason)`) rather than raising errors, because errors don't always travel cleanly between processes.

The API route also runs `screen()` in a thread pool (`run_in_threadpool`), so one big batch doesn't freeze the server for everyone else.

### 7. The page: `app/static/index.html`

The page is plain HTML, CSS and JavaScript in one file: no framework and no build step.
- **Safe display:** everything from a resume is inserted with `textContent`, never `innerHTML`. A resume containing `<script>` can't run code in the recruiter's browser (cross-site scripting, or XSS).
- **Safe CSV export:** cells starting with `=`, `+`, `-` or `@` get an apostrophe in front, so a malicious "name" can't run as a formula in Excel (CSV injection). A byte-order mark makes Excel read the file as UTF-8.
- **Extras:** drag-and-drop, filter tabs, copy shortlisted emails, and a "Try it with sample data" button for demos.
- **Light and dark mode** follow the system setting.

### 8. Privacy

Uploaded files live only for the length of one request. There's no database and no file storage. This is the strongest selling point for agencies, and it's simply true of the design.

## Decisions and trade-offs

- **No database yet.** A pilot doesn't need accounts or history. Every feature not built is one that can't break. Add storage when someone uses it every week.
- **Rules, not machine learning, for ranking.** Every rank can be explained in one sentence, which recruiters need before they trust it. A model trained on past hiring decisions can learn past biases.
- **No LLM yet.** Sending resumes to an AI provider needs the organisation's consent and costs money per resume. It's the planned next step, as an optional summary, not the thing that decides.
- **Skills over wording.** Similarity gets only 10%, because two resumes can use the same words and mean very different things.

## Known limits

- The skill vocabulary is about 100 skills, mostly technical, with some business skills. Must-haves outside it still work, matched as typed.
- It finds whether a skill appears, not how good someone is at it. A keyword-stuffed resume scores well. That's why the interview questions check claimed skills.
- The name guess uses the first short line of plain words, so unusual layouts fall back to the file name.
- Scanned resumes need a person. Reading text from images (OCR) isn't built.
- There's no per-file time limit. A deliberately malformed PDF could keep a worker busy. Worth fixing before a public launch.

## Testing

There are 68 automated tests in `tests/`, run with `.venv/bin/python -m pytest -q`:

| File | What it checks |
|---|---|
| `test_skills.py` | Java vs JavaScript, C++, "excel at", aliases, spacing |
| `test_parsing.py` | Real PDF and DOCX files built in memory, damaged files, unsupported types |
| `test_academics.py` | 16 ways of writing (or not writing) a CGPA |
| `test_suggestions.py` | Every decision rule, the warnings and the questions |
| `test_screening.py` | Whole batches, ordering, CGPA cut-off, manual review, parallel equals sequential |
| `test_api.py` | The real HTTP endpoints, validation errors, the sample data, caching |

## Talking about it in an interview

**The 30-second version:**
> "I built a resume-screening tool for campus placement cells and small recruiters. You upload a job description and up to 200 resumes, and it ranks them, suggests shortlist, maybe or not a fit, and explains each decision in one line. It's a FastAPI backend with parsing spread across processes; 200 resumes take about 2 seconds. I kept the ranking rule-based so every decision is explainable, and nothing is stored, for privacy. I'm piloting it with my college's placement cell."

Only say the last sentence once it's true.

**Questions you'll likely get:**
- *How do you stop "Java" matching "JavaScript"?* Regex lookarounds that require a non-letter on both sides. See section 2.
- *Why processes, not threads?* The GIL; parsing is CPU-bound. See section 6.
- *Why not use an LLM to rank?* Explainability, cost, consent, and bias. See "Decisions and trade-offs".
- *What would you change at scale?* Move parsing to a job queue with per-file time limits, add storage and accounts, add OCR for scanned resumes, and measure ranking quality against recruiters' real picks.
- *How do you know it works?* 68 tests, plus the pilot comparison with a human shortlist.

## What to build next

1. **Run the pilot** (see `pilot-outreach.md`) and change the rules to match what recruiters actually check.
2. **Deploy it.** The `Dockerfile` is written for hosts like Render, Railway or Fly.io. It hasn't been built yet, because Docker isn't installed on this Mac, so build it once before relying on it.
3. **Add an optional LLM summary per candidate,** with consent.
4. **Add a per-file time limit and OCR** for scanned resumes.
5. **Add accounts and saved screenings,** once someone uses it weekly.
