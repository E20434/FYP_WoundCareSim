"""
VR Response Schema
Backend ↔ Unity Contract Definition

This module defines the standardized response format that Unity VR clients
will receive from the backend. This contract is designed to be:
- Non-breaking: Future additions won't break existing Unity implementations
- Actionable: Unity knows exactly what to display, block, and enable
- Safety-first: Critical safety information is always included
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class FeedbackSeverity(str, Enum):
    """Severity levels for feedback messages"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SUCCESS = "success"


class ActionType(str, Enum):
    """Standard action types that Unity can send and backend can validate"""
    # Hygiene actions
    WASH_HANDS = "WASH_HANDS"
    APPLY_GLOVES = "APPLY_GLOVES"
    REMOVE_GLOVES = "REMOVE_GLOVES"
    
    # Assessment actions
    ASSESS_PATIENT = "ASSESS_PATIENT"
    CHECK_VITALS = "CHECK_VITALS"
    INSPECT_WOUND = "INSPECT_WOUND"
    
    # Wound care actions
    CLEAN_WOUND = "CLEAN_WOUND"
    APPLY_ANTISEPTIC = "APPLY_ANTISEPTIC"
    APPLY_DRESSING = "APPLY_DRESSING"
    SECURE_DRESSING = "SECURE_DRESSING"
    
    # Documentation
    DOCUMENT_PROCEDURE = "DOCUMENT_PROCEDURE"
    
    # Communication
    SPEAK_TO_PATIENT = "SPEAK_TO_PATIENT"
    CALL_SUPERVISOR = "CALL_SUPERVISOR"


class StepStatus(str, Enum):
    """Current status of a training step"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    REQUIRES_RETRY = "requires_retry"


class FeedbackMessage(BaseModel):
    """Individual feedback message for Unity to display"""
    text: str = Field(..., description="Feedback text to display/speak to student")
    severity: FeedbackSeverity = Field(..., description="How critical this feedback is")
    timestamp: datetime = Field(default_factory=datetime.now, description="When this feedback was generated")
    voice_enabled: bool = Field(default=True, description="Whether this should be spoken aloud in VR")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Remember to wash your hands before putting on gloves",
                "severity": "warning",
                "timestamp": "2025-01-04T10:30:00Z",
                "voice_enabled": True
            }
        }


class ActionConstraint(BaseModel):
    """Defines why an action is blocked or required"""
    action: ActionType
    reason: str = Field(..., description="Human-readable explanation")
    required_before: Optional[List[ActionType]] = Field(
        default=None,
        description="Actions that must be completed first"
    )


class VRSessionResponse(BaseModel):
    """
    Primary response schema for Unity VR client.
    This is what Unity receives after each action or step request.
    """
    
    # Session State
    session_id: str = Field(..., description="Unique session identifier")
    current_step: int = Field(..., description="Current step number (0-indexed)")
    step_name: str = Field(..., description="Human-readable step name")
    step_status: StepStatus = Field(..., description="Current status of this step")
    
    # Progression Control
    ready_for_next_step: bool = Field(
        ..., 
        description="Whether student can advance to next step"
    )
    session_locked: bool = Field(
        default=False,
        description="Whether entire session is locked due to critical safety violation"
    )
    retry_count: int = Field(
        default=0,
        description="Number of times student has retried this step"
    )
    max_retries_reached: bool = Field(
        default=False,
        description="Whether student has exhausted retry attempts"
    )
    
    # Action Management
    allowed_actions: List[ActionType] = Field(
        default_factory=list,
        description="Actions student can currently perform"
    )
    blocked_actions: List[ActionConstraint] = Field(
        default_factory=list,
        description="Actions that are blocked with reasons"
    )
    next_expected_action: Optional[ActionType] = Field(
        default=None,
        description="The next action backend expects (guidance for Unity UI)"
    )
    
    # Feedback
    feedback: List[FeedbackMessage] = Field(
        default_factory=list,
        description="Feedback messages to display/speak"
    )
    
    # Performance Summary
    performance_score: Optional[float] = Field(
        default=None,
        description="Current performance score (0-100), if applicable"
    )
    safety_violations: List[str] = Field(
        default_factory=list,
        description="List of safety violations in this step"
    )
    
    # Additional Context
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context data for Unity (extensible)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "current_step": 2,
                "step_name": "Hand Hygiene",
                "step_status": "in_progress",
                "ready_for_next_step": False,
                "session_locked": False,
                "retry_count": 1,
                "max_retries_reached": False,
                "allowed_actions": ["WASH_HANDS", "APPLY_GLOVES"],
                "blocked_actions": [
                    {
                        "action": "CLEAN_WOUND",
                        "reason": "Must complete hand hygiene first",
                        "required_before": ["WASH_HANDS", "APPLY_GLOVES"]
                    }
                ],
                "next_expected_action": "WASH_HANDS",
                "feedback": [
                    {
                        "text": "Good start! Now wash your hands thoroughly.",
                        "severity": "info",
                        "voice_enabled": True
                    }
                ],
                "performance_score": 75.5,
                "safety_violations": [],
                "metadata": {
                    "total_steps": 8,
                    "estimated_time_remaining": "5 minutes"
                }
            }
        }


class VRActionRequest(BaseModel):
    """
    Request schema when Unity sends an action to backend.
    This is what Unity SENDS to the backend.
    """
    session_id: str = Field(..., description="Current session ID")
    action_type: ActionType = Field(..., description="Action student performed")
    step: int = Field(..., description="Current step number")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When action was performed in VR"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional action context (e.g., duration, accuracy metrics)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "action_type": "WASH_HANDS",
                "step": 2,
                "timestamp": "2025-01-04T10:30:00Z",
                "metadata": {
                    "duration_seconds": 25,
                    "completion_percentage": 95
                }
            }
        }


class VRSessionStartRequest(BaseModel):
    """Request to start a new VR training session"""
    student_id: str = Field(..., description="Unique student identifier")
    scenario_id: str = Field(..., description="Training scenario to load")
    difficulty_level: Optional[str] = Field(
        default="beginner",
        description="Difficulty level (beginner/intermediate/advanced)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "student_456",
                "scenario_id": "wound_care_basic",
                "difficulty_level": "beginner"
            }
        }


# Helper Functions for Route Implementation

def map_coordinator_to_vr_response(
    coordinator_output: Dict[str, Any],
    session_state: Dict[str, Any]
) -> VRSessionResponse:
    """
    Maps internal coordinator output to clean VR response.
    
    This function should be called in your session routes to convert
    the internal backend evaluation into Unity-friendly format.
    
    Args:
        coordinator_output: Output from EvaluationService/Coordinator
        session_state: Current session state info
        
    Returns:
        VRSessionResponse ready to send to Unity
    """
    
    # Extract feedback with severity mapping
    feedback_messages = []
    for fb in coordinator_output.get("feedback", []):
        # Map coordinator severity to VR severity
        severity = FeedbackSeverity.WARNING
        if "critical" in fb.lower() or "safety" in fb.lower():
            severity = FeedbackSeverity.CRITICAL
        elif "good" in fb.lower() or "correct" in fb.lower():
            severity = FeedbackSeverity.SUCCESS
        else:
            severity = FeedbackSeverity.INFO
            
        feedback_messages.append(
            FeedbackMessage(
                text=fb,
                severity=severity,
                voice_enabled=True
            )
        )
    
    # Determine blocked actions based on safety rules
    blocked = []
    safety_violations = coordinator_output.get("safety_violations", [])
    
    # Build response
    return VRSessionResponse(
        session_id=session_state.get("session_id"),
        current_step=session_state.get("current_step", 0),
        step_name=session_state.get("step_name", "Unknown Step"),
        step_status=StepStatus.IN_PROGRESS,
        ready_for_next_step=coordinator_output.get("ready_for_next_step", False),
        session_locked=coordinator_output.get("session_locked", False),
        retry_count=session_state.get("retry_count", 0),
        max_retries_reached=session_state.get("retry_count", 0) >= 3,
        allowed_actions=session_state.get("allowed_actions", []),
        blocked_actions=blocked,
        next_expected_action=coordinator_output.get("next_expected_action"),
        feedback=feedback_messages,
        performance_score=coordinator_output.get("performance_score"),
        safety_violations=safety_violations,
        metadata={
            "total_steps": session_state.get("total_steps", 0),
            "step_completion_percentage": coordinator_output.get("completion_percentage", 0)
        }
    )


def create_safety_block_response(
    session_id: str,
    current_step: int,
    violation_reason: str
) -> VRSessionResponse:
    """
    Creates a session-locked response for critical safety violations.
    Use this when student performs an action that requires immediate intervention.
    """
    return VRSessionResponse(
        session_id=session_id,
        current_step=current_step,
        step_name="Safety Block",
        step_status=StepStatus.BLOCKED,
        ready_for_next_step=False,
        session_locked=True,
        allowed_actions=[],
        blocked_actions=[],
        feedback=[
            FeedbackMessage(
                text=f"Training paused: {violation_reason}",
                severity=FeedbackSeverity.CRITICAL,
                voice_enabled=True
            ),
            FeedbackMessage(
                text="Please speak with your instructor before continuing.",
                severity=FeedbackSeverity.CRITICAL,
                voice_enabled=True
            )
        ],
        safety_violations=[violation_reason]
    )