from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["shortlist", "maybe", "not_a_fit"]


class Fact(BaseModel):
    """One value taken from the resume, with the line that proves it."""

    value: float | str | None = Field(description="Normalised value; null when the resume says something that isn't a value")
    unit: str | None = Field(default=None, description="years, days or LPA; null for text")
    display: str
    quote: str = Field(description="The exact line from the resume")
    note: str | None = None
    confirm: bool = Field(default=False, description="The resume is unclear here; check on the call")
    low: float | None = Field(default=None, description="Lower end when the resume gives a range; `value` is the upper end")
    tags: list[str] = Field(default_factory=list, description="negotiable, serving or per_skill, where the resume says so")


class CandidateFacts(BaseModel):
    """Fields a recruiter's tracker needs. A field is null when the resume doesn't state it."""

    phone: Fact | None = None
    total_experience: Fact | None = None
    notice_period: Fact | None = None
    current_ctc: Fact | None = None
    expected_ctc: Fact | None = None
    current_location: Fact | None = None
    preferred_location: Fact | None = None


CheckStatus = Literal["meets", "near", "does_not_meet", "unknown", "needs_review"]
StepKey = Literal["ready", "clarify", "check", "conflict", "low_fit"]


class RequirementCheck(BaseModel):
    """One requirement compared with what the resume states."""

    requirement: str = Field(description="experience, notice_period, ctc or location")
    label: str
    required: str = Field(description="The requirement in words, such as '60 days or less'")
    candidate: str | None = Field(description="What the resume states, or null")
    status: CheckStatus
    reason: str


class SkillsFit(BaseModel):
    level: Literal["strong", "partial", "weak", "not_set"]
    score: int | None = Field(description="0-100: 70% required skills, 30% preferred. No wording-overlap part")
    required_matched: list[str]
    required_missing: list[str]
    preferred_matched: list[str]
    preferred_missing: list[str]
    experience: RequirementCheck | None
    explanation: str


class ConstraintsFit(BaseModel):
    overall: CheckStatus | Literal["none_set"] = Field(description="The most serious status among the checks")
    checks: list[RequirementCheck]
    summary: str


class Completeness(BaseModel):
    stated: int
    total: int
    missing: list[str] = Field(description="Tracker fields the resume doesn't state")
    unclear: list[str] = Field(description="Fields the resume states in words or with conflicting values")


class NextStep(BaseModel):
    key: StepKey
    label: str
    reason: str


class Evaluation(BaseModel):
    """Three separate views of one candidate, plus a one-line summary that never hides a conflict."""

    skills: SkillsFit
    constraints: ConstraintsFit
    completeness: Completeness
    next_step: NextStep


class AppliedRequirements(BaseModel):
    """The requirements candidates were evaluated against, as the recruiter confirmed them."""

    required_skills: list[str]
    preferred_skills: list[str]
    min_experience_years: float | None
    max_experience_years: float | None
    max_notice_days: float | None
    max_ctc_lpa: float | None
    locations: list[str]


class ResolvedFact(BaseModel):
    """The value in use for one field, and where it came from. The resume's own value is kept beside it."""

    source: Literal["resume", "recruiter_confirmed", "recruiter_entered", "unknown"]
    value: float | str | None = None
    unit: str | None = None
    display: str | None = Field(default=None, description="The value in use, in words; null when unknown")
    resume_display: str | None = Field(default=None, description="What the resume says, whatever is in use")
    state: Literal["answered", "confirmed", "pending", "not_applicable"] | None = Field(
        default=None, description="What the recruiter recorded for this field, if anything")
    note: str = ""


class CandidateResult(BaseModel):
    file_name: str
    status: Literal["ranked", "needs_review"]
    rank: int | None = None
    decision: Decision | None = Field(default=None, description="The suggested next step")
    score: int | None = Field(default=None, ge=0, le=100)
    name: str | None = None
    email: str | None = None
    cgpa: float | None = None
    must_haves_matched: list[str] = Field(default_factory=list)
    must_haves_missing: list[str] = Field(default_factory=list)
    other_skills_matched: list[str] = Field(default_factory=list)
    summary: str
    flags: list[str] = Field(default_factory=list, description="Things a person should double-check")
    interview_questions: list[str] = Field(default_factory=list)
    facts: CandidateFacts = Field(default_factory=CandidateFacts)
    to_ask: list[str] = Field(default_factory=list, description="Tracker fields the recruiter still has to ask about")
    evaluation: Evaluation | None = Field(default=None, description="Present only for experienced hiring")
    resolved: dict[str, ResolvedFact] | None = Field(
        default=None, description="Experienced hiring only: each field's value in use and its source. `facts` is never changed")
    remarks: str = Field(default="", description="The recruiter's notes, once recorded")
    profile: dict[str, Fact] = Field(
        default_factory=dict,
        description="Experienced hiring only: current designation, employer, education and relevant experience, where stated")


class DuplicateGroup(BaseModel):
    """Resumes that look like the same person, because they share a phone number or an email address."""

    file_names: list[str]
    names: list[str]
    reason: str


class ScreeningResult(BaseModel):
    must_haves: list[str]
    other_skills: list[str] = Field(description="Skills found in the job description that aren't must-haves")
    min_cgpa: float | None
    ranked_count: int
    needs_review_count: int
    decision_counts: dict[Decision, int]
    fact_coverage: dict[str, int] = Field(
        default_factory=dict, description="For each tracker field, how many ranked resumes gave a usable value"
    )
    hiring_mode: Literal["campus", "experienced"] = "campus"
    requirements: AppliedRequirements | None = Field(default=None, description="Present only for experienced hiring")
    next_step_counts: dict[StepKey, int] | None = None
    duplicates: list[DuplicateGroup] = Field(default_factory=list, description="Experienced hiring only")
    candidates: list[CandidateResult] = Field(
        description="Ranked candidates first, then files that need a person to look. Campus hiring orders by "
        "shortlist, maybe, not a fit; experienced hiring orders by next step, and removes nobody"
    )
