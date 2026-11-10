"""Evaluate one candidate against the requirements the recruiter confirmed.

Three things are kept apart and never folded into one number:

1. Skills and experience fit: which required and preferred skills the resume shows, and whether
   the stated experience is in range. Wording overlap with the job description is not counted.
2. Client limits: notice period, CTC and location, each with its own status and reason.
3. Information: how many tracker fields the resume states.

Statuses never reject anyone. "Unknown" means the resume doesn't say, which is a question for
the call, not a mismatch.
"""

from __future__ import annotations

from typing import Literal

from app.schemas.screening import (
    Completeness, ConstraintsFit, Evaluation, NextStep, RequirementCheck, SkillsFit,
)
from app.services.facts import ASK_FIELDS, FIELD_LABELS, Found, _number
from app.services.locations import canonical_city, cities_in, open_to_anywhere
from app.services.requirements import Requirements

Status = Literal["meets", "near", "does_not_meet", "unknown", "needs_review"]

# How far outside a limit still counts as a near match. Stated in every reason, so it's visible.
NEAR_NOTICE_DAYS = 15
NEAR_CTC_SHARE = 0.10
NEAR_YEARS = 0.5

# Share of the skills score. There is no wording-similarity part.
REQUIRED_WEIGHT, PREFERRED_WEIGHT = 0.7, 0.3
STRONG_SCORE, PARTIAL_SCORE = 60, 35  # used only when no required skills were set

# Worst first: what the "client limits" summary reports when checks disagree.
SEVERITY: tuple[Status, ...] = ("does_not_meet", "needs_review", "near", "unknown", "meets")
STEP_ORDER = {"ready": 0, "clarify": 1, "check": 2, "conflict": 3, "low_fit": 4}
STEP_LABELS = {
    "ready": "Looks ready",
    "clarify": "Clarify first",
    "check": "Check by hand",
    "conflict": "Conflicts with a limit",
    "low_fit": "Low skills fit",
}
LEVEL_ORDER = {"strong": 0, "partial": 1, "not_set": 1, "weak": 2}


def _check(key: str, label: str, required: str, status: Status, reason: str, candidate: str | None) -> RequirementCheck:
    return RequirementCheck(requirement=key, label=label, required=required, status=status, reason=reason, candidate=candidate)


def _years_text(value: float) -> str:
    return f"{_number(value)} year{'' if value == 1 else 's'}"


# Individual checks -----------------------------------------------------------------------------------

def check_experience(fact: Found | None, minimum: float | None, maximum: float | None) -> RequirementCheck | None:
    if minimum is None and maximum is None:
        return None
    if minimum is not None and maximum is not None:
        required = f"{_number(minimum)} to {_number(maximum)} years"
    elif minimum is not None:
        required = f"{_years_text(minimum)} or more"
    else:
        required = f"up to {_years_text(maximum)}"

    def result(status: Status, reason: str) -> RequirementCheck:
        return _check("experience", "Experience", required, status, reason, fact.display if fact else None)

    if fact is None:
        return result("unknown", "Total experience isn't stated on the resume.")
    if fact.value is None:
        return result("needs_review", f"The resume gives no total: {fact.display}.")
    if fact.confirm:
        return result("needs_review", f"The resume gives more than one figure ({fact.display} is the first). Confirm the total.")
    years = float(fact.value)
    if minimum is not None and years < minimum:
        short = minimum - years
        if short <= NEAR_YEARS:
            return result("near", f"{fact.display} is {_months(short)} short of the {_years_text(minimum)} asked for.")
        return result("does_not_meet", f"{fact.display} is below the {_years_text(minimum)} asked for.")
    if maximum is not None and years > maximum:
        over = years - maximum
        if over <= NEAR_YEARS:
            return result("near", f"{fact.display} is {_months(over)} over the {_years_text(maximum)} upper limit.")
        return result("does_not_meet", f"{fact.display} is above the {_years_text(maximum)} upper limit.")
    return result("meets", f"{fact.display} is within {required}.")


def _months(years: float) -> str:
    months = max(1, round(years * 12))
    return f"{months} month{'' if months == 1 else 's'}"


def check_notice(fact: Found | None, maximum: float | None) -> RequirementCheck | None:
    if maximum is None:
        return None
    required = "Immediate" if maximum == 0 else f"{_number(maximum)} days or less"

    def result(status: Status, reason: str) -> RequirementCheck:
        return _check("notice_period", "Notice period", required, status, reason, fact.display if fact else None)

    if fact is None:
        return result("unknown", "Notice period isn't stated on the resume.")
    if fact.value is None:
        # "Serving notice" has no day count, and none is invented.
        detail = f" {fact.note}" if fact.note else ""
        return result("needs_review", f"The resume says \"{fact.display}\" without a number of days.{detail}")
    if fact.confirm:
        return result("needs_review", f"The resume gives two different notice periods ({fact.display} is the first).")
    days = float(fact.value)
    if days <= maximum:
        return result("meets", f"{fact.display} is within the {_number(maximum)}-day limit.")
    over = days - maximum
    if fact.low is not None and fact.low <= maximum:
        return result("near", f"The resume gives a range ({_number(fact.low)} to {_number(days)} days) that starts within the limit.")
    if "negotiable" in fact.tags:
        return result("near", f"{fact.display} is {_number(over)} days over the limit, but the resume says it can be shortened.")
    if over <= NEAR_NOTICE_DAYS:
        return result("near", f"{fact.display} is {_number(over)} days over the {_number(maximum)}-day limit.")
    return result("does_not_meet", f"{fact.display} is {_number(over)} days over the {_number(maximum)}-day limit.")


def check_ctc(expected: Found | None, current: Found | None, maximum: float | None) -> RequirementCheck | None:
    if maximum is None:
        return None
    required = f"up to {_number(maximum)} LPA"
    budget = f"the {_number(maximum)} LPA budget"
    current_known = current is not None and current.value is not None
    above = current_known and float(current.value) > maximum
    current_text = f" Current CTC ({current.display}) is already above {budget}." if above else (
        f" Current CTC is {current.display}, within the budget." if current_known else "")

    def result(status: Status, reason: str) -> RequirementCheck:
        shown = f"Expects {expected.display}" if expected else (f"Current {current.display}" if current else None)
        return _check("ctc", "CTC", required, status, reason, shown)

    if expected is None:
        if above:
            return result("needs_review", f"Expected CTC isn't stated.{current_text}")
        return result("unknown", f"Expected CTC isn't stated on the resume.{current_text}")
    if expected.value is None:
        return result("needs_review", f"Expected CTC on the resume is \"{expected.display}\", not a figure.{current_text if above else ''}")
    if expected.confirm:
        return result("needs_review", f"The resume gives two different expected figures ({expected.display} is the first).")
    amount = float(expected.value)
    if amount <= maximum:
        return result("meets", f"Expects {expected.display}, within {budget}.")
    if expected.low is not None and expected.low <= maximum:
        return result("near", f"Expects {expected.display}; the lower end is within {budget}.")
    over = amount - maximum
    if over <= maximum * NEAR_CTC_SHARE:
        return result("near", f"Expects {expected.display}, {_number(over)} LPA over {budget} (within {round(NEAR_CTC_SHARE * 100)}%).")
    return result("does_not_meet", f"Expects {expected.display}, {_number(over)} LPA over {budget}.")


def check_location(current: Found | None, preferred: Found | None, accepted: list[str]) -> RequirementCheck | None:
    if not accepted:
        return None
    required = " or ".join(accepted)

    def result(status: Status, reason: str) -> RequirementCheck:
        return _check("location", "Location", required, status, reason, current.display if current else None)

    wanted = {place.lower() for place in accepted}
    prefers = preferred.display if preferred else ""
    prefers_match = [city for city in cities_in(prefers) if city.lower() in wanted]
    if current is None:
        extra = f" It lists {prefers_match[0]} as a preferred location." if prefers_match else ""
        return result("unknown", f"Current location isn't stated on the resume.{extra}")
    stated = str(current.value)
    city = canonical_city(stated)
    if (city or stated).lower() in wanted:
        return result("meets", f"Currently in {current.display}.")
    if city is None:
        return result("needs_review", f"\"{current.display}\" isn't a place on the built-in city list, so it can't be compared.")
    if prefers_match:
        return result("near", f"Currently in {city}; the resume lists {prefers_match[0]} as a preferred location.")
    if preferred and open_to_anywhere(prefers):
        return result("near", f"Currently in {city}; the resume says \"{preferred.display}\".")
    return result("does_not_meet", f"Currently in {city}; the role is in {required}.")


# The three dimensions ----------------------------------------------------------------------------------

def skills_fit(text: str, requirements: Requirements, experience: RequirementCheck | None) -> SkillsFit:
    required_matched = [term.name for term in requirements.required_skills if term.found_in(text)]
    required_missing = [term.name for term in requirements.required_skills if term.name not in required_matched]
    preferred_matched = [term.name for term in requirements.preferred_skills if term.found_in(text)]
    preferred_missing = [term.name for term in requirements.preferred_skills if term.name not in preferred_matched]

    parts: list[tuple[float, float]] = []
    if requirements.required_skills:
        parts.append((REQUIRED_WEIGHT, len(required_matched) / len(requirements.required_skills)))
    if requirements.preferred_skills:
        parts.append((PREFERRED_WEIGHT, len(preferred_matched) / len(requirements.preferred_skills)))
    score = round(100 * sum(weight * share for weight, share in parts) / sum(weight for weight, _ in parts)) if parts else None

    if requirements.required_skills:
        if not required_missing:
            level = "strong"
        elif len(required_missing) == 1 and len(requirements.required_skills) >= 2:
            level = "partial"
        else:
            level = "weak"
    elif score is None:
        level = "not_set"
    else:
        level = "strong" if score >= STRONG_SCORE else "partial" if score >= PARTIAL_SCORE else "weak"

    sentences = []
    if requirements.required_skills:
        text_missing = f"; missing {', '.join(required_missing)}" if required_missing else ""
        sentences.append(f"Has {len(required_matched)} of {len(requirements.required_skills)} required skills{text_missing}.")
    if requirements.preferred_skills:
        sentences.append(f"Has {len(preferred_matched)} of {len(requirements.preferred_skills)} preferred skills.")
    if score is None:
        sentences.append("No skills were set, so skills fit wasn't scored.")
    elif len(parts) == 2:
        sentences.append(f"Score {score} = {round(REQUIRED_WEIGHT * 100)}% required skills + {round(PREFERRED_WEIGHT * 100)}% preferred skills.")
    else:
        sentences.append(f"Score {score} is the share of those skills found.")
    if experience is not None and experience.status == "does_not_meet" and level == "strong":
        level = "partial"
        sentences.append("Shown as partial, not strong, because the stated experience is outside the range asked for.")

    return SkillsFit(
        level=level, score=score,
        required_matched=required_matched, required_missing=required_missing,
        preferred_matched=preferred_matched, preferred_missing=preferred_missing,
        experience=experience, explanation=" ".join(sentences),
    )


def constraints_fit(checks: list[RequirementCheck]) -> ConstraintsFit:
    if not checks:
        return ConstraintsFit(overall="none_set", checks=[], summary="No client limits were set.")
    overall = next(status for status in SEVERITY if any(check.status == status for check in checks))
    words = {"meets": "meets", "near": "near match", "does_not_meet": "does not meet", "unknown": "unknown",
             "needs_review": "check by hand"}
    counted = [f"{sum(1 for c in checks if c.status == status)} {words[status]}"
               for status in SEVERITY if any(c.status == status for c in checks)]
    return ConstraintsFit(overall=overall, checks=checks, summary=", ".join(counted))


def completeness(facts: dict[str, Found]) -> Completeness:
    stated, missing, unclear = [], [], []
    for field in ASK_FIELDS:
        fact = facts.get(field)
        label = FIELD_LABELS[field]
        if fact is None:
            missing.append(label)
        elif fact.value is None or fact.confirm:
            unclear.append(label)
        else:
            stated.append(label)
    return Completeness(stated=len(stated), total=len(ASK_FIELDS), missing=missing, unclear=unclear)


def next_step(skills: SkillsFit, constraints: ConstraintsFit) -> NextStep:
    """A one-line summary. It reports the most serious thing found and never hides a conflict.

    Order of checks: low skills fit, then any limit that isn't met, then anything to check by
    hand or nearly met, then anything unknown. Only when none of those apply is it "ready".
    """
    checks = ([skills.experience] if skills.experience else []) + constraints.checks

    def labels(*statuses: str) -> str:
        # "Notice period" -> "notice period", but "CTC" stays "CTC".
        return ", ".join(check.label if check.label.isupper() else check.label.lower()
                         for check in checks if check.status in statuses)

    if skills.level == "weak":
        conflict = f" Also conflicts on: {labels('does_not_meet')}." if labels("does_not_meet") else ""
        missing = f"Missing required skills: {', '.join(skills.required_missing)}." if skills.required_missing else "Few of the skills asked for were found."
        return _step("low_fit", missing + conflict)
    if labels("does_not_meet"):
        return _step("conflict", f"Does not meet: {labels('does_not_meet')}. Discuss with the client or the candidate before submitting.")
    if labels("needs_review", "near"):
        return _step("check", f"Needs a closer look: {labels('needs_review', 'near')}.")
    if labels("unknown"):
        return _step("clarify", f"Not on the resume: {labels('unknown')}. Ask on the call.")
    if not checks:
        return _step("ready", "No limits were set, so only skills were checked.")
    return _step("ready", "Meets every requirement that was checked.")


def _step(key: str, reason: str) -> NextStep:
    return NextStep(key=key, label=STEP_LABELS[key], reason=reason)


def evaluate(text: str, facts: dict[str, Found], requirements: Requirements) -> Evaluation:
    experience = check_experience(facts.get("total_experience"), requirements.min_experience_years,
                                  requirements.max_experience_years)
    checks = [check for check in (
        check_notice(facts.get("notice_period"), requirements.max_notice_days),
        check_ctc(facts.get("expected_ctc"), facts.get("current_ctc"), requirements.max_ctc_lpa),
        check_location(facts.get("current_location"), facts.get("preferred_location"), requirements.locations),
    ) if check is not None]
    skills = skills_fit(text, requirements, experience)
    constraints = constraints_fit(checks)
    return Evaluation(skills=skills, constraints=constraints, completeness=completeness(facts),
                      next_step=next_step(skills, constraints))


def review_order(evaluation: Evaluation, file_name: str) -> tuple:
    """Sort key for experienced hiring. Nobody is removed; this only decides who is read first."""
    return (STEP_ORDER[evaluation.next_step.key], LEVEL_ORDER[evaluation.skills.level],
            -(evaluation.skills.score or 0), file_name.lower())
