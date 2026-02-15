"""
Task Complexity Analyzer - shared layer for orchestrator and worker.

Wraps intelligent_model_router.estimate_task_complexity so both orchestrator and
smart_worker use the same complexity and task_type logic (simple/complex/multi-dept).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from intelligent_model_router import get_intelligent_router
except ImportError:
    try:
        from app.intelligent_model_router import get_intelligent_router
    except ImportError:
        get_intelligent_router = None


class TaskComplexityAnalyzer:
    """
    Analyzes task complexity and type. Delegates to intelligent_model_router.
    Returns complexity_score (0-1), task_type (coding, reasoning, fast, general),
    and derived classification: simple / complex / multi-dept for orchestration.
    """

    def __init__(self, db_url: Optional[str] = None):
        self._router = None
        self._db_url = db_url

    def _get_router(self):
        if self._router is None and get_intelligent_router:
            try:
                self._router = get_intelligent_router(self._db_url)
            except Exception as e:
                logger.debug("get_intelligent_router failed: %s", e)
        return self._router

    def estimate_complexity(self, prompt: str, category: Optional[str] = None):
        """
        Return TaskComplexity (complexity_score, requires_reasoning, requires_coding,
        estimated_tokens, task_type). Uses intelligent_model_router.estimate_task_complexity.
        """
        router = self._get_router()
        if router is None:
            return _fallback_complexity(prompt, category)
        try:
            return router.estimate_task_complexity(prompt, category=category)
        except Exception as e:
            logger.warning("estimate_task_complexity failed: %s", e)
            return _fallback_complexity(prompt, category)

    def get_orchestration_type(self, prompt: str, category: Optional[str] = None) -> str:
        """
        Return simple, complex, or multi_dept for orchestration strategy.
        simple: one step, one expert. complex: multi-step, one expert. multi_dept: multiple experts.
        """
        tc = self.estimate_complexity(prompt, category)
        
        # МОНСТР-ЛОГИКА: Если файл гигантский, ВСЕГДА форсируем complex (декомпозицию)
        if any(w in prompt.lower() for w in ["app.py", "dashboard", "3000 строк"]):
            logger.info("🐉 [MONSTER ANALYZER] Обнаружен гигантский файл. Форсируем стратегию COMPLEX.")
            return "complex"

        if tc.complexity_score >= 0.7 and (tc.requires_reasoning or tc.requires_coding):
            return "complex"
        if tc.complexity_score >= 0.5 and tc.task_type not in ("fast", "general"):
            return "complex"
        return "simple"


def _fallback_complexity(prompt: str, category: Optional[str] = None):
    """Fallback when intelligent_model_router is unavailable."""
    try:
        from intelligent_model_router import TaskComplexity
    except ImportError:
        try:
            from app.intelligent_model_router import TaskComplexity
        except ImportError:
            from dataclasses import dataclass
            @dataclass
            class TaskComplexity:
                complexity_score: float = 0.5
                requires_reasoning: bool = False
                requires_coding: bool = False
                requires_creativity: bool = False
                estimated_tokens: int = 0
                task_type: str = "general"
    score = 0.3 + min(len(prompt) / 2000.0, 0.5)
    task_type = "general"
    if category:
        task_type = category
    return TaskComplexity(
        complexity_score=min(score, 1.0),
        requires_reasoning="reasoning" in (category or ""),
        requires_coding="coding" in (category or ""),
        requires_creativity=False,
        estimated_tokens=max(100, len(prompt) // 4),
        task_type=task_type,
    )
