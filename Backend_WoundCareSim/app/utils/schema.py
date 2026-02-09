from pydantic import BaseModel, Field, field_validator
from typing import List
from typing import Literal


class EvaluatorResponse(BaseModel):
    """
    Structured evaluator output (Week-4)
    No scoring, no evidence linking yet.
    """

    agent_name: str = Field(..., description="Name of evaluator agent")
    step: str = Field(..., description="Current procedure step")

    strengths: List[str] = Field(
        ..., description="What the student did correctly"
    )

    issues_detected: List[str] = Field(
        ..., description="Problems or mistakes identified"
    )

    explanation: str = Field(
        ..., description="Reasoning tied to scenario & guidelines"
    )

    verdict: Literal["Appropriate", "Partially Appropriate", "Inappropriate"] = Field(
        ..., description="One of: Appropriate, Partially Appropriate, Inappropriate"
    )

    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Evaluator confidence (0–1)"
    )

    @field_validator('verdict')
    @classmethod
    def validate_verdict(cls, v):
        """Ensure verdict is one of the three allowed values"""
        valid_verdicts = ["Appropriate", "Partially Appropriate", "Inappropriate"]
        if v not in valid_verdicts:
            raise ValueError(f"Verdict must be one of {valid_verdicts}, got '{v}'")
        return v
