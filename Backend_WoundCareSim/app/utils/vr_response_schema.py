"""
VR Response Schema
Backend ↔ Unity Contract (Week-6 Correct)

This module defines ONLY the data contract between backend and Unity.
It contains:
- No business logic
- No action rules
- No UI mapping
- No VR assumptions

Week-6 scope:
- Session enforcement
- Readiness signaling
- Safety blocking
- Retry control
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


# -------------------------------------------------
# Enums
# -------------------------------------------------

class FeedbackSeverity(str, Enum):
    """
    Severity level of feedback sent to Unity.
    Unity decides how to present this.
    """
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SUCCESS = "success"


class StepStatus(str, Enum):
    """
    Backend-determined status of the current step.
    """
    IN_PROGRESS = "in_progress"
    REQUIRES_RETRY = "requires_retry"
    COMPLETED = "completed"
    BLOCKED = "blocked"


# -------------------------------------------------
# Feedback Model
# -------------------------------------------------

class FeedbackMessage(BaseModel):
    """
    A single feedback message for Unity.
    """
    text: str = Field(..., description="Feedback message text")
    severity: FeedbackSeverity = Field(..., description="Severity level")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Time feedback was generated"
    )
    voice_enabled: bool = Field(
        default=True,
        description="Whether this message may be spoken aloud"
    )


# -------------------------------------------------
# Core VR Session Response
# -------------------------------------------------

class VRSessionResponse(BaseModel):
    """
    Canonical response schema sent from backend to Unity.

    This schema communicates:
    - Current session state
    - Whether progression is allowed
    - Whether the session is blocked
    - Feedback for the student

    It does NOT:
    - Define allowed actions
    - Enforce action ordering
    - Contain UI logic
    """

    # Session identification
    session_id: str = Field(..., description="Unique session identifier")

    # Step state
    current_step: str = Field(
        ...,
        description="Current procedural step identifier (e.g. HISTORY)"
    )
    step_status: StepStatus = Field(
        ...,
        description="Backend-determined step status"
    )

    # Progression control
    ready_for_next_step: bool = Field(
        ...,
        description="Whether the student may advance to the next step"
    )
    session_locked: bool = Field(
        default=False,
        description="Whether the session is locked due to safety violation"
    )

    # Retry tracking
    retry_count: int = Field(
        default=0,
        description="Number of attempts made for this step"
    )
    max_retries_reached: bool = Field(
        default=False,
        description="Whether retry limit has been reached"
    )

    # Feedback
    feedback: List[FeedbackMessage] = Field(
        default_factory=list,
        description="Feedback messages for Unity to display or speak"
    )

    # Optional extensible metadata (future-safe)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional backend context (non-breaking)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_123",
                "current_step": "CLEANING",
                "step_status": "requires_retry",
                "ready_for_next_step": False,
                "session_locked": False,
                "retry_count": 1,
                "max_retries_reached": False,
                "feedback": [
                    {
                        "text": "You must wash your hands before cleaning the wound.",
                        "severity": "warning",
                        "voice_enabled": True
                    }
                ],
                "metadata": {}
            }
        }
