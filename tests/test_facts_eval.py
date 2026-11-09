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
