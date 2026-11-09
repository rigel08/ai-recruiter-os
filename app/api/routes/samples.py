"""Built-in demo data, so the tool can be shown without real resumes."""

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["samples"])

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"


class SampleResume(BaseModel):
    file_name: str
    text: str


class Sample(BaseModel):
    job_description: str
    must_haves: str
    min_cgpa: float
    resumes: list[SampleResume]


@lru_cache(maxsize=1)
def load_sample() -> Sample:
    return Sample(
        job_description=(SAMPLES_DIR / "job_description.txt").read_text(encoding="utf-8"),
        must_haves="Python, SQL, REST APIs",
        min_cgpa=7.0,
        resumes=[
            SampleResume(file_name=path.name, text=path.read_text(encoding="utf-8"))
            for path in sorted((SAMPLES_DIR / "resumes").glob("*.txt"))
        ],
    )


@router.get("/samples", response_model=Sample)
def get_sample() -> Sample:
    """A fictional job and fictional resumes for demos. Nobody in them is real."""
    return load_sample()
