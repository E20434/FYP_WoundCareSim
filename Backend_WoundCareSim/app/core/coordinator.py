from typing import List, Dict, Any
from app.utils.schema import EvaluatorResponse
from app.utils.scoring import aggregate_scores, check_readiness


class Coordinator:
    def aggregate(
        self,
        evaluations: List[EvaluatorResponse],
        current_step: str
    ) -> Dict[str, Any]:

        # -------------------------------------------------
        # No evaluations case
        # -------------------------------------------------
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
                    "threshold_used": None
                }
            }

        # -------------------------------------------------
        # Collect per-agent feedback
        # -------------------------------------------------
        agent_feedback = {}
        all_strengths = []
        all_issues = []
        explanations = []

        for ev in evaluations:
            agent_feedback[ev.agent_name] = {
                "strengths": ev.strengths,
                "issues_detected": ev.issues_detected,
                "explanation": ev.explanation,
                "verdict": ev.verdict,
                "confidence": ev.confidence,
            }

            all_strengths.extend(
                [f"[{ev.agent_name}] {s}" for s in ev.strengths]
            )
            all_issues.extend(
                [f"[{ev.agent_name}] {i}" for i in ev.issues_detected]
            )
            explanations.append(
                f"[{ev.agent_name}] {ev.explanation}"
            )

        # -------------------------------------------------
        # Scoring & readiness (Week-5 logic)
        # -------------------------------------------------
        score_result = aggregate_scores(evaluations, current_step)

        readiness_result = check_readiness(
            evaluations,
            current_step,
            score_result["composite_score"]
        )

        # -------------------------------------------------
        # SAFETY OVERRIDE (Week-6 — CRITICAL)
        # -------------------------------------------------
        safety_blocked = False
        blocking_issues = []

        if current_step in ["CLEANING", "DRESSING"]:
            for ev in evaluations:
                if ev.agent_name == "ClinicalAgent" and ev.verdict == "Inappropriate":
                    safety_blocked = True
                    blocking_issues.append(
                        "Unsafe clinical action detected during procedure"
                    )
                    break

        # -------------------------------------------------
        # FINAL DECISION (Safety overrides readiness)
        # -------------------------------------------------
        decision = {
            "ready_for_next_step": (
                False if safety_blocked else readiness_result.get("ready_for_next_step", False)
            ),
            "safety_blocked": safety_blocked,
            "blocking_issues": blocking_issues,
            "threshold_used": readiness_result.get("threshold_used"),
        }

        # -------------------------------------------------
        # Final aggregated response
        # -------------------------------------------------
        return {
            "step": current_step,
            "summary": {
                "strengths": all_strengths,
                "issues_detected": all_issues,
            },
            "agent_feedback": agent_feedback,
            "combined_explanation": " ".join(explanations),
            "scores": score_result,
            "decision": decision,
        }
