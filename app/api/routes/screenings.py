from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BeforeValidator, Field
from starlette.concurrency import run_in_threadpool

from app.schemas.screening import ScreeningResult
from app.services.screening import MAX_FILE_BYTES, ResumeFile, screen

router = APIRouter(prefix="/api", tags=["screenings"])

MAX_FILES = 200

# A blank form field means "no cut-off", not an invalid number. The Form()
# has to sit inside Annotated (as a default value, FastAPI drops the
# validator), and the 0-10 range belongs on the number, not on None.
OptionalCgpa = Annotated[
    Annotated[float, Field(ge=0, le=10)] | None,
    BeforeValidator(lambda value: None if isinstance(value, str) and not value.strip() else value),
    Form(description="Minimum CGPA on a 10-point scale. Leave blank for no cut-off."),
]


@router.post("/screenings", response_model=ScreeningResult)
async def create_screening(
    job_description: str = Form(..., min_length=30, max_length=20_000),
    must_haves: str = Form("", max_length=2_000),
    resumes: list[UploadFile] = File(...),
    min_cgpa: OptionalCgpa = None,
) -> ScreeningResult:
    """Rank uploaded resumes against a job description and suggest a next step for each.

    Nothing is saved: files are read for this request and discarded with it.
    """
    if len(resumes) > MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload at most {MAX_FILES} resumes at a time.",
        )

    files = []
    for upload in resumes:
        # Read one byte past the limit: enough to know a file is too big
        # without holding all of a huge file in memory.
        data = await upload.read(MAX_FILE_BYTES + 1)
        files.append(ResumeFile(file_name=upload.filename or "unnamed file", data=data))

    # Parsing is CPU work; keep it off the event loop.
    return await run_in_threadpool(screen, job_description, must_haves, files, min_cgpa)
