from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status

from app.schemas.submissions import SubmissionDocument, SubmissionDraft, SubmissionDraftRequest
from app.services.clarify import ClarificationError
from app.services.submission import build_draft, to_csv, to_text, to_xlsx

router = APIRouter(prefix="/api", tags=["submissions"])


@router.post("/submissions/draft", response_model=SubmissionDraft)
def draft_submission(body: SubmissionDraftRequest) -> SubmissionDraft:
    """Draft client-facing profiles for the chosen candidates, with pre-submission checks.

    A draft only: the recruiter edits it, and nothing is sent anywhere. Unknown details are
    left empty rather than filled in.
    """
    try:
        return build_draft(body.result, body.clarifications, body.file_names, body.title)
    except ClarificationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None


@router.post("/submissions/export")
def export_submission(document: SubmissionDocument, format: Literal["csv", "xlsx", "text"] = "csv") -> Response:
    """Export the submission as the recruiter finalised it. Phone and email are left out unless `include_contact` is true."""
    if format == "text":
        return Response(content=to_text(document), media_type="text/plain; charset=utf-8")
    if format == "xlsx":
        return Response(
            content=to_xlsx(document),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="candidate-profiles.xlsx"'},
        )
    return Response(content=to_csv(document).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="candidate-profiles.csv"'})
