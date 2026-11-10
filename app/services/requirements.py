"""Read a job description into structured requirements a recruiter can check and edit.

Nothing here is applied automatically. Each value is a suggestion that carries the sentence it
came from and says whether the job description states it outright ("explicit") or only hints at
it ("suggested": worded as a preference, or just mentioned). The recruiter confirms or changes
every value before candidates are evaluated against it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.services.facts import MAX_NOTICE_DAYS, MAX_QUOTE_CHARS, MAX_YEARS, _money, _number
from app.services.locations import cities_in
from app.services.skills import Term, skills_in, terms_from_input

Basis = Literal["explicit", "suggested"]
MAX_OTHER = 8


@dataclass(frozen=True)
class Suggestion:
    """One value read from the job description."""

    value: float
    basis: Basis
    quote: str
    note: str | None = None


@dataclass(frozen=True)
class SkillSuggestion:
    name: str
    basis: Basis
    quote: str


@dataclass(frozen=True)
class LocationSuggestion:
    values: list[str]
    basis: Basis
    quote: str
    note: str | None = None


@dataclass(frozen=True)
class ParsedJob:
    required_skills: list[SkillSuggestion] = field(default_factory=list)
    preferred_skills: list[SkillSuggestion] = field(default_factory=list)
    min_experience_years: Suggestion | None = None
    max_experience_years: Suggestion | None = None
    max_notice_days: Suggestion | None = None
    max_ctc_lpa: Suggestion | None = None
    locations: LocationSuggestion | None = None
    other: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Requirements:
    """What the recruiter confirmed. Candidates are evaluated against exactly this, nothing inferred."""

    required_skills: list[Term] = field(default_factory=list)
    preferred_skills: list[Term] = field(default_factory=list)
    min_experience_years: float | None = None
    max_experience_years: float | None = None
    max_notice_days: float | None = None
    max_ctc_lpa: float | None = None
    locations: list[str] = field(default_factory=list)


def locations_from_input(raw: str) -> list[str]:
    """A recruiter's comma-separated places. Known cities get their usual name; others stay as typed."""
    places: list[str] = []
    for piece in re.split(r"[,;/\n]|\bor\b", raw):
        typed = " ".join(piece.split())
        if not typed:
            continue
        for place in cities_in(typed) or [typed]:
            if place.lower() not in {existing.lower() for existing in places}:
                places.append(place)
    return places


# Reading the job description -------------------------------------------------------------------------

_SOFT = re.compile(r"\b(?:prefer(?:red|ably|ence)?|ideal(?:ly)?|desirable|nice\s+to\s+have|good\s+to\s+have|"
                   r"a\s+plus|bonus|advantage|optional|approximately|approx\.?|around|roughly)\b|~", re.IGNORECASE)
_REQUIRED_WORDS = re.compile(r"\b(?:must|required?|mandatory|essential|strong|hands[- ]on|expert(?:ise)?|proficien\w+|"
                             r"need(?:s|ed)?|should\s+have)\b", re.IGNORECASE)
_REQUIRED_HEADING = re.compile(r"\b(?:requirements?|must[- ]haves?|what\s+we(?:'|’)?re\s+looking\s+for|what\s+you(?:'|’)?ll\s+need|"
                               r"what\s+you\s+need|qualifications?|required\s+skills|skills\s+required|key\s+skills|"
                               r"mandatory\s+skills|who\s+you\s+are)\b", re.IGNORECASE)
_PREFERRED_HEADING = re.compile(r"\b(?:nice\s+to\s+have|good\s+to\s+have|preferred|bonus|plus\s+points?|desirable)\b", re.IGNORECASE)

_YEARS_UNIT = r"(?:years?|yrs?)"
_EXPERIENCE_WORD = re.compile(r"\bexp(?:erience|erienced)?\b", re.IGNORECASE)
_RANGE_YEARS = re.compile(rf"(?<![\d.])(\d{{1,2}})\s*(?:-|–|to)\s*(\d{{1,2}})\s*\+?\s*{_YEARS_UNIT}\b", re.IGNORECASE)
_MIN_YEARS = re.compile(
    rf"(?:\b(?:min(?:imum)?\.?|at\s*least|over|more\s+than)\s*(?:of\s*)?(\d{{1,2}})\s*\+?\s*{_YEARS_UNIT}\b)"
    rf"|(?:(?<![\d.])(\d{{1,2}})\s*\+\s*{_YEARS_UNIT}\b)"
    rf"|(?:(?<![\d.])(\d{{1,2}})\s*{_YEARS_UNIT}\s*(?:and\s+above|or\s+more|minimum))",
    re.IGNORECASE,
)
_MAX_YEARS_ONLY = re.compile(rf"\b(?:up\s*to|max(?:imum)?\.?|not\s+more\s+than|below|under)\s*(\d{{1,2}})\s*{_YEARS_UNIT}\b", re.IGNORECASE)
_PLAIN_YEARS = re.compile(rf"(?<![\d.])(\d{{1,2}})\s*{_YEARS_UNIT}\b", re.IGNORECASE)

_NOTICE_SENTENCE = re.compile(r"\bnotice\b|\bjoin(?:er|ers|ing)?\b", re.IGNORECASE)
_NOTICE_DURATION = re.compile(r"(?<![\d.])(\d{1,3})\s*(?:(?:-|–|to)\s*(\d{1,3})\s*)?(days?|weeks?|months?)\b", re.IGNORECASE)
_IMMEDIATE = re.compile(r"\bimmediate(?:ly)?\b", re.IGNORECASE)

_PAY_SENTENCE = re.compile(r"\b(?:budget|ctc|salary|compensation|package|lpa)\b", re.IGNORECASE)
_PAY_AMOUNT = re.compile(
    r"(?:(?:rs\.?|inr|₹)\s*)?\d+(?:,\d{2,3})*(?:\.\d+)?\s*(?:(?:-|–|to)\s*\d+(?:\.\d+)?\s*)?(?:lpa|lakhs?|lacs?|crores?|cr\b|l\b)"
    r"|(?:rs\.?|inr|₹)\s*\d+(?:,\d{2,3})+",
    re.IGNORECASE,
)

_LOCATION_LABEL = re.compile(
    r"\b(?:(?:work|job|base|office)\s+)?locations?\s*[:\-–]\s*([^\n.;]+)|\bbased\s+(?:in|out\s+of)\s+([^\n.;]+)|"
    r"\boffice\s+(?:in|at)\s+([^\n.;]+)",
    re.IGNORECASE,
)
_REMOTE = re.compile(r"\b(?:remote|work\s+from\s+home|wfh)\b", re.IGNORECASE)

_OTHER_MARKERS = re.compile(
    r"\b(?:must|mandatory|required?|only|should\s+have|days?\s+a\s+week|work\s+from\s+office|on[- ]?site|hybrid|"
    r"shifts?|bond|relocat\w+|travel|degree|b\.?\s?tech|graduat\w+|certifi\w+|passport|visa)\b",
    re.IGNORECASE,
)
_WORK_MODE = re.compile(r"\b(?:days?\s+a\s+week|work\s+from\s+office|on[- ]?site|hybrid|shifts?)\b", re.IGNORECASE)


# A full stop ends a sentence, except after short forms such as "Rs.", "min." or "approx.".
_SENTENCE_END = re.compile(
    r"(?<=[.!?])(?<!\brs\.)(?<!\bno\.)(?<!\bmin\.)(?<!\bmax\.)(?<!\bexp\.)(?<!\byrs\.)(?<!\bapprox\.)\s+(?=[A-Z0-9])",
    re.IGNORECASE,
)


def _clip(text: str) -> str:
    text = text.strip(" -•*\t")
    return text if len(text) <= MAX_QUOTE_CHARS else text[: MAX_QUOTE_CHARS - 1].rstrip() + "…"


def _sentences(job_description: str) -> list[tuple[str, str]]:
    """(sentence, kind of section it sits in). Kind is "required", "preferred" or "other"."""
    result: list[tuple[str, str]] = []
    section = "other"
    for raw in job_description.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        bare = line.strip(" -•*:")
        is_heading = len(bare.split()) <= 6 and not line.rstrip().endswith(".") and not raw.lstrip().startswith(("-", "•", "*"))
        if is_heading and not any(ch.isdigit() for ch in bare):
            if _PREFERRED_HEADING.search(bare):
                section = "preferred"
            elif _REQUIRED_HEADING.search(bare):
                section = "required"
            elif ":" not in line[:-1]:  # "Location: Hyderabad" is a field, not a heading
                section = "other"
        for sentence in _SENTENCE_END.split(line):
            if sentence.strip(" -•*"):
                result.append((sentence.strip(), section))
    return result


def parse_job_description(job_description: str) -> ParsedJob:
    sentences = _sentences(job_description)
    notes: list[str] = []
    used: set[str] = set()  # sentences that produced a structured value

    required: dict[str, SkillSuggestion] = {}
    preferred: dict[str, SkillSuggestion] = {}
    mentioned: dict[str, SkillSuggestion] = {}
    for sentence, section in sentences:
        names = [term.name for term in skills_in(sentence)]
        if not names:
            continue
        if _SOFT.search(sentence) or (section == "preferred" and not _REQUIRED_WORDS.search(sentence)):
            bucket, basis = preferred, "explicit"
        elif _REQUIRED_WORDS.search(sentence) or section == "required":
            bucket, basis = required, "explicit"
        else:
            bucket, basis = mentioned, "suggested"
        for name in names:
            bucket.setdefault(name, SkillSuggestion(name, basis, _clip(sentence)))
    for name in required:
        preferred.pop(name, None)
        mentioned.pop(name, None)
    for name, suggestion in mentioned.items():
        preferred.setdefault(name, suggestion)

    minimum, maximum = _experience(sentences, notes, used)
    notice = _notice(sentences, notes, used)
    pay = _pay(sentences, notes, used)
    locations = _locations(job_description, sentences, notes, used)

    other: list[str] = []
    for sentence, _ in sentences:
        if not _OTHER_MARKERS.search(sentence):
            continue
        # Skip sentences already turned into a field, unless they also carry a working-pattern condition.
        if sentence in used and not _WORK_MODE.search(sentence):
            continue
        if skills_in(sentence) and not _WORK_MODE.search(sentence):
            continue
        text = _clip(sentence)
        if text not in other:
            other.append(text)

    return ParsedJob(
        required_skills=list(required.values()),
        preferred_skills=list(preferred.values()),
        min_experience_years=minimum,
        max_experience_years=maximum,
        max_notice_days=notice,
        max_ctc_lpa=pay,
        locations=locations,
        other=other[:MAX_OTHER],
        notes=notes,
    )


def _basis(sentence: str) -> Basis:
    return "suggested" if _SOFT.search(sentence) else "explicit"


def _experience(sentences, notes, used) -> tuple[Suggestion | None, Suggestion | None]:
    found: list[tuple[float | None, float | None, str]] = []
    for sentence, _ in sentences:
        if not _EXPERIENCE_WORD.search(sentence) or _NOTICE_SENTENCE.search(sentence):
            continue
        low = high = None
        if match := _RANGE_YEARS.search(sentence):
            low, high = float(match.group(1)), float(match.group(2))
        elif match := _MIN_YEARS.search(sentence):
            low = float(next(group for group in match.groups() if group))
        elif match := _MAX_YEARS_ONLY.search(sentence):
            high = float(match.group(1))
        elif match := _PLAIN_YEARS.search(sentence):
            low = float(match.group(1))
        if low is None and high is None:
            continue
        if any(value is not None and not 0 <= value <= MAX_YEARS for value in (low, high)) or (low and high and low > high):
            continue
        found.append((low, high, sentence))
    if not found:
        return None, None
    low, high, sentence = found[0]
    used.add(sentence)
    note = None
    others = [text for other_low, other_high, text in found[1:] if (other_low, other_high) != (low, high)]
    if others:
        note = "The job description gives other experience figures too. Check which one is the overall requirement."
        notes.append(f"More than one experience figure: also \"{_clip(others[0])}\".")
    basis = _basis(sentence)
    minimum = Suggestion(low, basis, _clip(sentence), note) if low is not None else None
    maximum = Suggestion(high, basis, _clip(sentence), note) if high is not None else None
    return minimum, maximum


def _notice(sentences, notes, used) -> Suggestion | None:
    for sentence, _ in sentences:
        if not _NOTICE_SENTENCE.search(sentence):
            continue
        hard: list[float] = []
        soft: list[float] = []
        for clause in re.split(r"[,;(]|\bbut\b", sentence):
            days: float | None = None
            if match := _NOTICE_DURATION.search(clause):
                amount = int(match.group(2) or match.group(1))
                unit = match.group(3).lower()
                days = float(amount * (30 if unit.startswith("m") else 7 if unit.startswith("w") else 1))
            elif _IMMEDIATE.search(clause):
                days = 0.0
            if days is None or days > MAX_NOTICE_DAYS:
                continue
            (soft if _SOFT.search(clause) else hard).append(days)
        if not hard and not soft:
            continue
        used.add(sentence)
        if hard:
            note = f"{_number(min(soft))} days or less is preferred." if soft and min(soft) < max(hard) else None
            return Suggestion(max(hard), "explicit", _clip(sentence), note)
        notes.append("The notice period is worded as a preference, not a limit.")
        return Suggestion(max(soft), "suggested", _clip(sentence), "Worded as a preference, so it isn't a hard limit.")
    return None


def _pay(sentences, notes, used) -> Suggestion | None:
    for sentence, _ in sentences:
        if not _PAY_SENTENCE.search(sentence):
            continue
        match = _PAY_AMOUNT.search(sentence)
        if not match:
            continue
        parsed = _money(sentence[match.start():])
        if not parsed or parsed[0] is None:
            continue
        used.add(sentence)
        value, display, _, low = parsed
        note = f"The job description gives {display}; the top of the range is used." if low is not None else None
        return Suggestion(value, _basis(sentence), _clip(sentence), note)
    return None


def _locations(job_description: str, sentences, notes, used) -> LocationSuggestion | None:
    for sentence, _ in sentences:
        match = _LOCATION_LABEL.search(sentence)
        if not match:
            continue
        stated = next(group for group in match.groups() if group)
        cities = cities_in(stated)
        if cities:
            used.add(sentence)
            note = "Remote or work from home is also mentioned." if _REMOTE.search(sentence) else None
            return LocationSuggestion(cities, "explicit", _clip(sentence), note)
        if _REMOTE.search(stated):
            used.add(sentence)
            notes.append("The job is described as remote, so no location limit is suggested.")
            return None
        typed = " ".join(stated.split(",")[0].split()[:3]).strip(" -")
        if typed:
            used.add(sentence)
            return LocationSuggestion([typed], "explicit", _clip(sentence), "Not a city on the built-in list, so it is matched as typed.")
    title = next((sentence for sentence, _ in sentences), "")
    cities = cities_in(title)
    if cities:
        return LocationSuggestion(cities, "suggested", _clip(title), "Found in the title only, not stated as a requirement.")
    if _REMOTE.search(job_description):
        notes.append("The job description mentions remote work, so no location limit is suggested.")
    return None


def confirmed(
    must_haves: str,
    preferred_skills: str | None,
    fallback_preferred: list[Term],
    min_experience_years: float | None,
    max_experience_years: float | None,
    max_notice_days: float | None,
    max_ctc_lpa: float | None,
    locations: str | None,
) -> Requirements:
    """Build the requirements to evaluate against from what the recruiter submitted."""
    required = terms_from_input(must_haves)
    names = {term.name.lower() for term in required}
    # None means the field wasn't sent at all, so fall back to the skills found in the job description.
    preferred = fallback_preferred if preferred_skills is None else terms_from_input(preferred_skills)
    return Requirements(
        required_skills=required,
        preferred_skills=[term for term in preferred if term.name.lower() not in names],
        min_experience_years=min_experience_years,
        max_experience_years=max_experience_years,
        max_notice_days=max_notice_days,
        max_ctc_lpa=max_ctc_lpa,
        locations=locations_from_input(locations or ""),
    )
