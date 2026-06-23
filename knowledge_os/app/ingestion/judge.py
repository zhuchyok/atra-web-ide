import os
from typing import Dict


class IngestionJudge:
    """
    Borderline candidate judge contract.
    Default mode is fail-closed (reject) unless explicitly enabled with a custom implementation.
    """

    def __init__(self):
        self.enabled = os.getenv("INGESTION_JUDGE_ENABLED", "false").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        self.timeout_sec = float(os.getenv("INGESTION_JUDGE_TIMEOUT_SEC", "8"))

    async def evaluate(self, text: str, source_type: str) -> Dict:
        """
        Must return payload with:
          - decision: accept|reject
          - reason: string
          - quality_score: float 0..1
        """
        if not self.enabled:
            return {
                "decision": "reject",
                "reason": "judge_disabled",
                "quality_score": 0.0,
            }

        # Placeholder for future strict-model judge integration.
        # Keeping behavior fail-closed by default.
        return {
            "decision": "reject",
            "reason": "judge_not_implemented",
            "quality_score": 0.0,
        }
