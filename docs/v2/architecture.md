# Architecture for 2.0

Written 10 November 2026. This describes the target. Only the parts marked **(M1, built)** exist.

## Rules every new part follows

1. **Additive.** No 1.0 API field, test or behaviour changes. New data arrives as new fields.
2. **Evidence or blank.** Any value taken from a document carries the exact text it came from. If the code isn't sure, the field is empty and goes on the call sheet.
3. **Deterministic core.** Rules run first and always. Anything probabilistic is optional, off by default, and checked against the rules.
4. **Stateless by default.** Files live for one request. Memory is opt-in, local, and stores the minimum.
5. **Measured.** Each extractor has a labelled test set. A change that produces a wrong value on it doesn't merge.
6. **A person decides.** The tool suggests, explains and flags. It never rejects on its own.
7. **Protected attributes are never read.** Age, gender, marital status, religion, caste and photos are not extracted or scored.

## The pipeline

```
intake ─► parse ─► extract facts ─► match skills ─► check limits ─► de-duplicate ─► rank and explain ─► export
 M5        1.0      M1 (built)        1.0             M2              M4              1.0                 M4
```

| Stage | Module | Input → output | State |
|---|---|---|---|
| Intake | `services/intake/` | Files, a chat export or pasted text → documents with a source label | Files only (1.0). Chat export: M5 |
| Parse | `services/parsing.py` | Bytes → text, or a reason a person must look | 1.0 |
| Extract facts | `services/facts.py` | Text → facts, each with value, unit, display text, quote and note; plus a list to ask | **M1, built** |
| Match skills | `services/skills.py`, `scoring.py` | Text and job → matched and missing skills, score | 1.0. Skill packs: M4 |
| Check limits | `services/limits.py` | Facts and the requirement's limits → pass, near-miss or ask | M2 |
| De-duplicate | `services/dedupe.py` | Candidates → groups sharing a phone or email | M4 |
| Rank and explain | `services/suggestions.py`, `screening.py` | All of the above → ordered list with reasons | 1.0 |
| Export | `services/tracker.py` | Candidates and a client template → CSV or XLSX | Fixed CSV (1.0). Templates: M4 |

## Core data shapes

```
Fact         value (number, text or none) · unit · display · quote · note
Candidate    1.0 fields + facts{phone, total_experience, notice_period, current_ctc,
             expected_ctc, current_location, preferred_location} + to_ask[]
Requirement  job description · must-haves · limits{max_notice_days, max_ctc_lpa,
             locations[], min_years} · client template           (M2, M4)
```

A fact with a display but no value means "the document says something, but not a number": for example "Negotiable" or "Serving notice". It stays on the call sheet.

## How extraction stays honest (M1, built)

- **Line-based rules** with India-specific reading: "LPA", lakhs and crores, "12,00,000", "45k per month", "5.10 years" as 5 years 10 months, "immediate joiner", "NP", "CCTC" and "ECTC".
- **Position rules.** A bare "CTC:" or "Location:" counts only where a field would start, and a bare "Location:" only near the top of the resume, so a past job's city isn't taken as the current one.
- **Abstention.** Foreign currency, amounts with no clear unit, out-of-range values and unlabelled guesses return nothing.
- **Conflicts are surfaced.** Two different values for one field keep the first, add a note and put the field on the call sheet.
- **The quote is the line itself,** so it can always be found in the source.

## The optional model layer (M6, not built)

```
rules ─► blanks and conflicts only ─► model returns {field, value, quote}
                                              │
                    quote appears verbatim in the source text?  ── no ──► discard
                                              │ yes
                    rule normaliser reads the same value from the quote?  ── no ──► discard
                                              │ yes
                                      accept, labelled "found by model"
```

- Off by default. Needs the agency's written consent, because resume text leaves the machine.
- A provider interface, so the model can be swapped. Start with the most capable Claude model to find the accuracy ceiling on the labelled set, then test whether a smaller one matches it. Cost per resume is to be measured, not assumed.
- It is never allowed to fill a field the rules already filled.

## Storage

| Tier | What's kept | When |
|---|---|---|
| None (default) | Nothing | 1.0 and M1 to M3 |
| Pilot log | Counts and timings only: files, fields found, seconds. No resume text | M3 |
| Workspace (opt-in) | Client templates; salted hashes of phone and email with requirement and date | M4 and M7 |

The workspace reuses the SQLite pattern already proven in `outreach/db.py`: one local file, owner-only permissions, standard library only.

## Security before any hosted pilot (M3)

- An access code per agency, checked by middleware.
- A cap on total request size, enforced while reading.
- A per-file time limit on parsing, using the existing worker processes.
- A rate limit, and API docs switched off in production.
- The page's script moved to its own file so a strict Content Security Policy can be set, as the outreach dashboard does.
- The Docker image built and run at least once.

**A local pilot needs none of this.** Running on the founder's laptop with the agency's files means no data leaves the room. That's the recommended way to run the first pilots.

## Testing and measurement

| Layer | What | Where |
|---|---|---|
| Unit tests | Each rule and each tricky phrasing | `tests/test_facts.py` |
| Labelled set | Short labelled cases, including traps that must return nothing | `evals/facts/gold.json` |
| Gate | No wrong value on the labelled set; coverage must not drop | `tests/test_facts_eval.py` |
| Report | Per-field found, missed and wrong | `python -m evals.facts` |
| API tests | New fields present; 1.0 fields unchanged | `tests/test_api.py` |

**The labelled set today is synthetic.** I wrote both the rules and the cases, so it proves the rules do what I intended. It does not prove accuracy on real resumes. Real numbers need real, consented resumes from pilots.

## Front end

Keep one page and plain JavaScript. An "Experienced hires" switch shows the new columns; with it off, the page and the CSV are exactly as in 1.0. No framework until there's a second screen that needs one.
