from typing import List, Dict, Any
from app.utils.schema import EvaluatorResponse
from app.utils.scoring import aggregate_scores, check_readiness


class Coordinator:
    def aggregate(
        self,
        evaluations: List[EvaluatorResponse],
        current_step: str
    ) -> Dict[str, Any]:

        if not evaluations:
            return {
                "step": current_step,
                "summary": {},
                "agent_feedback": {},
                "combined_explanation": "",
                "scores": {},
                "decision": {
                    "ready_for_next_step": False,
                    "safety_blocked": False,
                    "blocking_issues": ["No evaluations available"],
                    "threshold_used": None,
                },
            }

        agent_feedback = {}
        strengths = []
        issues = []
        explanations = []

        for ev in evaluations:
            agent_feedback[ev.agent_name] = {
                "strengths": ev.strengths,
                "issues_detected": ev.issues_detected,
                "explanation": ev.explanation,
                "verdict": ev.verdict,
                "confidence": ev.confidence,
            }

            strengths.extend([f"[{ev.agent_name}] {s}" for s in ev.strengths])
            issues.extend([f"[{ev.agent_name}] {i}" for i in ev.issues_detected])
            explanations.append(f"[{ev.agent_name}] {ev.explanation}")

        scores = aggregate_scores(evaluations, current_step)
        readiness = check_readiness(
            evaluations,
            current_step,
            scores["composite_score"]
        )

        # 🔥 NORMALIZE DECISION KEYS (CRITICAL)
        decision = {
            "ready_for_next_step": readiness.get("ready_for_next_step", False),
            "safety_blocked": readiness.get("safety_blocked", False),
            "blocking_issues": readiness.get("blocking_issues", []),
            "threshold_used": readiness.get("threshold_used"),
        }

        return {
            "step": current_step,
            "summary": {
                "strengths": strengths,
                "issues_detected": issues,
            },
            "agent_feedback": agent_feedback,
            "combined_explanation": " ".join(explanations),
            "scores": scores,
            "decision": decision,
        }
