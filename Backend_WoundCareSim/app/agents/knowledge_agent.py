import json

from pydantic import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

class KnowledgeAgent(BaseAgent):
    """
    Evaluates the student's clinical knowledge and information gathering during history taking.
    Focuses on: completeness of history, appropriate questions, clinical reasoning.
    """

    def __init__(self):
        super().__init__()

    async def evaluate(
        self,
        current_step: str,
        student_input: str,
        scenario_metadata: dict,
        rag_response: str,
    ) -> EvaluatorResponse:
        """
        Evaluate clinical knowledge and information gathering completeness.
        """

        # CRITICAL: Check for empty input first
        if current_step == "history" and (not student_input or student_input.strip() == ""):
            return EvaluatorResponse(
                agent_name="KnowledgeAgent",
                step=current_step,
                strengths=[],
                issues_detected=[
                    "No patient history obtained",
                    "Failed to gather critical medical information",
                    "Cannot assess patient safety without complete history"
                ],
                explanation="The student did not gather any patient history. Understanding the patient's medical background, allergies, current medications, pain level, and surgical history is essential for safe wound care. Without this knowledge, the student cannot make informed clinical decisions or ensure patient safety.",
                verdict="Inappropriate",
                confidence=0.0
            )

        system_prompt = (
            "You are a nursing clinical knowledge evaluator for HISTORY-TAKING.\n\n"
            "ROLE: Evaluate what patient information the student ACTUALLY GATHERED by asking questions.\n"
            "Do NOT evaluate communication style (that's CommunicationAgent's job).\n"
            "Do NOT assume student gathered information unless explicitly asked in transcript.\n\n"
            "CRITICAL SAFETY RULE:\n"
            "═════════════════════════════════════════════════════════════════════════\n"
            "IF ALLERGIES WERE NOT ASKED IN THE CONVERSATION:\n"
            "  → Verdict MUST be \"Inappropriate\"\n"
            "  → This is non-negotiable (safety-critical)\n"
            "═════════════════════════════════════════════════════════════════════════\n\n"
            "INFORMATION ITEMS TO CHECK (in order of criticality):\n\n"
            "CRITICAL (MUST ask):\n"
            "  1. ALLERGIES - Any allergies? (Medications, latex, tape, dressing materials)\n"
            "     → If NOT asked: Automatic Inappropriate verdict\n"
            "     → This is the highest-priority safety check\n\n"
            "HIGH IMPORTANCE:\n"
            "  2. IDENTITY - Name, age, date of birth verification\n"
            "  3. PAIN - Any pain? Location? Severity/description?\n"
            "  4. MEDICAL HISTORY - Current conditions, recent surgery, medications\n\n"
            "SUPPORTING INFORMATION:\n"
            "  5. PROCEDURE EXPLANATION - What you will do, why, expected timeline\n\n"
            "EVALUATION RULES:\n"
            "- ONLY count information if student EXPLICITLY ASKED in the conversation\n"
            "- Do NOT credit it if patient volunteered and student didn't ask\n"
            "- Do NOT credit it if it appears in scenario metadata but wasn't asked about\n"
            "- Evidence-based only: Point to specific student questions in transcript\n\n"
            "CONFIDENCE CALCULATION (EVIDENCE-BASED):\n"
            "  Calculate as: (Items successfully gathered) / (Total critical items)\n\n"
            "  Example with 5 critical items (Identity, Allergies, Pain, Medical History, Procedure):\n"
            "    - Asked all 5 clearly → 5/5 = confidence 1.0\n"
            "    - Asked 4 of 5 → 4/5 = confidence 0.8\n"
            "    - Asked 3 of 5 → 3/5 = confidence 0.6\n"
            "    - Asked 2 of 5 → 2/5 = confidence 0.4\n"
            "    - Asked 1 or 0 of 5 → 0-1/5 = confidence 0.0-0.2\n\n"
            "VERDICT ASSIGNMENT (STRICT):\n\n"
            "APPROPRIATE (all critical items covered):\n"
            "  - Allergies: ASKED and understood\n"
            "  - Identity: Verified (name, age at minimum)\n"
            "  - Pain: Assessed\n"
            "  - Medical history: Explored\n"
            "  - Procedure: Explained to patient\n"
            "  → Confidence ≥ 0.85\n\n"
            "PARTIALLY APPROPRIATE (some critical items missing):\n"
            "  - Allergy check: MUST have been asked (or auto-Inappropriate)\n"
            "  - 2-4 of the other items gathered\n"
            "  - OR all items asked but some answers unclear\n"
            "  → Confidence 0.4-0.8\n\n"
            "INAPPROPRIATE (critical gaps):\n"
            "  - Allergies NOT asked → Auto-Inappropriate, confidence reduced\n"
            "  - Missing 3+ critical items\n"
            "  - No meaningful history-taking occurred\n"
            "  → Confidence typically ≤ 0.4\n\n"
            "OUTPUT FORMAT (RAW JSON ONLY):\n"
            "Return ONLY valid JSON with these exact fields:\n"
            "{\n"
            '  "agent_name": "KnowledgeAgent",\n'
            '  "step": "history",\n'
            '  "strengths": ["Specific item gathered with transcript reference", "Another item"],\n'
            '  "issues_detected": ["Missing critical item", "Unclear assessment"],\n'
            '  "explanation": "Detailed assessment: Which items gathered, which missing, evidence from transcript. If allergies not asked, state this prominently.",\n'
            '  "verdict": "Appropriate",\n'
            '  "confidence": 0.8\n'
            "}\n"
        )

        user_prompt = (
            f"STUDENT-PATIENT CONVERSATION (Speaker labels are explicit):\n"
            f"═" * 70 + "\n"
            f"{student_input}\n"
            f"═" * 70 + "\n\n"
            f"SCENARIO CONTEXT:\n"
            f"Patient: {scenario_metadata.get('patient_history', {}).get('name', 'Patient Unknown')}\n"
            f"Wound Type: {scenario_metadata.get('wound_details', {}).get('wound_type', 'Unknown')}\n\n"
            f"TASK:\n"
            f"Analyze what the student EXPLICITLY ASKED about in the conversation.\n"
            f"Review against the 5 critical information items from the system prompt.\n"
            f"Count only items that were directly asked about.\n"
            f"Calculate confidence as (items_gathered / 5).\n"
            f"\n"
            f"CRITICAL: If allergies were never asked about, verdict must be \"Inappropriate\" regardless of other items.\n"
        )

        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        try:
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            response_data = json.loads(clean_json)
            
            response_data["step"] = current_step
            response_data["agent_name"] = "KnowledgeAgent"

            # ================================================================
            # VERDICT VALIDATION AND NORMALIZATION
            # ================================================================
            # Ensure verdict is one of the three allowed values
            verdict = response_data.get("verdict", "").strip()
            valid_verdicts = ["Appropriate", "Partially Appropriate", "Inappropriate"]
            
            if verdict not in valid_verdicts:
                # Try to match if typo or slight variation
                verdict_lower = verdict.lower()
                if "appropriate" in verdict_lower and "partial" in verdict_lower:
                    response_data["verdict"] = "Partially Appropriate"
                elif "inappropriate" in verdict_lower or "no" in verdict_lower or "failed" in verdict_lower:
                    response_data["verdict"] = "Inappropriate"
                elif "appropriate" in verdict_lower:
                    response_data["verdict"] = "Appropriate"
                else:
                    # Default to Inappropriate if unrecognized
                    print(f"⚠️ KnowledgeAgent returned invalid verdict: {verdict}")
                    response_data["verdict"] = "Inappropriate"

            # ================================================================
            # CONFIDENCE VALIDATION
            # ================================================================
            # Ensure confidence is between 0.0 and 1.0
            confidence = response_data.get("confidence", 0.0)
            try:
                confidence = float(confidence)
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0.0, 1.0]
                response_data["confidence"] = round(confidence, 2)
            except (ValueError, TypeError):
                print(f"⚠️ KnowledgeAgent returned invalid confidence: {confidence}")
                response_data["confidence"] = 0.0

            # ================================================================
            # CRITICAL SAFETY CHECK: Verify allergies were explicitly asked
            # ================================================================
            # This is a hard requirement - if allergies were not asked,
            # verdict MUST be Inappropriate, regardless of LLM output
            
            allergies_asked = self._check_allergies_asked(student_input)
            
            if not allergies_asked:
                # Override verdict and confidence
                response_data["verdict"] = "Inappropriate"
                response_data["confidence"] = max(0.0, response_data.get("confidence", 0.0) - 0.3)
                
                # Add to issues if not already there
                if "issues_detected" not in response_data:
                    response_data["issues_detected"] = []
                
                if "CRITICAL: Allergies not assessed" not in response_data["issues_detected"]:
                    response_data["issues_detected"].insert(
                        0, 
                        "CRITICAL: Allergies not assessed - Safety risk"
                    )
                
                # Update explanation to emphasize allergy gap
                response_data["explanation"] = (
                    f"CRITICAL SAFETY ISSUE: The student did not ask about allergies. "
                    f"This is a non-negotiable requirement in history-taking. "
                    f"Without allergy assessment, the student cannot safely select materials or medications. "
                    f"Original assessment: {response_data.get('explanation', 'N/A')}"
                )

            return EvaluatorResponse(**response_data)

        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            print(f"KnowledgeAgent Parsing Failed: {e}")
            return EvaluatorResponse(
                agent_name="KnowledgeAgent",
                step=current_step,
                strengths=[],
                issues_detected=["Error parsing evaluator response"],
                explanation=f"Failed to parse LLM output. Raw: {raw_response[:50]}...",
                verdict="Inappropriate",
                confidence=0.0
            )

    def _check_allergies_asked(self, transcript: str) -> bool:
        """
        Check if the student explicitly asked about allergies in the transcript.
        
        Returns:
            True if allergies were asked, False otherwise
        """
        if not transcript:
            return False
        
        # Convert to lowercase for case-insensitive matching
        transcript_lower = transcript.lower()
        
        # Keywords that indicate allergy assessment
        allergy_keywords = [
            "allerg",  # Covers: allergies, allergic, allergy
            "latex",
            "reaction",
            "sensitive",
            "tolerate",  # Covers: tolerate, tolerance, tolerant
            "medication",
            "drug",
            "dressing material",
            "adhesive",
            "tape",
            "bandage",
            "anaphyl",  # Covers: anaphylaxis, anaphylactic
        ]
        
        # Check if student line (not patient line) contains allergy-related keywords
        lines = transcript.split("\n")
        for line in lines:
            # Only check student's lines
            if line.lower().startswith("student:"):
                # Check for allergy keywords
                for keyword in allergy_keywords:
                    if keyword in line.lower():
                        # Verify it's actually a question (has question mark or interrogative structure)
                        if "?" in line or "do you have" in line or "are you" in line or \
                           "have you" in line or "any" in line:
                            return True
        
        return False
