"""Turn evaluated candidates into client-facing profiles.

Everything in a profile is either stated on the resume, recorded by the recruiter, or worked out
from those in a way the profile says. Nothing is invented, and unknown stays unknown. Phone and
email are left out unless the recruiter asks for them.
"""

from __future__ import annotations

from datetime import date

from app.schemas.clarifications import CandidateClarification
from app.schemas.screening import CandidateResult, ScreeningResult
from app.schemas.submissions import PreflightCheck, ProfileDraft, ProfileField, SubmissionDocument, SubmissionDraft
from app.services import xlsx
from app.services.clarify import ClarificationError, apply
from app.services.duplicates import find_duplicates
from app.services.export import BOM, _cell

SOURCE_WORDS = {"resume": "resume", "recruiter_confirmed": "confirmed with candidate", "recruiter_entered": "from recruiter's call",
                "worked_out": "worked out", "unknown": "not known"}
# In the order a client usually reads them. The recruiter can reorder and exclude.
FIELD_ORDER = [
    ("current_designation", "Current designation"), ("current_employer", "Current employer"),
    ("total_experience", "Total experience"), ("relevant_experience", "Relevant experience"),
    ("skills", "Skills matching the role"), ("current_location", "Current location"),
    ("preferred_location", "Preferred location"), ("current_ctc", "Current CTC"), ("expected_ctc", "Expected CTC"),
    ("notice_period", "Notice period"), ("availability", "Availability"), ("education", "Education"),
    ("phone", "Phone"), ("email", "Email"),
]
CONTACT_KEYS = ("phone", "email")
# Not knowing these is normal, so they aren't listed as missing.
OPTIONAL_KEYS = ("preferred_location", "relevant_experience", "availability")


def _field(key: str, label: str, value: str | None, source: str) -> ProfileField:
    known = value is not None and str(value).strip() != ""
    return ProfileField(key=key, label=label, value=str(value) if known else None,
                        source=source if known else "unknown", contact=key in CONTACT_KEYS)


def _availability(candidate: CandidateResult) -> tuple[str | None, str]:
    """Said in words, from the notice period only. A last working day is repeated as the resume wrote it."""
    notice = candidate.resolved["notice_period"]
    if notice.value is not None:
        if notice.value == 0:
            return "Can join immediately", "worked_out"
        return f"Can join about {notice.display} after an offer", "worked_out"
    resume = candidate.facts.notice_period
    if resume is not None and "serving" in resume.tags:
        return f"Serving notice. {resume.note}" if resume.note else "Serving notice", "resume"
    return None, "unknown"


def _fields(candidate: CandidateResult) -> list[ProfileField]:
    fields = []
    skills = candidate.evaluation.skills
    for key, label in FIELD_ORDER:
        if key in candidate.resolved:
            resolved = candidate.resolved[key]
            fields.append(_field(key, label, resolved.display, resolved.source))
        elif key in ("current_designation", "current_employer", "education", "relevant_experience"):
            fact = candidate.profile.get(key)
            fields.append(_field(key, label, fact.display if fact else None, "resume"))
        elif key == "skills":
            found = skills.required_matched + skills.preferred_matched
            fields.append(_field(key, label, ", ".join(found) if found else None, "resume"))
        elif key == "availability":
            fields.append(_field(key, label, *_availability(candidate)))
        elif key == "email":
            fields.append(_field(key, label, candidate.email, "resume"))
    return fields


def _strengths(candidate: CandidateResult) -> list[str]:
    """Only what the evaluation found to be met. Gaps are for the recruiter's checks, not the client's page."""
    skills = candidate.evaluation.skills
    strengths = []
    required = len(skills.required_matched) + len(skills.required_missing)
    if skills.required_matched:
        lead = f"All {required} required skills" if not skills.required_missing else f"{len(skills.required_matched)} of {required} required skills"
        strengths.append(f"{lead}: {', '.join(skills.required_matched)}.")
    if skills.preferred_matched:
        strengths.append(f"Preferred skills: {', '.join(skills.preferred_matched)}.")
    checks = ([skills.experience] if skills.experience else []) + candidate.evaluation.constraints.checks
    strengths += [f"{check.label}: {check.reason}" for check in checks if check.status == "meets"]
    return strengths


def _summary(name: str, fields: list[ProfileField]) -> str:
    """A plain starting point built only from known values. The recruiter rewrites it."""
    known = {field.key: field.value for field in fields if field.value}
    role, employer, experience = known.get("current_designation"), known.get("current_employer"), known.get("total_experience")
    if role and employer:
        opening = f"{name} is a {role} at {employer}"
    elif role:
        opening = f"{name} is a {role}"
    else:
        opening = name
    if experience:
        opening += f" with {experience} of experience" if role else f" has {experience} of experience"
    elif not role:
        return ""
    sentences = [opening + "."]
    if known.get("skills"):
        sentences.append(f"Skills matching the role: {known['skills']}.")
    if known.get("current_location"):
        sentences.append(f"Based in {known['current_location']}.")
    return " ".join(sentences)


def _preflight(candidate: CandidateResult, fields: list[ProfileField]) -> list[PreflightCheck]:
    evaluation = candidate.evaluation
    checks = ([evaluation.skills.experience] if evaluation.skills.experience else []) + evaluation.constraints.checks
    found: list[PreflightCheck] = []
    for check in checks:
        if check.status == "does_not_meet":
            found.append(PreflightCheck(level="conflict", text=f"{check.label} does not meet what the client asked for ({check.required}). {check.reason}"))
    if evaluation.skills.level == "weak":
        missing = ", ".join(evaluation.skills.required_missing) or "most of the skills asked for"
        found.append(PreflightCheck(level="conflict", text=f"Low skills fit: missing {missing}."))
    for check in checks:
        if check.status in ("near", "needs_review"):
            found.append(PreflightCheck(level="warning", text=f"{check.label} needs a closer look. {check.reason}"))
        elif check.status == "unknown":
            found.append(PreflightCheck(level="warning", text=f"{check.label} is not known, and the client asked for {check.required}."))
    entered = [field.label for field in fields if field.source == "recruiter_entered"]
    if entered:
        found.append(PreflightCheck(level="note", text=f"From your call, not the resume: {', '.join(entered)}."))
    return found


def build_draft(result: ScreeningResult, clarifications: dict[str, CandidateClarification], file_names: list[str],
                title: str) -> SubmissionDraft:
    updated = apply(result, clarifications)
    by_file = {c.file_name: c for c in updated.candidates if c.status == "ranked" and c.evaluation is not None}
    strangers = [name for name in file_names if name not in by_file]
    if strangers:
        raise ClarificationError(f"Not an evaluated candidate in this result: {', '.join(strangers)}.")

    chosen = [by_file[name] for name in dict.fromkeys(file_names)]
    profiles = []
    for candidate in chosen:
        name = candidate.name or candidate.file_name
        fields = _fields(candidate)
        profiles.append(ProfileDraft(
            file_name=candidate.file_name, name=name, summary=_summary(name, fields), strengths=_strengths(candidate),
            remarks=candidate.remarks, fields=fields,
            missing=[f.label for f in fields if f.value is None and not f.contact and f.key not in OPTIONAL_KEYS],
            checks=_preflight(candidate, fields),
        ))
    overall = [PreflightCheck(level="warning", text=f"{' and '.join(group.names)} look like the same person. {group.reason} Submit only one.")
               for group in find_duplicates(chosen)]
    return SubmissionDraft(title=title.strip() or "Candidate profiles", prepared_on=date.today(), profiles=profiles, checks=overall)


# Exporting the finalised document ---------------------------------------------------------------------

def _visible(profile: ProfileDraft, document: SubmissionDocument) -> list[ProfileField]:
    """The fields that go out: included, known, and never contact details unless asked for."""
    return [field for field in profile.fields
            if field.included and field.value and (document.include_contact or not field.contact)]


def _value(field: ProfileField, document: SubmissionDocument) -> str:
    if document.show_sources and field.source in ("recruiter_confirmed", "recruiter_entered"):
        return f"{field.value} ({SOURCE_WORDS[field.source]})"
    return field.value


def to_text(document: SubmissionDocument) -> str:
    blocks = []
    for number, profile in enumerate(document.profiles, start=1):
        lines = [f"{number}. {profile.name}" if len(document.profiles) > 1 else profile.name]
        if profile.summary.strip():
            lines.append(profile.summary.strip())
        lines += [f"{field.label}: {_value(field, document)}" for field in _visible(profile, document)]
        if profile.strengths:
            lines.append("Strengths for this role:")
            lines += [f"- {item}" for item in profile.strengths]
        if profile.remarks.strip():
            lines.append(f"Recruiter's remarks: {profile.remarks.strip()}")
        blocks.append("\n".join(lines))
    heading = document.title.strip()
    return (heading + "\n\n" if heading else "") + "\n\n".join(blocks) + "\n"


def to_table(document: SubmissionDocument) -> tuple[list[str], list[list[str]]]:
    """One row per candidate. Columns follow the first profile's field order, then any others."""
    labels: list[str] = []
    for profile in document.profiles:
        for field in _visible(profile, document):
            if field.label not in labels:
                labels.append(field.label)
    header = ["Candidate", *labels, "Summary", "Strengths for this role", "Recruiter's remarks"]
    rows = []
    for profile in document.profiles:
        values = {field.label: _value(field, document) for field in _visible(profile, document)}
        rows.append([profile.name, *(values.get(label, "") for label in labels), profile.summary.strip(),
                     " | ".join(profile.strengths), profile.remarks.strip()])
    return header, rows


def to_csv(document: SubmissionDocument) -> str:
    header, rows = to_table(document)
    return BOM + "\r\n".join(",".join(_cell(value) for value in line) for line in [header, *rows])


def to_xlsx(document: SubmissionDocument) -> bytes:
    header, rows = to_table(document)
    return xlsx.workbook(header, rows, sheet_name="Candidates")
