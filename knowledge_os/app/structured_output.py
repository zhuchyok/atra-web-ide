"""
Structured Output - Гарантированный JSON от LLM (Anthropic pattern)

Usage:
    from structured_output import StructuredOutput, TaskResult

    output = StructuredOutput(TaskResult)
    result = await output.generate("Проанализируй задачу", context="...")
    print(result.answer, result.confidence)
"""

import json
import os
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

MLX_URL = os.getenv("MLX_API_URL", "http://localhost:11435")
DEFAULT_MODEL = os.getenv("VICTORIA_MODEL", "victoria-wisdom-v3.5")


class StructuredOutputError(Exception):
    pass


class StructuredOutput:
    """
    Structured Output Generator - гарантирует JSON в ответе LLM.
    Pattern: inject schema → parse JSON → validate → retry on failure
    """

    def __init__(
        self,
        schema: Type[BaseModel],
        model: str = DEFAULT_MODEL,
        max_retries: int = 3,
        temperature: float = 0.3,
    ):
        self.schema = schema
        self.model = model
        self.max_retries = max_retries
        self.temperature = temperature
        self._schema_json = self._generate_schema_json(schema)

    def _generate_schema_json(self, schema: Type[BaseModel]) -> str:
        try:
            return schema.model_json_schema()
        except AttributeError:
            return schema.schema()

    def _build_system_prompt(self) -> str:
        return f"""Ты отвечаешь СТРОГО в формате JSON.

IMPORTANT: Ответ ДОЛЖЕН быть валидным JSON по схеме:
{self._schema_json}

Пример: {{"answer": "ответ", "confidence": 0.85}}

НЕ добавляй текст до или после JSON. НЕ используй markdown.
"""

    async def generate(
        self,
        user_prompt: str,
        context: Optional[str] = None,
        category: Optional[str] = None,
    ) -> BaseModel:
        system_prompt = self._build_system_prompt()
        full_prompt = f"{system_prompt}\n\nКонтекст: {context or ''}\n\nЗапрос: {user_prompt}"

        for attempt in range(self.max_retries):
            try:
                response_text = await self._call_llm(full_prompt, category)
                parsed = self._parse_json_response(response_text)
                validated = self.schema(**parsed)
                logger.info(f"[StructuredOutput] OK, attempt {attempt + 1}")
                return validated
            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"[StructuredOutput] Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    full_prompt += "\n\nПопробуй еще раз."

        raise StructuredOutputError(f"Failed after {self.max_retries} attempts")

    async def _call_llm(self, prompt: str, category: Optional[str] = None) -> str:
        url = MLX_URL.rstrip("/")
        is_mlx = "11435" in url

        async with httpx.AsyncClient(timeout=120.0) as client:
            if is_mlx:
                payload = {
                    "category": category or "general",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": 2000},
                }
            else:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": 2000},
                }
            resp = await client.post(f"{url}/api/generate", json=payload)
            if resp.status_code != 200:
                raise StructuredOutputError(f"LLM error: {resp.status_code}")
            return resp.json().get("response", "").strip()

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1] if "```" in text[3:] else text
        if text.startswith("```json"):
            text = text[7:]
        text = text.strip("`").strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise


class TaskResult(BaseModel):
    answer: str = "Нет ответа"
    confidence: float = 0.5
    reasoning: Optional[str] = None


class AnalysisResult(BaseModel):
    summary: str
    key_findings: list[str] = []
    confidence: float = 0.5
    risks: list[str] = []
    recommendations: list[str] = []


class CodeReviewResult(BaseModel):
    issues: list[dict] = []
    score: float = 0.5
    suggestions: list[str] = []
    security_issues: list[str] = []


async def generate_structured(
    prompt: str,
    schema: Type[BaseModel],
    context: Optional[str] = None,
    category: Optional[str] = None,
) -> BaseModel:
    output = StructuredOutput(schema)
    return await output.generate(prompt, context, category)
