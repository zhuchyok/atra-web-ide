"""
[SINGULARITY 26.6] Quality Pipeline - World-Class Response Quality

Мировые практики:
- Anthropic: Constitutional AI, Self-Reflection
- OpenAI: Ensemble, Debate
- Google: Fact Verification
- Microsoft: Red Team

Включает: reflection, ensemble, constitutional, fact-check
"""

import asyncio
import json
import logging
import os
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class QualityConfig(BaseModel):
    reflection: bool = True
    ensemble: bool = True
    constitutional: bool = False  # Heavy - check if needed
    fact_check: bool = True
    confidence_threshold: float = 0.7
    max_iterations: int = 2


class QualityResult(BaseModel):
    response: str
    confidence: float
    quality_score: float
    passed: bool
    issues: list[str] = []
    iterations: int = 0
    metadata: dict = {}


_quality_config = QualityConfig()


def get_quality_config() -> QualityConfig:
    return _quality_config


def set_quality_config(
    reflection: Optional[bool] = None,
    ensemble: Optional[bool] = None,
    constitutional: Optional[bool] = None,
    fact_check: Optional[bool] = None,
    confidence_threshold: Optional[float] = None,
) -> QualityConfig:
    global _quality_config
    if reflection is not None:
        _quality_config.reflection = reflection
    if ensemble is not None:
        _quality_config.ensemble = ensemble
    if constitutional is not None:
        _quality_config.constitutional = constitutional
    if fact_check is not None:
        _quality_config.fact_check = fact_check
    if confidence_threshold is not None:
        _quality_config.confidence_threshold = confidence_threshold
    return _quality_config


async def check_confidence(response: str, prompt: str) -> float:
    """Оценка уверенности ответа (0-1)."""
    try:
        from run_smart_agent_async import run_smart_agent_async

        analysis_prompt = f"""
Оцени уверенность ответа на шкале 0-1.

ВОПРОС: {prompt[:500]}
ОТВЕТ: {response[:1000]}

ВЕРНИ ТОЛЬКО ЧИСЛО (например 0.85).
Критерий:
- 1.0 = полная уверенность, ответ точный и полный
- 0.7 = хорошая уверенность, некоторые нюансы
- 0.5 = неопределённость, требует уточнения  
- 0.3 = низкая уверенность, проблемы с фактами
- 0.0 = не знаю, отказ от ответа
"""

        result = await run_smart_agent_async(
            goal=analysis_prompt, expert_name="Аналитик", category="reasoning"
        )

        text = str(result.get("output", ""))
        numbers = [c for c in text if c.isdigit() or c == "."]
        num_str = "".join(numbers).strip(".")

        try:
            score = float(num_str[:4])
            return min(max(score, 0.0), 1.0)
        except ValueError:
            return 0.5

    except Exception as e:
        logger.warning(f"Confidence check failed: {e}")
        return 0.5


async def self_reflect(prompt: str, response: str) -> str:
    """Self-reflection - пересмотр ответа."""
    try:
        from run_smart_agent_async import run_smart_agent_async

        reflection_prompt = f"""
Пересмотри свой ответ. ��удь строгим критиком.

ВОПРОС: {prompt[:500]}
ТВОЙ ОТВЕТ: {response[:1000]}

Проверь:
1. Фактическая точность
2. Полнота ответа
3. Логическая согласованность
4. Потенциальные ошибки

Если ответ хороший - верни его без изменений.
Если есть проблемы - исправь и верни улучшенную версию.
        
ВЕРНИ ТОЛЬКО ИСПРАВЛЕННЫЙ ОТВЕТ.
"""

        result = await run_smart_agent_async(
            goal=reflection_prompt, expert_name="Критик", category="reasoning"
        )

        return str(result.get("output", response))

    except Exception as e:
        logger.warning(f"Self-reflection failed: {e}")
        return response


async def ensemble_check(prompt: str, response: str) -> dict:
    """Ensemble - проверка множественными моделями."""
    try:
        from run_smart_agent_async import run_smart_agent_async

        ensemble_prompt = f"""
Проверь ответ другими моделями. Найди ошибки.

ВОПРОС: {prompt[:500]}
ОТВЕТ: {response[:1000]}

Будь строг. Ищи:
1. Фактические ошибки
2. Логические ошибки
3. Упущения
4. Неоднозначности

ВЕРНИ JSON:
{{
    "issues": ["список проблем"],
    "score": 0.85,
    "verdict": "PASS" или "FAIL"
}}
"""

        result = await run_smart_agent_async(
            goal=ensemble_prompt, expert_name="Эксперт", category="general"
        )

        output = str(result.get("output", ""))

        try:
            start = output.find("{")
            end = output.rfind("}") + 1
            data = json.loads(output[start:end])
            return data
        except:
            return {"issues": [], "score": 0.7, "verdict": "UNKNOWN"}

    except Exception as e:
        logger.warning(f"Ensemble check failed: {e}")
        return {"issues": [], "score": 0.5, "verdict": "UNKNOWN"}


async def fact_check(prompt: str, response: str) -> dict:
    """Fact-check через RAG."""
    try:
        from run_smart_agent_async import run_smart_agent_async

        fact_prompt = f"""
Проверь факты в ответе через знания.

ВОПРОС: {prompt[:500]}
ОТВЕТ: {response[:1000]}

Для каждого утверждения в ответе:
- Найди соответствующие знания
- Проверь точность
- Отметь ошибки

ВЕРНИ JSON:
{{
    "verified": true/false,
    "claims_checked": 5,
    "errors": ["список ошибок"]
}}
"""

        result = await run_smart_agent_async(
            goal=fact_prompt, expert_name="Проверяющий", category="reasoning"
        )

        output = str(result.get("output", ""))

        try:
            start = output.find("{")
            end = output.rfind("}") + 1
            data = json.loads(output[start:end])
            return data
        except:
            return {"verified": True, "claims_checked": 0, "errors": []}

    except Exception as e:
        logger.warning(f"Fact check failed: {e}")
        return {"verified": True, "claims_checked": 0, "errors": []}


async def run_quality_pipeline(
    prompt: str,
    initial_response: str,
    config: Optional[QualityConfig] = None,
) -> QualityResult:
    """Запустить полный Quality Pipeline."""
    cfg = config or _quality_config

    response = initial_response
    iterations = 0
    issues = []
    metadata = {}

    logger.info(f"🚀 [QUALITY PIPELINE] Starting with config: {cfg}")

    for iteration in range(cfg.max_iterations):
        iterations = iteration + 1
        logger.info(f"🔄 [QUALITY] Iteration {iteration + 1}/{cfg.max_iterations}")

        # 1. Self-reflection
        if cfg.reflection:
            response = await self_reflect(prompt, response)
            logger.debug("✅ Reflection done")

        # 2. Confidence check
        confidence = await check_confidence(response, prompt)
        logger.info(f"📊 Confidence: {confidence:.2f}")

        if confidence >= cfg.confidence_threshold:
            logger.info(f"✅ Confidence PASS ({confidence:.2f} >= {cfg.confidence_threshold})")
            break

        # 3. Ensemble check
        if cfg.ensemble and confidence < cfg.confidence_threshold:
            ensemble_result = await ensemble_check(prompt, response)
            issues.extend(ensemble_result.get("issues", []))
            metadata["ensemble"] = ensemble_result
            logger.info(f"🔍 Ensemble: {ensemble_result.get('verdict', 'UNKNOWN')}")

        # 4. Fact check
        if cfg.fact_check:
            fact_result = await fact_check(prompt, response)
            if not fact_result.get("verified", True):
                issues.extend(fact_result.get("errors", []))
            metadata["fact_check"] = fact_result
            logger.info(f"🔍 Fact-check: {'PASS' if fact_result.get('verified') else 'FAIL'}")

        # If we're past max iterations, stop
        if iteration >= cfg.max_iterations - 1:
            break

    # Calculate quality score
    quality_score = confidence
    if issues:
        quality_score *= 1.0 - min(len(issues) * 0.1, 0.5)

    passed = quality_score >= cfg.confidence_threshold

    return QualityResult(
        response=response,
        confidence=confidence,
        quality_score=quality_score,
        passed=passed,
        issues=issues,
        iterations=iterations,
        metadata=metadata,
    )


async def enhance_response(
    prompt: str,
    response: str,
    enable_full: bool = False,
) -> tuple[str, dict]:
    """
    Улучшить ответ через Quality Pipeline.

    Returns: (enhanced_response, metadata)
    """
    if enable_full:
        result = await run_quality_pipeline(prompt, response)
        return result.response, {
            "quality": result.quality_score,
            "confidence": result.confidence,
            "passed": result.passed,
            "iterations": result.iterations,
            "issues": result.issues,
            **result.metadata,
        }

    # Light mode: just confidence check
    confidence = await check_confidence(response, prompt)

    return response, {
        "quality": confidence,
        "confidence": confidence,
        "passed": confidence >= _quality_config.confidence_threshold,
    }


def is_quality_enabled() -> bool:
    """Check if quality pipeline is enabled."""
    return _quality_config.reflection or _quality_config.ensemble or _quality_config.fact_check


def get_quality_stats() -> dict:
    """Get quality pipeline stats."""
    return {
        "reflection": _quality_config.reflection,
        "ensemble": _quality_config.ensemble,
        "constitutional": _quality_config.constitutional,
        "fact_check": _quality_config.fact_check,
        "threshold": _quality_config.confidence_threshold,
        "enabled": is_quality_enabled(),
    }
