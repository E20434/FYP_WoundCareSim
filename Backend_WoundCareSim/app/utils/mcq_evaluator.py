from typing import Dict, List, Any


class MCQEvaluator:
    """
    Educational MCQ evaluator for ASSESSMENT step.

    Principles:
    - No blocking
    - No retries
    - No pass/fail
    - Always returns feedback
    """

    @staticmethod
    def validate_mcq_answers(
        student_answers: Dict[str, str],
        assessment_questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate MCQ answers against Firestore questions.

        Firestore format (per question):
        {
          "id": "q1",
          "question": "...",
          "options": [...],
          "correct_answer": "Wash hands"
        }
        """

        if not assessment_questions:
            return {
                "total_questions": 0,
                "correct_count": 0,
                "feedback": [],
                "summary": "No MCQ questions available"
            }

        feedback = []
        correct_count = 0

        for q in assessment_questions:
            qid = q.get("id")
            question_text = q.get("question", "")
            correct_answer = q.get("correct_answer")

            student_answer = student_answers.get(qid)

            if student_answer == correct_answer:
                correct_count += 1
                feedback.append({
                    "question_id": qid,
                    "question": question_text,
                    "status": "correct",
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "explanation": "Correct answer."
                })
            else:
                feedback.append({
                    "question_id": qid,
                    "question": question_text,
                    "status": "incorrect",
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "explanation": (
                        f"The correct answer is '{correct_answer}'."
                        if correct_answer else
                        "Correct answer not available."
                    )
                })

        total = len(assessment_questions)
        score = correct_count / total if total > 0 else 0.0

        return {
            "total_questions": total,
            "correct_count": correct_count,
            "score": round(score, 2),
            "feedback": feedback,
            "summary": f"{correct_count}/{total} correct"
        }

    # -------------------------------------------------
    # Optional helper (safe to keep for future use)
    # -------------------------------------------------
    @staticmethod
    def get_mcq_summary(mcq_result: Dict[str, Any]) -> str:
        """
        Returns a simple human-readable summary.
        """
        total = mcq_result.get("total_questions", 0)
        correct = mcq_result.get("correct_count", 0)

        if total == 0:
            return "No MCQs available"

        return f"{correct}/{total} questions answered correctly"
