"""The release gate for fact extraction: nothing wrong on the labelled set, and coverage can't slip."""

from evals.facts.run import evaluate, load_cases

CASES = load_cases()


def test_labelled_set_is_big_enough_to_mean_something():
    assert len(CASES) >= 70
    assert len({case["id"] for case in CASES}) == len(CASES)
    traps = [case for case in CASES if case["id"].startswith("trap-")]
    assert len(traps) >= 20, "keep plenty of cases where the right answer is 'nothing'"


def test_no_wrong_values_on_the_labelled_set():
    report = evaluate(CASES)
    wrong = [p for p in report["problems"] if p["kind"] == "wrong"]
    assert wrong == [], "a wrong value is worse than a blank"


def test_coverage_does_not_slip():
    report = evaluate(CASES)
    # Every value in the labelled set is found today. If a rule change loses one, decide on purpose.
    assert report["missed"] == 0, report["problems"]


# ---------- Traceability: a quote is copied from the resume, never written by the tool ----------

from pathlib import Path  # noqa: E402

from app.services.facts import extract_facts  # noqa: E402

SAMPLES = sorted((Path(__file__).resolve().parent.parent / "app" / "samples" / "experienced" / "resumes").glob("*.txt"))
SOURCES = [case["text"] for case in CASES] + [path.read_text(encoding="utf-8") for path in SAMPLES]


def test_every_quote_is_copied_from_the_source_text():
    checked = 0
    for text in SOURCES:
        source = " ".join(text.split())  # the same whitespace clean-up the extractor does
        for field, fact in extract_facts(text).items():
            assert fact.quote.strip("…") in source, (field, fact.quote)
            checked += 1
    assert checked >= 90


def test_every_value_can_be_read_from_its_quote_alone():
    # Hand someone only the quote and they reach the same value: the quote is real evidence.
    for text in SOURCES:
        for field, fact in extract_facts(text).items():
            again = extract_facts(fact.quote.strip("…")).get(field)
            assert again is not None and again.value == fact.value, (field, fact.quote)
