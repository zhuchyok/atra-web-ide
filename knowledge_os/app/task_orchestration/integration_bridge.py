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
        
        # ПРИНУДИТЕЛЬНО: для кодинга всегда добавляем Веронику, даже в V2
        is_coding = any(w in (task_description or "").lower() for w in ["код", "функци", "програм", "рефактор", "скрипт", "python"])
        
        try:
            result = await self._orchestrator_v2.run_phases_1_to_5(
                description=task_description,
                metadata=metadata or {},
                task_type_hint=kwargs.get("task_type_hint"),
            )
            
            assignments = result.get("assignments", {})
            if is_coding:
                # Проверяем, есть ли уже Вероника
                has_veronica = any("veronica" in str(a.get("expert_name", "")).lower() or "вероника" in str(a.get("expert_name", "")).lower() for a in assignments.values())
                if not has_veronica:
                    assignments["developer_forced"] = {
                        "expert_name": "Вероника",
                        "role": "Local Developer",
                        "score": 1.0,
                        "assigned_models": ["ollama:qwen2.5-coder:32b"]
                    }
            
            # ПРИНУДИТЕЛЬНО: для БД всегда добавляем Романа
            is_db = any(w in (task_description or "").lower() for w in ["бд", "база дан", "database", "sql", "postgres"])
            if is_db:
                has_roman = any("roman" in str(a.get("expert_name", "")).lower() or "роман" in str(a.get("expert_name", "")).lower() for a in assignments.values())
                if not has_roman:
                    assignments["db_engineer_forced"] = {
                        "expert_name": "Роман",
                        "role": "Database Engineer",
                        "score": 1.0,
                        "assigned_models": ["ollama:qwen2.5-coder:32b"]
                    }
            
            return {
                "orchestrator": "v2",
                "task_id": result.get("task_id"),
                "status": "planned",
                "assignments": assignments,
                "strategy": result.get("strategy"),
                "has_graph": result.get("has_graph", False),
                "execution_order": result.get("execution_order"),
                "parallel_estimate": result.get("parallel_estimate"),
                "recommend_veronica": is_coding
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
        # ПРИОРИТЕТ: для кодинга всегда предлагаем Веронику (мировая практика: Local Developer)
        is_coding = any(w in (task_description or "").lower() for w in ["код", "функци", "програм", "рефактор", "скрипт", "python"])
        
        if ExpertMatchingEngine:
            try:
                engine = ExpertMatchingEngine()
                category = "coding" if is_coding else "general"
                if not is_coding and any(w in (task_description or "").lower() for w in ["анализ", "план", "решен"]):
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
        
        # Если это кодинг и Вероника не назначена основным — добавляем её рекомендацию
        status = "ready_for_smart_worker"
        if is_coding:
            # Проверяем, не Вероника ли уже назначена
            main_expert = expert_assignments.get("main", {}).get("expert_name", "").lower()
            if "veronica" not in main_expert and "вероника" not in main_expert:
                # Рекомендуем Веронику через метаданные или доп. назначение
                expert_assignments["developer"] = {
                    "expert_name": "Вероника",
                    "role": "Local Developer",
                    "score": 1.0
                }
        
        return {
            "orchestrator": "existing",
            "status": status,
            "assignments": expert_assignments,
            "recommend_veronica": is_coding
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
