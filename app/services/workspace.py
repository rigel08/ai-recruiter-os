"""Saved sessions in one local SQLite file, using only the standard library.

What is kept: the job description, the requirements, the evaluation as shown on screen
(including the facts and lines extracted from each resume), call answers, notes and the
submission being edited. What is not kept: the resume files themselves or their full text.

This is for one recruiter on their own computer. There are no accounts, so the API that
uses it refuses requests from any other machine.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.screening import ScreeningResult
from app.services.duplicates import contact_keys

MAX_SUBMISSION_BYTES = 600_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    job_description TEXT NOT NULL,
    form TEXT NOT NULL,
    result TEXT NOT NULL,
    clarifications TEXT NOT NULL,
    submission TEXT
);
-- One row per phone number or email in a saved session, to notice the same person elsewhere.
CREATE TABLE IF NOT EXISTS contacts (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS contacts_value ON contacts(value);
"""


class NotFound(LookupError):
    pass


class TooLarge(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Workspace:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._ready = False

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self._ready:
            new_file = not self.path.exists()
            self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            if not self._ready:
                conn.executescript(SCHEMA)
                if new_file:
                    # It holds candidates' details and the recruiter's notes: readable by this user only.
                    os.chmod(self.path, 0o600)
                self._ready = True
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Reading ----------------------------------------------------------------------------------------

    @staticmethod
    def _summary(row: sqlite3.Row) -> dict[str, Any]:
        result = json.loads(row["result"])
        clarifications = json.loads(row["clarifications"])
        return {
            "id": row["id"], "name": row["name"], "status": row["status"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "candidates": sum(1 for c in result["candidates"] if c["status"] == "ranked"),
            "with_call_notes": sum(1 for entry in clarifications.values() if entry.get("answers") or entry.get("remarks")),
            "has_submission": row["submission"] is not None,
        }

    def list(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC, created_at DESC").fetchall()
        return [self._summary(row) for row in rows]

    def get(self, session_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise NotFound(session_id)
        return {
            **self._summary(row),
            "job_description": row["job_description"],
            "form": json.loads(row["form"]),
            "result": json.loads(row["result"]),
            "clarifications": json.loads(row["clarifications"]),
            "submission": json.loads(row["submission"]) if row["submission"] else None,
        }

    # Writing ----------------------------------------------------------------------------------------

    @staticmethod
    def _submission_text(submission: dict[str, Any] | None) -> str | None:
        if submission is None:
            return None
        text = json.dumps(submission, ensure_ascii=False)
        if len(text.encode("utf-8")) > MAX_SUBMISSION_BYTES:
            raise TooLarge("The submission is too large to save.")
        return text

    def create(self, name: str, job_description: str, form: dict[str, str], result: ScreeningResult,
               clarifications: dict[str, Any], submission: dict[str, Any] | None) -> dict[str, Any]:
        session_id = uuid.uuid4().hex[:12]
        now = _now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, name, created_at, updated_at, job_description, form, result, clarifications, submission) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, name.strip(), now, now, job_description, json.dumps(form, ensure_ascii=False),
                 result.model_dump_json(), json.dumps(clarifications, ensure_ascii=False), self._submission_text(submission)),
            )
            for candidate in result.candidates:
                if candidate.status != "ranked":
                    continue
                for kind, value in contact_keys(candidate):
                    conn.execute("INSERT INTO contacts (session_id, file_name, name, kind, value) VALUES (?, ?, ?, ?, ?)",
                                 (session_id, candidate.file_name, candidate.name or candidate.file_name, kind, value))
        return self.get(session_id)

    def update(self, session_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        columns: dict[str, Any] = {}
        if changes.get("name") is not None:
            columns["name"] = changes["name"].strip()
        if changes.get("status") is not None:
            columns["status"] = changes["status"]
        if changes.get("clarifications") is not None:
            columns["clarifications"] = json.dumps(changes["clarifications"], ensure_ascii=False)
        if changes.get("clear_submission"):
            columns["submission"] = None
        elif changes.get("submission") is not None:
            columns["submission"] = self._submission_text(changes["submission"])
        with self.connect() as conn:
            if conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone() is None:
                raise NotFound(session_id)
            columns["updated_at"] = _now()
            assignments = ", ".join(f"{column} = ?" for column in columns)  # fixed column names from above
            conn.execute(f"UPDATE sessions SET {assignments} WHERE id = ?", (*columns.values(), session_id))
        return self.get(session_id)

    def delete(self, session_id: str) -> None:
        with self.connect() as conn:
            if conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,)).rowcount == 0:
                raise NotFound(session_id)

    # The same person in another session ----------------------------------------------------------------

    def seen_elsewhere(self, result: ScreeningResult, exclude_session: str | None) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        with self.connect() as conn:
            for candidate in result.candidates:
                if candidate.status != "ranked":
                    continue
                sessions_seen: set[str] = set()
                for kind, value in contact_keys(candidate):
                    rows = conn.execute(
                        "SELECT s.id, s.name, s.status, s.created_at FROM contacts c JOIN sessions s ON s.id = c.session_id "
                        "WHERE c.value = ? AND c.kind = ? AND s.id IS NOT ? ORDER BY s.created_at DESC",
                        (value, kind, exclude_session),
                    ).fetchall()
                    for row in rows:
                        if row["id"] in sessions_seen:
                            continue
                        sessions_seen.add(row["id"])
                        found.append({
                            "file_name": candidate.file_name, "name": candidate.name or candidate.file_name,
                            "session_id": row["id"], "session_name": row["name"], "session_status": row["status"],
                            "saved_on": row["created_at"][:10], "matched_on": kind,
                        })
        return found
