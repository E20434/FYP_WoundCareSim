from app.agents.agent_base import BaseAgent
from app.core.step_guidance import STEP_GUIDANCE


class StaffNurseAgent(BaseAgent):
    """
    Conversational supervising nurse (GUIDANCE ONLY + VERIFICATION).

    - Explains the CURRENT step by default
    - Explains the NEXT step ONLY if the student indicates they are finished
    - VERIFIES solutions and dressing packets when asked
    - Does NOT evaluate performance
    - Does NOT approve or block steps
    - Does NOT decide when a step ends
    """

    FINISH_KEYWORDS = [
        "finished",
        "done",
        "what next",
        "next step",
        "can i proceed",
        "ready",
        "move on",
        "complete"
    ]

    VERIFICATION_KEYWORDS = [
        "verify",
        "check",
        "confirm",
        "is this correct",
        "is this right",
        "can you check",
        "look at this",
        "expired",
        "expiration",
        "solution",
        "dressing packet",
        "sterile",
        "surgical spirit",
        "dry dressing"
    ]

    def __init__(self):
        super().__init__()

    def _is_student_finishing(self, student_input: str) -> bool:
        """
        Simple intent detection for step completion.
        This is deterministic and VR-safe.
        """
        student_lower = student_input.lower()
        return any(keyword in student_lower for keyword in self.FINISH_KEYWORDS)

    def _is_verification_request(self, student_input: str) -> bool:
        """
        Detect if student is asking for verification of solution/dressing.
        """
        student_lower = student_input.lower()
        return any(keyword in student_lower for keyword in self.VERIFICATION_KEYWORDS)

    async def respond(
        self,
        student_input: str,
        current_step: str,
        next_step: str | None
    ) -> str:

        is_finishing = self._is_student_finishing(student_input)
        is_verification = self._is_verification_request(student_input)

        current_guidance = STEP_GUIDANCE.get(current_step, "")
        next_guidance = STEP_GUIDANCE.get(next_step, "") if next_step else ""

        # VERIFICATION MODE (for cleaning_and_dressing step)
        if is_verification and current_step == "cleaning_and_dressing":
            system_prompt = (
                "You are a supervising staff nurse verifying materials with a nursing student.\n\n"
                "VERIFICATION ROLE:\n"
                "- The student is showing you a cleaning solution or dressing packet.\n"
                "- Your job is to verify it is safe to use based on what they tell you.\n"
                "- The student should state: name/type, expiration date, package integrity.\n"
                "- Listen to what the student says about the item.\n"
                "- If student provides complete details, give clear approval.\n"
                "- If student mentions a problem (expired, damaged), advise getting replacement.\n"
                "- If student doesn't provide details, ask them to state the information.\n\n"
                "RESPONSE STYLE:\n"
                "- Be supportive and professional.\n"
                "- Use simple, clear language.\n"
                "- Acknowledge what the student stated.\n"
                "- Give specific feedback: 'Surgical spirit, expires [date], bottle intact - looks good.'\n"
                "- End with clear approval: 'You may use it' or 'You can proceed.'\n\n"
                "EXPECTED MATERIALS:\n"
                "- Cleaning solution: Surgical spirit\n"
                "- Dressing packet: Dry dressing (sterile)\n\n"
                "VERIFICATION PROCESS:\n"
                "- If student states complete info → Acknowledge and approve\n"
                "- If student provides incomplete info → Ask for missing details\n"
                "- If student mentions 'expired' or 'damaged' → Instruct to get replacement\n"
                "- Assume items are correct if student states them properly\n"
            )

            user_prompt = (
                f"CURRENT STEP: {current_step}\n"
                f"STUDENT REQUEST:\n{student_input}\n\n"
                f"The student is asking you to verify materials.\n"
                "Respond as a staff nurse checking what the student tells you and giving approval or feedback."
            )

        # FINISHING MODE (explaining next step)
        elif is_finishing and next_guidance:
            system_prompt = (
                "You are a supervising staff nurse guiding a nursing student.\n\n"
                "STRICT ROLE RULES:\n"
                "- You provide guidance only.\n"
                "- You do NOT evaluate performance.\n"
                "- You do NOT say whether the student did well or poorly.\n"
                "- You do NOT grant permission to proceed.\n"
                "- You do NOT decide when a step is complete.\n"
                "- The student controls step progression.\n\n"
                "Guidance behavior:\n"
                "- Student indicated they are finished with current step.\n"
                "- Explain the NEXT step briefly.\n"
                "- Keep responses short, clear, and spoken-friendly.\n"
            )

            user_prompt = (
                f"CURRENT STEP: {current_step}\n"
                f"NEXT STEP: {next_step}\n"
                f"NEXT STEP GUIDANCE:\n{next_guidance}\n\n"
                f"STUDENT MESSAGE:\n{student_input}\n"
            )

        # GUIDANCE MODE (default - explaining current step)
        else:
            system_prompt = (
                "You are a supervising staff nurse guiding a nursing student.\n\n"
                "STRICT ROLE RULES:\n"
                "- You provide guidance only.\n"
                "- You do NOT evaluate performance.\n"
                "- You do NOT say whether the student did well or poorly.\n"
                "- You do NOT grant permission to proceed.\n"
                "- You do NOT decide when a step is complete.\n"
                "- The student controls step progression.\n\n"
                "Guidance behavior:\n"
                "- Student is asking about the CURRENT step.\n"
                "- Explain what they should be doing now.\n"
                "- Keep responses short, clear, and spoken-friendly.\n"
            )

            user_prompt = (
                f"CURRENT STEP: {current_step}\n"
                f"CURRENT STEP GUIDANCE:\n{current_guidance}\n\n"
                f"STUDENT MESSAGE:\n{student_input}\n"
            )

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )
