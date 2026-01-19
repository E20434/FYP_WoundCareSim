from typing import Dict, List, Any, Optional

from app.rag.retriever import retrieve_with_rag
from app.core.coordinator import Coordinator
from app.services.session_manager import SessionManager
from app.utils.mcq_evaluator import MCQEvaluator
from app.utils.schema import EvaluatorResponse
from app.services.conversation_manager import ConversationManager
from app.services.history_completeness_service import HistoryCompletenessService
from app.utils.feedback_schema import Feedback


class EvaluationService:
    """
    Orchestrates evaluator agents and aggregates feedback.

    Week-8:
    - Supports history completeness analysis
    - Produces structured, VR-ready feedback
    - Integrates staff nurse supervision (optional)
    - Feedback-only (no enforcement)
    """

    def __init__(
        self,
        coordinator: Coordinator,
        session_manager: SessionManager,
        staff_nurse_agent: Optional[Any] = None
    ):
        self.coordinator = coordinator
        self.session_manager = session_manager
        self.mcq_evaluator = MCQEvaluator()
        self.conversation_manager = ConversationManager()
        self.history_service = HistoryCompletenessService()
        self.staff_nurse_agent = staff_nurse_agent

    # ------------------------------------------------
    # Context preparation
    # ------------------------------------------------
    async def prepare_agent_context(
        self,
        session_id: str,
        step: str
    ) -> Dict[str, Any]:

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        scenario_metadata = session["scenario_metadata"]

        transcript = ""
        action_events: List[Dict[str, Any]] = []

        if step == "HISTORY":
            transcript = self.conversation_manager.get_aggregated_transcript(
                session_id=session_id,
                step=step
            )

        elif step in ["CLEANING", "DRESSING"]:
            action_events = session.get("action_events", [])

        rag_query = transcript or (
            f"{step} procedure actions" if action_events else "clinical nursing evaluation"
        )

        rag = await retrieve_with_rag(
            query=rag_query,
            scenario_id=session["scenario_id"]
        )

        return {
            "step": step,
            "scenario_metadata": scenario_metadata,
            "transcript": transcript,
            "action_events": action_events,
            "rag_context": rag.get("text", "")
        }

    # ------------------------------------------------
    # Evaluation aggregation + Week-8 extensions
    # ------------------------------------------------
    async def aggregate_evaluations(
        self,
        session_id: str,
        evaluator_outputs: List[EvaluatorResponse],
        student_mcq_answers: Optional[Dict[str, str]] = None,
        request_staff_permission: bool = False,
        student_request_text: Optional[str] = None
    ) -> Dict[str, Any]:

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        step = evaluator_outputs[0].step

        # ---- Coordinator aggregation ----
        coordinator_output = self.coordinator.aggregate(
            evaluations=evaluator_outputs,
            current_step=step
        )

        # ---- MCQ handling (ASSESSMENT only) ----
        if step == "ASSESSMENT":
            assessment_questions = session["scenario_metadata"].get(
                "assessment_questions", []
            )

            if assessment_questions and student_mcq_answers:
                mcq_result = self.mcq_evaluator.validate_mcq_answers(
                    student_answers=student_mcq_answers,
                    assessment_questions=assessment_questions
                )
            else:
                mcq_result = {
                    "total_questions": 0,
                    "correct_count": 0,
                    "feedback": [],
                    "summary": "No MCQ questions available"
                }

            coordinator_output["mcq_result"] = mcq_result

        # ---- HISTORY completeness analysis (Week-8 Task B) ----
        history_summary = None
        if step == "HISTORY":
            transcript = self.conversation_manager.get_aggregated_transcript(
                session_id=session_id,
                step=step
            )

            required_points = session["scenario_metadata"].get(
                "required_conversation_points", []
            )

            history_summary = self.history_service.analyze(
                transcript=transcript,
                required_points=required_points
            )

        # ---- Optional Staff Nurse interaction (Week-8) ----
        staff_nurse_response = None
        if (
            step == "HISTORY"
            and request_staff_permission
            and self.staff_nurse_agent
        ):
            staff_nurse_response = await self.staff_nurse_agent.respond(
                student_request=student_request_text or "",
                scenario_summary=session["scenario_metadata"],
                history_completeness=history_summary,
                evaluation_summary=coordinator_output
            )

        # ---- Build structured feedback ----
        feedback_payload = self._build_feedback(
            coordinator_output=coordinator_output,
            history_summary=history_summary,
            staff_nurse_response=staff_nurse_response
        )

        self.session_manager.store_last_evaluation(
            session_id=session_id,
            evaluation=feedback_payload
        )

        return feedback_payload

    # ------------------------------------------------
    # Feedback builder (VR-ready, text-only)
    # ------------------------------------------------
    def _build_feedback(
        self,
        coordinator_output: Dict[str, Any],
        history_summary: Optional[Dict[str, Any]],
        staff_nurse_response: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:

        feedback_items: List[Dict[str, Any]] = []

        # Evaluator summary feedback
        feedback_items.append(
            Feedback(
                text=coordinator_output.get("overall_feedback", ""),
                speaker="system",
                category="knowledge",
                timing="post_step"
            ).to_dict()
        )

        # History completeness feedback
        if history_summary and history_summary.get("missing_points"):
            feedback_items.append(
                Feedback(
                    text=history_summary["summary"],
                    speaker="system",
                    category="communication",
                    timing="post_step"
                ).to_dict()
            )

        # Staff nurse feedback
        if staff_nurse_response:
            feedback_items.append(
                Feedback(
                    text=staff_nurse_response.get("guidance", ""),
                    speaker="staff_nurse",
                    category="clinical",
                    timing="post_step"
                ).to_dict()
            )

        return {
            "step": coordinator_output.get("step"),
            "scores": coordinator_output.get("scores"),
            "readiness": coordinator_output.get("readiness"),
            "feedback": feedback_items,
            "permission_granted": (
                staff_nurse_response.get("permission_granted")
                if staff_nurse_response else None
            )
        }
