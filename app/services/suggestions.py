"""Suggest a next step for each candidate: shortlist, maybe, or not a fit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.scoring import Score

Decision = Literal["shortlist", "maybe", "not_a_fit"]
DECISION_ORDER: dict[Decision, int] = {"shortlist": 0, "maybe": 1, "not_a_fit": 2}

# Used only when the recruiter gave no must-haves, so the score decides.
SHORTLIST_SCORE = 60
MAYBE_SCORE = 35
MAX_QUESTIONS = 3

_GAP_QUESTION = "The role needs {skill}. What's your experience with it, or with something similar?"
# Varied wording, so three questions about three skills don't read like a form.
_CHECK_QUESTIONS = (
    "Walk me through a project where you used {skill}. Which part did you do yourself?",
    "What's the hardest problem you've solved using {skill}, and how did you solve it?",
    "Where have you used {skill} outside coursework, and what did you learn?",
)


@dataclass(frozen=True)
class Suggestion:
    decision: Decision
    cgpa_note: str | None
    flags: list[str]
    interview_questions: list[str]


def suggest(score: Score, must_have_count: int, cgpa: float | None, min_cgpa: float | None) -> Suggestion:
    on_skills = _decide_on_skills(score, must_have_count)
    decision = on_skills
    flags: list[str] = []
    cgpa_note = None

    if min_cgpa is not None:
        if cgpa is None:
            flags.append("No CGPA found on the resume. Check it against the cut-off by hand.")
        elif cgpa < min_cgpa:
            decision = "not_a_fit"
            cgpa_note = f"CGPA {format_cgpa(cgpa)} is below the {format_cgpa(min_cgpa)} cut-off."
            if on_skills == "shortlist":
                flags.append("Would be shortlisted on skills. Only the CGPA cut-off rules them out.")
        else:
            cgpa_note = f"CGPA {format_cgpa(cgpa)} meets the {format_cgpa(min_cgpa)} cut-off."

    return Suggestion(
        decision=decision,
        cgpa_note=cgpa_note,
        flags=flags,
        interview_questions=[] if decision == "not_a_fit" else _questions(score),
    )


def format_cgpa(value: float) -> str:
    """7.0 -> "7.0", 8.25 -> "8.25", 8.70 -> "8.7"."""
    text = f"{value:.2f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def _decide_on_skills(score: Score, must_have_count: int) -> Decision:
    if must_have_count:
        missing = len(score.must_haves_missing)
        if missing == 0:
            return "shortlist"
        if missing == 1 and must_have_count >= 2:
            return "maybe"
        return "not_a_fit"
    if score.total >= SHORTLIST_SCORE:
        return "shortlist"
    if score.total >= MAYBE_SCORE:
        return "maybe"
    return "not_a_fit"


def _questions(score: Score) -> list[str]:
    """Probe the gaps first, then check that the skills they claim are real."""
    questions = [_GAP_QUESTION.format(skill=skill) for skill in score.must_haves_missing]
    to_check = score.must_haves_matched or score.other_skills_matched
    questions += [
        _CHECK_QUESTIONS[index % len(_CHECK_QUESTIONS)].format(skill=skill)
        for index, skill in enumerate(to_check)
    ]
    return questions[:MAX_QUESTIONS]
