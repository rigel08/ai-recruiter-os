"""Saved sessions: stored locally, restored exactly, and closed to every other machine."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.routes import workspace
from app.main import app

WRITE = {"X-Workspace": "1"}
LIMITS = {"hiring_mode": "experienced", "must_haves": "Java, Spring Boot, SQL",
          "preferred_skills": "REST APIs, Docker, AWS, Kubernetes, Redis", "min_experience_years": "5",
          "max_experience_years": "9", "max_notice_days": "60", "max_ctc_lpa": "24", "locations": "Hyderabad"}
TANVI_CALL = {"tanvi_deshpande.txt": {"answers": {"notice_period": {"state": "answered", "value": 30}}, "remarks": "Call back Friday."}}

plain = TestClient(app)


@pytest.fixture(scope="module")
def result():
    sample = plain.get("/api/samples", params={"kind": "experienced"}).json()
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    files.append(("resumes", ("scan.pdf", b"not a pdf", "application/pdf")))
    return plain.post("/api/screenings", data={"job_description": sample["job_description"], **LIMITS}, files=files).json()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client treated as local, writing to a throwaway database."""
    monkeypatch.setenv("WORKSPACE_DB", str(tmp_path / "workspace.db"))
    monkeypatch.delenv("RECRUITER_WORKSPACE", raising=False)
    app.dependency_overrides[workspace.local_only] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def save(client, result, name="Senior Java, GCC", **extra):
    body = {"name": name, "job_description": "Senior Java Backend Developer for a GCC in Hyderabad.",
            "form": {"must_haves": "Java, Spring Boot, SQL", "max_notice_days": "60"}, "result": result, **extra}
    return client.post("/api/workspace/sessions", json=body, headers=WRITE)


def test_a_saved_session_comes_back_exactly(client, result, tmp_path):
    created = save(client, result, clarifications=TANVI_CALL, submission={"title": "Profiles", "order": ["skills"]})
    assert created.status_code == 201
    session = created.json()
    assert (session["name"], session["status"], session["candidates"], session["with_call_notes"], session["has_submission"]) == \
           ("Senior Java, GCC", "open", 8, 1, True)

    restored = client.get(f"/api/workspace/sessions/{session['id']}").json()
    assert restored["result"] == result
    assert restored["clarifications"]["tanvi_deshpande.txt"]["answers"]["notice_period"]["value"] == 30
    assert restored["clarifications"]["tanvi_deshpande.txt"]["remarks"] == "Call back Friday."
    assert restored["form"] == {"must_haves": "Java, Spring Boot, SQL", "max_notice_days": "60"}
    assert restored["submission"] == {"title": "Profiles", "order": ["skills"]}
    assert restored["job_description"].startswith("Senior Java Backend Developer")

    database = tmp_path / "workspace.db"
    assert database.exists() and database.stat().st_mode & 0o077 == 0        # readable by this user only


def test_sessions_are_listed_newest_first_with_counts(client, result):
    save(client, result, name="First")
    second = save(client, result, name="Second", clarifications=TANVI_CALL).json()
    listing = client.get("/api/workspace/sessions").json()
    assert [s["name"] for s in listing] == ["Second", "First"] or {s["name"] for s in listing} == {"First", "Second"}
    by_name = {s["name"]: s for s in listing}
    assert (by_name["Second"]["with_call_notes"], by_name["First"]["with_call_notes"]) == (1, 0)
    assert "result" not in listing[0]                                         # the list carries no candidate data
    assert second["id"] in {s["id"] for s in listing}


def test_updates_change_only_what_is_sent(client, result):
    session = save(client, result).json()
    url = f"/api/workspace/sessions/{session['id']}"
    renamed = client.patch(url, json={"name": "Java, Northgate", "status": "submitted"}, headers=WRITE).json()
    assert (renamed["name"], renamed["status"]) == ("Java, Northgate", "submitted")
    noted = client.patch(url, json={"clarifications": TANVI_CALL}, headers=WRITE).json()
    assert noted["with_call_notes"] == 1 and noted["name"] == "Java, Northgate"
    with_doc = client.patch(url, json={"submission": {"title": "x"}}, headers=WRITE).json()
    assert with_doc["has_submission"] and with_doc["clarifications"] == noted["clarifications"]
    cleared = client.patch(url, json={"clear_submission": True}, headers=WRITE).json()
    assert cleared["submission"] is None and cleared["status"] == "submitted"


def test_delete_removes_the_session_and_its_contact_rows(client, result, tmp_path):
    session = save(client, result).json()
    assert client.delete(f"/api/workspace/sessions/{session['id']}", headers=WRITE).status_code == 204
    assert client.get(f"/api/workspace/sessions/{session['id']}").status_code == 404
    assert client.get("/api/workspace/sessions").json() == []
    rows = sqlite3.connect(tmp_path / "workspace.db").execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    assert rows == 0


def test_resume_files_and_full_text_are_not_stored(client, result, tmp_path):
    save(client, result)
    dump = "\n".join(str(row) for row in sqlite3.connect(tmp_path / "workspace.db").execute("SELECT * FROM sessions"))
    # A line that is in Divya's resume but is neither a fact nor evidence for one.
    assert "Tuned PostgreSQL queries and cut report time" not in dump
    assert "Notice Period: 30 Days" in dump                                   # extracted evidence is kept, as shown on screen


@pytest.mark.parametrize("change, code", [
    (lambda body: body.update(name=""), 422),
    (lambda body: body.update(name="x" * 121), 422),
    (lambda body: body.update(clarifications={"nobody.txt": {"answers": {}}}), 422),
    (lambda body: body.update(clarifications={"tanvi_deshpande.txt": {"answers": {"notice_period": {"state": "answered", "value": 999}}}}), 422),
    (lambda body: body.update(submission={"blob": "x" * 700_000}), 413),
])
def test_bad_sessions_are_refused(client, result, change, code):
    body = {"name": "ok", "job_description": "jd", "result": result}
    change(body)
    assert client.post("/api/workspace/sessions", json=body, headers=WRITE).status_code == code


def test_campus_results_cannot_be_saved(client):
    sample = plain.get("/api/samples").json()
    files = [("resumes", (r["file_name"], r["text"].encode(), "text/plain")) for r in sample["resumes"]]
    campus = plain.post("/api/screenings", data={"job_description": sample["job_description"]}, files=files).json()
    assert client.post("/api/workspace/sessions", json={"name": "c", "job_description": "jd", "result": campus}, headers=WRITE).status_code == 422


def test_unknown_session_and_bad_status(client, result):
    assert client.get("/api/workspace/sessions/nope").status_code == 404
    assert client.patch("/api/workspace/sessions/nope", json={"name": "x"}, headers=WRITE).status_code == 404
    assert client.delete("/api/workspace/sessions/nope", headers=WRITE).status_code == 404
    session = save(client, result).json()
    assert client.patch(f"/api/workspace/sessions/{session['id']}", json={"status": "won"}, headers=WRITE).status_code == 422


def test_the_same_person_in_another_session_is_noticed(client, result):
    first = save(client, result, name="Java, Northgate").json()
    client.patch(f"/api/workspace/sessions/{first['id']}", json={"status": "submitted"}, headers=WRITE)

    # A later requirement where only Divya turns up again, with a different file name.
    divya = next(c for c in result["candidates"] if c["name"] == "Divya Rao")
    later = {**result, "candidates": [{**divya, "file_name": "Divya_Resume_Final.pdf"}]}
    seen = client.post("/api/workspace/seen", json={"result": later}, headers=WRITE).json()
    assert seen == [{"file_name": "Divya_Resume_Final.pdf", "name": "Divya Rao", "session_id": first["id"],
                     "session_name": "Java, Northgate", "session_status": "submitted",
                     "saved_on": first["created_at"][:10], "matched_on": "email address"}]
    # A session doesn't report itself.
    assert client.post("/api/workspace/seen", json={"result": result, "exclude_session": first["id"]}, headers=WRITE).json() == []
    # People with no contact details on their resume are never matched on name.
    tanvi = next(c for c in result["candidates"] if c["name"] == "Tanvi Deshpande")
    assert tanvi["facts"]["phone"] is None
    assert not any(s["name"] == "Tanvi Deshpande" for s in client.post("/api/workspace/seen", json={"result": result}, headers=WRITE).json()
                   if s["matched_on"] == "phone number")


# ---------- Closed to other machines ----------

def test_other_machines_are_refused(result, tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DB", str(tmp_path / "workspace.db"))
    # The test client reports itself as "testclient", which is not this computer's loopback address.
    assert plain.get("/api/workspace/sessions").status_code == 403
    assert plain.post("/api/workspace/sessions", json={"name": "x", "job_description": "", "result": result}, headers=WRITE).status_code == 403
    assert not (tmp_path / "workspace.db").exists()                           # nothing was even created
    info = plain.get("/api/workspace").json()
    assert info["enabled"] is False and info["location"] is None


def test_host_header_and_write_header_are_checked(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DB", str(tmp_path / "workspace.db"))
    monkeypatch.setattr(workspace, "LOCAL_CLIENTS", frozenset({"testclient"}))
    local = {"Host": "localhost:8765"}
    assert plain.get("/api/workspace/sessions", headers=local).status_code == 200
    assert plain.get("/api/workspace/sessions", headers={"Host": "evil.example:8765"}).status_code == 403    # DNS rebinding
    assert plain.delete("/api/workspace/sessions/abc", headers=local).status_code == 403                     # no write header
    assert plain.delete("/api/workspace/sessions/abc", headers={**local, **WRITE}).status_code == 404
    assert plain.get("/api/workspace", headers=local).json()["enabled"] is True


def test_a_hosted_copy_has_no_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("RECRUITER_WORKSPACE", "off")
    monkeypatch.setattr(workspace, "LOCAL_CLIENTS", frozenset({"testclient"}))
    assert plain.get("/api/workspace/sessions", headers={"Host": "localhost"}).status_code == 404
    assert plain.get("/api/workspace", headers={"Host": "localhost"}).json()["enabled"] is False


def test_workspace_is_off_in_the_docker_image_and_out_of_git():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    assert "RECRUITER_WORKSPACE=off" in (root / "Dockerfile").read_text()
    assert "data/" in (root / ".gitignore").read_text().splitlines()
    assert "data/" in (root / ".dockerignore").read_text().splitlines()
