from typing import Dict, List, Any, Optional

from app.rag.retriever import retrieve_with_rag
from app.core.coordinator import Coordinator
from app.services.session_manager import SessionManager
from app.core.state_machine import Step

from app.utils.mcq_evaluator import MCQEvaluator
from app.utils.schema import EvaluatorResponse
from app.services.conversation_manager import ConversationManager
from app.utils.feedback_schema import Feedback

from app.agents.feedback_narrator_agent import FeedbackNarratorAgent


class EvaluationService:
    """
    Evaluation Orchestrator - Generates narrated feedback for students
    
    Key responsibilities:
    1. Run evaluator agents (Communication, Knowledge for HISTORY; None for CLEANING_AND_DRESSING)
    2. Aggregate into scores (via Coordinator) 
    3. Generate narrated feedback paragraph (via FeedbackNarrator) - NOT for ASSESSMENT
    4. Return student-facing feedback + debugging data
    
    NO blocking, NO enforcement - purely formative feedback
    
    NOTE: 
    - ASSESSMENT step gets NO narration (MCQ explanations are sufficient)
    - CLEANING_AND_DRESSING step gets NO final evaluation (real-time feedback only)
    """

    def __init__(
        self,
        coordinator: Coordinator,
        session_manager: SessionManager,
        staff_nurse_agent: Optional[Any] = None,
        feedback_narrator_agent: Optional[FeedbackNarratorAgent] = None,
    ):
        self.coordinator = coordinator
        self.session_manager = session_manager
        self.mcq_evaluator = MCQEvaluator()
        self.conversation_manager = ConversationManager()
        self.staff_nurse_agent = staff_nurse_agent
        self.feedback_narrator_agent = feedback_narrator_agent

    # ------------------------------------------------
    # Context preparation for evaluator agents
    # ------------------------------------------------
    async def prepare_agent_context(
        self,
        session_id: str,
        step: str
    ) -> Dict[str, Any]:
        """
        Prepare evaluation context for agent evaluation.
        
        Includes:
        - Scenario metadata
        - Student input (transcript or actions)
        - RAG guidelines specific to the step
        """

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        scenario_metadata = session["scenario_metadata"]

        transcript = ""
        action_events: List[Dict[str, Any]] = []

        if step == Step.HISTORY.value:
            transcript = self.conversation_manager.get_aggregated_transcript(
                session_id=session_id,
                step=step
            )

        elif step == Step.CLEANING_AND_DRESSING.value:
            action_events = session.get("action_events", [])

        # Step-specific RAG queries for accurate guideline retrieval
        # Note: ASSESSMENT step uses MCQ-only evaluation (no RAG needed)
        rag_query_map = {
            Step.HISTORY.value: "patient history taking guidelines nursing communication assessment questions",
            Step.CLEANING_AND_DRESSING.value: "wound cleaning and dressing preparation procedure protocol hand hygiene aseptic technique",
        }
        
        rag_context = ""
        if step in rag_query_map:
            rag_query = rag_query_map.get(step)
            rag = await retrieve_with_rag(
                query=rag_query,
                scenario_id=session["scenario_id"]
            )
            rag_context = rag.get("text", "")

        return {
            "step": step,
            "scenario_metadata": scenario_metadata,
            "transcript": transcript,
            "action_events": action_events,
            "rag_context": rag_context
        }

    # ------------------------------------------------
    # Aggregation + narrated feedback generation
    # ------------------------------------------------
    async def aggregate_evaluations(
        self,
        session_id: str,
        evaluator_outputs: List[EvaluatorResponse],
        student_mcq_answers: Optional[Dict[str, str]] = None,
        student_message_to_nurse: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aggregate evaluations and generate student-facing feedback.
        
        Returns:
        - scores: Numeric indicators (for reporting/display) - ONLY for HISTORY
        - narrated_feedback: Single paragraph for student - ONLY for HISTORY
        - mcq_result: MCQ evaluation (ASSESSMENT step only, NO narration)
        - raw_feedback: Agent breakdowns (for terminal debugging)
        
        NOTE: 
        - For ASSESSMENT: Only MCQ results, NO narration
        - For CLEANING_AND_DRESSING: Returns minimal data (no scores, no narration)
        """

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        current_step = Step(session["current_step"])

        # ------------------------------------------------
        # CLEANING_AND_DRESSING: No final evaluation
        # ------------------------------------------------
        if current_step == Step.CLEANING_AND_DRESSING:
            payload = {
                "step": current_step.value,
                "scores": None,  # No scores
                "narrated_feedback": None,  # No narration
                "raw_feedback": [],  # No feedback
            }
            
            self.session_manager.store_last_evaluation(
                session_id=session_id,
                evaluation=payload
            )
            
            return payload

        # ------------------------------------------------
        # ASSESSMENT: MCQ only, NO narration
        # ------------------------------------------------
        if current_step == Step.ASSESSMENT:
            questions = session["scenario_metadata"].get(
                "assessment_questions", []
            )

            if not questions:
                mcq_result = {
                    "total_questions": 0,
                    "correct_count": 0,
                    "score": 0.0,
                    "feedback": [],
                    "summary": "No MCQ questions available in scenario"
                }
            elif not student_mcq_answers or len(student_mcq_answers) == 0:
                mcq_result = {
                    "total_questions": len(questions),
                    "correct_count": 0,
                    "score": 0.0,
                    "feedback": [
                        {
                            "question_id": q.get("id"),
                            "question": q.get("question", ""),
                            "status": "not_answered",
                            "student_answer": None,
                            "correct_answer": q.get("correct_answer"),
                            "explanation": "This question was not answered."
                        }
                        for q in questions
                    ],
                    "summary": f"0/{len(questions)} questions answered - Assessment incomplete"
                }
            else:
                mcq_result = self.mcq_evaluator.validate_mcq_answers(
                    student_answers=student_mcq_answers,
                    assessment_questions=questions
                )

            payload = {
                "step": current_step.value,
                "mcq_result": mcq_result,
                "scores": None,  # No agent scores for MCQ step
                "narrated_feedback": None,  # NO NARRATION for assessment
                "raw_feedback": [],  # No agent feedback
            }
            
            self.session_manager.store_last_evaluation(
                session_id=session_id,
                evaluation=payload
            )
            
            return payload

        # ------------------------------------------------
        # HISTORY: Normal evaluation with narration
        # ------------------------------------------------
        
        # ---- Coordinator aggregation (numeric scores) ----
        coordinator_output = self.coordinator.aggregate(
            evaluations=evaluator_outputs,
            current_step=current_step.value
        )

        # ------------------------------------------------
        # Build RAW feedback from evaluator agents
        # (Used for narration, not shown directly to student)
        # ------------------------------------------------
        raw_feedback_items: List[Dict[str, Any]] = []

        for ev in evaluator_outputs:
            agent_text_parts = []

            if ev.strengths:
                agent_text_parts.append(
                    "Strengths: " + ", ".join(ev.strengths)
                )

            if ev.issues_detected:
                agent_text_parts.append(
                    "Areas for improvement: " + ", ".join(ev.issues_detected)
                )

            agent_text_parts.append(ev.explanation)

            raw_feedback_items.append(
                Feedback(
                    text=" ".join(agent_text_parts),
                    speaker="system",
                    category=(
                        "communication"
                        if ev.agent_name == "CommunicationAgent"
                        else "knowledge"
                        if ev.agent_name == "KnowledgeAgent"
                        else "clinical"
                    ),
                    timing="post_step"
                ).to_dict()
            )

        # ------------------------------------------------
        # Generate NARRATED feedback (student-facing paragraph)
        # ------------------------------------------------
        narrated_feedback_dict = None

        if self.feedback_narrator_agent and raw_feedback_items:
            try:
                narrated_feedback_obj = await self.feedback_narrator_agent.narrate(
                    raw_feedback=raw_feedback_items,
                    step=current_step.value
                )
                if narrated_feedback_obj:
                    narrated_feedback_dict = narrated_feedback_obj.model_dump()
            except Exception as e:
                # Fail-safe: narration must never break evaluation
                print(f"⚠️  Narration failed: {e}")
                # Fallback to simple concatenation
                narrated_feedback_dict = {
                    "speaker": "system",
                    "step": current_step.value,
                    "message_text": " ".join([item["text"] for item in raw_feedback_items])
                }

        # ------------------------------------------------
        # Final payload for HISTORY step
        # ------------------------------------------------
        payload = {
            "step": current_step.value,
            "scores": coordinator_output.get("scores"),
            "narrated_feedback": narrated_feedback_dict,  # Student sees this
            "raw_feedback": raw_feedback_items,  # Debugging only
        }

        # Store for session history
        self.session_manager.store_last_evaluation(
            session_id=session_id,
            evaluation=payload
        )

        return payload
