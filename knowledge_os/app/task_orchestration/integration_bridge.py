"""
Integration Bridge - мост между новой оркестрацией (V2) и существующей системой.

Позволяет постепенно внедрять EnhancedOrchestratorV2 через feature flag / A/B.
A/B: X% трафика в V2 (process_task с use_v2=True), остальные — существующая система.
"""

import logging
import os
import random
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from app.config import ORCHESTRATION_V2_ENABLED, ORCHESTRATION_V2_PERCENTAGE
except ImportError:
    ORCHESTRATION_V2_ENABLED = os.getenv("ORCHESTRATION_V2_ENABLED", "false").lower() in ("1", "true", "yes")
    ORCHESTRATION_V2_PERCENTAGE = float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10"))

EnhancedOrchestratorV2 = None
ExpertMatchingEngine = None

try:
    from app.enhanced_orchestrator_v2 import EnhancedOrchestratorV2 as _EOV2
    EnhancedOrchestratorV2 = _EOV2
except ImportError:
    try:
        from enhanced_orchestrator_v2 import EnhancedOrchestratorV2 as _EOV2
        EnhancedOrchestratorV2 = _EOV2
    except ImportError:
        pass

try:
    from .expert_matching_engine import ExpertMatchingEngine as _EME
    ExpertMatchingEngine = _EME
except ImportError:
    try:
        from task_orchestration.expert_matching_engine import ExpertMatchingEngine as _EME
        ExpertMatchingEngine = _EME
    except ImportError:
        pass


def _use_v2_default() -> bool:
    return os.getenv("USE_ORCHESTRATION_V2", "").lower() in ("1", "true", "yes")


class IntegrationBridge:
    """
    Мост для постепенного внедрения новой оркестрации.
    A/B: X% задач в V2 (_process_with_v2), остальные в существующую систему (_process_with_existing).
    """

    def __init__(
        self,
        use_new_orchestration: Optional[bool] = None,
        v2_percentage: Optional[float] = None,
    ):
        self.use_new_orchestration = use_new_orchestration if use_new_orchestration is not None else _use_v2_default()
        self.v2_percentage = v2_percentage if v2_percentage is not None else ORCHESTRATION_V2_PERCENTAGE
        self._orchestrator_v2 = None
        if EnhancedOrchestratorV2:
            try:
                self._orchestrator_v2 = EnhancedOrchestratorV2()
                if self.use_new_orchestration:
                    logger.info("IntegrationBridge: EnhancedOrchestratorV2 ready (A/B %s%%)", self.v2_percentage)
            except Exception as e:
                logger.warning("IntegrationBridge: V2 init failed: %s", e)
                self._orchestrator_v2 = None

    async def _process_with_v2(
        self,
        task_description: str,
        metadata: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Обработка через EnhancedOrchestratorV2 (фазы 1–5)."""
        if not self._orchestrator_v2:
            return await self._process_with_existing(task_description, metadata, kwargs)
        try:
            result = await self._orchestrator_v2.run_phases_1_to_5(
                description=task_description,
                metadata=metadata or {},
                task_type_hint=kwargs.get("task_type_hint"),
            )
            return {
                "orchestrator": "v2",
                "task_id": result.get("task_id"),
                "status": "planned",
                "assignments": result.get("assignments", {}),
                "strategy": result.get("strategy"),
                "has_graph": result.get("has_graph", False),
                "execution_order": result.get("execution_order"),
                "parallel_estimate": result.get("parallel_estimate"),
            }
        except Exception as e:
            logger.warning("V2 process_task failed, falling back to existing: %s", e)
            return await self._process_with_existing(task_description, metadata, kwargs)

    async def _process_with_existing(
        self,
        task_description: str,
        metadata: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Обработка через ExpertMatchingEngine (существующая система)."""
        expert_assignments = {}
        if ExpertMatchingEngine:
            try:
                engine = ExpertMatchingEngine()
                category = "general"
                if any(w in (task_description or "").lower() for w in ["код", "функци", "програм"]):
                    category = "coding"
                elif any(w in (task_description or "").lower() for w in ["анализ", "план", "решен"]):
                    category = "reasoning"
                best = await engine.find_best_expert_for_task(
                    task_id="bridge_" + str(hash(task_description) % 10**8),
                    task_description=task_description,
                    required_category=category,
                )
                if best:
                    expert_assignments["main"] = best
            except Exception as e:
                logger.debug("ExpertMatchingEngine fallback failed: %s", e)
        return {
            "orchestrator": "existing",
            "status": "ready_for_smart_worker",
            "assignments": expert_assignments,
        }

    async def process_task(
        self,
        task_description: str,
        metadata: Optional[Dict[str, Any]] = None,
        use_v2: Optional[bool] = None,
        project_context: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        A/B: при use_v2=None решает по ORCHESTRATION_V2_PERCENTAGE (random);
        при use_v2=True/False — явный выбор. Возвращает orchestrator: "v2" | "existing".
        project_context передаётся в metadata для сохранения в задачах БД.
        """
        meta = dict(metadata) if metadata else {}
        if project_context:
            meta["project_context"] = project_context
        if use_v2 is not None:
            use_new = use_v2
        elif ORCHESTRATION_V2_ENABLED and self.v2_percentage > 0:
            use_new = (random.random() * 100) < self.v2_percentage
        else:
            use_new = self.use_new_orchestration

        if use_new and self._orchestrator_v2:
            return await self._process_with_v2(task_description, meta, kwargs)
        return await self._process_with_existing(task_description, meta, kwargs)
