import pytest

from app.services.academics import find_cgpa


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Education: B.Tech CSE | CGPA 8.20 / 10", 8.2),
        ("CGPA: 7.8", 7.8),
        ("C.G.P.A - 7.9", 7.9),
        ("GPA of 8.1/10.0", 8.1),
        ("CPI 8.45", 8.45),
        ("Graduated with 8.5 CGPA", 8.5),
        ("(CGPA 8.9/10)", 8.9),
        ("B.Tech 2027, CGPA 9", 9.0),
    ],
)
def test_reads_common_formats(text, expected):
    assert find_cgpa(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "GPA 3.6/4",  # a 4-point scale isn't converted
        "Percentage: 78%",
        "SGPA 9.1 in semester 5",  # one semester, not the overall CGPA
        "Expected 2027",
        "CGPA 78/100",
        "No grades mentioned here",
    ],
)
def test_ignores_things_that_arent_a_10_point_cgpa(text):
    assert find_cgpa(text) is None


def test_uses_the_first_cgpa_on_the_resume():
    text = "B.Tech, CGPA 8.2\nClass XII: 92%\nClass X: CGPA 9.8"
    assert find_cgpa(text) == 8.2


def test_skips_a_4_point_gpa_and_finds_the_next():
    assert find_cgpa("MS: GPA 3.7/4\nB.Tech: CGPA 8.4/10") == 8.4
