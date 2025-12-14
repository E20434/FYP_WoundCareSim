from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional

from app.services.session_manager import SessionManager
from app.services.scenario_loader import load_scenario
from app.core.state_machine import Step, next_step
from app.core.coordinator import coordinate
from app.rag.retriever import retrieve_context

router = APIRouter(prefix="/session", tags=["Session"])

session_manager = SessionManager()


class StartSessionRequest(BaseModel):
    scenario_id: str
    student_id: str


class EvalInput(BaseModel):
    session_id: str
    step: str
    user_input: Optional[str] = None
    evaluator_outputs: List[Dict] = []


@router.post("/start")
def start_session(req: StartSessionRequest):
    try:
        scenario = load_scenario(req.scenario_id)

        session_id = session_manager.create_session(
            scenario_id=req.scenario_id,
            student_id=req.student_id,
            scenario_metadata=scenario
        )

        return {
            "session_id": session_id,
            "current_step": Step.HISTORY.value,
            "scenario_summary": {
                "scenario_id": scenario["scenario_id"],
                "title": scenario["title"],
                "patient_history": scenario["patient_history"],
                "wound_details": scenario["wound_details"]
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step")
def session_step(payload: EvalInput):
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    cur_step = session["current_step"]
    scenario_id = session["scenario_id"]

    rag_context = []

    if payload.user_input:
        rag_context = retrieve_context(
            query=payload.user_input,
            scenario_id=scenario_id,
            top_k=5
        )

        session_manager.add_rag_result(
            payload.session_id,
            {
                "step": cur_step,
                "query": payload.user_input,
                "results": rag_context
            }
        )

    # Aggregate evaluator outputs (Week-3 stub logic)
    evaluation = coordinate(payload.evaluator_outputs)

    session_manager.add_log(
        payload.session_id,
        {
            "step": cur_step,
            "user_input": payload.user_input,
            "evaluation": evaluation
        }
    )

    response = {
        "session_id": payload.session_id,
        "current_step": cur_step,
        "evaluation": evaluation
    }

    try:
        next_s = next_step(Step(cur_step))
        session["current_step"] = next_s.value
        response["next_step"] = next_s.value
    except Exception:
        pass

    if rag_context:
        response["rag_context"] = rag_context

    return response
