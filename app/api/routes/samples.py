"""Built-in demo data, so the tool can be shown without real resumes."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    min_cgpa: float | None
    resumes: list[SampleResume]


def _resumes(folder: Path) -> list[SampleResume]:
    return [
        SampleResume(file_name=path.name, text=path.read_text(encoding="utf-8"))
        for path in sorted((folder / "resumes").glob("*.txt"))
    ]


@lru_cache(maxsize=2)
def load_sample(kind: Literal["campus", "experienced"] = "campus") -> Sample:
    if kind == "experienced":
        folder = SAMPLES_DIR / "experienced"
        return Sample(
            job_description=(folder / "job_description.txt").read_text(encoding="utf-8"),
            must_haves="Java, Spring Boot, SQL",
            min_cgpa=None,
            resumes=_resumes(folder),
        )
    return Sample(
        job_description=(SAMPLES_DIR / "job_description.txt").read_text(encoding="utf-8"),
        must_haves="Python, SQL, REST APIs",
        min_cgpa=7.0,
        resumes=_resumes(SAMPLES_DIR),
    )


@router.get("/samples", response_model=Sample)
def get_sample(kind: Literal["campus", "experienced"] = "campus") -> Sample:
    """A fictional job and fictional resumes for demos. Nobody in them is real.

    `kind=experienced` returns resumes that state notice period, CTC and experience in the
    varied ways real ones do, including one that states almost nothing.
    """
    return load_sample(kind)
