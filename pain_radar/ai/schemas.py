from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


ProblemTypeLiteral = Literal[
    "manual_work",
    "workflow_friction",
    "bad_existing_tool",
    "expensive_solution",
    "missing_solution",
    "unreliable_solution",
    "repetitive_task",
    "time_waste",
    "other",
]


class PainSignalSchema(BaseModel):
    is_real_problem: bool = Field(
        ...,
        description="True only if this represents a genuine, recurring, experienced user problem (not a hypothetical idea)."
    )
    pain_level: int = Field(
        ...,
        ge=1,
        le=5,
        description="1=trivial, 2=minor, 3=moderate, 4=significant, 5=severe"
    )
    recurring_problem: bool = Field(
        ...,
        description="True if this is an ongoing/repeated operational pain."
    )
    manual_workaround: bool = Field(
        ...,
        description="True if the user is currently doing things manually (Excel, copy-paste, scripts, WhatsApp, etc.)."
    )
    existing_solution_failure: bool = Field(
        ...,
        description="True if existing commercial tools failed, broke, or dissatisfied the user."
    )
    purchase_signal: bool = Field(
        ...,
        description="True if user expresses willingness to pay or actively seeks paid software/services."
    )
    switching_signal: bool = Field(
        ...,
        description="True if user is looking to cancel/replace their current software."
    )
    problem_type: str = Field(
        ...,
        description="Type of problem (manual_work, workflow_friction, bad_existing_tool, expensive_solution, missing_solution, etc.)"
    )
    problem_statement: str = Field(
        ...,
        description="A concise, normalized 1-sentence statement of the underlying problem."
    )
    target_user: str = Field(
        ...,
        description="Who is experiencing this pain (e.g. 'B2B SaaS founders', 'Freelance copywriters')."
    )
    current_workaround: str = Field(
        ...,
        description="What the user or team does right now to cope with the problem."
    )
    why_painful: str = Field(
        ...,
        description="Specific explanation of why this hurts (time loss, errors, churn, cost)."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0."
    )

    @field_validator("problem_statement")
    @classmethod
    def validate_problem_statement(cls, v: str) -> str:
        s = v.strip()
        lower = s.lower()
        generic_patterns = [
            "users struggle with manual work",
            "businesses face operational overhead",
            "founders have difficulty with marketing",
            "businesses struggle with invoicing",
            "founders struggle with marketing",
            "struggle with manual work",
            "difficulty with marketing",
            "face operational overhead",
            "struggle with invoicing",
            "incomplete input",
            "problem details unavailable",
            "manual operational overhead consuming excessive",
            "insufficient information",
            "unreliable behavior that causes recurring",
            "missing required problem fields",
        ]
        for pat in generic_patterns:
            if pat in lower:
                raise ValueError(
                    f"Problem statement '{s}' is too generic. Must specify: 1) WHO has the problem, 2) WHAT exact task/problem they experience, and 3) WHAT makes the current solution inadequate."
                )
        if len(s) < 25:
            raise ValueError(
                f"Problem statement '{s}' is too short/generic. Must specify WHO, WHAT exact task, and WHAT makes current solution inadequate."
            )
        return s

    @field_validator("pain_level", mode="before")
    @classmethod
    def clamp_pain_level(cls, v):
        try:
            val = int(v)
            return max(1, min(5, val))
        except (ValueError, TypeError):
            return 1

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.5


class OpportunitySynthesisSchema(BaseModel):
    problem_summary: str = Field(
        ...,
        description="Synthesized summary of the recurring pain point grounded strictly in evidence."
    )
    target_user: str = Field(
        ...,
        description="Primary target user persona identified from the discussions."
    )
    why_it_hurts: str = Field(
        ...,
        description="Root cause of the pain and business/operational consequences."
    )
    current_workaround: str = Field(
        ...,
        description="Common workarounds observed across the evidence records."
    )
    existing_solutions: List[str] = Field(
        default_factory=list,
        description="Existing products or competitors mentioned."
    )
    observed_gaps: List[str] = Field(
        default_factory=list,
        description="Where existing solutions fail or fall short."
    )
    product_direction: str = Field(
        ...,
        description="Evidence-backed opportunity direction to solve the core friction."
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Potential execution risks or market challenges."
    )

    @field_validator("problem_summary")
    @classmethod
    def validate_problem_summary(cls, v: str) -> str:
        s = v.strip()
        lower = s.lower()
        generic_patterns = [
            "users struggle with manual work",
            "businesses face operational overhead",
            "founders have difficulty with marketing",
            "businesses struggle with invoicing",
            "founders struggle with marketing",
            "struggle with manual work",
            "difficulty with marketing",
            "face operational overhead",
            "struggle with invoicing",
            "incomplete input",
            "problem details unavailable",
            "manual operational overhead consuming excessive",
            "insufficient information",
            "unreliable behavior that causes recurring",
            "missing required problem fields",
        ]
        for pat in generic_patterns:
            if pat in lower:
                raise ValueError(
                    f"Problem summary '{s}' is too generic. Must specify: 1) WHO has the problem, 2) WHAT exact task/problem they experience, and 3) WHAT makes the current solution inadequate."
                )
        if len(s) < 25:
            raise ValueError(
                f"Problem summary '{s}' is too short/generic. Must specify WHO, WHAT exact task, and WHAT makes current solution inadequate."
            )
        return s
