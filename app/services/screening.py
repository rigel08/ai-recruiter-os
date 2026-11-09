"""Screen a batch of resumes against one job description."""

from __future__ import annotations

import os
import re
import threading
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass

from app.schemas.screening import CandidateFacts, CandidateResult, Fact, ScreeningResult
from app.services.academics import find_cgpa
from app.services.facts import FIELD_LABELS, FIELD_UNITS, extract_facts, questions_to_ask
from app.services.parsing import UnreadableDocument, extract_text
from app.services.scoring import explain, score_resume, word_counts
from app.services.skills import skills_in, terms_from_input
from app.services.suggestions import DECISION_ORDER, suggest

MAX_FILE_BYTES = 5 * 1024 * 1024
# Less text than this usually means a scanned image with no text layer.
MIN_TEXT_CHARS = 100
# Parsing is pure-Python CPU work, so batches at least this big are spread
# across processes. Smaller ones aren't worth the cost of starting workers.
PARALLEL_THRESHOLD = 12

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_NAME_WORD = re.compile(r"[A-Za-z][A-Za-z.'-]*")
_NOT_NAME_WORDS = {"resume", "curriculum", "vitae", "cv", "profile", "summary", "objective", "contact"}

_pool: ProcessPoolExecutor | None = None
_pool_lock = threading.Lock()


@dataclass(frozen=True)
class ResumeFile:
    file_name: str
    data: bytes


def screen(
    job_description: str,
    must_haves_raw: str,
    files: list[ResumeFile],
    min_cgpa: float | None = None,
) -> ScreeningResult:
    must_haves = terms_from_input(must_haves_raw)
    must_have_names = {term.name.lower() for term in must_haves}
    other_skills = [term for term in skills_in(job_description) if term.name.lower() not in must_have_names]
    job_words = word_counts(job_description)

    ranked: list[CandidateResult] = []
    needs_review: list[CandidateResult] = []

    for file, (text, problem) in zip(files, _parse_all(files)):
        if text is None:
            needs_review.append(CandidateResult(file_name=file.file_name, status="needs_review", summary=problem))
            continue

        score = score_resume(text, must_haves, other_skills, job_words)
        cgpa = find_cgpa(text)
        suggestion = suggest(score, len(must_haves), cgpa, min_cgpa)
        summary = explain(score, len(must_haves), len(other_skills))
        if suggestion.cgpa_note:
            summary = f"{suggestion.cgpa_note} {summary}"
        found = extract_facts(text)

        ranked.append(
            CandidateResult(
                file_name=file.file_name,
                status="ranked",
                decision=suggestion.decision,
                score=score.total,
                name=guess_name(text),
                email=find_email(text),
                cgpa=cgpa,
                must_haves_matched=score.must_haves_matched,
                must_haves_missing=score.must_haves_missing,
                other_skills_matched=score.other_skills_matched,
                summary=summary,
                flags=suggestion.flags,
                interview_questions=suggestion.interview_questions,
                facts=CandidateFacts(**{
                    field: Fact(value=fact.value, unit=FIELD_UNITS.get(field), display=fact.display,
                                quote=fact.quote, note=fact.note, confirm=fact.confirm)
                    for field, fact in found.items()
                }),
                to_ask=questions_to_ask(found),
            )
        )

    # Group by suggestion, then highest score; ties go to whoever has more
    # must-haves, then by file name so the order is always the same.
    ranked.sort(
        key=lambda c: (DECISION_ORDER[c.decision], -c.score, -len(c.must_haves_matched), c.file_name.lower())
    )
    for position, candidate in enumerate(ranked, start=1):
        candidate.rank = position

    counts = {decision: 0 for decision in DECISION_ORDER}
    for candidate in ranked:
        counts[candidate.decision] += 1

    # A fact counts as covered only when it has a usable value, not just words like "negotiable".
    coverage = {
        field: sum(1 for c in ranked if (fact := getattr(c.facts, field)) is not None and fact.value is not None)
        for field in FIELD_LABELS
    }

    return ScreeningResult(
        must_haves=[term.name for term in must_haves],
        other_skills=[term.name for term in other_skills],
        min_cgpa=min_cgpa,
        ranked_count=len(ranked),
        needs_review_count=len(needs_review),
        decision_counts=counts,
        fact_coverage=coverage,
        candidates=ranked + needs_review,
    )


def parse_file(file_name: str, data: bytes) -> tuple[str | None, str | None]:
    """Return (text, None), or (None, reason) when a person needs to look.

    Runs in worker processes, so it returns plain values instead of raising.
    """
    if len(data) > MAX_FILE_BYTES:
        return None, "The file is larger than 5 MB, so it wasn't read."
    try:
        text = extract_text(file_name, data)
    except UnreadableDocument as exc:
        return None, str(exc)
    if len(text.strip()) < MIN_TEXT_CHARS:
        return None, "Almost no text was found. It may be a scanned image, so check it by hand."
    return text, None


def _parse_all(files: list[ResumeFile]) -> list[tuple[str | None, str | None]]:
    names = [file.file_name for file in files]
    blobs = [file.data for file in files]
    if len(files) >= PARALLEL_THRESHOLD and (os.cpu_count() or 1) > 1:
        try:
            return list(_get_pool().map(parse_file, names, blobs, chunksize=4))
        except BrokenProcessPool:
            # A worker died (for example, out of memory). Start fresh next
            # time and finish this batch in this process.
            shutdown_pool()
    return [parse_file(name, blob) for name, blob in zip(names, blobs)]


def _get_pool() -> ProcessPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 1))
        return _pool


def shutdown_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
            _pool = None


def guess_name(text: str) -> str | None:
    """The first short line of plain words near the top is usually the name."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:5]:
        words = line.split()
        if not 2 <= len(words) <= 4:
            continue
        if not all(_NAME_WORD.fullmatch(word) for word in words):
            continue
        if {word.lower().strip(".") for word in words} & _NOT_NAME_WORDS:
            continue
        return " ".join(word.capitalize() if word.isupper() else word for word in words)
    return None


def find_email(text: str) -> str | None:
    match = _EMAIL.search(text)
    return match.group(0) if match else None
