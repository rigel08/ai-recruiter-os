"""Evaluating a candidate against confirmed requirements: three separate dimensions, no auto-rejection."""

import pytest

from app.services.evaluation import (
    check_ctc, check_experience, check_location, check_notice, evaluate, review_order,
)
from app.services.facts import extract_facts
from app.services.requirements import Requirements, locations_from_input
from app.services.skills import terms_from_input


def fact(text, field):
    return extract_facts(text).get(field)


def requirements(**kwargs):
    kwargs["required_skills"] = terms_from_input(kwargs.pop("required", "Java, Spring Boot, SQL"))
    kwargs["preferred_skills"] = terms_from_input(kwargs.pop("preferred", "Docker, AWS"))
    kwargs["locations"] = locations_from_input(kwargs.pop("locations", ""))
    return Requirements(**kwargs)


CLIENT = dict(min_experience_years=5, max_experience_years=9, max_notice_days=60, max_ctc_lpa=20, locations="Hyderabad")
STRONG = "Skills: Java, Spring Boot, SQL, Docker, AWS\n"


# ---------- Notice period ----------

@pytest.mark.parametrize("text, status", [
    ("Notice Period: 30 days", "meets"),
    ("Notice Period: 60 days", "meets"),
    ("Immediate joiner", "meets"),
    ("Notice Period: 75 days", "near"),                       # within 15 days of the limit
    ("Notice Period: 90 days", "does_not_meet"),
    ("Notice Period: 90 days (negotiable)", "near"),          # over, but the resume says it can be shortened
    ("Notice Period: 45-90 days", "near"),                    # the range starts within the limit
    ("Currently serving notice period.", "needs_review"),     # no day count, and none is invented
    ("Notice Period: 60 days\nNotice Period: 90 days", "needs_review"),
    ("Python developer", "unknown"),
])
def test_notice_against_a_60_day_limit(text, status):
    assert check_notice(fact(text, "notice_period"), 60).status == status


def test_notice_reason_states_the_numbers():
    check = check_notice(fact("Notice Period: 90 days", "notice_period"), 60)
    assert check.reason == "90 days is 30 days over the 60-day limit."
    assert (check.required, check.candidate) == ("60 days or less", "90 days")


def test_serving_notice_reason_quotes_the_resume_and_gives_no_days():
    check = check_notice(fact("Serving notice period, last working day is 28th November 2026", "notice_period"), 30)
    assert check.status == "needs_review"
    assert "Serving notice" in check.reason and "28th November 2026" in check.reason


def test_no_limit_means_no_check():
    assert check_notice(fact("Notice Period: 90 days", "notice_period"), None) is None
    assert check_ctc(None, None, None) is None
    assert check_location(None, None, []) is None
    assert check_experience(None, None, None) is None


# ---------- CTC ----------

@pytest.mark.parametrize("text, status", [
    ("Expected CTC: 18 LPA", "meets"),
    ("Expected CTC: 20 LPA", "meets"),
    ("Expected CTC: 22 LPA", "near"),                 # within 10% of the budget
    ("Expected CTC: 23 LPA", "does_not_meet"),
    ("Expected CTC: 18-24 LPA", "near"),              # the lower end is within budget
    ("Expected CTC: 22-26 LPA", "does_not_meet"),
    ("Expected salary: 1,50,000 per month", "meets"),  # 18 LPA
    ("Expected CTC: Rs. 25,00,000", "does_not_meet"),
    ("Expected CTC: Negotiable", "needs_review"),
    ("Expected CTC: 30% hike", "needs_review"),
    ("Current CTC: 14 LPA", "unknown"),               # expected not stated: unknown, not a mismatch
    ("Current CTC: 26 LPA", "needs_review"),          # already above budget, but expected isn't stated
    ("Java developer", "unknown"),
])
def test_ctc_against_a_20_lpa_budget(text, status):
    facts = extract_facts(text)
    assert check_ctc(facts.get("expected_ctc"), facts.get("current_ctc"), 20).status == status


def test_ctc_example_from_the_brief():
    facts = extract_facts("Expected CTC: 22 LPA")
    check = check_ctc(facts.get("expected_ctc"), None, 19)
    assert check.status == "does_not_meet"
    assert check.reason == "Expects 22 LPA, 3 LPA over the 19 LPA budget."


def test_a_hike_percentage_is_never_turned_into_a_figure():
    facts = extract_facts("Current CTC: 26 LPA\nExpected CTC: 30% hike")
    check = check_ctc(facts.get("expected_ctc"), facts.get("current_ctc"), 24)
    assert check.status == "needs_review"
    assert "33.8" not in check.reason and '"30% hike"' in check.reason
    assert "Current CTC (26 LPA) is already above" in check.reason


# ---------- Location ----------

@pytest.mark.parametrize("text, status", [
    ("Current Location: Hyderabad", "meets"),
    ("Current Location: Gachibowli", "meets"),         # a Hyderabad locality
    ("Current Location: Secunderabad", "meets"),
    ("Current Location: Chennai", "does_not_meet"),
    ("Current Location: Chennai\nPreferred Location: Hyderabad / Chennai", "near"),
    ("Current Location: Pune\nPreferred Location: Anywhere in India", "near"),
    ("Current Location: Rajahmundry", "needs_review"),  # not on the city list, so it isn't guessed
    ("Preferred Location: Hyderabad", "unknown"),       # current location isn't stated
    ("Java developer", "unknown"),
])
def test_location_against_hyderabad(text, status):
    facts = extract_facts(text)
    check = check_location(facts.get("current_location"), facts.get("preferred_location"), ["Hyderabad"])
    assert check.status == status


def test_city_names_match_across_spellings():
    facts = extract_facts("Current Location: Bangalore")
    assert check_location(facts.get("current_location"), None, locations_from_input("Bengaluru, Pune")).status == "meets"
    assert check_location(facts.get("current_location"), None, locations_from_input("Rajahmundry")).status == "does_not_meet"


# ---------- Experience ----------

@pytest.mark.parametrize("text, status", [
    ("Total Experience: 6 years", "meets"),
    ("Total Experience: 5 years", "meets"),
    ("Total Experience: 4 Years 8 Months", "near"),      # 4 months short
    ("Total Experience: 3 years", "does_not_meet"),
    ("Total Experience: 9 Years 4 Months", "near"),      # 4 months over the upper limit
    ("Total Experience: 14 years", "does_not_meet"),
    ("4 years of experience in Node.js, 2 years of experience in Java", "needs_review"),
    ("Java developer", "unknown"),
])
def test_experience_against_5_to_9_years(text, status):
    assert check_experience(fact(text, "total_experience"), 5, 9).status == status


def test_minimum_only_and_reason_text():
    check = check_experience(fact("Total Experience: 6 years", "total_experience"), 5, None)
    assert (check.status, check.required, check.reason) == ("meets", "5 years or more", "6 years is within 5 years or more.")


# ---------- The three dimensions and the summary ----------

def test_strong_candidate_with_a_notice_conflict_shows_the_conflict():
    text = STRONG + "Total Experience: 7 years\nNotice Period: 90 days\nExpected CTC: 18 LPA\nCurrent Location: Hyderabad"
    result = evaluate(text, extract_facts(text), requirements(**CLIENT))
    assert (result.skills.level, result.skills.score) == ("strong", 100)       # skills are not marked down
    assert result.constraints.overall == "does_not_meet"
    assert result.constraints.summary == "1 does not meet, 2 meets"
    assert result.next_step.key == "conflict"
    assert "notice period" in result.next_step.reason


def test_excellent_fit_with_nothing_stated_is_marked_for_clarification_not_penalised():
    result = evaluate(STRONG, extract_facts(STRONG), requirements(**CLIENT))
    assert (result.skills.level, result.skills.score) == ("strong", 100)
    assert result.constraints.overall == "unknown"
    assert {check.status for check in result.constraints.checks} == {"unknown"}
    assert (result.completeness.stated, result.completeness.total) == (0, 6)
    assert result.next_step.key == "clarify"


def test_everything_met_is_ready():
    text = STRONG + "Mobile: 9845012345\nTotal Experience: 7 years\nNotice Period: 30 days\nCurrent CTC: 14 LPA\nExpected CTC: 18 LPA\nCurrent Location: Hyderabad"
    result = evaluate(text, extract_facts(text), requirements(**CLIENT))
    assert result.next_step.key == "ready" and result.constraints.overall == "meets"
    assert result.completeness.stated == 6 and result.completeness.missing == []


def test_skills_score_ignores_wording_overlap():
    padded = STRONG + "notice period budget location client limits experience " * 20
    assert evaluate(padded, {}, requirements()).skills.score == evaluate(STRONG, {}, requirements()).skills.score == 100


def test_skills_score_is_70_30_and_says_so():
    text = "Skills: Java, Spring Boot, SQL, Docker"   # all 3 required, 1 of 2 preferred
    skills = evaluate(text, {}, requirements()).skills
    assert skills.score == 85 and "70% required skills + 30% preferred skills" in skills.explanation
    assert (skills.preferred_matched, skills.preferred_missing) == (["Docker"], ["AWS"])


@pytest.mark.parametrize("text, level", [
    ("Java, Spring Boot, SQL", "strong"),
    ("Java, SQL", "partial"),          # one of three required missing
    ("Java", "weak"),
])
def test_skill_levels(text, level):
    assert evaluate(text, {}, requirements()).skills.level == level


def test_low_skills_fit_still_reports_a_conflict():
    text = "Skills: Java\nNotice Period: 90 days"
    result = evaluate(text, extract_facts(text), requirements(max_notice_days=30))
    assert result.next_step.key == "low_fit"
    assert "Also conflicts on: notice period" in result.next_step.reason


def test_experience_outside_the_range_caps_the_level_and_explains_why():
    text = STRONG + "Total Experience: 2 years"
    skills = evaluate(text, extract_facts(text), requirements(min_experience_years=5)).skills
    assert skills.level == "partial" and skills.experience.status == "does_not_meet"
    assert "because the stated experience is outside the range" in skills.explanation


def test_no_requirements_set_means_only_skills_are_reported():
    result = evaluate(STRONG, {}, requirements())
    assert result.constraints.overall == "none_set" and result.constraints.checks == []
    assert result.next_step.reason == "No limits were set, so only skills were checked."


def test_conflicting_resume_values_need_a_person():
    text = STRONG + "Expected CTC: 18 LPA\nExpected CTC: 26 LPA"
    result = evaluate(text, extract_facts(text), requirements(max_ctc_lpa=20))
    assert result.constraints.checks[0].status == "needs_review"
    assert "CTC" in result.next_step.reason and result.next_step.key == "check"


def test_review_order_puts_ready_first_and_nobody_is_dropped():
    reqs = requirements(**CLIENT)
    resumes = {
        "conflict.txt": STRONG + "Total Experience: 7 years\nNotice Period: 90 days\nExpected CTC: 18 LPA\nCurrent Location: Hyderabad",
        "ready.txt": STRONG + "Total Experience: 7 years\nNotice Period: 30 days\nExpected CTC: 18 LPA\nCurrent Location: Hyderabad",
        "clarify.txt": STRONG,
        "lowfit.txt": "Skills: Python",
    }
    ordered = sorted(resumes, key=lambda name: review_order(evaluate(resumes[name], extract_facts(resumes[name]), reqs), name))
    assert ordered == ["ready.txt", "clarify.txt", "conflict.txt", "lowfit.txt"]
