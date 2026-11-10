"""Call answers: applied on top of the resume, never over it, and everyone is evaluated again."""

import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.replies import read_reply

client = TestClient(app)

LIMITS = {"hiring_mode": "experienced", "must_haves": "Java, Spring Boot, SQL",
          "preferred_skills": "REST APIs, Docker, AWS, Kubernetes, Redis", "min_experience_years": "5",
          "max_experience_years": "9", "max_notice_days": "60", "max_ctc_lpa": "24", "locations": "Hyderabad"}


@pytest.fixture(scope="module")
def result():
    sample = client.get("/api/samples", params={"kind": "experienced"}).json()
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    files.append(("resumes", ("scan.pdf", b"not a pdf", "application/pdf")))
    return client.post("/api/screenings", data={"job_description": sample["job_description"], **LIMITS}, files=files).json()


def apply(result, clarifications):
    return client.post("/api/clarifications/apply", json={"result": result, "clarifications": clarifications})


def candidate(body, name):
    return next(c for c in body["candidates"] if c["name"] == name)


def answers(**fields):
    return {"answers": {field: ({"state": value} if isinstance(value, str) and value in ("confirmed", "pending", "not_applicable")
                                else {"state": "answered", "value": value}) for field, value in fields.items()}}


TANVI_CALL = {"tanvi_deshpande.txt": answers(phone="+91 90000 00108", total_experience=6.5, notice_period=30,
                                             current_ctc=16, expected_ctc=21, current_location="Hyderabad")}


def test_a_fresh_result_already_says_where_each_value_came_from(result):
    divya = candidate(result, "Divya Rao")
    assert divya["resolved"]["notice_period"] == {
        "source": "resume", "value": 30.0, "unit": "days", "display": "30 days", "resume_display": "30 days",
        "state": None, "note": ""}
    tanvi = candidate(result, "Tanvi Deshpande")
    assert {fact["source"] for fact in tanvi["resolved"].values()} == {"unknown"}


def test_call_answers_turn_unknown_into_checked_and_reorder(result):
    before = candidate(result, "Tanvi Deshpande")
    assert before["evaluation"]["next_step"]["key"] == "clarify"

    body = apply(result, TANVI_CALL).json()
    tanvi = candidate(body, "Tanvi Deshpande")
    statuses = {check["requirement"]: check["status"] for check in tanvi["evaluation"]["constraints"]["checks"]}
    assert statuses == {"notice_period": "meets", "ctc": "meets", "location": "meets"}
    assert tanvi["evaluation"]["skills"]["experience"]["status"] == "meets"
    assert tanvi["evaluation"]["next_step"]["key"] == "ready"
    assert tanvi["evaluation"]["completeness"] == {"stated": 6, "total": 6, "missing": [], "unclear": []}
    assert tanvi["to_ask"] == []
    assert body["next_step_counts"]["ready"] == 3 and body["next_step_counts"]["clarify"] == 0
    assert [c["rank"] for c in body["candidates"] if c["status"] == "ranked"] == list(range(1, 9))
    # Skills didn't change: the same resume text was matched.
    assert tanvi["evaluation"]["skills"]["score"] == before["evaluation"]["skills"]["score"]


def test_recruiter_entries_never_become_resume_evidence(result):
    tanvi = candidate(apply(result, TANVI_CALL).json(), "Tanvi Deshpande")
    assert all(fact is None for fact in tanvi["facts"].values())          # the resume still says nothing
    entered = tanvi["resolved"]["notice_period"]
    assert (entered["source"], entered["display"], entered["resume_display"]) == ("recruiter_entered", "30 days", None)
    assert tanvi["resolved"]["preferred_location"]["source"] == "unknown"


def test_an_entered_value_sits_beside_the_resume_value_not_over_it(result):
    body = apply(result, {"rohit_verma.txt": answers(notice_period=45, expected_ctc=24)}).json()
    rohit = candidate(body, "Rohit Verma")
    assert rohit["facts"]["notice_period"]["value"] == 90.0               # untouched
    assert rohit["facts"]["notice_period"]["quote"] == "Notice Period: 90 Days"
    resolved = rohit["resolved"]["notice_period"]
    assert (resolved["source"], resolved["value"], resolved["resume_display"]) == ("recruiter_entered", 45.0, "90 days")
    statuses = {check["requirement"]: check["status"] for check in rohit["evaluation"]["constraints"]["checks"]}
    assert statuses == {"notice_period": "meets", "ctc": "meets", "location": "does_not_meet"}
    assert "Entered by the recruiter" not in rohit["facts"]["notice_period"]["quote"]


def test_confirming_a_resume_value_clears_the_doubt_and_keeps_the_quote(result):
    before = candidate(result, "Suresh Pillai")
    assert before["facts"]["notice_period"]["confirm"] is True            # the resume says 60 and 45
    body = apply(result, {"suresh_pillai.txt": answers(notice_period="confirmed")}).json()
    suresh = candidate(body, "Suresh Pillai")
    assert suresh["resolved"]["notice_period"]["source"] == "recruiter_confirmed"
    check = next(c for c in suresh["evaluation"]["constraints"]["checks"] if c["requirement"] == "notice_period")
    assert check["status"] == "meets"
    assert suresh["facts"]["notice_period"]["confirm"] is True            # the resume fact is as extracted
    assert not any(item.startswith("Notice period") for item in suresh["to_ask"])


def test_pending_and_not_applicable_change_the_ask_list_only(result):
    body = apply(result, {"tanvi_deshpande.txt": answers(notice_period="pending", expected_ctc="not_applicable")}).json()
    tanvi = candidate(body, "Tanvi Deshpande")
    assert "Notice period: asked, waiting for an answer" in tanvi["to_ask"]
    assert not any(item.startswith("Expected CTC") for item in tanvi["to_ask"])
    assert tanvi["resolved"]["notice_period"]["source"] == "unknown"
    assert tanvi["resolved"]["expected_ctc"]["state"] == "not_applicable"
    assert {c["status"] for c in tanvi["evaluation"]["constraints"]["checks"]} == {"unknown"}   # still not a mismatch


def test_clearing_an_answer_restores_the_resume_view(result):
    body = apply(result, {}).json()
    for before, after in zip(result["candidates"], body["candidates"]):
        assert (before["name"], before["evaluation"], before["to_ask"]) == (after["name"], after["evaluation"], after["to_ask"])


def test_applying_does_not_change_the_result_sent_in(result):
    untouched = copy.deepcopy(result)
    apply(result, TANVI_CALL)
    assert result == untouched


def test_an_entered_answer_can_also_create_a_conflict(result):
    body = apply(result, {"divya_rao.txt": answers(notice_period=90)}).json()
    divya = candidate(body, "Divya Rao")
    assert divya["evaluation"]["next_step"]["key"] == "conflict"
    assert divya["rank"] > candidate(result, "Divya Rao")["rank"]


def test_remarks_are_kept_with_the_candidate(result):
    body = apply(result, {"divya_rao.txt": {"answers": {}, "remarks": "  Spoke on 10 Nov. Keen on fintech.  "}}).json()
    assert candidate(body, "Divya Rao")["remarks"] == "Spoke on 10 Nov. Keen on fintech."


def test_immediate_and_text_answers(result):
    body = apply(result, {"rohit_verma.txt": answers(notice_period=0, current_location="Gachibowli")}).json()
    rohit = candidate(body, "Rohit Verma")
    assert rohit["resolved"]["notice_period"]["display"] == "Immediate"
    location = next(c for c in rohit["evaluation"]["constraints"]["checks"] if c["requirement"] == "location")
    assert location["status"] == "meets"          # Gachibowli is a Hyderabad locality


@pytest.mark.parametrize("clarifications, message", [
    ({"tanvi_deshpande.txt": {"answers": {"notice_period": {"state": "answered"}}}}, "type the answer"),
    ({"tanvi_deshpande.txt": answers(notice_period="thirty")}, "enter a number"),
    ({"tanvi_deshpande.txt": answers(notice_period=900)}, "from 0 to 365"),
    ({"tanvi_deshpande.txt": answers(expected_ctc=0)}, "from 0.5 to 500"),
    ({"tanvi_deshpande.txt": answers(notice_period="confirmed")}, "no value on the resume to confirm"),
    ({"tanvi_deshpande.txt": answers(shoe_size=9)}, "Unknown field"),
    ({"nobody.txt": answers(notice_period=30)}, "No such candidate"),
    ({"scan.pdf": answers(notice_period=30)}, "No such candidate"),      # an unreadable file has no evaluation
    ({"tanvi_deshpande.txt": answers(current_location="x" * 81)}, "under 80 characters"),
])
def test_unusable_entries_are_refused_with_a_reason(result, clarifications, message):
    response = apply(result, clarifications)
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_errors_name_the_candidate(result):
    detail = apply(result, {"tanvi_deshpande.txt": answers(notice_period=900)}).json()["detail"]
    assert detail.startswith("Tanvi Deshpande. Notice period")


def test_campus_results_cannot_take_call_answers():
    sample = client.get("/api/samples").json()
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    campus = client.post("/api/screenings", data={"job_description": sample["job_description"]}, files=files).json()
    assert apply(campus, {}).status_code == 422
    assert all(c["resolved"] is None for c in campus["candidates"])       # 1.0 results don't grow this field's content


def test_bad_states_are_rejected_by_the_schema(result):
    bad = {"tanvi_deshpande.txt": {"answers": {"notice_period": {"state": "maybe"}}}}
    assert apply(result, bad).status_code == 422


# ---------- Reading a pasted reply ----------

@pytest.mark.parametrize("text, expected", [
    ("NP 30 days, cctc 14, ectc 18, loc hyd",
     {"notice_period": 30.0, "current_ctc": 14.0, "expected_ctc": 18.0, "current_location": "Hyderabad"}),
    ("Hi, my notice period is 2 months. Current CTC: 12.5 LPA, Expected CTC: 16 LPA. I am in Bangalore.",
     {"notice_period": 60.0, "current_ctc": 12.5, "expected_ctc": 16.0, "current_location": "Bengaluru"}),
    ("immediate joiner. total exp 6.5 yrs. expecting 22 lpa",
     {"notice_period": 0.0, "total_experience": 6.5, "expected_ctc": 22.0}),
    ("ctc 9 lpa expected 12-13 lpa np 45d", {"current_ctc": 9.0, "expected_ctc": 13.0, "notice_period": 45.0}),
    ("Currently in Pune, open to relocate to Hyderabad", {"current_location": "Pune", "preferred_location": "Hyderabad"}),
    ("7 years of experience, notice 15 days", {"total_experience": 7.0, "notice_period": 15.0}),
    ("Thanks, will call you tomorrow.", {}),
    ("np 900 days ctc 9000", {}),                    # not believable, so not offered
])
def test_reply_reading(text, expected):
    found, _ = read_reply(text)
    assert {field: value["value"] for field, value in found.items()} == expected


def test_reply_values_keep_the_words_they_came_from():
    found, not_found = read_reply("NP 30 days, cctc 14, ectc 18")
    assert found["notice_period"]["quote"] == "NP 30 days" and "ectc 18" in found["expected_ctc"]["quote"]
    assert found["current_ctc"]["display"] == "14 LPA"
    assert not_found == ["phone", "total_experience", "current_location"]


def test_reply_api_only_suggests():
    body = client.post("/api/clarifications/read-reply", json={"text": "np 30 days ectc 18"}).json()
    assert body["found"]["notice_period"] == {"value": 30.0, "display": "30 days", "quote": "np 30 days"}
    assert "current_ctc" in body["not_found"]
    assert client.post("/api/clarifications/read-reply", json={"text": ""}).status_code == 422
