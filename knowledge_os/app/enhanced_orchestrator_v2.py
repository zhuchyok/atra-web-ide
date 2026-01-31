"""
[KNOWLEDGE OS] Enhanced Orchestrator V2 - Phases 1-5.

World-class orchestration: complexity analysis, task decomposition, expert matching.
Does not replace enhanced_orchestrator.py; use feature flag or config to switch.
State in memory (active_tasks, phase_history); no DB writes for subtasks at this stage.
"""

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional imports from task_orchestration
TaskComplexityAnalyzer = None
TaskDecomposer = None
TaskDependencyGraph = None
SubTask = None
ExpertMatchingEngine = None
ModelRegistry = None

try:
    from task_orchestration import (
        TaskComplexityAnalyzer as _TCA,
        TaskDecomposer as _TD,
        TaskDependencyGraph as _TDG,
        SubTask as _ST,
        ExpertMatchingEngine as _EME,
        ModelRegistry as _MR,
    )
    TaskComplexityAnalyzer = _TCA
    TaskDecomposer = _TD
    TaskDependencyGraph = _TDG
    SubTask = _ST
    ExpertMatchingEngine = _EME
    ModelRegistry = _MR
except ImportError:
    try:
        from app.task_orchestration import (
            TaskComplexityAnalyzer as _TCA,
            TaskDecomposer as _TD,
            TaskDependencyGraph as _TDG,
            SubTask as _ST,
            ExpertMatchingEngine as _EME,
            ModelRegistry as _MR,
        )
        TaskComplexityAnalyzer = _TCA
        TaskDecomposer = _TD
        TaskDependencyGraph = _TDG
        SubTask = _ST
        ExpertMatchingEngine = _EME
        ModelRegistry = _MR
    except ImportError as e:
        logger.debug("task_orchestration not available: %s", e)


def _get_db_url() -> str:
    return os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"


class EnhancedOrchestratorV2:
    """
    Orchestrator V2: phases 1-5 in memory.
    Phase 1: accept task -> task_id, active_tasks.
    Phase 2: complexity + orchestration_type.
    Phase 3: optional dependency graph (TaskDecomposer).
    Phase 4: strategy (simple/complex/multi_dept).
    Phase 5: expert matching per (sub)task.
    """

    def __init__(self, db_url: Optional[str] = None):
        self._db_url = db_url or _get_db_url()
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.phase_history: Dict[str, List[Dict[str, Any]]] = {}

    def _log_phase(self, task_id: str, phase: str, result: Dict[str, Any]) -> None:
        if task_id not in self.phase_history:
            self.phase_history[task_id] = []
        self.phase_history[task_id].append({"phase": phase, "result": result})

    async def phase_5_select_experts(
        self,
        task_id: str,
        graph: Optional[Any] = None,
        description: str = "",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Подбор экспертов для задачи (или подзадач). Переопределяется в EnhancedOrchestratorV2Swarm.
        """
        assignments: Dict[str, Dict[str, Any]] = {}
        if not ExpertMatchingEngine:
            return assignments
        engine = ExpertMatchingEngine(self._db_url)
        if graph and graph.subtasks:
            for st_id, st in graph.subtasks.items():
                try:
                    best = await engine.find_best_expert_for_task(
                        st_id, st.description, st.category, st.required_models
                    )
                    if best:
                        assignments[st_id] = {
                            "expert_id": best.get("expert_id"),
                            "expert_name": best.get("expert_name"),
                            "score": best.get("score"),
                            "assigned_models": best.get("assigned_models"),
                        }
                except Exception as e:
                    logger.debug("Expert match for %s failed: %s", st_id, e)
        else:
            try:
                best = await engine.find_best_expert_for_task(
                    task_id, description, "general", None
                )
                if best:
                    assignments[task_id] = {
                        "expert_id": best.get("expert_id"),
                        "expert_name": best.get("expert_name"),
                        "score": best.get("score"),
                        "assigned_models": best.get("assigned_models"),
                    }
            except Exception as e:
                logger.debug("Expert match for task failed: %s", e)
        return assignments

    async def run_phases_1_to_5(
        self,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
        task_type_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run phases 1-5 for one task. Returns plan with task_id, complexity, graph (if any),
        strategy, and assignments (subtask_id -> expert_id / expert_name).
        """
        metadata = metadata or {}
        # Phase 1: accept task
        task_id = str(uuid.uuid4())
        self.active_tasks[task_id] = {
            "description": description,
            "metadata": metadata,
            "task_type_hint": task_type_hint,
            "complexity": None,
            "orchestration_type": None,
            "graph": None,
            "strategy": None,
            "assignments": {},
        }
        self._log_phase(task_id, "1_accept", {"task_id": task_id})

        # Phase 2: complexity and orchestration type
        complexity_score = 0.5
        orchestration_type = "simple"
        if TaskComplexityAnalyzer:
            try:
                analyzer = TaskComplexityAnalyzer(self._db_url)
                tc = analyzer.estimate_complexity(description, category=None)
                complexity_score = getattr(tc, "complexity_score", 0.5)
                orchestration_type = analyzer.get_orchestration_type(description, category=None)
            except Exception as e:
                logger.warning("Phase 2 complexity failed: %s", e)
        self.active_tasks[task_id]["complexity"] = complexity_score
        self.active_tasks[task_id]["orchestration_type"] = orchestration_type
        self._log_phase(task_id, "2_complexity", {"complexity_score": complexity_score, "orchestration_type": orchestration_type})

        # Phase 3: optional dependency graph
        graph = None
        if TaskDecomposer and complexity_score >= 0.6:
            try:
                decomposer = TaskDecomposer(self._db_url)
                graph = await decomposer.create_dependency_graph_async(task_id, description)
                if graph and graph.subtasks:
                    self.active_tasks[task_id]["graph"] = graph
                    self._log_phase(task_id, "3_decompose", {"subtask_count": len(graph.subtasks)})
            except Exception as e:
                logger.warning("Phase 3 decompose failed: %s", e)

        # Phase 4: strategy
        strategy = task_type_hint or orchestration_type
        if strategy == "auto":
            strategy = "complex" if (graph and len(graph.subtasks) > 1) else orchestration_type
        self.active_tasks[task_id]["strategy"] = strategy
        self._log_phase(task_id, "4_strategy", {"strategy": strategy})

        # Phase 5: expert matching per (sub)task (переопределяется в EnhancedOrchestratorV2Swarm)
        assignments = await self.phase_5_select_experts(task_id, graph=graph, description=description)
        self.active_tasks[task_id]["assignments"] = assignments
        self._log_phase(task_id, "5_assignments", {"count": len(assignments)})

        # Phase 6: check models (optional, non-blocking)
        models_ok = {}
        if ModelRegistry and assignments:
            try:
                registry = ModelRegistry()
                for aid, a in assignments.items():
                    models = a.get("assigned_models") or []
                    if models:
                        for m in models:
                            if m and getattr(registry, "is_model_available", None):
                                ok = await registry.is_model_available(m)
                                models_ok[m] = ok
            except Exception as e:
                logger.debug("Phase 6 check_models: %s", e)
        self._log_phase(task_id, "6_check_models", {"models_checked": models_ok})

        # Phase 7: create_subtasks (in-memory only; no DB writes at this stage)
        self._log_phase(task_id, "7_create_subtasks", {"in_memory": True})

        # Phase 8: assign_executors (already done in phase 5; future: persist or send to Smart Worker)
        self._log_phase(task_id, "8_assign_executors", {"assignments_count": len(assignments)})

        return {
            "task_id": task_id,
            "complexity_score": complexity_score,
            "orchestration_type": orchestration_type,
            "strategy": strategy,
            "has_graph": graph is not None and len(graph.subtasks) > 0 if graph else False,
            "subtask_count": len(graph.subtasks) if graph else 0,
            "execution_order": graph.get_execution_order() if graph else [[task_id]],
            "assignments": assignments,
            "parallel_estimate": graph.estimate_parallel_duration() if graph and getattr(graph, "estimate_parallel_duration", None) else None,
        }
