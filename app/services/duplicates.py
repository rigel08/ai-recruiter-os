"""Spot resumes that are probably the same person, so a recruiter doesn't call or submit them twice.

Only exact contact matches count: the same phone number or the same email address. Names are
not used, because different people share names.
"""

from __future__ import annotations

import re

from app.schemas.screening import CandidateResult, DuplicateGroup


def contact_keys(candidate: CandidateResult) -> list[tuple[str, str]]:
    """(kind, normalised value) for each contact detail on the resume."""
    keys = []
    if candidate.email:
        keys.append(("email address", candidate.email.strip().lower()))
    phone = candidate.facts.phone
    if phone is not None and phone.value:
        digits = re.sub(r"\D", "", str(phone.value))[-10:]
        if len(digits) == 10:
            keys.append(("phone number", digits))
    return keys


def find_duplicates(candidates: list[CandidateResult]) -> list[DuplicateGroup]:
    by_key: dict[tuple[str, str], list[CandidateResult]] = {}
    for candidate in candidates:
        for key in contact_keys(candidate):
            by_key.setdefault(key, []).append(candidate)

    groups: list[DuplicateGroup] = []
    seen: set[frozenset[str]] = set()
    for (kind, _), members in by_key.items():
        files = frozenset(member.file_name for member in members)
        if len(files) < 2:
            continue
        if files in seen:
            # The same resumes also share another detail: say so on the group already found.
            group = next(g for g in groups if frozenset(g.file_names) == files)
            if kind not in group.reason:
                group.reason = group.reason.replace("the same ", "the same " + kind + " and ", 1)
            continue
        seen.add(files)
        groups.append(DuplicateGroup(
            file_names=[member.file_name for member in members],
            names=[member.name or member.file_name for member in members],
            reason=f"They share the same {kind}.",
        ))
    return groups
