"""
Model Validator для кросс-валидации моделей.
Запускает одни и те же тесты на всех моделях и сравнивает качество.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


@dataclass
class ValidationResult:
    """Результат валидации модели"""

    model_name: str
    accuracy: float  # 0.0 - 1.0
    latency_ms: float
    quality_score: float  # 0.0 - 1.0
    tokens_used: int
    errors: List[str]
    passed: bool


class ModelValidator:
    """
    Валидатор моделей для кросс-валидации.
    Запускает тесты на всех моделях и сравнивает результаты.
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.test_prompts = self._get_test_prompts()
        self.min_accuracy_threshold = 0.8  # Минимальная точность для прохождения

    def _get_test_prompts(self) -> List[Dict[str, str]]:
        """Возвращает набор тестовых промптов для валидации"""
        return [
            {
                "prompt": "Напиши функцию на Python для вычисления факториала",
                "category": "coding",
                "expected_keywords": ["def", "factorial", "return"],
            },
            {
                "prompt": "Объясни, что такое REST API",
                "category": "general",
                "expected_keywords": ["REST", "API", "HTTP"],
            },
            {
                "prompt": "Как оптимизировать SQL запрос?",
                "category": "general",
                "expected_keywords": ["SQL", "индекс", "оптимизация"],
            },
            {
                "prompt": "Напиши тест для функции сложения двух чисел",
                "category": "coding",
                "expected_keywords": ["test", "assert", "def"],
            },
            {
                "prompt": "Что такое асинхронное программирование?",
                "category": "general",
                "expected_keywords": ["async", "await", "асинхронный"],
            },
        ]

    async def get_available_models(self, ollama_url: str) -> List[str]:
        """Получить список доступных моделей"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Ошибка получения моделей из {ollama_url}: {e}")
        return []

    async def test_model(
        self, model_name: str, ollama_url: str, test_prompt: Dict[str, str]
    ) -> Tuple[float, float, List[str]]:
        """
        Тестирует модель на одном промпте.

        Returns:
            (accuracy, latency_ms, errors)
        """
        start_time = asyncio.get_event_loop().time()
        errors = []
        accuracy = 0.0

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": model_name, "prompt": test_prompt["prompt"], "stream": False},
                    timeout=60.0,
                )

                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    result_text = data.get("response", "").lower()

                    # Проверяем наличие ожидаемых ключевых слов
                    expected_keywords = test_prompt.get("expected_keywords", [])
                    found_keywords = sum(1 for kw in expected_keywords if kw.lower() in result_text)

                    if expected_keywords:
                        accuracy = found_keywords / len(expected_keywords)
                    else:
                        # Если нет ожидаемых ключевых слов, проверяем, что ответ не пустой
                        accuracy = 1.0 if result_text.strip() else 0.0

                    if not result_text.strip():
                        errors.append("Пустой ответ")
                else:
                    errors.append(f"HTTP {response.status_code}")
                    latency_ms = 0.0

        except asyncio.TimeoutError:
            errors.append("Timeout")
            latency_ms = 0.0
        except Exception as e:
            errors.append(str(e)[:100])
            latency_ms = 0.0

        return accuracy, latency_ms, errors

    async def validate_model(self, model_name: str, ollama_url: str) -> ValidationResult:
        """Валидирует модель на всех тестовых промптах"""
        logger.info(f"🧪 Валидация модели {model_name}...")

        total_accuracy = 0.0
        total_latency = 0.0
        total_tokens = 0
        all_errors = []

        for test_prompt in self.test_prompts:
            accuracy, latency_ms, errors = await self.test_model(
                model_name, ollama_url, test_prompt
            )

            total_accuracy += accuracy
            total_latency += latency_ms
            all_errors.extend(errors)

        avg_accuracy = total_accuracy / len(self.test_prompts) if self.test_prompts else 0.0
        avg_latency = total_latency / len(self.test_prompts) if self.test_prompts else 0.0

        # Quality score = комбинация accuracy и latency
        # Чем выше accuracy и ниже latency, тем выше quality
        latency_score = max(0, 1.0 - (avg_latency / 10000.0))  # Нормализуем latency (10s = 0)
        quality_score = (avg_accuracy * 0.7) + (latency_score * 0.3)

        passed = avg_accuracy >= self.min_accuracy_threshold

        result = ValidationResult(
            model_name=model_name,
            accuracy=avg_accuracy,
            latency_ms=avg_latency,
            quality_score=quality_score,
            tokens_used=total_tokens,
            errors=all_errors,
            passed=passed,
        )

        logger.info(
            f"{'✅' if passed else '❌'} Модель {model_name}: "
            f"accuracy={avg_accuracy:.2f}, latency={avg_latency:.0f}ms, quality={quality_score:.2f}"
        )

        return result

    async def validate_all_models(self, ollama_urls: List[str] = None) -> List[ValidationResult]:
        """Валидирует все доступные модели"""
        if ollama_urls is None:
            ollama_urls = ["http://localhost:11434", "http://localhost:11434"]

        all_results = []

        for ollama_url in ollama_urls:
            models = await self.get_available_models(ollama_url)

            for model_name in models:
                try:
                    result = await self.validate_model(model_name, ollama_url)
                    all_results.append(result)

                    # Сохраняем результат в БД
                    await self.save_validation_result(result, ollama_url)

                    # Если модель не прошла валидацию, понижаем приоритет
                    if not result.passed:
                        logger.warning(
                            f"⚠️ Модель {model_name} не прошла валидацию "
                            f"(accuracy={result.accuracy:.2f} < {self.min_accuracy_threshold})"
                        )
                except Exception as e:
                    logger.error(f"❌ Ошибка валидации модели {model_name}: {e}")

        return all_results

    async def save_validation_result(self, result: ValidationResult, ollama_url: str):
        """Сохраняет результат валидации в БД"""
        if not ASYNCPG_AVAILABLE:
            return

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute(
                    """
                    INSERT INTO model_validation_results
                    (model_name, ollama_url, accuracy, latency_ms, quality_score,
                     tokens_used, errors, passed, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                """,
                    result.model_name,
                    ollama_url,
                    result.accuracy,
                    result.latency_ms,
                    result.quality_score,
                    result.tokens_used,
                    json.dumps(result.errors),
                    result.passed,
                )

                logger.debug(f"✅ Результат валидации {result.model_name} сохранен в БД")
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сохранить результат валидации: {e}")

    async def get_validation_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Получает сводку по валидации за указанный период"""
        if not ASYNCPG_AVAILABLE:
            return {}

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                rows = await conn.fetch(
                    """
                    SELECT
                        model_name,
                        AVG(accuracy) as avg_accuracy,
                        AVG(latency_ms) as avg_latency,
                        AVG(quality_score) as avg_quality,
                        COUNT(*) FILTER (WHERE passed = true) as passed_count,
                        COUNT(*) as total_count
                    FROM model_validation_results
                    WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                    GROUP BY model_name
                    ORDER BY avg_quality DESC
                """,
                    hours,
                )

                summary = {}
                for row in rows:
                    summary[row["model_name"]] = {
                        "avg_accuracy": float(row["avg_accuracy"]) if row["avg_accuracy"] else 0.0,
                        "avg_latency_ms": float(row["avg_latency"]) if row["avg_latency"] else 0.0,
                        "avg_quality": float(row["avg_quality"]) if row["avg_quality"] else 0.0,
                        "passed_count": row["passed_count"],
                        "total_count": row["total_count"],
                        "pass_rate": row["passed_count"] / row["total_count"]
                        if row["total_count"] > 0
                        else 0.0,
                    }

                return summary
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка получения сводки валидации: {e}")
            return {}


# Глобальный экземпляр
_model_validator: Optional[ModelValidator] = None


def get_model_validator() -> ModelValidator:
    """Получить глобальный экземпляр ModelValidator"""
    global _model_validator
    if _model_validator is None:
        _model_validator = ModelValidator()
    return _model_validator
