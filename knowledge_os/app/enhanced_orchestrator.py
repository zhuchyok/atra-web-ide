"""
[KNOWLEDGE OS] Enhanced Orchestrator v3.1.
Enhanced Orchestrator with Task Prioritization and Workload Balancing.
Part of the ATRA Singularity framework.
"""

import asyncio
import getpass
import json
import logging
import os
import subprocess
import sys
import time
import traceback
import fcntl  # [SINGULARITY 21.30] Для блокировки файлов на Unix-системах
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

# ... (остальные импорты)

class PIDLock:
    """[SINGULARITY 21.30] Механизм предотвращения запуска дубликатов процесса."""
    def __init__(self, lock_file="/tmp/enhanced_orchestrator.pid"):
        self.lock_file = lock_file
        self.fd = None

    def acquire(self):
        try:
            self.fd = open(self.lock_file, "w")
            # Попытка установить эксклюзивную блокировку без ожидания
            fcntl.lockf(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd.write(str(os.getpid()))
            self.fd.flush()
            return True
        except (IOError, OSError):
            return False

    def release(self):
        if self.fd:
            try:
                fcntl.lockf(self.fd, fcntl.LOCK_UN)
                self.fd.close()
                if os.path.exists(self.lock_file):
                    os.remove(self.lock_file)
            except Exception:
                pass


try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Third-party imports with fallback
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

# Local project imports with fallback
try:
    from resource_manager import acquire_resource_lock
except ImportError:

    def acquire_resource_lock(name):  # pylint: disable=unused-argument
        """Fallback for acquire_resource_lock."""

        class MockLock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        return MockLock()


try:
    from task_dedup import same_task_for_expert_in_last_n_days
except ImportError:
    same_task_for_expert_in_last_n_days = None
try:
    from ai_core import run_smart_agent_async, run_smart_agent_sync
except ImportError:

    def run_smart_agent_sync(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_sync."""
        return None

    async def run_smart_agent_async(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_async."""
        return None


try:
    from global_scout import run_global_scout_cycle
except ImportError:

    async def run_global_scout_cycle():
        pass


try:
    from distillation_engine import KnowledgeDistiller
except ImportError:

    class KnowledgeDistiller:
        """Fallback for KnowledgeDistiller."""

        async def collect_high_quality_samples(self, **kwargs):
            return 0


try:
    from synthetic_generator import SyntheticKnowledgeGenerator
except ImportError:

    class SyntheticKnowledgeGenerator:
        """Fallback for SyntheticKnowledgeGenerator."""

        async def generate_synthetic_samples(self, **kwargs):
            pass


try:
    from training_pipeline import LocalTrainingPipeline
except ImportError:

    class LocalTrainingPipeline:
        """Fallback for LocalTrainingPipeline."""

        def trigger_auto_upgrade(self):
            return "MOCK_OFFLINE"


# Canonical domains (план Этап 2): маппинг для recruit_expert
CANONICAL_DOMAINS = {
    "Machine Learning": "ML/AI",
    "AI Systems": "ML/AI",
    "AI": "ML/AI",
    "Backend": "Backend",
    "Frontend": "Frontend",
    "DevOps": "DevOps/Infra",
    "Infrastructure": "DevOps/Infra",
}


def _canonical_domain(name: str) -> str:
    """Возвращает каноническое имя домена."""
    return CANONICAL_DOMAINS.get(name, name)


# --- Живой организм: мониторинг Ollama/MLX и запрос восстановления на хосте ---
LLM_HEALTH_TIMEOUT = float(os.getenv("ORCHESTRATOR_LLM_HEALTH_TIMEOUT", "5.0"))
RECOVERY_WEBHOOK_URL = os.getenv(
    "RECOVERY_WEBHOOK_URL", ""
).strip()  # POST при недоступности Ollama/MLX


async def get_ollama_latency() -> float:
    """Измеряет латентность Ollama (Singularity 21.29)."""
    ollama_url = (
        os.getenv("OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_API_URL")
        or "http://host.docker.internal:11434"
    ).rstrip("/")
    if not HTTPX_AVAILABLE:
        return 999.0
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            if r.status_code == 200:
                return time.perf_counter() - start
    except Exception:
        pass
    return 999.0


async def _justify_task_value(title: str, description: str) -> Tuple[bool, str]:
    """Justification Filter: Проверка ценности задачи перед созданием (Singularity 21.29)."""
    try:
        prompt = f"""Обоснуй ценность этой автономной задачи для системы ATRA.
Задача: {title}
Описание: {description[:500]}

Верни JSON: {{"is_valuable": true/false, "reason": "краткое обоснование"}}
Ценными считаются задачи, связанные с безопасностью, критическими ошибками, оптимизацией производительности или новыми технологиями R&D 2026.
"""
        # Используем легкую модель для фильтрации
        result = await run_smart_agent_async(prompt, expert_name="Виктория", category="fast")
        if not result or not isinstance(result, str):
            return True, "no_justification_needed"
        import re

        match = re.search(r"\{.*\}", result, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return bool(data.get("is_valuable", True)), str(data.get("reason", ""))
    except Exception:
        pass
    return True, "fallback_approved"


async def apply_time_decay(conn):
    """Energy Budget (Time Decay): Эволюционный отбор задач (Singularity 21.29)."""
    logger.info("⏳ Applying Time Decay (Energy Budget) to autonomous tasks...")
    # Твои задачи (is_user_requested) имеют бесконечный бюджет.
    # Автономные задачи теряют энергию.
    # Лимиты: low=12h, medium=24h, high=48h. Urgent не трогаем.
    try:
        decay_results = await conn.execute("""
            UPDATE tasks
            SET status = 'cancelled',
                metadata = metadata || jsonb_build_object(
                    'cancel_reason', 'energy_depleted',
                    'cancelled_at', NOW()
                )
            WHERE status = 'pending'
              AND (metadata->>'is_user_requested')::boolean IS NOT TRUE
              AND (
                  (priority = 'low' AND created_at < NOW() - INTERVAL '12 hours') OR
                  (priority = 'medium' AND created_at < NOW() - INTERVAL '24 hours') OR
                  (priority = 'high' AND created_at < NOW() - INTERVAL '48 hours')
              )
              AND parent_task_id IS NULL
        """)
        if decay_results != "UPDATE 0":
            logger.info(f"  🧹 Time Decay: {decay_results.split()[-1]} stale tasks cancelled.")
    except Exception as e:
        logger.warning(f"Time Decay failed: {e}")


async def check_llm_services_health() -> Tuple[bool, bool]:
    """
    Проверка доступности Ollama и MLX (живой организм: оркестратор следит за серверами).
    Возвращает (ollama_ok, mlx_ok).
    """
    ollama_url = (
        os.getenv("OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_API_URL")
        or "http://host.docker.internal:11434"
    ).rstrip("/")
    mlx_url = (os.getenv("MLX_API_URL") or "http://host.docker.internal:11435").rstrip("/")
    ollama_ok, mlx_ok = False, False
    if not HTTPX_AVAILABLE:
        return ollama_ok, mlx_ok
    timeout = httpx.Timeout(LLM_HEALTH_TIMEOUT)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Ollama: GET /api/tags
            try:
                r = await client.get(f"{ollama_url}/api/tags")
                ollama_ok = r.status_code == 200
            except Exception:  # pylint: disable=broad-except
                pass
            # MLX: проверяем /health (быстро), затем /api/tags, fallback /v1/models
            try:
                r = await client.get(f"{mlx_url}/health")
                if r.status_code == 200:
                    mlx_ok = True
                else:
                    # /health не ответил успехом — пробуем /api/tags
                    r = await client.get(f"{mlx_url}/api/tags")
                    mlx_ok = r.status_code == 200
            except Exception:  # pylint: disable=broad-except
                try:
                    r = await client.get(f"{mlx_url}/api/tags")
                    mlx_ok = r.status_code == 200
                except Exception:  # pylint: disable=broad-except
                    pass
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.debug("LLM health check failed: %s", e)
    return ollama_ok, mlx_ok


async def trigger_recovery_webhook(ollama_down: bool, mlx_down: bool) -> None:
    """Уведомить хост о необходимости восстановления Ollama/MLX (живой организм)."""
    if not RECOVERY_WEBHOOK_URL or not HTTPX_AVAILABLE:
        return
    try:
        payload = {
            "ollama": not ollama_down,
            "mlx": not mlx_down,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(RECOVERY_WEBHOOK_URL, json=payload)
            if r.status_code >= 400:
                logger.warning("Recovery webhook returned %s", r.status_code)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.debug("Recovery webhook failed: %s", e)


async def _decompose_via_victoria(goal: str) -> Optional[Dict]:
    """Декомпозиция сложной задачи через Victoria (ORCHESTRATION_IMPROVEMENTS §3.2).
    Возвращает task_plan_struct с subtasks или None."""
    import re

    try:
        prompt = f"""Разложи задачу на подзадачи по отделам.
ВАЖНО: Если задача требует написания кода или анализа данных из конкретного файла, НЕ разбивай её на мелкие теоретические вопросы.
Создай ОДНУ или ДВЕ подзадачи для написания и запуска скрипта.

Задача:
{goal[:2000]}

Верни ТОЛЬКО валидный JSON:
{{"task_description": "кратко", "subtasks": [{{"subtask": "промпт для сотрудника", "department": "отдел", "expert_role": "имя/роль", "priority": "medium"}}]}}"""
        result = await run_smart_agent_async(prompt, expert_name="Виктория", category="planning")
        if not result or not isinstance(result, str):
            return None
        match = re.search(r"\{.*\}", result, re.DOTALL)
        if not match:
            return None
        fixed = re.sub(r",\s*([}\]])", r"\1", match.group())
        data = json.loads(fixed)
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.debug("_decompose_via_victoria: %s", e)
        return None


try:
    from swarm_orchestrator import SwarmOrchestrator
except ImportError:

    class SwarmOrchestrator:
        """Fallback for SwarmOrchestrator."""

        async def handle_critical_failures(self):
            pass


try:
    from meta_architect import MetaArchitect
except ImportError:

    class MetaArchitect:
        """Fallback for MetaArchitect."""

        async def self_repair_cycle(self):
            pass


try:
    from knowledge_graph import run_auto_link_detection
except ImportError:

    async def run_auto_link_detection():
        pass


try:
    from task_rule_executor import can_handle as rule_executor_can_handle
    from task_rule_executor import execute_fallback as rule_executor_execute
except ImportError:

    async def rule_executor_execute(task):  # type: ignore
        return None

    def rule_executor_can_handle(task):  # type: ignore
        return False


try:
    from evolution_monitor import SingularityEvolutionMonitor
except ImportError:

    class SingularityEvolutionMonitor:
        """Fallback for SingularityEvolutionMonitor."""

        async def run_daily_check(self):
            return "MOCK_EVOLUTION_OFFLINE"


try:
    from curiosity_engine import CuriosityEngine
except ImportError:

    class CuriosityEngine:
        """Fallback for CuriosityEngine."""

        async def scan_for_gaps(self):
            return "MOCK_CURIOSITY_OFFLINE"


try:
    from memory_consolidator import MemoryConsolidator
except ImportError:

    class MemoryConsolidator:
        """Fallback for MemoryConsolidator."""

        async def consolidate_memory(self):
            return "MOCK_CONSOLIDATION_OFFLINE"


try:
    from core.cluster_bridge import MultiClusterBridge
except ImportError:
    MultiClusterBridge = None


# Add scripts directory to path for sync
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
try:
    from server_knowledge_sync import ServerKnowledgeSync
except ImportError:
    ServerKnowledgeSync = None

logger = logging.getLogger(__name__)


def _mask_db_url(url: str) -> str:
    """Mask password in DATABASE_URL for logging."""
    if not url or "@" not in url:
        return "***"
    try:
        pre, rest = url.split("@", 1)
        if ":" in pre:
            user_part, _ = pre.rsplit(":", 1)
            return f"{user_part}:***@{rest}"
    except Exception:
        pass
    return "***"


USER_NAME = getpass.getuser()
# Локальная БД (Mac Studio): DATABASE_URL или localhost
DEFAULT_DB_URL = (
    os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"
)
DB_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Приоритеты задач
PRIORITY_WEIGHTS = {
    "urgent": 100,
    "high": 50,
    "medium": 25,
    "low": 10,
}


async def run_cursor_agent(prompt: str):
    """Запуск Cursor Agent для генерации контента через умное ядро"""
    if run_smart_agent_async:
        return await run_smart_agent_async(prompt, expert_name="Виктория", category="orchestrator")
    return run_smart_agent_sync(prompt, expert_name="Виктория", category="orchestrator")


async def get_expert_workload(conn, expert_id: str) -> Dict:
    """Получение текущей загрузки эксперта"""
    # Количество активных задач
    active_tasks = await conn.fetchval(
        """
        SELECT count(*)
        FROM tasks
        WHERE assignee_expert_id = $1
        AND status IN ('pending', 'in_progress')
    """,
        expert_id,
    )

    # Среднее время выполнения задач
    avg_duration = (
        await conn.fetchval(
            """
        SELECT AVG(actual_duration_minutes)
        FROM tasks
        WHERE assignee_expert_id = $1
        AND status = 'completed'
        AND actual_duration_minutes IS NOT NULL
        AND completed_at > NOW() - INTERVAL '30 days'
    """,
            expert_id,
        )
        or 60
    )  # По умолчанию 60 минут

    # Количество завершенных задач за последние 7 дней
    completed_recent = (
        await conn.fetchval(
            """
        SELECT count(*)
        FROM tasks
        WHERE assignee_expert_id = $1
        AND status = 'completed'
        AND completed_at > NOW() - INTERVAL '7 days'
    """,
            expert_id,
        )
        or 0
    )

    # Успешность выполнения (процент завершенных)
    success_rate = (
        await conn.fetchval(
            """
        SELECT
            CASE
                WHEN count(*) = 0 THEN 1.0
                ELSE count(*) FILTER (WHERE status = 'completed')::float / count(*)::float
            END
        FROM tasks
        WHERE assignee_expert_id = $1
        AND created_at > NOW() - INTERVAL '30 days'
    """,
            expert_id,
        )
        or 1.0
    )

    return {
        "active_tasks": active_tasks,
        "avg_duration_minutes": round(avg_duration, 1),
        "completed_recent": completed_recent,
        "success_rate": round(success_rate, 2),
        "workload_score": active_tasks * 10 + (avg_duration / 10),  # Простая метрика загрузки
    }


async def calculate_task_priority(
    conn, title: str, description: str, metadata: Dict, domain_id: Optional[str] = None
) -> str:
    """Автоматический расчет приоритета задачи"""
    priority_score = 0

    # Ключевые слова для urgent
    urgent_keywords = ["критично", "срочно", "urgent", "critical", "🔥", "🚨"]
    if any(kw in title.lower() or kw in description.lower() for kw in urgent_keywords):
        priority_score += 50

    # Ключевые слова для high
    high_keywords = ["важно", "important", "high", "⚠️"]
    if any(kw in title.lower() or kw in description.lower() for kw in high_keywords):
        priority_score += 25

    # Метаданные
    if metadata.get("reason") == "curiosity_engine_starvation":
        priority_score += 30  # Голодные домены - высокий приоритет

    if metadata.get("source") == "code_auditor":
        severity = metadata.get("severity", "medium")
        if severity == "high":
            priority_score += 40
        elif severity == "medium":
            priority_score += 20

    # Время с момента создания (старые задачи получают бонус)
    if domain_id:
        domain_starvation = await conn.fetchval(
            """
            SELECT count(*) < 50
            FROM knowledge_nodes
            WHERE domain_id = $1
        """,
            domain_id,
        )
        if domain_starvation:
            priority_score += 20

    # Определение приоритета
    if priority_score >= 50:
        return "urgent"
    if priority_score >= 30:
        return "high"
    if priority_score >= 15:
        return "medium"
    return "low"


async def assign_task_to_best_expert(
    conn,
    task_id: str,
    domain_id: Optional[str] = None,
    required_role: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Optional[str]:
    """Назначение задачи лучшему эксперту с учетом загрузки и assignee_hint (Этап 6 плана)."""
    # assignee_hint из metadata (например, "Frontend/Performance", "QA")
    assignee_hint = None
    if metadata and isinstance(metadata, dict):
        assignee_hint = metadata.get("assignee_hint")
    if not required_role and assignee_hint:
        required_role = str(assignee_hint)

    # Получаем кандидатов
    candidates = None

    if domain_id:
        # Пробуем найти экспертов по домену
        candidates = await conn.fetch(
            """
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            AND department = (SELECT name FROM domains WHERE id = $1)
        """,
            domain_id,
        )

        # Если не нашли по домену, пробуем по связанным доменам через knowledge_nodes
        if not candidates:
            candidates = await conn.fetch(
                """
                SELECT DISTINCT e.id, e.name, e.role, e.department
                FROM experts e
                INNER JOIN knowledge_nodes kn ON kn.domain_id = $1
                WHERE e.is_active = true
                AND (e.department ILIKE '%' || (SELECT name FROM domains WHERE id = $1) || '%'
                     OR e.role ILIKE '%' || (SELECT name FROM domains WHERE id = $1) || '%')
                LIMIT 20
            """,
                domain_id,
            )

    if not candidates and required_role:
        candidates = await conn.fetch(
            """
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            AND role ILIKE $1
        """,
            f"%{required_role}%",
        )

    # Fallback: если не нашли, берем всех активных экспертов
    if not candidates:
        candidates = await conn.fetch("""
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            ORDER BY RANDOM()
            LIMIT 50
        """)

    if not candidates:
        logger.warning("No experts found for task %s (no active experts in system)", task_id)
        return None

    # Оцениваем каждого кандидата
    best_expert = None
    best_score = float("inf")  # Меньше загрузка = лучше

    for expert in candidates:
        workload = await get_expert_workload(conn, expert["id"])

        # Считаем score (меньше = лучше)
        # Учитываем: активные задачи, среднее время выполнения, успешность
        score = (
            workload["workload_score"] * 0.5  # Загрузка
            + (1.0 - workload["success_rate"]) * 100 * 0.3  # Неуспешность (штраф)
            + (workload["avg_duration_minutes"] / 10) * 0.2  # Время выполнения
        )

        if score < best_score:
            best_score = score
            best_expert = expert

    if best_expert:
        # Оркестратор назначает preferred_source (mlx/ollama) по отделу эксперта
        # ML/Backend/R&D/Performance/Trading/Quant → mlx; остальные → ollama (тяжёлый/лёгкий pairing)
        dept = (best_expert.get("department") or "").lower()
        mlx_depts = ("ml", "backend", "r&d", "performance", "trading", "quant", "devops", "sre")
        preferred_source = "mlx" if any(d in dept for d in mlx_depts) else "ollama"
        # Если создатель уже указал preferred_source в metadata — уважаем
        if metadata and isinstance(metadata, dict) and metadata.get("preferred_source"):
            preferred_source = str(metadata["preferred_source"]).lower()
            if preferred_source not in ("mlx", "ollama"):
                preferred_source = "ollama"
        meta_extra = {"preferred_source": preferred_source}
        await conn.execute(
            """
            UPDATE tasks
            SET assignee_expert_id = $1,
                status = 'pending',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb
            WHERE id = $2
        """,
            best_expert["id"],
            task_id,
            json.dumps(meta_extra),
        )

        logger.info(
            "✅ Task %s assigned to %s (workload: %.2f, source=%s)",
            task_id,
            best_expert["name"],
            best_score,
            preferred_source,
        )
        return best_expert["id"]

    return None


async def get_best_expert_for_domain(
    conn,
    domain_id: Optional[str],
    required_role: Optional[str] = None,
    metadata: Optional[Dict] = None,
):
    """
    Возвращает лучшего эксперта для домена по загрузке (без записи в БД).
    Используется для проверки дедупликации перед созданием задачи Curiosity.
    """
    assignee_hint = None
    if metadata and isinstance(metadata, dict):
        assignee_hint = metadata.get("assignee_hint")
    if not required_role and assignee_hint:
        required_role = str(assignee_hint)

    candidates = None
    if domain_id:
        candidates = await conn.fetch(
            """
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            AND department = (SELECT name FROM domains WHERE id = $1)
        """,
            domain_id,
        )
        if not candidates:
            candidates = await conn.fetch(
                """
                SELECT DISTINCT e.id, e.name, e.role, e.department
                FROM experts e
                INNER JOIN knowledge_nodes kn ON kn.domain_id = $1
                WHERE e.is_active = true
                AND (e.department ILIKE '%' || (SELECT name FROM domains WHERE id = $1) || '%'
                     OR e.role ILIKE '%' || (SELECT name FROM domains WHERE id = $1) || '%')
                LIMIT 20
            """,
                domain_id,
            )
    if not candidates and required_role:
        candidates = await conn.fetch(
            """
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            AND role ILIKE $1
        """,
            f"%{required_role}%",
        )
    if not candidates:
        candidates = await conn.fetch("""
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            ORDER BY RANDOM()
            LIMIT 50
        """)
    if not candidates:
        return None

    best_expert = None
    best_score = float("inf")
    for expert in candidates:
        workload = await get_expert_workload(conn, expert["id"])
        score = (
            workload["workload_score"] * 0.5
            + (1.0 - workload["success_rate"]) * 100 * 0.3
            + (workload["avg_duration_minutes"] / 10) * 0.2
        )
        if score < best_score:
            best_score = score
            best_expert = expert
    return best_expert


async def rebalance_workload(conn):
    """Перебалансировка нагрузки между экспертами"""
    logger.info("⚖️ Starting workload rebalancing...")

    # Находим перегруженных экспертов (> 5 активных задач)
    overloaded = await conn.fetch("""
        SELECT assignee_expert_id, count(*) as task_count
        FROM tasks
        WHERE status IN ('pending', 'in_progress')
        GROUP BY assignee_expert_id
        HAVING count(*) > 5
    """)

    # Перераспределяем задачи
    for overloaded_expert in overloaded:
        expert_id = overloaded_expert["assignee_expert_id"]
        excess_tasks = overloaded_expert["task_count"] - 5

        # Берем задачи с низким приоритетом для перераспределения
        tasks_to_reassign = await conn.fetch(
            """
            SELECT id, priority, domain_id
            FROM tasks
            WHERE assignee_expert_id = $1
            AND status = 'pending'
            ORDER BY
                CASE priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END DESC,
                created_at ASC
            LIMIT $2
        """,
            expert_id,
            excess_tasks,
        )

        for task in tasks_to_reassign:
            # Назначаем незагруженному эксперту из того же домена
            if task["domain_id"]:
                new_expert = await conn.fetchrow(
                    """
                    SELECT e.id, e.department
                    FROM experts e
                    JOIN domains d ON e.department = d.name
                    WHERE d.id = $1
                    AND e.id != $2
                    AND e.id IN (
                        SELECT id FROM (
                            SELECT e2.id, count(t2.id) as task_count
                            FROM experts e2
                            LEFT JOIN tasks t2 ON t2.assignee_expert_id = e2.id
                                AND t2.status IN ('pending', 'in_progress')
                            GROUP BY e2.id
                            HAVING count(t2.id) < 2
                        ) underloaded_inner
                    )
                    ORDER BY RANDOM()
                    LIMIT 1
                """,
                    task["domain_id"],
                    expert_id,
                )

                if new_expert:
                    dept = (new_expert.get("department") or "").lower()
                    mlx_depts = (
                        "ml",
                        "backend",
                        "r&d",
                        "performance",
                        "trading",
                        "quant",
                        "devops",
                        "sre",
                    )
                    pref = "mlx" if any(d in dept for d in mlx_depts) else "ollama"
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET assignee_expert_id = $1,
                            updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb
                        WHERE id = $2
                    """,
                        new_expert["id"],
                        task["id"],
                        json.dumps({"preferred_source": pref}),
                    )
                    logger.info("  ↻ Task %s reassigned (source=%s)", task["id"], pref)


async def run_enhanced_orchestration_cycle():
    """Запуск цикла Enhanced Orchestrator с обновлением знаний корпорации"""
    # Живой организм: проверка Ollama/MLX перед циклом; при недоступности — не грузим эмбеддинги (избегаем OOM) и запрашиваем восстановление
    ollama_ok, mlx_ok = await check_llm_services_health()
    if not ollama_ok:
        logger.warning(
            "[ENHANCED_ORCHESTRATOR] Ollama недоступен — пропускаю обновление знаний корпорации (избегаем OOM), запрашиваю восстановление"
        )
        await trigger_recovery_webhook(ollama_down=True, mlx_down=not mlx_ok)
    if not mlx_ok:
        logger.warning("[ENHANCED_ORCHESTRATOR] MLX недоступен — запрашиваю восстановление")
        if ollama_ok:
            await trigger_recovery_webhook(ollama_down=False, mlx_down=True)

    # Обновляем знания корпорации только если Ollama доступен (иначе множество get_embedding → таймауты и риск OOM)
    if ollama_ok:
        try:
            from corporation_knowledge_system import update_all_agents_knowledge

            await update_all_agents_knowledge()
            logger.info("✅ Знания корпорации обновлены перед циклом оркестрации")
        except Exception as e:
            logger.debug("Не удалось обновить знания корпорации: %s", e)

    """Основной цикл улучшенного Orchestrator"""
    if not ASYNCPG_AVAILABLE:
        logger.error("❌ asyncpg is not installed. Orchestration aborted.")
        return

    async with acquire_resource_lock("orchestrator"):
        logger.info("[ENHANCED_ORCHESTRATOR] cycle start DATABASE_URL=%s", _mask_db_url(DB_URL))
        conn = await asyncpg.connect(DB_URL)
        try:
            unassigned_count = await conn.fetchval(
                "SELECT COUNT(*) FROM tasks WHERE assignee_expert_id IS NULL"
            )
            logger.info("[ENHANCED_ORCHESTRATOR] unassigned_tasks=%s", unassigned_count)
        except Exception as e:
            logger.warning("[ENHANCED_ORCHESTRATOR] could not count unassigned: %s", e)
        rd = None
        if REDIS_AVAILABLE:
            rd = await redis.from_url(REDIS_URL, decode_responses=True)

        try:
            # --- ФАЗА 0: AUTONOMOUS ERROR FIXING (Автоматическое исправление ошибок) ---
            t0 = time.time()
            logger.info("🔧 Phase 0: Auto-fixing errors...")
            
            # [SINGULARITY 21.29] Apply Time Decay before starting new work
            await apply_time_decay(conn)
            
            phase_result = "skipped"
            try:
                from error_auto_fixer import auto_fix_all_errors

                fix_results = await auto_fix_all_errors(conn)
                if (
                    fix_results.get("stuck_tasks_fixed", 0) > 0
                    or fix_results.get("unassigned_tasks", 0) > 0
                ):
                    phase_result = str(fix_results)
                else:
                    phase_result = "ok"
            except ImportError:
                logger.debug("error_auto_fixer module not found, skipping")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Auto-fix error: %s", exc)
                phase_result = str(exc)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=0 duration_ms=%.0f result=%s",
                (time.time() - t0) * 1000,
                phase_result,
            )

            # --- ФАЗА 0.5: AUTONOMOUS MIGRATIONS (работает без knowledge_nodes/domains) ---
            t05 = time.time()
            logger.info("🗄️ Phase 0.5: Autonomous Migrations...")
            try:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id SERIAL PRIMARY KEY,
                        migration_name VARCHAR(255) UNIQUE NOT NULL,
                        applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                base_dir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                migration_dir = os.path.join(base_dir_path, "db", "migrations")
                if os.path.exists(migration_dir):
                    applied_list = await conn.fetch("SELECT migration_name FROM schema_migrations")
                    applied_set = {r["migration_name"] for r in applied_list}
                    for file_name in sorted(os.listdir(migration_dir)):
                        if not file_name.endswith(".sql"):
                            continue
                        if file_name in applied_set:
                            continue
                        logger.info("  ⚡ Applying migration: %s", file_name)
                        try:
                            with open(
                                os.path.join(migration_dir, file_name), encoding="utf-8"
                            ) as f:
                                await conn.execute(f.read())
                            await conn.execute(
                                "INSERT INTO schema_migrations (migration_name, applied_at) VALUES ($1, NOW()) ON CONFLICT (migration_name) DO NOTHING",
                                file_name,
                            )
                            logger.info("  ✅ Applied: %s", file_name)
                        except Exception as mig_err:  # pylint: disable=broad-exception-caught
                            logger.error("  ❌ Migration %s failed: %s", file_name, mig_err)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Migration error: %s", exc)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=0.5 duration_ms=%.0f result=migrations",
                (time.time() - t05) * 1000,
            )

            victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
            if not victoria_id:
                logger.warning("Victoria not found, creating...")
                victoria_id = await conn.fetchval("""
                    INSERT INTO experts (name, role, system_prompt, department)
                    VALUES ('Виктория', 'Team Lead', 'Team Lead and Coordinator', 'Management')
                    RETURNING id
                """)

            # --- ФАЗА 1: ПРИОРИТИЗАЦИЯ СУЩЕСТВУЮЩИХ ЗАДАЧ ---
            t1 = time.time()
            logger.info("📊 Phase 1: Prioritizing existing tasks...")
            unprioritized_tasks = await conn.fetch("""
                SELECT id, title, description, metadata, domain_id
                FROM tasks
                WHERE priority = 'medium'
                AND status = 'pending'
                AND created_at > NOW() - INTERVAL '24 hours'
            """)

            for task in unprioritized_tasks:
                task_meta = (
                    json.loads(task["metadata"])
                    if isinstance(task["metadata"], str)
                    else task["metadata"]
                )
                new_priority = await calculate_task_priority(
                    conn, task["title"], task["description"], task_meta, task["domain_id"]
                )
                if new_priority != "medium":
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET priority = $1,
                            updated_at = NOW()
                        WHERE id = $2
                    """,
                        new_priority,
                        task["id"],
                    )
                    logger.info("  📌 Task %s: priority updated to %s", task["id"], new_priority)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=1 duration_ms=%.0f result=%s tasks reprioritized",
                (time.time() - t1) * 1000,
                len(unprioritized_tasks),
            )

            # --- ФАЗА 1.5: ДЕКОМПОЗИЦИЯ СЛОЖНЫХ ЗАДАЧ (ORCHESTRATION_IMPROVEMENTS §3.2) ---
            t15 = time.time()
            decomposed_count = 0
            try:
                complex_unassigned = await conn.fetch("""
                    SELECT id, title, description, domain_id, priority, metadata,
                           (metadata->>'project_context') AS project_context
                    FROM tasks
                    WHERE assignee_expert_id IS NULL
                    AND status = 'pending'
                    AND (metadata->>'decomposed') IS DISTINCT FROM 'true'
                    AND (
                        priority IN ('high', 'urgent')
                        OR (metadata->>'complex')::boolean = true
                    )
                    AND parent_task_id IS NULL
                    ORDER BY
                        CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 ELSE 3 END,
                        created_at ASC
                    LIMIT 3
                """)
            except Exception as schema_err:
                if (
                    "parent_task_id" in str(schema_err).lower()
                    or "column" in str(schema_err).lower()
                ):
                    logger.debug(
                        "Phase 1.5 skipped: parent_task_id not in schema (run add_task_orchestration_schema migration)"
                    )
                else:
                    logger.warning("Phase 1.5 query failed: %s", schema_err)
                complex_unassigned = []
            for task in complex_unassigned:
                try:
                    goal = f"{task['title']}\n\n{task['description'] or ''}"
                    struct = await _decompose_via_victoria(goal)
                    if struct and struct.get("subtasks"):
                        subtasks = struct["subtasks"]

                        # --- PLAN MODE: Одобрение плана для сложных задач ---
                        if len(subtasks) >= 3 or (task.get("metadata") or {}).get("complex"):
                            from human_in_the_loop import get_hitl

                            hitl = get_hitl()

                            # [AUTONOMOUS IMPLEMENTATION PROTOCOL]
                            # Если уверенность выше 0.95, пропускаем HITL и помечаем как авто-одобрено
                            confidence = struct.get("confidence", 0.0)
                            if confidence >= 0.95:
                                logger.info(
                                    f"🚀 [AUTO-IMPL] Высокая уверенность ({confidence:.2f}) для задачи {task['id']}. Авто-одобрение."
                                )
                                await conn.execute(
                                    """
                                    UPDATE tasks
                                    SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"plan_status": "auto_approved", "auto_impl": true}'::jsonb
                                    WHERE id = $1
                                """,
                                    task["id"],
                                )
                            else:
                                approval_req = await hitl.request_approval(
                                    action="plan_approval",
                                    description=f"Одобрение плана для задачи: {task['title']}",
                                    agent_name="Виктория",
                                    proposed_result=struct,
                                    context={
                                        "task_id": str(task["id"]),
                                        "subtasks_count": len(subtasks),
                                    },
                                )
                                # Если требуется одобрение и оно еще не получено (pending), пропускаем выполнение в этом цикле
                                if await hitl.check_approval_required("plan_approval"):
                                    logger.info(
                                        f"⏳ Task {task['id']} is waiting for plan approval."
                                    )
                                    await conn.execute(
                                        """
                                        UPDATE tasks
                                        SET status = 'pending',
                                            metadata = COALESCE(metadata, '{}'::jsonb) || '{"plan_status": "pending_approval"}'::jsonb
                                        WHERE id = $1
                                    """,
                                        task["id"],
                                    )
                                    continue

                        for st in subtasks[:5]:  # max 5 subtasks
                            st_desc = st.get("subtask", st.get("description", ""))
                            st_dept = st.get("department", "General")
                            domain_row = await conn.fetchrow(
                                "SELECT id FROM domains WHERE name = $1", st_dept
                            )
                            st_domain_id = domain_row["id"] if domain_row else task["domain_id"]
                            meta = json.dumps(
                                {
                                    "source": "orchestrator_decompose",
                                    "parent_task_id": str(task["id"]),
                                    "expert_role": st.get("expert_role", ""),
                                }
                            )
                            _meta = task.get("metadata")
                            parent_pc = task.get("project_context") or (
                                json.loads(_meta).get("project_context")
                                if isinstance(_meta, str)
                                else (_meta or {}).get("project_context")
                            )
                            try:
                                sub_id = await conn.fetchval(
                                    """
                                    INSERT INTO tasks (title, description, status, priority, domain_id, creator_expert_id, metadata, parent_task_id, project_context)
                                    VALUES ($1, $2, 'pending', $3, $4, $5, $6::jsonb, $7, $8)
                                    RETURNING id
                                """,
                                    (st_desc[:255] if len(st_desc) > 255 else st_desc),
                                    st_desc,
                                    st.get("priority", "medium"),
                                    st_domain_id,
                                    victoria_id,
                                    meta,
                                    task["id"],
                                    parent_pc,
                                )
                            except Exception as col_err:
                                if (
                                    "project_context" in str(col_err)
                                    or "column" in str(col_err).lower()
                                ):
                                    sub_id = await conn.fetchval(
                                        """
                                        INSERT INTO tasks (title, description, status, priority, domain_id, creator_expert_id, metadata, parent_task_id)
                                        VALUES ($1, $2, 'pending', $3, $4, $5, $6::jsonb, $7)
                                        RETURNING id
                                    """,
                                        (st_desc[:255] if len(st_desc) > 255 else st_desc),
                                        st_desc,
                                        st.get("priority", "medium"),
                                        st_domain_id,
                                        victoria_id,
                                        meta,
                                        task["id"],
                                    )
                                else:
                                    raise
                            if sub_id:
                                await assign_task_to_best_expert(
                                    conn,
                                    str(sub_id),
                                    st_domain_id,
                                    metadata={"assignee_hint": st.get("expert_role")},
                                )
                                decomposed_count += 1
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"decomposed": true}'::jsonb,
                                updated_at = NOW()
                            WHERE id = $1
                        """,
                            task["id"],
                        )
                        logger.info(
                            "  📦 Task %s decomposed into %s subtasks",
                            task["id"],
                            min(len(subtasks), 5),
                        )
                except Exception as e:
                    logger.warning("Decompose task %s failed: %s", task["id"], e)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=1.5 duration_ms=%.0f result=%s decomposed",
                (time.time() - t15) * 1000,
                decomposed_count,
            )

            # --- ФАЗА 1.6: БАТЧ-ГРУППИРОВКА МЕЛКИХ ЗАДАЧ (ARCHITECTURE_IMPROVEMENTS §2.5) ---
            # При BATCH_SMALL_TASKS_ENABLED=true: задачи одного domain, low/medium, не complex → batch_group в metadata
            t16 = time.time()
            batch_grouped = 0
            if os.getenv("BATCH_SMALL_TASKS_ENABLED", "").lower() in ("1", "true", "yes"):
                try:
                    batch_threshold = int(os.getenv("BATCH_SMALL_TASKS_THRESHOLD", "3"))
                    domains_with_many = await conn.fetch(
                        """
                        SELECT domain_id, COUNT(*) as cnt
                        FROM tasks
                        WHERE assignee_expert_id IS NULL
                        AND status = 'pending'
                        AND priority IN ('low', 'medium')
                        AND (metadata->>'complex') IS DISTINCT FROM 'true'
                        AND domain_id IS NOT NULL
                        GROUP BY domain_id
                        HAVING COUNT(*) >= $1
                    """,
                        batch_threshold,
                    )
                    for row in domains_with_many:
                        batch_id = f"batch_{row['domain_id']}"
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                                updated_at = NOW()
                            WHERE assignee_expert_id IS NULL
                            AND status = 'pending'
                            AND domain_id = $1
                            AND priority IN ('low', 'medium')
                            AND (metadata->>'complex') IS DISTINCT FROM 'true'
                        """,
                            row["domain_id"],
                            json.dumps({"batch_group": batch_id}),
                        )
                        batch_grouped += row["cnt"]
                except Exception as e:
                    logger.debug("Phase 1.6 (batch grouping) failed: %s", e)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=1.6 duration_ms=%.0f result=%s batch_grouped",
                (time.time() - t16) * 1000,
                batch_grouped,
            )

            # --- ФАЗА 1.8: ПРЕДВАРИТЕЛЬНЫЙ АУДИТ ПЛАНА (RED TEAM CRITIC) ---
            # Паттерн OpenAI o1/o3: эксперт-критик ищет ошибки до начала выполнения
            t18 = time.time()
            critique_count = 0
            complex_tasks = await conn.fetch("""
                SELECT id, title, description, metadata
                FROM tasks
                WHERE status = 'pending'
                AND (metadata->>'decomposed' = 'true' OR priority = 'urgent')
                AND (metadata->>'critique_passed') IS NULL
                LIMIT 5
            """)

            for task in complex_tasks:
                try:
                    # [ADAPTIVE PRUNING] Обрезаем контекст для критика
                    from isolated_context import IsolatedContext

                    temp_ctx = IsolatedContext(agent_name="Critic", project_context="Orchestration")
                    # Добавляем описание задачи как базовую память
                    temp_ctx.add_memory("user", task["description"])
                    temp_ctx.prune_context(task["title"], max_chars=2000)

                    # Получаем подзадачи для аудита
                    subtasks = await conn.fetch(
                        "SELECT title, description FROM tasks WHERE parent_task_id = $1", task["id"]
                    )
                    plan_summary = f"Задача: {task['title']}\n"
                    plan_summary += "\n".join([f"- {st['title']}" for st in subtasks])

                    critic_prompt = f"""Ты - Red Team Critic в корпорации ATRA. Проведи аудит плана.
ПЛАН:
{plan_summary}

Найди:
1. Логические дыры (пропущенные шаги).
2. Риски безопасности или стабильности.
3. Ошибки в зависимостях.

Выдай вердикт: ОДОБРЕНО или КРИТИКА (с описанием правок).
"""
                    critic_verdict = await run_smart_agent_async(
                        critic_prompt, expert_name="Red Team Critic", category="reasoning"
                    )

                    # [AUTONOMOUS IMPLEMENTATION PROTOCOL]
                    # Если критик ОДОБРИЛ и уверенность высокая, помечаем как готовое к исполнению
                    is_approved = critic_verdict and "ОДОБРЕНО" in critic_verdict

                    if critic_verdict and "КРИТИКА" in critic_verdict:
                        logger.warning(
                            f"🚨 [CRITIC] План задачи {task['id']} отклонен: {critic_verdict[:200]}..."
                        )
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                                status = 'pending'
                            WHERE id = $1
                        """,
                            task["id"],
                            json.dumps(
                                {"critique_failed": True, "critic_feedback": critic_verdict}
                            ),
                        )
                    else:
                        # Если авто-одобрено или критик сказал ОДОБРЕНО
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"critique_passed": true, "ready_for_execution": true}'::jsonb
                            WHERE id = $1
                        """,
                            task["id"],
                        )
                        critique_count += 1
                        if is_approved:
                            logger.info(
                                f"✅ [AUTO-IMPL] План задачи {task['id']} прошел аудит и запущен в работу."
                            )
                except Exception as e:
                    logger.debug(f"Critic phase failed for task {task['id']}: {e}")

            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=1.8 duration_ms=%.0f result=%s audited",
                (time.time() - t18) * 1000,
                critique_count,
            )

            # --- ФАЗА 1.9: ИНТЕЛЛЕКТУАЛЬНЫЙ ОПТИМИЗАТОР ОЧЕРЕДИ (EXECUTION OPTIMIZER) ---
            # Паттерн OpenAI GPT-5: строим граф зависимостей и запускаем независимые задачи параллельно
            t19 = time.time()
            optimized_count = 0
            pending_tasks = await conn.fetch("""
                SELECT id, title, parent_task_id, metadata
                FROM tasks
                WHERE status = 'pending'
                AND assignee_expert_id IS NOT NULL
                AND (metadata->>'critique_passed' = 'true' OR metadata->>'decomposed' IS NULL)
                LIMIT 20
            """)

            if pending_tasks:
                # Группируем по родительской задаче
                groups = {}
                for t in pending_tasks:
                    pid = str(t["parent_task_id"]) if t["parent_task_id"] else "root"
                    if pid not in groups:
                        groups[pid] = []
                    groups[pid].append(t)

                for pid, tasks in groups.items():
                    # Для каждой группы определяем, что можно запустить сейчас
                    # (В нашей упрощенной схеме: если нет явных зависимостей в metadata, можно всё параллельно)
                    for t in tasks:
                        # Если задача не имеет зависимостей (или они выполнены), помечаем как ready_for_execution
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"ready_for_execution": true}'::jsonb
                            WHERE id = $1
                        """,
                            t["id"],
                        )
                        optimized_count += 1

            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=1.9 duration_ms=%.0f result=%s optimized",
                (time.time() - t19) * 1000,
                optimized_count,
            )

            # --- ФАЗА 2: НАЗНАЧЕНИЕ ЗАДАЧ БЕЗ ИСПОЛНИТЕЛЯ ---
            t2 = time.time()
            logger.info("👥 Phase 2: Assigning unassigned tasks...")
            unassigned_tasks = await conn.fetch("""
                SELECT id, title, description, domain_id, priority, metadata
                FROM tasks
                WHERE assignee_expert_id IS NULL
                AND status = 'pending'
                AND (metadata->>'decomposed') IS DISTINCT FROM 'true'
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    created_at ASC
            """)

            for task in unassigned_tasks:
                await assign_task_to_best_expert(
                    conn, task["id"], task["domain_id"], metadata=task.get("metadata")
                )
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=2 duration_ms=%.0f result=%s tasks assigned",
                (time.time() - t2) * 1000,
                len(unassigned_tasks),
            )

            # --- ФАЗА 2.5: ORCHESTRATOR FALLBACK (задачи с attempt_count >= 3, rule-based) ---
            t25 = time.time()
            failed_tasks = await conn.fetch("""
                SELECT id, title, description, metadata
                FROM tasks
                WHERE status = 'pending'
                AND (
                    COALESCE((metadata->>'attempt_count')::int, 0) >= 3
                    OR COALESCE((metadata->>'agent_failed_count')::int, 0) >= 3
                )
                LIMIT 20
            """)
            rule_completed = 0
            for ft in failed_tasks:
                task_dict = dict(ft)
                # metadata может прийти как JSON-строка из asyncpg — парсим в dict
                import json as _json

                if isinstance(task_dict.get("metadata"), str):
                    try:
                        task_dict["metadata"] = _json.loads(task_dict["metadata"])
                    except Exception:
                        task_dict["metadata"] = {}
                if rule_executor_can_handle(task_dict):
                    try:
                        result = await rule_executor_execute(task_dict)
                        if result:
                            await conn.execute(
                                """
                                UPDATE tasks
                                SET status = 'completed', result = $2, updated_at = NOW(),
                                    metadata = COALESCE(metadata, '{}'::jsonb) || '{"execution_mode": "rule_based", "orchestrator_fallback": true}'::jsonb
                                WHERE id = $1
                            """,
                                ft["id"],
                                result,
                            )
                            rule_completed += 1
                            logger.info("  rule_executor completed task %s", ft["id"])
                    except Exception as e:
                        logger.warning("rule_executor failed for task %s: %s", ft["id"], e)
            if failed_tasks:
                logger.info(
                    "[ENHANCED_ORCHESTRATOR] phase=2.5 duration_ms=%.0f result=%s rule-based of %s failed",
                    (time.time() - t25) * 1000,
                    rule_completed,
                    len(failed_tasks),
                )

            # --- ФАЗА 3: ПЕРЕБАЛАНСИРОВКА НАГРУЗКИ ---
            t3 = time.time()
            logger.info("⚖️ Phase 3: Rebalancing workload...")
            await rebalance_workload(conn)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=3 duration_ms=%.0f result=rebalance",
                (time.time() - t3) * 1000,
            )

            # --- ФАЗА 4: АССОЦИАТИВНЫЙ МОЗГ (как в оригинале) ---
            logger.info("🧩 Phase 4: Cross-domain linking...")
            new_knowledge = await conn.fetch("""
                SELECT k.id, k.content, d.name as domain, k.metadata, k.domain_id
                FROM knowledge_nodes k
                JOIN domains d ON k.domain_id = d.id
                WHERE k.created_at > NOW() - INTERVAL '6 hours'
                AND (k.metadata->>'orchestrated' IS NULL OR k.metadata->>'orchestrated' = 'false')
                LIMIT 10
            """)

            for node in new_knowledge:
                random_node = await conn.fetchrow(
                    """
                    SELECT k.content, d.name as domain
                    FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
                    WHERE k.domain_id != $1 ORDER BY RANDOM() LIMIT 1
                """,
                    node["domain_id"],
                )

                if random_node:
                    link_prompt = f"""
                    Вы - Виктория (Team Lead). Найдите неочевидную связь между двумя фактами:
                    ФАКТ А ({node["domain"]}): {node["content"]}
                    ФАКТ Б ({random_node["domain"]}): {random_node["content"]}

                    ЗАДАЧА: Сформулируйте одну инновационную гипотезу на стыке этих знаний.
                    Верните ТОЛЬКО текст гипотезы.
                    """
                    hypothesis = await run_cursor_agent(link_prompt)
                    if hypothesis:
                        content_kn = f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}"
                        meta_kn = json.dumps(
                            {"source": "cross_domain_linker", "parents": [str(node["id"])]}
                        )
                        embedding = None
                        try:
                            from semantic_cache import get_embedding

                            embedding = await get_embedding(content_kn[:8000])
                        except Exception:
                            pass
                        if embedding is not None:
                            kn_id = await conn.fetchval(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                                VALUES ($1, $2, 0.95, $3, true, $4::vector)
                                RETURNING id
                            """,
                                node["domain_id"],
                                content_kn,
                                meta_kn,
                                str(embedding),
                            )
                        else:
                            kn_id = await conn.fetchval(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                                VALUES ($1, $2, 0.95, $3, true)
                                RETURNING id
                            """,
                                node["domain_id"],
                                content_kn,
                                meta_kn,
                            )
                        if rd:
                            await rd.xadd(
                                "knowledge_stream",
                                {"type": "synthetic_link", "content": hypothesis},
                            )
                        # Отправка гипотезы в дебаты для обсуждения экспертами
                        try:
                            from nightly_learner import create_debate_for_hypothesis

                            await create_debate_for_hypothesis(
                                conn,
                                kn_id,
                                f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}",
                                node["domain_id"],
                            )
                        except Exception as db_err:
                            logger.debug("Hypothesis debate skip: %s", db_err)

                await conn.execute(
                    """
                    UPDATE knowledge_nodes
                    SET metadata = metadata || '{"orchestrated": "true"}'::jsonb
                    WHERE id = $1
                """,
                    node["id"],
                )

            # --- ФАЗА 5: ДВИГАТЕЛЬ ЛЮБОПЫТСТВА (с приоритизацией) ---
            logger.info("🔍 Phase 5: Curiosity Engine...")

            # [SINGULARITY 21.29] Resource-Driven Curiosity: Check Ollama latency
            # Если латентность > 1.0с (Ollama перегружена), Curiosity Engine "засыпает"
            ollama_latency = await get_ollama_latency()
            if ollama_latency > 1.0:
                logger.warning(
                    "⏸️ RESOURCE-DRIVEN CURIOSITY: Ollama latency high (%.2fs > 1.0s). Curiosity Engine sleeps.",
                    ollama_latency,
                )
                deserts = []
            else:
                # BACKPRESSURE: Лимит ожидающих задач (Stability & Performance Watchdog)
                # Если задач в очереди уже много, Curiosity Engine не должен создавать новые,
                # чтобы не усугублять перегрузку.
                pending_count = await conn.fetchval(
                    "SELECT count(*) FROM tasks WHERE status = 'pending'"
                )
                max_pending = int(os.getenv("SMART_WORKER_MAX_PENDING", "10"))
                if pending_count >= max_pending:
                    logger.warning(
                        "⏸️ BACKPRESSURE: Too many pending tasks (%s/%s). Skipping Curiosity Engine research tasks.",
                        pending_count,
                        max_pending,
                    )
                    deserts = []
                else:
                    deserts = await conn.fetch("""
                        SELECT d.id, d.name, count(k.id) as node_count
                        FROM domains d LEFT JOIN knowledge_nodes k ON d.id = k.domain_id
                        GROUP BY d.id, d.name
                        HAVING count(k.id) < 50 OR max(k.created_at) < NOW() - INTERVAL '48 hours'
                        ORDER BY count(k.id) ASC
                        LIMIT 5
                    """)

            # Лимит автономных экспертов (план: не более 25)
            autonomous_count = await conn.fetchval(
                "SELECT count(*) FROM experts WHERE (metadata->>'is_autonomous')::text = 'true'"
            )
            autonomous_limit = int(os.getenv("AUTONOMOUS_EXPERT_LIMIT", "25"))

            for desert in deserts:
                canonical = _canonical_domain(desert["name"])
                expert_count = await conn.fetchval(
                    "SELECT count(*) FROM experts WHERE department = $1 OR department = $2",
                    desert["name"],
                    canonical,
                )
                if expert_count == 0 and (autonomous_count or 0) < autonomous_limit:
                    logger.info(
                        "  🔍 Recruiting expert for %s (canonical: %s)...",
                        desert["name"],
                        canonical,
                    )
                    expert_gen_path = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), "expert_generator.py"
                    )
                    subprocess.run(["python3", expert_gen_path, canonical], check=False)
                    autonomous_count = (autonomous_count or 0) + 1

                curiosity_task = (
                    f"Проведи глубокое исследование новых технологий и трендов 2026 "
                    f"в области {desert['name']}. Найди 3 прорывных инсайта."
                )
                title_curiosity = f"🔥 ИССЛЕДОВАНИЕ: {desert['name']}"

                # [SINGULARITY 21.29] Justification Filter (Proof of Value)
                is_valuable, reason = await _justify_task_value(title_curiosity, curiosity_task)
                if not is_valuable:
                    logger.info(
                        "  ⏭️ Skip Curiosity task for %s: low value (reason: %s)",
                        desert["name"],
                        reason,
                    )
                    continue

                best_expert = await get_best_expert_for_domain(conn, desert["id"])
                if best_expert and same_task_for_expert_in_last_n_days:
                    if await same_task_for_expert_in_last_n_days(
                        conn, title_curiosity, curiosity_task, best_expert["id"], days=30
                    ):
                        logger.info(
                            "  ⏭️ Skip duplicate: same research task for expert %s (%s) in last 30 days",
                            best_expert.get("name"),
                            desert["name"],
                        )
                        continue
                priority = "high" if desert["node_count"] < 20 else "medium"
                task_id = await conn.fetchval(
                    """
                    INSERT INTO tasks (title, description, status, priority, creator_expert_id, domain_id, metadata)
                    VALUES ($1, $2, 'pending', $3, $4, $5, $6)
                    RETURNING id
                """,
                    title_curiosity,
                    curiosity_task,
                    priority,
                    victoria_id,
                    desert["id"],
                    json.dumps(
                        {
                            "reason": "curiosity_engine_starvation",
                            "node_count": desert["node_count"],
                            "justification": reason,
                            "is_autonomous": True,
                        }
                    ),
                )
                await assign_task_to_best_expert(conn, task_id, desert["id"])

            logger.info("🌐 Phase 5: Running Global Scout validation...")
            try:
                await run_global_scout_cycle()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Global Scout error: %s", exc)

            logger.info("🔗 Phase 6: Running auto-link detection...")
            try:
                await run_auto_link_detection()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Auto-link detection error: %s", exc)

            logger.info("🧬 Phase 7: Knowledge Distillation & Auto-Upgrade...")
            try:
                distiller = KnowledgeDistiller()
                distilled_count = await distiller.collect_high_quality_samples(days=1)
                if distilled_count > 0:
                    logger.info("  ✨ Distilled %d high-quality samples.", distilled_count)
                generator = SyntheticKnowledgeGenerator()
                await generator.generate_synthetic_samples(limit=5)
                pipeline = LocalTrainingPipeline()
                status = pipeline.trigger_auto_upgrade()
                if "ЗАПУЩЕН" in status or "ГОТОВ" in status:
                    logger.info("  🔥 AUTONOMOUS UPGRADE STATUS: %s", status)
                    await conn.execute("INSERT INTO notifications (message) VALUES ($1)", status)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Distillation error: %s", exc)

            logger.info("🔧 Phase 8: Self-Repair Engine...")
            try:
                errors = await conn.fetch("""
                    SELECT id, user_query, assistant_response, metadata
                    FROM interaction_logs
                    WHERE (assistant_response LIKE '❌%' OR assistant_response LIKE '⚠️%')
                    AND created_at > NOW() - INTERVAL '1 hour'
                    AND (metadata->>'repaired' IS NULL OR metadata->>'repaired' = 'false')
                    LIMIT 5
                """)
                for err in errors:
                    repair_task = (
                        f"ОШИБКА В СИСТЕМЕ: {err['assistant_response']}\n"
                        f"ЗАПРОС: {err['user_query']}\n\n"
                        f"ЗАДАЧА: Проанализируй логи и код, найди причину и предложи исправление."
                    )
                    await conn.execute(
                        """
                        INSERT INTO tasks (title, description, status, priority, creator_expert_id, metadata)
                        VALUES ($1, $2, 'pending', 'urgent', $3, $4)
                    """,
                        "🚨 АВТО-РЕМОНТ: Ошибка",
                        repair_task,
                        victoria_id,
                        json.dumps({"source": "self_repair", "log_id": str(err["id"])}),
                    )
                    await conn.execute(
                        """
                        UPDATE interaction_logs
                        SET metadata = metadata || '{"repaired": "true"}'::jsonb
                        WHERE id = $1
                    """,
                        err["id"],
                    )
                    logger.info("  🔧 Created repair task for log %s", err["id"])
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Self-repair error: %s", exc)

            logger.info("🐝 Phase 10: Swarm War-Room...")
            try:
                swarm = SwarmOrchestrator()
                await swarm.handle_critical_failures()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Swarm error: %s", exc)

            logger.info("🏗️ Phase 11: Meta-Architect Review...")
            try:
                architect = MetaArchitect()
                await architect.self_repair_cycle()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Meta-Architect error: %s", exc)

            logger.info("🧬 Phase 12: Autonomous Evolution...")
            try:
                evolution = SingularityEvolutionMonitor()
                evolution_report = await evolution.run_daily_check()
                logger.info("  %s", evolution_report)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Evolution error: %s", exc)

            logger.info("🔍 Phase 13: Curiosity Engine Gap Analysis...")
            try:
                curiosity = CuriosityEngine()
                gap_result = await curiosity.scan_for_gaps()
                logger.info("  %s", gap_result)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Curiosity error: %s", exc)

            logger.info("🧠 Phase 14: Memory Consolidation (The Dreaming)...")
            try:
                consolidator = MemoryConsolidator()
                consolidation_result = await consolidator.consolidate_memory()
                logger.info("  %s", consolidation_result)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Consolidation error: %s", exc)

            logger.info("🌐 Phase 14.5: Multi-Cluster Bridge Sync...")
            if MultiClusterBridge:
                try:
                    bridge = MultiClusterBridge()
                    await bridge.initialize(conn)
                    await bridge.send_heartbeat()
                    await bridge.gossip_sync()
                    await bridge.task_tunneling()
                    logger.info("  ✅ Multi-cluster sync completed.")
                except Exception as exc:
                    logger.error("Multi-cluster bridge error: %s", exc)

            logger.info("🌐 Phase 15: Global Team Knowledge Sync...")
            if ServerKnowledgeSync:
                try:
                    last_sync_key = "last_global_sync"
                    last_sync = None
                    if rd:
                        last_sync = await rd.get(last_sync_key)
                    now_str = datetime.now().isoformat()
                    should_sync = True
                    if last_sync:
                        last_sync_dt = datetime.fromisoformat(last_sync)
                        if datetime.now() - last_sync_dt < timedelta(hours=1):
                            should_sync = False
                    if should_sync:
                        sync_manager = ServerKnowledgeSync()
                        await sync_manager.sync_experts()
                        synced_count = await sync_manager.sync_reports(limit=50)
                        logger.info("  📥 Synced %d reports and full team hierarchy.", synced_count)
                        if rd:
                            await rd.set(last_sync_key, now_str)
                    else:
                        logger.info("  ⏭️ Sync skipped (already synced recently).")
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Sync error: %s", exc)
            else:
                logger.info("  ⚠️ ServerKnowledgeSync module not found.")

            logger.info("📦 Phase 16: Knowledge Archivation...")
            try:
                from knowledge_archiver import KnowledgeArchiver
                from strategy_session_manager import StrategySessionManager

                session_manager = StrategySessionManager()
                archiver = KnowledgeArchiver(session_manager)
                archive_key = "last_knowledge_archive"
                last_archive = None
                if rd:
                    last_archive = await rd.get(archive_key)
                now_str = datetime.now().isoformat()
                should_archive = True
                if last_archive:
                    last_archive_dt = datetime.fromisoformat(last_archive)
                    if datetime.now() - last_archive_dt < timedelta(days=1):
                        should_archive = False
                if should_archive:
                    await archiver.periodic_archive_task()
                    if rd:
                        await rd.set(archive_key, now_str)
                    logger.info("  ✅ Knowledge archivation completed.")
                else:
                    logger.info("  ⏭️ Archive skipped (already archived today).")
            except ImportError:
                logger.info("  ⚠️ KnowledgeArchiver module not found.")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Archive error: %s", exc)

            # Автоочистка старых задач (completed > 30 дней, cancelled) — раз в сутки
            cleanup_key = "last_tasks_cleanup"
            last_cleanup = None
            if rd:
                last_cleanup = await rd.get(cleanup_key)
            should_cleanup = True
            if last_cleanup:
                try:
                    last_cleanup_dt = datetime.fromisoformat(last_cleanup)
                    if datetime.now() - last_cleanup_dt < timedelta(days=1):
                        should_cleanup = False
                except (TypeError, ValueError):
                    pass
            if should_cleanup:
                try:
                    deleted_completed = (
                        await conn.fetchval("""
                        WITH d AS (
                            DELETE FROM tasks
                            WHERE status = 'completed' AND updated_at < NOW() - INTERVAL '30 days'
                            RETURNING id
                        )
                        SELECT count(*)::int FROM d
                    """)
                        or 0
                    )
                    deleted_cancelled = (
                        await conn.fetchval("""
                        WITH d AS (DELETE FROM tasks WHERE status = 'cancelled' RETURNING id)
                        SELECT count(*)::int FROM d
                    """)
                        or 0
                    )
                    if deleted_completed or deleted_cancelled:
                        logger.info(
                            "  🗑️ Tasks cleanup: %s old completed, %s cancelled deleted.",
                            deleted_completed,
                            deleted_cancelled,
                        )
                    if rd:
                        await rd.set(cleanup_key, datetime.now().isoformat())
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.warning("Tasks cleanup error: %s", exc)

            await conn.close()
            logger.info("[ENHANCED_ORCHESTRATOR] cycle finished successfully.")
        except Exception as cycle_exc:  # pylint: disable=broad-exception-caught
            logger.error("[ENHANCED_ORCHESTRATOR] cycle exception: %s", cycle_exc)
            logger.error(traceback.format_exc())
            try:
                await conn.close()
            except Exception:
                pass
            raise


async def _health_monitor_loop(interval_seconds: int = 300):
    """
    Фоновый цикл живого организма: периодически проверяем Ollama/MLX и при недоступности
    запрашиваем восстановление на хосте (RECOVERY_WEBHOOK_URL).
    """
    if not RECOVERY_WEBHOOK_URL:
        return
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            ollama_ok, mlx_ok = await check_llm_services_health()
            if not ollama_ok or not mlx_ok:
                logger.warning(
                    "[ENHANCED_ORCHESTRATOR] Health monitor: ollama=%s mlx=%s — запрос восстановления",
                    ollama_ok,
                    mlx_ok,
                )
                await trigger_recovery_webhook(ollama_down=not ollama_ok, mlx_down=not mlx_ok)
        except asyncio.CancelledError:
            break
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.debug("Health monitor error: %s", e)


async def run_continuous(interval_seconds: int = 60, quick_poll_seconds: int = 30):
    """
    Бесконечный цикл: оркестратор «все время слушает» — периодически запускает цикл оркестрации.
    После каждого цикла спит interval_seconds; если есть нераспределённые задачи — следующий цикл
    через quick_poll_seconds (реагируем быстрее при появлении работы).
    Живой организм: запускается фоновый монитор Ollama/MLX с запросом восстановления при сбое.
    """
    logger.info(
        "[ENHANCED_ORCHESTRATOR] continuous mode: interval=%ss, quick_poll=%ss",
        interval_seconds,
        quick_poll_seconds,
    )
    health_monitor_interval = int(os.getenv("ORCHESTRATOR_HEALTH_MONITOR_INTERVAL", "300"))
    health_task = None
    if RECOVERY_WEBHOOK_URL:
        health_task = asyncio.create_task(
            _health_monitor_loop(interval_seconds=health_monitor_interval)
        )
        logger.info(
            "[ENHANCED_ORCHESTRATOR] Health monitor started (interval=%ss, webhook=%s)",
            health_monitor_interval,
            RECOVERY_WEBHOOK_URL[:50] + "..."
            if len(RECOVERY_WEBHOOK_URL) > 50
            else RECOVERY_WEBHOOK_URL,
        )
    try:
        while True:
            try:
                await run_enhanced_orchestration_cycle()
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("[ENHANCED_ORCHESTRATOR] cycle error: %s", e)
                logger.error(traceback.format_exc())
            # Решаем, сколько спать: если есть нераспределённые задачи — короткий сон
            sleep_sec = interval_seconds
            if ASYNCPG_AVAILABLE and interval_seconds > quick_poll_seconds:
                try:
                    conn = await asyncpg.connect(DB_URL)
                    try:
                        unassigned = await conn.fetchval(
                            "SELECT COUNT(*) FROM tasks WHERE assignee_expert_id IS NULL AND status = 'pending'"
                        )
                        if unassigned and unassigned > 0:
                            sleep_sec = quick_poll_seconds
                            logger.info(
                                "[ENHANCED_ORCHESTRATOR] %s unassigned tasks, next cycle in %ss",
                                unassigned,
                                sleep_sec,
                            )
                    finally:
                        await conn.close()
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.debug("Quick poll failed: %s, using full interval", e)
            await asyncio.sleep(sleep_sec)
    finally:
        if health_task and not health_task.done():
            health_task.cancel()
            try:
                await health_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    import argparse

    # [SINGULARITY 21.30] PID Lock Enforcement
    lock = PIDLock()
    if not lock.acquire():
        print(f"⚠️ [ORCHESTRATOR] Process already running. Exiting to prevent duplication.")
        sys.exit(0)

    try:
        parser = argparse.ArgumentParser(description="Enhanced Orchestrator")
        # ... (остальной код argparse)
    finally:
        lock.release()
    parser.add_argument("--prompt", nargs="*", help="Single prompt (for Telegram gateway)")
    parser.add_argument(
        "--continuous", action="store_true", help="Run forever: listen and orchestrate on interval"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between cycles in continuous mode (default: 60)",
    )
    parser.add_argument(
        "--quick-poll",
        type=int,
        default=30,
        help="Seconds to next cycle when unassigned tasks exist (default: 30)",
    )
    args = parser.parse_args()

    # Поддержка прямого вызова через аргументы (для Telegram шлюза)
    if args.prompt:
        PROMPT_TEXT_INPUT = " ".join(args.prompt)
        try:
            main_result = asyncio.run(run_cursor_agent(PROMPT_TEXT_INPUT))
        except RuntimeError:
            main_result = run_smart_agent_sync(
                PROMPT_TEXT_INPUT, expert_name="Виктория", category="orchestrator"
            )
        if main_result:
            print(main_result)
        else:
            print("❌ Ошибка генерации ответа в ядре.")
    elif args.continuous:
        asyncio.run(
            run_continuous(interval_seconds=args.interval, quick_poll_seconds=args.quick_poll)
        )
    else:
        asyncio.run(run_enhanced_orchestration_cycle())
