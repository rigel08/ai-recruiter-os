"""Read a candidate's reply to the recruiter's questions, such as "NP 30 days, cctc 14, ectc 18, loc hyd".

People answer in shorthand on WhatsApp and email. Because the recruiter has just asked for these
exact details and reviews every value before using it, the reading here is looser than the resume
extractor's. Nothing read here is applied on its own, and each value keeps the words it came from.
"""

from __future__ import annotations

import re

from app.services.clarify import NUMBER_RANGES, display_for
from app.services.facts import ASK_FIELDS, extract_facts
from app.services.locations import cities_in

_NUM = r"(\d{1,3}(?:\.\d{1,2})?)"
_SEP = r"\s*(?:[:=\-]|is|of|-)?\s*"
_NOTICE = re.compile(rf"\b(?:np|notice(?:\s*period)?)\b{_SEP}{_NUM}\s*(d|days?|w|wks?|weeks?|m|mos?|months?)\b", re.IGNORECASE)
_NOTICE_NUMBER_FIRST = re.compile(rf"{_NUM}\s*(days?|weeks?|months?)\s*(?:np|notice)\b", re.IGNORECASE)
_IMMEDIATE = re.compile(r"\b(?:immediate(?:ly)?|can\s+join\s+(?:now|asap|right\s+away))\b", re.IGNORECASE)
_PAY_UNIT = r"\s*(?:(?:-|to)\s*(\d{1,3}(?:\.\d{1,2})?)\s*)?(lpa|lakhs?|lacs?|l)?\b"
_EXPECTED = re.compile(rf"\b(?:ectc|e\.ctc|exp(?:ected)?\.?\s*ctc|expected(?:\s+salary)?|expecting)\b{_SEP}{_NUM}{_PAY_UNIT}", re.IGNORECASE)
_CURRENT = re.compile(rf"\b(?:cctc|c\.ctc|current(?:\s*ctc|\s+salary)?|present(?:\s*ctc)?|ctc)\b{_SEP}{_NUM}{_PAY_UNIT}", re.IGNORECASE)
_EXPERIENCE = re.compile(
    rf"\b(?:total\s*)?exp(?:erience)?\b{_SEP}{_NUM}\s*\+?\s*(?:y|yrs?|years?)\b|{_NUM}\s*\+?\s*(?:yrs?|years?)\s*(?:of\s*)?(?:total\s*)?exp(?:erience)?\b",
    re.IGNORECASE,
)
_LOCATION_CUE = re.compile(r"\b(?:loc(?:ation)?|based|staying|living|residing|currently\s+in|i\s*(?:am|'m)\s+in|from)\b[^.\n;]{0,30}", re.IGNORECASE)
_PREFERRED_CUE = re.compile(r"\b(?:prefer(?:red)?|open\s+to|relocate\s+to|willing\s+to\s+move\s+to)\b[^.\n;]{0,40}", re.IGNORECASE)


def _days(amount: str, unit: str) -> float:
    unit = unit.lower()
    return float(amount) * (30 if unit.startswith("m") else 7 if unit.startswith("w") else 1)


def _in_range(field: str, value: float) -> bool:
    low, high = NUMBER_RANGES[field]
    return low <= value <= high


def read_reply(text: str) -> tuple[dict[str, dict], list[str]]:
    """(values found, tracker fields not mentioned). Each value has `value`, `display` and `quote`."""
    found: dict[str, dict] = {}

    def offer(field: str, value: float | str, quote: str) -> None:
        if field in found:
            return
        if field in NUMBER_RANGES and not _in_range(field, float(value)):
            return
        found[field] = {"value": value, "display": display_for(field, value), "quote": " ".join(quote.split())}

    # Anything written out properly ("Notice period: 30 days") is read by the resume rules first.
    for field, fact in extract_facts(text).items():
        if fact.value is not None and not fact.confirm:
            offer(field, fact.value, fact.quote)

    flat = " ".join(text.split())
    if match := _NOTICE.search(flat) or _NOTICE_NUMBER_FIRST.search(flat):
        offer("notice_period", _days(match.group(1), match.group(2)), match.group(0))
    elif match := _IMMEDIATE.search(flat):
        offer("notice_period", 0.0, match.group(0))

    # Expected first, then hide it, so "ectc 18" isn't also read as a current CTC.
    remaining = flat
    if match := _EXPECTED.search(flat):
        offer("expected_ctc", float(match.group(2) or match.group(1)), match.group(0))
        remaining = flat[: match.start()] + " " * len(match.group(0)) + flat[match.end():]
    if match := _CURRENT.search(remaining):
        offer("current_ctc", float(match.group(1)), match.group(0))

    if match := _EXPERIENCE.search(flat):
        offer("total_experience", float(match.group(1) or match.group(2)), match.group(0))

    preferred = _PREFERRED_CUE.search(flat)
    if preferred and cities_in(preferred.group(0)):
        offer("preferred_location", ", ".join(cities_in(preferred.group(0))), preferred.group(0))
    for match in _LOCATION_CUE.finditer(flat):
        if preferred and match.start() >= preferred.start() and match.end() <= preferred.end():
            continue
        cities = cities_in(match.group(0))
        if cities:
            offer("current_location", cities[0], match.group(0))
            break

    return found, [field for field in ASK_FIELDS if field not in found]
