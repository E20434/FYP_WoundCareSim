from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.services.session_manager import SessionManager
from app.services.scenario_loader import load_scenario
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.core.state_machine import Step, next_step
from app.utils.schema import EvaluatorResponse
from app.rag.retriever import retrieve_with_rag


router = APIRouter(prefix="/session", tags=["Session"])

# Core services
session_manager = SessionManager()
coordinator = Coordinator()
evaluation_service = EvaluationService(coordinator=coordinator)


# ----------------------------
# Request models
# ----------------------------

class StartSessionRequest(BaseModel):
    scenario_id: str
    student_id: str


class EvalInput(BaseModel):
    session_id: str
    step: str
    user_input: Optional[str] = None
    evaluator_outputs: List[EvaluatorResponse]


# ----------------------------
# Routes
# ----------------------------

@router.post("/step")
async def session_step(payload: EvalInput):
    sid = payload.session_id
    session = session_manager.get_session(sid)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # ----------------------------
    # Step order enforcement
    # ----------------------------
    current_step = session["current_step"]

    if payload.step != current_step:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step order. Current step is '{current_step}'."
        )

    if session.get("locked"):
        raise HTTPException(
            status_code=403,
            detail="Session is locked due to safety violation."
        )

    scenario_id = session["scenario_id"]
    rag_result = None

    # ----------------------------
    # Optional RAG retrieval
    # ----------------------------
    if payload.user_input:
        try:
            rag_result = await retrieve_with_rag(
                query=payload.user_input,
                scenario_id=scenario_id,
                system_instruction=(
                    f"You are assisting in step '{current_step}' "
                    "of a surgically clean wound care procedure."
                ),
            )

            session_manager.add_rag_result(
                sid,
                {
                    "step": current_step,
                    "query": payload.user_input,
                    "llm_output": rag_result["text"],
                },
            )
        except Exception as e:
            print(f"RAG retrieval failed: {str(e)}")

    # ----------------------------
    # Evaluation aggregation
    # ----------------------------
    try:
        evaluation = await evaluation_service.aggregate_evaluations(
            evaluator_outputs=payload.evaluator_outputs,
            step=current_step,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation aggregation failed: {str(e)}",
        )

    # ----------------------------
    # Session logging
    # ----------------------------
    session_manager.add_log(
        sid,
        {
            "step": current_step,
            "user_input": payload.user_input,
            "evaluation": evaluation,
            "rag_used": rag_result is not None,
        },
    )

    # ----------------------------
    # SAFETY ENFORCEMENT (Week-6)
    # ----------------------------
    if evaluation.get("safety_blocked"):
        session_manager.lock_session(
            sid,
            reason="Unsafe clinical action detected"
        )

        return {
            "session_id": sid,
            "current_step": current_step,
            "locked": True,
            "evaluation": evaluation,
            "message": "Session locked due to unsafe clinical action."
        }

    # ----------------------------
    # READINESS & RETRY ENFORCEMENT
    # ----------------------------
    if evaluation.get("ready_for_next_step"):
        try:
            next_s = next_step(Step(current_step))
            session_manager.advance_step(sid, next_s.value)
        except Exception:
            next_s = None
    else:
        session_manager.increment_attempt(sid)

        if session_manager.exceeded_max_attempts(sid):
            session_manager.lock_session(
                sid,
                reason="Maximum retries exceeded"
            )

            return {
                "session_id": sid,
                "current_step": current_step,
                "locked": True,
                "evaluation": evaluation,
                "message": "Maximum retry attempts exceeded."
            }

        next_s = None

    # ----------------------------
    # Response (VR-ready)
    # ----------------------------
    response = {
        "session_id": sid,
        "current_step": current_step,
        "evaluation": evaluation,
        "ready_for_next_step": evaluation.get("ready_for_next_step", False),
        "locked": session.get("locked", False),
    }

    if rag_result:
        response["assistant_response"] = rag_result["text"]

    if next_s:
        response["next_step"] = next_s.value

    return response

