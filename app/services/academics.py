"""Find a candidate's CGPA in resume text."""

from __future__ import annotations

import re

# Matches "CGPA", "C.G.P.A", "GPA" and "CPI", but not "SGPA" (a single semester).
_LABEL = r"(?:C\.?\s?G\.?\s?P\.?\s?A|G\.?\s?P\.?\s?A|CPI)"
_NUMBER = r"(\d{1,2}(?:\.\d{1,2})?)"
# An optional scale such as "/ 10", "/10.0" or "out of 10".
_SCALE = r"(?:\s*(?:/|out\s+of)\s*(\d{1,2})(?:\.0+)?(?!\d))?"

# "CGPA: 8.2", "CGPA 8.20 / 10", "C.G.P.A - 7.9", "GPA of 8.1/10"
_LABEL_FIRST = re.compile(rf"\b{_LABEL}\b\s*(?:[:\-–=]|of|is)?\s*{_NUMBER}{_SCALE}", re.IGNORECASE)
# "8.5 CGPA", "8.5/10 CGPA"
_NUMBER_FIRST = re.compile(rf"(?<![\d.]){_NUMBER}{_SCALE}\s*{_LABEL}\b", re.IGNORECASE)


def find_cgpa(text: str) -> float | None:
    """The first CGPA on a 10-point scale, or None if there isn't one.

    Resumes usually list the degree first, so the first CGPA is normally
    the degree's. Scores on other scales (such as 3.6/4) are ignored rather
    than converted, because there's no reliable conversion.
    """
    matches = sorted(
        [*_LABEL_FIRST.finditer(text), *_NUMBER_FIRST.finditer(text)],
        key=lambda match: match.start(),
    )
    for match in matches:
        value, scale = float(match.group(1)), match.group(2)
        if scale is not None and int(scale) != 10:
            continue
        if 0 < value <= 10:
            return round(value, 2)
    return None
