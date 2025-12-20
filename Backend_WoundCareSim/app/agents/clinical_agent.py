from app.agents.agent_base import BaseAgent


class ClinicalAgent(BaseAgent):
    """
    Evaluates the student's clinical and procedural correctness.
    Focuses on cleaning and dressing steps, with minimal involvement elsewhere.
    """

    def __init__(self):
        super().__init__()

    async def evaluate(
        self,
        *,
        current_step: str,
        student_input: str,
        scenario_metadata: dict,
        rag_response: str,
    ) -> str:
        """
        Evaluate clinical and procedural correctness based on student input.
        Returns structured natural-language feedback.
        """

        system_prompt = (
            "You are a nursing clinical skills evaluator.\n"
            "Your role is to evaluate ONLY clinical and procedural correctness.\n\n"
            "Strict Rules:\n"
            "- Do NOT evaluate communication style or empathy.\n"
            "- Do NOT evaluate theoretical nursing knowledge.\n"
            "- Do NOT assume actions that were not explicitly stated.\n"
            "- Only evaluate actions relevant to the CURRENT STEP.\n"
            "- Prioritize patient safety above all else.\n"
        )

        user_prompt = (
            f"CURRENT PROCEDURE STEP:\n"
            f"{current_step}\n\n"

            f"SCENARIO CONTEXT:\n"
            f"Wound details:\n"
            f"{scenario_metadata.get('wound_details', 'N/A')}\n\n"

            f"CLINICAL EXPECTATIONS BY STEP:\n"
            f"- HISTORY: no clinical actions expected\n"
            f"- ASSESSMENT: conceptual awareness only\n"
            f"- CLEANING: hand hygiene, aseptic technique, correct cleaning direction\n"
            f"- DRESSING: appropriate dressing selection, protection, closure\n\n"

            f"REFERENCE PROCEDURE CONTEXT:\n"
            f"{rag_response}\n\n"

            f"STUDENT INPUT (described actions or intentions):\n"
            f"{student_input}\n\n"

            f"EVALUATION INSTRUCTIONS:\n"
            f"Evaluate ONLY the clinical correctness relevant to the CURRENT STEP.\n"
            f"Do not penalize missing actions from future steps.\n"
            f"Explicitly flag unsafe or incorrect actions if mentioned.\n\n"

            f"Respond using EXACTLY the following structure:\n"
            f"1. Correct Clinical Actions Identified:\n"
            f"2. Clinical Errors or Unsafe Actions:\n"
            f"3. Why This Matters for Patient Safety:\n"
            f"4. Step Clinical Appropriateness (Appropriate / Partially Appropriate / Inappropriate):\n"
            f"5. Confidence (0.0 to 1.0):\n"
        )

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )
