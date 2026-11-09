"""Score one resume against one job."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.services.skills import Term

# How much each part counts towards the 0-100 score. A part that doesn't
# apply (no must-haves given, or no other skills found in the job
# description) is left out, and the remaining weights are scaled to fill 100.
WEIGHTS = {"must_haves": 0.6, "other_skills": 0.3, "similarity": 0.1}

# Words too common in resumes and job descriptions to say anything about fit.
_STOPWORDS = frozenset(
    """a about after all also am an and any are as at be been being both but by can could did do
    does each etc for from had has have he her his how i if in into is it its just me more most my
    no not of on only or other our out over per she should so some such than that the their them
    then there these they this those through to too under up very via was we were what when where
    which while who will with within would you your
    ability candidate candidates experience good job knowledge preferred required requirements
    responsibilities role skill skills strong team understanding use using work working year years""".split()
)
_WORD = re.compile(r"[a-z][a-z0-9+#]*")


@dataclass(frozen=True)
class Score:
    total: int
    must_haves_matched: list[str]
    must_haves_missing: list[str]
    other_skills_matched: list[str]


def word_counts(text: str) -> Counter[str]:
    words = _WORD.findall(text.lower())
    return Counter(word for word in words if len(word) > 1 and word not in _STOPWORDS)


def cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(count * b[word] for word, count in a.items() if word in b)
    norm_a = math.sqrt(sum(count * count for count in a.values()))
    norm_b = math.sqrt(sum(count * count for count in b.values()))
    return dot / (norm_a * norm_b)


def score_resume(
    text: str,
    must_haves: list[Term],
    other_skills: list[Term],
    job_words: Counter[str],
) -> Score:
    matched = [term.name for term in must_haves if term.found_in(text)]
    missing = [term.name for term in must_haves if term.name not in matched]
    others = [term.name for term in other_skills if term.found_in(text)]

    parts = {"similarity": cosine_similarity(word_counts(text), job_words)}
    if must_haves:
        parts["must_haves"] = len(matched) / len(must_haves)
    if other_skills:
        parts["other_skills"] = len(others) / len(other_skills)
    weight_sum = sum(WEIGHTS[name] for name in parts)
    total = round(100 * sum(WEIGHTS[name] * value for name, value in parts.items()) / weight_sum)

    return Score(
        total=total,
        must_haves_matched=matched,
        must_haves_missing=missing,
        other_skills_matched=others,
    )


def explain(score: Score, must_have_count: int, other_skill_count: int) -> str:
    """One plain-English line a recruiter can read at a glance."""
    sentences = []
    if must_have_count:
        sentence = f"Has {len(score.must_haves_matched)} of {must_have_count} must-haves"
        if score.must_haves_missing:
            sentence += f"; missing {', '.join(score.must_haves_missing)}"
        sentences.append(sentence)
    if other_skill_count:
        sentences.append(
            f"Matches {len(score.other_skills_matched)} of {other_skill_count} other skills in the job description"
        )
    if not sentences:
        sentences.append("Ranked on how closely the resume's wording matches the job description")
    return ". ".join(sentences) + "."
