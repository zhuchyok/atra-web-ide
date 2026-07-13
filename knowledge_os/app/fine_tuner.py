"""
Fine-tuner - Local + OpenAI Fine-tuning API wrapper

Usage:
    from fine_tuner import FineTuner

    tuner = FineTuner()
    job = await tuner.create_job("my-model", training_data)
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MLX_FINE_TUNE_URL = os.getenv("MLX_FINE_TUNE_URL", "http://localhost:11435")


class FineTuner:
    """
    Fine-tuning wrapper for OpenAI API + local MLX.
    """

    def __init__(self):
        self.openai_key = OPENAI_API_KEY
        self.mlx_url = MLX_FINE_TUNE_URL

    async def create_job(
        self,
        model_name: str,
        training_data: List[Dict[str, Any]],
        base_model: str = "gpt-4o-mini",
    ) -> Dict[str, Any]:
        """Create fine-tuning job."""
        if self.openai_key:
            return await self._openai_fine_tune(model_name, training_data, base_model)
        return await self._mlx_fine_tune(model_name, training_data)

    async def _openai_fine_tune(
        self,
        model_name: str,
        training_data: List[Dict[str, Any]],
        base_model: str,
    ) -> Dict[str, Any]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/fine_tuning/jobs",
                    headers={"Authorization": f"Bearer {self.openai_key}"},
                    json={
                        "training_file": training_data,
                        "model": base_model,
                        "suffix": model_name,
                    },
                )
                return resp.json()
        except Exception as e:
            logger.error(f"[FineTuner] OpenAI error: {e}")
            return {"error": str(e)}

    async def _mlx_fine_tune(
        self,
        model_name: str,
        training_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        import json

        import httpx

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                training_file = "training.JSONL"
                with open(training_file, "w", encoding="utf-8") as f:
                    for item in training_data:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")

                with open(training_file, "rb") as f:
                    files = {"file": f}
                    resp = await client.post(
                        f"{self.mlx_url}/api/fineTune",
                        files={"file": training_file},
                        data={
                            "model": model_name,
                            "epochs": 3,
                        },
                    )

                if resp.status_code == 200:
                    result = resp.json()
                    logger.info(f"[FineTuner] MLX fine-tune started: {result.get('id')}")
                    return {"status": "started", "job_id": result.get("id"), "model": model_name}
                else:
                    logger.warning(f"[FineTuner] MLX fine-tune failed: {resp.status_code}")
                    return {"status": "error", "error": resp.text}
        except httpx.ConnectError:
            logger.warning(f"[FineTuner] Cannot connect to MLX at {self.mlx_url}")
            return {"status": "error", "message": "MLX not available"}
        except Exception as e:
            logger.error(f"[FineTuner] MLX fine-tune error: {e}")
            return {"status": "error", "message": str(e)}

    async def list_jobs(self) -> List[Dict[str, Any]]:
        """List fine-tuning jobs."""
        if not self.openai_key:
            return []
        import httpx

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/fine_tuning/jobs",
                    headers={"Authorization": f"Bearer {self.openai_key}"},
                )
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.error(f"[FineTuner] List error: {e}")
            return []


_instance: Optional[FineTuner] = None


def get_fine_tuner() -> FineTuner:
    global _instance
    if _instance is None:
        _instance = FineTuner()
    return _instance
