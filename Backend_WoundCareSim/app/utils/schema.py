from pydantic import BaseModel, Field
from typing import List


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

    verdict: str = Field(
        ..., description="Appropriate / Partially Appropriate / Inappropriate"
    )

    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Evaluator confidence (0–1)"
    )
