from fastapi import APIRouter, HTTPException, status

from app.schemas.clarifications import ClarifyRequest, ReplyIn, ReplyReading, ReplyValue
from app.schemas.screening import ScreeningResult
from app.services.clarify import ClarificationError, apply
from app.services.replies import read_reply

router = APIRouter(prefix="/api", tags=["clarifications"])

MAX_CANDIDATES = 250


@router.post("/clarifications/apply", response_model=ScreeningResult)
def apply_clarifications(body: ClarifyRequest) -> ScreeningResult:
    """Apply the recruiter's call answers to a screening result and evaluate everyone again.

    Send the result exactly as the screening returned it, with all answers so far. Resume facts
    are never changed: the values in use, and where each came from, come back in `resolved`.
    Nothing is stored.
    """
    if len(body.result.candidates) > MAX_CANDIDATES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"At most {MAX_CANDIDATES} candidates at a time.")
    try:
        return apply(body.result, body.clarifications)
    except ClarificationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None


@router.post("/clarifications/read-reply", response_model=ReplyReading)
def read_candidate_reply(body: ReplyIn) -> ReplyReading:
    """Read a candidate's pasted reply into suggested answers. Suggestions only; nothing is applied or stored."""
    found, not_found = read_reply(body.text)
    return ReplyReading(found={field: ReplyValue(**value) for field, value in found.items()}, not_found=not_found)
