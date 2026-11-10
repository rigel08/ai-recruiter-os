# Roadmap

Written 10 November 2026. Effort figures are my estimates for part-time work, not measurements.

**The rule:** M1 to M3 are worth building whatever the calls say, because they make the pitch honest and a local pilot possible. **M4 onwards is built only when its gate is met.** The 9 December decision from the research still stands: fewer than 3 paid pilots means stop or change direction.

| # | Milestone | What ships | Effort | Risk | Gate to start |
|---|---|---|---|---|---|
| M0 | Baseline and plan | Git repository, `v1-baseline` tag, `v2` branch, these documents | Done | None | None |
| **M1** | **Candidate facts with evidence** | Phone, total experience, notice period, current and expected CTC, location; a quote for each; an "ask on call" list; coverage counts; an experienced-hire sample; a labelled test set | **Done on `v2`** | Low: additive, 1.0 output unchanged | None |
| **M2** | **Requirements and evaluation** | Requirements read from the job description for the recruiter to confirm or edit; each candidate checked against them (meets, near match, does not meet, unknown, check by hand); skills, client limits and information shown separately; side-by-side comparison; CSV built on the server | **Done on `v2`**. The call sheet moved to M2b | Low | None |
| M2b | Call sheet and answers | A printable call sheet per candidate; type the answers back in and re-evaluate | 1 to 2 days | Low | None |
| M3 | Local pilot kit | A pilot log (counts and timings only); a one-command local start; a one-page data agreement template; `.doc` flagged with a how-to-convert hint | 1 to 2 days | Low | First discovery call booked |
| M4 | The client's tracker | Column templates per client; XLSX export; duplicates within a batch; SAP and Oracle skill packs | 3 to 4 days | Low | One agency shares a blank tracker |
| M5 | Message-aware intake | Read a WhatsApp chat export or pasted messages; pair each resume with what the candidate typed | 3 to 5 days | Medium: export formats vary | Two agencies say a quarter or more of resumes arrive outside Naukri |
| M6 | Deeper reading | Experience added up from job dates; the evidence-locked model pass, off by default | 5 to 8 days | Medium to high: privacy, cost, accuracy | 100 real, consented, labelled resumes from pilots |
| M7 | Hosted and remembered | Access codes, size caps, time limits, rate limit, strict CSP, Docker built and deployed; opt-in workspace; submission memory; clean candidate profile | 5 to 8 days | Medium | Two agencies paying |

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

## Order of work if nothing changes

1. M2b, so a recruiter can finish the job after the call: enter what the candidate said and see the evaluation update.
2. M3, once a call is booked, so a pilot can run on the laptop the same week.
3. Stop and read the call notes before starting M4.

## Open questions for the missing brief

The 2.0 brief wasn't available when this was written. It may change:
- whether a language model is expected from the start (this plan makes it optional and late)
- whether a hosted product is expected early (this plan runs pilots locally first)
- any stack, timeline or scope it prescribes
