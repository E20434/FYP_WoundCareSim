from typing import List, Dict
from app.agents.agent_base import BaseAgent


class PatientAgent(BaseAgent):
    """
    LLM-driven virtual patient for HISTORY step.

    Week-7 (FINAL):
    - Uses ONLY Firestore scenario data
    - No RAG
    - No hallucination
    - Deterministic for testing
    """

    def _format_patient_history(self, history: Dict) -> str:
        """
        Convert structured Firestore patient_history
        into an explicit narrative for the LLM.
        """
        if not history:
            return "No patient history available."

        surgery = history.get("surgery_details", {})

        return (
            f"Patient Name: {history.get('name', 'Unknown')}\n"
            f"Age: {history.get('age', 'Unknown')}\n"
            f"Gender: {history.get('gender', 'Unknown')}\n\n"
            f"Medical Conditions: {', '.join(history.get('medical_history', [])) or 'None'}\n"
            f"Allergies: {', '.join(history.get('allergies', [])) or 'None'}\n\n"
            f"Surgery Information:\n"
            f"- Procedure: {surgery.get('procedure', 'Unknown')}\n"
            f"- Date: {surgery.get('date', 'Unknown')}\n"
            f"- Surgeon: {surgery.get('surgeon', 'Unknown')}\n\n"
            f"Wound Cause: The wound is due to the surgical procedure on the left forearm.\n"
        )

    async def respond(
        self,
        patient_history: Dict,
        conversation_history: List[Dict[str, str]],
        student_message: str
    ) -> str:
        """
        Generate a patient response strictly grounded
        in Firestore scenario data.
        """

        formatted_history = self._format_patient_history(patient_history)

        system_prompt = (
            "You are a patient in a nursing training simulation.\n\n"
            "STRICT RULES:\n"
            "- You may ONLY answer using the information provided below.\n"
            "- If the student asks about something NOT stated, say:\n"
            "  'I’m not sure' or 'I don’t know.'\n"
            "- Do NOT guess.\n"
            "- Do NOT add new medical information.\n"
            "- Keep answers short and realistic.\n"
            "- Never contradict the given information.\n"
            "- You are NOT a medical professional.\n"
        )

        conversation_text = ""
        for turn in conversation_history:
            role = turn["speaker"].capitalize()
            conversation_text += f"{role}: {turn['text']}\n"

        user_prompt = (
            f"KNOWN PATIENT INFORMATION:\n"
            f"{formatted_history}\n"
            f"CONVERSATION SO FAR:\n"
            f"{conversation_text}\n"
            f"Student Nurse: {student_message}\n"
            f"Patient:"
        )

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0  # deterministic & scenario-faithful
        )
