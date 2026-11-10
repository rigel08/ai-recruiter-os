"""What the job-description reader returns: suggestions for the recruiter to confirm or change."""

from typing import Literal

from pydantic import BaseModel, Field

Basis = Literal["explicit", "suggested"]


class JobDescriptionIn(BaseModel):
    job_description: str = Field(min_length=30, max_length=20_000)


class ValueSuggestion(BaseModel):
    value: float
    basis: Basis = Field(description="explicit: stated outright. suggested: worded as a preference or only hinted at")
    quote: str = Field(description="The sentence it came from")
    note: str | None = None


class SkillSuggestion(BaseModel):
    name: str
    basis: Basis
    quote: str


class LocationSuggestion(BaseModel):
    values: list[str]
    basis: Basis
    quote: str
    note: str | None = None


class JobRequirements(BaseModel):
    """Nothing here is applied until the recruiter sends it back with a screening request."""

    required_skills: list[SkillSuggestion]
    preferred_skills: list[SkillSuggestion]
    min_experience_years: ValueSuggestion | None
    max_experience_years: ValueSuggestion | None
    max_notice_days: ValueSuggestion | None
    max_ctc_lpa: ValueSuggestion | None
    locations: LocationSuggestion | None
    other: list[str] = Field(description="Other stated conditions. Shown for the recruiter; not evaluated")
    notes: list[str] = Field(description="Things that were ambiguous in the job description")
