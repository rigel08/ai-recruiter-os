# Roadmap

Written 10 November 2026. Effort figures are my estimates for part-time work, not measurements.

**The rule:** everything up to M3b is built. **From M4 onwards, each milestone is built only when its gate is met.** The 9 December decision from the research still stands: fewer than 3 paid pilots means stop or change direction.

| # | Milestone | What ships | Effort | Risk | Gate to start |
|---|---|---|---|---|---|
| M0 | Baseline and plan | Git repository, `v1-baseline` tag, `v2` branch, these documents | Done | None | None |
| **M1** | **Candidate facts with evidence** | Phone, total experience, notice period, current and expected CTC, location; a quote for each; an "ask on call" list; coverage counts; an experienced-hire sample; a labelled test set | **Done on `v2`** | Low: additive, 1.0 output unchanged | None |
| **M2** | **Requirements and evaluation** | Requirements read from the job description for the recruiter to confirm or edit; each candidate checked against them (meets, near match, does not meet, unknown, check by hand); skills, client limits and information shown separately; side-by-side comparison; CSV built on the server | **Done on `v2`**. The call sheet moved to M2b | Low | None |
| **M2b** | **Call answers and re-evaluation** | Record what the candidate said (answered, confirmed, waiting, not applicable); review the before and after; re-evaluate. Resume evidence is never changed, and every value shows its source. Paste a candidate's reply to fill the answers | **Done on `v2`** | Low | None |
| **M3** | **Client submissions** | Profiles drafted from known details only; pre-submission checks; editable summary, remarks, details and order; live preview; print or save as PDF, copy as text, Excel and CSV; contact details off by default | **Done on `v2`** | Low | None |
| **M3b** | **Saved sessions** | Named sessions with a status in a local SQLite file; call notes and submissions save as you go; duplicates within a batch and people already in another session are flagged | **Done on `v2`**, local only | Medium: it stores candidates' details | None |
| M4 | Pilot kit and measurement | Run on real, permissioned resumes; count corrections made in call notes as accuracy data; a pilot log (counts and timings only); a one-page data agreement | 2 to 3 days | Low | First discovery call booked |
| M5 | The client's tracker | Column templates saved per client; SAP and Oracle skill packs | 2 to 3 days | Low | One agency shares a blank tracker |
| M6 | Wider intake and deeper reading | Whole WhatsApp chat exports; experience added up from job dates; the evidence-locked model pass, off by default | 5 to 8 days | Medium to high | Two agencies say a quarter or more of resumes arrive outside Naukri; 100 real labelled resumes |
| M7 | Hosted and shared | Accounts and access control, size caps, time limits, rate limit, strict CSP, Docker built and deployed, a shared workspace for an agency's recruiters | 8 to 12 days | High | Two agencies paying |

## Why M1 came first

- **Highest value:** it's the exact thing the value proposition promises and 1.0 lacked.
- **Lowest risk:** it only adds fields. With the "Experienced hires" switch off, the page, the CSV and every 1.0 API field are unchanged.
- **Needed by everything after it:** limits, the call sheet, the tracker and duplicate checks all read these facts.

## What M1 does not claim

- **No accuracy figure for real resumes.** The labelled set is synthetic and written by the same hand as the rules.
- **Coverage will often be low.** Many resumes don't state notice period or CTC at all. That's what the "ask on call" list is for.
- **Facts don't change the ranking yet.** That's M2.

## What M2 does not claim

- **The job-description reader is rule-based and untested on real job descriptions.** It knows the 93 skills in the vocabulary and the wordings in its tests. Anything it misses, the recruiter types in.
- **Location matching uses a hand-kept list of about 40 Indian cities.** A place that isn't on it is sent for a manual check, not guessed.
- **The near-match margins are my choices,** not measured: 15 days on notice, 10% on CTC, 6 months on experience.
- **Answers from the call can't be typed back in yet.** That's M2b.

## What M2b, M3 and saved sessions do not claim

- **A recruiter-entered answer is not verified.** It is what the recruiter typed, shown as such.
- **The summary is a template sentence** built from known details. It is a starting point for the recruiter to rewrite, not writing.
- **Role, employer and education are read by simple rules.** When a title and a company can't be told apart, the field is left empty.
- **Excel files were opened in macOS Quick Look, not in Excel itself.** The print layout was checked through its style rules, not on paper.
- **Saved sessions are for one person on one computer.** No accounts, no sync, no backup. A hosted copy runs without them.
- **"Seen before" matches only an identical phone number or email.** It will miss the same person with new contact details.

## Order of work if nothing changes

1. M4, because nothing here has met a real resume or a real recruiter yet. Corrections made in call notes are free accuracy data: count them.
2. M5, once an agency shares its client's tracker.
3. Stop and read the call notes before starting M6 or M7.

## Open questions for the missing brief

The 2.0 brief wasn't available when this was written. It may change:
- whether a language model is expected from the start (this plan makes it optional and late)
- whether a hosted product is expected early (this plan runs pilots locally first)
- any stack, timeline or scope it prescribes
