"""Pull the facts a recruiter's tracker needs out of resume text, each with the line it came from.

The rule throughout: a blank is better than a wrong value. A fact is returned only when the
text states it in a recognisable way, and it always carries the exact line as evidence.
Anything missing or unclear goes on the "ask on the call" list instead.

Nothing here reads age, gender, marital status or any other protected attribute.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# field key -> label a recruiter reads
FIELD_LABELS = {
    "phone": "Phone number",
    "total_experience": "Total experience",
    "notice_period": "Notice period",
    "current_ctc": "Current CTC",
    "expected_ctc": "Expected CTC",
    "current_location": "Current location",
    "preferred_location": "Preferred location",
}
FIELD_UNITS = {"total_experience": "years", "notice_period": "days", "current_ctc": "LPA", "expected_ctc": "LPA"}
# A missing preferred location isn't worth a question on every call.
ASK_FIELDS = ("phone", "total_experience", "notice_period", "current_ctc", "expected_ctc", "current_location")

MAX_QUOTE_CHARS = 180
# A bare "Location:" is trusted only this near the top; further down it's usually a past job's city.
HEADER_LINES = 12
# Where a resume's summary normally sits.
SUMMARY_LINES = 15
MAX_NOTICE_DAYS = 180
MAX_YEARS = 50
MIN_LPA, MAX_LPA = 0.5, 500


@dataclass(frozen=True)
class Found:
    value: float | str | None  # normalised number or text; None when the resume says something that isn't a value
    display: str
    quote: str
    note: str | None = None
    confirm: bool = False  # the resume is unclear here, so the recruiter should check on the call


# Shared pieces -------------------------------------------------------------------------------------

# Where a field can start: the beginning of a line, or after a separator in "A: 1 | B: 2" rows.
_FIELD_START = r"(?:^|[|,;•·/(]\s*)"
_SEP = r"\s*(?:[:\-–—=]|\bis\b|\bof\b)?\s*"
_HARD_SEP = r"\s*[:\-–—=]\s*"


def _lines(text: str) -> list[str]:
    return [line for line in (" ".join(raw.split()) for raw in text.splitlines()) if line]


def _units(lines: list[str]) -> list[tuple[int, str]]:
    """Each line, plus label lines joined to the value on the next line.

    Tables in PDFs often come out as "Notice Period" on one line and "30 Days" on the next.
    Joining is limited to short pairs so a section heading isn't glued to a sentence.
    """
    units: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        units.append((index, line))
        if index + 1 < len(lines):
            following = lines[index + 1]
            label_only = len(line.split()) <= 3 and not any(ch.isdigit() for ch in line)
            if (line.endswith((":", "-", "–")) or label_only) and len(following.split()) <= 4:
                units.append((index, f"{line} {following}"))
    return units


def _clip(line: str, start: int, end: int) -> str:
    if len(line) <= MAX_QUOTE_CHARS:
        return line
    half = (MAX_QUOTE_CHARS - (end - start)) // 2
    left = max(0, start - max(half, 0))
    right = min(len(line), left + MAX_QUOTE_CHARS)
    return ("…" if left else "") + line[left:right].strip() + ("…" if right < len(line) else "")


def _number(value: float) -> str:
    return f"{round(value, 2):g}"


def _with_conflict(first: Found, others: list[Found]) -> Found:
    """Keep the first value, but say so when the resume also states a different one."""
    for other in others:
        if other.value is not None and first.value is not None and other.value != first.value:
            note = f"The resume also says {other.display}. Confirm on the call."
            return Found(first.value, first.display, first.quote, f"{first.note} {note}" if first.note else note, True)
    return first


# Phone ---------------------------------------------------------------------------------------------

_PHONE = re.compile(r"(?<![\d.])(?:\(?\+?91\)?[\s.-]{0,2}|0)?([6-9]\d(?:[\s.-]?\d){8})(?!\d)")


_LINK_OR_EMAIL = re.compile(r"https?:|www\.|\.(?:com|in|org|io|net|me)\b|@", re.IGNORECASE)


def _phone(lines: list[str]) -> Found | None:
    for line in lines:
        for match in _PHONE.finditer(line):
            raw = match.group(1)
            if sum(1 for ch in raw if not ch.isdigit()) > 3:
                continue
            token_start = line.rfind(" ", 0, match.start(1)) + 1
            token_end = line.find(" ", match.end(1))
            if _LINK_OR_EMAIL.search(line[token_start: token_end if token_end != -1 else len(line)]):
                continue
            digits = re.sub(r"\D", "", raw)
            if len(set(digits)) == 1:  # 9999999999 is a placeholder, not a number
                continue
            shown = f"+91 {digits[:5]} {digits[5:]}"
            return Found(shown, shown, _clip(line, match.start(), match.end()))
    return None


# Total experience ----------------------------------------------------------------------------------

_YEARS = r"(\d{1,2}(?:\.\d{1,2})?)\s*\+?\s*(?:years?|yrs?)\b(?:\s*(?:and|&|,)?\s*(\d{1,2})\s*(?:months?|mos?)\b)?"
# "Total experience: 6.5 years", "Overall exp - 4 yrs 3 months"
_EXPERIENCE_QUALIFIED = re.compile(
    rf"\b(?:total|overall)\s+(?:(?:work|professional|it|industry)\s+)?exp(?:erience)?\b\.?{_SEP}(?:around|about|approx\.?|over|nearly)?\s*{_YEARS}",
    re.IGNORECASE,
)
# A bare "Experience" needs a separator, so a section heading followed by a job line doesn't count.
_EXPERIENCE_BARE = re.compile(rf"{_FIELD_START}(?:work\s+)?exp(?:erience)?\b\.?{_HARD_SEP}{_YEARS}", re.IGNORECASE)
_EXPERIENCE_FRESHER = re.compile(rf"{_FIELD_START}(?:total\s+|work\s+)?exp(?:erience)?\b\.?{_HARD_SEP}(fresher|nil|none)\b", re.IGNORECASE)
# "5+ years of experience", "7 yrs of IT experience"
_EXPERIENCE_SENTENCE = re.compile(
    rf"(?<![\d.]){_YEARS}\s*(?:of\s+)?(?:(?:total|overall|professional|work|working|industry|it|hands[- ]on|rich|extensive|solid)\s+){{0,2}}exp(?:erience)?\b",
    re.IGNORECASE,
)
_NOT_THE_CANDIDATE = re.compile(r"\b(?:required|requires?|minimum|at least|must have|looking for)\b", re.IGNORECASE)
_SOMEONE_ELSE = re.compile(r"\b(?:company|firm|organi[sz]ation|client|vendor|provider)\b", re.IGNORECASE)
# "2 years of experience at TCS" is one employer, not the total.
_AT_AN_EMPLOYER = re.compile(r"\s+at\s+[A-Z]")


def _years(whole: str, months: str | None) -> tuple[float, str] | None:
    if months is not None:
        value = float(whole.split(".")[0]) + int(months) / 12
        shown = f"{whole.split('.')[0]} years {int(months)} months"
    elif re.fullmatch(r"\d{1,2}\.1[01]", whole):
        # Indian resumes write 5 years 10 months as "5.10 years".
        years, extra = whole.split(".")
        value = int(years) + int(extra) / 12
        shown = f"{years} years {extra} months"
    else:
        value = float(whole)
        shown = f"{_number(value)} years"
    if not 0 < value <= MAX_YEARS:
        return None
    return round(value, 2), shown


def _experience(lines: list[str]) -> Found | None:
    labelled: list[Found] = []
    stated: list[tuple[int, Found]] = []
    for _, unit in _units(lines):
        match = _EXPERIENCE_QUALIFIED.search(unit) or _EXPERIENCE_BARE.search(unit)
        if match:
            parsed = _years(match.group(1), match.group(2))
            if parsed:
                labelled.append(Found(parsed[0], parsed[1], _clip(unit, match.start(), match.end())))
            continue
        fresher = _EXPERIENCE_FRESHER.search(unit)
        if fresher:
            labelled.append(Found(0.0, "Fresher", _clip(unit, fresher.start(), fresher.end())))
    if labelled:
        return _with_conflict(labelled[0], labelled[1:])

    for index, line in enumerate(lines):
        if _NOT_THE_CANDIDATE.search(line):
            continue
        for match in _EXPERIENCE_SENTENCE.finditer(line):
            # "a firm with 25 years of experience" describes an employer, not the candidate.
            if _SOMEONE_ELSE.search(line[max(0, match.start() - 40): match.start()]):
                continue
            if _AT_AN_EMPLOYER.match(line[match.end():]):
                continue
            parsed = _years(match.group(1), match.group(2))
            if parsed:
                stated.append((index, Found(parsed[0], parsed[1], _clip(line, match.start(), match.end()),
                                            "Stated by the candidate, not worked out from job dates.")))
    if not stated:
        return None
    # The summary at the top states the total; figures further down are usually per skill.
    # "8 years of experience ... 3 years of experience in AWS": the largest figure is the total.
    near_top = [found for index, found in stated if index < SUMMARY_LINES]
    pool = near_top or [found for _, found in stated]
    best = max(pool, key=lambda found: found.value)
    others = sorted({found.display for found in pool if found.value != best.value})
    if others:
        # "4 years of experience in Node.js, 2 years in Java": these may be per skill, not a total.
        note = f"The resume also mentions {', '.join(others)}, so this may not be the total. Confirm on the call."
        return Found(best.value, best.display, best.quote, note, True)
    return best


# Notice period -------------------------------------------------------------------------------------

_DURATION = r"(\d{1,3})\s*(?:(?:-|–|to)\s*(\d{1,3})\s*)?(days?|weeks?|wks?|months?|mos?|mths?)\b"
_IMMEDIATE = r"(?:immediate(?:ly)?(?:\s+joiner)?|available\s+immediately)"
_NOTICE_LABEL = r"(?:\bnotice(?:\s*period)?\b|(?-i:\bN\.?P\b\.?(?=\s*[:\-–=])))"
_NOTICE_LABELLED = re.compile(rf"{_NOTICE_LABEL}{_SEP}(?:(?:{_DURATION})|({_IMMEDIATE})\b|(serving))", re.IGNORECASE)
# "15 days notice reminders" is about something else: "notice" must end the phrase or be "notice period".
_NOTICE_NUMBER_FIRST = re.compile(
    rf"(?<![\d.]){_DURATION}['’]?\s*(?:of\s+)?notice(?:\s*period\b|\s*(?=$|[|,;.)]))", re.IGNORECASE
)
_IMMEDIATE_UP_TO = re.compile(r"\s*(?:/|-|–|to|or)\s*(\d{1,3})\s*(days?|weeks?|wks?|months?|mos?|mths?)\b", re.IGNORECASE)
_NOTICE_CAN_JOIN = re.compile(
    rf"\b(?:can|able\s+to|available\s+to|ready\s+to)\s+join\s+(?:(immediately)|(?:in|within)\s+{_DURATION})", re.IGNORECASE
)
_NOTICE_IMMEDIATE_JOINER = re.compile(r"\bimmediate\s+joiner\b", re.IGNORECASE)
_NOTICE_SERVING = re.compile(r"\bserving\s+(?:my\s+|the\s+)?notice\b", re.IGNORECASE)
_LAST_DAY = re.compile(
    r"\b(?:lwd|last\s+working\s+da(?:y|te))\b\s*(?:[:\-–]|is|on)?\s*(?:is\s+|on\s+)?"
    r"(\d{1,2}(?:st|nd|rd|th)?[\s\-/.]+[A-Za-z0-9]{2,9}(?:[\s\-/.,]+\d{2,4})?)",
    re.IGNORECASE,
)
_NEGOTIABLE = re.compile(r"\b(?:negotiable|buy[- ]?out|can be reduced|early release)\b", re.IGNORECASE)


def _days(low: str, high: str | None, unit: str) -> tuple[float, str, str | None] | None:
    scale = 30 if unit.lower().startswith("m") else 7 if unit.lower().startswith("w") else 1
    upper = int(high) if high else int(low)
    days = upper * scale
    if not 0 < days <= MAX_NOTICE_DAYS:
        return None
    word = "month" if scale == 30 else "week"
    shown = f"{days} days" if scale == 1 else f"{days} days ({upper} {word}{'' if upper == 1 else 's'})"
    return float(days), shown, ("A range was given; the longer end is shown." if high else None)


def _notice_from(unit: str) -> Found | None:
    match = _NOTICE_LABELLED.search(unit)
    if match:
        low, high, duration_unit, immediate, serving = match.groups()
        if low:
            parsed = _days(low, high, duration_unit)
            if parsed is None:
                return None
            notes = [parsed[2]] if parsed[2] else []
            # Only the words straight after the value, up to the next field on the line.
            if _NEGOTIABLE.search(re.split(r"[|;]", unit[match.end():])[0][:60]):
                notes.append("The resume says this can be shortened.")
            return Found(parsed[0], parsed[1], _clip(unit, match.start(), match.end()), " ".join(notes) or None)
        if immediate:
            up_to = _IMMEDIATE_UP_TO.match(unit[match.end():])
            parsed = _days(up_to.group(1), None, up_to.group(2)) if up_to else None
            if parsed:
                return Found(parsed[0], parsed[1], _clip(unit, match.start(), match.end() + up_to.end()),
                             "The resume says immediate to this long; the longer end is shown.")
            return Found(0.0, "Immediate", _clip(unit, match.start(), match.end()))
        if serving:
            return _serving(unit, match)

    match = _NOTICE_NUMBER_FIRST.search(unit)
    if match:
        parsed = _days(match.group(1), match.group(2), match.group(3))
        if parsed:
            return Found(parsed[0], parsed[1], _clip(unit, match.start(), match.end()), parsed[2])

    match = _NOTICE_CAN_JOIN.search(unit)
    if match:
        if match.group(1):
            return Found(0.0, "Immediate", _clip(unit, match.start(), match.end()))
        parsed = _days(match.group(2), match.group(3), match.group(4))
        if parsed:
            return Found(parsed[0], parsed[1], _clip(unit, match.start(), match.end()), parsed[2])

    match = _NOTICE_IMMEDIATE_JOINER.search(unit)
    if match:
        return Found(0.0, "Immediate", _clip(unit, match.start(), match.end()))

    match = _NOTICE_SERVING.search(unit)
    if match:
        return _serving(unit, match)
    return None


def _serving(unit: str, match: re.Match[str]) -> Found:
    last_day = _LAST_DAY.search(unit)
    note = f"Last working day stated: {last_day.group(1).strip(' .,')}." if last_day else "No last working day stated."
    return Found(None, "Serving notice", _clip(unit, match.start(), match.end()), note)


def _notice(lines: list[str]) -> Found | None:
    found = [fact for _, unit in _units(lines) if (fact := _notice_from(unit))]
    if not found:
        return None
    with_value = [fact for fact in found if fact.value is not None]
    first = with_value[0] if with_value else found[0]
    return _with_conflict(first, with_value[1:])


# CTC -----------------------------------------------------------------------------------------------

_AMOUNT = re.compile(
    r"(?:(?:rs\.?|inr|₹)\s*)?"
    r"(\d+(?:,\d{2,3})*(?:\.\d+)?)"
    r"\s*(?:(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*)?"
    r"(lpa|lakhs?|lacs?|lac|crores?|cr|l|k)?(?![A-Za-z])"
    r"(\s*(?:(?:/|per|p\.?)\s*(?:month|mo\b|m\b)|p\.?m\b\.?|monthly))?",
    re.IGNORECASE,
)
_NOT_RUPEES = re.compile(r"^\s*(?:\$|usd|us\$|eur|€|gbp|£|aed|sgd|cad|aud)", re.IGNORECASE)
_CTC_WORDS = re.compile(
    r"^\s*(negotiable|open|as\s+per\s+(?:company|industry|market)\s+(?:norms?|standards?)|"
    r"\d{1,3}\s*%\s*(?:hike|increment|increase|raise)(?:\s+on\s+current(?:\s+ctc)?)?)",
    re.IGNORECASE,
)
_PAY = r"(?:annual\s+)?(?:ctc|salary|package|compensation)"
_EXPECTED_LABEL = re.compile(
    rf"(?:\b(?:expected|exp\.?|desired)\s*{_PAY}\b|\bectc\b|\be\.\s?ctc\b|\bsalary\s+expectations?\b){_SEP}", re.IGNORECASE
)
_CURRENT_LABEL = re.compile(
    rf"(?:\b(?:current|present|last\s+drawn|existing)\s*{_PAY}\b|\bcctc\b|\bc\.\s?ctc\b){_SEP}", re.IGNORECASE
)
# A bare "CTC" could be anything ("negotiated CTC of 12 LPA for candidates"), so it must start a field.
_BARE_CTC_LABEL = re.compile(rf"{_FIELD_START}(?:annual\s+)?ctc{_HARD_SEP}", re.IGNORECASE)
# "Current / Expected CTC: 8 / 12 LPA"
_PAIR = re.compile(
    rf"\bcurrent\s*(?:ctc)?\s*/\s*expected\s*ctc\b{_SEP}(\d+(?:\.\d+)?)\s*(?:lpa|l|lakhs?)?\s*/\s*(\d+(?:\.\d+)?)\s*(lpa|lakhs?|lacs?|l)\b",
    re.IGNORECASE,
)


def _money(after: str) -> tuple[float | None, str, str | None] | None:
    """Read an amount from the text straight after a pay label. Returns (LPA, display, note)."""
    words = _CTC_WORDS.match(after)
    if words:
        text = " ".join(words.group(1).split())
        return None, text[0].upper() + text[1:], "Not a figure."
    if _NOT_RUPEES.match(after):
        return None, after.split("|")[0].strip(" .,;")[:30], "Not in rupees, so it isn't converted."
    match = _AMOUNT.match(after)
    if not match:
        return None
    low_text, high_text, unit, monthly = match.groups()
    low = float(low_text.replace(",", ""))
    high = float(high_text) if high_text else None
    unit = (unit or "").lower()
    notes = []

    def to_lpa(amount: float) -> float | None:
        if unit in ("cr", "crore", "crores"):
            return amount * 100
        if unit == "k":
            if monthly:
                notes.append("A monthly figure, multiplied by 12.")
                return amount * 12 / 100
            return amount / 100
        if unit:  # lpa, lakh, lac, l
            return amount
        if monthly and 5_000 <= amount <= 2_000_000:
            notes.append("A monthly figure, multiplied by 12.")
            return amount * 12 / 100_000
        if amount >= 100_000:
            return amount / 100_000
        if amount < 100 and not monthly:
            notes.append("No unit given; read as lakhs a year.")
            return amount
        return None

    value = to_lpa(low)
    if value is None or not MIN_LPA <= value <= MAX_LPA:
        return None
    shown = f"{_number(value)} LPA"
    if high is not None:
        upper = to_lpa(high)
        if upper is not None and value < upper <= MAX_LPA:
            shown = f"{_number(value)}–{_number(upper)} LPA"
            value = upper
            notes.append("A range was given; the higher end is used.")
    return round(value, 2), shown, " ".join(dict.fromkeys(notes)) or None


def _ctc(lines: list[str]) -> tuple[Found | None, Found | None]:
    current: list[Found] = []
    expected: list[Found] = []
    for _, unit in _units(lines):
        pair = _PAIR.search(unit)
        if pair:
            quote = _clip(unit, pair.start(), pair.end())
            current.append(Found(float(pair.group(1)), f"{_number(float(pair.group(1)))} LPA", quote))
            expected.append(Found(float(pair.group(2)), f"{_number(float(pair.group(2)))} LPA", quote))
            continue
        for pattern, bucket in ((_EXPECTED_LABEL, expected), (_CURRENT_LABEL, current), (_BARE_CTC_LABEL, current)):
            for match in pattern.finditer(unit):
                parsed = _money(unit[match.end():])
                if parsed:
                    bucket.append(Found(parsed[0], parsed[1], _clip(unit, match.start(), match.end() + 30), parsed[2]))

    def pick(found: list[Found]) -> Found | None:
        if not found:
            return None
        with_value = [fact for fact in found if fact.value is not None]
        return _with_conflict(with_value[0], with_value[1:]) if with_value else found[0]

    return pick(current), pick(expected)


# Location ------------------------------------------------------------------------------------------

_PLACE = r"([A-Za-z][A-Za-z .&'-]{1,40})"
_CURRENT_LOCATION = re.compile(
    rf"\b(?:current|present|base)\s+(?:work\s+)?location\b{_SEP}{_PLACE}|"
    rf"\b(?:currently|presently)\s+(?:based|located|residing|living|working)\s+(?:in|at|out\s+of)\s+{_PLACE}",
    re.IGNORECASE,
)
_BARE_LOCATION = re.compile(rf"{_FIELD_START}(?:location|city){_HARD_SEP}{_PLACE}", re.IGNORECASE)
_PREFERRED_LOCATION = re.compile(
    rf"\bpreferred\s+(?:work\s+|job\s+)?locations?\b{_SEP}([A-Za-z][A-Za-z .&'/,-]{{1,80}})", re.IGNORECASE
)
_PLACE_STOP = re.compile(r"\s+(?:and|with|since|from|for|but|where|having|working|at|as)\b.*$", re.IGNORECASE)
_NOT_A_PLACE = {"yes", "no", "na", "n/a", "any", "open", "flexible", "remote", "india", "onsite", "hybrid"}


def _place(raw: str) -> str | None:
    text = re.split(r"\s[-–]\s", raw)[0]  # "Hyderabad - Notice period ..." on one line
    text = _PLACE_STOP.sub("", text).strip(" .,-&'")
    if not text or len(text.split()) > 4 or text.lower() in _NOT_A_PLACE:
        return None
    return text


def _locations(lines: list[str]) -> tuple[Found | None, Found | None]:
    current: Found | None = None
    preferred: Found | None = None
    for index, unit in _units(lines):
        if preferred is None:
            match = _PREFERRED_LOCATION.search(unit)
            if match:
                places = [p.strip(" .-") for p in re.split(r"[/,]|\bor\b|\band\b", match.group(1)) if p.strip(" .-")]
                places = [p for p in places if len(p.split()) <= 4][:6]
                if places:
                    shown = ", ".join(places)
                    preferred = Found(shown, shown, _clip(unit, match.start(), match.end()))
        if current is None:
            # Hide "Preferred location: X" first, so its "location: X" isn't read as the current one.
            searchable = _PREFERRED_LOCATION.sub(lambda m: " " * len(m.group(0)), unit)
            match = _CURRENT_LOCATION.search(searchable)
            if not match and index < HEADER_LINES:
                match = _BARE_LOCATION.search(searchable)
            if match:
                place = _place(next(group for group in match.groups() if group))
                if place:
                    current = Found(place, place, _clip(unit, match.start(), match.end()))
    return current, preferred


# Public API ----------------------------------------------------------------------------------------

def extract_facts(text: str) -> dict[str, Found]:
    """The facts stated in the text, keyed by field. Fields that aren't stated are simply absent."""
    lines = _lines(text)
    current_ctc, expected_ctc = _ctc(lines)
    current_location, preferred_location = _locations(lines)
    found = {
        "phone": _phone(lines),
        "total_experience": _experience(lines),
        "notice_period": _notice(lines),
        "current_ctc": current_ctc,
        "expected_ctc": expected_ctc,
        "current_location": current_location,
        "preferred_location": preferred_location,
    }
    return {field: fact for field, fact in found.items() if fact is not None}


def questions_to_ask(facts: dict[str, Found]) -> list[str]:
    """What the recruiter still has to find out on the call, in tracker order."""
    ask = []
    for field in ASK_FIELDS:
        label = FIELD_LABELS[field]
        fact = facts.get(field)
        if fact is None:
            ask.append(f"{label}: not on the resume")
        elif fact.value is None:
            ask.append(f"{label}: resume says \"{fact.display}\"")
        elif fact.confirm:
            ask.append(f"{label}: more than one figure on the resume")
    return ask
