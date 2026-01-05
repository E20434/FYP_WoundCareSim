from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict

from app.services.session_manager import SessionManager
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.core.state_machine import Step
from app.utils.schema import EvaluatorResponse
from app.rag.retriever import retrieve_with_rag

router = APIRouter(prefix="/session", tags=["Session"])

# -------------------------------------------------
# Core services (Week-6 correct wiring)
# -------------------------------------------------

session_manager = SessionManager()
coordinator = Coordinator()
evaluation_service = EvaluationService(
    coordinator=coordinator,
    session_manager=session_manager
)

# -------------------------------------------------
# Request models
# -------------------------------------------------

class StartSessionRequest(BaseModel):
    scenario_id: str
    student_id: str


class EvalInput(BaseModel):
    session_id: str
    step: str
    user_input: Optional[str] = None
    evaluator_outputs: List[EvaluatorResponse]
    student_mcq_answers: Optional[Dict[str, str]] = None


# -------------------------------------------------
# Routes
# -------------------------------------------------

@router.post("/step")
async def session_step(payload: EvalInput):
    session = session_manager.get_session(payload.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # -------------------------------------------------
    # Step order enforcement (Week-6A)
    # -------------------------------------------------
    current_step = session["current_step"]

    if payload.step != current_step:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step order. Current step is '{current_step}'."
        )

    if session.get("locked_step"):
        return {
            "session_id": payload.session_id,
            "current_step": current_step,
            "session_locked": True,
            "message": "Session is locked due to safety violation."
        }

    # -------------------------------------------------
    # Optional RAG retrieval
    # -------------------------------------------------
    rag_result = None
    if payload.user_input:
        try:
            rag_result = await retrieve_with_rag(
                query=payload.user_input,
                scenario_id=session["scenario_id"]
            )
        except Exception as e:
            print(f"RAG retrieval failed: {str(e)}")

    # -------------------------------------------------
    # Evaluation aggregation (Week-6 correct call)
    # -------------------------------------------------
    evaluation = await evaluation_service.aggregate_evaluations(
        session_id=payload.session_id,
        evaluator_outputs=payload.evaluator_outputs,
        student_mcq_answers=payload.student_mcq_answers
    )

    decision = evaluation.get("decision", {})

    # -------------------------------------------------
    # SAFETY ENFORCEMENT (Week-6A)
    # -------------------------------------------------
    if decision.get("safety_blocked"):
        session_manager.lock_current_step(payload.session_id)

        return {
            "session_id": payload.session_id,
            "current_step": current_step,
            "session_locked": True,
            "evaluation": evaluation
        }

    # -------------------------------------------------
    # READINESS & RETRY ENFORCEMENT
    # -------------------------------------------------
    if decision.get("ready_for_next_step"):
        next_step = session_manager.advance_step(payload.session_id)
        session_manager.reset_attempts(payload.session_id)

        return {
            "session_id": payload.session_id,
            "current_step": current_step,
            "next_step": next_step,
            "evaluation": evaluation
        }

    # Retry path
    session_manager.increment_attempt(payload.session_id)

    return {
        "session_id": payload.session_id,
        "current_step": current_step,
        "retry_count": session["attempt_count"].get(current_step, 0),
        "evaluation": evaluation
    }
