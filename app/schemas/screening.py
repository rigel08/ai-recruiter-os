from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["shortlist", "maybe", "not_a_fit"]


class Fact(BaseModel):
    """One value taken from the resume, with the line that proves it."""

    value: float | str | None = Field(description="Normalised value; null when the resume says something that isn't a value")
    unit: str | None = Field(default=None, description="years, days or LPA; null for text")
    display: str
    quote: str = Field(description="The exact line from the resume")
    note: str | None = None
    confirm: bool = Field(default=False, description="The resume is unclear here; check on the call")
    low: float | None = Field(default=None, description="Lower end when the resume gives a range; `value` is the upper end")


class CandidateFacts(BaseModel):
    """Fields a recruiter's tracker needs. A field is null when the resume doesn't state it."""

    phone: Fact | None = None
    total_experience: Fact | None = None
    notice_period: Fact | None = None
    current_ctc: Fact | None = None
    expected_ctc: Fact | None = None
    current_location: Fact | None = None
    preferred_location: Fact | None = None


class CandidateResult(BaseModel):
    file_name: str
    status: Literal["ranked", "needs_review"]
    rank: int | None = None
    decision: Decision | None = Field(default=None, description="The suggested next step")
    score: int | None = Field(default=None, ge=0, le=100)
    name: str | None = None
    email: str | None = None
    cgpa: float | None = None
    must_haves_matched: list[str] = Field(default_factory=list)
    must_haves_missing: list[str] = Field(default_factory=list)
    other_skills_matched: list[str] = Field(default_factory=list)
    summary: str
    flags: list[str] = Field(default_factory=list, description="Things a person should double-check")
    interview_questions: list[str] = Field(default_factory=list)
    facts: CandidateFacts = Field(default_factory=CandidateFacts)
    to_ask: list[str] = Field(default_factory=list, description="Tracker fields the recruiter still has to ask about")


class ScreeningResult(BaseModel):
    must_haves: list[str]
    other_skills: list[str] = Field(description="Skills found in the job description that aren't must-haves")
    min_cgpa: float | None
    ranked_count: int
    needs_review_count: int
    decision_counts: dict[Decision, int]
    fact_coverage: dict[str, int] = Field(
        default_factory=dict, description="For each tracker field, how many ranked resumes gave a usable value"
    )
    candidates: list[CandidateResult] = Field(
        description="Ranked candidates first (shortlist, then maybe, then not a fit), then files that need a person to look"
    )
