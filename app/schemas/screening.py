from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["shortlist", "maybe", "not_a_fit"]


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


class ScreeningResult(BaseModel):
    must_haves: list[str]
    other_skills: list[str] = Field(description="Skills found in the job description that aren't must-haves")
    min_cgpa: float | None
    ranked_count: int
    needs_review_count: int
    decision_counts: dict[Decision, int]
    candidates: list[CandidateResult] = Field(
        description="Ranked candidates first (shortlist, then maybe, then not a fit), then files that need a person to look"
    )
