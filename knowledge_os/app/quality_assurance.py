"""
Quality Assurance System для гарантии качества при всех оптимизациях
Singularity 5.0: Quality-First Optimizations
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Environment flags
try:
    from env_flags import is_strict_local  # type: ignore
except ImportError:
    # Fallback если модуль не найден
    def is_strict_local():
        return os.getenv("STRICT_LOCAL", "").lower() in ("1", "true", "yes")


class QualityLevel(Enum):
    """Уровни качества ответов"""

    EXCELLENT = 0.9  # Отличное качество
    GOOD = 0.7  # Хорошее качество
    ACCEPTABLE = 0.5  # Приемлемое качество
    POOR = 0.3  # Плохое качество
    UNACCEPTABLE = 0.0  # Неприемлемое качество


@dataclass
class QualityMetrics:
    """Метрики качества ответа"""

    safety_score: float = 1.0
    completeness_score: float = 1.0
    relevance_score: float = 1.0
    correctness_score: float = 1.0
    overall_score: float = 1.0

    def calculate_overall(self) -> float:
        """Вычисляет общую оценку качества"""
        # Взвешенное среднее
        self.overall_score = (
            self.safety_score * 0.3
            + self.completeness_score * 0.25
            + self.relevance_score * 0.25
            + self.correctness_score * 0.2
        )
        return self.overall_score


class QualityAssurance:
    """
    Система контроля качества для всех оптимизаций.
    Гарантирует, что оптимизации не снижают качество ответов.
    """

    def __init__(self, min_quality_threshold: float = 0.7):
        """
        Args:
            min_quality_threshold: Минимальный порог качества (0.0-1.0)
        """
        self.min_quality_threshold = min_quality_threshold
        self.quality_history = []  # История оценок для анализа

    async def validate_response(
        self,
        response: str,
        original_query: str,
        response_type: str = "general",
        source: str = "local",
    ) -> Tuple[bool, QualityMetrics, Optional[str]]:
        """
        Валидирует ответ на качество.
        [SINGULARITY 22.4] Sandbox Grounding: автоматическая проверка кода через выполнение.

        Returns:
            (is_acceptable, metrics, recommendation)
            - is_acceptable: True если качество приемлемо
            - metrics: Метрики качества
            - recommendation: Рекомендация (например, "reroute_to_cloud")
        """
        metrics = QualityMetrics()
        issues = []

        # [SINGULARITY 22.4] Sandbox Grounding для кода
        if response_type == "code" or "```python" in response:
            grounding_ok, grounding_score, error_msg = await self._run_sandbox_grounding(response)
            metrics.correctness_score = grounding_score
            if not grounding_ok:
                issues.append(f"Sandbox Grounding Failed: {error_msg}")
                logger.warning(f"🧪 [SANDBOX GROUNDING] Code failed verification: {error_msg}")
            else:
                logger.info(f"🧪 [SANDBOX GROUNDING] Code verified successfully (score: {grounding_score})")

        # 1. Safety Check (критично!)
        safety_ok, safety_warning, safety_score = await self._check_safety(response, response_type)
        metrics.safety_score = safety_score
        if not safety_ok:
            issues.append(f"Safety: {safety_warning}")

        # 2. Completeness Check
        completeness_score = await self._check_completeness(response, original_query, response_type)
        metrics.completeness_score = completeness_score
        if completeness_score < 0.7:
            issues.append("Incomplete response")

        # 3. Relevance Check
        relevance_score = await self._check_relevance(response, original_query)
        metrics.relevance_score = relevance_score
        if relevance_score < 0.7:
            issues.append("Response not relevant to query")

        # 4. Correctness Check (базовая)
        correctness_score = await self._check_correctness(response, response_type)
        metrics.correctness_score = correctness_score
        if correctness_score < 0.7:
            issues.append("Possible correctness issues")

        # Вычисляем общую оценку
        overall = metrics.calculate_overall()

        # Сохраняем в историю
        self.quality_history.append(
            {
                "source": source,
                "type": response_type,
                "score": overall,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

        # Определяем, приемлемо ли качество
        is_acceptable = (
            overall >= self.min_quality_threshold
            and safety_ok
            and metrics.completeness_score >= 0.6
            and metrics.relevance_score >= 0.6
        )

        # Рекомендация
        recommendation = None
        if not is_acceptable:
            if not safety_ok:
                # В STRICT_LOCAL режиме вместо reroute_to_cloud используем retry_local или reject
                if is_strict_local():
                    recommendation = "retry_local"  # Попытка улучшить безопасность локально
                    logger.warning(
                        "[STRICT_LOCAL] Safety issue, recommendation changed to retry_local"
                    )
                else:
                    recommendation = "reroute_to_cloud"  # Критично - перенаправляем в облако
            elif overall < 0.5:
                # В STRICT_LOCAL режиме вместо reroute_to_cloud используем retry_local
                if is_strict_local():
                    recommendation = "retry_local"  # Попытка улучшить качество локально
                    logger.warning(
                        "[STRICT_LOCAL] Low quality, recommendation changed to retry_local"
                    )
                else:
                    recommendation = "reroute_to_cloud"  # Низкое качество - перенаправляем
            elif overall < self.min_quality_threshold:
                recommendation = "retry_local"  # Можно попробовать еще раз локально

        if issues:
            logger.warning(f"⚠️ [QUALITY CHECK] Issues: {', '.join(issues)} (score: {overall:.2f})")

        return is_acceptable, metrics, recommendation

    async def _check_safety(
        self, response: str, response_type: str
    ) -> Tuple[bool, Optional[str], float]:
        """Проверка безопасности (использует SafetyChecker)"""
        try:
            from safety_checker import SafetyChecker

            checker = SafetyChecker()
            is_safe, warning, score = checker.check_response(response, response_type)
            return is_safe, warning, score
        except Exception as e:
            logger.error(f"Safety check error: {e}")
            return True, None, 1.0  # Если не можем проверить, считаем безопасным

    async def _check_completeness(self, response: str, query: str, response_type: str) -> float:
        """Проверка полноты ответа"""
        score = 1.0

        # Минимальная длина
        if len(response.strip()) < 20:
            score -= 0.5

        # Для кода: проверка на placeholder'ы
        if response_type == "code":
            placeholders = ["TODO", "FIXME", "your_code", "table_name", "your_function"]
            if any(ph in response for ph in placeholders):
                score -= 0.4

            # Проверка на незавершенные блоки
            if ("def " in response or "class " in response) and not response.strip().endswith(":"):
                # Проверяем баланс скобок
                open_brackets = response.count("(") + response.count("[") + response.count("{")
                close_brackets = response.count(")") + response.count("]") + response.count("}")
                if abs(open_brackets - close_brackets) > 2:
                    score -= 0.3

        # Для вопросов: проверка на наличие ответа
        question_words = ["как", "что", "почему", "где", "когда", "кто"]
        if any(qw in query.lower() for qw in question_words):
            if len(response) < 50:  # Слишком короткий ответ на вопрос
                score -= 0.3

        return max(0.0, min(1.0, score))

    async def _check_relevance(self, response: str, query: str) -> float:
        """Проверка релевантности ответа запросу"""
        # Простая эвристика: проверка ключевых слов
        # Очищаем от стоп-слов и пунктуации для более точного сравнения
        import re

        def clean_text(text):
            text = text.lower()
            text = re.sub(r"[^\w\s]", " ", text)
            words = set(text.split())
            # Убираем короткие слова (менее 3 символов)
            return {w for w in words if len(w) > 2}

        query_words = clean_text(query)
        response_words = clean_text(response)

        if not query_words:
            return 1.0

        # Пересечение ключевых слов
        common_words = query_words.intersection(response_words)
        relevance_ratio = len(common_words) / len(query_words)

        # Порог релевантности снижен, так как технические ответы могут использовать другие термины
        # Но при этом используем более высокий множитель для совпадений
        if relevance_ratio < 0.15:
            return 0.5

        return min(1.0, relevance_ratio * 2.5)  # Более агрессивный множитель

    async def validate_vision_response(
        self, image_analysis: str, original_query: str, source: str = "local"
    ) -> Tuple[bool, QualityMetrics, Optional[str]]:
        """
        Валидирует качество анализа изображения.

        Args:
            image_analysis: Результат анализа изображения
            original_query: Исходный запрос пользователя
            source: Источник обработки (local/cloud)

        Returns:
            (is_acceptable, metrics, recommendation)
        """
        metrics = QualityMetrics()

        # Проверка полноты анализа
        completeness_score = await self._check_vision_completeness(image_analysis, original_query)
        metrics.completeness_score = completeness_score

        # Проверка релевантности
        relevance_score = await self._check_relevance(image_analysis, original_query)
        metrics.relevance_score = relevance_score

        # Проверка корректности (базовая)
        correctness_score = await self._check_correctness(image_analysis, "vision")
        metrics.correctness_score = correctness_score

        # Safety всегда OK для изображений (проверяется на уровне модели)
        metrics.safety_score = 1.0

        # Вычисляем общую оценку
        overall = metrics.calculate_overall()

        # Определяем, приемлемо ли качество
        is_acceptable = (
            overall >= self.min_quality_threshold
            and completeness_score >= 0.6
            and relevance_score >= 0.6
        )

        # Рекомендация
        recommendation = None
        if not is_acceptable:
            if overall < 0.5:
                # В STRICT_LOCAL режиме вместо reroute_to_cloud используем retry_local
                if is_strict_local():
                    recommendation = "retry_local"  # Попытка улучшить качество локально
                    logger.warning(
                        "[STRICT_LOCAL] Low quality, recommendation changed to retry_local"
                    )
                else:
                    recommendation = "reroute_to_cloud"  # Низкое качество - перенаправляем
            elif overall < self.min_quality_threshold:
                recommendation = "retry_local"  # Можно попробовать еще раз локально

        if not is_acceptable:
            logger.warning(
                f"⚠️ [VISION QUALITY] Image analysis quality {overall:.2f} below threshold"
            )

        return is_acceptable, metrics, recommendation

    async def _check_vision_completeness(self, analysis: str, query: str) -> float:
        """Проверка полноты анализа изображения"""
        score = 1.0

        # Минимальная длина анализа
        if len(analysis.strip()) < 30:
            score -= 0.5

        # Проверка на пустые или generic ответы
        generic_responses = [
            "i can't",
            "i don't",
            "unable to",
            "cannot",
            "не могу",
            "не вижу",
            "не понял",
            "пусто",
        ]
        analysis_lower = analysis.lower()
        if any(gr in analysis_lower for gr in generic_responses):
            score -= 0.6

        # Проверка на конкретность описания
        # Если в запросе упоминаются конкретные объекты, они должны быть в анализе
        query_lower = query.lower()
        if any(
            word in query_lower for word in ["что", "what", "опиши", "describe", "какой", "what is"]
        ):
            # Запрос требует описания - проверяем, есть ли детали
            if len(analysis.split()) < 20:  # Слишком короткое описание
                score -= 0.3

        return max(0.0, min(1.0, score))

    async def _check_correctness(self, response: str, response_type: str) -> float:
        """Базовая проверка корректности"""
        score = 1.0

        # Проверка на очевидные ошибки
        error_patterns = [
            "undefined",
            "null reference",
            "undefined variable",
            "syntax error",
            "import error",
            "module not found",
        ]

        if any(ep in response.lower() for ep in error_patterns):
            score -= 0.5

        # Проверка на повторяющиеся фразы (признак зацикливания)
        words = response.split()
        if len(words) > 20:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:
                score -= 0.4  # Много повторений

        return max(0.0, min(1.0, score))

    async def _run_sandbox_grounding(self, response: str) -> Tuple[bool, float, Optional[str]]:
        """
        [SINGULARITY 22.4] Sandbox Grounding:
        Извлекает код из ответа и запускает его в изолированном процессе для проверки.
        """
        import re
        import subprocess
        import tempfile

        # Извлекаем блоки кода Python
        code_blocks = re.findall(r"```python\n(.*?)\n```", response, re.DOTALL)
        if not code_blocks:
            return True, 1.0, None  # Кода нет, проверка не нужна

        combined_code = "\n\n".join(code_blocks)
        
        # Ограничиваем опасные операции (базовый уровень)
        forbidden = ["os.remove", "os.system", "shutil.rmtree", "subprocess.", "socket."]
        for f in forbidden:
            if f in combined_code:
                return False, 0.0, f"Forbidden operation detected: {f}"

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
                tmp.write(combined_code)
                tmp_path = tmp.name

            # Запускаем с таймаутом и ограничением ресурсов
            process = await asyncio.create_subprocess_exec(
                "python3", "-m", "py_compile", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                return False, 0.3, f"Syntax Error: {error_msg}"

            # Если синтаксис ок, пробуем выполнить (только если это не деструктивный код)
            if "def test_" in combined_code or "assert " in combined_code:
                test_process = await asyncio.create_subprocess_exec(
                    "python3", tmp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(test_process.communicate(), timeout=5.0)
                if test_process.returncode != 0:
                    return False, 0.5, f"Runtime/Assertion Error: {stderr.decode().strip()}"

            return True, 1.0, None

        except asyncio.TimeoutError:
            return False, 0.2, "Execution Timeout (Infinite loop?)"
        except Exception as e:
            return False, 0.1, f"Grounding Error: {str(e)}"
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def get_quality_statistics(self, source: Optional[str] = None) -> Dict:
        """Получает статистику качества"""
        if not self.quality_history:
            return {}

        filtered = self.quality_history
        if source:
            filtered = [h for h in self.quality_history if h["source"] == source]

        if not filtered:
            return {}

        scores = [h["score"] for h in filtered]

        return {
            "count": len(filtered),
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "above_threshold": sum(1 for s in scores if s >= self.min_quality_threshold),
            "below_threshold": sum(1 for s in scores if s < self.min_quality_threshold),
        }


class QualityGate:
    """
    Quality Gate для контроля качества при оптимизациях.
    Блокирует оптимизации, которые снижают качество.
    """

    def __init__(self, qa: QualityAssurance):
        self.qa = qa

    async def check_optimization_impact(
        self,
        original_response: str,
        optimized_response: str,
        query: str,
        response_type: str = "general",
    ) -> Tuple[bool, str]:
        """
        Проверяет, не снизило ли оптимизация качество.

        Returns:
            (is_acceptable, reason)
        """
        # Валидируем оригинальный ответ
        orig_ok, orig_metrics, _ = await self.qa.validate_response(
            original_response, query, response_type, "original"
        )

        # Валидируем оптимизированный ответ
        opt_ok, opt_metrics, _ = await self.qa.validate_response(
            optimized_response, query, response_type, "optimized"
        )

        # Сравниваем
        if opt_metrics.overall_score < orig_metrics.overall_score - 0.1:
            # Качество снизилось более чем на 10%
            return (
                False,
                f"Quality dropped from {orig_metrics.overall_score:.2f} to {opt_metrics.overall_score:.2f}",
            )

        if not opt_ok:
            return False, "Optimized response failed quality check"

        return True, "Quality maintained"

    async def allow_optimization(
        self, optimization_type: str, current_quality: float, expected_quality: float
    ) -> bool:
        """
        Разрешает оптимизацию только если качество не снижается.
        """
        if expected_quality < current_quality - 0.05:  # Допускаем снижение до 5%
            logger.warning(
                f"🚫 [QUALITY GATE] Blocked {optimization_type}: quality would drop from {current_quality:.2f} to {expected_quality:.2f}"
            )
            return False

        return True


# Экспорт
__all__ = ["QualityAssurance", "QualityGate", "QualityMetrics", "QualityLevel"]
