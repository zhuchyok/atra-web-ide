import json
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AnomalyDetectorBridge:
    """
    [SINGULARITY 21.23] Bridge for Anomaly Detection logic with Rust acceleration.
    """

    @staticmethod
    async def analyze_request(
        prompt: str, request_id: str, expert_name: str, category: str
    ) -> Tuple[bool, Optional[Any]]:
        # [SINGULARITY 21.23] Try Rust Anomaly Detector first
        try:
            import httpx

            rust_url = "http://localhost:8081/api/security/analyze"
            payload = {
                "prompt": prompt,
                "request_id": request_id,
                "expert_name": expert_name,
                "category": category,
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(rust_url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    should_block = data.get("should_block", False)
                    alert = data.get("alert")
                    if should_block:
                        logger.warning(
                            f"🛡️ [RUST ANOMALY] Request {request_id} blocked by Rust Gateway."
                        )
                    return should_block, alert
        except Exception as re:
            logger.debug(f"⚠️ Rust Anomaly Detector failed, falling back to Python: {re}")

        # Fallback to Python logic
        try:
            from anomaly_detector import get_anomaly_detector

            detector = get_anomaly_detector()
            should_block, alert = await detector.analyze_request(
                prompt,
                identifier=request_id,
                metadata={"expert_name": expert_name, "category": category},
            )
            return should_block, alert
        except Exception as e:
            logger.debug(f"Python Anomaly detection failed: {e}")
            return False, None

    @staticmethod
    def is_blocked(request_id: str) -> bool:
        # [SINGULARITY 21.23] Check Rust blocklist first
        # (In a real implementation, this would be a fast Redis/In-memory check in Rust)
        try:
            from anomaly_detector import get_anomaly_detector

            detector = get_anomaly_detector()
            return detector.is_blocked(request_id)
        except:
            return False
