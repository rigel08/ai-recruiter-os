# Session progress report

Snapshot taken Tuesday 10 November 2026, after the M2b, M3 and saved-sessions sprint. Earlier snapshots are in git history.

## The short version

- **A recruiter can now take one job from job description to client submission in the page:** confirm requirements, upload resumes, see the evaluation, record call answers, re-evaluate, compare, prepare and export a submission, and save the session.
- **348 tests pass, none fail** (273 before this sprint).
- **Checked in the browser** at desktop and phone width with no console errors.
- **Still true:** every resume and job description used so far is synthetic. Nothing here is a claim about accuracy on real documents.

## 1. What existed before this sprint

Branch `v2` at `fb4d05e`, 273 tests passing: M1 (facts with evidence) and M2 (requirements read from the job description, three-part evaluation, comparison, server-built CSV). The tool could say "Unknown: ask on the call" but had nowhere to put the answer, produced no client-facing output beyond a CSV, and forgot everything on reload.

## 2. What was implemented

**M2b. Call answers and re-evaluation**

- **Four states per detail:** answered (the recruiter types a value), confirmed (the candidate confirmed the resume's value), asked and waiting, not applicable.
- **Sources are kept apart.** Each value in use is labelled Resume, Confirmed on call or From recruiter. The resume's own value and line are never changed; when a recruiter's value replaces it, the page still shows "Resume says: …".
- **Review before accepting.** "Review changes" shows the before and after for each detail, each check and the next step. Nothing applies until "Accept and re-evaluate". Answers can be edited or cleared later.
- **Re-evaluation** recomputes experience, notice, CTC and location checks, the next step and the order.
- **A message to copy** listing what to ask, to send by hand.

**M3. Client submissions**

- **Profiles drafted from known details only:** designation, employer, total and relevant experience, skills matching the role, current and preferred location, current and expected CTC, notice period, availability, education. Unknown details are left out, never filled.
- **New extraction** for designation, employer, education and relevant experience, each with its resume line; left empty when unclear.
- **Strengths** list only what the evaluation found met.
- **Editing:** summary, remarks, any detail's value, which details appear and in what order, candidate order, remove a candidate.
- **Live preview** of what the client sees, with details from a call marked.
- **Exports:** print or save as PDF, copy as text, Excel, CSV. Several candidates in one document.
- **Privacy default:** phone and email are left out unless the recruiter ticks the box, and the server drops them again unless told to include them.

**M3b. Saved sessions**

- **Named sessions with a status** (open, submitted, on hold, closed) in one SQLite file. Call notes and the submission save as you go, and a session reopens exactly as it was.
- **What is stored:** the job description, requirements, the evaluation as shown (facts and their lines), call notes and the submission. **Not stored:** resume files or their full text.
- **Local only:** the API answers only the loopback address with a local Host header, changes need a custom header, the file is readable only by its owner, and the feature is off in the Docker image.

**Improvements chosen after the core was working**

| Built | Why |
|---|---|
| **Paste the reply.** Paste what the candidate sent ("NP 30 days, cctc 14, ectc 18, loc hyd") and the answer boxes are filled for checking, each with the words it was read from | Candidates answer in shorthand on WhatsApp. Retyping five values per candidate is the most repeated manual step left |
| **Pre-submission checks.** Before export, each profile lists conflicts with the client's limits, unknowns the client asked about, low skills fit, and which details came from a call | A submission that breaks the client's stated limit, or sends the same person twice, costs the agency credibility. It never blocks: the recruiter decides |
| **Duplicates and "seen before".** Resumes sharing a phone number or email are flagged in the batch and in a submission; people already in another saved session are named with that session's status | Calling or submitting the same person twice wastes time and can cause fee disputes |

## 3. What remains incomplete

- **Client-specific tracker templates.** The Excel and CSV use this tool's columns, in the order chosen for that session. Nothing is saved per client.
- **Re-evaluating after changing skills.** Call answers re-evaluate without the resumes. Changing required skills needs the resumes uploaded again, because resume text isn't kept.
- **Relevant experience, designation, employer and education can't be recorded in call notes.** They can be typed in the submission editor only.
- **No reminders** for answers marked "asked, waiting".
- **No real PDF generation.** PDF comes from the browser's print dialog.
- **Not built at all:** accounts, sharing between recruiters, hosting, WhatsApp intake of whole chats, a language-model layer, candidate search across sessions, a pipeline dashboard.

## 4. Files

Since the `m3-start` tag: 34 files changed, about 3,500 lines added.

**Created (18)**
- Services: `app/services/clarify.py`, `replies.py`, `profile.py`, `submission.py`, `duplicates.py`, `xlsx.py`, `workspace.py`
- Routes: `app/api/routes/clarifications.py`, `submissions.py`, `workspace.py`
- Schemas: `app/schemas/clarifications.py`, `submissions.py`, `workspace.py`
- Page: `app/static/app.js` (the old inline script, moved), `app/static/workspace.js`
- Tests: `tests/test_clarify.py`, `test_submission.py`, `test_workspace.py`

**Modified**
- `app/main.py`, `app/schemas/screening.py`, `app/services/screening.py`, `evaluation.py`, `export.py`
- `app/static/index.html`
- Five sample resumes (an education line each)
- `tests/test_api.py`, `test_export.py`
- `Dockerfile`, `.gitignore`, `.dockerignore`
- `README.md`, `docs/v2/README.md`, `docs/v2/roadmap.md`, this file

**Untouched:** the 1.0 ranking (`scoring.py`, `suggestions.py`, `skills.py`, `academics.py`) and everything under `outreach/`.

**Evaluation logic:** not changed. It was split so it can rerun from facts without the resume text; the M2 tests pass unmodified.

**New dependency:** none. Excel files are written with the standard library.

## 5. Tests

| Measure | Result |
|---|---|
| Passing | **348** |
| Failing | **0** |
| Before this sprint | 273 |
| New | 75 |

| File | Tests | Covers |
|---|---:|---|
| `test_clarify.py` (new) | 33 | Sources, entered beside resume, confirmed, waiting, not applicable, clearing, new conflicts, refusals with reasons, reading replies |
| `test_submission.py` (new) | 24 | Role, employer and education reading; drafts from known values only; strengths; pre-submission checks; duplicates; contact left out; edits and order; CSV; Excel structure; bad input |
| `test_workspace.py` (new) | 17 | Save and restore exactly; updates; delete; no resume text stored; seen before; refusal of other machines, wrong Host and missing header; off in Docker |
| `test_export.py` | 8 (1 new) | CSV shows the value in use, its source and remarks, and still quotes the resume |
| Everything else | 266 | Unchanged and passing, including the pin against the `v1-baseline` result |

## 6. Browser verification

Synthetic data, in the app's built-in browser, against a throwaway session database.

| Check | Result |
|---|---|
| Switch off (1.0) | Same 7 columns, tabs, counts and 13-column CSV. No requirements, selection or session bars |
| Call notes | Opened for a candidate with nothing on the resume; pasted a reply; 5 boxes filled; reviewed; "Back to editing" kept the draft; accepted. The candidate moved from "Clarify first" to "Looks ready" and up the order. Resume facts were still empty |
| Source labels | "Resume" and "From recruiter" shown beside values; notes shown under the candidate |
| Submission | Three candidates drafted. Contact switch off by default and reversible. Excluded a detail, moved one up, edited a summary, remarks and one candidate's detail: the preview followed each change and marked the edited detail |
| Exports | Text, Excel and CSV fetched from the page. Excel opened in macOS Quick Look |
| Print layout | Checked by applying the print rules on screen: only the document remains. **Not printed to an actual PDF** |
| Sessions | Saved, renamed status, reloaded the page, reopened from the list: results, call answers, requirement boxes, status and the edited submission all came back. Deleted |
| Duplicates | The same resume under two names was flagged in the results and in the submission |
| Seen before | Re-screening people from a saved session produced one grouped notice naming the session and its status |
| Phone width (375 px) | No sideways page scroll. Dialogs fit. The submission stacks into one column. The results table scrolls inside its box |
| Console | No errors |

**Not checked:** Safari or Firefox; Excel itself; light mode on the new screens; real printing; the operating system's file picker.

## 7. Known limitations

1. **Synthetic data only.** No accuracy claim can be made for real resumes, real job descriptions or real candidate messages.
2. **Reply reading is deliberately loose.** It is safe only because every value is reviewed before it's used.
3. **A recruiter-entered value is taken as typed.** There is no check against the resume beyond showing both.
4. **Role and employer rules** depend on common layouts ("Title, Company (2022 to present)"). Other layouts return nothing.
5. **Summaries are template sentences.** Useful as a start, flat as writing.
6. **"Seen before" needs an identical phone number or email.**
7. **Saved sessions hold personal data on disk, unencrypted,** protected by file permissions only. There is no backup, and deleting a session is permanent.
8. **Single user.** Two browser tabs on the same session will overwrite each other's saves.
9. **The page's JavaScript (about 1,300 lines) has no automated tests.**
10. **Hosted copies** still have no access control, upload cap or rate limit, and run without sessions.

## 8. Git

| Item | Value |
|---|---|
| Branch | `v2` |
| Tags | `v1-baseline`, `m2-start`, `m3-start` |
| Commits this sprint | `e776fad` script move, `8ec7d34` M2b backend, `e8b8c8d` M2b page, `7cbd3f1` M3 backend, `cb238da` M3 page, `8098c35` saved sessions, then a documentation commit containing this file |
| Remote | **None.** The repository exists only on this laptop |

Run `git log --oneline -8` for exact hashes.

## 9. How to run it

```bash
cd ~/ai-recruiter-os && .venv/bin/uvicorn app.main:app --port 8765
```

Open http://localhost:8765, tick "Hiring experienced candidates" and press "Try it with sample data".

```bash
cd ~/ai-recruiter-os && .venv/bin/python -m pytest -q
```

Expect 348 passed. Restart the server after changing anything under `app/`.

## 10. Five biggest remaining weaknesses

1. **It has never met a real resume, job description or recruiter.** Everything else is secondary to this.
2. **Skills fit is keyword presence** against 93 skills. It can't tell two years of Java from ten, or a course from a job.
3. **The output isn't the client's own tracker.** Agencies submit in the client's format; this exports in ours.
4. **One person, one computer.** A two-recruiter agency can't share a session, and there is no backup.
5. **The page is untested code.** Every screen was checked by hand once; nothing stops a later change from breaking it.

## 11. Ideas considered, and three new opportunities

Ranked by time saved per use, how often it happens, and effort:

| # | Idea | Value | Effort | Decision |
|---:|---|---|---|---|
| 1 | Paste the candidate's reply to fill answers | High, several times a day | Low | **Built** |
| 2 | Pre-submission checks | High, every submission | Low | **Built** |
| 3 | Duplicates and "seen before" | Medium to high | Low | **Built** |
| 4 | Corrections as measurement | High for trust and sales | Low | Next (M4) |
| 5 | Questions for the client when the job description is silent on budget, notice or location | Medium | Low | Later |
| 6 | A "waiting on" list across sessions for answers marked asked | Medium | Low | Later |
| 7 | Client tracker templates | High once a real tracker is seen | Medium | Gated (M5) |
| 8 | Natural-language search over candidates | Low at this scale | High | Not worth it yet |

**Three opportunities found while building:**

1. **Every correction is a free accuracy label.** When a recruiter replaces a resume value in call notes, that is a measured disagreement between the extractor and reality. Counting these per field gives a real error rate from pilot use, with no extra work for the recruiter.
2. **"Paste anything" intake.** The reply reader already turns loose text into reviewed values. The same step could take a Naukri profile's text, an email, or a WhatsApp chat pasted whole, which reaches the M5 goal without parsing export files.
3. **Submission memory as fee protection.** "Seen before" knows who was in which session. Recording which candidates actually went to which client, and when, would warn before a duplicate submission, which is where agencies lose fees.

## 12. Recommended next milestone

**M4: pilot kit and measurement.** Run the tool on one agency's real, permissioned requirement, on your laptop, with them watching. Count how many extracted values they correct, per field. Record how long resumes-to-submission takes with and without it.

No further feature will tell you as much as that one session, and the list of what to build next should come from it.

## To resume safely

1. `cd ~/ai-recruiter-os`, check `git status` is clean and the branch is `v2`.
2. Run the tests and expect 348 passed.
3. Read [roadmap.md](roadmap.md), then sections 3, 7 and 10 above.
4. `data/workspace.db` appears the first time a session is saved. It is ignored by git and holds personal data.
