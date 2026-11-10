"""A client submission: drafted from a screening result, edited by the recruiter, then exported."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.clarifications import CandidateClarification
from app.schemas.screening import ScreeningResult

FieldSource = Literal["resume", "recruiter_confirmed", "recruiter_entered", "worked_out", "unknown"]
CheckLevel = Literal["conflict", "warning", "note"]


class ProfileField(BaseModel):
    key: str
    label: str
    value: str | None = Field(description="Null when it isn't known. Never filled with a guess")
    source: FieldSource
    contact: bool = Field(default=False, description="Phone and email: left out unless the recruiter asks for them")
    included: bool = True


class PreflightCheck(BaseModel):
    level: CheckLevel
    text: str


class ProfileDraft(BaseModel):
    file_name: str
    name: str
    summary: str = Field(max_length=3_000)
    strengths: list[str]
    remarks: str = Field(default="", max_length=2_000)
    fields: list[ProfileField]
    missing: list[str] = Field(default_factory=list, description="Labels of fields that aren't known")
    checks: list[PreflightCheck] = Field(default_factory=list)


class SubmissionDraftRequest(BaseModel):
    result: ScreeningResult
    clarifications: dict[str, CandidateClarification] = Field(default_factory=dict)
    file_names: list[str] = Field(min_length=1, max_length=50)
    title: str = Field(default="", max_length=200)


class SubmissionDraft(BaseModel):
    title: str
    prepared_on: date
    profiles: list[ProfileDraft]
    checks: list[PreflightCheck] = Field(description="Checks across the whole submission, such as duplicates")


class SubmissionDocument(BaseModel):
    """The submission as the recruiter finalised it. This is what gets exported."""

    title: str = Field(max_length=200)
    prepared_on: date | None = None
    include_contact: bool = Field(default=False, description="Phone and email are dropped unless this is true")
    show_sources: bool = True
    profiles: list[ProfileDraft] = Field(min_length=1, max_length=50)
