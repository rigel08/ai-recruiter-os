"""Client submissions: drafted only from what is known, checked before sending, exported without contact details."""

import csv
import io
import zipfile
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.profile import extract_profile
from app.services.xlsx import workbook

client = TestClient(app)

LIMITS = {"hiring_mode": "experienced", "must_haves": "Java, Spring Boot, SQL",
          "preferred_skills": "REST APIs, Docker, AWS, Kubernetes, Redis", "min_experience_years": "5",
          "max_experience_years": "9", "max_notice_days": "60", "max_ctc_lpa": "24", "locations": "Hyderabad"}


@pytest.fixture(scope="module")
def result():
    sample = client.get("/api/samples", params={"kind": "experienced"}).json()
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    # The same person sent twice, as happens when a resume arrives by email and by WhatsApp.
    divya = next(r for r in sample["resumes"] if r["file_name"] == "divya_rao.txt")
    files.append(("resumes", ("divya_rao_whatsapp.txt", divya["text"].encode(), "text/plain")))
    return client.post("/api/screenings", data={"job_description": sample["job_description"], **LIMITS}, files=files).json()


def draft(result, file_names, clarifications=None, title="Senior Java Backend Developer"):
    return client.post("/api/submissions/draft", json={"result": result, "file_names": file_names,
                                                       "clarifications": clarifications or {}, "title": title})


def field(profile, key):
    return next(f for f in profile["fields"] if f["key"] == key)


def export(document, fmt):
    return client.post(f"/api/submissions/export?format={fmt}", json=document)


# ---------- Reading role, employer and education ----------

@pytest.mark.parametrize("text, expected", [
    ("Asha Rao\nSenior Analyst at Northwind Ltd (Jan 2021 - Present)\nB.Com, Osmania University, 2015",
     {"current_designation": "Senior Analyst", "current_employer": "Northwind Ltd", "education": "B.Com, Osmania University, 2015"}),
    ("Ravi K\nInfosys Limited — Technology Lead, Pune, 2019 to present",
     {"current_designation": "Technology Lead", "current_employer": "Infosys Limited"}),
    ("Senior Software Engineer, Northgate Payments, Hyderabad (2022 to present)",
     {"current_designation": "Senior Software Engineer", "current_employer": "Northgate Payments"}),
    ("Meena\nCurrent Company: Tata Consultancy Services | Designation: IT Analyst\nRelevant experience: 4.5 years",
     {"current_designation": "IT Analyst", "current_employer": "Tata Consultancy Services", "relevant_experience": 4.5}),
    ("Imran\nJava Developer\nSenior Developer, Coralbay Systems, Hyderabad (2021 to October 2026)",
     {"current_designation": "Java Developer"}),              # the dated job has ended, so only the headline counts
    ("Arun\nWorked on many projects, 2020 to present\nI want to be an engineer and so does he", {}),
    ("Kiran\nFreelance, 2022 to present", {}),                 # no title and no clear company: left blank
])
def test_profile_details(text, expected):
    assert {key: fact.value for key, fact in extract_profile(text).items()} == expected


def test_profile_details_keep_their_source_line():
    line = "Senior Software Engineer, Northgate Payments, Hyderabad (2022 to present)"
    found = extract_profile("Divya Rao\n" + line)
    assert found["current_designation"].quote == found["current_employer"].quote == line
    headline = extract_profile("Imran\nJava Developer")["current_designation"]
    assert "headline" in headline.note


# ---------- Drafting ----------

def test_draft_uses_only_known_values(result):
    body = draft(result, ["divya_rao.txt", "tanvi_deshpande.txt"]).json()
    divya, tanvi = body["profiles"]
    assert divya["summary"].startswith("Divya Rao is a Senior Software Engineer at Northgate Payments with 7 years 2 months of experience.")
    assert field(divya, "education")["value"] == "B.Tech, Computer Science, JNTU Hyderabad, 2019"
    assert field(divya, "availability") == {"key": "availability", "label": "Availability", "included": True, "contact": False,
                                            "value": "Can join about 30 days after an offer", "source": "worked_out"}
    assert divya["missing"] == []

    # Tanvi's resume states no tracker facts: nothing is filled in for her.
    assert [f["key"] for f in tanvi["fields"] if f["value"] is None and not f["contact"]] == [
        "total_experience", "relevant_experience", "current_location", "preferred_location", "current_ctc",
        "expected_ctc", "notice_period", "availability", "education"]
    assert "Total experience" in tanvi["missing"] and "Preferred location" not in tanvi["missing"]
    assert tanvi["summary"] == "Tanvi Deshpande is a Senior Java Engineer at Meridian Banking Tech. Skills matching the role: " \
                               "Java, Spring Boot, SQL, REST APIs, Docker, AWS, Kubernetes."
    assert "of experience" not in tanvi["summary"]


def test_strengths_list_only_what_is_met(result):
    rohit = draft(result, ["rohit_verma.txt"]).json()["profiles"][0]
    assert rohit["strengths"] == ["All 3 required skills: Java, Spring Boot, SQL.",
                                  "Preferred skills: REST APIs, Docker, AWS, Kubernetes, Redis.",
                                  "Experience: 9 years is within 5 to 9 years."]
    assert not any("90 days" in item or "Bengaluru" in item for item in rohit["strengths"])


def test_preflight_checks_flag_conflicts_unknowns_and_low_fit(result):
    profiles = {p["name"]: p for p in draft(result, ["rohit_verma.txt", "tanvi_deshpande.txt", "neha_kapoor.txt",
                                                      "divya_rao.txt"]).json()["profiles"]}
    rohit = [(c["level"], c["text"].split(" does")[0]) for c in profiles["Rohit Verma"]["checks"]]
    assert rohit == [("conflict", "Notice period"), ("conflict", "CTC"), ("conflict", "Location")]
    assert {c["level"] for c in profiles["Tanvi Deshpande"]["checks"]} == {"warning"}
    assert any("not known, and the client asked for 60 days or less" in c["text"] for c in profiles["Tanvi Deshpande"]["checks"])
    assert profiles["Neha Kapoor"]["checks"][0] == {"level": "conflict", "text": "Low skills fit: missing Java, Spring Boot, SQL."}
    assert profiles["Divya Rao"]["checks"] == []


def test_duplicates_in_a_submission_are_flagged(result):
    assert result["duplicates"] == [{"file_names": ["divya_rao.txt", "divya_rao_whatsapp.txt"], "names": ["Divya Rao", "Divya Rao"],
                                     "reason": "They share the same phone number and email address."}]
    body = draft(result, ["divya_rao.txt", "divya_rao_whatsapp.txt", "imran_sheikh.txt"]).json()
    assert body["checks"] == [{"level": "warning", "text": "Divya Rao and Divya Rao look like the same person. They share the same "
                                                           "phone number and email address. Submit only one."}]
    assert draft(result, ["divya_rao.txt", "imran_sheikh.txt"]).json()["checks"] == []


def test_call_answers_flow_into_the_profile_with_their_source(result):
    answers = {"tanvi_deshpande.txt": {"answers": {"notice_period": {"state": "answered", "value": 30},
                                                   "total_experience": {"state": "answered", "value": 6.5}},
                                       "remarks": "Available for interviews after 6 pm."},
               "suresh_pillai.txt": {"answers": {"notice_period": {"state": "confirmed"}}}}
    tanvi, suresh = draft(result, ["tanvi_deshpande.txt", "suresh_pillai.txt"], answers).json()["profiles"]
    assert (field(tanvi, "notice_period")["value"], field(tanvi, "notice_period")["source"]) == ("30 days", "recruiter_entered")
    assert tanvi["remarks"] == "Available for interviews after 6 pm."
    assert "with 6.5 years of experience" in tanvi["summary"]
    assert {"level": "note", "text": "From your call, not the resume: Total experience, Notice period."} in tanvi["checks"]
    assert field(suresh, "notice_period")["source"] == "recruiter_confirmed"


def test_draft_rejects_candidates_that_are_not_in_the_result(result):
    assert draft(result, ["nobody.txt"]).status_code == 422
    assert draft(result, []).status_code == 422


# ---------- Exporting ----------

def document(result, names, **options):
    body = draft(result, names).json()
    return {"title": body["title"], "profiles": body["profiles"], **options}


def test_contact_details_are_left_out_unless_asked_for(result):
    doc = document(result, ["divya_rao.txt"])
    for fmt in ("text", "csv"):
        out = export(doc, fmt).text
        assert "90000 00101" not in out and "divya.rao@example.com" not in out and "Phone" not in out
    with_contact = export({**doc, "include_contact": True}, "text").text
    assert "Phone: +91 90000 00101" in with_contact and "Email: divya.rao@example.com" in with_contact


def test_text_export_is_ready_to_paste(result):
    text = export(document(result, ["divya_rao.txt", "imran_sheikh.txt"]), "text").text
    assert text.startswith("Senior Java Backend Developer\n\n1. Divya Rao\nDivya Rao is a Senior Software Engineer")
    assert "Notice period: 30 days\n" in text and "\n2. Imran Sheikh\n" in text
    assert "Strengths for this role:\n- All 3 required skills: Java, Spring Boot, SQL." in text
    assert "Relevant experience" not in text          # unknown fields are simply absent, never "N/A" or a guess


def test_excluded_and_edited_fields_are_respected(result):
    doc = document(result, ["divya_rao.txt"])
    profile = doc["profiles"][0]
    field(profile, "current_ctc")["included"] = False
    field(profile, "expected_ctc")["value"] = "Open to discussion"
    field(profile, "expected_ctc")["source"] = "recruiter_entered"
    profile["summary"] = "A strong payments engineer."
    profile["remarks"] = "Interviewed by me on 10 Nov."
    profile["fields"].insert(0, profile["fields"].pop(next(i for i, f in enumerate(profile["fields"]) if f["key"] == "notice_period")))
    text = export(doc, "text").text
    assert "Current CTC" not in text
    assert "Expected CTC: Open to discussion (from recruiter's call)" in text
    assert text.index("Notice period: 30 days") < text.index("Current designation")      # the new order is kept
    assert "A strong payments engineer." in text and "Recruiter's remarks: Interviewed by me on 10 Nov." in text
    assert "(from recruiter's call)" not in export({**doc, "show_sources": False}, "text").text


def test_csv_export_has_one_row_per_candidate(result):
    response = export(document(result, ["divya_rao.txt", "tanvi_deshpande.txt"]), "csv")
    assert response.headers["content-disposition"] == 'attachment; filename="candidate-profiles.csv"'
    table = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))
    assert table[0][0] == "Candidate" and table[0][-3:] == ["Summary", "Strengths for this role", "Recruiter's remarks"]
    assert [row[0] for row in table[1:]] == ["Divya Rao", "Tanvi Deshpande"]
    notice = table[0].index("Notice period")
    assert (table[1][notice], table[2][notice]) == ("30 days", "")          # unknown stays empty
    assert "Phone" not in table[0] and "Email" not in table[0]


def test_formula_like_values_are_defused_in_the_submission_csv(result):
    doc = document(result, ["divya_rao.txt"])
    doc["profiles"][0]["name"] = "=cmd|' /C calc'!A0"
    table = list(csv.reader(io.StringIO(export(doc, "csv").content.decode("utf-8-sig"), newline="")))
    assert table[1][0].startswith("'=cmd")


def test_xlsx_export_is_a_valid_workbook_with_the_same_table(result):
    response = export(document(result, ["divya_rao.txt", "rohit_verma.txt"]), "xlsx")
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml",
            "xl/worksheets/sheet1.xml"} <= set(archive.namelist())
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    for name in archive.namelist():
        ElementTree.fromstring(archive.read(name))                          # every part is well-formed XML
    sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows = [["".join(t.text or "" for t in cell.iter(f"{{{ns['m']}}}t")) for cell in row] for row in sheet.iter(f"{{{ns['m']}}}row")]
    assert rows[0][0] == "Candidate" and [row[0] for row in rows[1:]] == ["Divya Rao", "Rohit Verma"]
    assert "30 days" in rows[1] and "divya.rao@example.com" not in rows[1]


def test_xlsx_writer_escapes_and_names_columns():
    data = workbook(["A & B", "<tag>"], [["x\x00y", None], ["=1+1", 'say "hi"']], sheet_name="Bad/Name:*")
    archive = zipfile.ZipFile(io.BytesIO(data))
    sheet = archive.read("xl/worksheets/sheet1.xml").decode()
    assert "A &amp; B" in sheet and "&lt;tag&gt;" in sheet and "xy" in sheet and "\x00" not in sheet
    assert 'r="B3"' in sheet and "=1+1" in sheet          # kept as text: the cell type is inlineStr, not a formula
    assert 'name="Bad Name  "' in archive.read("xl/workbook.xml").decode()


@pytest.mark.parametrize("change", [
    lambda d: d.update(profiles=[]),
    lambda d: d["profiles"][0].update(summary="x" * 3001),
    lambda d: d["profiles"][0]["fields"][0].update(source="made_up"),
])
def test_bad_documents_are_rejected(result, change):
    doc = document(result, ["divya_rao.txt"])
    change(doc)
    assert export(doc, "csv").status_code == 422
    assert export(document(result, ["divya_rao.txt"]), "pdf").status_code == 422
