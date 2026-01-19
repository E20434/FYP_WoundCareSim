from typing import List, Dict


class HistoryCompletenessService:
    """
    Performs deterministic completeness checks
    for HISTORY-taking conversations.
    """

    def analyze(
        self,
        transcript: str,
        required_points: List[str]
    ) -> Dict[str, List[str]]:
        """
        Compare aggregated transcript against required points.

        Args:
            transcript: Full HISTORY conversation text
            required_points: Required history topics from scenario

        Returns:
            {
              covered_points: [...],
              missing_points: [...],
              summary: str
            }
        """

        transcript_lower = transcript.lower()

        covered = []
        missing = []

        for point in required_points:
            if point.lower() in transcript_lower:
                covered.append(point)
            else:
                missing.append(point)

        summary = self._generate_summary(covered, missing)

        return {
            "covered_points": covered,
            "missing_points": missing,
            "summary": summary
        }

    def _generate_summary(
        self,
        covered: List[str],
        missing: List[str]
    ) -> str:
        if not missing:
            return (
                "All required history points were covered "
                "during the interaction."
            )

        return (
            "History taking covered the following points: "
            f"{', '.join(covered)}. "
            "However, the following areas were missed: "
            f"{', '.join(missing)}."
        )
