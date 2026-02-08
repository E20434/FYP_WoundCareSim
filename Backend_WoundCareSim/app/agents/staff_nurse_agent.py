from app.agents.agent_base import BaseAgent
from app.core.step_guidance import STEP_GUIDANCE


class StaffNurseAgent(BaseAgent):
    """
    Conversational supervising nurse (GUIDANCE + VERIFICATION).
    
    Three modes:
    1. GUIDANCE: Explains current/next step
    2. VERIFICATION (Conversational): Student shows material and describes it verbally
    3. VERIFICATION (Structured - deprecated): Old form-based method
    
    Does NOT evaluate, approve progression, or block steps.
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
        "dry dressing",
        "bottle",
        "packet",
        "package",
        "expires"
    ]

    def __init__(self):
        super().__init__()

    def _is_student_finishing(self, student_input: str) -> bool:
        """Detect if student is asking about next step."""
        student_lower = student_input.lower()
        return any(keyword in student_lower for keyword in self.FINISH_KEYWORDS)

    def _is_verification_request(self, student_input: str) -> bool:
        """Detect if student is asking for material verification."""
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

        # ================================================
        # MODE 1: VERIFICATION REDIRECT (for cleaning_and_dressing)
        # ================================================
        if is_verification and current_step == "cleaning_and_dressing":
            # Redirect to proper verification endpoint
            return (
                "I can help verify materials! Please use the verification conversation "
                "feature to show me what you have. Describe the material, its expiry date, "
                "and the package condition, and I'll verify it for you."
            )

        # ================================================
        # MODE 2: NEXT STEP GUIDANCE (when student finishes)
        # ================================================
        elif is_finishing and next_guidance:
            system_prompt = (
                "You are a supervising staff nurse guiding a nursing student.\n\n"
                "ROLE RULES:\n"
                "- Provide guidance only\n"
                "- Do NOT evaluate performance\n"
                "- Do NOT grant permission to proceed\n"
                "- The student controls step progression\n\n"
                "TASK:\n"
                "- Student indicated they are finished with current step\n"
                "- Explain the NEXT step briefly\n"
                "- Keep responses short, clear, and spoken-friendly\n"
            )

            user_prompt = (
                f"CURRENT STEP: {current_step}\n"
                f"NEXT STEP: {next_step}\n"
                f"NEXT STEP GUIDANCE:\n{next_guidance}\n\n"
                f"STUDENT MESSAGE:\n{student_input}\n"
            )

        # ================================================
        # MODE 3: CURRENT STEP GUIDANCE (default)
        # ================================================
        else:
            system_prompt = (
                "You are a supervising staff nurse guiding a nursing student.\n\n"
                "ROLE RULES:\n"
                "- Provide guidance only\n"
                "- Do NOT evaluate performance\n"
                "- Do NOT grant permission to proceed\n"
                "- The student controls step progression\n\n"
                "TASK:\n"
                "- Student is asking about the CURRENT step\n"
                "- Explain what they should be doing now\n"
                "- Keep responses short, clear, and spoken-friendly\n"
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

    async def verify_material_conversational(
        self,
        student_message: str,
        material_type: str
    ) -> str:
        """
        CONVERSATIONAL verification response.
        Student describes the material verbally, nurse responds conversationally.
        
        This is the new preferred method - natural conversation like in real clinical practice.
        
        Args:
            student_message: What the student says (e.g., "Can you verify this surgical spirit? 
                           It expires March 2026 and the bottle is intact.")
            material_type: "solution" or "dressing" (for context)
        
        Returns:
            Nurse's conversational verification response
        """
        
        system_prompt = (
            "You are a supervising staff nurse conducting material verification.\n\n"
            "ROLE:\n"
            "- Student is showing you a material and describing it verbally\n"
            "- Respond conversationally as a real nurse would\n"
            "- Listen to what they tell you about the material\n\n"
            "VERIFICATION PROCESS:\n"
            "- If student provides complete info (name, expiry, condition) → Acknowledge and approve\n"
            "- If student provides incomplete info → Ask for missing details naturally\n"
            "- If student mentions 'expired' or 'damaged' → Instruct to get replacement\n"
            "- If everything sounds correct → Give clear approval\n\n"
            "EXPECTED MATERIALS:\n"
            "- Cleaning solution: Surgical spirit\n"
            "- Dressing packet: Dry sterile dressing\n\n"
            "RESPONSE STYLE:\n"
            "- Be supportive and professional\n"
            "- Use natural conversational language\n"
            "- Give specific feedback based on what student says\n"
            "- End with clear approval: 'You may use it' or 'You can proceed'\n"
            "- Keep responses SHORT (2-3 sentences)\n\n"
            "EXAMPLES:\n"
            "Student: 'Nurse, can you verify this surgical spirit? It expires March 2026 and the bottle is intact.'\n"
            "Nurse: 'Let me see... Surgical spirit, expires March 2026, bottle intact - looks good. You may use it.'\n\n"
            "Student: 'Could you check this sterile dressing packet? Expires April 2026.'\n"
            "Nurse: 'What's the condition of the package? Is it sealed properly?'\n\n"
            "Student: 'This solution expires next month.'\n"
            "Nurse: 'That's too close to expiry. Please get a fresh bottle with a longer expiration date.'\n"
        )
        
        user_prompt = (
            f"MATERIAL TYPE: {material_type}\n"
            f"STUDENT MESSAGE:\n{student_message}\n\n"
            "Respond as a staff nurse verifying this material conversationally."
        )
        
        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2
        )

    async def verify_material(
        self,
        material_type: str,
        material_name: str,
        expiry_date: str,
        package_condition: str
    ) -> str:
        """
        DEPRECATED: Structured verification response.
        This is the old form-based method, kept for backwards compatibility.
        Use verify_material_conversational() instead for better clinical simulation.
        
        Args:
            material_type: "solution" or "dressing"
            material_name: What the student says it is
            expiry_date: What the student states
            package_condition: "intact", "damaged", etc.
        
        Returns:
            Nurse's verbal verification response
        """
        
        system_prompt = (
            "You are a supervising staff nurse conducting material verification.\n\n"
            "ROLE:\n"
            "- Student is showing you a material for verification\n"
            "- They have stated: name, expiry date, package condition\n"
            "- Provide clear verbal feedback\n\n"
            "VERIFICATION LOGIC:\n"
            "- If package is damaged → Reject and instruct to get new one\n"
            "- If expired → Reject and instruct to get new one\n"
            "- If information incomplete → Ask for missing details\n"
            "- If all correct → Approve clearly\n\n"
            "EXPECTED MATERIALS:\n"
            "- Cleaning solution: Surgical spirit\n"
            "- Dressing: Dry sterile dressing\n\n"
            "RESPONSE STYLE:\n"
            "- Short, professional, clear\n"
            "- State your verification decision explicitly\n"
        )
        
        user_prompt = (
            f"MATERIAL TYPE: {material_type}\n"
            f"STUDENT DECLARATION:\n"
            f"- Name: {material_name}\n"
            f"- Expiry Date: {expiry_date}\n"
            f"- Package Condition: {package_condition}\n\n"
            "Provide your verification response."
        )
        
        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2
        )
