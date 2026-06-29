"""
[KNOWLEDGE OS] Enhanced Orchestrator v3.1.
Enhanced Orchestrator with Task Prioritization and Workload Balancing.
Part of the ATRA Singularity framework.
"""

import asyncio
import fcntl  # [SINGULARITY 21.30] Для блокировки файлов на Unix-системах
import getpass
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from orchestrator_helpers import has_execution_backlog

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = None

_orch_active_cycles = _orch_tasks_assigned = _orch_task_duration = _orch_errors = (
    _orch_tasks_per_phase
) = None
_orch_cycles_total = None
_orch_dynamic_spawn_attempts = _orch_dynamic_spawn_success = _orch_dynamic_fallbacks = None
_orch_dynamic_stuck = None
CONTRACT_ROLLOUT_MODE = os.getenv("ORCHESTRATOR_CONTRACT_ROLLOUT_MODE", "shadow").strip().lower()
CONTRACT_CANARY_ENFORCE_PERCENT = int(os.getenv("ORCHESTRATOR_CONTRACT_CANARY_PERCENT", "20"))
ROLLOUT_KPI_WINDOW_MIN = int(os.getenv("ORCHESTRATOR_ROLLOUT_KPI_WINDOW_MIN", "10"))
ROLLOUT_KPI_MIN_COMPLETED = int(os.getenv("ORCHESTRATOR_ROLLOUT_KPI_MIN_COMPLETED", "2"))
ROLLOUT_KPI_MAX_FAILURE_RATE = float(os.getenv("ORCHESTRATOR_ROLLOUT_KPI_MAX_FAILURE_RATE", "0.20"))
ROLLOUT_KPI_MAX_PENDING = int(os.getenv("ORCHESTRATOR_ROLLOUT_KPI_MAX_PENDING", "20"))
_corp_refresh_task: Optional[asyncio.Task] = None
_corp_refresh_last_start_ts: float = 0.0
_corp_refresh_lock = asyncio.Lock()
_corp_refresh_min_interval_sec = int(
    os.getenv("CORPORATION_KNOWLEDGE_MIN_REFRESH_INTERVAL_SEC", "900")
)

if _PROMETHEUS_AVAILABLE and Gauge is not None:
    _orch_tasks_assigned = Counter(
        "orchestrator_tasks_assigned_total",
        "Total tasks assigned by orchestrator",
        ["phase", "status"],
    )
    _orch_task_duration = Histogram(
        "orchestrator_task_duration_seconds",
        "Time to assign single task",
        ["phase"],
    )
    _orch_active_cycles = Gauge(
        "orchestrator_active_cycles",
        "Number of active orchestration cycles",
    )
    _orch_errors = Counter(
        "orchestrator_errors_total",
        "Total orchestrator errors",
        ["phase", "error_type"],
    )
    _orch_tasks_per_phase = Counter(
        "orchestrator_tasks_per_phase_total",
        "Tasks processed per orchestration phase",
        ["phase"],
    )
    _orch_cycles_total = Counter(
        "orchestrator_cycles_total",
        "Total orchestrator cycle outcomes",
        ["status"],
    )
    _orch_dynamic_spawn_attempts = Counter(
        "orchestrator_dynamic_spawn_attempts_total",
        "Dynamic worker spawn attempts",
        ["result"],
    )
    _orch_dynamic_spawn_success = Counter(
        "orchestrator_dynamic_spawn_success_total",
        "Dynamic worker spawn success",
        ["slot"],
    )
    _orch_dynamic_fallbacks = Counter(
        "orchestrator_dynamic_fallback_total",
        "Fallbacks when dynamic worker unavailable",
        ["reason"],
    )
    _orch_dynamic_stuck = Counter(
        "orchestrator_stuck_agent_run_total",
        "Tasks at risk of stuck execution due to non-live experts",
        ["reason"],
    )
    _orch_registry = CollectorRegistry()
    _orch_registry.register(_orch_tasks_assigned)
    _orch_registry.register(_orch_task_duration)
    _orch_registry.register(_orch_active_cycles)
    _orch_registry.register(_orch_errors)
    _orch_registry.register(_orch_tasks_per_phase)
    _orch_registry.register(_orch_cycles_total)
    _orch_registry.register(_orch_dynamic_spawn_attempts)
    _orch_registry.register(_orch_dynamic_spawn_success)
    _orch_registry.register(_orch_dynamic_fallbacks)
    _orch_registry.register(_orch_dynamic_stuck)


def _record_orch_metric(metric_type, name, *args, **kwargs):
    """Record a metric, safely wrapped in try/except."""
    if not _PROMETHEUS_AVAILABLE:
        return
    try:
        if metric_type == "counter":
            name.labels(*args, **kwargs).inc()
        elif metric_type == "histogram":
            name.labels(*args, **kwargs).observe(kwargs.get("value", 0))
        elif metric_type == "gauge_inc":
            name.inc(*args, **kwargs)
        elif metric_type == "gauge_dec":
            name.dec(*args, **kwargs)
    except Exception:
        pass


def _is_canary_enforce(task_id: str, percent: int) -> bool:
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    digest = hashlib.sha1(task_id.encode("utf-8", errors="ignore")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < percent


async def _resolve_contract_mode(rd=None) -> str:
    mode = CONTRACT_ROLLOUT_MODE
    if rd is not None:
        try:
            redis_mode = await rd.get("system:contract_rollout_mode")
            if redis_mode:
                mode = str(redis_mode).strip().lower()
        except Exception:
            pass
    if mode not in {"off", "shadow", "enforce", "auto"}:
        mode = "shadow"
    if mode == "auto" and rd is not None:
        try:
            enforce_flag = await rd.get("system:contract_enforce")
            return (
                "enforce" if str(enforce_flag).lower() in ("1", "true", "yes", "on") else "shadow"
            )
        except Exception:
            return "shadow"
    return mode


async def _compute_rollout_kpis(conn) -> Dict[str, float]:
    row = await conn.fetchrow(
        """
        SELECT
            count(*) FILTER (WHERE status = 'completed' AND updated_at > NOW() - ($1 || ' minutes')::interval) AS completed_10m,
            count(*) FILTER (WHERE status = 'failed' AND updated_at > NOW() - ($1 || ' minutes')::interval) AS failed_10m,
            count(*) FILTER (WHERE status = 'in_progress') AS in_progress_now,
            count(*) FILTER (WHERE status = 'pending') AS pending_now
        FROM tasks
    """,
        str(ROLLOUT_KPI_WINDOW_MIN),
    )
    completed = int((row or {}).get("completed_10m") or 0)
    failed = int((row or {}).get("failed_10m") or 0)
    denom = completed + failed
    failure_rate = (failed / denom) if denom > 0 else 0.0
    return {
        "completed_10m": completed,
        "failed_10m": failed,
        "in_progress_now": int((row or {}).get("in_progress_now") or 0),
        "pending_now": int((row or {}).get("pending_now") or 0),
        "failure_rate": failure_rate,
    }


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
        except OSError:
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

[SINGULARITY 26.2] SWARM MODE: Если задача сложная, предложи цепочку экспертов (handoff chain).
Для каждого шага укажи: subtask, department, expert_role, priority и ОЖИДАЕМЫЙ КОНТРАКТ (JSON schema для результата).

Задача:
{goal[:2000]}

Верни ТОЛЬКО валидный JSON:
{{
  "task_description": "кратко",
  "is_swarm": true,
  "subtasks": [
    {{
      "subtask": "промпт для сотрудника",
      "department": "отдел",
      "expert_role": "имя/роль",
      "priority": "medium",
      "contract": {{"type": "object", "properties": {{"code": {{"type": "string"}}}}}}
    }}
  ]
}}"""
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
    from explicit_handoffs import get_handoff_manager
    from swarm_orchestrator import SwarmOrchestrator
except ImportError:

    class SwarmOrchestrator:
        """Fallback for SwarmOrchestrator."""

        async def handle_critical_failures(self):
            pass

    def get_handoff_manager():
        return None


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
_DISTILLER_SINGLETON = None
_SYNTHETIC_GENERATOR_SINGLETON = None
_TRAINING_PIPELINE_SINGLETON = None
_SWARM_ORCHESTRATOR_SINGLETON = None
_META_ARCHITECT_SINGLETON = None
_EVOLUTION_MONITOR_SINGLETON = None
_CURIOSITY_ENGINE_SINGLETON = None
_MEMORY_CONSOLIDATOR_SINGLETON = None
_MULTI_CLUSTER_BRIDGE_SINGLETON = None
_SERVER_KNOWLEDGE_SYNC_SINGLETON = None
_STRATEGY_SESSION_MANAGER_SINGLETON = None
_KNOWLEDGE_ARCHIVER_SINGLETON = None


def _get_distiller():
    global _DISTILLER_SINGLETON
    if _DISTILLER_SINGLETON is None:
        _DISTILLER_SINGLETON = KnowledgeDistiller()
    return _DISTILLER_SINGLETON


def _get_synthetic_generator():
    global _SYNTHETIC_GENERATOR_SINGLETON
    if _SYNTHETIC_GENERATOR_SINGLETON is None:
        _SYNTHETIC_GENERATOR_SINGLETON = SyntheticKnowledgeGenerator()
    return _SYNTHETIC_GENERATOR_SINGLETON


def _get_training_pipeline():
    global _TRAINING_PIPELINE_SINGLETON
    if _TRAINING_PIPELINE_SINGLETON is None:
        _TRAINING_PIPELINE_SINGLETON = LocalTrainingPipeline()
    return _TRAINING_PIPELINE_SINGLETON


def _get_swarm_orchestrator():
    global _SWARM_ORCHESTRATOR_SINGLETON
    if _SWARM_ORCHESTRATOR_SINGLETON is None:
        _SWARM_ORCHESTRATOR_SINGLETON = SwarmOrchestrator()
    return _SWARM_ORCHESTRATOR_SINGLETON


def _get_meta_architect():
    global _META_ARCHITECT_SINGLETON
    if _META_ARCHITECT_SINGLETON is None:
        _META_ARCHITECT_SINGLETON = MetaArchitect()
    return _META_ARCHITECT_SINGLETON


def _get_evolution_monitor():
    global _EVOLUTION_MONITOR_SINGLETON
    if _EVOLUTION_MONITOR_SINGLETON is None:
        _EVOLUTION_MONITOR_SINGLETON = SingularityEvolutionMonitor()
    return _EVOLUTION_MONITOR_SINGLETON


def _get_curiosity_engine():
    global _CURIOSITY_ENGINE_SINGLETON
    if _CURIOSITY_ENGINE_SINGLETON is None:
        _CURIOSITY_ENGINE_SINGLETON = CuriosityEngine()
    return _CURIOSITY_ENGINE_SINGLETON


def _get_memory_consolidator():
    global _MEMORY_CONSOLIDATOR_SINGLETON
    if _MEMORY_CONSOLIDATOR_SINGLETON is None:
        _MEMORY_CONSOLIDATOR_SINGLETON = MemoryConsolidator()
    return _MEMORY_CONSOLIDATOR_SINGLETON


def _get_multi_cluster_bridge():
    global _MULTI_CLUSTER_BRIDGE_SINGLETON
    if not MultiClusterBridge:
        return None
    if _MULTI_CLUSTER_BRIDGE_SINGLETON is None:
        _MULTI_CLUSTER_BRIDGE_SINGLETON = MultiClusterBridge()
    return _MULTI_CLUSTER_BRIDGE_SINGLETON


def _get_server_knowledge_sync():
    global _SERVER_KNOWLEDGE_SYNC_SINGLETON
    if not ServerKnowledgeSync:
        return None
    if _SERVER_KNOWLEDGE_SYNC_SINGLETON is None:
        _SERVER_KNOWLEDGE_SYNC_SINGLETON = ServerKnowledgeSync()
    return _SERVER_KNOWLEDGE_SYNC_SINGLETON


def _get_knowledge_archiver():
    global _STRATEGY_SESSION_MANAGER_SINGLETON, _KNOWLEDGE_ARCHIVER_SINGLETON
    if _KNOWLEDGE_ARCHIVER_SINGLETON is not None:
        return _KNOWLEDGE_ARCHIVER_SINGLETON
    from knowledge_archiver import KnowledgeArchiver
    from strategy_session_manager import StrategySessionManager

    if _STRATEGY_SESSION_MANAGER_SINGLETON is None:
        _STRATEGY_SESSION_MANAGER_SINGLETON = StrategySessionManager()
    _KNOWLEDGE_ARCHIVER_SINGLETON = KnowledgeArchiver(_STRATEGY_SESSION_MANAGER_SINGLETON)
    return _KNOWLEDGE_ARCHIVER_SINGLETON


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
    os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:6432/knowledge_os"
)
DB_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ACTIVE_EXECUTOR_EXPERTS = {
    item.strip()
    for item in os.getenv(
        "ORCHESTRATOR_ACTIVE_EXPERTS",
        "Виктория,Анна,Роман",
    ).split(",")
    if item.strip()
}
PERMANENT_EXECUTOR_EXPERTS = {
    item.strip()
    for item in os.getenv(
        "ORCHESTRATOR_PERMANENT_EXPERTS",
        "Виктория,Анна,Роман",
    ).split(",")
    if item.strip()
}
DYNAMIC_WORKERS_ENABLED = os.getenv("ORCHESTRATOR_DYNAMIC_WORKERS_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)
DYNAMIC_WORKER_SLOTS = [
    item.strip()
    for item in os.getenv(
        "ORCHESTRATOR_DYNAMIC_WORKER_SLOTS",
        "expert-worker-dynamic-1,expert-worker-dynamic-2",
    ).split(",")
    if item.strip()
]
DYNAMIC_WORKER_ALLOWED_EXPERTS = {
    item.strip()
    for item in os.getenv("ORCHESTRATOR_DYNAMIC_ALLOWED_EXPERTS", "").split(",")
    if item.strip()
}
DYNAMIC_WORKER_WARMUP_SEC = max(15, int(os.getenv("ORCHESTRATOR_DYNAMIC_WARMUP_SEC", "45")))
DYNAMIC_WORKER_IDLE_TTL_SEC = max(300, int(os.getenv("ORCHESTRATOR_DYNAMIC_IDLE_TTL_SEC", "1800")))
DYNAMIC_WORKER_STATE_KEY = os.getenv(
    "ORCHESTRATOR_DYNAMIC_WORKER_STATE_KEY", "runtime:dynamic_worker_slots"
)
DYNAMIC_COMPOSE_FILES = [
    item.strip()
    for item in os.getenv(
        "ORCHESTRATOR_DYNAMIC_COMPOSE_FILES",
        "/app/knowledge_os/docker-compose.yml,/app/knowledge_os/docker-compose.agents.yml",
    ).split(",")
    if item.strip()
]
DYNAMIC_COMPOSE_WORKDIR = os.getenv("ORCHESTRATOR_DYNAMIC_COMPOSE_WORKDIR", "/app/knowledge_os")
RUNTIME_WORKER_HEARTBEAT_KEY = os.getenv(
    "RUNTIME_WORKER_HEARTBEAT_KEY", "runtime:expert_heartbeats"
)
RUNTIME_WORKER_HEARTBEAT_TTL_SEC = int(os.getenv("RUNTIME_WORKER_HEARTBEAT_TTL_SEC", "90"))
RUNTIME_WORKER_CACHE_TTL_SEC = int(os.getenv("ORCHESTRATOR_RUNTIME_CACHE_TTL_SEC", "10"))
REQUIRE_RUNTIME_HEARTBEAT = os.getenv("ORCHESTRATOR_REQUIRE_RUNTIME_HEARTBEAT", "true").lower() in (
    "true",
    "1",
    "yes",
)
_runtime_live_experts_cache = set()
_runtime_live_experts_cache_at = 0.0

# Приоритеты задач
PRIORITY_WEIGHTS = {
    "urgent": 100,
    "high": 50,
    "medium": 25,
    "low": 10,
}


async def _get_runtime_live_experts(force_refresh: bool = False):
    """Get live experts from runtime worker heartbeat registry."""
    global _runtime_live_experts_cache, _runtime_live_experts_cache_at

    now = time.time()
    if (
        not force_refresh
        and _runtime_live_experts_cache_at > 0
        and (now - _runtime_live_experts_cache_at) < RUNTIME_WORKER_CACHE_TTL_SEC
    ):
        return _runtime_live_experts_cache

    live = set()
    stale = []
    if REDIS_AVAILABLE:
        rd = None
        try:
            rd = await redis.from_url(REDIS_URL, decode_responses=True)
            entries = await rd.hgetall(RUNTIME_WORKER_HEARTBEAT_KEY)
            for expert_name, raw in entries.items():
                ts = 0
                try:
                    payload = json.loads(raw)
                    ts = int(payload.get("ts", 0))
                except Exception:
                    try:
                        ts = int(raw)
                    except Exception:
                        ts = 0
                if ts > 0 and (now - ts) <= RUNTIME_WORKER_HEARTBEAT_TTL_SEC:
                    live.add(expert_name)
                else:
                    stale.append(expert_name)
            if stale:
                await rd.hdel(RUNTIME_WORKER_HEARTBEAT_KEY, *stale)
        except Exception as hb_err:
            logger.warning("[RUNTIME-REGISTRY] heartbeat registry unavailable: %s", hb_err)
        finally:
            if rd is not None:
                try:
                    await rd.aclose()
                except Exception:
                    pass

    _runtime_live_experts_cache = live
    _runtime_live_experts_cache_at = now
    return live


def _dynamic_slot_env_var(slot_name: str) -> str:
    suffix = slot_name.rsplit("-", 1)[-1]
    return f"DYNAMIC_EXPERT_NAME_SLOT{suffix}"


async def _dynamic_state_get(rd) -> Dict[str, Dict]:
    try:
        raw = await rd.get(DYNAMIC_WORKER_STATE_KEY)
        if not raw:
            return {}
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


async def _dynamic_state_set(rd, state: Dict[str, Dict]) -> None:
    try:
        await rd.set(DYNAMIC_WORKER_STATE_KEY, json.dumps(state, ensure_ascii=False))
    except Exception:
        pass


async def _reserve_dynamic_slot(expert_name: str) -> Optional[str]:
    if not DYNAMIC_WORKERS_ENABLED or not DYNAMIC_WORKER_SLOTS:
        return None
    if expert_name in PERMANENT_EXECUTOR_EXPERTS:
        return None
    if DYNAMIC_WORKER_ALLOWED_EXPERTS and expert_name not in DYNAMIC_WORKER_ALLOWED_EXPERTS:
        return None
    if not REDIS_AVAILABLE:
        return None

    rd = None
    try:
        rd = await redis.from_url(REDIS_URL, decode_responses=True)
        state = await _dynamic_state_get(rd)
        now_ts = int(time.time())
        live_experts = await _get_runtime_live_experts(force_refresh=True)

        for slot, info in state.items():
            if str((info or {}).get("expert_name", "")).strip() == expert_name:
                return slot

        for slot in DYNAMIC_WORKER_SLOTS:
            info = state.get(slot) or {}
            slot_expert = str(info.get("expert_name", "")).strip()
            if not slot_expert or slot_expert not in live_experts:
                state[slot] = {
                    "expert_name": expert_name,
                    "reserved_at_ts": now_ts,
                    "last_activity_ts": now_ts,
                }
                await _dynamic_state_set(rd, state)
                return slot
    except Exception as reserve_err:
        logger.warning("[DYNAMIC-WORKERS] reserve failed for %s: %s", expert_name, reserve_err)
    finally:
        if rd is not None:
            try:
                await rd.aclose()
            except Exception:
                pass
    return None


async def _release_dynamic_slot(slot_name: str) -> None:
    if not REDIS_AVAILABLE:
        return
    rd = None
    try:
        rd = await redis.from_url(REDIS_URL, decode_responses=True)
        state = await _dynamic_state_get(rd)
        if slot_name in state:
            state.pop(slot_name, None)
            await _dynamic_state_set(rd, state)
    except Exception:
        pass
    finally:
        if rd is not None:
            try:
                await rd.aclose()
            except Exception:
                pass


def _compose_cmd_for_slot(slot_name: str) -> List[str]:
    cmd = ["docker", "compose"]
    for compose_file in DYNAMIC_COMPOSE_FILES:
        cmd.extend(["-f", compose_file])
    cmd.extend(["up", "-d", "--no-deps", "--force-recreate", slot_name])
    return cmd


def _compose_stop_cmd(slot_name: str) -> List[str]:
    cmd = ["docker", "compose"]
    for compose_file in DYNAMIC_COMPOSE_FILES:
        cmd.extend(["-f", compose_file])
    cmd.extend(["stop", slot_name])
    return cmd


async def _spawn_dynamic_worker(expert_name: str) -> bool:
    if not DYNAMIC_WORKERS_ENABLED:
        return False
    live = await _get_runtime_live_experts(force_refresh=True)
    if expert_name in live:
        return True

    slot = await _reserve_dynamic_slot(expert_name)
    if not slot:
        _record_orch_metric("counter", _orch_dynamic_stuck, reason="no_slot_available")
        return False

    _record_orch_metric("counter", _orch_dynamic_spawn_attempts, result="started")
    env = os.environ.copy()
    env[_dynamic_slot_env_var(slot)] = expert_name

    try:

        def _run_compose_up():
            return subprocess.run(
                _compose_cmd_for_slot(slot),
                cwd=DYNAMIC_COMPOSE_WORKDIR,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        proc = await asyncio.to_thread(_run_compose_up)
        compose_stdout = (proc.stdout or "").strip()
        compose_stderr = (proc.stderr or "").strip()
        nonzero_rc = proc.returncode != 0
        if proc.returncode != 0:
            logger.warning(
                "[DYNAMIC-WORKERS] compose returned non-zero for %s slot=%s rc=%s stdout=%s stderr=%s",
                expert_name,
                slot,
                proc.returncode,
                compose_stdout[:300],
                compose_stderr[:300],
            )

        deadline = time.time() + DYNAMIC_WORKER_WARMUP_SEC
        while time.time() < deadline:
            await asyncio.sleep(3)
            live = await _get_runtime_live_experts(force_refresh=True)
            if expert_name in live:
                _record_orch_metric("counter", _orch_dynamic_spawn_success, slot=slot)
                _record_orch_metric(
                    "counter",
                    _orch_dynamic_spawn_attempts,
                    result=("success_after_nonzero_rc" if nonzero_rc else "success"),
                )
                return True

        if nonzero_rc:
            _record_orch_metric("counter", _orch_dynamic_spawn_attempts, result="failed_nonzero_rc")
            await _release_dynamic_slot(slot)
            return False

        logger.warning(
            "[DYNAMIC-WORKERS] warmup timeout for %s in slot %s (%ss)",
            expert_name,
            slot,
            DYNAMIC_WORKER_WARMUP_SEC,
        )
        _record_orch_metric("counter", _orch_dynamic_spawn_attempts, result="timeout")
        await _release_dynamic_slot(slot)
        return False
    except Exception as spawn_err:
        logger.warning("[DYNAMIC-WORKERS] exception for %s: %s", expert_name, spawn_err)
        _record_orch_metric("counter", _orch_dynamic_spawn_attempts, result="error")
        await _release_dynamic_slot(slot)
        return False


async def _touch_dynamic_worker_activity(expert_name: str) -> None:
    if not REDIS_AVAILABLE or not expert_name:
        return
    rd = None
    try:
        rd = await redis.from_url(REDIS_URL, decode_responses=True)
        state = await _dynamic_state_get(rd)
        now_ts = int(time.time())
        changed = False
        for slot, info in state.items():
            if str((info or {}).get("expert_name", "")).strip() == expert_name:
                state[slot]["last_activity_ts"] = now_ts
                changed = True
        if changed:
            await _dynamic_state_set(rd, state)
    except Exception:
        pass
    finally:
        if rd is not None:
            try:
                await rd.aclose()
            except Exception:
                pass


async def _scale_down_idle_dynamic_workers(conn) -> int:
    if not DYNAMIC_WORKERS_ENABLED or not REDIS_AVAILABLE:
        return 0

    rd = None
    stopped = 0
    try:
        rd = await redis.from_url(REDIS_URL, decode_responses=True)
        state = await _dynamic_state_get(rd)
        if not state:
            return 0
        now_ts = int(time.time())
        live = await _get_runtime_live_experts(force_refresh=True)
        dirty = False

        for slot, info in list(state.items()):
            expert_name = str((info or {}).get("expert_name", "")).strip()
            if not expert_name:
                state.pop(slot, None)
                dirty = True
                continue
            if expert_name in PERMANENT_EXECUTOR_EXPERTS:
                state.pop(slot, None)
                dirty = True
                continue

            expert_id = await conn.fetchval("SELECT id FROM experts WHERE name = $1", expert_name)
            active_tasks = 0
            if expert_id:
                active_tasks = (
                    await conn.fetchval(
                        """
                        SELECT COUNT(*)
                        FROM tasks
                        WHERE assignee_expert_id = $1
                          AND status IN ('pending', 'in_progress')
                        """,
                        expert_id,
                    )
                    or 0
                )
            if active_tasks > 0:
                info["last_activity_ts"] = now_ts
                state[slot] = info
                dirty = True
                continue

            last_activity_ts = int(
                info.get("last_activity_ts") or info.get("reserved_at_ts") or now_ts
            )
            idle_sec = now_ts - last_activity_ts
            if idle_sec < DYNAMIC_WORKER_IDLE_TTL_SEC:
                continue

            if expert_name in live:

                def _run_compose_stop():
                    return subprocess.run(
                        _compose_stop_cmd(slot),
                        cwd=DYNAMIC_COMPOSE_WORKDIR,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                proc = await asyncio.to_thread(_run_compose_stop)
                if proc.returncode != 0:
                    logger.warning(
                        "[DYNAMIC-WORKERS] failed stop slot=%s expert=%s rc=%s stderr=%s",
                        slot,
                        expert_name,
                        proc.returncode,
                        (proc.stderr or "").strip()[:300],
                    )
                    continue
            state.pop(slot, None)
            dirty = True
            stopped += 1
            logger.info(
                "[DYNAMIC-WORKERS] scaled down slot=%s expert=%s idle=%ss",
                slot,
                expert_name,
                idle_sec,
            )

        if dirty:
            await _dynamic_state_set(rd, state)
    except Exception as scale_err:
        logger.warning("[DYNAMIC-WORKERS] scale-down check failed: %s", scale_err)
    finally:
        if rd is not None:
            try:
                await rd.aclose()
            except Exception:
                pass
    return stopped


async def _filter_active_executor_candidates(candidates):
    """Keep only explicitly active runtime executors when configured."""
    if not candidates:
        return []

    candidate_names = [str(c.get("name") or "").strip() for c in candidates if c.get("name")]
    if not candidate_names:
        return []

    allowed_names = set(ACTIVE_EXECUTOR_EXPERTS or set(candidate_names))
    if DYNAMIC_WORKERS_ENABLED:
        allowed_names |= {
            name
            for name in candidate_names
            if name not in PERMANENT_EXECUTOR_EXPERTS
            and (not DYNAMIC_WORKER_ALLOWED_EXPERTS or name in DYNAMIC_WORKER_ALLOWED_EXPERTS)
        }

    configured = [c for c in candidates if c.get("name") in allowed_names]
    if not configured:
        return []

    live_experts = await _get_runtime_live_experts()
    live_configured = [c for c in configured if c.get("name") in live_experts]
    if live_configured:
        return live_configured

    if DYNAMIC_WORKERS_ENABLED:
        dynamic_candidates = [
            c
            for c in configured
            if c.get("name") not in PERMANENT_EXECUTOR_EXPERTS and c.get("name") not in live_experts
        ]
        if dynamic_candidates:
            spawned = False
            for candidate in dynamic_candidates[:2]:
                expert_name = str(candidate.get("name") or "").strip()
                if not expert_name:
                    continue
                if await _spawn_dynamic_worker(expert_name):
                    spawned = True
                    break
            live_experts = await _get_runtime_live_experts(force_refresh=True)
            live_configured = [c for c in configured if c.get("name") in live_experts]
            if live_configured:
                return live_configured
            if spawned:
                _record_orch_metric(
                    "counter", _orch_dynamic_fallbacks, reason="spawned_but_not_live"
                )

    permanent_live = [
        c
        for c in configured
        if c.get("name") in live_experts and c.get("name") in PERMANENT_EXECUTOR_EXPERTS
    ]
    if permanent_live:
        _record_orch_metric("counter", _orch_dynamic_fallbacks, reason="fallback_to_permanent")
        return permanent_live

    if REQUIRE_RUNTIME_HEARTBEAT:
        logger.warning(
            "[RUNTIME-REGISTRY] No live experts found in '%s'; skipping assignment until heartbeats appear.",
            RUNTIME_WORKER_HEARTBEAT_KEY,
        )
        _record_orch_metric("counter", _orch_dynamic_stuck, reason="no_live_experts")
        return []
    return configured


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
    # Fetch task details from DB
    task = await conn.fetchrow(
        "SELECT id, title, description, metadata FROM tasks WHERE id = $1", task_id
    )
    if not task:
        logger.warning(f"Task {task_id} not found for assignment")
        return None

    task_dict = dict(task)

    # assignee_hint из metadata (например, "Frontend/Performance", "QA")
    assignee_hint = None
    preferred_target_expert = None
    task_meta = task_dict.get("metadata") or {}
    if isinstance(task_meta, dict):
        assignee_hint = task_meta.get("assignee_hint")
        preferred_target_expert = task_meta.get("target_expert")
    if not required_role and assignee_hint:
        required_role = str(assignee_hint)

    # Hard preference: if task carries target_expert, honor it first (when active/live).
    if preferred_target_expert:
        preferred_name = str(preferred_target_expert).strip()
        if preferred_name:
            preferred_candidates = await conn.fetch(
                """
                SELECT id, name, role, department
                FROM experts
                WHERE is_active = true
                  AND name = $1
                LIMIT 1
            """,
                preferred_name,
            )
            preferred_candidates = await _filter_active_executor_candidates(preferred_candidates)
            if preferred_candidates:
                preferred = preferred_candidates[0]
                preferred_source = "ollama"
                if task_dict.get("metadata") and isinstance(task_dict.get("metadata"), dict):
                    if task_dict["metadata"].get("preferred_source"):
                        preferred_source = str(task_dict["metadata"]["preferred_source"]).lower()
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
                    preferred["id"],
                    task_id,
                    json.dumps(meta_extra),
                )
                logger.info(
                    "✅ Task %s pinned to target_expert=%s (source=%s)",
                    task_id,
                    preferred_name,
                    preferred_source,
                )
                await _touch_dynamic_worker_activity(preferred_name)
                return preferred["id"]

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
    candidates = await _filter_active_executor_candidates(candidates)

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
        # [SINGULARITY 26.10] Smart model selection - по отделу (упрощено для стабильности)
        dept = (best_expert.get("department") or "").lower()
        mlx_depts = ("ml", "backend", "r&d", "performance", "trading", "quant", "devops", "sre")
        preferred_source = "mlx" if any(d in dept for d in mlx_depts) else "ollama"

        # Если создатель уже указал preferred_source в metadata — уважаем
        if task_dict.get("metadata") and isinstance(task_dict.get("metadata"), dict):
            if task_dict["metadata"].get("preferred_source"):
                preferred_source = str(task_dict["metadata"]["preferred_source"]).lower()
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
        await _touch_dynamic_worker_activity(str(best_expert["name"]))
        return best_expert["id"]

    return None


async def dispatch_pending_assignments(conn, limit: int = 50) -> int:
    """
    Publish pending assigned tasks into expert stream.
    Guarded by metadata timestamp to avoid hot-loop duplicates.
    """
    if not REDIS_AVAILABLE:
        return 0
    max_redispatch_attempts = int(os.getenv("ORCHESTRATOR_MAX_REDISPATCH_ATTEMPTS", "6"))
    dispatch_retry_interval_min = int(os.getenv("ORCHESTRATOR_DISPATCH_RETRY_INTERVAL_MIN", "2"))

    rows = await conn.fetch(
        """
        SELECT t.id, t.title, t.description, t.metadata, e.name AS expert_name
        FROM tasks t
        JOIN experts e ON e.id = t.assignee_expert_id
        WHERE t.status = 'pending'
          AND t.assignee_expert_id IS NOT NULL
          AND (t.retry_after IS NULL OR t.retry_after <= NOW())
          AND COALESCE((t.metadata->>'dispatch_attempts')::int, 0) < $2
          AND (
            (t.metadata->>'dispatched_to_stream_at') IS NULL
            OR (
                (t.metadata->>'dispatched_to_stream_at')::timestamptz <
                NOW() - make_interval(mins => $3::int)
            )
          )
        ORDER BY t.updated_at ASC
        LIMIT $1
    """,
        limit,
        max_redispatch_attempts,
        dispatch_retry_interval_min,
    )
    if not rows:
        return 0

    rd = None
    dispatched = 0
    try:
        rd = await redis.from_url(REDIS_URL, decode_responses=True)
        rollout_mode = await _resolve_contract_mode(rd)
        for row in rows:
            task_meta = row["metadata"] or {}
            if isinstance(task_meta, str):
                try:
                    task_meta = json.loads(task_meta)
                except Exception:
                    task_meta = {}
            assigned_expert_name = row.get("expert_name")
            raw_target_expert = task_meta.get("target_expert")
            if isinstance(raw_target_expert, str):
                raw_target_expert = raw_target_expert.strip()
            if assigned_expert_name:
                if raw_target_expert and raw_target_expert != assigned_expert_name:
                    task_meta["target_expert_original"] = raw_target_expert
                    if not task_meta.get("subject_expert"):
                        task_meta["subject_expert"] = raw_target_expert
                    task_meta["target_expert"] = assigned_expert_name
                    task_meta["target_expert_normalized"] = True
                    logger.warning(
                        "[TARGET-GUARD] task %s: normalized target_expert '%s' -> '%s'",
                        row["id"],
                        raw_target_expert,
                        assigned_expert_name,
                    )
                elif not raw_target_expert:
                    task_meta["target_expert"] = assigned_expert_name
            task_id = str(row["id"])
            enforce_for_task = rollout_mode == "enforce" or (
                rollout_mode == "shadow"
                and _is_canary_enforce(task_id, CONTRACT_CANARY_ENFORCE_PERCENT)
            )
            payload = {
                "task_id": task_id,
                "expert_name": row["expert_name"],
                "description": row.get("description") or row.get("title") or "",
                "category": "orchestrator_assignment",
                "contract": {
                    "version": "1",
                    "intent": "execute_assigned_task",
                    "output_schema": "expert_response_v1",
                    "risk_level": (task_meta.get("risk_level") or "medium"),
                    "freshness_sla_sec": int(os.getenv("TASK_FRESHNESS_SLA_SEC", "900")),
                    "required_capabilities": task_meta.get("required_capabilities", []),
                    "audit_required": bool(enforce_for_task),
                },
                "metadata": {
                    **task_meta,
                    "orchestrator_dispatch": True,
                    "backend_profile": task_meta.get("backend_profile", "default"),
                    "contract_rollout_mode": rollout_mode,
                    "contract_enforce": bool(enforce_for_task),
                },
            }
            try:
                from app.expert_stream_routing import publish_expert_payload
            except ImportError:
                from expert_stream_routing import publish_expert_payload

            await publish_expert_payload(rd, row["expert_name"], payload)
            try:
                from app.expert_stream_routing import dispatch_stream_for_expert
            except ImportError:
                from expert_stream_routing import dispatch_stream_for_expert

            logger.debug(
                "[DISPATCH] task=%s expert=%s stream=%s",
                task_id,
                assigned_expert_name,
                dispatch_stream_for_expert(assigned_expert_name),
            )
            metadata_patch = {}
            for key in (
                "target_expert",
                "target_expert_original",
                "subject_expert",
                "target_expert_normalized",
            ):
                if key in task_meta:
                    metadata_patch[key] = task_meta.get(key)
            await conn.execute(
                """
                UPDATE tasks
                SET metadata = COALESCE(metadata, '{}'::jsonb) ||
                    $2::jsonb ||
                    jsonb_build_object(
                        'dispatched_to_stream_at', NOW()::text,
                        'dispatch_attempts',
                        COALESCE((metadata->>'dispatch_attempts')::int, 0) + 1
                    )
                WHERE id = $1
            """,
                row["id"],
                json.dumps(metadata_patch, ensure_ascii=False),
            )
            dispatched += 1
    except Exception as dispatch_err:
        logger.warning(
            "[ORCHESTRATOR-DISPATCH] failed to dispatch pending assignments: %s", dispatch_err
        )
    finally:
        if rd is not None:
            try:
                await rd.aclose()
            except Exception:
                pass
    return dispatched


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
    candidates = await _filter_active_executor_candidates(candidates)
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


async def reconcile_nonlive_assignments(conn) -> Tuple[int, int]:
    """Reopen tasks assigned to experts without fresh runtime heartbeat."""
    pending_grace_sec = int(os.getenv("ORCHESTRATOR_NONLIVE_PENDING_GRACE_SEC", "120"))
    live_experts = await _get_runtime_live_experts(force_refresh=True)
    if REQUIRE_RUNTIME_HEARTBEAT and not live_experts:
        return 0, 0

    assigned_rows = await conn.fetch(
        """
        SELECT DISTINCT e.name
        FROM tasks t
        JOIN experts e ON e.id = t.assignee_expert_id
        WHERE t.status IN ('pending', 'in_progress')
    """
    )
    assigned_names = {row["name"] for row in assigned_rows if row.get("name")}
    if ACTIVE_EXECUTOR_EXPERTS:
        assigned_names |= ACTIVE_EXECUTOR_EXPERTS
    nonlive_names = sorted(name for name in assigned_names if name not in live_experts)
    if not nonlive_names:
        return 0, 0

    nonlive_ids = await conn.fetch(
        "SELECT id FROM experts WHERE name = ANY($1::text[])", nonlive_names
    )
    nonlive_uuid_ids = [row["id"] for row in nonlive_ids]
    if not nonlive_uuid_ids:
        return 0, 0

    pending_reopened = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET assignee_expert_id = NULL,
                status = 'pending',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    '{"runtime_reassign_reason":"nonlive_worker_pending"}'::jsonb
            WHERE status = 'pending'
              AND assignee_expert_id = ANY($1::uuid[])
              AND created_at < NOW() - ($2::text || ' seconds')::interval
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        nonlive_uuid_ids,
        str(pending_grace_sec),
    )
    inprogress_reopened = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET assignee_expert_id = NULL,
                status = 'pending',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    '{"runtime_reassign_reason":"nonlive_worker_stale_in_progress"}'::jsonb
            WHERE status = 'in_progress'
              AND assignee_expert_id = ANY($1::uuid[])
              AND updated_at < NOW() - INTERVAL '5 minutes'
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        nonlive_uuid_ids,
    )

    if pending_reopened or inprogress_reopened:
        logger.warning(
            "[RUNTIME-REGISTRY] Reopened tasks from non-live experts=%s pending=%s in_progress=%s",
            ",".join(nonlive_names),
            pending_reopened,
            inprogress_reopened,
        )
    return int(pending_reopened or 0), int(inprogress_reopened or 0)


async def reconcile_stale_in_progress(conn) -> Tuple[int, int]:
    """Requeue stale in_progress tasks with bounded retries and fallback staging."""
    stale_minutes = int(os.getenv("ORCHESTRATOR_STALE_INPROGRESS_MINUTES", "45"))
    max_retries = int(os.getenv("ORCHESTRATOR_STALE_INPROGRESS_MAX_RETRIES", "3"))
    ghost_grace_sec = int(os.getenv("ORCHESTRATOR_GHOST_INPROGRESS_GRACE_SEC", "60"))
    curiosity_ghost_minutes = int(os.getenv("ORCHESTRATOR_CURIOSITY_GHOST_NO_LLM_MINUTES", "15"))
    curiosity_pending_timeout_min = int(
        os.getenv("ORCHESTRATOR_CURIOSITY_PENDING_TIMEOUT_MIN", "120")
    )
    pending_dispatch_timeout_min = int(os.getenv("ORCHESTRATOR_PENDING_DISPATCH_TIMEOUT_MIN", "60"))
    pending_dispatch_cap_reopen_min = int(os.getenv("ORCHESTRATOR_DISPATCH_CAP_REOPEN_MIN", "1"))
    pending_dispatch_max_strikes = int(os.getenv("ORCHESTRATOR_PENDING_DISPATCH_MAX_STRIKES", "3"))
    pending_dispatch_progress_grace_min = int(
        os.getenv("ORCHESTRATOR_PENDING_DISPATCH_PROGRESS_GRACE_MIN", "20")
    )
    autonomous_runtime_cap_min = int(os.getenv("ORCHESTRATOR_AUTONOMOUS_RUNTIME_CAP_MIN", "120"))

    ghost_requeued = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET status = 'pending',
                assignee_expert_id = NULL,
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'stale_requeued_at', NOW()::text,
                        'stale_requeue_reason', 'ghost_in_progress_no_owner'
                    )
            WHERE status = 'in_progress'
              AND updated_at < NOW() - ($1::text || ' seconds')::interval
              AND (
                    assignee_expert_id IS NULL
                    OR COALESCE(metadata->>'processing_worker', '') = ''
                  )
              AND COALESCE(metadata->>'last_llm_call_at', '') = ''
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(ghost_grace_sec),
    )

    curiosity_force_failed = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET status = 'failed',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'auto_fallback_at', NOW()::text,
                        'auto_fallback_reason', 'curiosity_no_llm_progress_timeout',
                        'stale_force_fallback', true
                    )
            WHERE status = 'in_progress'
              AND COALESCE(metadata->>'reason', '') = 'curiosity_engine_starvation'
              AND COALESCE(
                    NULLIF(metadata->>'processing_started_at', '')::timestamptz,
                    updated_at,
                    created_at
                  ) < NOW() - ($1::text || ' minutes')::interval
              AND COALESCE(metadata->>'last_llm_call_at', '') = ''
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(curiosity_ghost_minutes),
    )

    pending_curiosity_force_failed = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET status = 'failed',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'auto_fallback_at', NOW()::text,
                        'auto_fallback_reason', 'pending_curiosity_starvation_timeout',
                        'stale_force_fallback', true
                    )
            WHERE status = 'pending'
              AND COALESCE(metadata->>'reason', '') = 'curiosity_engine_starvation'
              AND COALESCE(
                    NULLIF(metadata->>'manual_requeue_at', '')::timestamptz,
                    updated_at,
                    created_at
                  ) < NOW() - ($1::text || ' minutes')::interval
              AND COALESCE(metadata->>'dispatched_to_stream_at', '') = ''
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(curiosity_pending_timeout_min),
    )
    pending_dispatch_requeued = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET updated_at = NOW(),
                metadata = (
                    COALESCE(metadata, '{}'::jsonb)
                    - 'dispatched_to_stream_at'
                    - 'next_retry_after'
                ) || jsonb_build_object(
                    'pending_dispatch_timeout_count',
                    COALESCE((metadata->>'pending_dispatch_timeout_count')::int, 0) + 1,
                    'pending_dispatch_requeued', true,
                    'pending_dispatch_last_timeout_at', NOW()::text
                )
            WHERE status = 'pending'
              AND COALESCE(metadata->>'dispatched_to_stream_at', '') <> ''
              AND (
                    COALESCE(metadata->>'next_retry_after', '') = ''
                    OR NULLIF(metadata->>'next_retry_after', '')::timestamptz <= NOW()
                  )
              AND COALESCE(
                    NULLIF(metadata->>'dispatched_to_stream_at', '')::timestamptz,
                    updated_at,
                    created_at
                  ) < NOW() - ($1::text || ' minutes')::interval
              AND COALESCE((metadata->>'pending_dispatch_timeout_count')::int, 0) + 1 < $2::int
              AND (
                    COALESCE(metadata->>'last_llm_call_at', '') = ''
                    OR (metadata->>'last_llm_call_at')::timestamptz <
                        NOW() - ($3::text || ' minutes')::interval
                  )
              AND (
                    COALESCE(metadata->>'processing_started_at', '') = ''
                    OR (metadata->>'processing_started_at')::timestamptz <
                        NOW() - ($3::text || ' minutes')::interval
                  )
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(pending_dispatch_timeout_min),
        pending_dispatch_max_strikes,
        str(pending_dispatch_progress_grace_min),
    )
    pending_dispatch_cap_reopened = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET updated_at = NOW(),
                metadata = (
                    COALESCE(metadata, '{}'::jsonb)
                    - 'dispatched_to_stream_at'
                    - 'next_retry_after'
                ) || jsonb_build_object(
                    'dispatch_attempts', 0,
                    'pending_dispatch_timeout_count', 0,
                    'dispatch_cap_reopened', true,
                    'dispatch_cap_reopened_at', NOW()::text
                )
            WHERE status = 'pending'
              AND COALESCE((metadata->>'dispatch_attempts')::int, 0) >= $2::int
              AND (
                    COALESCE(metadata->>'dispatched_to_stream_at', '') = ''
                    OR NULLIF(metadata->>'dispatched_to_stream_at', '')::timestamptz <
                        NOW() - ($1::text || ' minutes')::interval
                  )
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(pending_dispatch_cap_reopen_min),
        pending_dispatch_max_strikes,
    )
    pending_dispatch_force_failed = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET status = 'failed',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'auto_fallback_at', NOW()::text,
                        'auto_fallback_reason', 'pending_dispatch_starvation_timeout',
                        'stale_force_fallback', true
                    )
            WHERE status = 'pending'
              AND COALESCE(metadata->>'dispatched_to_stream_at', '') <> ''
              AND (
                    COALESCE(metadata->>'next_retry_after', '') = ''
                    OR NULLIF(metadata->>'next_retry_after', '')::timestamptz <= NOW()
                  )
              AND COALESCE(
                    NULLIF(metadata->>'dispatched_to_stream_at', '')::timestamptz,
                    updated_at,
                    created_at
                  ) < NOW() - ($1::text || ' minutes')::interval
              AND COALESCE((metadata->>'pending_dispatch_timeout_count')::int, 0) + 1 >= $2::int
              AND (
                    COALESCE(metadata->>'last_llm_call_at', '') = ''
                    OR (metadata->>'last_llm_call_at')::timestamptz <
                        NOW() - ($3::text || ' minutes')::interval
                  )
              AND (
                    COALESCE(metadata->>'processing_started_at', '') = ''
                    OR (metadata->>'processing_started_at')::timestamptz <
                        NOW() - ($3::text || ' minutes')::interval
                  )
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(pending_dispatch_timeout_min),
        pending_dispatch_max_strikes,
        str(pending_dispatch_progress_grace_min),
    )
    autonomous_runtime_force_failed = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET status = 'failed',
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'auto_fallback_at', NOW()::text,
                        'auto_fallback_reason', 'autonomous_runtime_cap_timeout',
                        'stale_force_fallback', true
                    )
            WHERE status = 'in_progress'
              AND COALESCE((metadata->>'is_autonomous')::boolean, false) = true
              AND COALESCE(
                    NULLIF(metadata->>'processing_started_at', '')::timestamptz,
                    started_at,
                    updated_at,
                    created_at
                  ) < NOW() - ($1::text || ' minutes')::interval
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(autonomous_runtime_cap_min),
    )

    requeued = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET status = 'pending',
                assignee_expert_id = NULL,
                updated_at = NOW(),
                metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'stale_requeued_at', NOW()::text,
                        'stale_requeue_reason', 'in_progress_timeout'
                    ),
                    '{attempt_count}',
                    to_jsonb(COALESCE((metadata->>'attempt_count')::int, 0) + 1),
                    true
                )
            WHERE status = 'in_progress'
              AND updated_at < NOW() - ($1::text || ' minutes')::interval
              AND COALESCE((metadata->>'attempt_count')::int, 0) < $2
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(stale_minutes),
        max_retries,
    )

    fallback_ready = await conn.fetchval(
        """
        WITH moved AS (
            UPDATE tasks
            SET status = 'pending',
                assignee_expert_id = NULL,
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'stale_requeued_at', NOW()::text,
                        'stale_requeue_reason', 'in_progress_timeout_fallback',
                        'stale_force_fallback', true
                    )
            WHERE status = 'in_progress'
              AND updated_at < NOW() - ($1::text || ' minutes')::interval
              AND COALESCE((metadata->>'attempt_count')::int, 0) >= $2
            RETURNING id
        )
        SELECT count(*) FROM moved
    """,
        str(stale_minutes),
        max_retries,
    )
    return int(
        (ghost_requeued or 0)
        + (requeued or 0)
        + (curiosity_force_failed or 0)
        + (pending_curiosity_force_failed or 0)
        + (pending_dispatch_requeued or 0)
        + (pending_dispatch_cap_reopened or 0)
        + (pending_dispatch_force_failed or 0)
        + (autonomous_runtime_force_failed or 0)
    ), int(fallback_ready or 0)


async def rebalance_workload(conn) -> int:
    """Перебалансировка нагрузки между экспертами"""
    logger.info("⚖️ Starting workload rebalancing...")
    reassignments = 0
    live_experts = await _get_runtime_live_experts(force_refresh=True)
    live_names = sorted(live_experts) if live_experts else []

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
                if REQUIRE_RUNTIME_HEARTBEAT and live_names:
                    new_expert = await conn.fetchrow(
                        """
                        SELECT e.id, e.department
                        FROM experts e
                        JOIN domains d ON e.department = d.name
                        WHERE d.id = $1
                        AND e.id != $2
                        AND e.name = ANY($3::text[])
                        AND e.id IN (
                            SELECT id FROM (
                                SELECT e2.id, count(t2.id) as task_count
                                FROM experts e2
                                LEFT JOIN tasks t2 ON t2.assignee_expert_id = e2.id
                                    AND t2.status IN ('pending', 'in_progress')
                                WHERE e2.name = ANY($3::text[])
                                GROUP BY e2.id
                                HAVING count(t2.id) < 2
                            ) underloaded_inner
                        )
                        ORDER BY RANDOM()
                        LIMIT 1
                    """,
                        task["domain_id"],
                        expert_id,
                        live_names,
                    )
                else:
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
                            metadata = (
                                COALESCE(metadata, '{}'::jsonb)
                                - 'dispatched_to_stream_at'
                                - 'dispatch_attempts'
                            ) || $3::jsonb
                        WHERE id = $2
                    """,
                        new_expert["id"],
                        task["id"],
                        json.dumps({"preferred_source": pref}),
                    )
                    logger.info("  ↻ Task %s reassigned (source=%s)", task["id"], pref)
                    reassignments += 1
                else:
                    # [SINGULARITY 31.3] No underloaded live expert found → route to overflow pool
                    _overflow_names_str = os.getenv("EXPERT_OVERFLOW_NAMES", "Инна,Юлия")
                    for _ov_name in _overflow_names_str.split(","):
                        _ov_name = _ov_name.strip()
                        if not _ov_name:
                            continue
                        _ov_expert = await conn.fetchrow(
                            "SELECT id, name FROM experts WHERE name = $1 LIMIT 1", _ov_name
                        )
                        if _ov_expert:
                            await conn.execute(
                                """
                                UPDATE tasks
                                SET assignee_expert_id = $1,
                                    updated_at = NOW(),
                                    metadata = (
                                        COALESCE(metadata, '{}'::jsonb)
                                        - 'dispatched_to_stream_at'
                                        - 'dispatch_attempts'
                                    ) || $3::jsonb
                                WHERE id = $2
                            """,
                                _ov_expert["id"],
                                task["id"],
                                json.dumps({"routed_to_overflow": True, "original_expert_id": str(expert_id)}),
                            )
                            logger.info("  ↻ Task %s → overflow pool (%s)", task["id"], _ov_name)
                            reassignments += 1
                            break
    return reassignments


async def run_enhanced_orchestration_cycle():
    """Запуск цикла Enhanced Orchestrator с обновлением знаний корпорации"""
    _record_orch_metric("gauge_inc", _orch_active_cycles)

    try:
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

        if ollama_ok:
            try:
                from corporation_knowledge_system import update_all_agents_knowledge

                async with _corp_refresh_lock:
                    global _corp_refresh_task, _corp_refresh_last_start_ts
                    now_ts = time.monotonic()
                    if _corp_refresh_task and not _corp_refresh_task.done():
                        logger.info(
                            "⏭️ [CORP-KNOWLEDGE] Skip refresh: previous update still running."
                        )
                    elif (now_ts - _corp_refresh_last_start_ts) < _corp_refresh_min_interval_sec:
                        wait_left = int(
                            _corp_refresh_min_interval_sec - (now_ts - _corp_refresh_last_start_ts)
                        )
                        logger.info(
                            "⏭️ [CORP-KNOWLEDGE] Skip refresh: cooldown active (%ss left).",
                            max(wait_left, 0),
                        )
                    else:
                        _corp_refresh_last_start_ts = now_ts
                        _corp_refresh_task = asyncio.create_task(update_all_agents_knowledge())
                        logger.info(
                            "✅ [CORP-KNOWLEDGE] Background refresh started (min interval=%ss)",
                            _corp_refresh_min_interval_sec,
                        )
            except Exception as e:
                logger.debug("Не удалось обновить з��ания корпорации: %s", e)
    except Exception as e:
        _record_orch_metric("counter", _orch_errors, phase="health_check", error_type="exception")
        logger.debug("Health check error: %s", e)

    if not ASYNCPG_AVAILABLE:
        logger.error("❌ asyncpg is not installed. Orchestration aborted.")
        return

    async with acquire_resource_lock("orchestrator") as orch_lock:
        logger.info("[ENHANCED_ORCHESTRATOR] cycle start DATABASE_URL=%s", _mask_db_url(DB_URL))
        conn = await asyncpg.connect(DB_URL)
        heavy_phase_step_timeout_sec = int(
            os.getenv("ORCHESTRATOR_HEAVY_PHASE_STEP_TIMEOUT_SEC", "120")
        )

        async def _has_execution_backlog(_conn) -> bool:
            return await has_execution_backlog(_conn)

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

            # --- ФАЗА 1.5: ДЕКОМПОЗИЦИЯ СЛОЖНЫХ ЗАДАЧ (Pipelines & First Principles) ---
            t15 = time.time()
            decomposed_count = 0

            # [AGENT SCOPE] Orchestration Pipeline
            try:
                from agentscope.agents import DialogAgent
                from agentscope.pipelines import SequentialPipeline

                # 1. Decomposition Agent (First Principles)
                decomposer = DialogAgent(
                    name="Decomposer",
                    sys_prompt="ТЫ - Архитектор. Разложи задачу на атомарные части (First Principles Thinking).",
                    model_config_name="victoria_mlx",
                )

                # 2. Red Team Auditor (Pre-mortem)
                auditor = DialogAgent(
                    name="Auditor",
                    sys_prompt="ТЫ - Red Team. Найди 3 причины, почему этот план провалится (Pre-mortem).",
                    model_config_name="victoria_mlx",
                )

                # Pipeline: Decompose -> Audit -> Execute
                orch_pipeline = SequentialPipeline([decomposer, auditor])

            except ImportError:
                orch_pipeline = None

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
                    # [SINGULARITY 24.6] Emergency Concurrency Guard
                    # If more than 3 tasks are already in progress, skip decomposition to prevent RAM overload
                    active_count = await conn.fetchval(
                        "SELECT count(*) FROM tasks WHERE status = 'in_progress'"
                    )
                    if active_count >= 3:
                        logger.warning(
                            f"⚠️ [CONCURRENCY GUARD] {active_count} tasks in progress. Skipping decomposition."
                        )
                        continue

                    goal = f"{task['title']}\n\n{task['description'] or ''}"

                    # [SINGULARITY 28.6] Decentralized Market: Post to Blackboard first
                    try:
                        from services.blackboard_service import get_blackboard_service

                        blackboard = get_blackboard_service()
                        await blackboard.post_goal(
                            str(task["id"]),
                            goal,
                            {
                                "priority": task["priority"],
                                "domain_id": str(task["domain_id"]) if task["domain_id"] else None,
                                "project_context": task.get("project_context"),
                                "is_market_task": True,
                            },
                        )
                        logger.info(
                            f"🏛️ [MARKET] Goal {task['id']} posted to Blackboard for self-organization."
                        )
                        # Мы НЕ вызываем _decompose_via_victoria сразу.
                        # Даем экспертам 60 секунд на самоорганизацию.
                        continue
                    except Exception as market_err:
                        logger.warning(f"⚠️ [MARKET] Failed to post to Blackboard: {market_err}")

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

                        # [SINGULARITY 26.2] Swarm MsgHub Integration
                        is_swarm = bool(struct.get("is_swarm", False))

                        # [SINGULARITY 26.3] Dynamic Sub-Agent Spawning (Micro-Agent Factory)
                        # Если задача требует ультра-специфичного навыка, которого нет у экспертов
                        if struct.get("needs_micro_agent"):
                            try:
                                from expert_generator import recruit_expert

                                micro_domain = struct.get("micro_agent_domain", st_dept)
                                logger.info(
                                    f"🧬 [SPAWNING] Spawning micro-agent for domain: {micro_domain}"
                                )
                                await recruit_expert(micro_domain, is_micro=True)
                            except Exception as se:
                                logger.error(f"❌ [SPAWNING] Failed to spawn micro-agent: {se}")

                        if is_swarm:
                            logger.info(f"🐝 [SWARM] Initializing MsgHub for task {task['id']}")
                            try:
                                from agentscope.msghub import msghub
                                # MsgHub создается в контексте AI Core, здесь мы просто помечаем задачу
                            except ImportError:
                                pass

                        for st in subtasks[:5]:  # max 5 subtasks
                            st_desc = st.get("subtask", st.get("description", ""))
                            st_dept = st.get("department", "General")
                            domain_row = await conn.fetchrow(
                                "SELECT id FROM domains WHERE name = $1", st_dept
                            )
                            st_domain_id = domain_row["id"] if domain_row else task["domain_id"]

                            # [SINGULARITY 26.2] Contract & Handoff metadata
                            st_contract = st.get("contract")

                            meta = {
                                "source": "orchestrator_decompose",
                                "parent_task_id": str(task["id"]),
                                "expert_role": st.get("expert_role", ""),
                                "is_swarm": is_swarm,
                                "contract": st_contract,
                            }

                            _meta = task.get("metadata")
                            parent_pc = task.get("project_context") or (
                                json.loads(_meta).get("project_context")
                                if isinstance(_meta, str)
                                else (_meta or {}).get("project_context")
                            )
                        # [SINGULARITY 24.7] Adaptive Priority for Monster Audits
                        _priority = st.get("priority", "medium")
                        meta_json = json.loads(meta)
                        if meta_json.get("source") == "victoria_monster_delegation":
                            _priority = "low"  # Аудиты не должны мешать основным задачам

                        try:
                            sub_id = await conn.fetchval(
                                """
                                INSERT INTO tasks (title, description, status, priority, domain_id, creator_expert_id, metadata, parent_task_id, project_context)
                                VALUES ($1, $2, 'pending', $3, $4, $5, $6::jsonb, $7, $8)
                                ON CONFLICT (title, COALESCE(project_context, 'default'))
                                WHERE status IN ('pending', 'in_progress')
                                DO NOTHING
                                RETURNING id
                            """,
                                (st_desc[:255] if len(st_desc) > 255 else st_desc),
                                st_desc,
                                _priority,
                                st_domain_id,
                                victoria_id,
                                json.dumps(meta),
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
                                    ON CONFLICT (title)
                                    WHERE status IN ('pending', 'in_progress')
                                    DO NOTHING
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

            # --- ФАЗА 1.95: RUNTIME REGISTRY RECONCILE ---
            t195 = time.time()
            reopened_pending, reopened_in_progress = await reconcile_nonlive_assignments(conn)
            stale_reopened, stale_fallback_ready = await reconcile_stale_in_progress(conn)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=1.95 duration_ms=%.0f result=%s pending_reopened, %s in_progress_reopened, %s stale_reopened, %s stale_fallback_ready",
                (time.time() - t195) * 1000,
                reopened_pending,
                reopened_in_progress,
                stale_reopened,
                stale_fallback_ready,
            )

            # --- ФАЗА 1.97: DYNAMIC WORKER SCALE-DOWN ---
            t197 = time.time()
            dynamic_scaled_down = await _scale_down_idle_dynamic_workers(conn)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=1.97 duration_ms=%.0f result=%s dynamic_workers_scaled_down",
                (time.time() - t197) * 1000,
                dynamic_scaled_down,
            )

            # --- ФАЗА 2: НАЗНАЧЕНИЕ ЗАДАЧ БЕЗ ИСПОЛНИТЕЛЯ ---
            t2 = time.time()
            logger.info("👥 Phase 2: Assigning unassigned tasks...")
            unassigned_tasks = await conn.fetch("""
                SELECT t.id, t.title, t.description, t.domain_id, t.priority, t.metadata
                FROM tasks t
                WHERE t.assignee_expert_id IS NULL
                AND t.status = 'pending'
                AND (t.metadata->>'decomposed') IS DISTINCT FROM 'true'
                ORDER BY
                    CASE t.priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    t.created_at ASC
            """)

            assigned_count = 0
            failed_assign_count = 0
            for task in unassigned_tasks:
                task_start = time.time()
                try:
                    result = await assign_task_to_best_expert(
                        conn, task["id"], task["domain_id"], metadata=task.get("metadata")
                    )
                    if result:
                        assigned_count += 1
                        _record_orch_metric(
                            "counter", _orch_tasks_assigned, phase="phase2", status="success"
                        )
                    else:
                        failed_assign_count += 1
                        _record_orch_metric(
                            "counter", _orch_tasks_assigned, phase="phase2", status="no_expert"
                        )
                except Exception as assign_err:
                    failed_assign_count += 1
                    _record_orch_metric(
                        "counter", _orch_tasks_assigned, phase="phase2", status="error"
                    )
                    _record_orch_metric(
                        "counter", _orch_errors, phase="phase2", error_type="assignment"
                    )
                    logger.debug("Task assignment error: %s", assign_err)
                _record_orch_metric(
                    "histogram", _orch_task_duration, "phase2", value=time.time() - task_start
                )
            _record_orch_metric("counter", _orch_tasks_per_phase, "phase2")

            # [SINGULARITY 25.0] Expert-Based Task Prioritization
            # Повышаем приоритет задач, назначенных VIP-экспертам
            await conn.execute("""
                UPDATE tasks t
                SET priority = 'urgent'
                FROM experts e
                WHERE t.assignee_expert_id = e.id
                AND e.priority = 'VIP'
                AND t.status = 'pending'
                AND t.priority != 'urgent'
            """)

            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=2 duration_ms=%.0f result=%s assigned, %s failed",
                (time.time() - t2) * 1000,
                assigned_count,
                failed_assign_count,
            )
            t22 = time.time()
            dispatched = await dispatch_pending_assignments(conn, limit=100)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=2.2 duration_ms=%.0f result=%s dispatched_to_stream",
                (time.time() - t22) * 1000,
                dispatched,
            )
            try:
                rollout_mode = await _resolve_contract_mode(rd)
                rollout_kpi = await _compute_rollout_kpis(conn)
                logger.info(
                    "[ROLLOUT] window=%sm completed_10m=%s failed_10m=%s in_progress_now=%s pending_now=%s failure_rate=%.3f mode=%s canary=%s",
                    ROLLOUT_KPI_WINDOW_MIN,
                    rollout_kpi["completed_10m"],
                    rollout_kpi["failed_10m"],
                    rollout_kpi["in_progress_now"],
                    rollout_kpi["pending_now"],
                    rollout_kpi["failure_rate"],
                    rollout_mode,
                    CONTRACT_CANARY_ENFORCE_PERCENT,
                )
                if rd is not None:
                    await rd.set("system:contract_rollout_kpi", json.dumps(rollout_kpi))
                if rd is not None and rollout_mode == "auto":
                    should_enforce = (
                        rollout_kpi["completed_10m"] >= ROLLOUT_KPI_MIN_COMPLETED
                        and rollout_kpi["failure_rate"] <= ROLLOUT_KPI_MAX_FAILURE_RATE
                        and rollout_kpi["pending_now"] <= ROLLOUT_KPI_MAX_PENDING
                    )
                    await rd.set("system:contract_enforce", "1" if should_enforce else "0")
                    logger.info(
                        "[ROLLOUT] auto_switch contract_enforce=%s (min_completed=%s max_failure_rate=%.2f max_pending=%s)",
                        should_enforce,
                        ROLLOUT_KPI_MIN_COMPLETED,
                        ROLLOUT_KPI_MAX_FAILURE_RATE,
                        ROLLOUT_KPI_MAX_PENDING,
                    )
            except Exception as rollout_err:
                logger.warning("[ROLLOUT] KPI evaluation failed: %s", rollout_err)

            # --- ФАЗА 2.5: ORCHESTRATOR FALLBACK (задачи с attempt_count >= 3, rule-based) ---
            t25 = time.time()
            fallback_for_rd_verify = os.getenv(
                "ORCHESTRATOR_RULE_FALLBACK_FOR_RD_VERIFY", "true"
            ).lower() in (
                "true",
                "1",
                "yes",
            )
            fallback_for_file_audit = os.getenv(
                "ORCHESTRATOR_RULE_FALLBACK_FOR_FILE_AUDIT", "true"
            ).lower() in (
                "true",
                "1",
                "yes",
            )
            fallback_min_attempts = int(
                os.getenv("ORCHESTRATOR_RULE_FALLBACK_MIN_ATTEMPTS", "3")
            )
            failed_tasks = await conn.fetch(
                """
                SELECT id, title, description, metadata
                FROM tasks
                WHERE status = 'pending'
                AND (
                    COALESCE((metadata->>'attempt_count')::int, 0) >= $2
                    OR COALESCE((metadata->>'agent_failed_count')::int, 0) >= $2
                    OR (
                        $1::boolean = true
                        AND COALESCE((metadata->>'stale_force_fallback')::boolean, false) = true
                    )
                    OR (
                        $3::boolean = true
                        AND (
                            title ILIKE '%проверь файл%'
                            OR description ILIKE '%проверь файл%'
                            OR title ILIKE '%check file%'
                            OR description ILIKE '%check file%'
                        )
                    )
                )
                LIMIT 50
            """,
                fallback_for_rd_verify,
                fallback_min_attempts,
                fallback_for_file_audit,
            )
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
            reassignments = await rebalance_workload(conn)
            logger.info(
                "[ENHANCED_ORCHESTRATOR] phase=3 duration_ms=%.0f result=rebalance reassigned=%s",
                (time.time() - t3) * 1000,
                reassignments,
            )
            if reassignments > 0:
                t32 = time.time()
                dispatched_after_rebalance = await dispatch_pending_assignments(conn, limit=100)
                logger.info(
                    "[ENHANCED_ORCHESTRATOR] phase=3.2 duration_ms=%.0f result=%s dispatched_after_rebalance",
                    (time.time() - t32) * 1000,
                    dispatched_after_rebalance,
                )

            # --- RELEASE GLOBAL LOCK BEFORE HEAVY/NON-CRITICAL PHASES ---
            if os.getenv("ORCHESTRATOR_RELEASE_LOCK_BEFORE_HEAVY_PHASES", "true").lower() in (
                "true",
                "1",
                "yes",
            ):
                try:
                    await orch_lock.release()
                    logger.info(
                        "[ENHANCED_ORCHESTRATOR] released global lock before heavy phases (4+)"
                    )
                except Exception as lock_release_err:
                    logger.warning(
                        "[ENHANCED_ORCHESTRATOR] failed to release global lock early: %s",
                        lock_release_err,
                    )

            # [QUALITY-FIRST] Keep cycle cadence high while execution backlog exists.
            # This prevents heavy R&D phases from starving assignment/recovery loops.
            execution_focus = os.getenv(
                "ORCHESTRATOR_FOCUS_EXECUTION_WHEN_BACKLOG", "true"
            ).lower() in ("true", "1", "yes")
            backlog_threshold = int(os.getenv("ORCHESTRATOR_BACKLOG_THRESHOLD", "10"))

            backlog_pending = await conn.fetchval(
                "SELECT count(*) FROM tasks WHERE status = 'pending'"
            )
            backlog_in_progress = await conn.fetchval(
                "SELECT count(*) FROM tasks WHERE status = 'in_progress'"
            )

            if execution_focus and (
                backlog_pending > backlog_threshold
                or backlog_in_progress > (backlog_threshold // 2)
            ):
                logger.info(
                    "[ENHANCED_ORCHESTRATOR] quality-focus: skip heavy phases (4+) while backlog exceeds threshold (%s) pending=%s in_progress=%s",
                    backlog_threshold,
                    backlog_pending,
                    backlog_in_progress,
                )
                _record_orch_metric("counter", _orch_cycles_total, status="success")
                return

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
                    try:
                        hypothesis = await asyncio.wait_for(
                            run_cursor_agent(link_prompt),
                            timeout=heavy_phase_step_timeout_sec,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "[ENHANCED_ORCHESTRATOR] phase4 step timeout (%ss) for cross-domain hypothesis",
                            heavy_phase_step_timeout_sec,
                        )
                        hypothesis = None
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
                if execution_focus and await _has_execution_backlog(conn):
                    logger.info(
                        "[ENHANCED_ORCHESTRATOR] quality-focus: backlog appeared during phase4, interrupt heavy phases"
                    )
                    _record_orch_metric("counter", _orch_cycles_total, status="success")
                    return

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
                # [SINGULARITY 24.6] Stricter Backpressure: Reduced from 10 to 5 to prevent RAM spikes
                max_pending = int(os.getenv("SMART_WORKER_MAX_PENDING", "5"))

                # [SINGULARITY 24.7] Health-Aware Backpressure
                # If RAM usage is high, reduce max_pending even further
                try:
                    import psutil

                    mem = psutil.virtual_memory()
                    if mem.percent > 85:
                        logger.warning(
                            f"🚨 [HEALTH-AWARE] RAM usage high ({mem.percent}%). Reducing max_pending to 1."
                        )
                        max_pending = 1
                    elif mem.percent > 70:
                        logger.warning(
                            f"⚠️ [HEALTH-AWARE] RAM usage moderate ({mem.percent}%). Reducing max_pending to 3."
                        )
                        max_pending = 3
                except ImportError:
                    pass

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

            curiosity_min_completed_10m = int(
                os.getenv("ORCHESTRATOR_CURIOSITY_MIN_COMPLETED_10M", "1")
            )
            completed_10m_now = await conn.fetchval(
                """
                SELECT count(*)
                FROM tasks
                WHERE status = 'completed'
                  AND updated_at > NOW() - INTERVAL '10 minutes'
                """
            )
            if int(completed_10m_now or 0) < curiosity_min_completed_10m:
                logger.info(
                    "⏸️ CURIOSITY THROTTLE: completed_10m=%s < min=%s, skip curiosity creation this cycle",
                    completed_10m_now,
                    curiosity_min_completed_10m,
                )
                deserts = []

            # Лимит автономных экспертов (план: не более 25)
            autonomous_count = await conn.fetchval(
                "SELECT count(*) FROM experts WHERE (metadata->>'is_autonomous')::text = 'true'"
            )
            autonomous_limit = int(os.getenv("AUTONOMOUS_EXPERT_LIMIT", "25"))
            max_active_curiosity = int(os.getenv("ORCHESTRATOR_MAX_ACTIVE_CURIOSITY_TASKS", "1"))

            curiosity_assigned = 0
            for desert in deserts:
                active_curiosity = await conn.fetchval(
                    """
                    SELECT count(*)
                    FROM tasks
                    WHERE status IN ('pending', 'in_progress')
                      AND COALESCE(metadata->>'reason', '') = 'curiosity_engine_starvation'
                    """
                )
                if int(active_curiosity or 0) >= max_active_curiosity:
                    logger.info(
                        "  ⏭️ Curiosity budget reached: active=%s limit=%s",
                        active_curiosity,
                        max_active_curiosity,
                    )
                    continue
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
                curiosity_cooldown_min = int(
                    os.getenv("ORCHESTRATOR_CURIOSITY_RETRY_COOLDOWN_MIN", "30")
                )
                recent_curiosity_failure = await conn.fetchval(
                    """
                    SELECT 1
                    FROM tasks
                    WHERE title = $1
                      AND status = 'failed'
                      AND updated_at > NOW() - ($2::text || ' minutes')::interval
                      AND COALESCE(metadata->>'auto_fallback_reason', '') IN (
                          'curiosity_no_llm_progress_timeout',
                          'pending_curiosity_starvation_timeout'
                      )
                    LIMIT 1
                    """,
                    title_curiosity,
                    str(curiosity_cooldown_min),
                )
                if recent_curiosity_failure:
                    logger.info(
                        "  ⏭️ Curiosity cooldown active for %s (recent timeout fallback within %s min)",
                        desert["name"],
                        curiosity_cooldown_min,
                    )
                    continue
                priority = "high" if desert["node_count"] < 20 else "medium"
                try:
                    task_id = await conn.fetchval(
                        """
                        INSERT INTO tasks (title, description, status, priority, creator_expert_id, domain_id, metadata)
                        VALUES ($1, $2, 'pending', $3, $4, $5, $6)
                        ON CONFLICT (title, COALESCE(project_context, 'default'))
                        WHERE status IN ('pending', 'in_progress')
                        DO UPDATE SET updated_at = NOW()
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
                    if task_id:
                        await assign_task_to_best_expert(conn, task_id, desert["id"])
                        curiosity_assigned += 1
                except Exception as task_err:
                    if "duplicate" in str(task_err).lower() or "23505" in str(task_err):
                        logger.info(f"  ⏭️ Task already exists (dedup): {title_curiosity[:50]}")
                    else:
                        raise
            if curiosity_assigned > 0:
                t52 = time.time()
                dispatched_curiosity = await dispatch_pending_assignments(conn, limit=100)
                logger.info(
                    "[ENHANCED_ORCHESTRATOR] phase=5.2 duration_ms=%.0f result=%s dispatched_curiosity",
                    (time.time() - t52) * 1000,
                    dispatched_curiosity,
                )
            if execution_focus and await _has_execution_backlog(conn):
                logger.info(
                    "[ENHANCED_ORCHESTRATOR] quality-focus: backlog appeared during phase5, interrupt heavy phases"
                )
                _record_orch_metric("counter", _orch_cycles_total, status="success")
                return
            if execution_focus:
                logger.info(
                    "[ENHANCED_ORCHESTRATOR] quality-focus: finish live cycle after phase5 (heavy phases delegated to nightly)"
                )
                _record_orch_metric("counter", _orch_cycles_total, status="success")
                return

            logger.info("🌐 Phase 5: Running Global Scout validation...")
            try:
                await asyncio.wait_for(
                    run_global_scout_cycle(),
                    timeout=heavy_phase_step_timeout_sec,
                )
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Global Scout error: %s", exc)

            logger.info("🔗 Phase 6: Running auto-link detection...")
            try:
                await asyncio.wait_for(
                    run_auto_link_detection(),
                    timeout=heavy_phase_step_timeout_sec,
                )
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Auto-link detection error: %s", exc)

            logger.info("🧬 Phase 7: Knowledge Distillation & Auto-Upgrade...")
            try:
                distiller = _get_distiller()
                distilled_count = await asyncio.wait_for(
                    distiller.collect_high_quality_samples(days=1),
                    timeout=heavy_phase_step_timeout_sec,
                )
                if distilled_count > 0:
                    logger.info("  ✨ Distilled %d high-quality samples.", distilled_count)
                generator = _get_synthetic_generator()
                await asyncio.wait_for(
                    generator.generate_synthetic_samples(limit=5),
                    timeout=heavy_phase_step_timeout_sec,
                )
                pipeline = _get_training_pipeline()
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
                        ON CONFLICT (title) WHERE status IN ('pending', 'in_progress') DO UPDATE SET updated_at = NOW()
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
                swarm = _get_swarm_orchestrator()
                await swarm.handle_critical_failures()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Swarm error: %s", exc)

            logger.info("🏗️ Phase 11: Meta-Architect Review...")
            try:
                architect = _get_meta_architect()
                await architect.self_repair_cycle()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Meta-Architect error: %s", exc)

            logger.info("🧬 Phase 12: Autonomous Evolution...")
            try:
                evolution = _get_evolution_monitor()
                evolution_report = await evolution.run_daily_check()
                logger.info("  %s", evolution_report)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Evolution error: %s", exc)

            logger.info("🔍 Phase 13: Curiosity Engine Gap Analysis...")
            try:
                curiosity = _get_curiosity_engine()
                gap_result = await curiosity.scan_for_gaps()
                logger.info("  %s", gap_result)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Curiosity error: %s", exc)

            logger.info("🧠 Phase 14: Memory Consolidation (The Dreaming)...")
            try:
                consolidator = _get_memory_consolidator()
                consolidation_result = await consolidator.consolidate_memory()
                logger.info("  %s", consolidation_result)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Consolidation error: %s", exc)

            logger.info("🌐 Phase 14.5: Multi-Cluster Bridge Sync...")
            if MultiClusterBridge:
                try:
                    bridge = _get_multi_cluster_bridge()
                    if bridge is None:
                        raise RuntimeError("MultiClusterBridge unavailable")
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
                        sync_manager = _get_server_knowledge_sync()
                        if sync_manager is None:
                            raise RuntimeError("ServerKnowledgeSync unavailable")
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
                archiver = _get_knowledge_archiver()
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

            try:
                if rd:
                    await rd.aclose()
            except Exception as rd_close_err:  # pylint: disable=broad-exception-caught
                logger.debug("Redis close error: %s", rd_close_err)
            await conn.close()
            logger.info("[ENHANCED_ORCHESTRATOR] cycle finished successfully.")
        except Exception as cycle_exc:  # pylint: disable=broad-exception-caught
            # Игнорируем duplicate key - это нормально (задача уже существует)
            if "duplicate" in str(cycle_exc).lower() or "23505" in str(cycle_exc):
                logger.info("[ENHANCED_ORCHESTRATOR] duplicate task ignored (dedup working)")
            else:
                logger.error("[ENHANCED_ORCHESTRATOR] cycle exception: %s", cycle_exc)
                logger.error(traceback.format_exc())
                _record_orch_metric(
                    "counter", _orch_errors, phase="orchestration", error_type="cycle_exception"
                )
            try:
                if rd:
                    await rd.aclose()
            except Exception:
                pass
            try:
                await conn.close()
            except Exception:
                pass
            raise
        finally:
            _record_orch_metric("gauge_dec", _orch_active_cycles)


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

    # [SINGULARITY 24.3] Запуск автономных демонов (Живой Чат, мониторинг)
    try:
        try:
            from app.autonomous_daemons import setup_daemons
        except ImportError:
            from autonomous_daemons import setup_daemons
        asyncio.create_task(setup_daemons())
        logger.info("🎭 [ENHANCED_ORCHESTRATOR] Autonomous daemons started")

        # [SINGULARITY 24.3] Periodically log subscribers to verify they stay active
        async def log_subscribers_periodically():
            try:
                from app.event_bus import get_event_bus
            except ImportError:
                from event_bus import get_event_bus

            while True:
                await asyncio.sleep(30)
                bus = get_event_bus()
                logger.info(
                    f"🔍 [DEBUG] Periodic check: EventBus ID: {id(bus)}, Subscribers: {list(bus.subscribers.keys())}"
                )

        asyncio.create_task(log_subscribers_periodically())

    except Exception as e:
        logger.error(f"❌ [ENHANCED_ORCHESTRATOR] Failed to start autonomous daemons: {e}")

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
                # Игнорируем duplicate key - это нормально (задача уже существует)
                if "duplicate" in str(e).lower() or "23505" in str(e):
                    logger.info("[ENHANCED_ORCHESTRATOR] duplicate task ignored (dedup working)")
                else:
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
        print("⚠️ [ORCHESTRATOR] Process already running. Exiting to prevent duplication.")
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


async def metrics_handler(request=None):
    """Prometheus metrics endpoint for orchestrator."""
    try:
        from fastapi.responses import Response
    except ImportError:
        try:
            from starlette.responses import Response
        except ImportError:
            Response = None

    if _PROMETHEUS_AVAILABLE and Response:
        try:
            metrics_output = generate_latest(_orch_registry).decode("utf-8")
            return Response(content=metrics_output, media_type="text/plain")
        except Exception as e:
            return (
                Response(content=f"# ERROR: {e}\n", media_type="text/plain", status_code=500)
                if Response
                else None
            )
    if Response:
        return Response(content="# No metrics available\n", media_type="text/plain")
    return None
