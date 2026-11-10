"""What a recruiter records after speaking to a candidate, and what a candidate's reply was read as."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.screening import ScreeningResult

AnswerState = Literal["answered", "confirmed", "pending", "not_applicable"]
Source = Literal["resume", "recruiter_confirmed", "recruiter_entered", "unknown"]


class Answer(BaseModel):
    """One field's outcome from the call.

    answered: the recruiter typed a value. confirmed: the candidate confirmed what the resume says.
    pending: asked, no answer yet. not_applicable: don't ask.
    """

    state: AnswerState
    value: float | str | None = Field(default=None, description="Only for 'answered': a number, or text for places and phone")
    note: str = Field(default="", max_length=500)


class CandidateClarification(BaseModel):
    answers: dict[str, Answer] = Field(default_factory=dict, description="Keyed by fact field")
    remarks: str = Field(default="", max_length=2_000, description="The recruiter's own notes about this candidate")


class ClarifyRequest(BaseModel):
    result: ScreeningResult
    clarifications: dict[str, CandidateClarification] = Field(description="Keyed by resume file name")


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)


class ReplyValue(BaseModel):
    value: float | str
    display: str
    quote: str = Field(description="The part of the reply it was read from")


class ReplyReading(BaseModel):
    """Values found in a candidate's message. Suggestions only: the recruiter reviews them before any is used."""

    found: dict[str, ReplyValue]
    not_found: list[str] = Field(description="Tracker fields the reply doesn't mention")
