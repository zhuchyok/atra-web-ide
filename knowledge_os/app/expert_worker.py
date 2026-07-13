import asyncio
import atexit
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import asyncpg

try:
    from aiohttp import web

    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False
    web = None

try:
    from prometheus_client import Counter, Gauge, Histogram

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = None

if _PROMETHEUS_AVAILABLE:
    _worker_tasks_total = Counter(
        "worker_tasks_total", "Total tasks processed", ["queue", "status"]
    )
    _worker_task_duration_seconds = Histogram(
        "worker_task_duration_seconds", "Task execution duration", ["queue"]
    )
    _worker_active = Gauge(
        "worker_active_tasks", "Number of active tasks being processed", ["queue"]
    )

# Сингулярность 10.0: Импорты с поддержкой разных путей (Docker/Local)
try:
    from ai_core import run_smart_agent_async
    from expert_contract import ExpertContract
    from knowledge_fabric import get_knowledge_fabric
    from react_agent import ReActAgent
    from redis_manager import redis_manager
    from services.knowledge_service import knowledge_service
except ImportError:
    try:
        from app.ai_core import run_smart_agent_async
        from app.expert_contract import ExpertContract
        from app.knowledge_fabric import get_knowledge_fabric
        from app.react_agent import ReActAgent
        from app.redis_manager import redis_manager
        from app.services.knowledge_service import knowledge_service
    except ImportError:
        # Fallback для тестов или специфических окружений
        import sys

        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from ai_core import run_smart_agent_async
        from redis_manager import redis_manager
        from services.knowledge_service import knowledge_service

        try:
            from react_agent import ReActAgent
        except ImportError:
            ReActAgent = None

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ExpertWorker")

DB_URL = os.getenv("DATABASE_URL")
try:
    from app.expert_stream_routing import SHARED_EXPERT_STREAM, worker_stream_name
except ImportError:
    from expert_stream_routing import SHARED_EXPERT_STREAM, worker_stream_name

_expert_name_env = os.getenv("EXPERT_NAME", "").strip()
STREAM_NAME = worker_stream_name(_expert_name_env)
GROUP_NAME = "expert_workers"
CONSUMER_NAME = f"worker_{os.uname()[1]}"
RUNTIME_WORKER_HEARTBEAT_KEY = os.getenv(
    "RUNTIME_WORKER_HEARTBEAT_KEY", "runtime:expert_heartbeats"
)
RUNTIME_WORKER_HEARTBEAT_TTL_SEC = int(os.getenv("RUNTIME_WORKER_HEARTBEAT_TTL_SEC", "90"))
HITL_ENFORCE_HIGH_RISK_TASKS = os.getenv("HITL_ENFORCE_HIGH_RISK_TASKS", "false").lower() in (
    "true",
    "1",
    "yes",
)
HITL_APPROVAL_TIMEOUT_SEC = int(os.getenv("HITL_APPROVAL_TIMEOUT_SEC", "900"))
HITL_HIGH_RISK_LEVELS = {
    item.strip().lower()
    for item in os.getenv("HITL_HIGH_RISK_LEVELS", "high,critical").split(",")
    if item.strip()
}

# Глобальный пул соединений (Singularity 21.9: Один пул — один процесс)
_db_pool = None
_last_success_ts = 0

# [SINGULARITY 30.0] Preemption State Tracking
# Maps task_id (str) -> pid (int) of the background process
_active_background_tasks: Dict[str, int] = {}
# List of suspended task_ids
_suspended_tasks: List[str] = []
_inference_executor = None


def _get_inference_executor():
    """DI-style singleton ThreadPoolExecutor for heavy inference wrappers."""
    global _inference_executor
    if _inference_executor is None:
        from concurrent.futures import ThreadPoolExecutor

        _inference_executor = ThreadPoolExecutor(max_workers=1)
    return _inference_executor


def _shutdown_inference_executor():
    global _inference_executor
    if _inference_executor is not None:
        try:
            _inference_executor.shutdown(wait=False, cancel_futures=False)
        except Exception:
            pass
        _inference_executor = None


atexit.register(_shutdown_inference_executor)


def _is_truthy_env(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _extract_monster_audit_path(description: str, metadata: Dict) -> Optional[str]:
    """Extract target Python file path from monster delegation audit prompt."""
    for key in ("source_path", "file_path", "target_file", "path"):
        value = metadata.get(key) if isinstance(metadata, dict) else None
        if isinstance(value, str) and value.strip().endswith(".py"):
            return value.strip().rstrip(".,:;)")

    path_patterns = (
        r"(/app/[^\s,;:]+\.py)",
        r"(/Users/[^\s,;:]+\.py)",
        r"(knowledge_os/[^\s,;:]+\.py)",
    )
    for pattern in path_patterns:
        match = re.search(pattern, description)
        if match:
            return match.group(1).rstrip(".,:;)")
    return None


def _resolve_existing_python_path(raw_path: str) -> Optional[str]:
    if not raw_path:
        return None

    candidates = [raw_path]
    clean = raw_path.lstrip("./")
    if clean.startswith("app/"):
        candidates.append(f"/app/{clean}")
    else:
        candidates.append(f"/app/{clean}")
        candidates.append(f"/app/knowledge_os/{clean}")
    if clean.startswith("knowledge_os/"):
        candidates.append(f"/app/{clean}")
    else:
        candidates.append(f"/app/knowledge_os/{clean}")
    candidates.append(os.path.join(os.getcwd(), clean))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _run_monster_pip_runtime_audit(description: str, metadata: Dict) -> Optional[str]:
    """
    Fast deterministic audit for prompts like:
    "проверь файл ... есть ли pip install в рантайме".
    Returns None when prompt is not applicable or file is unavailable.
    """
    if not _is_truthy_env(os.getenv("MONSTER_AUDIT_FAST_PATH", "true"), default=True):
        return None

    prompt = (description or "").lower()
    if "pip install" not in prompt:
        return None
    if "проверь файл" not in prompt and "check file" not in prompt:
        return None

    raw_path = _extract_monster_audit_path(description or "", metadata or {})
    if not raw_path:
        return None
    resolved_path = _resolve_existing_python_path(raw_path)
    if not resolved_path:
        return None

    findings: List[str] = []
    try:
        with open(resolved_path, encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                normalized = line.lower()
                if "pip" not in normalized or "install" not in normalized:
                    continue
                if (
                    "subprocess." in normalized
                    or "os.system(" in normalized
                    or "python -m pip install" in normalized
                    or "python3 -m pip install" in normalized
                ):
                    findings.append(f"L{idx}: {line.strip()[:220]}")
    except Exception as err:
        return f"ПРОБЛЕМА\nФайл: {resolved_path}\nНе удалось провести проверку файла: {err}"

    if findings:
        citations = "\n".join(f"- {line}" for line in findings[:5])
        return (
            f"ПРОБЛЕМА\nФайл: {resolved_path}\nНайдены признаки runtime pip install:\n{citations}"
        )

    return (
        "ОК\n"
        f"Файл: {resolved_path}\n"
        "Runtime вызовов pip install через subprocess/os.system/python -m pip install не обнаружено."
    )


def _run_monster_secret_header_audit(description: str, metadata: Dict) -> Optional[str]:
    """
    Deterministic audit for prompts like:
    "есть ли hardcoded секреты/пароли в первых 30 строках".
    """
    if not _is_truthy_env(os.getenv("MONSTER_AUDIT_FAST_PATH", "true"), default=True):
        return None

    prompt = (description or "").lower()
    is_secret_prompt = ("hardcoded" in prompt or "секрет" in prompt or "парол" in prompt) and (
        "первых 30 строк" in prompt or "first 30 lines" in prompt
    )
    if not is_secret_prompt:
        return None

    raw_path = _extract_monster_audit_path(description or "", metadata or {})
    if not raw_path:
        return None
    resolved_path = _resolve_existing_python_path(raw_path)
    if not resolved_path:
        return None

    suspicious: List[str] = []
    # Heuristics: assignment-like patterns with sensitive keywords.
    # Skip obviously safe env lookups and placeholders.
    key_markers = ("password", "passwd", "secret", "token", "apikey", "api_key", "private_key")
    safe_markers = ("os.getenv", "environ.get", "${", "<secret>", "changeme", "example", "dummy")
    try:
        with open(resolved_path, encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                if idx > 30:
                    break
                stripped = line.strip()
                lowered = stripped.lower()
                if not stripped or stripped.startswith("#"):
                    continue
                if not any(marker in lowered for marker in key_markers):
                    continue
                if "=" not in stripped:
                    continue
                if any(safe in lowered for safe in safe_markers):
                    continue
                if re.search(r"=\s*[\"'][^\"']{3,}[\"']", stripped):
                    suspicious.append(f"L{idx}: {stripped[:220]}")
    except Exception as err:
        return f"ПРОБЛЕМА\nФайл: {resolved_path}\nНе удалось провести проверку файла: {err}"

    if suspicious:
        citations = "\n".join(f"- {line}" for line in suspicious[:5])
        return (
            "ПРОБЛЕМА\n"
            f"Файл: {resolved_path}\n"
            "В первых 30 строках найдены потенциально hardcoded секреты/пароли:\n"
            f"{citations}"
        )

    return f"ОК\nФайл: {resolved_path}\nВ первых 30 строках hardcoded секреты/пароли не обнаружены."


async def _publish_worker_runtime_heartbeat(expert_name: str):
    """Publish liveness for orchestrator assignment decisions."""
    client = await redis_manager.get_client()
    payload = json.dumps(
        {
            "ts": int(time.time()),
            "consumer": CONSUMER_NAME,
            "pid": os.getpid(),
            "expert_name": expert_name,
            "last_success_ts": _last_success_ts,
        }
    )
    await client.hset(RUNTIME_WORKER_HEARTBEAT_KEY, expert_name, payload)


async def get_db_pool():
    """Возвращает глобальный пул соединений с БД"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            DB_URL,
            min_size=1,
            max_size=5,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
    return _db_pool


# [SINGULARITY 26.1] AgentScope Actor Model Integration
# Try real agentscope first, fall back to lightweight shim (same interface)
try:
    from agentscope.agent import AgentBase
    from agentscope.message import Msg

    _AGENTSCOPE_REAL = True
    logger.info("✅ [ACTOR] Using real AgentScope library")
except ImportError:
    try:
        from agentscope.agents import AgentBase  # legacy path (agentscope < 1.0)
        from agentscope.message import Msg

        _AGENTSCOPE_REAL = True
        logger.info("✅ [ACTOR] Using real AgentScope library (legacy path)")
    except ImportError:
        try:
            from agentscope_shim import AgentBase, Msg

            _AGENTSCOPE_REAL = False
            logger.info("⚡ [ACTOR] Using AgentScope shim (minimal fallback)")
        except ImportError:
            AgentBase = object
            Msg = dict
            _AGENTSCOPE_REAL = False
            logger.warning("⚠️ [ACTOR] No AgentScope or shim available")


class VictoriaExpertActor(AgentBase):
    """
    [AGENT SCOPE] Expert as a Distributed Actor.
    Implements 'Let it crash' philosophy and isolated state.
    [SINGULARITY 26.2] Swarm & Handoff Support.
    [SINGULARITY 26.3] Event Sourcing & State Recovery.
    Works with real agentscope OR with the lightweight agentscope_shim.
    """

    def __init__(self, name: str, role: str, persona: str, task_id: str = None):
        super().__init__(name=name, sys_prompt=persona)
        self.role = role
        self.task_id = task_id
        self._db_pool = None

    async def _get_conn(self):
        if not self._db_pool:
            self._db_pool = await get_db_pool()
        return self._db_pool

    async def record_event(self, event_type: str, payload: dict):
        """Записать событие в лог (Event Sourcing)"""
        pool = await self._get_conn()

        # [FIX 28.9] Handle non-UUID task IDs (e.g. from R&D or manual triggers)
        task_uuid = None
        if self.task_id:
            try:
                task_uuid = uuid.UUID(self.task_id)
            except ValueError:
                print(f"DEBUG: Non-UUID task_id detected: {self.task_id}")
                payload["original_task_id"] = self.task_id

        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO actor_events (actor_name, task_id, event_type, payload) VALUES ($1, $2, $3, $4)",
                self.name,
                task_uuid,
                event_type,
                json.dumps(payload),
            )

    async def save_snapshot(self):
        """Сохранить полный снимок состояния"""
        state = self.state_dict()
        pool = await self._get_conn()

        task_uuid = None
        if self.task_id:
            try:
                task_uuid = uuid.UUID(self.task_id)
            except ValueError:
                pass

        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO actor_states (actor_name, task_id, state_data) VALUES ($1, $2, $3)",
                self.name,
                task_uuid,
                json.dumps(state),
            )

    async def recover_state(self):
        """Восстановить состояние из последнего снимка и лога событий"""
        if not self.task_id:
            return

        task_uuid = None
        try:
            task_uuid = uuid.UUID(self.task_id)
        except ValueError:
            return  # Cannot recover if not a valid UUID in DB

        pool = await self._get_conn()
        async with pool.acquire() as conn:
            snapshot = await conn.fetchrow(
                "SELECT state_data FROM actor_states WHERE actor_name = $1 AND task_id = $2 ORDER BY created_at DESC LIMIT 1",
                self.name,
                task_uuid,
            )
            if snapshot:
                self.load_state_dict(json.loads(snapshot["state_data"]))
                logger.info(f"🔄 [RECOVERY] {self.name} restored from snapshot.")

    def reply(self, x: dict = None) -> dict:
        # Sync stub for AgentScope pipeline compatibility.
        # Real async processing goes through process_async() called from process_task().
        logger.info(f"🎭 [ACTOR:{self.name}] Processing message (sync stub)...")
        if x and "content" in x:
            asyncio.create_task(self.record_event("receive_message", {"content": x["content"]}))
        res = {
            "role": "assistant",
            "content": f"[Actor {self.name}: use process_async() for real work]",
            "name": self.name,
        }
        asyncio.create_task(self.record_event("reply_generated", res))
        return res

    async def process_async(self, task_description: str, category: str = "general") -> str:
        """Real async task processing via ai_core (the live replacement for stub reply())."""
        await self.record_event("task_started", {"description": task_description[:200]})

        # [SINGULARITY 28.2] Add contract enforcement to prompt
        contract_instruction = ExpertContract.format_prompt_instruction()
        full_prompt = f"{task_description}\n\n{contract_instruction}"

        result = await run_smart_agent_async(
            full_prompt,
            expert_name=self.name,
            category=category,
        )
        text = str(result.get("result") if isinstance(result, dict) else result)
        await self.record_event("task_finished", {"result_len": len(text)})
        return text

    async def initiate_handoff(
        self, to_expert: str, task: str, context: dict, contract: dict = None
    ):
        """Инициализировать передачу задачи другому эксперту (Singularity 26.2)"""
        try:
            await self.record_event("handoff_initiated", {"to": to_expert, "task": task})
            from explicit_handoffs import get_handoff_manager

            manager = get_handoff_manager()
            if manager:
                handoff = manager.create_handoff(
                    from_agent=self.name,
                    to_agent=to_expert,
                    task=task,
                    context=context,
                    expected_output=f"Result matching contract: {contract}",
                )
                if contract:
                    handoff.validation_schema = contract
                logger.info(f"🚀 [SWARM] {self.name} initiated handoff to {to_expert}")
                return handoff
        except Exception as e:
            logger.error(f"❌ [SWARM] Handoff initiation failed: {e}")
        return None


async def _mark_llm_call(conn, task_id: str) -> None:
    """[BUG FIX] Обновляет last_llm_call_at перед реальным LLM-вызовом.
    Защита от RAG-infinite-loop: сбрасывалка проверяет это поле, а не updated_at
    (который обновляет heartbeat каждые 15с, маскируя зависание в RAG-фазе).
    Google SRE principle: track the operation that matters, not the heartbeat proxy.
    """
    try:
        try:
            uuid.UUID(str(task_id))
        except ValueError:
            return
        await conn.execute(
            "UPDATE tasks SET last_llm_call_at = NOW() WHERE id = $1 AND status = 'in_progress'",
            task_id,
        )
    except Exception as _e:
        logger.debug(f"[LLM_CALL_MARK] Failed to update last_llm_call_at for {task_id}: {_e}")


def _as_uuid_str(value: Optional[str]) -> Optional[str]:
    """Return canonical UUID string or None."""
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError):
        return None


async def _upsert_identity_mapping(conn, external_task_id: str, canonical_task_id: str) -> None:
    """Persist short-id to UUID mapping for cross-system synchronization."""
    if not external_task_id or not canonical_task_id:
        return
    if external_task_id == canonical_task_id:
        return
    try:
        await conn.execute(
            """
            INSERT INTO task_identity_map (external_task_id, canonical_task_id)
            VALUES ($1, $2::uuid)
            ON CONFLICT (external_task_id)
            DO UPDATE SET canonical_task_id = EXCLUDED.canonical_task_id,
                          updated_at = NOW()
            """,
            str(external_task_id),
            str(canonical_task_id),
        )
    except asyncpg.exceptions.UndefinedTableError:
        # Backward compatibility while migration is rolling out.
        pass
    except Exception as map_err:
        logger.debug(
            f"⚠️ [TASK-ID] Failed to upsert task identity map {external_task_id} -> {canonical_task_id}: {map_err}"
        )


async def _resolve_canonical_task_id(
    conn, external_task_id: str, metadata: dict
) -> tuple[Optional[str], str]:
    """
    Resolve canonical Postgres UUID for a task from direct ID, metadata, or mapping table.
    Returns tuple(UUID string or None, resolution source).
    """
    direct_uuid = _as_uuid_str(external_task_id)
    if direct_uuid:
        return direct_uuid, "resolved_by_direct"

    metadata = metadata or {}
    candidate_fields = (
        "canonical_task_id",
        "db_task_id",
        "parent_task_id",
        "original_task_id",
    )
    for field in candidate_fields:
        candidate_uuid = _as_uuid_str(metadata.get(field))
        if candidate_uuid:
            return candidate_uuid, "resolved_by_metadata"

    try:
        mapped_id = await conn.fetchval(
            "SELECT canonical_task_id::text FROM task_identity_map WHERE external_task_id = $1",
            str(external_task_id),
        )
        if mapped_id:
            return str(mapped_id), "resolved_by_mapping"
    except asyncpg.exceptions.UndefinedTableError:
        # Backward compatibility while migration is rolling out.
        return None, "unresolved"
    except Exception as map_err:
        logger.debug(f"⚠️ [TASK-ID] Failed to resolve mapping for {external_task_id}: {map_err}")

    # Legacy fallback: recover mapping from tasks metadata for already created verification/handoff chains.
    try:
        metadata_match = await conn.fetchval(
            """
            SELECT id::text
            FROM tasks
            WHERE metadata->>'verification_task_id' = $1
               OR metadata->>'original_task_id' = $1
               OR metadata->>'external_task_id' = $1
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            str(external_task_id),
        )
        if metadata_match:
            return str(metadata_match), "resolved_by_legacy_metadata"
    except Exception as legacy_err:
        logger.debug(
            f"⚠️ [TASK-ID] Legacy metadata fallback failed for {external_task_id}: {legacy_err}"
        )
    return None, "unresolved"


async def _bootstrap_canonical_task(
    conn, external_task_id: str, expert_name: str, description: str, metadata: dict
) -> Optional[str]:
    """
    Create a canonical tasks row for legacy/non-UUID blackboard tasks.
    This unblocks ownership/status updates in Postgres.
    """
    try:
        canonical_task_id = str(uuid.uuid4())
        safe_description = (description or "").strip() or f"Blackboard task {external_task_id}"
        title = safe_description[:200]
        metadata = metadata or {}
        merged_metadata = {
            **metadata,
            "external_task_id": external_task_id,
            "canonical_task_bootstrap": True,
        }

        assignee_expert_id = await conn.fetchval(
            "SELECT id FROM experts WHERE name = $1 LIMIT 1", expert_name
        )
        await conn.execute(
            """
            INSERT INTO tasks (id, title, description, status, priority, assignee_expert_id, metadata)
            VALUES ($1::uuid, $2, $3, 'pending', 'high', $4, $5::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            canonical_task_id,
            title,
            safe_description,
            assignee_expert_id,
            json.dumps(merged_metadata, ensure_ascii=False),
        )
        await _upsert_identity_mapping(conn, external_task_id, canonical_task_id)
        logger.warning(
            f"🆔 [TASK-ID] Bootstrapped canonical task {canonical_task_id} for external id {external_task_id}"
        )
        return canonical_task_id
    except Exception as bootstrap_err:
        logger.error(
            f"❌ [TASK-ID] Failed to bootstrap canonical task for {external_task_id}: {bootstrap_err}"
        )
        return None


async def process_task(task_data: dict):
    """Выполняет задачу и сохраняет результат."""
    task_id = str(task_data["task_id"])
    expert_name = task_data["expert_name"]
    description = task_data["description"]
    queue_name = task_data.get("queue_name", STREAM_NAME)
    metadata = task_data.get("metadata", {}) or {}
    contract = task_data.get("contract", {}) or {}
    if not isinstance(contract, dict):
        contract = {}
    contract_trace = {
        "version": str(contract.get("version") or "1"),
        "intent": contract.get("intent") or "execute_assigned_task",
        "output_schema": contract.get("output_schema") or "expert_response_v1",
        "risk_level": contract.get("risk_level") or "medium",
        "audit_required": bool(contract.get("audit_required", False)),
    }

    # [SINGULARITY 31.3] Skills injection for expert
    _expert_skills_context = ""
    try:
        from app.worker_memory import load_skills_for_expert

        _expert_skills_context = await load_skills_for_expert(expert_name, description)
        if _expert_skills_context:
            description = _expert_skills_context + "\n\n" + description
            logger.info(f"📋 [SKILLS] Injected skills for {expert_name}")
    except Exception as _sk_err:
        logger.debug(f"[SKILLS] Not available: {_sk_err}")

    def _extract_source_attribution() -> List[Dict[str, str]]:
        md = metadata if isinstance(metadata, dict) else {}
        candidates: List[Dict[str, str]] = []

        def _push(source_type: str, source_ref: str, note: str = ""):
            if not source_ref:
                return
            candidates.append(
                {
                    "source_type": source_type,
                    "source_ref": str(source_ref)[:256],
                    "note": str(note)[:256] if note else "",
                }
            )

        for key in (
            "source_refs",
            "sources",
            "citations",
            "knowledge_node_ids",
            "knowledge_ids",
            "vector_doc_ids",
        ):
            value = md.get(key)
            if isinstance(value, list):
                for item in value[:20]:
                    if isinstance(item, dict):
                        _push(
                            item.get("source_type", key),
                            item.get("source_ref") or item.get("id") or "",
                            item.get("note", ""),
                        )
                    else:
                        _push(key, str(item))

        for scalar_key in ("source", "source_path", "dataset", "doc_id", "external_task_id"):
            scalar_val = md.get(scalar_key)
            if scalar_val:
                _push(scalar_key, str(scalar_val))

        dedup: Dict[str, Dict[str, str]] = {}
        for item in candidates:
            dedup_key = f"{item['source_type']}::{item['source_ref']}"
            if dedup_key not in dedup:
                dedup[dedup_key] = item
        return list(dedup.values())[:25]

    is_vip = metadata.get("is_vip", False) or metadata.get("is_dialogue", False)
    is_rd = metadata.get("is_rd", False)
    db_task_id: Optional[str] = None
    is_valid_uuid = False
    # Ignore stale stream messages for tasks already in terminal state.
    # This prevents workers from re-processing cancelled/completed tasks after restarts.
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            current_status = await conn.fetchval(
                """
                SELECT status
                FROM tasks
                WHERE id::text = $1
                   OR COALESCE(metadata->>'external_task_id', '') = $1
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                str(task_id),
            )
            if current_status in {"cancelled", "completed", "failed"}:
                logger.info(
                    "⏭️ [STALE-STREAM] Skip task %s for %s: status=%s",
                    task_id,
                    expert_name,
                    current_status,
                )
                return
    except Exception as stale_check_err:
        logger.debug("Stale stream pre-check failed for %s: %s", task_id, stale_check_err)

    # [SINGULARITY 30.0] Task Preemption Logic
    if is_vip:
        try:
            client = await redis_manager.get_client()
            ice_mode = await client.get("system:ice_mode")
            if ice_mode:
                logger.warning(
                    f"❄️ [ICE_MODE] VIP task {task_id} detected. Suspending background tasks..."
                )
                for bg_task_id in list(_active_background_tasks.keys()):
                    if bg_task_id != task_id:
                        pid = _active_background_tasks.get(bg_task_id)
                        if pid:
                            try:
                                os.kill(pid, signal.SIGSTOP)
                                if bg_task_id not in _suspended_tasks:
                                    _suspended_tasks.append(bg_task_id)
                                logger.info(
                                    f"⏸️ [PREEMPTION] Suspended task {bg_task_id} (PID: {pid})"
                                )
                            except ProcessLookupError:
                                _active_background_tasks.pop(bg_task_id, None)
        except Exception as e:
            logger.error(f"❌ [PREEMPTION] Failed to suspend tasks: {e}")

    # [SINGULARITY 30.0] Pre-flight Memory Cleanup for heavy/R&D tasks
    if is_rd or metadata.get("heavy") or metadata.get("complex"):
        try:
            # [SINGULARITY 30.5] Predictive Unloading
            try:
                from app.model_memory_manager import get_memory_manager

                mmm = get_memory_manager()
                intensity = metadata.get("resource_intensity", "normal")
                await mmm.predictive_unload(intensity)
            except:
                pass

            import psutil

            ram_usage = psutil.virtual_memory().percent
            if ram_usage > 75:
                logger.warning(
                    f"🧹 [PRE-FLIGHT GC] High RAM usage ({ram_usage}%). Cleaning up before heavy task {task_id}..."
                )
                import ctypes
                import ctypes.util
                import gc

                gc.collect()
                try:
                    libc = ctypes.CDLL(ctypes.util.find_library("c"))
                    libc.malloc_trim(0)
                except:
                    pass

                # Trigger global model cleanup via MemoryManager if possible
                try:
                    from app.model_memory_manager import get_model_memory_manager

                    mmm = get_model_memory_manager()
                    await mmm.cleanup_unused_models(aggressive=True)
                    logger.info("✅ [PRE-FLIGHT GC] Global model cleanup completed")
                except:
                    pass
        except Exception as gc_err:
            logger.debug(f"Pre-flight GC failed: {gc_err}")

    logger.info(f"🛠️ [WORKER] Начало выполнения задачи {task_id} для {expert_name}")
    print(f"DEBUG_PRINT: task_data metadata: {task_data.get('metadata')}")

    # [SINGULARITY 29.2] Background Heartbeat Task
    async def heartbeat_loop():
        start_time = time.time()
        last_progress_notify = start_time
        try:
            from services.blackboard_service import get_blackboard_service

            bb = get_blackboard_service()
            while True:
                await bb.heartbeat_task(str(task_id), expert_name)

                # [SINGULARITY 29.4] Notify progress for long tasks (every 30 min)
                now = time.time()
                if (
                    task_data.get("metadata", {}).get("is_rd")
                    and (now - last_progress_notify) > 1800
                ):
                    try:
                        from services.notification_service import get_notification_service

                        notifier = get_notification_service()
                        duration_h = (now - start_time) / 3600
                        await notifier.notify(
                            "🧠 R&D в процессе",
                            f"Эксперт {expert_name} всё ещё синтезирует решение для: {description[:50]}...\nДлительность: {duration_h:.1f} ч.",
                            priority="low",
                            tags=["brain", "hourglass"],
                        )
                        last_progress_notify = now
                    except:
                        pass

                await asyncio.sleep(20)  # Heartbeat every 20s (TTL is 60s)
        except asyncio.CancelledError:
            pass
        except Exception as hb_err:
            logger.error(f"❌ [HEARTBEAT] Loop failed for {task_id}: {hb_err}")

    hb_task = asyncio.create_task(heartbeat_loop())

    # [SINGULARITY 30.5] Sidecar Heartbeat: Dedicated Thread for Heartbeats
    def start_sidecar_heartbeat(task_id: str, expert_name: str, task_data: dict, description: str):
        """Запускает heartbeat в отдельном потоке, чтобы не зависеть от GIL/async loop основного процесса."""
        import json
        import threading
        import time

        from redis import Redis

        def heartbeat_thread_func():
            start_time = time.time()
            last_progress_notify = start_time

            # Create a dedicated sync Redis client for the thread
            # [SINGULARITY 30.5] Use UDS if available
            redis_url = os.getenv("REDIS_URL", "redis://knowledge_os_redis:6379/0")
            try:
                if redis_url.startswith("unix://"):
                    path = redis_url.replace("unix://", "")
                    client = Redis(unix_socket_path=path, decode_responses=True)
                else:
                    # Parse host/port from redis://knowledge_os_redis:6379/0
                    import re

                    match = re.match(r"redis://([^:]+):(\d+)", redis_url)
                    if match:
                        host, port = match.groups()
                        client = Redis(host=host, port=int(port), decode_responses=True)
                    else:
                        client = Redis(host="knowledge_os_redis", port=6379, decode_responses=True)

                heartbeat_key = f"blackboard:heartbeat:{task_id}"

                while not getattr(threading.current_thread(), "stopped", False):
                    try:
                        # Direct Redis call (atomic)
                        client.set(heartbeat_key, expert_name, ex=300)

                        # Progress notification (every 30 min)
                        now = time.time()
                        if (
                            task_data.get("metadata", {}).get("is_rd")
                            and (now - last_progress_notify) > 1800
                        ):
                            # For notifications, we still use the async bus via a separate mechanism or just log
                            # In a real sidecar, we might use a dedicated notification queue
                            last_progress_notify = now

                    except Exception as e:
                        print(f"❌ [SIDECAR-HEARTBEAT] Error: {e}")

                    time.sleep(20)
            except Exception as e:
                print(f"❌ [SIDECAR-HEARTBEAT] Thread failed to start: {e}")

        thread = threading.Thread(target=heartbeat_thread_func, daemon=True)
        thread.start()
        return thread

    # Sidecar heartbeat thread is optional and may remain disabled.
    hb_thread = None

    # [SINGULARITY 30.0] Inference isolation through shared singleton executor.
    executor = _get_inference_executor()

    async def run_in_executor(func, *args):
        loop = asyncio.get_running_loop()
        # [SINGULARITY 30.0] Track PID for preemption
        # Note: ThreadPoolExecutor doesn't give us PIDs easily,
        # but expert_worker usually runs in a way that we can track the main process
        # or if it spawns subprocesses (like ReActAgent might).
        # For now, we track the current PID as a placeholder if it's an R&D task.
        if is_rd:
            _active_background_tasks[task_id] = os.getpid()

        try:
            return await loop.run_in_executor(executor, func, *args)
        finally:
            if is_rd:
                _active_background_tasks.pop(task_id, None)

    task_start_time = time.perf_counter()
    if _PROMETHEUS_AVAILABLE:
        _worker_active.labels(queue=queue_name).inc()

    # actor объявлен на уровне функции, чтобы блок except мог записать task_failed event
    actor = None

    # [SINGULARITY 24.3] Fix 3: TTL для диалоговых задач — пропускаем устаревшие
    if task_data.get("metadata", {}).get("is_dialogue"):
        created_at_str = task_data.get("created_at")
        if created_at_str:
            try:
                task_created_at = datetime.fromisoformat(created_at_str)
                age_seconds = (datetime.now(timezone.utc) - task_created_at).total_seconds()
                if age_seconds > 300:  # 5 минут
                    logger.warning(
                        f"⏭️ [STALE] Пропускаем диалоговую задачу {task_id} для {expert_name} (возраст: {age_seconds:.0f}s > 300s)"
                    )
                    if _PROMETHEUS_AVAILABLE:
                        _worker_active.labels(queue=queue_name).dec()
                    return
            except Exception as age_err:
                logger.debug(f"⚠️ [TTL] Не удалось проверить возраст задачи: {age_err}")

    try:
        # [SINGULARITY 21.9] Circuit Breaker: Таймаут задачи
        # Для диалоговых задач — 300s, иначе WORKER_TASK_TOTAL_TIMEOUT (по умолчанию 3600s)
        is_dialogue_task = bool(task_data.get("metadata", {}).get("is_dialogue"))

        # [SINGULARITY 27.2] Three-tier adaptive timeout (Netflix Hystrix + AWS practice):
        #
        #  Tier 1 — Dialogue / live chat     : 300s   (must be fast, user waiting)
        #  Tier 2 — Quick orchestrator tasks  : 900s   (simple delegated: audit, review, analysis)
        #  Tier 3 — Heavy orchestrator tasks  : 1800s  (complex: write module, refactor, deep analysis)
        #  Tier 4 — victoria_monster_delegation: 300s  (background scan, fail-fast & retry)
        #  Default (non-orchestrator)          : WORKER_TASK_TOTAL_TIMEOUT env (default 3600s)
        #
        # "Heavy" signal: title starts with "[HANDOFF" or description > 500 chars
        # or metadata.complex=true set by enhanced_orchestrator.
        #
        # Rationale: 600s was too tight for coding/refactor tasks (LLM needs 5-15 min on MLX).
        # But 3600s blocks a worker for 1 hour on a failed attempt.
        # → 900s/1800s is the sweet spot: enough for real work, fast enough for retry.
        _desc_lower = (description or "").lower()
        _looks_like_monster_prompt = "pip install" in _desc_lower and (
            "проверь файл" in _desc_lower or "check file" in _desc_lower
        )
        is_monster_audit = (
            task_data.get("metadata", {}).get("source") == "victoria_monster_delegation"
            or _looks_like_monster_prompt
        )
        is_orchestrator_task = task_data.get("category") == "orchestrator_assignment"
        _task_meta = task_data.get("metadata", {}) or {}
        _is_complex = bool(_task_meta.get("complex")) or len(task_data.get("description", "")) > 500

        # [SINGULARITY 30.2] Adaptive Timeouts based on Ice Mode
        try:
            _ice_client = await redis_manager.get_client()
            _ice_mode = await _ice_client.get("system:ice_mode")
            if _ice_mode == b"hard" or _ice_mode == "hard":
                _ice_factor = 10.0
                logger.warning(
                    f"❄️ [ADAPTIVE TIMEOUT] Hard Ice Mode detected. Increasing timeout by {_ice_factor}x"
                )
            elif _ice_mode == b"soft" or _ice_mode == "soft":
                _ice_factor = 3.0
                logger.info(
                    f"❄️ [ADAPTIVE TIMEOUT] Soft Ice Mode detected. Increasing timeout by {_ice_factor}x"
                )
            else:
                _ice_factor = 1.0
        except Exception:
            _ice_factor = 1.0

        if is_monster_audit:
            TASK_TOTAL_TIMEOUT = 300.0 * _ice_factor
        elif is_orchestrator_task:
            if _is_complex:
                # Heavy delegated task: give it up to 30 min, but env-overridable
                TASK_TOTAL_TIMEOUT = (
                    float(os.getenv("ORCHESTRATOR_HEAVY_TIMEOUT", "3600")) * _ice_factor
                )  # [FIX] 60 min for heavy
            else:
                # Quick delegated task: 15 min is enough; fail fast → retry via backoff
                TASK_TOTAL_TIMEOUT = (
                    float(os.getenv("ORCHESTRATOR_TASK_TIMEOUT", "900")) * _ice_factor
                )
        else:
            TASK_TOTAL_TIMEOUT = (
                300.0 if is_dialogue_task else float(os.getenv("WORKER_TASK_TOTAL_TIMEOUT", "3600"))
            ) * _ice_factor

        # Hard upper bound for long-running worker tasks to avoid "appears hung for hours"
        # when ice-mode multiplier is active.
        if not is_dialogue_task:
            timeout_cap = float(os.getenv("WORKER_TASK_TIMEOUT_MAX_SEC", "2700"))
            if TASK_TOTAL_TIMEOUT > timeout_cap:
                logger.warning(
                    "⛔ [TIMEOUT CAP] Capping task timeout %.0fs -> %.0fs (expert=%s task=%s)",
                    TASK_TOTAL_TIMEOUT,
                    timeout_cap,
                    expert_name,
                    task_id,
                )
                TASK_TOTAL_TIMEOUT = timeout_cap

        # [SINGULARITY 24.3] Если активен флаг dialogue_active — не-диалоговые задачи пропускаем
        # Это гарантирует что воркеры не заблокированы тяжёлыми задачами во время Живого Чата
        if not is_dialogue_task and not is_monster_audit:
            try:
                _flag_client = await redis_manager.get_client()
                _dialogue_active = await _flag_client.get("dialogue_active")
                if _dialogue_active:
                    logger.info(
                        f"⏭️ [PRIORITY] Пропускаем не-диалоговую задачу {task_id} — активен dialogue_active флаг"
                    )
                    return
            except Exception:
                pass  # Если Redis недоступен — продолжаем обычно

        # [SINGULARITY 26.2] Swarm MsgHub Context
        is_swarm = bool(task_data.get("metadata", {}).get("is_swarm", False))
        if is_swarm:
            try:
                from agentscope.msghub import msghub

                # Воркер подключается к MsgHub задачи
                logger.info(f"🐝 [SWARM] Expert {expert_name} joining MsgHub for task {task_id}")
            except ImportError:
                pass

        async with asyncio.timeout(TASK_TOTAL_TIMEOUT):
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                db_task_id, resolution_source = await _resolve_canonical_task_id(
                    conn, task_id, metadata
                )
                if not db_task_id:
                    db_task_id = await _bootstrap_canonical_task(
                        conn,
                        external_task_id=task_id,
                        expert_name=expert_name,
                        description=description,
                        metadata=metadata,
                    )
                    if db_task_id:
                        resolution_source = "resolved_by_bootstrap"
                is_valid_uuid = db_task_id is not None
                if is_valid_uuid:
                    await _upsert_identity_mapping(conn, task_id, db_task_id)
                    task_data.setdefault("metadata", {})
                    task_data["metadata"]["canonical_task_id"] = db_task_id
                    task_data["metadata"]["identity_resolution"] = resolution_source
                    try:
                        _metrics_client = await redis_manager.get_client()
                        await _metrics_client.hincrby(
                            "task:id_resolution_metrics", resolution_source, 1
                        )
                        await _metrics_client.hset(
                            "task:id_resolution_metrics",
                            "updated_at",
                            datetime.now(timezone.utc).isoformat(),
                        )
                    except Exception:
                        pass
                else:
                    logger.warning(
                        f"⚠️ [TASK-ID] No canonical UUID for {task_id}. SQL updates are skipped."
                    )
                    try:
                        _metrics_client = await redis_manager.get_client()
                        await _metrics_client.hincrby("task:id_resolution_metrics", "unresolved", 1)
                        await _metrics_client.hset(
                            "task:id_resolution_metrics",
                            "updated_at",
                            datetime.now(timezone.utc).isoformat(),
                        )
                    except Exception:
                        pass
                    await _handle_task_error(
                        task_id,
                        "unresolved canonical task id",
                        None,
                        expert_name=expert_name,
                    )
                    return
                if is_valid_uuid:
                    # [SINGULARITY 27.1] Guard: skip if task already completed/failed in DB.
                    # This prevents the stale-xclaim loop: when Ollama times out, the Redis stream
                    # message stays in XPENDING past the 5-min threshold, gets re-claimed by another
                    # worker, and the task is processed again concurrently even though it's done.
                    _row = await conn.fetchrow(
                        "SELECT status, updated_at, last_llm_call_at FROM tasks WHERE id = $1",
                        db_task_id,
                    )
                    _current_status = _row["status"] if _row else None
                    _task_updated_at = _row["updated_at"] if _row else None
                    _task_last_llm_call_at = _row["last_llm_call_at"] if _row else None
                    if _current_status in ("completed", "failed", "cancelled"):
                        logger.info(
                            f"⏭️ [SKIP] Task {task_id} already {_current_status} in DB — "
                            f"skipping re-processing (stale stream message)"
                        )
                        return
                    # Zombie guard: in_progress but without real progress means previous worker stalled.
                    # Prefer last_llm_call_at over updated_at to avoid heartbeat-masked hangs.
                    if _current_status == "in_progress" and _task_updated_at is not None:
                        _stale_guard_point = _task_last_llm_call_at or _task_updated_at
                        _age_sec = (datetime.now(timezone.utc) - _stale_guard_point).total_seconds()
                        _reclaim_after_sec = max(
                            120, int(os.getenv("WORKER_STALE_INPROGRESS_RECLAIM_SEC", "300"))
                        )
                        if _age_sec < _reclaim_after_sec:
                            logger.info(
                                f"⏭️ [SKIP] Task {task_id} in_progress, updated {_age_sec:.0f}s ago — "
                                f"another worker is likely processing it"
                            )
                            return

                    await conn.execute(
                        "UPDATE tasks SET status = 'in_progress', updated_at = NOW() WHERE id = $1",
                        db_task_id,
                    )
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                        WHERE id = $1
                        """,
                        db_task_id,
                        json.dumps(
                            {
                                "external_task_id": task_id,
                                "identity_resolution": resolution_source,
                                "processing_worker": expert_name,
                                "started_at": datetime.now(timezone.utc).isoformat(),
                                "last_progress_at": datetime.now(timezone.utc).isoformat(),
                                "task_contract": contract_trace,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    # Fetch retry_count from DB (not in Redis stream payload)
                    _db_retry_count = await conn.fetchval(
                        "SELECT COALESCE(retry_count, 0) FROM tasks WHERE id = $1", db_task_id
                    )
                    if _db_retry_count is not None:
                        task_data["retry_count"] = _db_retry_count

                await redis_manager.update_task_status(
                    task_id, "in_progress", metadata={"expert": expert_name}
                )

                # [SINGULARITY 26.3] Actor Recovery & State Management
                try:
                    actor = VictoriaExpertActor(
                        name=expert_name,
                        role="Expert",
                        persona="",
                        task_id=str(db_task_id or task_id),
                    )
                    await actor.recover_state()
                    # Записываем старт НЕМЕДЛЕННО — до LLM-вызова, чтобы событие было даже при падении
                    await actor.record_event(
                        "task_started",
                        {
                            "description": description[:200],
                            "category": task_data.get("category", "general"),
                        },
                    )
                except Exception as actor_err:
                    logger.warning(f"⚠️ [ACTOR] Recovery failed: {actor_err}")

                # 2. Выполняем через AI Core или ReAct Agent (Singularity 14.0)
                # ... (логика выбора агента) ...

                # [SINGULARITY 24.3] Живой Чат: Публикация мысли эксперта
                if task_data.get("metadata", {}).get("is_dialogue"):
                    try:
                        # [SINGULARITY 24.3] Fix: Universal import for EventBus
                        try:
                            from app.event_bus import Event, EventType, get_event_bus
                        except ImportError:
                            from event_bus import Event, EventType, get_event_bus

                        bus = get_event_bus()
                        import uuid

                        await bus.publish(
                            Event(
                                event_id=str(uuid.uuid4()),
                                event_type=EventType.EXPERT_THOUGHT,
                                payload={
                                    "dialogue_id": task_data.get("metadata", {}).get("dialogue_id"),
                                    "expert_name": expert_name,
                                    "thought": f"Приступаю к анализу вопроса: {description[:100]}...",
                                },
                                source=expert_name,
                            )
                        )
                    except Exception as e:
                        logger.debug(f"⚠️ [DIALOGUE] Failed to publish thought: {e}")

                # [SINGULARITY 24.3] Fast Path для диалоговых задач — MLX (victoria-wisdom) или Ollama (phi3.5)
                if is_dialogue_task:
                    logger.info(
                        f"🎯 [DIALOGUE FAST PATH] Запуск для {expert_name} (task {task_id})"
                    )
                    try:
                        import httpx

                        # [SINGULARITY 25.0] Expert Priority Detection for Dialogue
                        is_vip_expert = False
                        try:
                            # NOTE: do not shadow outer `conn` from task transaction scope.
                            # Shadowing caused "connection has been released back to the pool"
                            # when later task status updates reused the wrong handle.
                            async with pool.acquire() as priority_conn:
                                expert_priority = await priority_conn.fetchval(
                                    "SELECT priority FROM experts WHERE name = $1", expert_name
                                )
                                if expert_priority == "VIP":
                                    is_vip_expert = True
                                    logger.info(
                                        f"🌟 [VIP DIALOGUE] Expert {expert_name} has VIP priority"
                                    )
                        except Exception as e:
                            logger.debug(f"Failed to fetch expert priority for dialogue: {e}")

                        _ollama_base = (
                            os.getenv("OLLAMA_BASE_URL")
                            or os.getenv("OLLAMA_API_URL")
                            or "http://host.docker.internal:11434"
                        )
                        _mlx_base = "http://host.docker.internal:11435"
                        # Prefer explicit DIALOGUE_MODEL, but default to a fast local model
                        # to keep expert dialogue responses within collection timeout.
                        _dialogue_model = os.getenv(
                            "DIALOGUE_MODEL",
                            os.getenv("DIALOGUE_FALLBACK_MODEL", "phi3.5:3.8b"),
                        )

                        # [SINGULARITY 27.2] DNA-Aware Dialogue: Use ExpertDNAManager for personas
                        try:
                            from expert_dna_manager import get_expert_dna_manager

                            dna_mgr = get_expert_dna_manager()
                            _expert_dna = await dna_mgr.get_expert_dna(expert_name)
                            if _expert_dna:
                                _persona = _expert_dna
                            else:
                                _persona = (
                                    f"Ты — {expert_name}, эксперт корпорации Singularity 21.5."
                                )
                        except Exception as dna_err:
                            logger.debug(f"Failed to load DNA for dialogue: {dna_err}")
                            _persona = f"Ты — {expert_name}, эксперт корпорации Singularity 21.5."

                        _system = f"{_persona}\n\nОтвечай от первого лица кратко (2-3 предложения), в своём стиле."

                        # Очищаем description от служебного префикса "УЧАСТИЕ В ДИАЛОГЕ [id]: ..."
                        import re as _re

                        _clean_desc = _re.sub(
                            r"^УЧАСТИЕ В ДИАЛОГЕ \[[\w\-]+\]:\s*", "", description
                        ).strip()

                        _messages = [
                            {"role": "system", "content": _system},
                            {"role": "user", "content": _clean_desc},
                        ]
                        report_text = None

                        # victoria-wisdom → MLX (в Ollama не работает для чата)
                        # phi3.5/другие → Ollama (MLX накапливает stuck requests для малых моделей)
                        _use_mlx = (
                            "victoria-wisdom" in _dialogue_model or "wisdom" in _dialogue_model
                        )

                        _headers = {}
                        if is_vip_expert:
                            _headers["X-Request-Priority"] = "high"

                        if _use_mlx:
                            logger.info(f"🎯 [FAST PATH] MLX victoria-wisdom для {expert_name}")
                            try:
                                await _mark_llm_call(conn, db_task_id or task_id)
                                async with httpx.AsyncClient(timeout=300.0) as _hc:
                                    _resp = await _hc.post(
                                        f"{_mlx_base}/api/chat",
                                        json={
                                            "model": _dialogue_model,
                                            "messages": _messages,
                                            "stream": False,
                                            "options": {"num_predict": 100},
                                        },
                                        headers=_headers,
                                    )
                                    logger.info(
                                        f"🔍 [FAST PATH] MLX status={_resp.status_code} for {expert_name}"
                                    )
                                    if _resp.status_code == 200:
                                        report_text = (
                                            _resp.json().get("message", {}).get("content", "")
                                        )
                                        # Убираем артефакты модели: ведущие точки/пробелы и эхо вопроса
                                        if report_text:
                                            report_text = report_text.strip().lstrip(".\n").strip()
                                            # Regex: удаляем эхо вопроса в начале (с любыми обёртками)
                                            _echo = _re.escape(_clean_desc)
                                            report_text = _re.sub(
                                                rf"^[\s\.]*{_echo}[\s\.]*", "", report_text
                                            ).strip()
                                        logger.info(
                                            f"✅ [FAST PATH] MLX ответил для {expert_name} ({len(report_text or '')} chars)"
                                        )
                                    else:
                                        logger.warning(
                                            f"⚠️ [FAST PATH] MLX вернул {_resp.status_code}"
                                        )
                            except asyncio.CancelledError:
                                raise
                            except Exception as _mlx_err:
                                logger.warning(f"⚠️ [FAST PATH] MLX ошибка: {_mlx_err}")
                        else:
                            # Ollama с retry для небольших моделей (phi3.5 и др.)
                            for _attempt in range(3):
                                try:
                                    await _mark_llm_call(conn, db_task_id or task_id)
                                    async with httpx.AsyncClient(timeout=180.0) as _hc:
                                        _resp = await _hc.post(
                                            f"{_ollama_base}/api/chat",
                                            json={
                                                "model": _dialogue_model,
                                                "messages": _messages,
                                                "stream": False,
                                            },
                                            headers=_headers,
                                        )
                                        logger.info(
                                            f"🔍 [FAST PATH] Ollama status={_resp.status_code} for {expert_name} (attempt {_attempt + 1})"
                                        )
                                        if _resp.status_code == 200:
                                            report_text = (
                                                _resp.json().get("message", {}).get("content", "")
                                            )
                                            logger.info(
                                                f"✅ [FAST PATH] Ollama ответил для {expert_name} ({len(report_text or '')} chars)"
                                            )
                                            break
                                        elif _resp.status_code == 503 and _attempt < 2:
                                            logger.info(
                                                f"⏳ [FAST PATH] Ollama 503, retry {_attempt + 1}/3 через 5s..."
                                            )
                                            await asyncio.sleep(5)
                                        else:
                                            logger.warning(
                                                f"⚠️ [FAST PATH] Ollama вернул {_resp.status_code}: {_resp.text[:100]}"
                                            )
                                            break
                                except asyncio.CancelledError:
                                    raise
                                except Exception as _oe:
                                    logger.warning(
                                        f"⚠️ [FAST PATH] Ollama exception (attempt {_attempt + 1}): {_oe}"
                                    )
                                    if _attempt < 2:
                                        await asyncio.sleep(5)
                        # ... (rest of the code) ...

                        if not report_text:
                            raise ValueError(f"LLM не ответил ({'MLX' if _use_mlx else 'Ollama'})")
                        logger.info(
                            f"✅ [DIALOGUE FAST PATH] {expert_name} ответил ({len(report_text)} chars)"
                        )
                    except Exception as fast_err:
                        logger.warning(f"⚠️ [DIALOGUE FAST PATH] Fallback на ai_core: {fast_err}")

                        # [SINGULARITY 24.7] Retry Intelligence: Downgrade model on failure
                        _retry_category = "fast" if "wisdom" in _dialogue_model else "general"
                        await _mark_llm_call(conn, db_task_id or task_id)
                        report = await run_smart_agent_async(
                            description,
                            expert_name=expert_name,
                            category=_retry_category,
                            is_vip=True,
                        )
                        report_text = str(
                            report.get("result") if isinstance(report, dict) else report
                        )

                elif is_monster_audit:
                    report_text = _run_monster_pip_runtime_audit(description, metadata)
                    if not report_text:
                        report_text = _run_monster_secret_header_audit(description, metadata)
                    if report_text:
                        logger.info(
                            "⚡ [MONSTER FAST AUDIT] Completed deterministic scan for %s",
                            task_id,
                        )
                    else:
                        await _mark_llm_call(conn, db_task_id or task_id)
                        report = await run_smart_agent_async(
                            description,
                            expert_name=expert_name,
                            category="general",
                            is_vip=False,
                        )
                        report_text = str(
                            report.get("result") if isinstance(report, dict) else report
                        )
                elif task_data.get("metadata", {}).get("complex") or expert_name == "Виктория":
                    logger.info(f"🧠 [WORKER] Используем ReAct Agent для сложной задачи {task_id}")
                    try:
                        model_hint = task_data.get("metadata", {}).get("model_hint")
                        print(
                            f"DEBUG_PRINT: Initializing ReActAgent with model: {model_hint or 'victoria-wisdom-v3.5:latest'}"
                        )
                        agent = ReActAgent(
                            agent_name=expert_name,
                            model_name=model_hint or "victoria-wisdom-v3.5:latest",
                        )
                        print(f"DEBUG_PRINT: Calling agent.run() for task {task_id}")
                        await _mark_llm_call(conn, db_task_id or task_id)

                        # [SINGULARITY 27.2] Event Sourcing: Record task start if actor exists
                        if actor:
                            await actor.record_event(
                                "react_agent_started",
                                {"model": model_hint or "victoria-wisdom-v3.5:latest"},
                            )

                        report = await agent.run(goal=description)
                        print(f"DEBUG_PRINT: agent.run() finished for task {task_id}")
                        # [SINGULARITY 21.26] Fix: ReActAgent returns 'response', not 'result'
                        if isinstance(report, dict) and "response" in report:
                            report_text = report["response"]
                        else:
                            report_text = str(
                                report.get("result") if isinstance(report, dict) else report
                            )

                        # [SINGULARITY 27.2] Event Sourcing: Record task completion
                        if actor:
                            await actor.record_event(
                                "react_agent_completed", {"result_len": len(report_text or "")}
                            )
                    except Exception as e:
                        logger.error(f"⚠️ Ошибка ReAct Agent, fallback на AI Core: {e}")
                        await _mark_llm_call(conn, db_task_id or task_id)

                        if actor:
                            await actor.record_event("react_agent_failed", {"error": str(e)})

                        report = await run_smart_agent_async(
                            description,
                            expert_name=expert_name,
                            category=task_data.get("category", "general"),
                            is_vip=is_dialogue_task,
                        )
                        report_text = str(
                            report.get("result") if isinstance(report, dict) else report
                        )
                else:
                    await _mark_llm_call(conn, db_task_id or task_id)

                    # [SINGULARITY 27.2] Event Sourcing: Record AI Core start
                    if actor:
                        await actor.record_event(
                            "ai_core_started", {"category": task_data.get("category", "general")}
                        )

                    report = await run_smart_agent_async(
                        description,
                        expert_name=expert_name,
                        category=task_data.get("category", "general"),
                        is_vip=is_dialogue_task,
                    )
                    report_text = str(report.get("result") if isinstance(report, dict) else report)

                    # [SINGULARITY 27.2] Event Sourcing: Record AI Core completion
                    if actor:
                        await actor.record_event(
                            "ai_core_completed", {"result_len": len(report_text or "")}
                        )

                # 3. Сохраняем результат
                if isinstance(report_text, dict):
                    report_text = json.dumps(report_text, ensure_ascii=False, indent=2)
                else:
                    report_text = str(report_text)

                # Guardrail: do not mark task completed when model returned stub/unavailable response.
                _report_low = (report_text or "").lower()
                _stub_markers = (
                    "[system: all llm sources unavailable]",
                    "all llm sources unavailable",
                    "все источники недоступны",
                    "llm sources unavailable",
                )
                if any(marker in _report_low for marker in _stub_markers):
                    raise RuntimeError("All LLM sources unavailable (stub response)")

                # [SINGULARITY 26.2] Swarm Handoff Detection
                if "HANDOFF:" in report_text and "TASK:" in report_text:
                    try:
                        import re as _re

                        # [FIX] Support both latin and cyrillic expert names (Игорь, Viktor, etc.)
                        _to_expert = _re.search(r"HANDOFF:\s*@?([\w\u0400-\u04FF_-]+)", report_text)
                        _task_desc = _re.search(
                            r"TASK:\s*(.+?)(?=CONTRACT:|HANDOFF:|$)", report_text, _re.DOTALL
                        )
                        _contract = _re.search(r"CONTRACT:\s*(\{.*?\})", report_text, _re.DOTALL)

                        if _to_expert and _task_desc:
                            to_name = _to_expert.group(1)
                            task_msg = _task_desc.group(1).strip()
                            contract_json = None
                            if _contract:
                                try:
                                    contract_json = json.loads(_contract.group(1))
                                except:
                                    pass

                            from explicit_handoffs import get_handoff_manager

                            manager = get_handoff_manager()
                            if manager:
                                manager.create_handoff(
                                    from_agent=expert_name,
                                    to_agent=to_name,
                                    task=task_msg,
                                    context={
                                        "parent_result": report_text,
                                        "parent_task_id": task_id,
                                    },
                                    expected_output=f"Swarm handoff result for {to_name}",
                                )
                                if contract_json:
                                    h_list = manager.get_pending_handoffs(to_name)
                                    if h_list:
                                        h_list[0].validation_schema = contract_json

                            # [SINGULARITY 27.0] Create real DB subtask so workers actually pick it up
                            # parent_task_id links this new task to its origin for tracing
                            try:
                                import uuid as _uuid_mod

                                _subtask_id = _uuid_mod.uuid4()
                                _subtask_title = f"[HANDOFF from {expert_name}] {task_msg[:120]}"
                                _subtask_meta = json.dumps(
                                    {
                                        "handoff_from": expert_name,
                                        "parent_task_id": str(task_id),
                                        "contract": contract_json,
                                        "is_handoff": True,
                                    }
                                )
                                # Idempotent insert: wrap in try/except for unique violation (23505).
                                # The dedup index prevents duplicate pending/in_progress tasks with same title.
                                # Erlang principle: let it crash → catch gracefully, not loudly fail.
                                try:
                                    await conn.execute(
                                        """
                                        INSERT INTO tasks
                                            (id, parent_task_id, title, description, status, priority,
                                             metadata, created_at, updated_at)
                                        VALUES
                                            ($1, $2, $3, $4, 'pending', 5, $5::jsonb, NOW(), NOW())
                                        """,
                                        _subtask_id,
                                        uuid.UUID(str(db_task_id)) if is_valid_uuid else None,
                                        _subtask_title,
                                        task_msg,
                                        _subtask_meta,
                                    )
                                except Exception as _ins_err:
                                    _err_str = str(_ins_err)
                                    if (
                                        "unique" in _err_str.lower()
                                        or "23505" in _err_str
                                        or "dedup" in _err_str.lower()
                                    ):
                                        logger.info(
                                            f"⏭️ [SWARM] Subtask already queued for handoff from {expert_name} "
                                            f"(dedup — idempotent skip)"
                                        )
                                    else:
                                        raise
                                logger.info(
                                    f"🐝 [SWARM] {expert_name} → {to_name}: subtask {_subtask_id} created in DB "
                                    f"(parent={task_id})"
                                )
                                await actor.record_event(
                                    "handoff_created",
                                    {
                                        "to_agent": to_name,
                                        "subtask_id": str(_subtask_id),
                                        "task_msg": task_msg[:200],
                                    },
                                )
                            except Exception as _sub_err:
                                logger.error(
                                    f"❌ [SWARM] Failed to create subtask in DB: {_sub_err}"
                                )

                    except Exception as he:
                        logger.error(f"❌ [SWARM] Handoff detection failed: {he}")

                # [SINGULARITY 27.0] Stub/unavailable result → requeue with exponential backoff
                # "Все источники недоступны" = ALL LLM routes failed — not a result, just a miss.
                # Do NOT mark completed; put back in queue so a worker can retry when LLMs free up.
                _STUB_MARKER = "все источники недоступны"
                _MAX_RETRIES = int(os.getenv("TASK_MAX_RETRIES", "3"))
                _is_stub = _STUB_MARKER in report_text.lower()
                _retry_count = task_data.get("retry_count") or 0

                if _is_stub and is_valid_uuid:
                    if _retry_count < _MAX_RETRIES:
                        _backoff_minutes = 2**_retry_count * 5  # 5, 10, 20 minutes
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET status = 'pending',
                                retry_count = retry_count + 1,
                                retry_after = NOW() + ($2 || ' minutes')::INTERVAL,
                                updated_at = NOW()
                            WHERE id = $1
                            """,
                            db_task_id,
                            str(_backoff_minutes),
                        )
                        await redis_manager.update_task_status(task_id, "pending")
                        logger.warning(
                            f"♻️ [REQUEUE] Task {task_id} got stub result "
                            f"(attempt {_retry_count + 1}/{_MAX_RETRIES}) "
                            f"— requeueing in {_backoff_minutes}m"
                        )
                        return
                    else:
                        logger.warning(
                            f"🚫 [REQUEUE] Task {task_id} exhausted {_MAX_RETRIES} retries — marking failed"
                        )
                        await conn.execute(
                            "UPDATE tasks SET status='failed', result=$2, updated_at=NOW() WHERE id=$1",
                            db_task_id,
                            report_text,
                        )
                        await redis_manager.update_task_status(
                            task_id, "failed", result=report_text
                        )
                        return

                # [SINGULARITY 31.3] Board consultation for high-priority tasks
                priority = task_data.get("metadata", {}).get("priority", 5)
                if isinstance(priority, str):
                    priority = 8 if priority.lower() == "high" else 5

                if priority >= 8:
                    try:
                        from strategic_board import consult_board

                        await consult_board(
                            question=f"Задача приоритета {priority}: {goal[:100]}",
                            source="task_escalation",
                        )
                    except Exception as board_err:
                        logger.warning(f"[BOARD] Consult failed (non-critical): {board_err}")

                    # [SINGULARITY 28.7] Mandatory Adversarial Trust Gate
                    try:
                        from adversarial_critic import verify_high_priority_task

                        verification = await verify_high_priority_task(str(task_id), report_text)
                        verification_reason = str(
                            verification.get("verification_reason") or ""
                        ).strip()
                        degraded_reasons = {
                            "critic_output_parse_error",
                            "critic_unavailable_or_empty_output",
                        }
                        if verification_reason in degraded_reasons:
                            logger.warning(
                                "⚠️ [TRUST GATE] Degraded verification for task %s: %s",
                                task_id,
                                verification_reason,
                            )
                        if not verification.get("survived", True):
                            logger.error(
                                f"💀 [TRUST GATE] Task {task_id} REJECTED by Critic: {verification.get('attack_report')}"
                            )
                            raise ValueError(
                                f"Adversarial Rejection: {verification.get('attack_report')}"
                            )
                        logger.info(
                            "🛡️ [TRUST GATE] Task %s SURVIVED adversarial attack (reason=%s).",
                            task_id,
                            verification_reason or "unspecified",
                        )
                    except Exception as gate_err:
                        if "Adversarial Rejection" in str(gate_err):
                            raise
                        logger.warning(
                            f"⚠️ [TRUST GATE] Verification skipped due to error: {gate_err}"
                        )

                # [SINGULARITY 29.7] Auto-Verification Loop for R&D
                is_rd = task_data.get("metadata", {}).get("is_rd")
                is_verification = task_data.get("metadata", {}).get("is_verification")

                if is_rd and not is_verification:
                    logger.info(
                        f"🔍 [SINGULARITY 29.7] Triggering Cross-Verification for R&D task {task_id}"
                    )
                    try:
                        from services.blackboard_service import get_blackboard_service

                        bb = get_blackboard_service()

                        verification_task_id = f"VERIFY_{task_id}_{uuid.uuid4().hex[:8]}"
                        verification_goal = f"### CROSS-VERIFICATION REQUIRED\n\nExpert {expert_name} has proposed an R&D solution for: {description[:100]}...\n\n**PROPOSED SOLUTION:**\n{report_text[:1000]}\n\n**TASK:** Audit this solution for technical feasibility, security risks, and architectural alignment. Provide a 'GO' or 'REJECT' decision with reasoning."

                        # Target a different expert (e.g. QA or Security)
                        target_expert = "Анна" if expert_name != "Анна" else "Алексей"

                        await bb.post_goal(
                            verification_task_id,
                            verification_goal,
                            {
                                "original_task_id": str(task_id),
                                "canonical_task_id": db_task_id,
                                "source_expert": expert_name,
                                "target_expert": target_expert,
                                "is_verification": True,
                                "priority": "high",
                                "category": "r&d_optimization",
                            },
                        )
                        logger.info(
                            f"✅ [SINGULARITY 29.7] Verification task {verification_task_id} posted to Blackboard."
                        )

                        # We mark the original as 'completed' but with a note that it's pending verification
                        # In a more complex system, we'd have a 'pending_verification' status.
                        # For now, we use metadata to track this.
                        if is_valid_uuid:
                            await conn.execute(
                                "UPDATE tasks SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb WHERE id = $1",
                                db_task_id,
                                json.dumps(
                                    {
                                        "verification_status": "pending",
                                        "verification_task_id": verification_task_id,
                                    }
                                ),
                            )
                    except Exception as v_err:
                        logger.error(
                            f"❌ [SINGULARITY 29.7] Failed to trigger verification: {v_err}"
                        )

                source_attribution = _extract_source_attribution()
                effective_risk = str(
                    metadata.get("risk_level") or contract_trace.get("risk_level") or "medium"
                ).lower()
                hitl_payload = {
                    "enabled": HITL_ENFORCE_HIGH_RISK_TASKS,
                    "checkpoint": "pre_completion_high_risk",
                    "requested": False,
                    "required": effective_risk in HITL_HIGH_RISK_LEVELS,
                }
                if effective_risk in HITL_HIGH_RISK_LEVELS:
                    try:
                        from human_approval import get_approval_system

                        approval_system = get_approval_system()
                        approval_id = await approval_system.request_approval(
                            requester_agent=expert_name,
                            action_description=f"production high-risk task completion: {task_id} {description[:120]}",
                            estimated_impact=f"risk={effective_risk}; source_count={len(source_attribution)}",
                            trace_id=str(task_id),
                        )
                        if approval_id:
                            hitl_payload["requested"] = True
                            hitl_payload["approval_id"] = approval_id
                            hitl_payload["status"] = "pending"
                            if HITL_ENFORCE_HIGH_RISK_TASKS:
                                approved = await approval_system.wait_for_approval(
                                    approval_id, timeout_seconds=HITL_APPROVAL_TIMEOUT_SEC
                                )
                                hitl_payload["status"] = (
                                    "approved" if approved else "rejected_or_timeout"
                                )
                                if not approved and is_valid_uuid:
                                    await conn.execute(
                                        """
                                        UPDATE tasks
                                        SET status = 'pending',
                                            retry_after = NOW() + INTERVAL '5 minutes',
                                            updated_at = NOW(),
                                            metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                                        WHERE id = $1
                                        """,
                                        db_task_id,
                                        json.dumps(
                                            {
                                                "hitl_status": "awaiting_approval",
                                                "hitl_approval_id": approval_id,
                                                "last_progress_at": datetime.now(
                                                    timezone.utc
                                                ).isoformat(),
                                            },
                                            ensure_ascii=False,
                                        ),
                                    )
                                    await redis_manager.update_task_status(task_id, "pending")
                                    logger.warning(
                                        "⏸️ [HITL] Task %s paused pending approval id=%s",
                                        task_id,
                                        approval_id,
                                    )
                                    return
                    except Exception as hitl_err:
                        logger.warning(
                            "⚠️ [HITL] checkpoint failed for task=%s: %s", task_id, hitl_err
                        )
                        hitl_payload["error"] = str(hitl_err)[:300]

                audit_trail = {
                    "schema": "expert_audit_v1",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "risk_level": effective_risk,
                    "result_sha256": hashlib.sha256(
                        report_text.encode("utf-8", errors="ignore")
                    ).hexdigest(),
                    "source_count": len(source_attribution),
                    "source_attribution": source_attribution,
                    "contract_trace": contract_trace,
                    "hitl": hitl_payload,
                }

                completion_committed = True
                global _last_success_ts
                _last_success_ts = int(time.time())
                if is_valid_uuid:
                    print(f"DEBUG_PRINT: Updating task {task_id} to completed in DB")
                    _update_res = await conn.execute(
                        """
                        UPDATE tasks
                        SET status = 'completed',
                            result = $2,
                            completed_at = NOW(),
                            updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb
                        WHERE id = $1
                          AND status = 'in_progress'
                    """,
                        db_task_id,
                        report_text,
                        json.dumps(
                            {
                                "completion_reason": "worker_success",
                                "completed_by": expert_name,
                                "last_progress_at": datetime.now(timezone.utc).isoformat(),
                                "task_contract_version": contract_trace["version"],
                                "task_contract_output_schema": contract_trace["output_schema"],
                                "task_contract_risk_level": contract_trace["risk_level"],
                                "source_attribution": source_attribution,
                                "audit_trail": audit_trail,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    try:
                        _updated_rows = int(str(_update_res).split()[-1])
                    except Exception:
                        _updated_rows = 0
                    if _updated_rows == 0:
                        completion_committed = False
                        _final_status = await conn.fetchval(
                            "SELECT status FROM tasks WHERE id = $1", db_task_id
                        )
                        logger.info(
                            "⏭️ [WORKER] Completion skipped for %s: current_status=%s",
                            task_id,
                            _final_status,
                        )

                if completion_committed:
                    try:
                        await redis_manager.update_task_status(
                            task_id, "completed", result=report_text
                        )
                    except Exception as status_err:
                        logger.warning(
                            "⚠️ [WORKER] Redis completed status update failed for %s: %s",
                            task_id,
                            status_err,
                        )

                # [SINGULARITY 26.3] Extract reasoning_trace and store in task metadata
                if "<reasoning_trace>" in report_text and is_valid_uuid:
                    try:
                        import re as _re

                        _trace_match = _re.search(
                            r"<reasoning_trace>(.*?)</reasoning_trace>", report_text, _re.DOTALL
                        )
                        if _trace_match:
                            _trace = _trace_match.group(1).strip()
                            await conn.execute(
                                "UPDATE tasks SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb WHERE id = $1",
                                db_task_id,
                                json.dumps({"reasoning_trace": _trace[:2000]}),
                            )
                            logger.info(f"🧠 [REFLECTION] reasoning_trace saved for task {task_id}")
                    except Exception as _te:
                        logger.debug(f"reasoning_trace extraction failed: {_te}")

                # [SINGULARITY 26.3] Final State Snapshot
                if actor:
                    try:
                        await actor.save_snapshot()
                        await actor.record_event("task_completed", {"result_len": len(report_text)})
                    except Exception:
                        pass

                # Сингулярность 10.0: Снимаем блокировку идемпотентности
                await redis_manager.release_task_lock(task_id)

                # 4. Сохраняем инсайт в базу знаний (через Knowledge Fabric)
                try:
                    fabric = get_knowledge_fabric()
                    await fabric.store(
                        report_text,
                        expert_name,
                        metadata={
                            "task_id": task_id,
                            "source": "worker_service",
                            "fabric_unified": True,
                        },
                    )
                except Exception as fabric_err:
                    logger.warning(
                        "⚠️ [WORKER] Non-critical fabric.store failed for %s: %s",
                        task_id,
                        fabric_err,
                    )

                # [SINGULARITY 30.5] Stop Sidecar Heartbeat (if enabled)
                if hb_thread is not None:
                    hb_thread.stopped = True

                try:
                    from services.blackboard_service import get_blackboard_service

                    bb = get_blackboard_service()
                    client = await bb.redis.get_client()
                    await client.delete(f"blackboard:heartbeat:{task_id}")
                    # [SINGULARITY 31.2] Release task from expert's active set
                    await bb.release_task(task_id, expert_name)

                    # [SINGULARITY 29.3] Notify R&D completion
                    if task_data.get("metadata", {}).get("is_rd"):
                        try:
                            from services.notification_service import get_notification_service

                            notifier = get_notification_service()
                            await notifier.notify(
                                "🚀 R&D задача завершена",
                                f"Эксперт {expert_name} завершил R&D: {description[:100]}...",
                                priority="high",
                                tags=["rocket", "brain"],
                            )
                        except:
                            pass
                except:
                    pass

                # [SINGULARITY 24.3] Живой Чат: Публикация ответа эксперта в EventBus
                if task_data.get("metadata", {}).get("is_dialogue"):
                    try:
                        # [SINGULARITY 24.3] Fix: Universal import for EventBus
                        try:
                            from app.event_bus import Event, EventType, get_event_bus
                        except ImportError:
                            from event_bus import Event, EventType, get_event_bus

                        import uuid

                        bus = get_event_bus()
                        dialogue_id = task_data.get("metadata", {}).get("dialogue_id")

                        await bus.publish(
                            Event(
                                event_id=str(uuid.uuid4()),
                                event_type=EventType.EXPERT_RESPONSE,
                                payload={
                                    "dialogue_id": dialogue_id,
                                    "expert_name": expert_name,
                                    "response": report_text,
                                },
                                source=expert_name,
                            )
                        )
                        logger.info(
                            f"🎭 [DIALOGUE] Expert {expert_name} published response for {dialogue_id}"
                        )
                    except Exception as e:
                        logger.error(f"⚠️ [DIALOGUE] Failed to publish response: {e}")

                # [SINGULARITY 30.0] Post-task Memory Release Hook
                try:
                    import psutil

                    ram_usage = psutil.virtual_memory().percent
                    if ram_usage > 85:
                        used_model = metadata.get("model_hint") or os.getenv("VICTORIA_MODEL")
                        # Never unload immortal models
                        from ollama_keep_alive_policy import IMMORTAL_MODELS

                        is_immortal = any(m in (used_model or "") for m in IMMORTAL_MODELS)

                        if used_model and not is_immortal:
                            logger.warning(
                                f"♻️ [POST-TASK] High RAM ({ram_usage}%). Releasing model {used_model}..."
                            )
                            import httpx

                            ollama_base = os.getenv(
                                "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
                            )
                            async with httpx.AsyncClient(timeout=5.0) as _hc:
                                await _hc.post(
                                    f"{ollama_base}/api/generate",
                                    json={"model": used_model, "prompt": "", "keep_alive": 0},
                                )
                            logger.info(f"✅ [POST-TASK] Model {used_model} released from VRAM/RAM")
                except Exception as release_err:
                    logger.debug(f"Post-task memory release failed: {release_err}")

                logger.info(f"✅ [WORKER] Задача {task_id} успешно завершена")

                if _PROMETHEUS_AVAILABLE:
                    duration = time.perf_counter() - task_start_time
                    _worker_tasks_total.labels(queue=queue_name, status="completed").inc()
                    _worker_task_duration_seconds.labels(queue=queue_name).observe(duration)
                    _worker_active.labels(queue=queue_name).dec()

                # [SWISS-CLOCK] PUBLISH completion event для pub/sub подписчиков (perpetual_evolution и др.)
                try:
                    _redis_client = await redis_manager.get_client()
                    await _redis_client.publish(f"task:completed:{task_id}", "completed")
                except Exception as _pub_err:
                    logger.debug(f"[PUBSUB] Publish failed (non-critical): {_pub_err}")

                # [SINGULARITY 26.4] Детерминированный handoff — без LLM-тегов
                try:
                    from explicit_handoffs import detect_deterministic_handoff

                    auto_handoff = detect_deterministic_handoff(
                        from_agent=expert_name,
                        task_description=description,
                        task_result=report_text[:300],
                        category=task_data.get("category", "general"),
                    )
                    if auto_handoff:
                        logger.info(
                            f"🔀 [AUTO-HANDOFF] {expert_name} → {auto_handoff.to_agent} "
                            f"| ID: {auto_handoff.handoff_id}"
                        )

                        # [SINGULARITY 28.6] Peer-to-Peer Market: Post handoff to Blackboard
                        try:
                            from services.blackboard_service import get_blackboard_service

                            blackboard = get_blackboard_service()
                            await blackboard.post_goal(
                                auto_handoff.handoff_id,
                                f"HANDOFF from {expert_name}: {auto_handoff.task}",
                                {
                                    "original_task_id": str(task_id),
                                    "canonical_task_id": db_task_id,
                                    "target_expert": auto_handoff.to_agent,
                                    "priority": "high",
                                    "is_handoff": True,
                                },
                            )
                        except Exception as h_err:
                            logger.warning(f"⚠️ [MARKET] Failed to post handoff: {h_err}")

                        if actor:
                            await actor.record_event(
                                "handoff_created",
                                {
                                    "to_agent": auto_handoff.to_agent,
                                    "handoff_id": auto_handoff.handoff_id,
                                },
                            )
                except Exception as _hf_err:
                    logger.debug(f"[HANDOFF] Deterministic check failed (non-critical): {_hf_err}")

    except asyncio.TimeoutError:
        logger.error(
            f"⌛ [CIRCUIT BREAKER] Задача {task_id} прервана по таймауту ({TASK_TOTAL_TIMEOUT}с)"
        )
        error_msg = f"Task timed out after {TASK_TOTAL_TIMEOUT}s (Circuit Breaker)"

        # [SINGULARITY 30.5] Stop Sidecar Heartbeat
        if hb_thread is not None:
            hb_thread.stopped = True

            # [SINGULARITY 30.0] Resume suspended tasks on timeout
            try:
                await actor.record_event(
                    "task_failed", {"reason": "timeout", "timeout_sec": TASK_TOTAL_TIMEOUT}
                )
            except Exception:
                pass
        if _PROMETHEUS_AVAILABLE:
            _worker_tasks_total.labels(queue=queue_name, status="timeout").inc()
            _worker_active.labels(queue=queue_name).dec()
        await _handle_task_error(task_id, error_msg, db_task_id, expert_name=expert_name)

    except Exception as e:
        logger.error(f"❌ [WORKER] Ошибка задачи {task_id}: {e}", exc_info=True)
        error_msg = str(e)
        error_type = type(e).__name__

        # [SINGULARITY 30.5] Stop Sidecar Heartbeat
        if hb_thread is not None:
            hb_thread.stopped = True

        if _PROMETHEUS_AVAILABLE:
            _worker_tasks_total.labels(queue=queue_name, status="failed").inc()
            _worker_active.labels(queue=queue_name).dec()

        # [SINGULARITY 30.0] Resume suspended tasks on error
        try:
            await _handle_task_error(
                task_id,
                f"{error_type}: {error_msg}",
                locals().get("db_task_id"),
                expert_name=expert_name,
            )
        except Exception as handle_err:
            logger.error("❌ [WORKER] _handle_task_error failed for %s: %s", task_id, handle_err)


async def _handle_task_error(
    external_task_id: str, error_msg: str, canonical_task_id: Optional[str], expert_name: str = None
):
    """
    Обработка ошибок задачи с retry-логикой.
    [SWISS-CLOCK] Унифицировано со smart_worker: transient errors → re-queue с exp backoff + jitter.
    Постоянные ошибки (attempt_count >= 3) → failed + [SINGULARITY 27.2] DNA Mutation.
    """
    import random as _random
    from datetime import datetime, timezone

    _is_transient = any(
        m in (error_msg or "").lower()
        for m in (
            "timeout",
            "503",
            "circuit breaker",
            "maximum pending",
            "все источники недоступны",
            "connection",
            "unavailable",
        )
    )

    try:
        if canonical_task_id and _is_transient:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                meta_raw = await conn.fetchval(
                    "SELECT metadata FROM tasks WHERE id = $1", canonical_task_id
                )
                try:
                    meta = json.loads(meta_raw) if isinstance(meta_raw, str) else (meta_raw or {})
                except Exception:
                    meta = {}
                attempt_count = int(meta.get("attempt_count", 0)) + 1

                # [SINGULARITY 27.2] Increased max retries: 3 → 5 for transient LLM overload.
                # Netflix Hystrix principle: distinguishing transient (Ollama busy) from permanent failures.
                # Backoff: 120s, 240s, 480s, 600s, 600s (+jitter 0-60s each)
                _MAX_ATTEMPTS = int(os.getenv("TASK_MAX_ATTEMPTS", "5"))
                if attempt_count < _MAX_ATTEMPTS:
                    # Exponential backoff + jitter (AWS best practice)
                    # Wider jitter (0-60s) spreads thundering herd when Ollama recovers
                    base = 120  # seconds (CB recovery_timeout = 120s)
                    exp_delay = min(base * (2 ** max(attempt_count - 1, 0)), 600)
                    jitter = _random.randint(0, 60)
                    retry_delay = exp_delay + jitter
                    retry_after_dt = datetime.fromtimestamp(
                        datetime.utcnow().timestamp() + retry_delay, tz=timezone.utc
                    )
                    retry_after = retry_after_dt.isoformat()

                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = 'pending',
                            updated_at = NOW(),
                            retry_after = $3::timestamptz,
                            metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                        WHERE id = $1
                        """,
                        canonical_task_id,
                        json.dumps(
                            {
                                "last_attempt_failed": True,
                                "attempt_count": attempt_count,
                                "last_error": error_msg[:300],
                                "next_retry_after": retry_after,
                                "llm_unavailable": True,
                            }
                        ),
                        retry_after_dt,
                    )
                    await redis_manager.update_task_status(external_task_id, "pending")
                    logger.warning(
                        f"⏳ [RETRY] Task {external_task_id} re-queued (attempt {attempt_count}/{_MAX_ATTEMPTS}, "
                        f"retry in {retry_delay}s): {error_msg[:80]}"
                    )
                    await redis_manager.release_task_lock(external_task_id)
                    # [SINGULARITY 31.2] Release task from expert's active set in Blackboard for retry
                    try:
                        from services.blackboard_service import get_blackboard_service

                        bb = get_blackboard_service()
                        await bb.release_task(external_task_id, expert_name)
                    except:
                        pass
                    return  # не fail — будет повтор

        # Постоянная ошибка или исчерпаны попытки → fail
        await redis_manager.update_task_status(external_task_id, "failed", result=error_msg)
        if canonical_task_id:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'failed',
                        result = $2,
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('last_error', $3::text)
                    WHERE id = $1
                    """,
                    canonical_task_id,
                    error_msg,
                    error_msg[:200],
                )

                # [SINGULARITY 27.2] DNA Mutation Loop: Learning from 5% errors
                if expert_name:
                    try:
                        from codebase_mutation_engine import get_mutation_engine

                        mutation = get_mutation_engine()
                        await mutation._update_expert_dna_on_failure(expert_name, error_msg)
                        logger.info(
                            f"🧬 [DNA] Mutation triggered for {expert_name} after permanent failure."
                        )
                    except Exception as mut_err:
                        logger.debug(f"Failed to trigger DNA mutation: {mut_err}")

        await redis_manager.release_task_lock(external_task_id)
        # [SINGULARITY 31.2] Release task from expert's active set in Blackboard
        try:
            from services.blackboard_service import get_blackboard_service

            bb = get_blackboard_service()
            await bb.release_task(external_task_id, expert_name)
        except:
            pass
    except Exception as e:
        logger.error(f"⚠️ Не удалось сохранить ошибку в БД/Redis: {e}")


async def worker_loop():
    """Основной цикл воркера: слушает Redis Stream."""
    client = await redis_manager.get_client()

    # [SINGULARITY 28.7] Identify this worker
    expert_name = os.getenv("EXPERT_NAME", f"Worker_{os.uname().nodename}")
    logger.error(f"🆔 [WORKER] I am identified as: {expert_name}")

    # [SINGULARITY 31.3] Agent messaging for all worker paths
    try:
        from app.agent_messaging import listen, start_presence_broadcast

        # Add suffix to avoid identity collision with main agents (e.g. Виктория)
        _agent_id = f"{expert_name}-Worker"
        asyncio.create_task(listen(_agent_id))
        asyncio.create_task(start_presence_broadcast(_agent_id, [expert_name.lower()]))
        logger.info(f"🔗 [AGENT_MSG] Expert '{_agent_id}' subscribed")
    except Exception as e:
        logger.debug(f"[AGENT_MSG] Init: {e}")

    enforce_target_expert = os.getenv("BLACKBOARD_ENFORCE_TARGET_EXPERT", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    verification_experts = {
        item.strip()
        for item in os.getenv("BLACKBOARD_VERIFICATION_EXPERTS", "Анна,Алексей").split(",")
        if item.strip()
    }
    rd_excluded_experts = {
        item.strip()
        for item in os.getenv("BLACKBOARD_RD_EXCLUDED_EXPERTS", "").split(",")
        if item.strip()
    }

    def _eligible_for_task(task_goal: dict) -> bool:
        metadata_local = task_goal.get("metadata", {}) or {}
        task_id_local = str(task_goal.get("task_id", ""))
        target_expert = metadata_local.get("target_expert")
        category = str(metadata_local.get("category", "")).lower()
        is_verification = bool(metadata_local.get("is_verification")) or task_id_local.startswith(
            "VERIFY_"
        )
        is_rd_task = (
            bool(metadata_local.get("is_rd"))
            or category.startswith("r&d")
            or task_id_local.startswith("RD_")
        )

        if enforce_target_expert and target_expert and target_expert != expert_name:
            return False
        if is_verification and verification_experts and expert_name not in verification_experts:
            return False
        if is_rd_task and rd_excluded_experts and expert_name in rd_excluded_experts:
            return False
        return True

    async def publish_runtime_presence():
        """Continuously refresh worker liveness heartbeat in Redis."""
        interval = max(10, RUNTIME_WORKER_HEARTBEAT_TTL_SEC // 3)
        while True:
            try:
                await _publish_worker_runtime_heartbeat(expert_name)
            except Exception as hb_err:
                logger.warning(f"⚠️ [RUNTIME-HEARTBEAT] Failed for {expert_name}: {hb_err}")
            await asyncio.sleep(interval)

    # [SINGULARITY 28.8] Autonomous Infrastructure: Self-Provisioning
    # If queue is too long, try to spawn a sibling worker
    async def monitor_queue_and_provision():
        """Monitor Redis stream and spawn new workers if needed."""
        try:
            while True:
                client = await redis_manager.get_client()
                # [FIX 28.9] Use pending count instead of total stream length
                groups_info = await client.xinfo_groups(f"stream:{STREAM_NAME}")
                pending_count = 0
                for group in groups_info:
                    if group["name"] == GROUP_NAME:
                        pending_count = group["pending"]

                if pending_count > 10:  # Threshold for spawning
                    logger.warning(
                        f"🚀 [PROVISIONING] High load detected ({pending_count} pending tasks). Spawning sibling..."
                    )
                    try:
                        # Simple docker-compose scale command (requires access to docker socket)
                        subprocess.Popen(
                            [
                                "docker-compose",
                                "up",
                                "-d",
                                "--scale",
                                f"expert-worker-heavy={pending_count // 5 + 1}",
                            ]
                        )
                    except Exception as e:
                        logger.error(f"❌ [PROVISIONING] Failed to scale: {e}")

                await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"❌ [PROVISIONING] Monitor failed: {e}")

    asyncio.create_task(monitor_queue_and_provision())
    asyncio.create_task(publish_runtime_presence())

    # [SINGULARITY 28.7] Decentralized Task Pickup & Bidding
    bb_autonomy_concurrency = max(1, int(os.getenv("SMART_WORKER_MAX_CONCURRENT", "1")))
    bb_autonomy_semaphore = asyncio.Semaphore(bb_autonomy_concurrency)

    async def _run_autonomy_payload(payload: dict):
        async with bb_autonomy_semaphore:
            await process_task(payload)

    async def monitor_blackboard_tasks():
        """Фоновый демон для поиска и захвата задач с Blackboard."""
        logger.error(f"👀 [AUTONOMY] Blackboard monitor started for {expert_name}")
        try:
            from resource_guard import get_resource_guard
            from services.blackboard_service import get_blackboard_service

            blackboard = get_blackboard_service()
            guard = get_resource_guard()

            while True:
                unclaimed = await blackboard.get_unclaimed_tasks()
                policy_client = await redis_manager.get_client()
                throttle_rd_bidding = await policy_client.get("system:throttle_rd_bidding")
                for task_goal in unclaimed:
                    task_id = task_goal["task_id"]
                    status = task_goal.get("status")
                    if not _eligible_for_task(task_goal):
                        continue
                    metadata_local = task_goal.get("metadata", {}) or {}
                    try:
                        pool_local = await get_db_pool()
                        async with pool_local.acquire() as conn_local:
                            canonical_task_id, _ = await _resolve_canonical_task_id(
                                conn_local, str(task_id), metadata_local
                            )
                            if canonical_task_id:
                                db_state = await conn_local.fetchrow(
                                    """
                                    SELECT status,
                                           COALESCE(metadata->>'processing_worker', '') AS processing_worker,
                                           (
                                               SELECT e.name
                                               FROM experts e
                                               WHERE e.id = tasks.assignee_expert_id
                                           ) AS assignee_name,
                                           updated_at,
                                           last_llm_call_at
                                    FROM tasks
                                    WHERE id = $1
                                    """,
                                    canonical_task_id,
                                )
                                if db_state:
                                    db_status = str(db_state["status"] or "")
                                    assignee_name = str(db_state["assignee_name"] or "").strip()
                                    if assignee_name and assignee_name != expert_name:
                                        logger.info(
                                            "⏭️ [AUTONOMY] Skip blackboard claim for %s: DB assignee is %s",
                                            task_id,
                                            assignee_name,
                                        )
                                        continue
                                    if db_status in ("completed", "failed", "cancelled"):
                                        continue
                                    if db_status == "in_progress":
                                        owner = (db_state["processing_worker"] or "").strip()
                                        progress_ts = (
                                            db_state["last_llm_call_at"] or db_state["updated_at"]
                                        )
                                        reclaim_after_sec = max(
                                            120,
                                            int(
                                                os.getenv(
                                                    "WORKER_STALE_INPROGRESS_RECLAIM_SEC", "300"
                                                )
                                            ),
                                        )
                                        age_sec = (
                                            (
                                                datetime.now(timezone.utc) - progress_ts
                                            ).total_seconds()
                                            if progress_ts is not None
                                            else 0
                                        )
                                        if (
                                            owner
                                            and owner != expert_name
                                            and age_sec < reclaim_after_sec
                                        ):
                                            logger.info(
                                                "⏭️ [AUTONOMY] Skip blackboard claim for %s: owned by %s (age %.0fs)",
                                                task_id,
                                                owner,
                                                age_sec,
                                            )
                                            continue
                    except Exception as db_guard_err:
                        logger.debug(
                            "Autonomy DB ownership guard skipped for %s: %s",
                            task_id,
                            db_guard_err,
                        )
                    is_rd_task = bool(metadata_local.get("is_rd")) or str(task_id).startswith("RD_")
                    if throttle_rd_bidding and is_rd_task:
                        logger.info(
                            f"🛡️ [SLA] RD bidding throttled, skipping task {task_id} for {expert_name}"
                        )
                        continue

                    # Phase 1: Bidding
                    if status == "bidding_open":
                        health_score = await guard.get_health_score()
                        expertise_score = 0.5
                        if any(
                            kw in task_goal["goal"].lower() for kw in ["security", "audit", "fix"]
                        ):
                            if expert_name in ("Роман", "Игорь"):
                                expertise_score = 0.9

                        bid_score = (expertise_score * 0.6) + (health_score * 0.4)
                        await blackboard.post_bid(task_id, expert_name, bid_score)
                        await asyncio.sleep(3)
                        winner = await blackboard.resolve_auction(task_id)
                        if winner == expert_name:
                            logger.error(f"🏆 [AUCTION] {expert_name} WON task {task_id}")
                            payload = {
                                "task_id": task_id,
                                "expert_name": expert_name,
                                "description": task_goal["goal"],
                                "metadata": {
                                    **task_goal["metadata"],
                                    "source": "blackboard_auction",
                                },
                            }
                            asyncio.create_task(_run_autonomy_payload(payload))

                    # Phase 2: Legacy Claim
                    elif status == "unclaimed":
                        if await blackboard.claim_task(task_id, expert_name):
                            logger.error(
                                f"🤝 [AUTONOMY] {expert_name} self-assigned task {task_id} from Blackboard"
                            )
                            payload = {
                                "task_id": task_goal["task_id"],
                                "expert_name": expert_name,
                                "description": task_goal["goal"],
                                "metadata": {
                                    **task_goal["metadata"],
                                    "source": "blackboard_autonomy",
                                },
                            }
                            asyncio.create_task(_run_autonomy_payload(payload))

                await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"❌ [AUTONOMY] Blackboard monitor failed: {e}")

    # [SINGULARITY 30.4] Resurrection Logic: Recover tasks assigned to this expert on startup
    async def recover_my_tasks():
        """Периодический поиск и возобновление задач, закрепленных за этим экспертом."""
        recovery_interval = max(30, int(os.getenv("WORKER_RECOVERY_INTERVAL_SEC", "90")))
        stale_progress_minutes = max(
            5, int(os.getenv("WORKER_RECOVERY_STALE_PROGRESS_MINUTES", "12"))
        )
        stale_claim_minutes = max(10, int(os.getenv("WORKER_RECOVERY_STALE_CLAIM_MINUTES", "20")))
        first_pass = True
        while True:
            try:
                # Wait a bit for EventBus/Redis Bridge to stabilize on first pass
                if first_pass:
                    await asyncio.sleep(5)
                    first_pass = False

                client = await redis_manager.get_client()
                goals_key = "blackboard:goals"
                all_goals = await client.hgetall(goals_key)
                pool = await get_db_pool()

                recovered_count = 0
                async with pool.acquire() as conn:
                    for tid_bytes, raw in all_goals.items():
                        tid = tid_bytes.decode() if isinstance(tid_bytes, bytes) else tid_bytes
                        data = json.loads(raw)

                        if data.get("status") == "claimed" and data.get("assignee") == expert_name:
                            metadata_local = data.get("metadata", {}) or {}
                            db_task_id, _ = await _resolve_canonical_task_id(
                                conn, tid, metadata_local
                            )
                            if not db_task_id:
                                claimed_at = data.get("claimed_at")
                                if claimed_at:
                                    try:
                                        claimed_dt = datetime.fromisoformat(
                                            str(claimed_at).replace("Z", "+00:00")
                                        )
                                        age_seconds = (
                                            datetime.now(timezone.utc) - claimed_dt
                                        ).total_seconds()
                                        if age_seconds > stale_claim_minutes * 60:
                                            data["status"] = "bidding_open"
                                            data["assignee"] = None
                                            data["reclaimed_at"] = datetime.now(
                                                timezone.utc
                                            ).isoformat()
                                            data["recovery_skip_reason"] = (
                                                "stale_claim_unresolved_canonical"
                                            )
                                            await client.hset(goals_key, tid, json.dumps(data))
                                            await client.delete(f"blackboard:heartbeat:{tid}")
                                            logger.warning(
                                                "♻️ [RESURRECTION] Reopened stale claimed goal %s (unresolved canonical id, age %.0fs)",
                                                tid,
                                                age_seconds,
                                            )
                                            continue
                                    except Exception:
                                        pass
                                # Do not resurrect unresolved non-canonical task ids.
                                # Blind resume here creates infinite reclaim/redispatch loops.
                                data["recovery_skip_reason"] = "unresolved_canonical_id"
                                await client.hset(goals_key, tid, json.dumps(data))
                                logger.warning(
                                    "⏭️ [RESURRECTION] Skip unresolved goal %s for %s (no canonical task id)",
                                    tid,
                                    expert_name,
                                )
                                continue
                            if db_task_id:
                                state = await conn.fetchrow(
                                    "SELECT status, updated_at, last_llm_call_at FROM tasks WHERE id = $1",
                                    db_task_id,
                                )
                                if state:
                                    task_status = state["status"]
                                    if task_status in ("completed", "failed", "cancelled"):
                                        await client.hdel(goals_key, tid)
                                        await client.delete(f"blackboard:heartbeat:{tid}")
                                        logger.info(
                                            "🧹 [RESURRECTION] Removed terminal task goal %s (%s) for %s",
                                            tid,
                                            task_status,
                                            expert_name,
                                        )
                                        continue
                                    progress_ts = state["last_llm_call_at"] or state["updated_at"]
                                    if task_status == "in_progress" and progress_ts is not None:
                                        age_seconds = (
                                            datetime.now(timezone.utc) - progress_ts
                                        ).total_seconds()
                                        if age_seconds > stale_progress_minutes * 60:
                                            await conn.execute(
                                                """
                                                UPDATE tasks
                                                SET status = 'pending',
                                                    assignee_expert_id = NULL,
                                                    updated_at = NOW(),
                                                    metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                                                WHERE id = $1
                                                  AND status = 'in_progress'
                                                """,
                                                db_task_id,
                                                json.dumps(
                                                    {
                                                        "worker_recovery_requeue": True,
                                                        "worker_recovery_requeue_reason": "stale_no_progress",
                                                        "worker_recovery_requeue_at": datetime.now(
                                                            timezone.utc
                                                        ).isoformat(),
                                                        "worker_recovery_expert": expert_name,
                                                    }
                                                ),
                                            )
                                            data["status"] = "bidding_open"
                                            data["assignee"] = None
                                            data["reclaimed_at"] = datetime.now(
                                                timezone.utc
                                            ).isoformat()
                                            data["recovery_skip_reason"] = "stale_no_progress"
                                            await client.hset(goals_key, tid, json.dumps(data))
                                            await client.delete(f"blackboard:heartbeat:{tid}")
                                            logger.warning(
                                                "♻️ [RESURRECTION] Requeued stale task %s after %.0fs without progress",
                                                tid,
                                                age_seconds,
                                            )
                                            continue
                                        # Task is actively progressing inside SLA window.
                                        # Do not re-spawn processing from recovery loop.
                                        continue

                            recovery_probe = {
                                "task_id": tid,
                                "metadata": metadata_local,
                            }
                            if not _eligible_for_task(recovery_probe):
                                data["status"] = "bidding_open"
                                data["assignee"] = None
                                data["reclaimed_at"] = datetime.now(timezone.utc).isoformat()
                                data["recovery_skip_reason"] = "policy_mismatch"
                                await client.hset(goals_key, tid, json.dumps(data))
                                await client.delete(f"blackboard:heartbeat:{tid}")
                                logger.warning(
                                    f"🧭 [RESURRECTION] Reopened task {tid} due to routing policy mismatch for {expert_name}"
                                )
                                continue

                            logger.error(f"🔄 [RESURRECTION] Found my task {tid}. Resuming...")
                            payload = {
                                "task_id": tid,
                                "expert_name": expert_name,
                                "description": data["goal"],
                                "metadata": {**metadata_local, "source": "blackboard_resurrection"},
                            }
                            asyncio.create_task(_run_autonomy_payload(payload))
                            recovered_count += 1

                if recovered_count > 0:
                    logger.error(
                        f"✅ [RESURRECTION] Successfully resumed {recovered_count} tasks for {expert_name}"
                    )
            except Exception as e:
                logger.error(f"❌ [RESURRECTION] Recovery failed: {e}")

            await asyncio.sleep(recovery_interval)

    # Start the monitor and recovery
    asyncio.create_task(monitor_blackboard_tasks())
    asyncio.create_task(recover_my_tasks())

    # Создаем группу потребителей, если её нет
    try:
        await client.xgroup_create(f"stream:{STREAM_NAME}", GROUP_NAME, mkstream=True)
    except Exception:
        pass  # Группа уже существует

    # Запускаем систему самообучения корпорации (Singularity 14.0)
    try:
        from corporation_self_learning import get_corporation_learner

        learner = get_corporation_learner()
        # Запускаем в фоне (интервал 6 часов)
        asyncio.create_task(learner.start_continuous_learning(interval_hours=6))
        logger.info("🧠 [SINGULARITY 10.0] Collective Learning system started")
    except Exception as e:
        logger.warning(f"⚠️ [SINGULARITY 10.0] Could not start collective learning: {e}")

    logger.info(
        "🚀 [WORKER] Воркер запущен. expert=%s dedicated_stream=%s shared_fallback=%s",
        _expert_name_env or "(any)",
        STREAM_NAME,
        SHARED_EXPERT_STREAM,
    )

    # [SINGULARITY 24.3] Живой Чат: Инициализация EventBus и Redis Bridge
    try:
        # [SINGULARITY 24.3] Fix: Universal import for EventBus
        try:
            from app.event_bus import get_event_bus
        except ImportError:
            from event_bus import get_event_bus

        from event_bus_redis_bridge import start_redis_bridge

        bus = get_event_bus()
        await bus.start()
        await start_redis_bridge(bus)
        logger.info("🌉 [WORKER] EventBus Redis Bridge запущен для Живого Чата")
    except Exception as e:
        logger.warning(f"⚠️ [WORKER] Не удалось запустить EventBus Bridge: {e}")

    # [FULL FIX 2026-04-08] Get DB pool once for the worker lifetime
    db_pool = await get_db_pool()
    supported_contract_versions = {
        item.strip()
        for item in os.getenv("WORKER_SUPPORTED_CONTRACT_VERSIONS", "1").split(",")
        if item.strip()
    }

    def _normalize_contract(payload: dict) -> Optional[dict]:
        """Validate task contract envelope and return normalized contract."""
        contract = payload.get("contract") or {}
        payload_meta = payload.get("metadata") or {}
        if not isinstance(payload_meta, dict):
            payload_meta = {}
        contract_enforce = bool(payload_meta.get("contract_enforce", True))
        if not isinstance(contract, dict):
            logger.warning("⚠️ [CONTRACT] Invalid contract type for task=%s", payload.get("task_id"))
            return None
        version = str(contract.get("version") or "1")
        if version not in supported_contract_versions:
            if contract_enforce:
                logger.warning(
                    "⚠️ [CONTRACT] Unsupported contract version=%s for task=%s",
                    version,
                    payload.get("task_id"),
                )
                return None
            logger.warning(
                "⚠️ [CONTRACT] Shadow mode pass-through for unsupported version=%s task=%s",
                version,
                payload.get("task_id"),
            )
        normalized = {
            "version": version,
            "intent": contract.get("intent") or "execute_assigned_task",
            "output_schema": contract.get("output_schema") or "expert_response_v1",
            "risk_level": contract.get("risk_level") or "medium",
            "freshness_sla_sec": 900,
            "audit_required": bool(contract.get("audit_required", False)),
            "enforce": contract_enforce,
        }
        try:
            normalized["freshness_sla_sec"] = int(contract.get("freshness_sla_sec") or 900)
        except Exception:
            pass
        return normalized

    # [FULL FIX 2026-04-08 / Sergey] Cleanup stale event_bus_stream consumer groups on startup.
    # Each restart/reconnect creates a new group. After months they accumulate (248+).
    # Safe cleanup: groups with 0 pending and 0 consumers are orphaned.
    try:
        eb_groups = await client.xinfo_groups("event_bus_stream")
        stale_eb_groups = [
            g["name"] for g in eb_groups if g.get("pending", 0) == 0 and g.get("consumers", 0) == 0
        ]
        if stale_eb_groups:
            for gname in stale_eb_groups:
                try:
                    await client.xgroup_destroy("event_bus_stream", gname)
                except Exception:
                    pass
            logger.info(
                f"🧹 [WORKER] Cleaned up {len(stale_eb_groups)} stale event_bus_stream groups"
            )
    except Exception as e:
        logger.warning(f"⚠️ [WORKER] event_bus_stream cleanup skipped: {e}")

    while True:
        try:
            # [FULL FIX 2026-04-08] Three-phase pending management:
            # Phase 1: Kill zombie messages (>10 deliveries) → ACK Redis + mark PostgreSQL failed
            # Phase 2: Xclaim legitimately stale messages (idle >5min, deliveries ≤10)
            # Phase 3: xreadgroup("0") reads OUR pending (including just-xclaimed) + new + autoclaim

            pending_info = await client.xpending(f"stream:{STREAM_NAME}", GROUP_NAME)
            if pending_info["pending"] > 0:
                p_range = await client.xpending_range(
                    f"stream:{STREAM_NAME}", GROUP_NAME, "-", "+", 10
                )
                if p_range:
                    # Phase 1: Zombies → DLQ + PostgreSQL sync
                    zombie_msg_ids = [p["message_id"] for p in p_range if p["times_delivered"] > 10]
                    if zombie_msg_ids:
                        zombie_task_ids = []
                        for zmid in zombie_msg_ids:
                            try:
                                raw = await client.xrange(f"stream:{STREAM_NAME}", zmid, zmid)
                                if raw:
                                    _, zdata = raw[0]
                                    raw_payload = zdata.get("payload") or zdata.get(b"payload")
                                    if raw_payload:
                                        zpayload = (
                                            json.loads(raw_payload)
                                            if isinstance(raw_payload, (str, bytes))
                                            else raw_payload
                                        )
                                        task_id = zpayload.get("task_id")
                                        if task_id:
                                            zombie_task_ids.append(task_id)
                            except Exception as ze:
                                logger.warning(
                                    f"⚠️ [DLQ] Could not read zombie payload {zmid}: {ze}"
                                )
                        logger.warning(
                            f"💀 [DLQ] Killing {len(zombie_msg_ids)} zombie messages, task_ids={zombie_task_ids}"
                        )
                        await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, *zombie_msg_ids)
                        if zombie_task_ids:
                            zombie_uuid_ids = [
                                parsed
                                for parsed in (_as_uuid_str(zid) for zid in zombie_task_ids)
                                if parsed
                            ]
                            if not zombie_uuid_ids:
                                logger.warning(
                                    "💀 [DLQ] No canonical UUID task_ids in zombie batch; skipping SQL status update."
                                )
                                # НЕ continue — нужно чтобы Phase 3a/3b/3c выполнились
                            if zombie_uuid_ids:
                                async with db_pool.acquire() as conn:
                                    updated = await conn.execute(
                                        """UPDATE tasks
                                           SET status = 'failed', updated_at = NOW(),
                                               metadata = jsonb_set(
                                                   COALESCE(metadata::jsonb, '{}'::jsonb),
                                                   '{dlq_reason}',
                                                   '"zombie_redis_exceeded_delivery_limit"'
                                               )
                                           WHERE id = ANY($1::uuid[])
                                             AND status IN ('pending', 'in_progress')""",
                                        zombie_uuid_ids,
                                    )
                                logger.warning(
                                    f"💀 [DLQ] PostgreSQL updated: {updated} zombie tasks → failed"
                                )

                    # Phase 2: Xclaim legitimately stale (idle >5min, not zombies)
                    claimable = [
                        p["message_id"]
                        for p in p_range
                        if p["times_delivered"] <= 10 and p["time_since_delivered"] > 300000
                    ]
                    if claimable:
                        logger.info(
                            f"🛠️ [WORKER] Claiming {len(claimable)} stale tasks for {CONSUMER_NAME}"
                        )
                        await client.xclaim(
                            f"stream:{STREAM_NAME}", GROUP_NAME, CONSUMER_NAME, 300000, claimable
                        )

            # Phase 3a: Read OUR pending messages (id="0" — includes just-xclaimed ones)
            pending_mine = await client.xreadgroup(
                GROUP_NAME, CONSUMER_NAME, {f"stream:{STREAM_NAME}": "0"}, count=5
            )

            # Phase 3b: Autoclaim stale messages from OTHER consumers (idle >5min)
            stale_messages = await redis_manager.autoclaim_tasks(
                STREAM_NAME, GROUP_NAME, CONSUMER_NAME, min_idle_time_ms=300000
            )

            # Phase 3c: New messages (blocking 5s)
            messages = await client.xreadgroup(
                GROUP_NAME, CONSUMER_NAME, {f"stream:{STREAM_NAME}": ">"}, count=1, block=5000
            )

            # [STALE-DROP] Drop only truly stale pending (idle > 5 min).
            # _run_task xack'ает сразу после старта → свежие сообщения в pending не задерживаются.
            # Если висит >5 мин — это остаток от прошлого запуска или упавший background task.
            _stale_cutoff_ms = 300_000
            _p_range = await client.xpending_range(
                f"stream:{STREAM_NAME}",
                GROUP_NAME,
                min="-",
                max="+",
                count=10,
            )
            _stale_pending = [p for p in _p_range if p["time_since_delivered"] > _stale_cutoff_ms]
            if _stale_pending:
                _stale_ids = [p["message_id"] for p in _stale_pending]
                await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, *_stale_ids)
                for _p in _stale_pending:
                    try:
                        _msg_data = await client.xrange(
                            f"stream:{STREAM_NAME}",
                            min=_p["message_id"],
                            max=_p["message_id"],
                        )
                        if _msg_data:
                            _raw = _msg_data[0][1].get(b"payload") or _msg_data[0][1].get("payload")
                            _payload = json.loads(_raw) if isinstance(_raw, (str, bytes)) else None
                            if _payload:
                                _task_id = _payload.get("task_id")
                                if _task_id:
                                    async with db_pool.acquire() as _conn:
                                        _db_id, _ = await _resolve_canonical_task_id(
                                            _conn, _task_id, _payload.get("metadata") or {}
                                        )
                                        if _db_id:
                                            await _conn.execute(
                                                """UPDATE tasks
                                                   SET status = 'failed',
                                                       updated_at = NOW(),
                                                       metadata = COALESCE(metadata, '{}'::jsonb) ||
                                                           jsonb_build_object('worker_dropped_stale_pending', true)
                                                   WHERE id = $1
                                                     AND status IN ('pending', 'in_progress')""",
                                                _db_id,
                                            )
                    except Exception as _drop_err:
                        logger.warning(
                            f"⚠️ [STALE-DROP] Failed to process stale msg {_p['message_id']}: {_drop_err}"
                        )
                logger.warning(f"🧹 [STALE-DROP] Dropped {len(_stale_ids)} stale pending messages")

            # pending_mine всё ещё нужен для Phase 3c: если не обработан через background,
            # попадёт в all_messages и будет повторно разобран.
            if pending_mine:
                # Только сообщения idle <= 5min — свежие (background ещё работает)
                _fresh_pending = [
                    p for p in _p_range if p["time_since_delivered"] <= _stale_cutoff_ms
                ]
                _fresh_ids = set(p["message_id"] for p in _fresh_pending)
                pending_mine = [
                    (s, [m for m in ms if m[0] in _fresh_ids]) for s, ms in pending_mine
                ]
                pending_mine = [(s, ms) for s, ms in pending_mine if ms]
                if not pending_mine:
                    pending_mine = None

            all_messages = []
            if stale_messages:
                all_messages.append((f"stream:{STREAM_NAME}", stale_messages))
            if messages:
                all_messages.extend(messages)
            if pending_mine:
                all_messages.extend(pending_mine)

            if not all_messages:
                continue

            for stream, msgs in all_messages:
                for msg_id, data in msgs:
                    try:
                        # Belt-and-suspenders: drop any zombie that slipped through Phase 1
                        info = await client.xpending_range(
                            f"stream:{STREAM_NAME}", GROUP_NAME, msg_id, msg_id, 1
                        )
                        if info and info[0]["times_delivered"] > 10:
                            logger.error(
                                f"💀 [DLQ] Message {msg_id} slipped through Phase 1. Dropping."
                            )
                            await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                            continue

                        raw_payload = data.get(b"payload") or data.get("payload")
                        if isinstance(raw_payload, (str, bytes)):
                            payload = json.loads(raw_payload)
                        else:
                            payload = {
                                k.decode() if isinstance(k, bytes) else k: v.decode()
                                if isinstance(v, bytes)
                                else v
                                for k, v in data.items()
                            }
                        payload["queue_name"] = STREAM_NAME
                        normalized_contract = _normalize_contract(payload)
                        if not normalized_contract:
                            await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                            continue
                        payload["contract"] = normalized_contract
                        payload_expert = payload.get("expert_name")
                        _expert_pool = os.getenv("EXPERT_POOL_MODE", "false").lower() in (
                            "true",
                            "1",
                            "yes",
                        )
                        if payload_expert and payload_expert != expert_name:
                            if _expert_pool:
                                logger.info(
                                    "🔄 [POOL] Adopting expert '%s' (was '%s') for task %s",
                                    payload_expert,
                                    expert_name,
                                    payload.get("task_id"),
                                )
                                expert_name = payload_expert
                            else:
                                logger.info(
                                    "⏭️ [WORKER] Skip чужого payload: payload=%s worker=%s task=%s",
                                    payload_expert,
                                    expert_name,
                                    payload.get("task_id"),
                                )

                        if payload_expert and payload_expert != expert_name and not _expert_pool:
                            # Do not drop foreign deliveries: requeue so the correct expert can consume.
                            metadata = payload.get("metadata") or {}
                            if not isinstance(metadata, dict):
                                metadata = {}
                            mismatch_hops = int(metadata.get("expert_mismatch_hops", 0))
                            if mismatch_hops >= 3:
                                task_id = str(payload.get("task_id") or "")
                                logger.error(
                                    "🛑 [MISMATCH-RECOVERY] Stop republish loop after mismatch hops: task=%s payload=%s worker=%s hops=%s",
                                    task_id,
                                    payload_expert,
                                    expert_name,
                                    mismatch_hops,
                                )
                                try:
                                    if task_id:
                                        pool = await get_db_pool()
                                        async with pool.acquire() as conn:
                                            db_task_id, _ = await _resolve_canonical_task_id(
                                                conn, task_id, metadata
                                            )
                                            if db_task_id:
                                                expected_expert_id = None
                                                try:
                                                    expected_expert_id = await conn.fetchval(
                                                        "SELECT id FROM experts WHERE name = $1 LIMIT 1",
                                                        str(payload_expert),
                                                    )
                                                except Exception as resolve_err:
                                                    logger.debug(
                                                        "⚠️ [MISMATCH-RECOVERY] Failed to resolve expected expert '%s': %s",
                                                        payload_expert,
                                                        resolve_err,
                                                    )

                                                mismatch_meta = {
                                                    "payload_mismatch_requeued": True,
                                                    "payload_mismatch_requeued_at": datetime.now(
                                                        timezone.utc
                                                    ).isoformat(),
                                                    "payload_mismatch_worker": expert_name,
                                                    "payload_expected_expert": payload_expert,
                                                    "expert_mismatch_hops": 0,
                                                    "payload_mismatch_exhausted": True,
                                                }
                                                retry_after = datetime.now(
                                                    timezone.utc
                                                ) + timedelta(minutes=2)
                                                mismatch_meta["next_retry_after"] = (
                                                    retry_after.isoformat()
                                                )
                                                if payload_expert:
                                                    mismatch_meta["target_expert"] = str(
                                                        payload_expert
                                                    )

                                                recovery_meta = json.dumps(
                                                    mismatch_meta, ensure_ascii=False
                                                )
                                                if expected_expert_id:
                                                    await conn.execute(
                                                        """
                                                        UPDATE tasks
                                                        SET status = 'pending',
                                                            assignee_expert_id = $2,
                                                            retry_after = $3,
                                                            updated_at = NOW(),
                                                            metadata = (
                                                                COALESCE(metadata, '{}'::jsonb)
                                                                - 'dispatched_to_stream_at'
                                                            ) || $4::jsonb
                                                        WHERE id = $1
                                                          AND status IN ('pending', 'in_progress')
                                                        """,
                                                        db_task_id,
                                                        expected_expert_id,
                                                        retry_after,
                                                        recovery_meta,
                                                    )
                                                else:
                                                    await conn.execute(
                                                        """
                                                        UPDATE tasks
                                                        SET status = 'pending',
                                                            assignee_expert_id = NULL,
                                                            retry_after = $2,
                                                            updated_at = NOW(),
                                                            metadata = (
                                                                COALESCE(metadata, '{}'::jsonb)
                                                                - 'dispatched_to_stream_at'
                                                            ) || $3::jsonb
                                                        WHERE id = $1
                                                          AND status IN ('pending', 'in_progress')
                                                        """,
                                                        db_task_id,
                                                        retry_after,
                                                        recovery_meta,
                                                    )
                                                logger.info(
                                                    "🧭 [MISMATCH-RECOVERY] Task %s parked for orchestrator redispatch (retry_after=%s expected=%s)",
                                                    db_task_id,
                                                    mismatch_meta["next_retry_after"],
                                                    payload_expert,
                                                )
                                except Exception as requeue_err:
                                    logger.warning(
                                        "⚠️ [MISMATCH-RECOVERY] Failed to park task %s: %s",
                                        task_id,
                                        requeue_err,
                                    )
                                await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                                continue

                            metadata["expert_mismatch_hops"] = mismatch_hops + 1
                            metadata["last_mismatch_worker"] = expert_name
                            metadata["last_mismatch_at"] = datetime.now(timezone.utc).isoformat()
                            payload["metadata"] = metadata

                            try:
                                from app.expert_stream_routing import publish_expert_payload
                            except ImportError:
                                from expert_stream_routing import publish_expert_payload

                            await publish_expert_payload(client, payload_expert, payload)
                            await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                            continue

                        # [CONCURRENCY] Process task in background so main loop can continue
                        # reading new messages without blocking on slow process_task (up to 2700s).
                        # Сразу xack чтобы выйти из PENDING — Phase 3a не дропнет свежую таску.
                        async def _run_task(_p=payload, _id=msg_id):
                            try:
                                await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, _id)
                            except Exception as _xack_err:
                                logger.warning(
                                    f"⚠️ [WORKER] Failed to early-xack {_id}: {_xack_err}"
                                )
                            try:
                                await process_task(_p)
                            except Exception as e:
                                logger.error(f"❌ [WORKER] Ошибка обработки сообщения {_id}: {e}")
                                _task_id = _p.get("task_id") if isinstance(_p, dict) else None
                                if _task_id:
                                    try:
                                        async with db_pool.acquire() as conn:
                                            _db_id, _ = await _resolve_canonical_task_id(
                                                conn,
                                                _task_id,
                                                _p.get("metadata") or {},
                                            )
                                            if _db_id:
                                                await conn.execute(
                                                    """UPDATE tasks
                                                       SET status = 'failed',
                                                           updated_at = NOW(),
                                                           metadata = COALESCE(metadata, '{}'::jsonb) ||
                                                               jsonb_build_object('worker_error', $2::text)
                                                       WHERE id = $1
                                                         AND status IN ('pending', 'in_progress')""",
                                                    _db_id,
                                                    str(e),
                                                )
                                    except Exception as _db_err:
                                        logger.warning(
                                            f"⚠️ [WORKER] Failed to mark task failed {_id}: {_db_err}"
                                        )

                        asyncio.create_task(_run_task())
                    except Exception as e:
                        logger.error(f"❌ [WORKER] Ошибка обработки сообщения {msg_id}: {e}")
                        try:
                            await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                        except Exception as xack_err:
                            logger.warning(f"⚠️ [WORKER] Failed to xack on msg {msg_id}: {xack_err}")

        except Exception as e:
            logger.error(f"⚠️ [WORKER] Ошибка в цикле: {e}")
            await asyncio.sleep(5)


async def metrics_handler(request):
    from prometheus_client import REGISTRY, generate_latest

    metrics = generate_latest(REGISTRY)
    return web.Response(body=metrics, content_type="text/plain")


async def health_handler(request):
    return web.json_response({"status": "healthy", "worker": "expert"})


def start_metrics_server(port=8001):
    app = web.Application()
    app.router.add_get("/metrics", metrics_handler)
    app.router.add_get("/health", health_handler)
    return app


def run_metrics_only(port=8001):
    """Запуск только HTTP сервера для метрик (без воркера)."""
    app = start_metrics_server(port)
    logger.info(f"📊 [METRICS] Starting metrics server on port {port}")
    web.run_app(app, host="0.0.0.0", port=port, print=lambda x: None)


def run_worker_with_metrics(port=8001):
    """Запуск и воркера и HTTP сервера метрик параллельно."""

    async def run_both():
        # [SINGULARITY 31.3] Agent messaging init
        try:
            from app.agent_messaging import listen, start_presence_broadcast

            _en = os.getenv("EXPERT_NAME", "expert")
            asyncio.create_task(listen(_en))
            asyncio.create_task(start_presence_broadcast(_en, [_en.lower()]))
            logger.info(f"🔗 [AGENT_MSG] Expert '{_en}' subscribed")
        except Exception as e:
            logger.debug(f"[AGENT_MSG] Init unavailable: {e}")

        metrics_app = start_metrics_server(port)
        metrics_runner = web.AppRunner(metrics_app)
        await metrics_runner.setup()
        metrics_site = web.TCPSite(metrics_runner, "0.0.0.0", port)
        await metrics_site.start()
        logger.info(f"📊 [METRICS] Metrics server started on port {port}")
        try:
            await worker_loop()
        finally:
            await metrics_runner.cleanup()

    asyncio.get_event_loop().run_until_complete(run_both())


if __name__ == "__main__":
    import sys

    enable_metrics = os.getenv("ENABLE_METRICS", "false").lower() in ("true", "1", "yes")
    metrics_port = int(os.getenv("METRICS_PORT", "8001"))
    run_as_metrics_only = "--metrics-only" in sys.argv

    async def metrics_handler(request):
        from prometheus_client import REGISTRY, generate_latest

        metrics = generate_latest(REGISTRY)
        return web.Response(body=metrics, content_type="text/plain")

    async def health_handler(request):
        return web.json_response({"status": "healthy", "worker": "expert"})

    def start_metrics_server(port=8001):
        app = web.Application()
        app.router.add_get("/metrics", metrics_handler)
        app.router.add_get("/health", health_handler)
        return app

    def run_metrics_only(port=8001):
        """Запуск только HTTP сервера для метрик (без воркера)."""
        app = start_metrics_server(port)
        logger.info(f"📊 [METRICS] Starting metrics server on port {port}")
        web.run_app(app, host="0.0.0.0", port=port, print=lambda x: None)

    def run_worker_with_metrics(port=8001):
        """Запуск и воркера и HTTP сервера метрик параллельно."""

        async def run_both():
            metrics_app = start_metrics_server(port)
            metrics_runner = web.AppRunner(metrics_app)
            await metrics_runner.setup()
            metrics_site = web.TCPSite(metrics_runner, "0.0.0.0", port)
            await metrics_site.start()
            logger.info(f"📊 [METRICS] Metrics server started on port {port}")
            try:
                await worker_loop()
            finally:
                await metrics_runner.cleanup()

        asyncio.get_event_loop().run_until_complete(run_both())

    if "--metrics" in sys.argv or enable_metrics:
        if run_as_metrics_only:
            run_metrics_only(metrics_port)
        else:
            run_worker_with_metrics(metrics_port)
    else:

        async def _run_with_messaging():
            # [SINGULARITY 31.3] Agent messaging init
            try:
                from app.agent_messaging import listen, start_presence_broadcast

                _en = os.getenv("EXPERT_NAME", "expert")
                asyncio.create_task(listen(_en))
                asyncio.create_task(start_presence_broadcast(_en, [_en.lower()]))
                logger.info(f"🔗 [AGENT_MSG] Expert '{_en}' subscribed")
            except Exception as e:
                logger.debug(f"[AGENT_MSG] Init unavailable: {e}")
            await worker_loop()

        try:
            asyncio.run(_run_with_messaging())
        except KeyboardInterrupt:
            logger.info("🛑 [WORKER] Остановка по сигналу пользователя")
