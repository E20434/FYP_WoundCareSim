import json

from pydantic import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

class ClinicalAgent(BaseAgent):
    """
    Evaluates the student's clinical and procedural correctness.
    Now handles the combined cleaning and dressing preparation step.
    Provides both real-time and final feedback.
    
    NOTE: Actions and sequences are defined in RAG guidelines, not hardcoded.
    """

    def __init__(self):
        super().__init__()

    def get_real_time_feedback(
        self,
        action_type: str,
        performed_actions: list[str]
    ) -> dict:
        """
        Provides immediate feedback when an action is performed.
        Simple acknowledgment - detailed validation happens in final evaluation with RAG.
        """
        
        # Simple real-time acknowledgment
        # RAG will provide detailed evaluation during final assessment
        action_name = self._format_action_name(action_type)
        
        return {
            "status": "success",
            "message": f"{action_name.capitalize()} recorded.",
            "action_type": action_type,
            "total_actions_so_far": len(performed_actions) + 1
        }

    def _format_action_name(self, action_type: str) -> str:
        """Convert action_type to readable name"""
        # Remove 'action_' prefix and replace underscores with spaces
        return action_type.replace("action_", "").replace("_", " ")

    async def evaluate(
        self,
        current_step: str,
        student_input: str,
        scenario_metadata: dict,
        rag_response: str,
    ) -> EvaluatorResponse:
        """
        Evaluate clinical correctness and return a structured object.
        Now handles combined cleaning and dressing preparation.
        
        Uses RAG guidelines to determine:
        - Required actions
        - Mandatory actions
        - Correct sequence
        - Evaluation criteria
        """

        # Parse action events
        try:
            action_events = json.loads(student_input) if student_input else []
        except json.JSONDecodeError:
            action_events = []

        # CRITICAL: Check for empty input (no actions performed)
        if not action_events:
            return EvaluatorResponse(
                agent_name="ClinicalAgent",
                step=current_step,
                strengths=[],
                issues_detected=[
                    "No preparation actions performed",
                    "Required preparation steps were not completed",
                    "Critical patient safety protocols not followed"
                ],
                explanation=f"The student did not perform any preparation actions for cleaning and dressing. According to clinical guidelines, proper preparation including hand hygiene, trolley preparation, solution verification, and material verification is required before wound care. Without proper preparation, patient safety cannot be ensured.",
                verdict="Inappropriate",
                confidence=1.0
            )

        system_prompt = (
            "You are a nursing clinical skills evaluator for wound care preparation.\n\n"
            "ROLE: Evaluate ONLY preparation actions for cleaning and dressing - NOT actual wound cleaning or dressing application.\n\n"
            "IMPORTANT: Use the REFERENCE GUIDELINES provided to determine:\n"
            "1. What actions are required\n"
            "2. Which actions are mandatory vs optional\n"
            "3. What the correct sequence should be\n"
            "4. How to evaluate completeness and safety\n\n"
            "CRITICAL EVALUATION AREAS:\n\n"
            "1. INFECTION CONTROL (Hand Hygiene)\n"
            "   - Was hand hygiene performed at appropriate times?\n"
            "   - Was hand hygiene done before touching equipment?\n"
            "   - Was hand hygiene done after cleaning tasks?\n"
            "   - Why critical: Prevents cross-contamination\n\n"
            "2. STAFF NURSE VERIFICATION (Check guidelines for requirements)\n"
            "   - Were solutions verified with staff nurse?\n"
            "   - Were sterile materials verified with staff nurse?\n"
            "   - Were expiration dates and integrity checked?\n"
            "   - Why critical: Prevents medication errors and ensures sterility\n\n"
            "3. ACTION SEQUENCING\n"
            "   - Were actions performed in logical, safe order?\n"
            "   - Were there any sequence violations that could cause contamination?\n"
            "   - Why critical: Prevents cross-contamination and ensures safety\n\n"
            "4. COMPLETENESS\n"
            "   - Were all required actions performed per guidelines?\n"
            "   - Were any critical steps skipped?\n"
            "   - Why critical: Incomplete preparation compromises patient safety\n\n"
            "EVALUATION RULES:\n"
            "- Base evaluation strictly on REFERENCE GUIDELINES provided\n"
            "- Base evaluation ONLY on actual actions performed by student\n"
            "- Do NOT assume or invent actions\n"
            "- Missing hand hygiene = MAJOR infection control violation\n"
            "- Missing staff nurse verification = MEDICATION SAFETY violation\n"
            "- Incorrect sequence = CROSS-CONTAMINATION risk\n"
            "- This is PREPARATION ONLY - no actual wound contact expected\n\n"
            "You MUST respond with valid JSON matching this structure:\n"
            "{\n"
            '  "agent_name": "ClinicalAgent",\n'
            '  "step": "cleaning_and_dressing",\n'
            '  "strengths": ["List of correctly performed preparation actions..."],\n'
            '  "issues_detected": ["List of missed actions, sequence violations, or safety issues..."],\n'
            '  "explanation": "Detailed assessment prioritizing patient safety and referencing guidelines...",\n'
            '  "verdict": "Appropriate" | "Partially Appropriate" | "Inappropriate",\n'
            '  "confidence": 0.0 to 1.0\n'
            "}\n\n"
            "VERDICT GUIDELINES (Use reference guidelines to determine thresholds):\n"
            "- Appropriate: All required actions completed in correct sequence, no safety violations\n"
            "- Partially Appropriate: Most actions completed but missing 1-2 non-critical actions OR minor sequence issues, mandatory actions present\n"
            "- Inappropriate: Missing mandatory actions OR major sequence violations OR multiple required actions missing\n\n"
            "Strict Rules:\n"
            "- Output RAW JSON only. No markdown formatting.\n"
            "- Prioritize patient safety above all else.\n"
            "- Base evaluation ONLY on the actual actions provided.\n"
            "- Do NOT assume or invent student actions.\n"
            "- Reference the guidelines when explaining issues.\n"
        )

        user_prompt = (
            f"CURRENT PROCEDURE STEP: {current_step}\n\n"
            f"STUDENT ACTIONS PERFORMED:\n{json.dumps(action_events, indent=2)}\n\n"
            f"SCENARIO CONTEXT:\n"
            f"Wound: {scenario_metadata.get('wound_details', {}).get('wound_type', 'Unknown')} on "
            f"{scenario_metadata.get('wound_details', {}).get('location', 'Unknown')}\n"
            f"Prescribed cleaning solution: {scenario_metadata.get('wound_details', {}).get('cleaning_solution', 'As per guidelines')}\n"
            f"Prescribed dressing type: {scenario_metadata.get('wound_details', {}).get('dressing_type', 'As per guidelines')}\n\n"
            f"REFERENCE GUIDELINES (USE THESE TO EVALUATE):\n"
            f"{rag_response}\n\n"
            "Based on the reference guidelines above:\n"
            "1. Identify what actions are required\n"
            "2. Determine which actions are mandatory\n"
            "3. Check if actions were performed in correct sequence\n"
            "4. Evaluate completeness and safety compliance\n"
            "5. Compare student's actions against guideline requirements\n\n"
            "Provide evaluation in JSON format."
        )

        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        try:
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            response_data = json.loads(clean_json)
            
            # Enforce consistency
            response_data["step"] = current_step
            response_data["agent_name"] = "ClinicalAgent"

            return EvaluatorResponse(**response_data)
        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            print(f"Agent Parsing Failed: {e}")
            return EvaluatorResponse(
                agent_name="ClinicalAgent",
                step=current_step,
                strengths=[],
                issues_detected=["Error parsing evaluator response"],
                explanation=f"Failed to parse LLM output. Raw: {raw_response[:50]}...",
                verdict="Inappropriate",
                confidence=0.0
            )
