from app.agents.agent_base import BaseAgent


class KnowledgeAgent(BaseAgent):
    """
    Evaluates the student's nursing knowledge and clinical reasoning.
    Focuses on cognitive correctness appropriate to the current step.
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
        Evaluate nursing knowledge demonstrated by the student.
        Returns structured natural-language feedback.
        """

        system_prompt = (
            "You are a nursing knowledge evaluator.\n"
            "Your task is to evaluate ONLY the student's nursing knowledge and reasoning.\n\n"
            "Strict Rules:\n"
            "- Do NOT evaluate communication style or politeness.\n"
            "- Do NOT evaluate physical execution of procedures.\n"
            "- Do NOT assume actions that were not stated.\n"
            "- Base your reasoning ONLY on the student input and provided context.\n"
            "- Be objective and clinically accurate.\n"
        )

        user_prompt = (
            f"CURRENT PROCEDURE STEP:\n"
            f"{current_step}\n\n"

            f"SCENARIO CONTEXT:\n"
            f"Patient history and relevant details:\n"
            f"{scenario_metadata.get('patient_history', 'N/A')}\n\n"

            f"KNOWLEDGE EXPECTATIONS BY STEP:\n"
            f"- HISTORY: relevant history questions (pain, duration, infection signs, allergies)\n"
            f"- ASSESSMENT: correct understanding of wound characteristics\n"
            f"- CLEANING: conceptual understanding of sterile principles\n"
            f"- DRESSING: understanding of dressing purpose and protection\n\n"

            f"REFERENCE KNOWLEDGE CONTEXT (guidelines / procedure):\n"
            f"{rag_response}\n\n"

            f"STUDENT INPUT:\n"
            f"{student_input}\n\n"

            f"EVALUATION INSTRUCTIONS:\n"
            f"Evaluate the nursing knowledge demonstrated ONLY for the CURRENT STEP.\n"
            f"Do not penalize missing knowledge unrelated to this step.\n\n"

            f"Respond using EXACTLY the following structure:\n"
            f"1. Demonstrated Correct Knowledge:\n"
            f"2. Knowledge Gaps or Errors:\n"
            f"3. Why This Knowledge Matters Clinically:\n"
            f"4. Step Knowledge Appropriateness (Adequate / Partially Adequate / Inadequate):\n"
            f"5. Confidence (0.0 to 1.0):\n"
        )

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )
