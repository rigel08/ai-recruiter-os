"""Build the CSV download from a screening result.

Campus results produce exactly the 1.0 file. Experienced-hiring results produce a wider file
with the evaluation, the facts, what to ask and the evidence.
"""

from __future__ import annotations

import re

from app.schemas.screening import CandidateResult, RequirementCheck, ScreeningResult

BOM = "﻿"  # makes Excel open the file as UTF-8
DECISION_LABELS = {"shortlist": "Shortlist", "maybe": "Maybe", "not_a_fit": "Not a fit"}
STATUS_LABELS = {"meets": "Meets", "near": "Near match", "does_not_meet": "Does not meet", "unknown": "Unknown",
                 "needs_review": "Check by hand"}
LEVEL_LABELS = {"strong": "Strong", "partial": "Partial", "weak": "Weak", "not_set": "Not scored"}
NEEDS_REVIEW = "Needs a manual look"

CAMPUS_HEADER = ["Rank", "Suggestion", "Name", "Email", "CGPA", "Score", "File", "Must-haves matched",
                 "Must-haves missing", "Other skills matched", "Summary", "Flags", "Interview questions"]
FACT_COLUMNS = [("phone", "Phone"), ("total_experience", "Total experience (years)"),
                ("notice_period", "Notice period (days)"), ("current_ctc", "Current CTC (LPA)"),
                ("expected_ctc", "Expected CTC (LPA)"), ("current_location", "Current location"),
                ("preferred_location", "Preferred location")]
FACT_NAMES = {"phone": "Phone", "total_experience": "Total experience", "notice_period": "Notice period",
              "current_ctc": "Current CTC", "expected_ctc": "Expected CTC", "current_location": "Current location",
              "preferred_location": "Preferred location"}
EXPERIENCED_HEADER = (
    ["Rank", "Next step", "Why", "Name", "Email", "File",
     "Skills fit", "Skills score", "Required skills matched", "Required skills missing", "Preferred skills matched",
     "Experience check", "Notice period check", "CTC check", "Location check", "Information stated"]
    + [title for _, title in FACT_COLUMNS]
    + ["Ask on the call", "Notes", "Evidence", "Interview questions"]
)

_FORMULA_START = re.compile(r"^[=+\-@\t\r]")


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value)


def _cell(value) -> str:
    """Quote a cell. Values come from resumes, so stop spreadsheet apps treating them as formulas."""
    text = _text(value)
    if _FORMULA_START.match(text):
        text = "'" + text
    return '"' + text.replace('"', '""') + '"'


def _ask_text(items: list[str]) -> str:
    """ "Notice period: not on the resume" -> "Notice period"; other reasons are kept in brackets."""
    parts = []
    for item in items:
        label, _, reason = item.partition(": ")
        parts.append(label if reason == "not on the resume" else f"{label} ({reason})")
    return ", ".join(parts)


def _check_text(check: RequirementCheck | None) -> str:
    return "Not set" if check is None else f"{STATUS_LABELS[check.status]}: {check.reason}"


def _campus_row(c: CandidateResult) -> list:
    ranked = c.status == "ranked"
    return [c.rank, DECISION_LABELS[c.decision] if ranked else NEEDS_REVIEW, c.name, c.email, c.cgpa, c.score,
            c.file_name, "; ".join(c.must_haves_matched), "; ".join(c.must_haves_missing),
            "; ".join(c.other_skills_matched), c.summary, " ".join(c.flags), " | ".join(c.interview_questions)]


def _experienced_row(c: CandidateResult) -> list:
    if c.status != "ranked" or c.evaluation is None:
        blanks = len(EXPERIENCED_HEADER) - 6
        return ["", NEEDS_REVIEW, c.summary, c.name, c.email, c.file_name] + [""] * blanks
    e = c.evaluation
    by_key = {check.requirement: check for check in e.constraints.checks}
    facts = {key: getattr(c.facts, key) for key, _ in FACT_COLUMNS}
    present = {key: fact for key, fact in facts.items() if fact is not None}

    values = []
    for key, _ in FACT_COLUMNS:
        fact = facts[key]
        # A value only where the resume gives one: words such as "Negotiable" stay out of number columns.
        if fact is None or fact.value is None:
            values.append("")
        elif key == "phone":
            values.append(str(fact.value).lstrip("+"))  # no leading "+", so the formula guard leaves it alone
        else:
            values.append(fact.value)

    notes = []
    for key, fact in present.items():
        parts = []
        if fact.unit and f"{_text(fact.value)} {fact.unit}" != fact.display:
            parts.append(f'shown as "{fact.display}"')
        if fact.note:
            parts.append(fact.note)
        if parts:
            notes.append(f"{FACT_NAMES[key]}: {'; '.join(parts)}")
    evidence = [f'{FACT_NAMES[key]}: "{fact.quote}"' for key, fact in present.items()]

    return [
        c.rank, e.next_step.label, e.next_step.reason, c.name, c.email, c.file_name,
        LEVEL_LABELS[e.skills.level], e.skills.score, "; ".join(e.skills.required_matched),
        "; ".join(e.skills.required_missing), "; ".join(e.skills.preferred_matched),
        _check_text(e.skills.experience), _check_text(by_key.get("notice_period")), _check_text(by_key.get("ctc")),
        _check_text(by_key.get("location")), f"{e.completeness.stated} of {e.completeness.total}",
        *values, _ask_text(c.to_ask), " | ".join(notes), " | ".join(evidence), " | ".join(c.interview_questions),
    ]


def to_csv(result: ScreeningResult) -> str:
    experienced = result.hiring_mode == "experienced"
    header = EXPERIENCED_HEADER if experienced else CAMPUS_HEADER
    row = _experienced_row if experienced else _campus_row
    lines = [",".join(_cell(title) for title in header)]
    lines += [",".join(_cell(value) for value in row(candidate)) for candidate in result.candidates]
    return BOM + "\r\n".join(lines)
