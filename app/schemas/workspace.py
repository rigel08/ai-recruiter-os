"""Saved screening sessions. They live in one file on the recruiter's own computer."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.clarifications import CandidateClarification
from app.schemas.screening import ScreeningResult

SessionStatus = Literal["open", "submitted", "on_hold", "closed"]


class SessionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    job_description: str = Field(max_length=20_000)
    form: dict[str, str] = Field(default_factory=dict, description="The requirement boxes as typed, to restore the form")
    result: ScreeningResult
    clarifications: dict[str, CandidateClarification] = Field(default_factory=dict)
    submission: dict[str, Any] | None = Field(default=None, description="The submission being edited, if any")


class SessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: SessionStatus | None = None
    clarifications: dict[str, CandidateClarification] | None = None
    submission: dict[str, Any] | None = None
    clear_submission: bool = False


class SessionSummary(BaseModel):
    id: str
    name: str
    status: SessionStatus
    created_at: str
    updated_at: str
    candidates: int
    with_call_notes: int
    has_submission: bool


class Session(SessionSummary):
    job_description: str
    form: dict[str, str]
    result: ScreeningResult
    clarifications: dict[str, CandidateClarification]
    submission: dict[str, Any] | None


class SeenRequest(BaseModel):
    result: ScreeningResult
    exclude_session: str | None = None


class SeenElsewhere(BaseModel):
    """A candidate in this result who is also in another saved session, matched on phone or email."""

    file_name: str
    name: str
    session_id: str
    session_name: str
    session_status: SessionStatus
    saved_on: str
    matched_on: str


class WorkspaceInfo(BaseModel):
    enabled: bool
    location: str | None = Field(description="Where sessions are stored on this computer")
    note: str
