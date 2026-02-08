import json

from pydantic import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

class ClinicalAgent(BaseAgent):
    """
    Evaluates clinical and procedural correctness for cleaning and dressing preparation.
    
    REAL-TIME MODE: Provides immediate feedback when action is performed
    FINAL MODE: No final evaluation - real-time feedback is sufficient
    
    Actions and sequences are defined in RAG guidelines using consistent action_ identifiers.
    """

    def __init__(self):
        super().__init__()

    async def get_real_time_feedback(
        self,
        action_type: str,
        performed_actions: list[dict],
        rag_guidelines: str
    ) -> dict:
        """
        Provides immediate feedback when an action is performed.
        
        Uses RAG guidelines to determine if:
        1. This action is appropriate at this point
        2. ANY prerequisite actions are missing (comprehensive check)
        3. This action completes correctly
        
        Returns simple, actionable feedback for the student.
        
        IMPORTANT: Action names must match exactly between:
        - Frontend action_type (e.g., "action_clean_trolley")
        - RAG guidelines (e.g., "action_clean_trolley")
        - This ensures no naming mismatches
        """
        
        # Format previously performed actions - use action_type directly
        if performed_actions:
            action_history = "\n".join([
                f"- {act['action_type']}"
                for act in performed_actions
            ])
        else:
            action_history = "None - this is the first action."
        
        system_prompt = (
            "You are a clinical skills evaluator providing REAL-TIME feedback during wound care preparation.\n\n"
            "ROLE: Verify if the current action can be performed based on what has been completed.\n\n"
            "REFERENCE GUIDELINES:\n"
            f"{rag_guidelines}\n\n"
            "EVALUATION LOGIC:\n"
            "1. Look at the CURRENT ACTION being performed (e.g., 'action_select_solution')\n"
            "2. Look at the COMPLETED ACTIONS list (actions already done)\n"
            "3. From the guidelines, find what prerequisites are required BEFORE the current action\n"
            "   CRITICAL: Prerequisites are actions that must be completed BEFORE the current action.\n"
            "   The CURRENT ACTION itself is NEVER its own prerequisite!\n"
            "   NEVER include the current action in the missing_actions list!\n"
            "4. Check: Are ALL those prerequisite actions in the COMPLETED list?\n"
            "5. Decision:\n"
            "   - If ALL prerequisites completed → status='complete', positive message, missing_actions=[]\n"
            "   - If ANY prerequisites missing → status='missing_prerequisites', list ONLY missing ones\n\n"
            "ACTION MATCHING RULE:\n"
            "- Action identifiers: action_initial_hand_hygiene, action_clean_trolley, etc.\n"
            "- Match them EXACTLY as they appear in the guidelines\n"
            "- Prerequisites are actions that come BEFORE the current action in the sequence\n\n"
            "FEEDBACK MESSAGE RULES:\n"
            "- When CORRECT (all prerequisites met):\n"
            "  DO NOT say: 'Correct!' or 'Great!' or 'You can proceed'\n"
            "  INSTEAD say: 'You performed [action name] correctly.'\n"
            "  Example: 'You performed Initial Hand Hygiene correctly.'\n"
            "  Example: 'You performed Clean The Dressing Trolley correctly.'\n\n"
            "- When MISSING prerequisites:\n"
            "  DO NOT say: 'Before X, complete Y'\n"
            "  INSTEAD say: 'You missed [action name]. Please complete it first.'\n"
            "  If multiple missing: 'You missed [action1], [action2], and [action3]. Please complete them first.'\n"
            "  Example: 'You missed Clean The Dressing Trolley. Please complete it first.'\n"
            "  Example: 'You missed Clean The Dressing Trolley and Hand Hygiene After Cleaning. Please complete them first.'\n\n"
            "EXAMPLES:\n\n"
            "Example 1 (Correct):\n"
            "   COMPLETED: ['action_initial_hand_hygiene']\n"
            "   CURRENT: 'action_clean_trolley'\n"
            "   Prerequisites: [action_initial_hand_hygiene]\n"
            "   All met? YES\n"
            "   Response: {\"status\": \"complete\", \"message\": \"You performed Clean The Dressing Trolley correctly.\", \"missing_actions\": [], \"can_proceed\": true}\n\n"
            "Example 2 (Correct - Action 4):\n"
            "   COMPLETED: ['action_initial_hand_hygiene', 'action_clean_trolley', 'action_hand_hygiene_after_cleaning']\n"
            "   CURRENT: 'action_select_solution'\n"
            "   Prerequisites: [action_initial_hand_hygiene, action_clean_trolley, action_hand_hygiene_after_cleaning]\n"
            "   All met? YES\n"
            "   Response: {\"status\": \"complete\", \"message\": \"You performed Select Prescribed Cleaning Solution correctly.\", \"missing_actions\": [], \"can_proceed\": true}\n\n"
            "Example 3 (Missing one prerequisite):\n"
            "   COMPLETED: ['action_initial_hand_hygiene', 'action_hand_hygiene_after_cleaning']\n"
            "   CURRENT: 'action_select_solution'\n"
            "   Prerequisites: [action_initial_hand_hygiene, action_clean_trolley, action_hand_hygiene_after_cleaning]\n"
            "   Missing: [action_clean_trolley]\n"
            "   Response: {\"status\": \"missing_prerequisites\", \"message\": \"You missed Clean The Dressing Trolley. Please complete it first.\", \"missing_actions\": [\"action_clean_trolley\"], \"can_proceed\": false}\n\n"
            "Example 4 (Missing multiple prerequisites):\n"
            "   COMPLETED: ['action_initial_hand_hygiene']\n"
            "   CURRENT: 'action_verify_solution'\n"
            "   Prerequisites: [action_initial_hand_hygiene, action_clean_trolley, action_hand_hygiene_after_cleaning, action_select_solution]\n"
            "   Missing: [action_clean_trolley, action_hand_hygiene_after_cleaning, action_select_solution]\n"
            "   Response: {\"status\": \"missing_prerequisites\", \"message\": \"You missed Clean The Dressing Trolley, Hand Hygiene After Trolley Cleaning, and Select Prescribed Cleaning Solution. Please complete them first.\", \"missing_actions\": [\"action_clean_trolley\", \"action_hand_hygiene_after_cleaning\", \"action_select_solution\"], \"can_proceed\": false}\n\n"
            "You MUST respond with valid JSON:\n"
            "{\n"
            '  "status": "complete" | "missing_prerequisites",\n'
            '  "message": "Follow the feedback message rules above",\n'
            '  "missing_actions": [],\n'
            '  "can_proceed": true | false\n'
            "}\n"
        )
        
        user_prompt = (
            f"COMPLETED ACTIONS:\n{action_history}\n\n"
            f"CURRENT ACTION BEING PERFORMED:\n{action_type}\n\n"
            "Step-by-step evaluation:\n"
            "1. Find '{current_action}' in the guidelines\n"
            "2. Look at its prerequisites list\n"
            "3. For each prerequisite, check: Is it in the COMPLETED ACTIONS list?\n"
            "4. List ONLY the prerequisites that are NOT in COMPLETED (exclude the current action itself)\n"
            "5. Create appropriate message:\n"
            "   - If no missing prerequisites: 'You performed [action description] correctly.'\n"
            "   - If missing prerequisites: 'You missed [action1], [action2]. Please complete them first.'\n\n"
            "REMINDER: '{current_action}' is the CURRENT action. Do NOT include it in missing_actions!\n\n"
            "Provide evaluation in JSON format.".replace("{current_action}", action_type)
        )
        
        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,  # Deterministic
        )
        
        try:
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            feedback = json.loads(clean_json)
            
            # POST-PROCESSING: Remove current action from missing_actions if LLM included it
            if feedback.get("missing_actions") and action_type in feedback["missing_actions"]:
                feedback["missing_actions"].remove(action_type)
                # If that was the only missing action, change status to complete
                if not feedback["missing_actions"]:
                    feedback["status"] = "complete"
                    feedback["can_proceed"] = True
                    feedback["message"] = f"You performed {self._format_action_name(action_type)} correctly."
            
            # Add metadata
            feedback["action_type"] = action_type
            feedback["total_actions_so_far"] = len(performed_actions) + 1
            
            # ENHANCED: Format message according to requirements
            if feedback.get("status") == "complete":
                # Correct action - use "You performed X correctly" format
                action_name = self._format_action_name(action_type)
                feedback["message"] = f"You performed {action_name} correctly."
                
            elif feedback.get("missing_actions"):
                # Missing prerequisites - use "You missed X" format
                missing_names = [self._format_action_name(act) for act in feedback["missing_actions"]]
                
                if len(missing_names) == 1:
                    feedback["message"] = f"You missed {missing_names[0]}. Please complete it first."
                elif len(missing_names) == 2:
                    feedback["message"] = f"You missed {missing_names[0]} and {missing_names[1]}. Please complete them first."
                else:
                    # 3+ missing actions
                    all_but_last = ", ".join(missing_names[:-1])
                    feedback["message"] = f"You missed {all_but_last}, and {missing_names[-1]}. Please complete them first."
            
            return feedback
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ Real-time feedback parsing failed: {e}")
            print(f"Raw response: {raw_response}")
            # Fallback
            return {
                "status": "complete",
                "message": f"You performed {self._format_action_name(action_type)} correctly.",
                "missing_actions": [],
                "can_proceed": True,
                "action_type": action_type,
                "total_actions_so_far": len(performed_actions) + 1
            }

    def _format_action_name(self, action_type: str) -> str:
        """
        Convert action_type to readable name for user messages.
        Maps to the descriptions used in RAG guidelines.
        """
        action_names = {
            "action_initial_hand_hygiene": "Initial Hand Hygiene",
            "action_clean_trolley": "Clean The Dressing Trolley",
            "action_hand_hygiene_after_cleaning": "Hand Hygiene After Trolley Cleaning",
            "action_select_solution": "Select Prescribed Cleaning Solution",
            "action_verify_solution": "Verify Cleaning Solution With Staff Nurse",
            "action_select_dressing": "Select Dressing Materials",
            "action_verify_dressing": "Verify Sterile Dressing Packet With Staff Nurse",
            "action_arrange_materials": "Arrange Solutions And Materials On Trolley",
            "action_bring_trolley": "Bring Prepared Trolley To Patient Area",
        }
        
        return action_names.get(
            action_type,
            action_type.replace("action_", "").replace("_", " ").title()
        )

    async def evaluate(
        self,
        current_step: str,
        student_input: str,
        scenario_metadata: dict,
        rag_response: str,
    ) -> EvaluatorResponse:
        """
        NO FINAL EVALUATION for cleaning_and_dressing step.
        Real-time feedback during actions is sufficient.
        
        This method returns None to indicate no evaluation needed.
        """
        
        # Return None to indicate this step doesn't need final evaluation
        return None
    