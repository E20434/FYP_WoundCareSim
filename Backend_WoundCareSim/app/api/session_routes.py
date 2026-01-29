from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from app.services.session_manager import SessionManager
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.core.state_machine import Step
from app.services.action_event_service import ActionEventService

from app.agents.patient_agent import PatientAgent
from app.agents.communication_agent import CommunicationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.clinical_agent import ClinicalAgent
from app.agents.staff_nurse_agent import StaffNurseAgent
from app.agents.feedback_narrator_agent import FeedbackNarratorAgent

from app.utils.mcq_evaluator import MCQEvaluator

router = APIRouter(prefix="/session", tags=["Session"])

# -------------------------------------------------
# Core services (singletons)
# -------------------------------------------------

session_manager = SessionManager()
coordinator = Coordinator()

evaluation_service = EvaluationService(
    coordinator=coordinator,
    session_manager=session_manager,
    staff_nurse_agent=StaffNurseAgent(),
    feedback_narrator_agent=FeedbackNarratorAgent(),
)

action_event_service = ActionEventService(session_manager)

patient_agent = PatientAgent()
conversation_manager = evaluation_service.conversation_manager

communication_agent = CommunicationAgent()
knowledge_agent = KnowledgeAgent()
clinical_agent = ClinicalAgent()
mcq_evaluator = MCQEvaluator()

# -------------------------------------------------
# Request models
# -------------------------------------------------

class StartSessionRequest(BaseModel):
    scenario_id: str
    student_id: str


class MessageInput(BaseModel):
    session_id: str
    message: str


class StepInput(BaseModel):
    session_id: str
    step: str
    user_input: Optional[str] = None
    student_mcq_answers: Optional[Dict[str, str]] = None
    # Note: Actions are now handled by separate /action endpoint


class StaffNurseInput(BaseModel):
    session_id: str
    message: str


class MCQAnswerInput(BaseModel):
    session_id: str
    question_id: str
    answer: str


class ActionInput(BaseModel):
    session_id: str
    action_type: str
    metadata: Optional[Dict[str, Any]] = None


# -------------------------------------------------
# Routes
# -------------------------------------------------

@router.post("/start")
def start_session(payload: StartSessionRequest):
    """
    Start a new training session.
    """
    session_id = session_manager.create_session(
        scenario_id=payload.scenario_id,
        student_id=payload.student_id
    )
    return {"session_id": session_id}


@router.get("/{session_id}")
def get_session_info(session_id: str):
    """
    Get current session state and information.
    NEW: Added for Test UI to fetch session details.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Return session info with scenario metadata
    return {
        "session_id": session_id,
        "scenario_id": session["scenario_id"],
        "student_id": session["student_id"],
        "current_step": session["current_step"],
        "scenario_metadata": session["scenario_metadata"],
        "last_evaluation": session.get("last_evaluation"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at")
    }


@router.post("/message")
async def send_message(payload: MessageInput):
    """
    Multi-turn student ↔ patient conversation.
    HISTORY step only.
    """
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["current_step"] != Step.HISTORY.value:
        raise HTTPException(
            status_code=400,
            detail="Conversation allowed only during HISTORY step"
        )

    scenario_meta = session["scenario_metadata"]
    patient_history = scenario_meta["patient_history"]

    conversation_manager.add_turn(
        payload.session_id,
        Step.HISTORY.value,
        "student",
        payload.message
    )

    response = await patient_agent.respond(
        patient_history=patient_history,
        conversation_history=conversation_manager.conversations[payload.session_id][Step.HISTORY.value],
        student_message=payload.message
    )

    conversation_manager.add_turn(
        payload.session_id,
        Step.HISTORY.value,
        "patient",
        response
    )

    return {"patient_response": response}


@router.post("/staff-nurse")
async def ask_staff_nurse(payload: StaffNurseInput):
    """
    Ask the staff nurse for guidance (available at any time).
    NEW: Added for Test UI staff nurse interaction.
    
    The staff nurse provides high-level guidance only.
    Does not evaluate, approve, or block the student.
    """
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    current_step = session["current_step"]
    
    # Determine next step
    try:
        from app.core.state_machine import next_step as get_next_step
        next_step_enum = get_next_step(Step(current_step))
        next_step_str = next_step_enum.value
    except ValueError:
        next_step_str = None
    
    staff_nurse = StaffNurseAgent()
    response = await staff_nurse.respond(
        student_input=payload.message,
        current_step=current_step,
        next_step=next_step_str
    )
    
    return {
        "staff_nurse_response": response,
        "current_step": current_step
    }


@router.post("/action")
def record_action(payload: ActionInput):
    """
    Record a clinical action (CLEANING/DRESSING steps).
    NEW: Added for Test UI to record actions without completing step.
    
    Actions are accumulated and evaluated when step completes.
    """
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    current_step = session["current_step"]
    
    # Only allow actions for CLEANING and DRESSING steps
    if current_step not in [Step.CLEANING.value, Step.DRESSING.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Actions not allowed in {current_step} step"
        )
    
    # Record the action
    result = action_event_service.record_action(
        session_id=payload.session_id,
        action_type=payload.action_type,
        step=current_step,
        metadata=payload.metadata
    )
    
    return {
        "action_recorded": True,
        "action_type": payload.action_type,
        "step": current_step,
        "timestamp": result.get("timestamp"),
        "total_actions": len(session.get("action_events", []))
    }


@router.post("/mcq-answer")
def answer_mcq_question(payload: MCQAnswerInput):
    """
    Evaluate a single MCQ answer immediately.
    NEW: Added for Test UI per-question feedback.
    
    Returns immediate feedback without LLM evaluation.
    """
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session["current_step"] != Step.ASSESSMENT.value:
        raise HTTPException(
            status_code=400,
            detail="MCQ answers allowed only during ASSESSMENT step"
        )
    
    # Get the question from scenario metadata
    questions = session["scenario_metadata"].get("assessment_questions", [])
    question = next((q for q in questions if q.get("id") == payload.question_id), None)
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Check if answer is correct
    correct_answer = question.get("correct_answer")
    is_correct = payload.answer == correct_answer
    
    # Store the answer in session for final evaluation
    if "mcq_answers" not in session:
        session["mcq_answers"] = {}
    session["mcq_answers"][payload.question_id] = payload.answer
    
    return {
        "question_id": payload.question_id,
        "question": question.get("question"),
        "student_answer": payload.answer,
        "correct_answer": correct_answer,
        "is_correct": is_correct,
        "explanation": question.get("explanation", "No explanation provided."),
        "status": "correct" if is_correct else "incorrect"
    }


@router.post("/step")
async def run_step(payload: StepInput):
    """
    Unified step handler (Week-9 FINAL - ASSESSMENT Agent Evaluation Removed).
    
    Handles step completion and evaluation for all steps.
    
    ASSESSMENT step now uses MCQ-only evaluation (no agents).
    """
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    current_step = session["current_step"]

    if payload.step != current_step:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step. Current step is '{current_step}'."
        )

    # ---------------------------------------------
    # Prepare evaluation context
    # ---------------------------------------------
    context = await evaluation_service.prepare_agent_context(
        session_id=payload.session_id,
        step=current_step
    )

    evaluator_outputs = []

    # ---------------------------------------------
    # Step-specific evaluation
    # ---------------------------------------------
    if current_step == Step.HISTORY.value:
        evaluator_outputs.append(
            await communication_agent.evaluate(
                current_step=current_step,
                student_input=context["transcript"],
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
        )
        evaluator_outputs.append(
            await knowledge_agent.evaluate(
                current_step=current_step,
                student_input=context["transcript"],
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
        )

    elif current_step == Step.ASSESSMENT.value:
        # ASSESSMENT step uses MCQ-only evaluation (no agents)
        # Evaluator outputs remain empty for this step
        # MCQ evaluation is handled separately in aggregate_evaluations
        pass

    else:  # CLEANING / DRESSING
        evaluator_outputs.append(
            await clinical_agent.evaluate(
                current_step=current_step,
                student_input=str(context["action_events"]),
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
        )

    # ---------------------------------------------
    # Aggregate + narrate feedback
    # ---------------------------------------------
    # For ASSESSMENT, use stored answers
    if current_step == Step.ASSESSMENT.value:
        mcq_answers = session.get("mcq_answers", payload.student_mcq_answers or {})
    else:
        mcq_answers = payload.student_mcq_answers
    
    evaluation = await evaluation_service.aggregate_evaluations(
        session_id=payload.session_id,
        evaluator_outputs=evaluator_outputs,
        student_mcq_answers=mcq_answers,
        student_message_to_nurse=payload.user_input
    )

    # ---------------------------------------------
    # Cleanup: Clear step-specific data after evaluation
    # ---------------------------------------------
    if current_step == Step.HISTORY.value:
        # Clear conversation history
        conversation_manager.clear_step(payload.session_id, Step.HISTORY.value)
    
    elif current_step == Step.ASSESSMENT.value:
        # Clear MCQ answers
        session = session_manager.get_session(payload.session_id)
        if session:
            session["mcq_answers"] = {}
    
    elif current_step in [Step.CLEANING.value, Step.DRESSING.value]:
        # Clear action events
        session = session_manager.get_session(payload.session_id)
        if session:
            session["action_events"] = []

    # ---------------------------------------------
    # Advance step (always allowed)
    # ---------------------------------------------
    next_step = session_manager.advance_step(payload.session_id)

    return {
        "session_id": payload.session_id,
        "current_step": current_step,
        "next_step": next_step,
        "evaluation": evaluation
    }
