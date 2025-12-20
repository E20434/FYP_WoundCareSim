from app.agents.agent_base import BaseAgent


class CommunicationAgent(BaseAgent):
    """
    Evaluates the student's communication quality during the procedure.
    Focuses ONLY on communication behavior, not medical or procedural correctness.
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
        Evaluate communication based on the current procedural step.
        Returns structured natural language (not parsed here).
        """

        system_prompt = (
            "You are a nursing communication evaluator.\n"
            "Your task is to evaluate ONLY the student's communication skills.\n\n"
            "Rules:\n"
            "- Do NOT evaluate medical knowledge.\n"
            "- Do NOT evaluate procedural or clinical steps.\n"
            "- Do NOT invent facts not present in the context.\n"
            "- Base your reasoning only on the provided scenario and student input.\n"
            "- Be concise, professional, and objective.\n"
            "- If communication is appropriate, say so clearly.\n"
        )

        user_prompt = (
            f"CURRENT PROCEDURE STEP:\n"
            f"{current_step}\n\n"
            f"SCENARIO CONTEXT:\n"
            f"Patient history and context:\n"
            f"{scenario_metadata.get('patient_history', 'N/A')}\n\n"
            f"EXPECTED COMMUNICATION FOCUS FOR THIS STEP:\n"
            f"- HISTORY: greeting, self-introduction, patient identification, consent, empathy\n"
            f"- ASSESSMENT: clear explanations, respectful questioning\n"
            f"- CLEANING: explaining actions, reassurance, consent\n"
            f"- DRESSING: professional explanation, reassurance, closure\n\n"
            f"REFERENCE CONTEXT (if relevant):\n"
            f"{rag_response}\n\n"
            f"STUDENT SPOKEN INPUT:\n"
            f"{student_input}\n\n"
            f"INSTRUCTIONS:\n"
            f"Evaluate the student's communication for the CURRENT STEP only.\n"
            f"Respond using the following structure:\n\n"
            f"- Strengths in communication\n"
            f"- Issues or missing communication elements (if any)\n"
            f"- Explanation (why this matters)\n"
            f"- Confidence (0.0 to 1.0)\n"
        )

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )
