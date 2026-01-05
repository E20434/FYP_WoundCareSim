from app.core.state_machine import Step, next_step
from typing import Optional, Dict, Any
from datetime import datetime


MAX_ATTEMPTS_PER_STEP = 3


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    # ----------------------------
    # Session lifecycle
    # ----------------------------

    def create_session(
        self,
        scenario_id: str,
        student_id: str,
        scenario_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = f"sess_{len(self.sessions) + 1}_{int(datetime.now().timestamp())}"

        self.sessions[session_id] = {
            "scenario_id": scenario_id,
            "student_id": student_id,
            "current_step": Step.HISTORY.value,
            "attempt_count": {},
            "last_evaluation": None,
            "locked": False,
            "lock_reason": None,
            "scenario_metadata": scenario_metadata or {},
            "logs": [],
            "rag_results": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    # ----------------------------
    # Evaluation & logging
    # ----------------------------

    def store_last_evaluation(self, session_id: str, evaluation: Dict[str, Any]) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["last_evaluation"] = evaluation
            session["updated_at"] = datetime.now().isoformat()

    def add_log(self, session_id: str, log: Dict[str, Any]) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["logs"].append(log)
            session["updated_at"] = datetime.now().isoformat()

    def add_rag_result(self, session_id: str, rag_result: Dict[str, Any]) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["rag_results"].append(rag_result)

    # ----------------------------
    # Attempt handling
    # ----------------------------

    def increment_attempt(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return

        step = session["current_step"]
        session["attempt_count"][step] = session["attempt_count"].get(step, 0) + 1
        session["updated_at"] = datetime.now().isoformat()

    def reset_attempts(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["attempt_count"][session["current_step"]] = 0

    def exceeded_max_attempts(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        step = session["current_step"]
        return session["attempt_count"].get(step, 0) >= MAX_ATTEMPTS_PER_STEP

    # ----------------------------
    # Locking & safety
    # ----------------------------

    def lock_session(self, session_id: str, reason: str) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["locked"] = True
            session["lock_reason"] = reason
            session["updated_at"] = datetime.now().isoformat()

    # ----------------------------
    # Step progression
    # ----------------------------

    def advance_step(self, session_id: str) -> Optional[str]:
        session = self.sessions.get(session_id)
        if not session or session["locked"]:
            return None

        current_step = Step(session["current_step"])
        new_step = next_step(current_step)

        session["current_step"] = new_step.value
        session["attempt_count"][new_step.value] = 0
        session["updated_at"] = datetime.now().isoformat()

        return new_step.value
