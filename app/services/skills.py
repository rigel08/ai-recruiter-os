"""Skill vocabulary and whole-term matching.

A skill matches only as a whole term, so "Java" does not match inside
"JavaScript", and spellings like "C++", "C#" and "Node.js" match literally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Canonical name -> other spellings that count as the same skill.
SKILLS: dict[str, tuple[str, ...]] = {
    # Programming languages
    "Python": (),
    "Java": (),
    "JavaScript": ("JS", "ECMAScript"),
    "TypeScript": (),
    "C++": ("CPP",),
    "C#": ("C Sharp",),
    "Golang": ("Go language",),
    "Rust": (),
    "Kotlin": (),
    "Swift": (),
    "PHP": (),
    "Scala": (),
    "SQL": (),
    "Bash": ("Shell scripting",),
    "MATLAB": (),
    # Web and backend
    "HTML": ("HTML5",),
    "CSS": ("CSS3",),
    "React": ("React.js", "ReactJS"),
    "Next.js": ("NextJS",),
    "Angular": ("AngularJS",),
    "Vue.js": ("Vue", "VueJS"),
    "Node.js": ("NodeJS", "Node JS"),
    "Express.js": ("ExpressJS",),
    "Django": (),
    "Flask": (),
    "FastAPI": (),
    "Spring Boot": (),
    ".NET": ("ASP.NET", "dotnet"),
    "Tailwind CSS": ("Tailwind",),
    "REST APIs": ("REST API", "RESTful", "RESTful APIs"),
    "GraphQL": (),
    # Databases
    "PostgreSQL": ("Postgres",),
    "MySQL": (),
    "MongoDB": ("Mongo",),
    "Redis": (),
    "SQLite": (),
    "Elasticsearch": (),
    "Firebase": (),
    # Cloud and DevOps
    "AWS": ("Amazon Web Services",),
    "Azure": ("Microsoft Azure",),
    "GCP": ("Google Cloud", "Google Cloud Platform"),
    "Docker": (),
    "Kubernetes": ("K8s",),
    "Terraform": (),
    "Linux": (),
    "Git": (),
    "GitHub Actions": (),
    "Jenkins": (),
    "CI/CD": ("CI CD", "Continuous Integration"),
    # Data and ML
    "Machine Learning": ("ML",),
    "Deep Learning": (),
    "NLP": ("Natural Language Processing",),
    "Computer Vision": (),
    "LLMs": ("LLM", "Large Language Models", "Generative AI", "GenAI"),
    "TensorFlow": (),
    "PyTorch": (),
    "Scikit-learn": ("sklearn", "scikit learn"),
    "Pandas": (),
    "NumPy": (),
    "Spark": ("Apache Spark", "PySpark"),
    "Data Analysis": ("Data Analytics",),
    "Statistics": (),
    "Power BI": ("PowerBI",),
    "Tableau": (),
    "Excel": ("MS Excel", "Microsoft Excel", "Advanced Excel"),
    # Testing
    "pytest": (),
    "Selenium": (),
    "Playwright": (),
    "Jest": (),
    "Unit Testing": (),
    # Mobile
    "Android": (),
    "iOS": (),
    "Flutter": (),
    "React Native": (),
    # Design
    "Figma": (),
    "UI/UX": ("UX Design", "UI Design", "User Experience"),
    "Photoshop": ("Adobe Photoshop",),
    # Business
    "Financial Modelling": ("Financial Modeling",),
    "Accounting": (),
    "Digital Marketing": (),
    "SEO": ("Search Engine Optimisation", "Search Engine Optimization"),
    "Social Media Marketing": (),
    "Content Writing": (),
    "Sales": (),
    "Business Development": (),
    "CRM": (),
    "Salesforce": (),
    "SAP": (),
    "Market Research": (),
    "Project Management": (),
    "Agile": ("Scrum",),
    "Product Management": (),
    "Supply Chain": ("Supply Chain Management",),
}

# These are also ordinary English words ("excel at", "a swift learner"),
# so they only count when capitalised the way the skill is written.
CASE_SENSITIVE = {"Excel", "Swift", "Spark", "Rust", "Jest", "SAP", "CRM", "SEO", "ML", "JS"}

# A term must not touch a letter, digit or one of "+#" on either side.
# A "." before it is also excluded, so ".NET" isn't found inside "ASP.NET".
_BEFORE = r"(?<![A-Za-z0-9+#.])"
_AFTER = r"(?![A-Za-z0-9+#])"


@dataclass(frozen=True)
class Term:
    """A skill (from the vocabulary, or typed by a recruiter) and how to find it."""

    name: str
    pattern: re.Pattern[str]

    def found_in(self, text: str) -> bool:
        return self.pattern.search(text) is not None


def _alternation(spellings: list[str]) -> str:
    # Longest first, so "React Native" wins over "React". Any run of
    # whitespace in the text counts as one space.
    regexes = {r"\s+".join(re.escape(word) for word in s.split()) for s in spellings}
    return "|".join(sorted(regexes, key=len, reverse=True))


def _pattern_for(spellings: list[str]) -> re.Pattern[str]:
    # The case rule is per spelling: "Excel" must be capitalised, but
    # "Microsoft Excel" matches in any case.
    loose = [s for s in spellings if s not in CASE_SENSITIVE]
    strict = [s for s in spellings if s in CASE_SENSITIVE]
    alternatives = []
    if loose:
        alternatives.append(f"(?i:{_alternation(loose)})")
    if strict:
        alternatives.append(_alternation(strict))
    return re.compile(f"{_BEFORE}(?:{'|'.join(alternatives)}){_AFTER}")


def _build_vocabulary() -> tuple[list[Term], dict[str, Term]]:
    terms: list[Term] = []
    by_spelling: dict[str, Term] = {}
    for name, aliases in SKILLS.items():
        spellings = [name, *aliases]
        term = Term(name=name, pattern=_pattern_for(spellings))
        terms.append(term)
        for spelling in spellings:
            by_spelling[spelling.lower()] = term
    return terms, by_spelling


VOCABULARY, _BY_SPELLING = _build_vocabulary()


def skills_in(text: str) -> list[Term]:
    """Vocabulary skills that appear in the text, in vocabulary order."""
    return [term for term in VOCABULARY if term.found_in(text)]


def terms_from_input(raw: str) -> list[Term]:
    """Turn a recruiter's comma- or line-separated list into terms.

    Known spellings map to the vocabulary skill (so "postgres" also finds
    "PostgreSQL"). Anything else is matched as typed, ignoring case.
    """
    terms: list[Term] = []
    seen: set[str] = set()
    for piece in re.split(r"[,;\n]", raw):
        typed = " ".join(piece.split())
        if not typed:
            continue
        term = _BY_SPELLING.get(typed.lower()) or Term(
            name=typed, pattern=re.compile(f"{_BEFORE}(?i:{_alternation([typed])}){_AFTER}")
        )
        if term.name.lower() not in seen:
            seen.add(term.name.lower())
            terms.append(term)
    return terms
