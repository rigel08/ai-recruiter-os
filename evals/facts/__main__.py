"""Print how the fact extractor does on the labelled set:  python -m evals.facts"""

import sys

from evals.facts.run import evaluate, load_cases

if __name__ == "__main__":
    report = evaluate(load_cases())
    print(f"{report['cases']} labelled cases (synthetic: written by hand, not real resumes)\n")
    print(f"{'Field':<20}{'Expected':>9}{'Found':>7}{'Missed':>8}{'Wrong':>7}")
    for field, row in report["fields"].items():
        print(f"{field:<20}{row['expected']:>9}{row['correct']:>7}{row['missed']:>8}{row['wrong']:>7}")
    for problem in report["problems"]:
        print(f"\n{problem['kind'].upper()}  {problem['case']}  {problem['field']}: "
              f"expected {problem['expected']!r}, got {problem['got']!r}")
    sys.exit(1 if report["wrong"] else 0)
