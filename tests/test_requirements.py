"""Reading a job description into requirements the recruiter confirms or edits."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.requirements import locations_from_input, parse_job_description

client = TestClient(app)
SAMPLE_JD = (Path(__file__).resolve().parent.parent / "app" / "samples" / "experienced" / "job_description.txt").read_text()


def names(skills):
    return [skill.name for skill in skills]


def test_sample_job_description_gives_every_field_with_its_sentence():
    job = parse_job_description(SAMPLE_JD)
    assert names(job.required_skills) == ["Java", "SQL", "Spring Boot"]
    assert {"REST APIs", "Docker", "AWS", "Kubernetes", "Redis"} <= set(names(job.preferred_skills))
    assert (job.min_experience_years.value, job.max_experience_years.value) == (5, 9)
    assert job.min_experience_years.quote == "5 to 9 years of experience in backend development."
    assert (job.max_notice_days.value, job.max_notice_days.basis) == (60, "explicit")
    assert job.max_notice_days.note == "30 days or less is preferred."
    assert (job.max_ctc_lpa.value, job.max_ctc_lpa.quote) == (24, "Budget: up to 24 LPA.")
    assert (job.locations.values, job.locations.basis) == (["Hyderabad"], "explicit")
    assert any("five days a week" in item for item in job.other)


def test_required_preferred_and_merely_mentioned_skills_are_told_apart():
    job = parse_job_description("Must have SQL and Excel.\nTableau is nice to have.\nYou will build reports in Power BI.")
    assert [(s.name, s.basis) for s in job.required_skills] == [("SQL", "explicit"), ("Excel", "explicit")]
    preferred = {s.name: s.basis for s in job.preferred_skills}
    # Stated as a preference: explicit. Only mentioned in passing: suggested, never required.
    assert preferred == {"Tableau": "explicit", "Power BI": "suggested"}


def test_headings_decide_when_a_sentence_has_no_marker():
    job = parse_job_description("Requirements\n- Python and Django\nNice to have\n- Docker\nAbout the team\n- We use AWS")
    assert names(job.required_skills) == ["Python", "Django"]
    assert {s.name: s.basis for s in job.preferred_skills} == {"Docker": "explicit", "AWS": "suggested"}


@pytest.mark.parametrize("text, low, high", [
    ("5 to 9 years of experience in backend development.", 5, 9),
    ("Experience: 6+ years.", 6, None),
    ("Minimum 4 years of experience required.", 4, None),
    ("At least 3 yrs experience in testing.", 3, None),
    ("Up to 8 years of experience.", None, 8),
    ("3 years of experience with Python.", 3, None),
    ("Experience: 4-6 yrs", 4, 6),
])
def test_experience_wording(text, low, high):
    job = parse_job_description(text)
    assert (job.min_experience_years and job.min_experience_years.value) == low
    assert (job.max_experience_years and job.max_experience_years.value) == high


def test_vague_experience_wording_is_only_a_suggestion():
    job = parse_job_description("Around 3 years of experience preferred.\n2+ years of experience in Django.")
    assert (job.min_experience_years.value, job.min_experience_years.basis) == (3, "suggested")
    assert "other experience figures" in job.min_experience_years.note
    assert any("More than one experience figure" in note for note in job.notes)


def test_nothing_is_inferred_when_the_job_description_is_silent():
    job = parse_job_description("We are a friendly team looking for a great engineer who loves hard problems.")
    assert (job.min_experience_years, job.max_notice_days, job.max_ctc_lpa, job.locations) == (None, None, None, None)
    assert job.required_skills == [] and job.other == []


@pytest.mark.parametrize("text, days, basis", [
    ("Notice period: 30 days or less preferred, 60 days at most.", 60, "explicit"),
    ("Notice period up to 30 days.", 30, "explicit"),
    ("Immediate joiners only.", 0, "explicit"),
    ("Immediate joiners preferred.", 0, "suggested"),
    ("Candidates who can join within 2 months.", 60, "explicit"),
    ("Immediate joiners or candidates serving notice (max 30 days).", 30, "explicit"),
    ("Notice: 0-15 days", 15, "explicit"),
])
def test_notice_wording(text, days, basis):
    notice = parse_job_description(text).max_notice_days
    assert (notice.value, notice.basis) == (days, basis)


@pytest.mark.parametrize("text, lpa", [
    ("Budget: up to 24 LPA.", 24),
    ("Salary range 18-22 LPA.", 22),
    ("CTC: Rs. 20,00,000 per annum", 20),
    ("Max CTC 1.2 Cr.", 120),
    ("CTC as per industry standards.", None),
    ("Budget is open for the right candidate.", None),
])
def test_pay_wording(text, lpa):
    pay = parse_job_description(text).max_ctc_lpa
    assert (pay and pay.value) == lpa


def test_a_pay_range_says_the_top_is_used():
    assert "top of the range" in parse_job_description("Salary range 18-22 LPA.").max_ctc_lpa.note


@pytest.mark.parametrize("text, cities, basis", [
    ("Work location: Bangalore or Pune.", ["Bengaluru", "Pune"], "explicit"),
    ("Location: Gurgaon", ["Gurugram"], "explicit"),
    ("Location - Delhi NCR", ["Delhi", "Gurugram", "Noida", "Greater Noida", "Faridabad", "Ghaziabad"], "explicit"),
    ("The role is based in Hitech City, Hyderabad.", ["Hyderabad"], "explicit"),
    ("Java Developer, Chennai\nGreat team.", ["Chennai"], "suggested"),
])
def test_location_wording(text, cities, basis):
    locations = parse_job_description(text).locations
    assert (locations.values, locations.basis) == (cities, basis)


def test_remote_jobs_get_no_location_limit():
    job = parse_job_description("Python developer.\nLocation: Remote\nMust know Django.")
    assert job.locations is None and any("remote" in note.lower() for note in job.notes)


def test_other_stated_conditions_are_listed_not_evaluated():
    job = parse_job_description("Must have SQL.\nRotational shifts.\nB.Tech mandatory.\nWe like curious people.")
    assert job.other == ["Rotational shifts.", "B.Tech mandatory."]


def test_recruiter_typed_locations_are_normalised():
    assert locations_from_input("bangalore, Hyd / Pune") == ["Bengaluru", "Hyderabad", "Pune"]
    assert locations_from_input("Rajahmundry") == ["Rajahmundry"]  # not on the list: kept as typed
    assert locations_from_input("  ") == []


def test_requirements_api_returns_suggestions_with_quotes():
    body = client.post("/api/requirements", json={"job_description": SAMPLE_JD}).json()
    assert body["max_notice_days"] == {"value": 60.0, "basis": "explicit", "note": "30 days or less is preferred.",
                                       "quote": "Notice period: 30 days or less preferred, 60 days at most."}
    assert body["required_skills"][0]["quote"] == "Strong Java, Spring Boot and SQL."


@pytest.mark.parametrize("payload", [{}, {"job_description": "too short"}, {"job_description": "x" * 20_001}])
def test_requirements_api_rejects_bad_input(payload):
    assert client.post("/api/requirements", json=payload).status_code == 422
