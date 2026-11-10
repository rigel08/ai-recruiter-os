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
    assert sample["min_cgpa"] is None and len(sample["resumes"]) == 8
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    body = client.post("/api/screenings", data={"job_description": sample["job_description"],
                                                 "must_haves": sample["must_haves"]}, files=files).json()
    by_name = {c["name"]: c for c in body["candidates"]}
    assert by_name["Divya Rao"]["to_ask"] == []
    assert len(by_name["Tanvi Deshpande"]["to_ask"]) == 6
    assert by_name["Suresh Pillai"]["facts"]["notice_period"]["confirm"] is True
    assert by_name["Suresh Pillai"]["facts"]["total_experience"]["value"] is None   # per-skill figures only
    assert by_name["Imran Sheikh"]["facts"]["current_location"]["value"] == "Hyderabad"
    assert by_name["Pooja Bansal"]["facts"]["current_ctc"]["value"] == 13.2
    assert body["fact_coverage"]["notice_period"] == 6
    # Without hiring_mode=experienced this is still a 1.0 screening: no evaluation, 1.0 order.
    assert body["hiring_mode"] == "campus" and body["requirements"] is None and body["next_step_counts"] is None
    assert all(c["evaluation"] is None for c in body["candidates"])
    assert body["decision_counts"] == {"shortlist": 5, "maybe": 2, "not_a_fit": 1}


def test_unknown_sample_kind_is_rejected():
    assert client.get("/api/samples", params={"kind": "other"}).status_code == 422


# ---------- M2: experienced hiring with confirmed requirements ----------

# Produced by running the code at the v1-baseline tag on the campus sample with a 7.0 cut-off.
V1_CAMPUS_RESULT = [
    ("Ananya Reddy", "shortlist", 85), ("Karthik Menon", "shortlist", 72), ("Vikram Singh", "shortlist", 68),
    ("Rahul Sharma", "maybe", 48), ("Sneha Patil", "maybe", 41), ("Priya Nair", "not_a_fit", 75),
    ("Meera Iyer", "not_a_fit", 1), ("Arjun Das", "not_a_fit", 0),
]

def experienced(**overrides):
    sample = client.get("/api/samples", params={"kind": "experienced"}).json()
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    data = {"job_description": sample["job_description"], "must_haves": "Java, Spring Boot, SQL",
            "hiring_mode": "experienced", "preferred_skills": "REST APIs, Docker, AWS, Kubernetes, Redis",
            "min_experience_years": "5", "max_experience_years": "9", "max_notice_days": "60", "max_ctc_lpa": "24",
            "locations": "Hyderabad", **overrides}
    return client.post("/api/screenings", data={k: v for k, v in data.items() if v is not None}, files=files)


def test_experienced_sample_separates_skills_limits_and_information():
    body = experienced().json()
    assert body["hiring_mode"] == "experienced"
    assert body["requirements"] == {
        "required_skills": ["Java", "Spring Boot", "SQL"], "preferred_skills": ["REST APIs", "Docker", "AWS", "Kubernetes", "Redis"],
        "min_experience_years": 5.0, "max_experience_years": 9.0, "max_notice_days": 60.0, "max_ctc_lpa": 24.0,
        "locations": ["Hyderabad"],
    }
    assert body["next_step_counts"] == {"ready": 2, "clarify": 1, "check": 3, "conflict": 1, "low_fit": 1}
    order = [(c["name"], c["evaluation"]["next_step"]["key"]) for c in body["candidates"]]
    assert order == [
        ("Divya Rao", "ready"), ("Imran Sheikh", "ready"), ("Tanvi Deshpande", "clarify"),
        ("Lakshmi Narayanan", "check"), ("Pooja Bansal", "check"), ("Suresh Pillai", "check"),
        ("Rohit Verma", "conflict"), ("Neha Kapoor", "low_fit"),
    ]
    assert [c["rank"] for c in body["candidates"]] == list(range(1, 9))   # everyone is still listed


def test_strong_candidate_with_conflicts_is_visible_not_hidden_by_a_score():
    rohit = next(c for c in experienced().json()["candidates"] if c["name"] == "Rohit Verma")
    evaluation = rohit["evaluation"]
    assert (evaluation["skills"]["level"], evaluation["skills"]["score"]) == ("strong", 100)
    statuses = {check["requirement"]: check["status"] for check in evaluation["constraints"]["checks"]}
    assert statuses == {"notice_period": "does_not_meet", "ctc": "does_not_meet", "location": "does_not_meet"}
    assert evaluation["constraints"]["overall"] == "does_not_meet"
    assert evaluation["next_step"]["label"] == "Conflicts with a limit"
    assert rohit["status"] == "ranked"   # shown and ranked, never rejected


def test_candidate_with_no_facts_is_unknown_not_a_mismatch():
    tanvi = next(c for c in experienced().json()["candidates"] if c["name"] == "Tanvi Deshpande")
    evaluation = tanvi["evaluation"]
    assert evaluation["skills"]["level"] == "strong"
    assert {check["status"] for check in evaluation["constraints"]["checks"]} == {"unknown"}
    assert evaluation["skills"]["experience"]["status"] == "unknown"
    assert evaluation["completeness"] == {"stated": 0, "total": 6, "unclear": [],
                                          "missing": ["Phone number", "Total experience", "Notice period", "Current CTC",
                                                      "Expected CTC", "Current location"]}


def test_recruiter_edits_change_the_evaluation():
    def rohit(**overrides):
        return next(c for c in experienced(**overrides).json()["candidates"] if c["name"] == "Rohit Verma")["evaluation"]

    relaxed = rohit(max_notice_days="90", max_ctc_lpa="35", locations="Hyderabad, Bangalore")
    assert relaxed["constraints"]["overall"] == "meets" and relaxed["next_step"]["key"] == "ready"
    # Blank fields mean "no limit": nothing is checked, and nothing is assumed from the job description.
    cleared = rohit(max_notice_days="", max_ctc_lpa="", locations="", min_experience_years="", max_experience_years="")
    assert cleared["constraints"]["overall"] == "none_set" and cleared["skills"]["experience"] is None


def test_preferred_skills_fall_back_to_the_job_description_only_when_not_sent():
    assert experienced(preferred_skills=None).json()["requirements"]["preferred_skills"] == [
        "REST APIs", "PostgreSQL", "MySQL", "Redis", "AWS", "Docker", "Kubernetes", "CI/CD", "Agile"]
    assert experienced(preferred_skills="").json()["requirements"]["preferred_skills"] == []


def test_experienced_mode_keeps_the_1_0_fields():
    candidate = experienced().json()["candidates"][0]
    for field in ("decision", "score", "must_haves_matched", "summary", "interview_questions", "facts", "to_ask"):
        assert field in candidate


@pytest.mark.parametrize("overrides, message", [
    ({"min_experience_years": "9", "max_experience_years": "5"}, "Minimum experience can't be more than maximum"),
    ({"max_notice_days": "400"}, None),
    ({"max_notice_days": "-1"}, None),
    ({"max_ctc_lpa": "0"}, None),
    ({"max_ctc_lpa": "lots"}, None),
    ({"min_experience_years": "80"}, None),
    ({"hiring_mode": "senior"}, None),
])
def test_bad_requirements_are_rejected(overrides, message):
    response = experienced(**overrides)
    assert response.status_code == 422
    if message:
        assert message in response.json()["detail"]


def test_limits_without_experienced_mode_are_refused_not_silently_ignored():
    response = client.post("/api/screenings", data={"job_description": JOB, "max_notice_days": "30"}, files=files_for(ASHA))
    assert response.status_code == 422
    assert "hiring_mode=experienced" in response.json()["detail"]


def test_campus_result_is_unchanged_by_m2():
    sample = client.get("/api/samples").json()
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    body = client.post("/api/screenings", data={"job_description": sample["job_description"],
                                                 "must_haves": sample["must_haves"], "min_cgpa": "7.0"}, files=files).json()
    # Same order, decisions and scores as the v1-baseline tag.
    assert [(c["name"], c["decision"], c["score"]) for c in body["candidates"]] == V1_CAMPUS_RESULT
    assert body["hiring_mode"] == "campus" and all(c["evaluation"] is None for c in body["candidates"])


def test_unreadable_files_are_reported_in_experienced_mode_too():
    sample = client.get("/api/samples", params={"kind": "experienced"}).json()
    files = [("resumes", ("divya.txt", sample["resumes"][0]["text"].encode(), "text/plain")),
             ("resumes", ("old.doc", b"binary", "application/msword")),
             ("resumes", ("photo.jpg", b"binary", "image/jpeg")),
             ("resumes", ("broken.pdf", b"not a pdf", "application/pdf")),
             ("resumes", ("empty.txt", b"hello", "text/plain"))]
    body = client.post("/api/screenings", data={"job_description": sample["job_description"], "hiring_mode": "experienced"},
                       files=files).json()
    review = {c["file_name"]: c for c in body["candidates"] if c["status"] == "needs_review"}
    assert "open it in Word" in review["old.doc"]["summary"]
    assert "photo or scan" in review["photo.jpg"]["summary"]
    assert "couldn't be opened" in review["broken.pdf"]["summary"]
    assert "Almost no text" in review["empty.txt"]["summary"]
    assert all(c["evaluation"] is None and c["rank"] is None for c in review.values())
    assert (body["ranked_count"], body["needs_review_count"]) == (1, 4)
