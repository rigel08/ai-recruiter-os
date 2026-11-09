# AI Recruiter OS 2.0: plan

Written 10 November 2026 on the `v2` branch. The 1.0 state is preserved on `main` and tagged `v1-baseline`.

**A gap to flag first.** The "2.0 development brief" and "Autonomous Innovation Directive" were not in the conversation this plan was written from. Everything here is built from the code, the docs and `research/market-validation/`. If the brief sets constraints this plan breaks, the brief wins.

## The plan in one paragraph

Stop competing on ranking. Naukri, Zoho, Manatal and Recruit CRM already ship AI ranking, and ChatGPT does a passable job for free. Build the **submission desk** instead: take resumes and candidate messages however they arrive, and produce the client's tracker with every number traced to the sentence it came from, plus a list of what the recruiter still has to ask on the call. The edge is **verification, not a bigger model**: the product leaves a field blank before it guesses, and it measures and publishes its own error rate.

## Documents

| File | What it answers |
|---|---|
| [audit.md](audit.md) | What exists, what's sound, what's risky |
| [innovation-strategy.md](innovation-strategy.md) | Which assumptions are wrong, and the ideas worth building beyond the original list |
| [architecture.md](architecture.md) | How 2.0 is structured, and the rules every new part follows |
| [roadmap.md](roadmap.md) | Milestones in order, each with a gate that must be met before the next is built |

## Where it stands

| Milestone | State |
|---|---|
| M0. Baseline, branch, plan | Done |
| M1. Candidate facts with evidence | Done on `v2` (see [roadmap.md](roadmap.md)) |
| M2 onwards | Not started. M4 onwards is gated on evidence from discovery calls |
