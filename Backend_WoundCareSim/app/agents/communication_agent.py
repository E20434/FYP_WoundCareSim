import json
import re

from pydantic import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

class CommunicationAgent(BaseAgent):
    """
    Evaluates student communication skills during history taking.
    Focuses on: rapport building, clarity, professionalism, patient-centered approach.
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
        
        # CRITICAL: Check for empty input first
        if not student_input or student_input.strip() == "":
            return EvaluatorResponse(
                agent_name="CommunicationAgent",
                step=current_step,
                strengths=[],
                issues_detected=[
                    "No communication with patient detected",
                    "Patient history gathering is mandatory",
                    "Failed to establish rapport"
                ],
                explanation="The student did not engage in any conversation with the patient. Gathering patient history through effective communication is a critical first step in wound care. Without patient interaction, essential information about allergies, pain levels, and medical history cannot be obtained.",
                verdict="Inappropriate",
                confidence=0.0
            )
        
        system_prompt = (
            "You are a nursing communication evaluator for history-taking.\n\n"
            "ROLE: Evaluate ONLY communication skills during patient interaction.\n"
            "Do NOT evaluate medical knowledge, whether specific questions were asked, or clinical accuracy.\n\n"
            "EVALUATION CRITERIA:\n\n"
            "1. PROFESSIONAL INTRODUCTION\n"
            "   Check: Student introduced self AND established respect for patient\n\n"
            "2. CLARITY & TONE\n"
            "   Check: Student used clear language, avoided jargon, spoke respectfully\n\n"
            "3. ACTIVE LISTENING & EMPATHY\n"
            "   Check: Student acknowledged patient responses, showed understanding, validated concerns\n\n"
            "4. PATIENT-CENTERED APPROACH\n"
            "   Check: Student addressed patient comfort, explained actions, invited questions\n\n"
            "EVALUATION RULES:\n"
            "- Base judgment ONLY on actual conversation transcript\n"
            "- Do NOT evaluate whether specific medical questions were asked (KnowledgeAgent does that)\n"
            "- Do NOT assume unspoken actions or thoughts\n"
            "- Rate communication quality independently of clinical content\n\n"
            "VERDICT ASSIGNMENT (STRICT):\n\n"
            "APPROPRIATE:\n"
            "  - Student introduces self professionally\n"
            "  - All responses are clear, respectful, and patient-centered\n"
            "  - Student demonstrates empathy and active listening\n"
            "  - Maintains professional tone throughout\n\n"
            "PARTIALLY APPROPRIATE:\n"
            "  - Student attempts introduction but tone/clarity needs work, OR\n"
            "  - Most responses are clear/respectful but some gaps in empathy/engagement, OR\n"
            "  - Some unprofessional moments but overall communication is functional\n\n"
            "INAPPROPRIATE:\n"
            "  - No real conversation with patient (zero or minimal student input), OR\n"
            "  - Consistently unprofessional tone/disrespectful language, OR\n"
            "  - Failed to establish any basic rapport, OR\n"
            "  - Student did not engage meaningfully with patient responses\n\n"
            "CONFIDENCE GUIDELINES:\n"
            "  Confidence = How clear the evidence is from the transcript\n\n"
            "  1.0 (certain): All communication elements clearly present/absent in conversation\n"
            "  0.8: Most elements clear, minor ambiguity in a few moments\n"
            "  0.6: Some elements clear, significant portions hard to assess from transcript\n"
            "  0.4: Limited conversation makes assessment difficult\n"
            "  0.0: No conversation or completely unable to assess\n\n"
            "OUTPUT FORMAT (RAW JSON ONLY, no markdown):\n"
            "Return ONLY valid JSON with these exact fields:\n"
            "{\n"
            '  "agent_name": "CommunicationAgent",\n'
            '  "step": "history",\n'
            '  "strengths": ["Clear example from transcript", "Another strength with evidence"],\n'
            '  "issues_detected": ["Specific issue observed"],\n'
            '  "explanation": "Evidence-based reasoning tying verdict to transcript moments",\n'
            '  "verdict": "Appropriate",\n'
            '  "confidence": 0.85\n'
            "}\n"
        )

        user_prompt = (
            f"STUDENT-PATIENT CONVERSATION (Speaker labels are explicit):\n"
            f"═" * 70 + "\n"
            f"{student_input}\n"
            f"═" * 70 + "\n\n"
            f"SCENARIO CONTEXT:\n"
            f"Patient: {scenario_metadata.get('patient_history', {}).get('name', 'Unknown')}, "
            f"Age {scenario_metadata.get('patient_history', {}).get('age', 'Unknown')}\n"
            f"Presenting Issue: {scenario_metadata.get('wound_details', {}).get('wound_type', 'Unknown')} "
            f"at {scenario_metadata.get('wound_details', {}).get('location', 'Unknown')}\n\n"
            f"Evaluate how professionally and empathetically the student communicated with the patient."
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
            response_data["agent_name"] = "CommunicationAgent"
            
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
                    print(f"⚠️ CommunicationAgent returned invalid verdict: {verdict}")
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
                print(f"⚠️ CommunicationAgent returned invalid confidence: {confidence}")
                response_data["confidence"] = 0.0

            return EvaluatorResponse(**response_data)

        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            print(f"CommunicationAgent Parsing Failed: {e}")
            return EvaluatorResponse(
                agent_name="CommunicationAgent",
                step=current_step,
                strengths=[],
                issues_detected=["Error parsing evaluator response"],
                explanation=f"Failed to parse LLM output. Raw: {raw_response[:50]}...",
                verdict="Inappropriate",
                confidence=0.0
            )
