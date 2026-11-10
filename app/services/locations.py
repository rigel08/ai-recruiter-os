"""Recognise Indian cities under their different names, so "Bangalore" matches "Bengaluru".

This is a small, hand-kept list aimed at IT hiring. A place that isn't here is never guessed at:
callers treat it as "not recognised" and ask a person.
"""

from __future__ import annotations

import re

# Canonical name -> other names and well-known localities that mean the same city for hiring.
CITIES: dict[str, tuple[str, ...]] = {
    "Hyderabad": ("hyd", "secunderabad", "cyberabad", "gachibowli", "madhapur", "hitech city", "hitec city",
                  "kondapur", "kukatpally", "banjara hills", "jubilee hills", "begumpet", "ameerpet", "uppal",
                  "kokapet", "nizampet", "miyapur", "financial district"),
    "Bengaluru": ("bangalore", "blr", "whitefield", "electronic city", "koramangala", "marathahalli",
                  "hsr layout", "indiranagar"),
    "Chennai": ("madras", "omr", "guindy", "tambaram"),
    "Navi Mumbai": ("vashi", "airoli", "belapur"),
    "Mumbai": ("bombay", "andheri", "powai", "bkc", "lower parel"),
    "Thane": (),
    "Pune": ("poona", "hinjewadi", "hinjawadi", "kharadi", "magarpatta", "pimpri", "chinchwad"),
    "Greater Noida": (),
    "Noida": (),
    "Delhi": ("new delhi",),
    "Gurugram": ("gurgaon",),
    "Faridabad": (),
    "Ghaziabad": (),
    "Kolkata": ("calcutta", "salt lake"),
    "Ahmedabad": ("gandhinagar",),
    "Kochi": ("cochin", "ernakulam", "kakkanad"),
    "Thiruvananthapuram": ("trivandrum",),
    "Coimbatore": (),
    "Visakhapatnam": ("vizag", "vishakhapatnam"),
    "Vijayawada": (),
    "Mysuru": ("mysore",),
    "Mangaluru": ("mangalore",),
    "Chandigarh": ("mohali", "panchkula"),
    "Jaipur": (),
    "Indore": (),
    "Bhopal": (),
    "Nagpur": (),
    "Lucknow": (),
    "Bhubaneswar": (),
    "Surat": (),
    "Vadodara": ("baroda",),
    "Nashik": (),
    "Warangal": (),
    "Tirupati": (),
    "Guntur": (),
    "Madurai": (),
    "Patna": (),
    "Goa": ("panaji",),
}
# A region named in a job description stands for all of its cities.
REGIONS: dict[str, tuple[str, ...]] = {
    "delhi ncr": ("Delhi", "Gurugram", "Noida", "Greater Noida", "Faridabad", "Ghaziabad"),
    "ncr": ("Delhi", "Gurugram", "Noida", "Greater Noida", "Faridabad", "Ghaziabad"),
}

_OPEN_TO_ANYWHERE = re.compile(r"\b(?:anywhere|any\s+location|pan[- ]?india|open\s+to\s+relocat\w*|willing\s+to\s+relocat\w*)\b",
                               re.IGNORECASE)

# Longest names first, so "Navi Mumbai" is found before "Mumbai" and "Greater Noida" before "Noida".
_NAMES: list[tuple[str, tuple[str, ...]]] = sorted(
    [(name.lower(), (name,)) for name in CITIES]
    + [(alias, (name,)) for name, aliases in CITIES.items() for alias in aliases]
    + list(REGIONS.items()),
    key=lambda pair: -len(pair[0]),
)
_PATTERN = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(name) for name, _ in _NAMES) + r")(?![A-Za-z])", re.IGNORECASE)
_LOOKUP = dict(_NAMES)


def cities_in(text: str) -> list[str]:
    """Canonical names of the cities mentioned in the text, in the order they appear."""
    found: list[str] = []
    for match in _PATTERN.finditer(text):
        for city in _LOOKUP[match.group(1).lower()]:
            if city not in found:
                found.append(city)
    return found


def canonical_city(text: str) -> str | None:
    """The one city this text names, or None if it names none that are recognised."""
    cities = cities_in(text)
    return cities[0] if cities else None


def open_to_anywhere(text: str) -> bool:
    return bool(_OPEN_TO_ANYWHERE.search(text))
