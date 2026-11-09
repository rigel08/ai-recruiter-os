"""Score the fact extractor against labelled cases.

Each case lists every value a careful reader would take from the text. A field that isn't
listed must come back with no usable value: returning one there counts as wrong.
"""

import json
from pathlib import Path
from typing import Any

from app.services.facts import FIELD_LABELS, extract_facts

GOLD_PATH = Path(__file__).parent / "gold.json"


def load_cases() -> list[dict[str, Any]]:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))["cases"]


def _same(expected: Any, got: Any) -> bool:
    if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
        return abs(float(expected) - float(got)) < 0.011
    return expected == got


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {field: {"expected": 0, "correct": 0, "missed": 0, "wrong": 0} for field in FIELD_LABELS}
    problems = []
    for case in cases:
        facts = extract_facts(case["text"])
        for field in FIELD_LABELS:
            expected = case["expect"].get(field)
            fact = facts.get(field)
            got = fact.value if fact is not None else None
            row = fields[field]
            if expected is not None:
                row["expected"] += 1
            if expected is None and got is None:
                continue
            if expected is not None and got is not None and _same(expected, got):
                row["correct"] += 1
            elif got is None:
                row["missed"] += 1
                problems.append({"kind": "missed", "case": case["id"], "field": field, "expected": expected, "got": None})
            else:
                row["wrong"] += 1
                problems.append({"kind": "wrong", "case": case["id"], "field": field, "expected": expected, "got": got})
    return {
        "cases": len(cases),
        "fields": fields,
        "problems": problems,
        "wrong": sum(row["wrong"] for row in fields.values()),
        "missed": sum(row["missed"] for row in fields.values()),
        "expected": sum(row["expected"] for row in fields.values()),
        "correct": sum(row["correct"] for row in fields.values()),
    }
