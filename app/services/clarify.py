"""Apply what a recruiter learned on a call, without ever touching the resume evidence.

Each field ends up with one of four sources:
- resume: the value extracted from the resume, unchanged
- recruiter_confirmed: the resume's value, confirmed by the candidate
- recruiter_entered: a value the recruiter typed, which is not resume evidence
- unknown: nothing usable yet

`facts` on a candidate always stays exactly as extracted. The values in use live in `resolved`.
"""

from __future__ import annotations

from dataclasses import replace

from app.schemas.clarifications import Answer, CandidateClarification
from app.schemas.screening import CandidateFacts, CandidateResult, ResolvedFact, ScreeningResult
from app.services.evaluation import STEP_ORDER, re_evaluate, review_order
from app.services.facts import ASK_FIELDS, FIELD_LABELS, FIELD_UNITS, Found, _number

# Believable ranges for typed answers. The page enforces them too; this is the backstop.
NUMBER_RANGES = {"total_experience": (0, 50), "notice_period": (0, 365), "current_ctc": (0.5, 500), "expected_ctc": (0.5, 500)}
TEXT_FIELDS = ("phone", "current_location", "preferred_location")
MAX_TEXT = 80


class ClarificationError(ValueError):
    """The recruiter's entry can't be used. The message says why, in plain words."""


def to_found(facts: CandidateFacts) -> dict[str, Found]:
    """The resume facts as the extractor's own type, so the same checks can run on them again."""
    found = {}
    for field in FIELD_LABELS:
        fact = getattr(facts, field)
        if fact is not None:
            found[field] = Found(fact.value, fact.display, fact.quote, fact.note, fact.confirm, fact.low, tuple(fact.tags))
    return found


def display_for(field: str, value: float | str) -> str:
    if field == "notice_period":
        return "Immediate" if value == 0 else f"{_number(value)} days"
    if field in ("current_ctc", "expected_ctc"):
        return f"{_number(value)} LPA"
    if field == "total_experience":
        return "Fresher" if value == 0 else f"{_number(value)} year{'' if value == 1 else 's'}"
    return str(value)


def _entered(field: str, answer: Answer) -> Found:
    label = FIELD_LABELS[field]
    if answer.value is None or (isinstance(answer.value, str) and not answer.value.strip()):
        raise ClarificationError(f"{label}: type the answer, or choose a different status.")
    if field in NUMBER_RANGES:
        low, high = NUMBER_RANGES[field]
        try:
            value: float | str = float(answer.value)
        except (TypeError, ValueError):
            raise ClarificationError(f"{label}: enter a number.") from None
        if not low <= value <= high:
            raise ClarificationError(f"{label}: enter a number from {_number(low)} to {_number(high)}.")
    else:
        value = " ".join(str(answer.value).split())
        if len(value) > MAX_TEXT:
            raise ClarificationError(f"{label}: keep it under {MAX_TEXT} characters.")
    note = "Entered by the recruiter; not on the resume." + (f" {answer.note.strip()}" if answer.note.strip() else "")
    return Found(value, display_for(field, value), "", note)


def resolve(facts: dict[str, Found], answers: dict[str, Answer]) -> tuple[dict[str, Found], dict[str, ResolvedFact]]:
    """The facts to evaluate with, and for every field where its value came from."""
    unknown = sorted(set(answers) - set(FIELD_LABELS))
    if unknown:
        raise ClarificationError(f"Unknown field: {', '.join(unknown)}.")
    in_use: dict[str, Found] = {}
    resolved: dict[str, ResolvedFact] = {}
    for field in FIELD_LABELS:
        resume = facts.get(field)
        answer = answers.get(field)
        state = answer.state if answer else None
        note = answer.note.strip() if answer else ""
        source = "resume"
        current = resume
        if state == "answered":
            current, source = _entered(field, answer), "recruiter_entered"
        elif state == "confirmed":
            if resume is None or resume.value is None:
                raise ClarificationError(f"{FIELD_LABELS[field]}: there is no value on the resume to confirm. Type the answer instead.")
            # Confirmed on the call, so it is no longer in doubt. The quote stays: it is still what the resume says.
            current, source = replace(resume, confirm=False), "recruiter_confirmed"
        if current is not None:
            in_use[field] = current
        usable = current is not None and current.value is not None
        resolved[field] = ResolvedFact(
            source=source if usable else "unknown",
            value=current.value if usable else None,
            unit=FIELD_UNITS.get(field) if usable else None,
            display=current.display if usable else None,
            resume_display=resume.display if resume else None,
            state=state,
            note=note,
        )
    return in_use, resolved


def questions(facts: dict[str, Found], answers: dict[str, Answer]) -> list[str]:
    """What is still open after the recruiter's entries, in tracker order."""
    ask = []
    for field in ASK_FIELDS:
        label = FIELD_LABELS[field]
        state = answers[field].state if field in answers else None
        if state in ("answered", "confirmed", "not_applicable"):
            continue
        fact = facts.get(field)
        if state == "pending":
            ask.append(f"{label}: asked, waiting for an answer")
        elif fact is None:
            ask.append(f"{label}: not on the resume")
        elif fact.value is None:
            ask.append(f"{label}: resume says \"{fact.display}\"")
        elif fact.confirm:
            ask.append(f"{label}: more than one figure on the resume")
    return ask


def resolve_candidate(candidate: CandidateResult, clarification: CandidateClarification | None, limits) -> None:
    """Fill in `resolved`, `to_ask`, `remarks` and the evaluation for one ranked candidate, in place."""
    answers = clarification.answers if clarification else {}
    in_use, resolved = resolve(to_found(candidate.facts), answers)
    candidate.resolved = resolved
    candidate.to_ask = questions(in_use, answers)
    candidate.remarks = clarification.remarks.strip() if clarification else ""
    candidate.evaluation = re_evaluate(candidate.evaluation, in_use, limits)


def apply(result: ScreeningResult, clarifications: dict[str, CandidateClarification]) -> ScreeningResult:
    """A new result with the recruiter's entries applied and everyone evaluated again.

    Pass the result as it came from the screening each time: applying is not cumulative.
    """
    if result.hiring_mode != "experienced" or result.requirements is None:
        raise ClarificationError("Call answers only apply to an experienced-hiring result.")
    updated = result.model_copy(deep=True)
    ranked = [c for c in updated.candidates if c.status == "ranked" and c.evaluation is not None]
    names = {c.file_name for c in ranked}
    strangers = sorted(set(clarifications) - names)
    if strangers:
        raise ClarificationError(f"No such candidate in this result: {', '.join(strangers)}.")
    for candidate in ranked:
        try:
            resolve_candidate(candidate, clarifications.get(candidate.file_name), updated.requirements)
        except ClarificationError as error:
            raise ClarificationError(f"{candidate.name or candidate.file_name}. {error}") from None
    ranked.sort(key=lambda c: review_order(c.evaluation, c.file_name))
    for position, candidate in enumerate(ranked, start=1):
        candidate.rank = position
    updated.candidates = ranked + [c for c in updated.candidates if c not in ranked]
    updated.next_step_counts = {key: sum(1 for c in ranked if c.evaluation.next_step.key == key) for key in STEP_ORDER}
    return updated
