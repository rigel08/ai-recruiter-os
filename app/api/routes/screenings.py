from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BeforeValidator, Field
from starlette.concurrency import run_in_threadpool

from app.schemas.screening import ScreeningResult
from app.services.requirements import confirmed
from app.services.screening import MAX_FILE_BYTES, ResumeFile, screen
from app.services.skills import skills_in, terms_from_input

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


_blank_is_none = BeforeValidator(lambda value: None if isinstance(value, str) and not value.strip() else value)


def _optional_number(low: float, high: float, description: str):
    return Annotated[Annotated[float, Field(ge=low, le=high)] | None, _blank_is_none, Form(description=description)]


OptionalYears = _optional_number(0, 50, "Years of experience. Leave blank for no limit.")
OptionalNoticeDays = _optional_number(0, 180, "Longest acceptable notice period in days. 0 means immediate.")
OptionalLpa = _optional_number(0.5, 500, "Highest acceptable expected CTC in lakhs a year.")

REQUIREMENT_FIELDS = ("preferred_skills", "min_experience_years", "max_experience_years", "max_notice_days",
                      "max_ctc_lpa", "locations")


@router.post("/screenings", response_model=ScreeningResult)
async def create_screening(
    job_description: str = Form(..., min_length=30, max_length=20_000),
    must_haves: str = Form("", max_length=2_000),
    resumes: list[UploadFile] = File(...),
    min_cgpa: OptionalCgpa = None,
    hiring_mode: Literal["campus", "experienced"] = Form("campus"),
    preferred_skills: str | None = Form(None, max_length=2_000),
    min_experience_years: OptionalYears = None,
    max_experience_years: OptionalYears = None,
    max_notice_days: OptionalNoticeDays = None,
    max_ctc_lpa: OptionalLpa = None,
    locations: str | None = Form(None, max_length=500),
) -> ScreeningResult:
    """Rank uploaded resumes against a job description and suggest a next step for each.

    Nothing is saved: files are read for this request and discarded with it.

    With `hiring_mode=experienced`, each candidate is also evaluated against the requirements
    sent here: `must_haves` are the required skills, and the other fields are the client's limits.
    Only what is sent is checked; nothing is inferred from the job description except, when
    `preferred_skills` is left out entirely, the skills it mentions.
    """
    limits = {"preferred_skills": preferred_skills, "min_experience_years": min_experience_years,
              "max_experience_years": max_experience_years, "max_notice_days": max_notice_days,
              "max_ctc_lpa": max_ctc_lpa, "locations": locations}
    if hiring_mode == "campus" and any(value not in (None, "") for value in limits.values()):
        sent = ", ".join(name for name, value in limits.items() if value not in (None, ""))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{sent} only apply to experienced hiring. Send hiring_mode=experienced to use them.",
        )
    if min_experience_years is not None and max_experience_years is not None and min_experience_years > max_experience_years:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Minimum experience can't be more than maximum experience.",
        )
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

    requirements = None
    if hiring_mode == "experienced":
        required = {term.name.lower() for term in terms_from_input(must_haves)}
        mentioned = [term for term in skills_in(job_description) if term.name.lower() not in required]
        requirements = confirmed(must_haves, preferred_skills, mentioned, min_experience_years, max_experience_years,
                                 max_notice_days, max_ctc_lpa, locations)

    # Parsing is CPU work; keep it off the event loop.
    return await run_in_threadpool(screen, job_description, must_haves, files, min_cgpa, requirements)
