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


# ---------- 2.0: facts with evidence (additive; nothing above changes) ----------

def test_campus_resumes_get_empty_facts_and_unchanged_fields():
    response = client.post("/api/screenings", data={"job_description": JOB, "must_haves": "SQL, Excel"},
                           files=files_for(ASHA))
    body = response.json()
    candidate = body["candidates"][0]
    assert all(fact is None for fact in candidate["facts"].values())
    assert len(candidate["to_ask"]) == 6
    assert set(body["fact_coverage"].values()) == {0}
    # The 1.0 fields are all still there.
    for field in ("file_name", "status", "rank", "decision", "score", "name", "email", "cgpa", "must_haves_matched",
                  "must_haves_missing", "other_skills_matched", "summary", "flags", "interview_questions"):
        assert field in candidate


def test_experienced_resume_facts_come_back_with_quotes():
    resume = ("meena.txt", "\n".join([
        *resume_lines("Meena Joshi", "meena@example.com", "SQL, Excel, Power BI"),
        "Total Experience: 4 Years 6 Months",
        "Current CTC: 7.2 LPA | Expected CTC: Negotiable | Notice Period: 30 days",
    ]).encode(), "text/plain")
    response = client.post("/api/screenings", data={"job_description": JOB}, files=files_for(resume, ASHA))
    body = response.json()
    meena = next(c for c in body["candidates"] if c["name"] == "Meena Joshi")
    assert meena["facts"]["notice_period"] == {
        "value": 30.0, "unit": "days", "display": "30 days", "note": None, "confirm": False, "low": None,
        "quote": "Current CTC: 7.2 LPA | Expected CTC: Negotiable | Notice Period: 30 days",
    }
    assert meena["facts"]["total_experience"]["value"] == 4.5
    assert meena["facts"]["expected_ctc"]["value"] is None
    assert 'Expected CTC: resume says "Negotiable"' in meena["to_ask"]
    # Coverage counts usable values only, across both ranked resumes.
    assert body["fact_coverage"]["notice_period"] == 1
    assert body["fact_coverage"]["expected_ctc"] == 0


def test_files_that_need_review_have_no_facts():
    scan = ("scan.pdf", b"not a pdf", "application/pdf")
    body = client.post("/api/screenings", data={"job_description": JOB}, files=files_for(scan, ASHA)).json()
    review = next(c for c in body["candidates"] if c["status"] == "needs_review")
    assert review["to_ask"] == [] and all(fact is None for fact in review["facts"].values())


def test_experienced_sample_shows_found_unclear_and_missing_facts():
    sample = client.get("/api/samples", params={"kind": "experienced"}).json()
    assert sample["min_cgpa"] is None and len(sample["resumes"]) == 6
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    body = client.post("/api/screenings", data={"job_description": sample["job_description"],
                                                 "must_haves": sample["must_haves"]}, files=files).json()
    by_name = {c["name"]: c for c in body["candidates"]}
    assert by_name["Divya Rao"]["to_ask"] == []
    assert len(by_name["Tanvi Deshpande"]["to_ask"]) == 6
    assert by_name["Suresh Pillai"]["facts"]["notice_period"]["confirm"] is True
    assert by_name["Pooja Bansal"]["facts"]["current_ctc"]["value"] == 13.2
    assert body["fact_coverage"]["notice_period"] == 4


def test_unknown_sample_kind_is_rejected():
    assert client.get("/api/samples", params={"kind": "other"}).status_code == 422
