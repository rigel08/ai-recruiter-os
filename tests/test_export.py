"""CSV export: the campus file is byte-for-byte the 1.0 file; the experienced file adds the evaluation."""

import csv
import io

from fastapi.testclient import TestClient

from app.main import app
from app.services.export import CAMPUS_HEADER, EXPERIENCED_HEADER, to_csv
from app.schemas.screening import ScreeningResult

client = TestClient(app)

LIMITS = {"hiring_mode": "experienced", "must_haves": "Java, Spring Boot, SQL",
          "preferred_skills": "REST APIs, Docker, AWS, Kubernetes, Redis", "min_experience_years": "5",
          "max_experience_years": "9", "max_notice_days": "60", "max_ctc_lpa": "24", "locations": "Hyderabad"}


def screen(kind, **data):
    sample = client.get("/api/samples", params={"kind": kind}).json()
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    files.append(("resumes", ("scan.pdf", b"not a pdf", "application/pdf")))
    data = {"job_description": sample["job_description"], "must_haves": sample["must_haves"], **data}
    if kind == "campus":
        data["min_cgpa"] = "7.0"
    return client.post("/api/screenings", data=data, files=files).json()


def rows(text):
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text[1:], newline="")))


def test_campus_csv_matches_the_1_0_file_exactly():
    text = to_csv(ScreeningResult(**screen("campus")))
    lines = text.split("\r\n")
    assert lines[0] == '﻿"Rank","Suggestion","Name","Email","CGPA","Score","File","Must-haves matched",' \
                       '"Must-haves missing","Other skills matched","Summary","Flags","Interview questions"'
    # The first data row as the 1.0 page's JavaScript wrote it: every cell quoted, 8.7 not 8.70.
    assert lines[1].startswith('"1","Shortlist","Ananya Reddy","ananya.reddy@example.com","8.7","')
    table = rows(text)
    assert all(len(row) == 13 for row in table) and len(table) == 1 + 8 + 1
    assert table[-1][:7] == ["", "Needs a manual look", "", "", "", "", "scan.pdf"]


def test_whole_number_cgpa_is_written_like_javascript_did():
    result = ScreeningResult(**screen("campus"))
    result.candidates[0].cgpa = 7.0
    assert rows(to_csv(result))[1][4] == "7"


def test_cells_that_look_like_formulas_are_defused():
    result = ScreeningResult(**screen("campus"))
    result.candidates[0].name = '=HYPERLINK("http://evil.example","x")'
    result.candidates[1].name = "+91 trick"
    table = rows(to_csv(result))
    assert table[1][2].startswith("'=HYPERLINK") and table[2][2] == "'+91 trick"


def test_experienced_csv_has_the_evaluation_facts_and_evidence():
    table = rows(to_csv(ScreeningResult(**screen("experienced", **LIMITS))))
    assert table[0] == EXPERIENCED_HEADER and all(len(row) == len(EXPERIENCED_HEADER) for row in table)
    by_name = {row[3]: dict(zip(table[0], row)) for row in table[1:]}

    divya = by_name["Divya Rao"]
    assert (divya["Next step"], divya["Skills fit"], divya["Information stated"]) == ("Looks ready", "Strong", "6 of 6")
    assert divya["Notice period check"] == "Meets: 30 days is within the 60-day limit."
    assert divya["Phone"] == "91 90000 00101"                       # no leading "+", so no apostrophe is added
    assert 'Notice period: "Notice Period: 30 Days"' in divya["Evidence"]

    rohit = by_name["Rohit Verma"]
    assert rohit["Next step"] == "Conflicts with a limit" and rohit["Skills fit"] == "Strong"
    assert rohit["Notice period check"].startswith("Does not meet: 90 days is 30 days over")
    assert rohit["CTC check"].startswith("Does not meet: Expects 34 LPA")
    assert rohit["Location check"] == "Does not meet: Currently in Bengaluru; the role is in Hyderabad."

    lakshmi = by_name["Lakshmi Narayanan"]
    assert lakshmi["Expected CTC (LPA)"] == ""                      # "30% hike" is not a number
    assert lakshmi["CTC check"].startswith('Check by hand: Expected CTC on the resume is "30% hike"')
    assert "Read \"8.10 years\" as 8 years 10 months" in lakshmi["Notes"]

    tanvi = by_name["Tanvi Deshpande"]
    assert tanvi["Next step"] == "Clarify first" and tanvi["Notice period check"].startswith("Unknown:")
    assert tanvi["Ask on the call"].startswith("Phone number, Total experience")

    number_columns = ["Skills score", "Total experience (years)", "Notice period (days)", "Current CTC (LPA)", "Expected CTC (LPA)"]
    for row in by_name.values():
        for column in number_columns:
            assert row[column] == "" or float(row[column]) >= 0

    unreadable = table[-1]
    assert unreadable[1] == "Needs a manual look" and unreadable[5] == "scan.pdf" and "couldn't be opened" in unreadable[2]


def test_limits_that_were_not_set_say_so():
    result = screen("experienced", hiring_mode="experienced")
    table = rows(to_csv(ScreeningResult(**result)))
    row = dict(zip(table[0], table[1]))
    assert row["Notice period check"] == row["CTC check"] == row["Location check"] == row["Experience check"] == "Not set"


def test_export_endpoint_returns_a_csv_download():
    result = screen("campus")
    response = client.post("/api/exports/csv", json=result)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="shortlist.csv"'
    assert response.content.startswith(b"\xef\xbb\xbf") and response.content.count(b"\r\n") == 9
    assert rows(response.content.decode("utf-8"))[0] == CAMPUS_HEADER


def test_export_endpoint_rejects_things_that_are_not_results():
    assert client.post("/api/exports/csv", json={"candidates": "nope"}).status_code == 422
    result = screen("campus")
    result["candidates"] = result["candidates"][:1] * 251
    assert client.post("/api/exports/csv", json=result).status_code == 413
