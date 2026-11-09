from app.services import screening
from app.services.screening import MAX_FILE_BYTES, ResumeFile, guess_name, screen
from tests.helpers import make_pdf, resume_lines

JOB = (
    "Backend Engineer. You will build REST APIs in Python with FastAPI and PostgreSQL, "
    "deploy on AWS with Docker, and write tests with pytest. React is a plus."
)


def pdf(file_name, name, email, skills, extra=()):
    return ResumeFile(file_name, make_pdf([*resume_lines(name, email, skills), *extra]))


def test_ranks_and_suggests_by_must_haves():
    result = screen(
        JOB,
        "Python, FastAPI, PostgreSQL",
        [
            pdf("weak.pdf", "Ravi Kumar", "ravi@example.com", "Java, Spring Boot"),
            pdf("strong.pdf", "Asha Verma", "asha@example.com", "Python, FastAPI, PostgreSQL, AWS, Docker"),
            pdf("close.pdf", "Neha Rao", "neha@example.com", "Python, FastAPI, MySQL"),
        ],
    )
    assert [(c.file_name, c.decision) for c in result.candidates] == [
        ("strong.pdf", "shortlist"),
        ("close.pdf", "maybe"),
        ("weak.pdf", "not_a_fit"),
    ]
    assert [c.rank for c in result.candidates] == [1, 2, 3]
    assert result.decision_counts == {"shortlist": 1, "maybe": 1, "not_a_fit": 1}

    top = result.candidates[0]
    assert (top.name, top.email) == ("Asha Verma", "asha@example.com")
    assert top.summary.startswith("Has 3 of 3 must-haves.")
    assert len(top.interview_questions) == 3

    close = result.candidates[1]
    assert close.must_haves_missing == ["PostgreSQL"]
    assert close.interview_questions[0].startswith("The role needs PostgreSQL.")
    assert result.candidates[2].interview_questions == []


def test_cgpa_cut_off_moves_a_strong_candidate_down_and_explains():
    result = screen(
        JOB,
        "Python",
        [
            pdf("high.pdf", "Asha Verma", "a@example.com", "Python", extra=["CGPA 8.4 / 10"]),
            pdf("low.pdf", "Ravi Kumar", "r@example.com", "Python, FastAPI, AWS", extra=["CGPA 6.5 / 10"]),
            pdf("none.pdf", "Neha Rao", "n@example.com", "Python"),
        ],
        min_cgpa=7.0,
    )
    by_file = {c.file_name: c for c in result.candidates}
    assert result.min_cgpa == 7.0
    assert by_file["high.pdf"].decision == "shortlist"
    assert by_file["high.pdf"].summary.startswith("CGPA 8.4 meets the 7.0 cut-off.")
    assert by_file["low.pdf"].decision == "not_a_fit"
    assert by_file["low.pdf"].cgpa == 6.5
    assert "Only the CGPA cut-off rules them out" in by_file["low.pdf"].flags[0]
    assert by_file["none.pdf"].decision == "shortlist"
    assert "No CGPA found" in by_file["none.pdf"].flags[0]
    # Shortlisted candidates come before the one below the cut-off, despite its higher score.
    assert result.candidates[-1].file_name == "low.pdf"


def test_other_skills_come_from_the_job_description():
    result = screen(JOB, "Python", [pdf("a.pdf", "Asha Verma", "a@example.com", "Python")])
    assert result.must_haves == ["Python"]
    assert {"FastAPI", "PostgreSQL", "AWS", "Docker", "pytest", "React", "REST APIs"} <= set(result.other_skills)
    assert "Python" not in result.other_skills


def test_files_that_cant_be_read_go_to_manual_review():
    result = screen(
        JOB,
        "Python",
        [
            pdf("good.pdf", "Asha Verma", "a@example.com", "Python"),
            ResumeFile("scan.pdf", make_pdf([""])),
            ResumeFile("old.doc", b"binary"),
            ResumeFile("huge.pdf", b"x" * (MAX_FILE_BYTES + 1)),
        ],
    )
    assert result.ranked_count == 1
    assert result.needs_review_count == 3
    review = {c.file_name: c for c in result.candidates if c.status == "needs_review"}
    assert set(review) == {"scan.pdf", "old.doc", "huge.pdf"}
    assert "scanned image" in review["scan.pdf"].summary
    assert all(c.rank is None and c.score is None and c.decision is None for c in review.values())
    assert result.candidates[0].file_name == "good.pdf"


def test_without_must_haves_ranks_on_job_description_skills():
    result = screen(
        JOB,
        "",
        [
            pdf("a.pdf", "Asha Verma", "a@example.com", "Python, FastAPI, AWS"),
            pdf("b.pdf", "Ravi Kumar", "r@example.com", "Photoshop"),
        ],
    )
    assert [c.file_name for c in result.candidates] == ["a.pdf", "b.pdf"]
    # Python, FastAPI and AWS out of the 8 skills the job description names.
    assert result.candidates[0].summary == "Matches 3 of 8 other skills in the job description."


def test_parallel_parsing_gives_the_same_result(monkeypatch):
    files = [
        pdf(f"{i}.pdf", name, f"{i}@example.com", skills)
        for i, (name, skills) in enumerate(
            [("Asha Verma", "Python, FastAPI"), ("Ravi Kumar", "Java"), ("Neha Rao", "Python, SQL")]
        )
    ] + [ResumeFile("broken.pdf", b"not a pdf")]
    sequential = screen(JOB, "Python", files)

    monkeypatch.setattr(screening, "PARALLEL_THRESHOLD", 2)
    try:
        parallel = screen(JOB, "Python", files)
        assert screening._pool is not None  # the worker processes really were used
    finally:
        screening.shutdown_pool()
    assert parallel == sequential


def test_guess_name_skips_headings_and_tidies_capitals():
    assert guess_name("RESUME\nASHA VERMA\nasha@example.com") == "Asha Verma"
    assert guess_name("Curriculum Vitae\nSkills: Python, SQL") is None
