from app.core.state_machine import Step, next_step
from typing import Optional, Dict, Any, List
from datetime import datetime


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def create_session(
        self,
        scenario_id: str,
        student_id: str,
        scenario_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        session_id = f"sess_{len(self.sessions)+1}_{int(datetime.now().timestamp())}"

        self.sessions[session_id] = {
            "scenario_id": scenario_id,
            "student_id": student_id,
            "current_step": Step.HISTORY.value,
            "attempt_count": {},
            "last_evaluation": None,
            "locked_step": False,
            "scenario_metadata": scenario_metadata or {},
            "logs": [],
            "rag_results": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def store_last_evaluation(self, session_id: str, evaluation: Dict[str, Any]) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["last_evaluation"] = evaluation
            session["updated_at"] = datetime.now().isoformat()

    def increment_attempt(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return
        step = session["current_step"]
        session["attempt_count"][step] = session["attempt_count"].get(step, 0) + 1

    def reset_attempts(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["attempt_count"][session["current_step"]] = 0

    def lock_current_step(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["locked_step"] = True

    def advance_step(self, session_id: str) -> Optional[str]:
        session = self.sessions.get(session_id)
        if not session or session["locked_step"]:
            return None

        current_step = Step(session["current_step"])
        new_step = next_step(current_step)

        session["current_step"] = new_step.value
        session["locked_step"] = False
        session["updated_at"] = datetime.now().isoformat()

        return new_step.value
