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
from orchestrator_phases import (
    ensure_victoria_id,
    phase_0_5_migrations,
    phase_0_auto_fix,
    phase_1_5_decompose,
    phase_1_6_batch_group,
    phase_1_8_red_team,
    phase_1_9_execution_optimizer,
    phase_1_95_reconcile,
    phase_1_97_scale_down,
    phase_1_prioritize,
    phase_2_2_dispatch,
    phase_2_5_rule_fallback,
    phase_2_assign,
    phase_3_rebalance,
    phase_4_cross_domain,
    phase_5_8_rnd,
    phase_5_curiosity,
    phase_heavy_tail,
)

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
                                json.dumps(
                                    {
                                        "routed_to_overflow": True,
                                        "original_expert_id": str(expert_id),
                                    }
                                ),
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
            # --- ФАЗА 0 / 0.5: модуль orchestrator_phases (behavior-preserving extract) ---
            # [SINGULARITY 21.29] Apply Time Decay before starting new work
            await apply_time_decay(conn)
            await phase_0_auto_fix(conn)
            await phase_0_5_migrations(conn, app_file=__file__)
            victoria_id = await ensure_victoria_id(conn)
            await phase_1_prioritize(conn, calculate_task_priority=calculate_task_priority)

            # --- ФАЗА 1.5: ДЕКОМПОЗИЦИЯ (orchestrator_phases) ---
            await phase_1_5_decompose(
                conn,
                victoria_id=victoria_id,
                decompose_via_victoria=_decompose_via_victoria,
                assign_task_to_best_expert=assign_task_to_best_expert,
            )

            # --- ФАЗА 1.6: БАТЧ-ГРУППИРОВКА (orchestrator_phases) ---
            await phase_1_6_batch_group(conn)

            # --- ФАЗА 1.8: RED TEAM CRITIC (orchestrator_phases) ---
            await phase_1_8_red_team(conn, run_smart_agent_async=run_smart_agent_async)

            # --- ФАЗА 1.9: EXECUTION OPTIMIZER (orchestrator_phases) ---
            await phase_1_9_execution_optimizer(conn)

            # --- ФАЗА 1.95: RUNTIME REGISTRY RECONCILE (orchestrator_phases) ---
            await phase_1_95_reconcile(
                conn,
                reconcile_nonlive_assignments=reconcile_nonlive_assignments,
                reconcile_stale_in_progress=reconcile_stale_in_progress,
            )

            # --- ФАЗА 1.97: DYNAMIC WORKER SCALE-DOWN (orchestrator_phases) ---
            await phase_1_97_scale_down(
                conn, scale_down_idle_dynamic_workers=_scale_down_idle_dynamic_workers
            )

            # --- ФАЗА 2: НАЗНАЧЕНИЕ ЗАДАЧ (orchestrator_phases) ---
            await phase_2_assign(
                conn,
                assign_task_to_best_expert=assign_task_to_best_expert,
                record_orch_metric=_record_orch_metric,
                orch_tasks_assigned=_orch_tasks_assigned,
                orch_task_duration=_orch_task_duration,
                orch_errors=_orch_errors,
                orch_tasks_per_phase=_orch_tasks_per_phase,
            )

            # --- ФАЗА 2.2: DISPATCH (orchestrator_phases) ---
            await phase_2_2_dispatch(
                conn, dispatch_pending_assignments=dispatch_pending_assignments, limit=100
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

            # --- ФАЗА 2.5: RULE FALLBACK (orchestrator_phases) ---
            await phase_2_5_rule_fallback(
                conn,
                rule_executor_can_handle=rule_executor_can_handle,
                rule_executor_execute=rule_executor_execute,
            )

            # --- ФАЗА 3 / 3.2: ПЕРЕБАЛАНСИРОВКА (orchestrator_phases) ---
            await phase_3_rebalance(
                conn,
                rebalance_workload=rebalance_workload,
                dispatch_pending_assignments=dispatch_pending_assignments,
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

            # --- ФАЗА 4: АССОЦИАТИВНЫЙ МОЗГ (orchestrator_phases) ---
            phase4 = await phase_4_cross_domain(
                conn,
                rd,
                run_cursor_agent=run_cursor_agent,
                heavy_phase_step_timeout_sec=heavy_phase_step_timeout_sec,
                execution_focus=execution_focus,
                has_execution_backlog=_has_execution_backlog,
            )
            if phase4.get("interrupted"):
                _record_orch_metric("counter", _orch_cycles_total, status="success")
                return

            # --- ФАЗА 5: CURIOSITY (orchestrator_phases) ---
            phase5 = await phase_5_curiosity(
                conn,
                victoria_id=victoria_id,
                get_ollama_latency=get_ollama_latency,
                canonical_domain=_canonical_domain,
                justify_task_value=_justify_task_value,
                get_best_expert_for_domain=get_best_expert_for_domain,
                same_task_for_expert_in_last_n_days=same_task_for_expert_in_last_n_days,
                assign_task_to_best_expert=assign_task_to_best_expert,
                dispatch_pending_assignments=dispatch_pending_assignments,
                execution_focus=execution_focus,
                has_execution_backlog=_has_execution_backlog,
                expert_generator_path=os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "expert_generator.py"
                ),
            )
            if phase5.get("interrupted") or phase5.get("finish_cycle"):
                _record_orch_metric("counter", _orch_cycles_total, status="success")
                return

            # --- PHASES 5(scout)–8: R&D tail (orchestrator_phases) ---
            await phase_5_8_rnd(
                conn,
                victoria_id=victoria_id,
                heavy_phase_step_timeout_sec=heavy_phase_step_timeout_sec,
                run_global_scout_cycle=run_global_scout_cycle,
                run_auto_link_detection=run_auto_link_detection,
                get_distiller=_get_distiller,
                get_synthetic_generator=_get_synthetic_generator,
                get_training_pipeline=_get_training_pipeline,
            )

            # --- PHASES 10–16: autonomous subsystems (orchestrator_phases) ---
            await phase_heavy_tail(
                conn,
                rd,
                get_swarm_orchestrator=_get_swarm_orchestrator,
                get_meta_architect=_get_meta_architect,
                get_evolution_monitor=_get_evolution_monitor,
                get_curiosity_engine=_get_curiosity_engine,
                get_memory_consolidator=_get_memory_consolidator,
                get_multi_cluster_bridge=_get_multi_cluster_bridge,
                get_server_knowledge_sync=_get_server_knowledge_sync,
                get_knowledge_archiver=_get_knowledge_archiver,
                multi_cluster_bridge_cls=MultiClusterBridge,
                server_knowledge_sync_cls=ServerKnowledgeSync,
            )

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

    metrics_runner = None
    if os.getenv("ENABLE_METRICS", "false").lower() in ("1", "true", "yes"):
        try:
            from aiohttp import web as _web

            metrics_port = int(os.getenv("METRICS_PORT", "8000"))

            async def _orch_metrics(request):
                if _PROMETHEUS_AVAILABLE:
                    try:
                        body = generate_latest(_orch_registry)
                        return _web.Response(body=body, content_type="text/plain")
                    except Exception as e:
                        return _web.Response(
                            text=f"# metrics error: {type(e).__name__}\n",
                            content_type="text/plain",
                            status=500,
                        )
                return _web.Response(
                    text="# prometheus_client not installed\n",
                    content_type="text/plain",
                    status=503,
                )

            async def _orch_health(request):
                return _web.json_response({"status": "healthy", "service": "orchestrator"})

            app = _web.Application()
            app.router.add_get("/metrics", _orch_metrics)
            app.router.add_get("/health", _orch_health)
            metrics_runner = _web.AppRunner(app)
            await metrics_runner.setup()
            await _web.TCPSite(metrics_runner, "0.0.0.0", metrics_port).start()
            logger.info("📊 [ORCHESTRATOR] Metrics server on port %s", metrics_port)
        except Exception as e:
            logger.warning("⚠️ [ORCHESTRATOR] Metrics server failed: %s", e)

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
        if metrics_runner is not None:
            try:
                await metrics_runner.cleanup()
            except Exception:
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
