from app.core.state_machine import Step, next_step
from typing import Optional, Dict, Any, List
from datetime import datetime

class SessionManager:
    """
    Tracks active sessions and their current step.
    Week 2: stores sessions in memory.
    Week 6: move to Firestore.
    """

    def __init__(self):
        self.sessions = {}

    def create_session(
        self, 
        scenario_id: str, 
        student_id: str,
        scenario_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new session with enhanced metadata tracking.
        
        Args:
            scenario_id: ID of the scenario being used
            student_id: ID of the student
            scenario_metadata: Full scenario metadata from Firestore
            
        Returns:
            session_id: Unique session identifier
        """
        session_id = f"sess_{len(self.sessions)+1}_{int(datetime.now().timestamp())}"
        
        self.sessions[session_id] = {
            "scenario_id": scenario_id,
            "student_id": student_id,
            "current_step": Step.HISTORY.value,
            "scenario_metadata": scenario_metadata or {},
            "logs": [],
            "rag_results": [],  # Store RAG retrieval results for debugging
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "events": []  # Keep for backward compatibility
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data by session ID.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Session data dictionary or None if not found
        """
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update session fields.
        
        Args:
            session_id: The session identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if updated successfully, False if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.update(updates)
        session["updated_at"] = datetime.now().isoformat()
        return True

    def add_rag_result(self, session_id: str, rag_data: Dict[str, Any]) -> bool:
        """
        Store RAG retrieval results for debugging purposes.
        
        Args:
            session_id: The session identifier
            rag_data: RAG retrieval result data
            
        Returns:
            True if added successfully, False if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session["rag_results"].append({
            "timestamp": datetime.now().isoformat(),
            "data": rag_data
        })
        session["updated_at"] = datetime.now().isoformat()
        return True

    def add_log(self, session_id: str, log_entry: Dict[str, Any]) -> bool:
        """
        Add a log entry to the session.
        
        Args:
            session_id: The session identifier
            log_entry: Log data to store
            
        Returns:
            True if added successfully, False if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "entry": log_entry
        })
        session["updated_at"] = datetime.now().isoformat()
        return True

    def advance_step(self, session_id: str) -> Optional[str]:
        """
        Advance the session to the next step in the state machine.
        
        Args:
            session_id: The session identifier
            
        Returns:
            The new step value or None if advancement failed
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        current_step = Step(session["current_step"])
        try:
            new_step = next_step(current_step)
            session["current_step"] = new_step.value
            session["updated_at"] = datetime.now().isoformat()
            return new_step.value
        except Exception:
            return None

    def get_scenario_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the scenario metadata for a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Scenario metadata dictionary or None if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return None
        return session.get("scenario_metadata")

    def list_sessions(self, student_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all sessions, optionally filtered by student ID.
        
        Args:
            student_id: Optional student ID to filter by
            
        Returns:
            List of session summaries
        """
        sessions_list = []
        for sid, session in self.sessions.items():
            if student_id and session.get("student_id") != student_id:
                continue
            
            sessions_list.append({
                "session_id": sid,
                "scenario_id": session.get("scenario_id"),
                "student_id": session.get("student_id"),
                "current_step": session.get("current_step"),
                "created_at": session.get("created_at"),
                "updated_at": session.get("updated_at")
            })
        
        return sessions_list

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            True if deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False