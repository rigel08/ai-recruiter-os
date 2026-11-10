"""Read the extra details a client-facing profile needs: current role, employer, education.

Same rule as the rest of the extraction: only what the resume states, with the line it came
from. A title and a company on one line are told apart by the words in them; if that isn't
clear, nothing is returned and the recruiter fills it in.
"""

from __future__ import annotations

import re

from app.services.facts import _SEP, _YEARS, Found, _clip, _lines, _years
from app.services.locations import cities_in

PROFILE_LABELS = {
    "current_designation": "Current designation",
    "current_employer": "Current employer",
    "relevant_experience": "Relevant experience",
    "education": "Education",
}
HEADLINE_LINES = 5

_ROLE = re.compile(
    r"\b(?:engineer|developer|programmer|architect|lead|manager|consultant|analyst|tester|designer|administrator|"
    r"specialist|executive|officer|associate|scientist|recruiter|head|director|intern|trainee|accountant|"
    r"coordinator|supervisor|technician|writer|devops|sre)\b",
    re.IGNORECASE,
)
_COMPANY = re.compile(
    r"\b(?:ltd|limited|pvt|private|inc|llp|corp|corporation|technologies|technology|solutions|systems|services|"
    r"software|infotech|labs|consulting|consultancy|bank|group|tech|payments|fintech|retail|commerce|apps|global)\b\.?",
    re.IGNORECASE,
)
# "Senior Engineer, Northgate Payments, Hyderabad (2022 to present)": the job the candidate is in now.
_CURRENT_JOB = re.compile(
    r"^(?P<body>.+?)[\s,(|–-]+(?:[A-Za-z]{3,9}\.?\s+)?(?:19|20)\d{2}\s*(?:-|–|to|till|until)\s*"
    r"(?:present|current|till\s+date|date|now)\b\)?\.?$",
    re.IGNORECASE,
)
_DESIGNATION_LABEL = re.compile(r"\b(?:current\s+)?(?:designation|job\s+title|position|current\s+role)\s*[:\-–]\s*(.+)$", re.IGNORECASE)
_EMPLOYER_LABEL = re.compile(r"\b(?:current|present)\s+(?:company|employer|organi[sz]ation)\s*[:\-–]\s*(.+)$", re.IGNORECASE)
_RELEVANT = re.compile(rf"\brelevant\s+exp(?:erience)?\b{_SEP}{_YEARS}", re.IGNORECASE)
# Short forms are matched in capitals only, so "be" and "me" in a sentence don't count.
_DEGREE = re.compile(
    r"\b(?:B\.?\s?Tech|M\.?\s?Tech|B\.E\.?|BE|M\.E\.?|MCA|BCA|B\.?Sc|M\.?Sc|MBA|BBA|B\.?Com|M\.?Com|Ph\.?D|PGDM|PGDBA)\b"
    r"|\b(?i:bachelor(?:'s)?|master(?:'s)?|diploma|b\.?\s?tech|m\.?\s?tech)\b"
)
_EDUCATION_LABEL = re.compile(r"^\s*(?:education|qualification|academics?)\s*[:\-–]\s*", re.IGNORECASE)


def _tidy(text: str) -> str:
    return text.strip(" ,.-–|()")


def _current_job(lines: list[str]) -> tuple[Found | None, Found | None]:
    for line in lines:
        match = _CURRENT_JOB.match(line.lstrip("-•* "))
        if not match:
            continue
        parts = [_tidy(part) for part in re.split(r",|\s+at\s+|\s[|–—-]\s|@", match.group("body")) if _tidy(part)]
        # A title ends in its role word ("Senior Software Engineer"); a company name doesn't.
        role = next((part for part in parts if _ROLE.fullmatch(part.split()[-1])), None)
        others = [part for part in parts if part != role and not (cities_in(part) and len(part.split()) <= 2)]
        company = next((part for part in others if _COMPANY.search(part)), None) or (others[0] if role and len(others) == 1 else None)
        quote = _clip(line, 0, len(line))
        return (Found(role, role, quote) if role and len(role.split()) <= 8 else None,
                Found(company, company, quote) if company and len(company.split()) <= 8 else None)
    return None, None


def extract_profile(text: str) -> dict[str, Found]:
    lines = _lines(text)
    found: dict[str, Found] = {}

    for line in lines:
        if "current_designation" not in found and (match := _DESIGNATION_LABEL.search(line)):
            value = _tidy(match.group(1).split("|")[0])
            if value and len(value.split()) <= 8:
                found["current_designation"] = Found(value, value, _clip(line, match.start(), match.end()))
        if "current_employer" not in found and (match := _EMPLOYER_LABEL.search(line)):
            value = _tidy(match.group(1).split("|")[0])
            if value and len(value.split()) <= 8:
                found["current_employer"] = Found(value, value, _clip(line, match.start(), match.end()))
        if "relevant_experience" not in found and (match := _RELEVANT.search(line)):
            parsed = _years(match.group(1), match.group(2))
            if parsed:
                found["relevant_experience"] = Found(parsed[0], parsed[1], _clip(line, match.start(), match.end()), parsed[2])
        if "education" not in found and _DEGREE.search(line) and len(line.split()) <= 30:
            value = _tidy(_EDUCATION_LABEL.sub("", line))
            found["education"] = Found(value, value if len(value) <= 140 else value[:139] + "…", _clip(line, 0, len(line)))

    role, company = _current_job(lines)
    if role and "current_designation" not in found:
        found["current_designation"] = role
    if company and "current_employer" not in found:
        found["current_employer"] = company

    if "current_designation" not in found:
        # The line under the name is usually the candidate's own headline.
        for line in lines[1:HEADLINE_LINES]:
            if _ROLE.search(line) and len(line.split()) <= 6 and not any(ch.isdigit() or ch in "@:|" for ch in line):
                found["current_designation"] = Found(line, line, line, "From the resume's headline, not a dated job entry.")
                break
    return found
