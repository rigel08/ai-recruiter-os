# Innovation strategy

Written 10 November 2026. No agency has been interviewed yet, so every "why" below is a hypothesis. Labels: **Verified** (in code or on a vendor page), **Reported** (third-party source), **Assumption** (my inference).

## The thesis

**Be the submission desk, not the ranker.**

A recruiter's deliverable isn't a ranking. It's a row in a client's tracker: name, phone, total experience, current and expected CTC, notice period, location. Getting to that row from a pile of PDFs, WhatsApp messages and Naukri downloads is the slow, error-prone part (Reported: foundit survey; Assumption until calls confirm).

So the product's job is:
1. Read everything, from any channel.
2. Fill the tracker, and show the sentence behind every value.
3. Leave a field blank when unsure, and turn the blanks into a call sheet.
4. Check the client's hard limits, and explain near-misses.
5. Export in the client's own format.

**The edge is trust.** ChatGPT can invent a CTC. A value here either has a quote you can read or it's blank.

## Assumptions I think are wrong

| Assumption | Why I doubt it | What to do instead |
|---|---|---|
| "2.0 should be built now" | The research verdict was: build only once two agencies commit real data. Nothing has changed since | Build the small part that makes the pitch honest (M1 to M3). Gate everything else on call evidence |
| "It's an OS" | An OS means an ATS, and that market belongs to Zoho, Manatal and Recruit CRM | Stay a tool that sits beside Excel and whatever they already use |
| "AI means a large language model" | Models are a commodity, and they invent values | Rules first. Add a model only where rules leave blanks, and only if every value it returns passes a quote check |
| "A better score wins" | For experienced hires, a 60-day notice period or a CTC over budget ends the conversation, whatever the score | Limits first, score second |
| "The resume has the data" | Recruiters will say notice period and CTC come from the call or the WhatsApp chat, not the resume (objection 11 in the research) | Expect low coverage from resumes. Make the "ask on call" list and message intake first-class |
| "Nothing stored is always a virtue" | Duplicate checks, templates and pilot measurement all need memory | Stay stateless by default. Add an opt-in workspace that stores as little as possible |
| "One product for campus and agencies" | CGPA matters to one and is noise to the other | An explicit mode. Campus stays exactly as it is |

## Ideas, ranked by value against risk

### Build first

**1. Evidence-locked facts (M1, built).** Phone, total experience, notice period, current and expected CTC and location, each with the line it came from. A blank beats a wrong value.

**2. The call sheet (M2).** Every blank or unclear field becomes a line to ask: "Notice period: not on resume", "Expected CTC: resume says negotiable". This turns the tool's biggest weakness (the data often isn't in the resume) into the recruiter's script. After the call, they type the answers and the tracker is complete.

**3. Near-miss, never silent rejection (M2).** A limit such as "notice up to 30 days" doesn't drop a 45-day candidate. It says "15 days over: ask about buyout". Recruiters know which limits bend (Assumption).

**4. A measured error rate (M1 onwards).** A labelled test set and a report of wrong values and coverage per field. Each pilot's corrections grow the set, with consent. "Here is our measured error rate on your resumes" is something no competitor's sales page says (Verified on the four vendor pages read).

### Build when calls confirm

**5. Message-aware intake (M5).** Read a WhatsApp chat export and pair each resume with what the candidate typed ("NP 30 days, ECTC 12"). That's where the missing fields live (Assumption). Gate: at least two agencies say a quarter or more of their resumes arrive outside Naukri.

**6. The client's tracker, exactly (M4).** Column order, names and units per client, saved as a template, exported as XLSX. Gate: one real blank tracker in hand.

**7. Enterprise-IT skill packs (M4).** SAP and Oracle modules with their spellings (FICO, FI/CO, S/4HANA Finance). Cheap, and directly relevant to two of the top ten prospects.

**8. Experience from dates (M6).** Add up job date ranges, handle overlaps, flag gaps, and show the ranges as evidence beside what the candidate claims.

**9. A requirement reader (M2 or M4).** Pull the limits out of the JD itself ("immediate joiners", "up to 18 LPA", "Hyderabad only") and ask the recruiter to confirm.

### Build only if paying agencies ask

**10. Submission memory (M7).** "This candidate was already sent to this client on 3 October." Duplicate submissions cause fee disputes (Assumption). Privacy-preserving design: store only a salted hash of phone and email with the requirement and date. No resumes and no names.

**11. A clean candidate profile for the client (M7).** A one-page summary in the agency's format, without the candidate's phone and email, and without date of birth, marital status or photo. Agencies commonly mask contact details so clients can't go around them (Assumption: confirm on calls). It also minimises personal data, which fits DPDP.

**12. An evidence-locked model pass (M6).** A language model fills only the fields rules left blank. Every value must come with a verbatim quote that is found in the source text and that the rule-based normaliser reads to the same value. Anything else is discarded. Gate: at least 100 real, consented, labelled resumes to measure it on.

**13. A joining-risk checklist (after pilots).** Prompts, not predictions: a 90-day notice period, a large expected hike, a relocation. There's no outcome data to justify a score, so it shouldn't pretend to be one.

## What I would not build

- **An ATS, a candidate database or sourcing.** Crowded, and Naukri owns the candidates.
- **Automated candidate outreach or a WhatsApp bot.** Naukri's AI REX already does it, and it needs WhatsApp Business approval.
- **Automatic rejection.** A person decides. The tool suggests and explains.
- **Personality scoring, video analysis or "fraud detection".** No evidence base, high bias risk.
- **Anything that uses age, gender, marital status or a photo.** Never extracted, never scored.

## How this could fail

1. **Most resumes come from Naukri and AI REX covers them.** Then there's no room. This is the first question on every call.
2. **Coverage is too low to feel useful.** If resumes rarely state notice period and CTC, M1 alone looks empty. Ideas 2 and 5 are the answer, and they need call evidence first.
3. **Line-based rules break on messy PDFs.** Two-column layouts scramble the text. The measured error rate will show this early.
4. **The price ceiling stays low.** At ₹1,999 an agency, 50 agencies is about ₹12 lakh a year. Per-requirement pricing is worth testing once pilots run.
