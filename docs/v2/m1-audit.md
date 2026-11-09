# M1 audit: facts with evidence

Done 10 November 2026 on the six fictional experienced-hire samples, before starting M2. The scoring algorithm was not changed.

## Confirmed bugs, fixed

| # | Bug | How to reproduce (before the fix) | Fix |
|---|---|---|---|
| 1 | Evidence bullets had no text of their own. Label and quote sat in child elements, so the browser's accessibility tree listed each bullet as an empty item, and the quotation marks were CSS-only and vanished on copy | Load `/?demo=1` with the switch on, open "Where each value came from", read the page's accessibility tree: 27 list items, most with no name | The quote is now the bullet's own text with real quotation marks. The tool's remark is a separate line starting "Note:" |
| 2 | CSV number columns held words: "30% hike" under Expected CTC (LPA), "Serving notice" under Notice period (days) | Download the CSV with the switch on; see Lakshmi and Pooja | Number columns hold numbers or are blank. The words stay in "Ask on the call" |
| 3 | CSV dropped every caveat. Imran's expected CTC read 20 with no sign the resume says 18–20; Suresh's CTC read 9 with no sign the unit was assumed | Same file; compare with the page | New "Notes" column: ranges, conversions, assumed units, conflicts, last working day |
| 4 | "8.10 years" was read as 8 years 10 months without saying so | Lakshmi's row | A note now states the reading |

## Checked and sound

- **Evidence is stored.** Every fact in the API response carries `quote`; all 27 render on the page.
- **Quotes are copied, not generated.** Across the samples and the labelled cases, 95 of 95 quotes appear verbatim in the source, and each value can be re-read from its quote alone. Two tests now enforce this.
- **The 1.0 view is unchanged** with the switch off: same 7 columns, same 13-column CSV.

## Limits found, not changed

- **The score ignores facts.** It is 60% must-have skills, 30% other skills from the job description, 10% wording overlap. Tanvi scores 85 with no facts because she lists all three must-haves and six of nine other skills.
- **Missing information doesn't move the ranking.** Removing Divya's phone, location, notice period and CTC leaves her at 92 and first.
- **Facts that break the client's limits don't lower it either.** Adding a 90-day notice period, 40 LPA and Delhi to Tanvi's resume raised her score from 85 to 86, because the job description contains the words "notice period" and "location".
- **One avoidable miss:** Imran's "Location: Hyderabad" is skipped because a bare "Location:" is trusted only in the first 12 lines.
- **The page's CSV and rendering code has no automated tests.** It was checked by hand in the browser.

## Sample coverage

Covered: labelled rows, "CCTC/ECTC", a range, rupees per annum, a monthly salary, "30% hike", "8.10 years", an immediate joiner, serving notice with a last working day, two conflicting notice periods, per-skill experience, a CTC with no unit, a leading-zero phone, a bracketed "+91", and a resume that states nothing.

Not covered: a PDF or DOCX file, a file that can't be read, anyone in "Not a fit", a label and value on separate lines, "NP:", crores, a foreign currency, a duplicate candidate, and a candidate who breaks the client's stated limits clearly enough to matter once M2 exists.

## Recommended next

1. M2 as planned: apply the client's limits, and show near-misses. This is what makes Tanvi and Lakshmi's positions honest.
2. In M2, keep the wording-overlap part of the score from reading the job description's "limits" section.
3. Accept a bare "Location:" when the line next to it is another tracker field.
4. Add two samples: one unreadable file and one clear "Not a fit".
5. Move CSV building to the server, or add a browser test, so the export is covered by the test suite.
