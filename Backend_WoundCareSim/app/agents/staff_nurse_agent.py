from app.agents.agent_base import BaseAgent
from app.core.step_guidance import STEP_GUIDANCE


class StaffNurseAgent(BaseAgent):
    """
    Conversational supervising nurse.

    - Does NOT evaluate
    - Does NOT approve or block steps
    - Provides step guidance based on student intent
    """

    def __init__(self):
        super().__init__()

    async def respond(
        self,
        student_input: str,
        current_step: str,
        next_step: str | None
    ) -> str:

        current_guidance = STEP_GUIDANCE.get(current_step, "")
        next_guidance = STEP_GUIDANCE.get(next_step, "") if next_step else ""

        system_prompt = (
            "You are a supervising staff nurse guiding a nursing student.\n"
            "Your role is to explain what the student should do.\n\n"
            "Rules:\n"
            "- Do NOT evaluate performance\n"
            "- Do NOT say whether the student did well or poorly\n"
            "- Do NOT grant permission\n"
            "- If the student seems to ask what to do next or indicates they are finished, "
            "explain the NEXT step\n"
            "- Otherwise, explain the CURRENT step\n"
            "- Respond in clear, supportive, spoken-friendly language\n"
        )

        user_prompt = (
            f"CURRENT STEP: {current_step}\n"
            f"CURRENT STEP GUIDANCE: {current_guidance}\n"
            f"NEXT STEP: {next_step}\n"
            f"NEXT STEP GUIDANCE: {next_guidance}\n\n"
            f"STUDENT MESSAGE:\n{student_input}\n"
        )

        response_text = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )

        return response_text
