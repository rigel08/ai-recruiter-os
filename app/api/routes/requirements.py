from dataclasses import asdict

from fastapi import APIRouter

from app.schemas.requirements import JobDescriptionIn, JobRequirements
from app.services.requirements import parse_job_description

router = APIRouter(prefix="/api", tags=["requirements"])


@router.post("/requirements", response_model=JobRequirements)
def read_requirements(body: JobDescriptionIn) -> JobRequirements:
    """Suggest structured requirements from a job description, each with the sentence it came from.

    These are suggestions only. Nothing is evaluated until the recruiter sends the values they
    accept (edited or not) with a screening request.
    """
    return JobRequirements(**asdict(parse_job_description(body.job_description)))
