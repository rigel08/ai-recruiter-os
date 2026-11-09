import pytest
from fastapi.testclient import TestClient

from app.api.routes.screenings import MAX_FILES
from app.main import app
from tests.helpers import make_docx, make_pdf, resume_lines

client = TestClient(app)

JOB = "Data Analyst. Must know SQL and Excel; Power BI or Tableau dashboards; Python is a bonus."


def files_for(*resumes):
    return [("resumes", resume) for resume in resumes]


ASHA = ("asha.pdf", make_pdf([*resume_lines("Asha Verma", "asha@example.com", "SQL, Excel, Power BI"), "CGPA 8.1"]),
        "application/pdf")
RAVI = ("ravi.docx", make_docx([*resume_lines("Ravi Kumar", "ravi@example.com", "Excel"), "CGPA 6.9"]),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def test_home_page_serves_the_upload_form():
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="screen-form"' in response.text


def test_screening_ranks_mixed_file_types():
    response = client.post(
        "/api/screenings", data={"job_description": JOB, "must_haves": "SQL, Excel"}, files=files_for(RAVI, ASHA)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["must_haves"] == ["SQL", "Excel"]
    assert [(c["name"], c["decision"]) for c in body["candidates"]] == [
        ("Asha Verma", "shortlist"),
        ("Ravi Kumar", "maybe"),
    ]
    assert body["candidates"][1]["must_haves_missing"] == ["SQL"]
    assert body["min_cgpa"] is None


def test_min_cgpa_is_applied():
    response = client.post(
        "/api/screenings", data={"job_description": JOB, "must_haves": "Excel", "min_cgpa": "7"},
        files=files_for(RAVI, ASHA),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["min_cgpa"] == 7.0
    ravi = next(c for c in body["candidates"] if c["name"] == "Ravi Kumar")
    assert (ravi["decision"], ravi["cgpa"]) == ("not_a_fit", 6.9)


@pytest.mark.parametrize("value", ["", "  "])
def test_blank_min_cgpa_means_no_cut_off(value):
    response = client.post(
        "/api/screenings", data={"job_description": JOB, "min_cgpa": value}, files=files_for(ASHA)
    )
    assert response.status_code == 200
    assert response.json()["min_cgpa"] is None


@pytest.mark.parametrize("value", ["11", "-1", "seven"])
def test_invalid_min_cgpa_is_rejected(value):
    response = client.post(
        "/api/screenings", data={"job_description": JOB, "min_cgpa": value}, files=files_for(ASHA)
    )
    assert response.status_code == 422


def test_short_job_description_is_rejected():
    response = client.post("/api/screenings", data={"job_description": "Analyst"}, files=files_for(ASHA))
    assert response.status_code == 422


def test_resumes_are_required():
    response = client.post("/api/screenings", data={"job_description": JOB})
    assert response.status_code == 422


def test_too_many_files_is_rejected():
    files = [("resumes", (f"{i}.txt", b"resume", "text/plain")) for i in range(MAX_FILES + 1)]
    response = client.post("/api/screenings", data={"job_description": JOB}, files=files)
    assert response.status_code == 413
    assert str(MAX_FILES) in response.json()["detail"]


def test_sample_data_screens_into_every_group():
    sample = client.get("/api/samples").json()
    assert len(sample["resumes"]) == 8
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    response = client.post(
        "/api/screenings",
        data={"job_description": sample["job_description"], "must_haves": sample["must_haves"],
              "min_cgpa": str(sample["min_cgpa"])},
        files=files,
    )
    body = response.json()
    assert body["decision_counts"] == {"shortlist": 3, "maybe": 2, "not_a_fit": 3}
    assert body["candidates"][0]["name"] == "Ananya Reddy"


def test_home_page_is_revalidated_so_updates_show_up():
    assert client.get("/").headers["cache-control"] == "no-cache"


def test_uptime_monitors_can_use_head():
    assert client.head("/").status_code == 200
    assert client.head("/health").status_code == 200
