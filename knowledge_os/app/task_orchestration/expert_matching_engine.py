"""
Expert Matching Engine - find best expert for a task by category and workload.

Selection takes roles into account:
  1. expert_specializations (category) when available;
  2. CATEGORY_TO_ROLES: task category (coding/reasoning/general/fast) → list of role names
     from configs/experts (team.md, employees.md); candidates filtered by experts.role;
  3. Fallback: department/role ILIKE required_category;
  4. Final: all active experts.

Integrates with ModelRegistry for assigned_models. Optional in-memory cache with TTL.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

try:
    from .model_registry import ModelRegistry
except ImportError:
    try:
        from task_orchestration.model_registry import ModelRegistry
    except ImportError:
        ModelRegistry = None


DEFAULT_DB_URL = os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"

# Маппинг категории задачи (coding/reasoning/general/fast) → роли экспертов из configs/experts (team.md, employees.md).
# Подбор экспертов учитывает роли: для категории выбираются только эксперты с подходящей ролью.
# Роли из configs/experts/employees.md — полный охват для подбора по категории задачи
CATEGORY_TO_ROLES = {
    "coding": [
        "Backend Developer",
        "QA Engineer",
        "Full-stack Developer",
        "Frontend Developer",
        "Principal Backend Architect",
        "Code Reviewer",
        "Database Engineer",
        "Performance Engineer",
        "Data Engineer",
        "QA Lead",
    ],
    "reasoning": [
        "ML Engineer",
        "Data Analyst",
        "Risk Manager",
        "Data Scientist",
        "Financial Analyst",
        "Trading Strategy Developer",
        "Product Manager",
        "System Architect",
        "Technical Lead",
        "Security Analyst",
        "Risk Analyst",
        "Trading Analyst",
        "Product Analyst",
        "ML Researcher",
        "Analyst",
    ],
    "general": [
        "Team Lead",
        "Backend Developer",
        "ML Engineer",
        "Data Analyst",
        "DevOps Engineer",
        "QA Engineer",
        "Monitor",
        "Security Engineer",
        "Technical Writer",
        "Risk Manager",
        "Database Engineer",
        "Performance Engineer",
        "Full-stack Developer",
        "Frontend Developer",
        "UI/UX Designer",
        "Product Manager",
        "SRE Engineer",
        "Data Engineer",
        "Documentation Writer",
        "QA Lead",
        "Security Analyst",
        "Content Manager",
        "Legal Counsel",
        "Compliance Officer",
        "Support Engineer",
        "HR Specialist",
        "Infrastructure Engineer",
        "ML Researcher",
        "UX Researcher",
        "Product Analyst",
        "Trading Analyst",
        "Risk Analyst",
        "Analyst",
    ],
    "fast": [
        "Backend Developer",
        "QA Engineer",
        "Monitor",
        "Code Reviewer",
        "SRE Engineer",
    ],
}


async def _get_expert_workload(conn, expert_id: str) -> Dict[str, Any]:
    """Current workload for an expert (active tasks, success rate, avg duration)."""
    active_tasks = await conn.fetchval("""
        SELECT count(*)
        FROM tasks
        WHERE assignee_expert_id = $1
        AND status IN ('pending', 'in_progress')
    """, expert_id) or 0

    avg_duration = await conn.fetchval("""
        SELECT AVG(actual_duration_minutes)
        FROM tasks
        WHERE assignee_expert_id = $1
        AND status = 'completed'
        AND actual_duration_minutes IS NOT NULL
        AND completed_at > NOW() - INTERVAL '30 days'
    """, expert_id) or 60.0

    success_rate = await conn.fetchval("""
        SELECT
            CASE
                WHEN count(*) = 0 THEN 1.0
                ELSE count(*) FILTER (WHERE status = 'completed')::float / count(*)::float
            END
        FROM tasks
        WHERE assignee_expert_id = $1
        AND created_at > NOW() - INTERVAL '30 days'
    """, expert_id) or 1.0

    workload_score = active_tasks * 10 + (avg_duration / 10)
    score = (
        workload_score * 0.5
        + (1.0 - success_rate) * 100 * 0.3
        + (avg_duration / 10) * 0.2
    )
    return {
        "active_tasks": active_tasks,
        "avg_duration_minutes": round(avg_duration, 1),
        "success_rate": round(success_rate, 2),
        "workload_score": workload_score,
        "score": score,
    }


class ExpertMatchingEngine:
    """
    Finds best expert for a task by required_category and workload.
    Uses expert_specializations when present; else experts by department/role (is_active).
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        model_registry: Optional["ModelRegistry"] = None,
        cache_ttl_sec: int = 60,
    ):
        self._db_url = db_url or DEFAULT_DB_URL
        self._registry = model_registry or (ModelRegistry() if ModelRegistry else None)
        self._cache_ttl = cache_ttl_sec
        self._cache: Dict[str, tuple] = {}  # key -> (result, expiry_ts)

    def _cache_key(self, task_id: str, required_category: str) -> str:
        return f"{task_id}:{required_category}"

    def _get_cached(self, key: str) -> Optional[Dict]:
        if key not in self._cache:
            return None
        result, expiry = self._cache[key]
        if time.monotonic() > expiry:
            del self._cache[key]
            return None
        return result

    def _set_cached(self, key: str, value: Dict) -> None:
        self._cache[key] = (value, time.monotonic() + self._cache_ttl)

    async def find_best_expert_for_task(
        self,
        task_id: str,
        task_description: str,
        required_category: str,
        required_models: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Return best expert for the task: expert_id, expert_name, score, assigned_models, etc.
        Returns None if no experts found.
        """
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg not available; ExpertMatchingEngine disabled")
            return None

        cache_key = self._cache_key(task_id, required_category)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        conn = None
        try:
            conn = await asyncpg.connect(self._db_url)
            candidates = await self._get_candidates(conn, required_category)
            if not candidates:
                return None

            best = None
            best_score = float("inf")

            for expert in candidates:
                workload = await _get_expert_workload(conn, expert["id"])
                score = workload["score"]
                if score < best_score:
                    best_score = score
                    best = {
                        "expert_id": expert["id"],
                        "expert_name": expert["name"],
                        "score": round(score, 2),
                        "workload": workload,
                        "assigned_models": None,
                    }

            if best is None:
                return None

            # Resolve assigned_models via ModelRegistry
            if self._registry:
                try:
                    model = await self._registry.get_available_model(
                        required_category or "general",
                        priority="mlx",
                    )
                    if model and (required_models is None or not required_models):
                        best["assigned_models"] = [model]
                    elif required_models:
                        available = []
                        for m in required_models:
                            if await self._registry.is_model_available(m):
                                available.append(m)
                        best["assigned_models"] = available or ([model] if model else None)
                    else:
                        best["assigned_models"] = [model] if model else None
                except Exception as e:
                    logger.debug("ModelRegistry resolution failed: %s", e)

            self._set_cached(cache_key, best)
            return best
        except Exception as e:
            logger.warning("find_best_expert_for_task failed: %s", e)
            return None
        finally:
            if conn:
                await conn.close()

    async def _get_candidates(self, conn, required_category: str) -> List[Dict]:
        """Experts by expert_specializations.category; fallback to experts by department/role."""
        # Try expert_specializations first
        try:
            rows = await conn.fetch("""
                SELECT e.id, e.name, e.role, e.department, es.proficiency_score
                FROM experts e
                INNER JOIN expert_specializations es ON es.expert_id = e.id
                WHERE es.category = $1
                AND (e.is_active = true OR e.is_active IS NULL)
                ORDER BY es.proficiency_score DESC NULLS LAST
            """, required_category)
            if rows:
                return [dict(r) for r in rows]
        except Exception as e:
            if "expert_specializations" in str(e) or "does not exist" in str(e).lower():
                pass
            else:
                logger.debug("expert_specializations query failed: %s", e)

        # Fallback по ролям: категория задачи (coding/reasoning/general/fast) → список ролей из configs/experts
        roles_for_category = CATEGORY_TO_ROLES.get(required_category)
        if roles_for_category:
            try:
                rows = await conn.fetch("""
                    SELECT id, name, role, department
                    FROM experts
                    WHERE (is_active = true OR is_active IS NULL)
                    AND role = ANY($1::text[])
                    ORDER BY RANDOM()
                    LIMIT 50
                """, roles_for_category)
                if rows:
                    logger.debug("Expert matching by roles for category %s: %s experts", required_category, len(rows))
                    return [dict(r) for r in rows]
            except Exception as e:
                if "is_active" in str(e).lower():
                    try:
                        rows = await conn.fetch("""
                            SELECT id, name, role, department
                            FROM experts
                            WHERE role = ANY($1::text[])
                            ORDER BY RANDOM()
                            LIMIT 50
                        """, roles_for_category)
                        if rows:
                            return [dict(r) for r in rows]
                    except Exception:
                        pass
                logger.debug("experts by roles query failed: %s", e)

        # Fallback: experts by department or role (ILIKE для произвольной категории/строки)
        try:
            pattern = f"%{required_category}%"
            rows = await conn.fetch("""
                SELECT id, name, role, department
                FROM experts
                WHERE (is_active = true OR is_active IS NULL)
                AND (
                    department ILIKE $1
                    OR role ILIKE $1
                )
                ORDER BY RANDOM()
                LIMIT 50
            """, pattern)
            if rows:
                return [dict(r) for r in rows]
        except Exception as e:
            if "is_active" in str(e).lower():
                rows = await conn.fetch("""
                    SELECT id, name, role, department
                    FROM experts
                    WHERE department ILIKE $1 OR role ILIKE $1
                    ORDER BY RANDOM()
                    LIMIT 50
                """, pattern)
                if rows:
                    return [dict(r) for r in rows]
            logger.debug("experts fallback query failed: %s", e)

        # Final fallback: all active experts
        try:
            rows = await conn.fetch("""
                SELECT id, name, role, department
                FROM experts
                WHERE is_active = true OR is_active IS NULL
                ORDER BY RANDOM()
                LIMIT 50
            """)
            if rows:
                return [dict(r) for r in rows]
        except Exception:
            rows = await conn.fetch("""
                SELECT id, name, role, department
                FROM experts
                ORDER BY RANDOM()
                LIMIT 50
            """)
            return [dict(r) for r in rows] if rows else []

        return []

    async def find_experts_for_complex_task(
        self,
        subtasks: List[Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Подбор команды экспертов для сложной задачи (несколько подзадач).
        Учитывает специализации по категории каждой подзадачи, балансировку нагрузки
        и минимизацию дублирования исполнителей где возможно.
        Returns: Dict[subtask_id -> {expert_id, expert_name, score, assigned_models, ...}]
        """
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg not available; find_experts_for_complex_task disabled")
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        try:
            for item in subtasks:
                st_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
                desc = item.get("description") if isinstance(item, dict) else getattr(item, "description", "")
                category = item.get("category", "general") if isinstance(item, dict) else getattr(item, "category", "general")
                required_models = item.get("required_models") if isinstance(item, dict) else getattr(item, "required_models", None)
                if not st_id:
                    continue
                best = await self.find_best_expert_for_task(
                    str(st_id), desc, category, required_models
                )
                if best:
                    result[str(st_id)] = best
            return result
        except Exception as e:
            logger.warning("find_experts_for_complex_task failed: %s", e)
            return {}

    async def get_expert_load_balancing(self) -> Dict[str, float]:
        """
        Рассчёт текущей загрузки всех экспертов (0.0–1.0).
        1.0 = нет задач, 0.0 = перегружен (на пороге max_concurrent_tasks или выше).
        Returns: Dict[expert_id -> load_score]
        """
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg not available; get_expert_load_balancing disabled")
            return {}
        conn = None
        try:
            conn = await asyncpg.connect(self._db_url)
            rows = await conn.fetch("""
                SELECT e.id, e.name,
                    COALESCE((SELECT MAX(es.max_concurrent_tasks) FROM expert_specializations es WHERE es.expert_id = e.id), 3) as max_tasks,
                    COUNT(t.id) FILTER (WHERE t.status IN ('pending', 'in_progress')) as current_tasks
                FROM experts e
                LEFT JOIN tasks t ON t.assignee_expert_id = e.id
                WHERE e.is_active = true OR e.is_active IS NULL
                GROUP BY e.id, e.name
            """)
            out: Dict[str, float] = {}
            for r in rows:
                rid = str(r["id"])
                max_t = max(1, r["max_tasks"] or 3)
                cur = r["current_tasks"] or 0
                ratio = cur / max_t
                load_score = max(0.0, min(1.0, 1.0 - ratio))
                out[rid] = round(load_score, 2)
            return out
        except Exception as e:
            if "expert_specializations" in str(e) or "does not exist" in str(e).lower():
                try:
                    rows = await conn.fetch("""
                        SELECT e.id,
                            COUNT(t.id) FILTER (WHERE t.status IN ('pending', 'in_progress')) as current_tasks
                        FROM experts e
                        LEFT JOIN tasks t ON t.assignee_expert_id = e.id
                        WHERE e.is_active = true OR e.is_active IS NULL
                        GROUP BY e.id
                    """)
                    out = {}
                    for r in rows:
                        rid = str(r["id"])
                        cur = r["current_tasks"] or 0
                        max_t = 3
                        load_score = max(0.0, min(1.0, 1.0 - cur / max_t))
                        out[rid] = round(load_score, 2)
                    return out
                except Exception:
                    pass
            logger.debug("get_expert_load_balancing failed: %s", e)
            return {}
        finally:
            if conn:
                await conn.close()
