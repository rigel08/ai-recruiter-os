import pytest

from app.services.scoring import Score
from app.services.suggestions import format_cgpa, suggest


def score(total=70, matched=(), missing=(), others=()):
    return Score(
        total=total,
        must_haves_matched=list(matched),
        must_haves_missing=list(missing),
        other_skills_matched=list(others),
    )


def test_every_must_have_means_shortlist_with_varied_questions():
    result = suggest(score(matched=["Python", "SQL", "Docker"]), 3, cgpa=None, min_cgpa=None)
    assert result.decision == "shortlist"
    assert result.flags == []
    assert len(result.interview_questions) == 3
    assert len({q.split(" ")[0] for q in result.interview_questions}) == 3  # three different openings
    assert "Python" in result.interview_questions[0]


def test_missing_one_of_several_must_haves_is_a_maybe_and_asks_about_the_gap_first():
    result = suggest(score(matched=["Python", "SQL"], missing=["Docker"]), 3, cgpa=None, min_cgpa=None)
    assert result.decision == "maybe"
    assert result.interview_questions[0].startswith("The role needs Docker.")


@pytest.mark.parametrize(
    ("matched", "missing", "count"),
    [([], ["Python"], 1), (["Python"], ["SQL", "Docker"], 3)],
)
def test_missing_the_only_must_have_or_two_or_more_is_not_a_fit(matched, missing, count):
    result = suggest(score(matched=matched, missing=missing), count, cgpa=None, min_cgpa=None)
    assert result.decision == "not_a_fit"
    assert result.interview_questions == []


def test_cgpa_below_cut_off_overrides_skills_and_says_so():
    result = suggest(score(matched=["Python"]), 1, cgpa=6.6, min_cgpa=7.0)
    assert result.decision == "not_a_fit"
    assert result.cgpa_note == "CGPA 6.6 is below the 7.0 cut-off."
    assert result.flags == ["Would be shortlisted on skills. Only the CGPA cut-off rules them out."]


def test_cgpa_meeting_cut_off_is_noted():
    result = suggest(score(matched=["Python"]), 1, cgpa=7.0, min_cgpa=7.0)
    assert result.decision == "shortlist"
    assert result.cgpa_note == "CGPA 7.0 meets the 7.0 cut-off."


def test_missing_cgpa_is_flagged_but_does_not_exclude():
    result = suggest(score(matched=["Python"]), 1, cgpa=None, min_cgpa=7.0)
    assert result.decision == "shortlist"
    assert "No CGPA found" in result.flags[0]


def test_no_cut_off_means_cgpa_is_not_mentioned():
    result = suggest(score(matched=["Python"]), 1, cgpa=5.0, min_cgpa=None)
    assert result.decision == "shortlist"
    assert result.cgpa_note is None and result.flags == []


@pytest.mark.parametrize(("total", "decision"), [(60, "shortlist"), (59, "maybe"), (35, "maybe"), (34, "not_a_fit")])
def test_without_must_haves_the_score_decides(total, decision):
    result = suggest(score(total=total, others=["AWS"]), 0, cgpa=None, min_cgpa=None)
    assert result.decision == decision


@pytest.mark.parametrize(("value", "text"), [(7.0, "7.0"), (8.25, "8.25"), (8.7, "8.7"), (10, "10.0")])
def test_format_cgpa(value, text):
    assert format_cgpa(value) == text
