"""Fact extraction: what's taken from a resume, the evidence kept with it, and what's left to ask."""

import pytest

from app.services.facts import ASK_FIELDS, MAX_QUOTE_CHARS, extract_facts, questions_to_ask

RESUME = """Ravi Teja Kolluri
Senior SAP FICO Consultant
ravi.teja@example.com | +91 90000 00012 | Location: Hyderabad, Telangana
Summary: 7.5 years of experience in SAP FICO across S/4HANA implementations.
Current CTC: 14.5 LPA | Expected CTC: 18-20 LPA | Notice Period: 60 days (negotiable)
Preferred Location: Hyderabad / Bengaluru
"""


def value(text, field):
    fact = extract_facts(text).get(field)
    return None if fact is None else fact.value


def test_a_full_resume_gives_every_field():
    facts = extract_facts(RESUME)
    assert {field: fact.value for field, fact in facts.items()} == {
        "phone": "+91 90000 00012",
        "total_experience": 7.5,
        "notice_period": 60.0,
        "current_ctc": 14.5,
        "expected_ctc": 20.0,
        "current_location": "Hyderabad",
        "preferred_location": "Hyderabad, Bengaluru",
    }
    assert questions_to_ask(facts) == []


def test_every_quote_is_a_line_from_the_resume():
    lines = [" ".join(line.split()) for line in RESUME.splitlines()]
    for fact in extract_facts(RESUME).values():
        assert fact.quote in lines


def test_long_lines_are_clipped_around_the_value():
    line = "Worked on many things. " * 12 + "Notice Period: 45 days. " + "And more besides. " * 12
    fact = extract_facts(line)["notice_period"]
    assert "Notice Period: 45 days" in fact.quote
    assert len(fact.quote) <= MAX_QUOTE_CHARS + 2  # plus the two ellipses


def test_nothing_stated_means_nothing_found_and_everything_asked():
    text = "Arjun Mehta\nPython developer building REST APIs with Django.\narjun@example.com"
    assert extract_facts(text) == {}
    assert len(questions_to_ask({})) == len(ASK_FIELDS)
    assert questions_to_ask({})[0] == "Phone number: not on the resume"


@pytest.mark.parametrize("text, days", [
    ("Notice Period: 30 Days", 30),
    ("NP: 2 months", 60),
    ("Notice period - Immediate", 0),
    ("Immediate joiner", 0),
    ("Can join in 3 weeks", 21),
    ("Notice Period:\n15 Days", 15),
    ("np: 30 days", None),             # lowercase "np" could be anything
    ("Notice period: 400 days", None),  # not believable, so left blank
])
def test_notice_period(text, days):
    assert value(text, "notice_period") == days


@pytest.mark.parametrize("text, lpa", [
    ("Current CTC: 8 LPA", 8),
    ("CCTC - 8.5 lakhs", 8.5),
    ("Current CTC: 12,00,000", 12),
    ("Current salary: 50k per month", 6),
    ("Last drawn salary: 7 LPA", 7),
    ("Current CTC: $90,000", None),      # not rupees: shown, not converted
    ("Current CTC: 450", None),          # no believable unit
    ("Current CTC: 9000 LPA", None),     # out of range
])
def test_current_ctc(text, lpa):
    assert value(text, "current_ctc") == lpa


def test_words_instead_of_a_figure_are_kept_but_still_asked():
    facts = extract_facts("Expected CTC: Negotiable\nNotice period: serving, LWD 30 Nov 2026")
    assert (facts["expected_ctc"].value, facts["expected_ctc"].display) == (None, "Negotiable")
    assert (facts["notice_period"].value, facts["notice_period"].display) == (None, "Serving notice")
    assert "30 Nov 2026" in facts["notice_period"].note
    ask = questions_to_ask(facts)
    assert 'Expected CTC: resume says "Negotiable"' in ask
    assert 'Notice period: resume says "Serving notice"' in ask


def test_two_different_values_keep_the_first_and_ask():
    facts = extract_facts("Notice Period: 60 days\nNotice Period: 45 days after appraisal")
    fact = facts["notice_period"]
    assert (fact.value, fact.confirm) == (60.0, True)
    assert "45 days" in fact.note
    assert "Notice period: more than one figure on the resume" in questions_to_ask(facts)


def test_the_same_value_twice_is_not_a_conflict():
    fact = extract_facts("Notice Period: 30 days\nNP: 1 month")["notice_period"]
    assert (fact.value, fact.confirm) == (30.0, False)


def test_a_labelled_total_beats_figures_in_sentences():
    text = "9 years of experience in testing.\nTotal Experience: 6 Years 3 Months"
    fact = extract_facts(text)["total_experience"]
    assert (fact.value, fact.display, fact.confirm) == (6.25, "6 years 3 months", False)


def test_per_skill_figures_are_not_added_up_or_picked_as_a_total():
    facts = extract_facts("4 years of experience in Node.js and React, 2 years of experience in Java")
    fact = facts["total_experience"]
    assert fact.value is None and "per_skill" in fact.tags
    assert fact.display == "Per-skill figures only (4 years, 2 years)"
    assert any(item.startswith("Total experience: resume says") for item in questions_to_ask(facts))


def test_a_stated_total_wins_over_per_skill_figures():
    fact = extract_facts("8 years of total experience. 3 years of experience in AWS.")["total_experience"]
    assert (fact.value, fact.confirm) == (8.0, False)


def test_one_figure_for_one_area_is_kept_with_a_caution():
    fact = extract_facts("Lead Engineer with 9 years of experience in Java backend systems.")["total_experience"]
    assert fact.value == 9.0 and "total may be higher" in fact.note


def test_five_point_ten_years_means_five_years_ten_months():
    fact = extract_facts("Total experience: 5.10 years")["total_experience"]
    assert (fact.value, fact.display) == (5.83, "5 years 10 months")
    # The value isn't literally on the resume, so the reading is spelled out.
    assert fact.note == 'Read "5.10 years" as 5 years 10 months.'
    assert extract_facts("Total experience: 5.5 years")["total_experience"].note is None


def test_bare_location_is_trusted_only_near_the_top():
    assert value("Asha Rao\nLocation: Pune", "current_location") == "Pune"
    deep = "\n".join(f"Line {n} of the work history" for n in range(15)) + "\nLocation: Chennai"
    assert value(deep, "current_location") is None
    assert value(deep + "\nCurrent Location: Mumbai", "current_location") == "Mumbai"


def test_preferred_location_is_not_read_as_current():
    facts = extract_facts("Preferred Location: Bengaluru")
    assert "current_location" not in facts
    assert facts["preferred_location"].value == "Bengaluru"


@pytest.mark.parametrize("text, phone", [
    ("+91 98450 12345", "+91 98450 12345"),
    ("Ph: 98450-12345", "+91 98450 12345"),
    ("919845012345", "+91 98450 12345"),
    ("Roll no 2019845012", None),
    ("github.com/user9845012345", None),
])
def test_phone(text, phone):
    assert value(text, "phone") == phone


def test_protected_details_are_never_extracted():
    text = "DOB: 12-08-1994 | Gender: Female | Marital Status: Married | Religion: Hindu | Father's name: K Rao"
    assert extract_facts(text) == {}


# ---------- M2 regression tests for M1 issues ----------

WORK_HISTORY = "\n".join(f"Line {n} of the work history" for n in range(15))


def test_bare_location_lower_down_counts_inside_a_personal_details_block():
    text = WORK_HISTORY + "\nCCTC: 14 LPA, ECTC: 18-20 LPA\nLocation: Hyderabad"
    assert value(text, "current_location") == "Hyderabad"
    two_lines_away = WORK_HISTORY + "\nMobile: 9845012345\nLanguages known: English, Telugu\nCity: Pune"
    assert value(two_lines_away, "current_location") == "Pune"


def test_bare_location_beside_a_past_job_is_still_ignored():
    text = WORK_HISTORY + "\nTech Lead, Finserve Ltd, 2021 to present\nLocation: Chennai\nBuilt settlement services."
    assert value(text, "current_location") is None


@pytest.mark.parametrize("text", [
    "Currently serving notice period.",
    "Serving notice period, last working day is 28th November 2026",
    "Notice period: serving, LWD 30 Nov 2026",
])
def test_serving_notice_never_becomes_a_number_of_days(text):
    fact = extract_facts(text)["notice_period"]
    assert fact.value is None and fact.low is None
    assert fact.display == "Serving notice" and "serving" in fact.tags


def test_ranges_keep_both_ends():
    facts = extract_facts("Expected CTC: 18-20 LPA\nNotice period: 30-45 days")
    assert (facts["expected_ctc"].low, facts["expected_ctc"].value) == (18.0, 20.0)
    assert (facts["notice_period"].low, facts["notice_period"].value) == (30.0, 45.0)
    assert extract_facts("Expected CTC: 20 LPA")["expected_ctc"].low is None


def test_negotiable_notice_is_tagged_only_for_the_notice_field():
    assert "negotiable" in extract_facts("Notice Period: 90 Days (negotiable)")["notice_period"].tags
    row = "Expected CTC: Negotiable | Notice Period: 30 days"
    assert extract_facts(row)["notice_period"].tags == ()
