"""
Smart Worker Integration - создание подзадач в БД и интеграция со Smart Worker.

Создаёт реальные записи в таблице tasks для подзадач (parent_task_id, assignee_expert_id,
estimated_duration_min и т.д.). Опционально вызывает Smart Worker для выполнения.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

try:
    from .task_decomposer import SubTask
except ImportError:
    try:
        from task_orchestration.task_decomposer import SubTask
    except ImportError:
        SubTask = None

DEFAULT_DB_URL = os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"


class SmartWorkerIntegration:
    """
    Мост между оркестратором и Smart Worker.
    Создаёт реальные подзадачи в БД; опционально запускает выполнение через Smart Worker.
    """

    def __init__(self, db_url: Optional[str] = None):
        self._db_url = db_url or DEFAULT_DB_URL
        self._smart_worker = None
        try:
            from app.smart_worker_autonomous import SmartWorkerAutonomous
            self._smart_worker = SmartWorkerAutonomous()
        except Exception as e:
            try:
                from smart_worker_autonomous import SmartWorkerAutonomous
                self._smart_worker = SmartWorkerAutonomous()
            except Exception:
                logger.debug("SmartWorkerAutonomous not available: %s", e)

    @property
    def has_smart_worker(self) -> bool:
        return self._smart_worker is not None

    async def create_subtasks_in_db(
        self,
        parent_task_id: str,
        subtasks: Dict[str, Any],
        expert_assignments: Dict[str, Dict[str, Any]],
        creator_expert_id: Optional[str] = None,
    ) -> List[str]:
        """
        Создать реальные подзадачи в таблице tasks.

        Ожидается, что родительская задача уже есть в таблице tasks (parent_task_id —
        UUID существующей записи). Иначе FK parent_task_id REFERENCES tasks(id) приведёт к ошибке.

        subtasks: Dict[subtask_id, SubTask] или dict с полями title, description, estimated_duration_min, required_models, category.
        expert_assignments: Dict[subtask_id, {expert_id, expert_name, ...}].
        Returns: список созданных id (UUID) записей в tasks.
        """
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg not available; create_subtasks_in_db disabled")
            return []
        created_ids: List[str] = []
        conn = None
        try:
            conn = await asyncpg.connect(self._db_url)
            for st_id, st in subtasks.items():
                assignment = expert_assignments.get(st_id, {})
                expert_id = assignment.get("expert_id")
                title = getattr(st, "title", None) or (st.get("title") if isinstance(st, dict) else "") or str(st_id)[:200]
                description = getattr(st, "description", None) or (st.get("description") if isinstance(st, dict) else "") or ""
                estimated_min = getattr(st, "estimated_duration_min", None) or (st.get("estimated_duration_min") if isinstance(st, dict) else None) or 30
                required_models = getattr(st, "required_models", None) or (st.get("required_models") if isinstance(st, dict) else None)
                metadata = {"source": "orchestrator_v2", "subtask_id": st_id, "parent_task_id": parent_task_id}
                try:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO tasks (
                            title, description, status, priority,
                            assignee_expert_id, creator_expert_id, metadata,
                            task_type, parent_task_id, complexity_score,
                            estimated_duration_min, required_models
                        ) VALUES ($1, $2, 'pending', 'medium', $3, $4, $5, 'subtask', $6, 0.5, $7, $8)
                        RETURNING id
                        """,
                        title[:500],
                        description[:10000],
                        expert_id,
                        creator_expert_id,
                        json.dumps(metadata),
                        parent_task_id if _is_uuid(parent_task_id) else None,
                        estimated_min,
                        json.dumps(required_models) if required_models else None,
                    )
                except Exception as e:
                    if "estimated_duration_min" in str(e) or "required_models" in str(e) or "column" in str(e).lower():
                        row = await conn.fetchrow(
                            """
                            INSERT INTO tasks (
                                title, description, status, priority,
                                assignee_expert_id, creator_expert_id, metadata,
                                task_type, parent_task_id
                            ) VALUES ($1, $2, 'pending', 'medium', $3, $4, $5, 'subtask', $6)
                            RETURNING id
                            """,
                            title[:500],
                            description[:10000],
                            expert_id,
                            creator_expert_id,
                            json.dumps(metadata),
                            parent_task_id if _is_uuid(parent_task_id) else None,
                        )
                    else:
                        raise
                if row and row.get("id"):
                    created_ids.append(str(row["id"]))
            return created_ids
        except Exception as e:
            logger.warning("create_subtasks_in_db failed: %s", e)
            return []
        finally:
            if conn:
                await conn.close()

    async def execute_task_plan(
        self,
        task_id: str,
        expert_assignments: Dict[str, Any],
        dependency_graph: Optional[Any] = None,
        create_in_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Создать подзадачи в БД (если create_in_db и есть dependency_graph) и вернуть план.
        Выполнение через Smart Worker — опционально (если has_smart_worker и вызов process_single/process_batch).
        """
        created_ids: List[str] = []
        if create_in_db and dependency_graph and getattr(dependency_graph, "subtasks", None):
            subtasks = dependency_graph.subtasks
            created_ids = await self.create_subtasks_in_db(task_id, subtasks, expert_assignments)
        if self._smart_worker and expert_assignments:
            try:
                if dependency_graph and getattr(dependency_graph, "subtasks", None):
                    return await self._execute_complex_plan(task_id, expert_assignments, dependency_graph, created_ids)
                return await self._execute_simple_plan(task_id, expert_assignments)
            except Exception as e:
                logger.debug("Smart Worker execution failed: %s", e)
        return {
            "task_id": task_id,
            "type": "planned",
            "subtasks_created_in_db": len(created_ids),
            "created_task_ids": created_ids,
            "assignments_count": len(expert_assignments),
        }

    async def _execute_simple_plan(self, task_id: str, expert_assignments: Dict[str, Any]) -> Dict[str, Any]:
        main = expert_assignments.get(task_id) or expert_assignments.get("main")
        if not main or not self._smart_worker:
            return {"task_id": task_id, "type": "simple", "success": False, "reason": "no_assignment"}
        if hasattr(self._smart_worker, "process_single"):
            result = await self._smart_worker.process_single({
                "id": task_id,
                "expert_id": main.get("expert_id"),
                "description": "",
            })
            return {"task_id": task_id, "type": "simple", "success": result.get("success", False), "result": result}
        return {"task_id": task_id, "type": "simple", "success": False, "reason": "process_single_not_available"}

    async def _execute_complex_plan(
        self,
        task_id: str,
        expert_assignments: Dict[str, Any],
        dependency_graph: Any,
        created_ids: List[str],
    ) -> Dict[str, Any]:
        order = dependency_graph.get_execution_order()
        results = {}
        for level in order:
            for st_id in level:
                if st_id in expert_assignments and hasattr(self._smart_worker, "process_single"):
                    st = dependency_graph.subtasks.get(st_id)
                    desc = getattr(st, "description", "") if st else ""
                    result = await self._smart_worker.process_single({
                        "id": st_id,
                        "expert_id": expert_assignments[st_id].get("expert_id"),
                        "description": desc,
                    })
                    results[st_id] = result
        return {
            "task_id": task_id,
            "type": "complex",
            "execution_levels": len(order),
            "subtasks_created_in_db": len(created_ids),
            "results": results,
            "success": all(r.get("success", False) for r in results.values()) if results else False,
        }


def _is_uuid(s: str) -> bool:
    if not s or len(s) != 36:
        return False
    try:
        parts = s.split("-")
        return len(parts) == 5 and all(len(p) in (8, 4, 4, 4, 12) for p in parts)
    except Exception:
        return False
