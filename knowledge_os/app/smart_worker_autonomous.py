import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional, Union

from app.memory.journal_manager import ExpertJournalManager
from app.memory.memory_service import MemoryService
from app.schemas import AgentResponse, TaskResult, parse_agent_response

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

logger = logging.getLogger(__name__)
_LOCAL_ROUTER_FACTORY_CACHE = None
_last_success_ts = 0

if _PROMETHEUS_AVAILABLE:
    _smart_worker_tasks_total = Counter(
        "smart_worker_tasks_total", "Total tasks processed by smart worker", ["status"]
    )
    _smart_worker_task_duration_seconds = Histogram(
        "smart_worker_task_duration_seconds", "Smart worker task execution duration", ["category"]
    )
    _smart_worker_active = Gauge(
        "smart_worker_active_tasks", "Number of active tasks being processed by smart worker"
    )


from app.worker.worker_logic import (
    _auto_requeue_delegation,
    _emit_delegation_metrics,
    _structured_cancel_reason,
)
from app.worker.worker_memory import (
    ROLE_DEPARTMENT_TO_SKILLS,
    _read_skill_snippets_sync,
    _select_skills_by_relevance_sync,
)

# Маркеры запроса актуальных данных — при наличии вызываем веб-поиск (П.1 PRINCIPLE_EXPERTS_FIRST)
_WEB_MARKERS = (
    "актуальн",
    "последн",
    "2025",
    "best practices",
    "свежий",
    "текущ",
    "новейш",
    "latest",
    "recent",
    "best practice",
    "как сейчас",
    "сейчас принято",
)


def _task_needs_web_search(title: str, description: str) -> bool:
    """Проверяет, нужен ли веб-поиск по маркерам актуальности в задаче."""
    combined = f"{title} {description}".lower()
    return any(m in combined for m in _WEB_MARKERS)


def _web_search_sync(query: str, max_results: int = 3) -> List[str]:
    """П.6: единый веб-поиск через web_search_fallback (DuckDuckGo → в будущем Ollama)."""
    try:
        from app.web_search_fallback import web_search_sync as _search

        results = _search(query, max_results=max_results)
        return [r.get("snippet", "")[:400] for r in results if r.get("snippet")]
    except Exception as e:
        logger.debug("Web search failed: %s", e)
        return []


# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 12-Factor: зависимости из requirements.txt, установка при setup, не в рантайме
try:
    import asyncpg
except ImportError:
    print(
        "Установите зависимости: bash knowledge_os/scripts/setup_knowledge_os.sh (или pip install -r knowledge_os/requirements.txt)",
        file=sys.stderr,
    )
    sys.exit(1)

# Используем тот же формат, что и другие модули
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os?application_name=knowledge_pool",
)

# Максимум попыток выполнения задачи; после исчерпания — эскалация в Совет Директоров
MAX_ATTEMPTS = int(os.getenv("SMART_WORKER_MAX_ATTEMPTS", "3"))

# Глобальный пул соединений (singleton)
_pool = None

# Кэш сканера моделей в главном цикле воркера (TTL 120 сек) — меньше вызовов к Ollama/MLX
_scanner_cache_time = 0.0
_scanner_cache_mlx = None
_scanner_cache_ollama = None


try:
    from app.db_pool import get_pool as _get_shared_pool
except ImportError:
    from db_pool import get_pool as _get_shared_pool


async def get_pool():
    """[SINGULARITY 10.0] Unified DB Pool: use shared pool from db_pool.py"""
    return await _get_shared_pool()


try:
    from ai_core import run_smart_agent_async
except ImportError:
    # Попытка импорта с полным путем
    import importlib.util

    ai_core_path = os.path.join(os.path.dirname(__file__), "ai_core.py")
    spec = importlib.util.spec_from_file_location("ai_core", ai_core_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load ai_core from {ai_core_path}")
    ai_core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai_core)  # type: ignore[union-attr]
    run_smart_agent_async = ai_core.run_smart_agent_async


async def run_cursor_agent_smart(prompt: str, expert_name: str, router=None):
    """Smart replacement for the old cursor-agent call. router — роутер с _preferred_source (mlx/ollama), чтобы не было гонки при параллельных задачах."""
    return await run_smart_agent_async(
        prompt, expert_name=expert_name, category="autonomous_worker", local_router=router
    )


def _create_local_router():
    """Provider/factory for task-scoped LocalAIRouter instances."""
    global _LOCAL_ROUTER_FACTORY_CACHE
    if _LOCAL_ROUTER_FACTORY_CACHE is None:
        from local_router import LocalAIRouter

        _LOCAL_ROUTER_FACTORY_CACHE = LocalAIRouter
    return _LOCAL_ROUTER_FACTORY_CACHE()


def _parse_batch_response(text: str, n: int) -> list:
    """Парсит ответ LLM для батча из N задач. Формат: [RESULT_1]...[/RESULT_1] [RESULT_2]...[/RESULT_2]
    Возвращает список строк или None при ошибке."""
    import re

    if not text or n < 1:
        return []
    parts = re.findall(r"\[RESULT_\d+\]\s*(.*?)\s*\[/RESULT_\d+\]", text, re.DOTALL)
    if len(parts) >= n:
        return [p.strip() if p else "" for p in parts[:n]]
    # Fallback: split by |||BATCH_SEP|||
    if "|||BATCH_SEP|||" in text:
        parts = text.split("|||BATCH_SEP|||")
        if len(parts) >= n:
            return [p.strip() if p else "" for p in parts[:n]]
    return []


async def escalate_task_to_board(
    pool,
    task_id: int,
    task_title: str,
    task_description: str,
    last_error: str,
    attempt_count: int,
) -> Optional[str]:
    """
    Эскалация задачи в Совет Директоров после исчерпания попыток (MAX_ATTEMPTS).
    Возвращает текст директивы Совета или None при ошибке.
    """
    question = (
        f"Задача не выполнена после {attempt_count} попыток. Требуется выяснение причин и решение.\n\n"
        f"Задача: {task_title}\n\nОписание: {(task_description or '')[:1500]}\n\n"
        f"Последняя ошибка/ответ: {(last_error or '')[:800]}"
    )
    context = {
        "task_id": task_id,
        "attempt_count": attempt_count,
        "source": "smart_worker_escalation",
    }
    try:
        from strategic_board import consult_board

        result = await consult_board(
            question=question,
            context=context,
            correlation_id=f"task_{task_id}",
            source="task_escalation",
            session_id=None,
            user_id=None,
        )
        if result and isinstance(result, dict):
            return result.get("directive_text") or result.get("directive") or None
        return None
    except Exception as e:
        logger.warning(f"Board escalation failed for task {task_id}: {e}")
        return None


async def process_batch_tasks(pool, tasks: list):
    """Обработка батча задач одним вызовом LLM (ARCHITECTURE_IMPROVEMENTS §2.5).
    Только для задач с metadata.batch_group. При ошибке парсинга — fallback на индивидуальную обработку."""
    if len(tasks) < 2 or len(tasks) > int(os.getenv("SMART_WORKER_BATCH_GROUP_MAX", "3")):
        return False
    bg = tasks[0].get("metadata") or {}
    if isinstance(bg, str):
        try:
            bg = json.loads(bg) if bg else {}
        except Exception:
            bg = {}
    if not bg.get("batch_group"):
        return False
    expert_name = tasks[0].get("assignee", "Виктория")
    src = tasks[0].get("preferred_source")
    model = tasks[0].get("preferred_model")
    if any((t.get("preferred_source") != src or t.get("preferred_model") != model) for t in tasks):
        return False

    prompt_parts = [
        f"You are {expert_name}. Process these {len(tasks)} short tasks. "
        "Return answers in EXACT format: [RESULT_1]answer for task 1[/RESULT_1] [RESULT_2]answer for task 2[/RESULT_2] etc.",
        "",
    ]
    for i, t in enumerate(tasks, 1):
        prompt_parts.append(f"--- Task {i}: {t.get('title', '')} ---")
        prompt_parts.append(str(t.get("description", ""))[:500])
        prompt_parts.append("")
    combined_prompt = "\n".join(prompt_parts)
    router_instance = None
    if src or model:
        try:
            router_instance = _create_local_router()
            if src:
                router_instance._preferred_source = src
            if model:
                router_instance._preferred_model = model
            import ai_core

            if hasattr(ai_core, "_current_router"):
                setattr(ai_core, "_current_router", router_instance)
        except Exception:
            pass

    try:
        llm_timeout = float(os.getenv("SMART_WORKER_LLM_TIMEOUT", "300"))
        report = await asyncio.wait_for(
            run_cursor_agent_smart(combined_prompt, expert_name, router=router_instance),
            timeout=llm_timeout,
        )
        if router_instance:
            router_instance._preferred_source = None
            router_instance._preferred_model = None

        if isinstance(report, tuple):
            report = report[0] if report[0] else (report[1] if len(report) > 1 else None)
        elif isinstance(report, dict):
            report = report.get("response", report.get("text", str(report)))
        else:
            report = str(report) if report else ""
        report_str: str = str(report) if report else ""

        parsed = _parse_batch_response(report_str, len(tasks))
        if parsed and all(len(p) > 10 for p in parsed):
            async with pool.acquire() as conn:
                for t, result in zip(tasks, parsed):
                    await conn.execute(
                        "UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1",
                        t["id"],
                        result,
                    )
                print(f"[{datetime.now()}] ✅ Batch completed: {len(tasks)} tasks (batch_group)")
                return True
    except Exception as e:
        logger.debug("Batch LLM failed, falling back to individual: %s", e)
    if router_instance:
        router_instance._preferred_source = None
        router_instance._preferred_model = None
    return False


def _fast_file_check(task_title: str) -> str | None:
    """
    FAST PATH: отвечает на тривиальные file_check задачи локально без LLM.
    Поддерживает паттерны:
      - 'проверь файл X.py — есть ли там pip install в рантайме'
      - 'проверь файл X.py — есть ли там hardcoded секреты или пароли в первых 30 строках'
      - 'проверь файл X.py — subprocess/eval/exec/hard-coded URL (deep_audit)'
    Возвращает строку-ответ или None если паттерн не совпадает.
    """
    import re as _re

    _pip_pattern = _re.compile(
        r"проверь файл (/app/[\w/._-]+\.py).*pip install.*рантайм",
        _re.IGNORECASE,
    )
    _secret_pattern = _re.compile(
        r"проверь файл (/app/[\w/._-]+\.py).*hardcoded.*секрет",
        _re.IGNORECASE,
    )
    _deep_audit_pattern = _re.compile(
        r"проверь файл (/app/[\w/._-]+\.py).*(subprocess|eval|exec|http[s]?://)",
        _re.IGNORECASE,
    )

    pip_m = _pip_pattern.search(task_title)
    secret_m = _secret_pattern.search(task_title)
    deep_m = _deep_audit_pattern.search(task_title)
    if not pip_m and not secret_m and not deep_m:
        return None

    file_path = (pip_m or secret_m or deep_m).group(1)
    if not os.path.exists(file_path):
        return f"ОК (файл {file_path} не найден на хосте — пропущено)"

    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except OSError as e:
        return f"ОК (ошибка чтения {file_path}: {e})"

    if pip_m:
        matches = []
        for i, line in enumerate(lines, 1):
            if "subprocess" in line and "pip" in line:
                matches.append(f"строка {i}: {line.strip()[:100]}")
            elif "os.system" in line and "pip" in line:
                matches.append(f"строка {i}: {line.strip()[:100]}")
        if matches:
            return "ПРОБЛЕМА: " + "; ".join(matches[:3])
        return "ОК"

    if secret_m:
        import re as _re2

        secret_re = _re2.compile(
            r'(password|secret|passwd|api_key|token)\s*=\s*["\'][^"\']{4,}["\']',
            _re2.IGNORECASE,
        )
        matches = []
        for i, line in enumerate(lines[:30], 1):
            if secret_re.search(line):
                matches.append(f"строка {i}: {line.strip()[:100]}")
        if matches:
            return "ПРОБЛЕМА: " + "; ".join(matches[:3])
        return "ОК"

    if deep_m:
        import re as _re3

        # Ищем опасные паттерны: subprocess.run/call/Popen, eval(, exec(, hardcoded http:// URLs
        _subprocess_re = _re3.compile(r"subprocess\.(run|call|Popen|check_output)", _re3.IGNORECASE)
        _eval_re = _re3.compile(r"\beval\s*\(|\bexec\s*\(")
        _url_re = _re3.compile(r'["\']https?://[^"\']{10,}["\']')
        matches = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _subprocess_re.search(line):
                matches.append(f"строка {i} [subprocess]: {stripped[:100]}")
            elif _eval_re.search(line):
                matches.append(f"строка {i} [eval/exec]: {stripped[:100]}")
            elif _url_re.search(line):
                matches.append(f"строка {i} [hardcoded URL]: {stripped[:100]}")
        if matches:
            return "ПРОБЛЕМА: " + "; ".join(matches[:5])
        return "ОК"

    return None


async def process_task(pool, task):
    global _last_success_ts
    task_id = task["id"]
    expert_name = task["assignee"]
    task_title = task["title"]
    preferred_source = task.get("preferred_source")  # MLX или Ollama
    task_category = task.get("_effective_category", "default")
    task_start_time = time.perf_counter()

    if _PROMETHEUS_AVAILABLE:
        _smart_worker_active.inc()

    # ─── FAST PATH: тривиальные file_check задачи — без LLM, за <1ms ───────────
    fast_result = _fast_file_check(task_title)
    if fast_result is not None:
        # [SINGULARITY 29.0] Guaranteed DB persistence
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tasks SET status='completed', result=$1, updated_at=NOW(), completed_at=NOW(), last_real_progress_at=NOW() WHERE id=$2",
                    fast_result,
                    task_id,
                )
        except Exception as db_err:
            logger.error(f"Failed to save fast-path result for {task_id}: {db_err}")

        # [SINGULARITY 29.1] Episodic Journaling (Fast Path)
        try:
            journal_mgr = ExpertJournalManager(pool)
            await journal_mgr.add_entry(
                expert_id=task.get("assignee_expert_id"),
                task_id=task_id,
                summary=f"Fast-path file check: {task_title}",
                learnings=f"Result: {fast_result}",
                importance=3,
                metadata={"execution_mode": "fast_path"},
            )
        except Exception as j_err:
            logger.debug(f"Journaling failed for fast-path {task_id}: {j_err}")
        return
    # ─────────────────────────────────────────────────────────────────────────────

    # Generate trace_id для полного трейсинга
    import uuid

    trace_id = f"trace_{uuid.uuid4().hex[:12]}"

    print(
        f"[{datetime.now()}] [TRACE:{trace_id}] Expert {expert_name} processing: {task_title} [Source: {preferred_source or 'auto'}]"
    )

    # Heartbeat механизм - обновляем updated_at каждые 30 секунд, чтобы задача не считалась застрявшей
    heartbeat_task = None
    heartbeat_stopped = False

    async def update_heartbeat():
        """Heartbeat с защитой от падений - обновляет updated_at каждые 15 секунд"""
        nonlocal heartbeat_stopped
        while not heartbeat_stopped:
            try:
                async with pool.acquire() as conn:
                    # Проверяем, что задача все еще в in_progress (не была сброшена монитором)
                    status = await conn.fetchval("SELECT status FROM tasks WHERE id = $1", task_id)
                    if status != "in_progress":
                        heartbeat_stopped = True
                        break
                    # Обновляем updated_at - это критично для предотвращения застревания
                    await conn.execute(
                        "UPDATE tasks SET updated_at = NOW() WHERE id = $1 AND status = 'in_progress'",
                        task_id,
                    )
                await asyncio.sleep(15)  # Heartbeat каждые 15 секунд (быстрее для надежности)
            except asyncio.CancelledError:
                heartbeat_stopped = True
                break
            except Exception as e:
                logger.debug(f"Heartbeat error for task {task_id}: {e}")
                # Продолжаем работу даже при ошибке heartbeat
                try:
                    await asyncio.sleep(15)
                except asyncio.CancelledError:
                    heartbeat_stopped = True
                    break

    # Используем транзакцию для атомарности
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Порог «зависшая in_progress» — тот же, что и в главном цикле (STUCK_MINUTES), иначе слоты заняты до 1 ч
            stuck_mins = int(os.getenv("SMART_WORKER_STUCK_MINUTES", "15"))
            # [BUG FIX] RAG-loop stuck: задача обновляет updated_at через heartbeat каждые 15с,
            # поэтому стандартный STUCK_MINUTES не работает.
            # Дополнительный критерий: last_llm_call_at IS NULL (нет LLM-вызова вообще) после 10 мин
            # или last_llm_call_at старше LLM_STUCK_MINUTES (LLM call есть, но завис).
            llm_stuck_mins = int(os.getenv("SMART_WORKER_LLM_STUCK_MINUTES", "10"))
            # Обновляем статус с проверкой, что задача не обрабатывается другим worker'ом
            result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'in_progress',
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'processing_worker', $4::text,
                        'processing_started_at', NOW()::text
                    )
                WHERE id = $1
                AND (
                    status = 'pending'
                    OR (status = 'in_progress' AND updated_at < NOW() - make_interval(mins => $2::int))
                    OR (status = 'in_progress'
                        AND created_at < NOW() - make_interval(mins => $3::int)
                        AND (last_llm_call_at IS NULL
                             OR last_llm_call_at < NOW() - make_interval(mins => $3::int)))
                )
            """,
                task_id,
                stuck_mins,
                llm_stuck_mins,
                expert_name,
            )

            # Если задача уже обрабатывается (не обновилась), пропускаем
            if result == "UPDATE 0":
                print(
                    f"[{datetime.now()}] Task {task_id} already being processed or recently updated, skipping..."
                )
                return

            try:
                from app.expert_aliases import resolve_expert_name_for_db

                resolved_name = resolve_expert_name_for_db(expert_name)
            except ImportError:
                resolved_name = expert_name
            expert_config = await conn.fetchrow(
                "SELECT id, system_prompt, role, department FROM experts WHERE name = $1",
                resolved_name,
            )
            if not expert_config:
                await conn.execute(
                    "UPDATE tasks SET status = 'failed', result = 'Expert not found', updated_at = NOW() WHERE id = $1",
                    task_id,
                )
                return

            # Auto-inject assigned skills + dynamic expert context into runtime prompt.
            try:
                from app.expert_services import get_full_expert_prompt
            except ImportError:
                from expert_services import get_full_expert_prompt

            full_expert_prompt = await get_full_expert_prompt(resolved_name, conn=conn)
            if full_expert_prompt:
                expert_config = dict(expert_config)
                expert_config["system_prompt"] = full_expert_prompt

            # 🌟 МИРОВЫЕ ПРАКТИКИ: Обогащаем задачу контекстом файлов
            task_description = task["description"]
            task_metadata = task.get("metadata", {})
            if isinstance(task_metadata, str):
                try:
                    task_metadata = json.loads(task_metadata)
                except:
                    task_metadata = {}

            # Автоматически читаем файлы из metadata (в executor — sync I/O не должен блокировать event loop и heartbeats)
            try:
                from file_context_enricher import get_file_enricher

                enricher = get_file_enricher()
                loop = asyncio.get_event_loop()
                file_path = task_metadata.get("file_path") or task_metadata.get("file")
                keywords = task_metadata.get("keywords", [])
                if file_path:
                    task_description = await loop.run_in_executor(
                        None,
                        partial(
                            enricher.enrich_task_with_file_context,
                            task_description,
                            file_path=file_path,
                            metadata=task_metadata,
                            keywords=keywords,
                        ),
                    )
                    logger.info(f"✅ Задача {task_id} обогащена контекстом файла: {file_path}")
                elif task_metadata.get("file_paths"):
                    file_paths = task_metadata.get("file_paths", [])
                    task_description = await loop.run_in_executor(
                        None,
                        partial(
                            enricher.enrich_task_with_multiple_files,
                            task_description,
                            file_paths,
                            task_metadata,
                        ),
                    )
                    logger.info(
                        f"✅ Задача {task_id} обогащена контекстом {len(file_paths)} файлов"
                    )
            except ImportError:
                logger.debug("file_context_enricher недоступен, используем базовое описание")
            except Exception as e:
                logger.warning(
                    f"Ошибка обогащения задачи контекстом: {e}, используем базовое описание"
                )

            # Формируем промпт с обогащенным описанием
            # 🌟 МИРОВЫЕ ПРАКТИКИ: Добавляем инструкции о работе с кодом
            file_access_instructions = ""
            if task_metadata.get("file_path") or task_metadata.get("file_paths"):
                file_access_instructions = """
📁 РАБОТА С КОДОМ (МИРОВЫЕ ПРАКТИКИ):
1. В контексте выше есть РЕАЛЬНЫЙ КОД файла(ов) - используй ЕГО для анализа
2. НЕ придумывай технологии, которых нет в коде
3. Если нужно прочитать другие файлы, используй инструмент read_file (если доступен через агента)
4. Анализируй ТОЛЬКО то, что реально есть в коде
5. Используй ТОЛЬКО те технологии, которые реально есть в коде
"""

            # 🌟 СПЕЦИАЛЬНАЯ ОБРАБОТКА: Задачи разведки (до формирования промпта)
            if task_metadata.get("source") in (
                "scout_orchestrator",
                "dashboard_scout",
                "enhanced_scout_orchestrator",
            ):
                try:
                    sys.path.insert(0, os.path.dirname(__file__))
                    from scout_task_processor import process_scout_task

                    logger.info(f"🕵️ Обработка задачи разведки: {task['title']}")
                    scout_result = await process_scout_task(task_metadata, task_description)

                    # Сохраняем результат
                    async with pool.acquire() as conn:
                        async with conn.transaction():
                            # [SINGULARITY 31.2] Update last success timestamp for cognitive health
                            _last_success_ts = int(time.time())
                            await conn.execute(
                                "UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1",
                                task_id,
                                scout_result,
                            )
                    logger.info(f"✅ Задача разведки {task_id} завершена: {scout_result[:100]}...")
                    return  # Выходим, не вызывая LLM
                except ImportError as e:
                    logger.warning(f"scout_task_processor недоступен ({e}), обрабатываем через LLM")
                except Exception as e:
                    logger.error(f"Ошибка обработки задачи разведки: {e}, обрабатываем через LLM")
                    import traceback

                    traceback.print_exc()

            # 🌟 ExpeL-style: подтягиваем релевантные знания по домену эксперта (recall at inference)
            relevant_knowledge_block = ""
            try:
                async with pool.acquire() as conn_k:
                    domain_id = await conn_k.fetchval(
                        "SELECT id FROM domains WHERE name = $1",
                        expert_config.get("department") or "General",
                    )
                    if not domain_id:
                        domain_id = await conn_k.fetchval("SELECT id FROM domains LIMIT 1")
                    if domain_id:
                        rows = await conn_k.fetch(
                            """
                            SELECT content FROM knowledge_nodes
                            WHERE domain_id = $1
                              AND (is_verified = true OR confidence_score > 0.75)
                              AND LENGTH(content) > 20
                            ORDER BY confidence_score DESC, created_at DESC
                            LIMIT 5
                        """,
                            domain_id,
                        )
                        if rows:
                            parts = [
                                f"- {r['content'][:400].strip()}{'...' if len(r['content']) > 400 else ''}"
                                for r in rows
                            ]
                            relevant_knowledge_block = (
                                "\n\n📚 RELEVANT KNOWLEDGE (use when solving):\n" + "\n".join(parts)
                            )
            except Exception as e:
                logger.debug("Relevant knowledge fetch failed: %s", e)

            # П.2 PRINCIPLE_EXPERTS_FIRST: инструкции из скиллов по role/department + по релевантности к задаче (до 3)
            skills_block = ""
            try:
                loop = asyncio.get_event_loop()
                role_lower = (expert_config.get("role") or "").lower()
                dept_lower = (expert_config.get("department") or "").lower()
                skill_folders = []
                for key, folders in ROLE_DEPARTMENT_TO_SKILLS.items():
                    if key in role_lower or key in dept_lower:
                        skill_folders.extend(f for f in folders if f not in skill_folders)
                # П.2 пушка: добавить до 3 скиллов по релевантности к title/description
                task_relevant = await loop.run_in_executor(
                    None,
                    partial(_select_skills_by_relevance_sync, task["title"], task_description, 3),
                )
                for f in task_relevant:
                    if f not in skill_folders:
                        skill_folders.append(f)
                skill_folders = skill_folders[:3]
                if skill_folders:
                    skills_block = await loop.run_in_executor(
                        None, partial(_read_skill_snippets_sync, skill_folders, 2000)
                    )
            except Exception as e:
                logger.debug("Skills block failed: %s", e)

            # П.1 PRINCIPLE_EXPERTS_FIRST: веб-поиск при маркерах актуальности (sync DDGS в run_in_executor, таймаут 10 с)
            web_block = ""

            # [SINGULARITY 29.2] Unified Memory Recall (Episodic + Semantic)
            memory_block = ""
            try:
                memory_svc = MemoryService(pool)
                memory_block = await memory_svc.recall(
                    expert_config["id"], f"{task_title} {task_description}"
                )
            except Exception as m_err:
                logger.debug(f"Memory recall failed: {m_err}")

            if _task_needs_web_search(task["title"], task_description):
                try:
                    loop = asyncio.get_event_loop()
                    query = f"{task['title']} {task_description}"[:200]
                    snippets = await asyncio.wait_for(
                        loop.run_in_executor(None, partial(_web_search_sync, query, 3)),
                        timeout=10.0,
                    )
                    if snippets:
                        web_block = "\n\n🔍 АКТУАЛЬНЫЕ ДАННЫЕ ИЗ ВЕБ-ПОИСКА:\n" + "\n".join(
                            f"- {s}" for s in snippets[:3]
                        )
                except asyncio.TimeoutError:
                    logger.debug("Web search timeout for task %s", task_id)
                except Exception as e:
                    logger.debug("Web search failed: %s", e)

            # 🌟 СПЕЦИАЛЬНАЯ ОБРАБОТКА: Симуляция бизнес-идеи (дашборд)
            if task_metadata.get("source") == "dashboard_simulator":
                sim_id = task_metadata.get("simulation_id")
                if sim_id is not None:
                    try:
                        from simulator import run_simulation as run_sim

                        logger.info(
                            f"🚀 Обработка симуляции бизнес-идеи #{sim_id}: {task['title']}"
                        )
                        await run_sim(int(sim_id))
                        async with pool.acquire() as conn:
                            result_text = await conn.fetchval(
                                "SELECT result FROM simulations WHERE id = $1", int(sim_id)
                            )
                            if result_text:
                                # [SINGULARITY 31.2] Update last success timestamp for cognitive health
                                _last_success_ts = int(time.time())
                                await conn.execute(
                                    "UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1",
                                    task_id,
                                    result_text,
                                )
                                logger.info(
                                    f"✅ Симуляция #{sim_id} завершена, задача {task_id} отмечена выполненной."
                                )
                            else:
                                await conn.execute(
                                    "UPDATE tasks SET status = 'failed', result = 'Симуляция выполнена, но результат не записан', updated_at = NOW() WHERE id = $1",
                                    task_id,
                                )
                        return
                    except ImportError as e:
                        logger.warning(f"simulator недоступен ({e}), обрабатываем через LLM")
                    except Exception as e:
                        logger.error(f"Ошибка симуляции #{sim_id}: {e}", exc_info=True)
                        async with pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE tasks SET status = 'failed', result = $2, updated_at = NOW() WHERE id = $1",
                                task_id,
                                f"Ошибка симуляции: {str(e)}",
                            )
                        return

            prompt = f"""{expert_config["system_prompt"]}

Role: {expert_config["role"]}
Dept: {expert_config["department"]}
{relevant_knowledge_block}
{memory_block}
{skills_block}
{web_block}

TASK: {task["title"]}

DESC: {task_description}
{file_access_instructions}

💡 КРИТИЧЕСКИ ВАЖНО:
- Если в контексте выше есть код файла, используй ЕГО для анализа
- НЕ придумывай технологии, которых нет в коде!
- Если нужно прочитать другие файлы, используй инструмент read_file (если доступен)
"""

    # КРИТИЧНО: Запускаем heartbeat СРАЗУ после перевода в in_progress, ДО вызова run_cursor_agent_smart
    # Это гарантирует, что updated_at будет обновляться даже если обработка зависнет
    heartbeat_task = asyncio.create_task(update_heartbeat())

    # Небольшая задержка, чтобы первый heartbeat успел выполниться
    await asyncio.sleep(0.1)

    # Устанавливаем предпочтительный источник и модель для router (батчи по модели — меньше load/unload на MLX/Ollama)
    router_instance = None
    preferred_model = task.get("preferred_model")
    if preferred_source or preferred_model:
        try:
            router_instance = _create_local_router()
            if preferred_source:
                router_instance._preferred_source = preferred_source
            if preferred_model:
                router_instance._preferred_model = preferred_model
            import ai_core

            if hasattr(ai_core, "_current_router"):
                setattr(ai_core, "_current_router", router_instance)
        except Exception as e:
            logger.debug(f"Could not set preferred source/model: {e}")

    if router_instance:
        router_instance._current_task_id = task_id

    # Причина последнего сбоя (таймаут/исключение) — сохраняем в last_error и передаём в Совет при эскалации
    _last_failure_reason = None
    t_start = time.perf_counter()
    # Выполняем обработку вне транзакции (может быть долгой)
    try:
        try:
            task_source = str((task_metadata or {}).get("source", "")).lower()
            is_delegated_task = bool(
                (task_title and task_title.startswith("🤖 Делегировано"))
                or task_source == "victoria_monster_delegation"
            )
            # Таймаут из env (по умолчанию 300 сек = 5 мин)
            llm_timeout = float(os.getenv("SMART_WORKER_LLM_TIMEOUT", "300"))
            # Делегированные задачи (MONSTER) могут выполняться значительно дольше LLM timeout
            if is_delegated_task:
                llm_timeout = float(os.getenv("WORKER_TASK_TOTAL_TIMEOUT", "3600"))
                logger.info(
                    "⏳ [DELEGATE] Task %s is a delegation task, using extended timeout: %ss",
                    task_id,
                    llm_timeout,
                )
            # Для тяжёлых моделей: учесть время загрузки (30-90 сек); иначе ReadTimeout при первом запросе
            if preferred_model:
                try:
                    from adaptive_concurrency import is_model_heavy

                    if is_model_heavy(preferred_model):
                        mult = float(
                            os.getenv("SMART_WORKER_HEAVY_MODEL_TIMEOUT_MULTIPLIER", "1.5")
                        )
                        llm_timeout = max(llm_timeout, llm_timeout * mult)
                        llm_timeout = min(
                            llm_timeout, 3600
                        )  # [FIX] Increased: 60 min for heavy delegation tasks
                    elif is_delegated_task:
                        llm_timeout = min(llm_timeout, 3600)  # [FIX] Delegation tasks get 60 min
                except ImportError:
                    pass
            # [QUEUE-AGE GUARD] При большом хвосте pending сокращаем timeout
            # для не-делегированных задач, чтобы быстрее освобождать слоты.
            try:
                if not is_delegated_task:
                    async with pool.acquire() as _bp_conn:
                        pending_now = await _bp_conn.fetchval(
                            "SELECT count(*) FROM tasks WHERE status = 'pending'"
                        )
                    pending_threshold = int(os.getenv("SMART_WORKER_BACKLOG_DEGRADE_PENDING", "8"))
                    if int(pending_now or 0) >= pending_threshold:
                        backlog_timeout = float(
                            os.getenv("SMART_WORKER_BACKLOG_TIMEOUT_SEC", "240")
                        )
                        llm_timeout = min(llm_timeout, backlog_timeout)
                        logger.info(
                            "[QUEUE-AGE GUARD] backlog pending=%s >= %s, timeout capped to %.1fs for task %s",
                            pending_now,
                            pending_threshold,
                            llm_timeout,
                            task_id,
                        )
            except Exception as _bp_err:
                logger.debug("Queue-age guard timeout capping failed for %s: %s", task_id, _bp_err)
            # [PROGRESS-GUARD PROFILE] Для задач после RAG-loop reset используем
            # "rescue_fast" профиль: более короткий timeout и предпочтение быстрых рук.
            try:
                execution_profile = str((task_metadata or {}).get("execution_profile", "")).lower()
                if execution_profile == "rescue_fast" and not is_delegated_task:
                    rescue_timeout = float(os.getenv("SMART_WORKER_RESCUE_TIMEOUT_SEC", "180"))
                    llm_timeout = min(llm_timeout, rescue_timeout)
                    if router_instance and not preferred_source:
                        router_instance._preferred_source = os.getenv(
                            "SMART_WORKER_RESCUE_PREFERRED_SOURCE", "ollama"
                        )
                    logger.info(
                        "[PROGRESS-GUARD] rescue_fast profile applied for %s, timeout=%.1fs",
                        task_id,
                        llm_timeout,
                    )
            except Exception as _pg_err:
                logger.debug("Progress-guard profile failed for %s: %s", task_id, _pg_err)
            # [BUG FIX] Mark LLM call BEFORE the actual call so RAG-loop guard knows
            # we're past the RAG phase. Heartbeat updates updated_at every 15s and masks
            # stuck tasks — last_llm_call_at is the only reliable indicator of real progress.
            try:
                async with pool.acquire() as _llm_mark_conn:
                    await _llm_mark_conn.execute(
                        """
                        UPDATE tasks
                        SET last_llm_call_at = NOW(),
                            metadata = jsonb_set(
                                COALESCE(metadata, '{}'::jsonb),
                                '{last_llm_call_at}',
                                to_jsonb(to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')),
                                true
                            )
                        WHERE id = $1 AND status = 'in_progress'
                        """,
                        task_id,
                    )
            except Exception as _lm_err:
                logger.debug(f"[LLM_CALL_MARK] smart_worker: failed for {task_id}: {_lm_err}")
            report = await asyncio.wait_for(
                run_cursor_agent_smart(prompt, expert_name, router=router_instance),
                timeout=llm_timeout,
            )
        except asyncio.TimeoutError:
            _last_failure_reason = "timeout"
            print(f"[{datetime.now()}] ⏱️ Task {task_id} timed out after {llm_timeout}s")
            report = None
        except Exception as e:
            _last_failure_reason = str(e)[:500]
            print(f"[{datetime.now()}] Error calling agent for task {task_id}: {e}")
            import traceback

            traceback.print_exc()
            report = None

        # Получаем использованную модель из router'а
        used_model = None
        if router_instance and hasattr(router_instance, "_used_model"):
            used_model = router_instance._used_model
            # Сохраняем в metadata задачи
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('used_model', $2::text)
                    WHERE id = $1
                """,
                    task_id,
                    str(used_model) if used_model else "",
                )
        # Обрабатываем разные типы ответов
        agent_resp = parse_agent_response(report)
        report = agent_resp.output or agent_resp.error or str(report)

        if agent_resp.status == "processing":
            is_error = True
            _last_failure_reason = "delegation_queued_processing"
            # [ANTI-LOOP] processing-ответ не должен крутиться бесконечно.
            # Учитываем попытки и переводим в failed после лимита.
            async with pool.acquire() as conn:
                attempts_now = await conn.fetchval(
                    """
                    UPDATE tasks
                    SET status = 'pending',
                        updated_at = NOW(),
                        metadata = jsonb_set(
                            jsonb_set(
                                COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                    'last_error', 'delegation_queued_processing',
                                    'last_attempt_failed', true
                                ),
                                '{processing_loop_count}',
                                to_jsonb(COALESCE((metadata->>'processing_loop_count')::int, 0) + 1),
                                true
                            ),
                            '{attempt_count}',
                            to_jsonb(COALESCE((metadata->>'attempt_count')::int, 0) + 1),
                            true
                        )
                    WHERE id = $1
                    RETURNING COALESCE((metadata->>'attempt_count')::int, 0) + 1
                    """,
                    task_id,
                )
                if int(attempts_now or 0) >= MAX_ATTEMPTS:
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = 'failed',
                            updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                'auto_fallback_reason', 'delegation_processing_loop_exhausted'
                            )
                        WHERE id = $1
                    """,
                        task_id,
                    )
            return

        # Логируем ответ для отладки
        print(
            f"[{datetime.now()}] Agent response for task {task_id} (length: {len(report) if report else 0}): {report[:100] if report else 'None'}..."
        )

        # Более мягкая проверка - принимаем любой ответ длиннее 5 символов
        if report and isinstance(report, str) and len(report.strip()) > 5:
            # Отслеживаем производительность модели
            try:
                from model_performance_tracker import get_performance_tracker

                tracker = get_performance_tracker()

                # Вычисляем качество ответа
                quality_score = tracker.calculate_quality_score(report)

                # Определяем использованную модель (из metadata задачи или по умолчанию)
                used_model = "phi3.5:3.8b"  # По умолчанию
                try:
                    async with pool.acquire() as conn:
                        metadata = await conn.fetchval(
                            "SELECT metadata FROM tasks WHERE id = $1", task_id
                        )
                        if metadata and metadata.get("used_model"):
                            used_model = metadata["used_model"]
                except:
                    pass

                # Записываем попытку (латентность от начала обработки до получения ответа)
                latency_ms = int((time.perf_counter() - t_start) * 1000)
                await tracker.record_attempt(
                    task_id=task_id,
                    model=used_model,
                    category="autonomous_worker",
                    success=True,
                    response_length=len(report),
                    latency_ms=latency_ms,
                    quality_score=quality_score,
                )

                # Проверяем, нужно ли переключиться на более мощную модель
                should_upgrade, next_model = await tracker.should_upgrade_model(
                    task_id=task_id,
                    current_model=used_model,
                    category="autonomous_worker",
                    response=report,
                )

                if should_upgrade and next_model:
                    logger.info(
                        f"🔄 [MODEL UPGRADE] Задача {task_id} требует более мощную модель: {next_model}"
                    )
                    # Сохраняем информацию о необходимости апгрейда и возвращаем в pending
                    backoff_seconds = int(os.getenv("SMART_WORKER_MODEL_UPGRADE_RETRY_SEC", "60"))
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET status = 'pending',
                                retry_after = NOW() + make_interval(secs => $3::int),
                                metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                    'model_upgrade_needed', true,
                                    'recommended_model', $2::text,
                                    'next_retry_after', to_char((NOW() + make_interval(secs => $3::int)) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
                                ),
                                updated_at = NOW(),
                                last_real_progress_at = NOW()
                            WHERE id = $1
                        """,
                            task_id,
                            str(next_model) if next_model else "",
                            backoff_seconds,
                        )
                    print(
                        f"[{datetime.now()}] 🔄 Task {task_id} reverted to PENDING for model upgrade "
                        f"to {next_model} (retry_after={backoff_seconds}s)"
                    )
                    return  # Прекращаем текущую обработку, так как задача ушла на апгрейд
            except Exception as e:
                logger.debug(f"Model performance tracking failed: {e}")

        # Проверяем, что ответ не является сообщением об ошибке или пустым (Singularity 24.3 Fix)
        is_error = agent_resp.status == "error"
        if not is_error:
            error_indicators = [
                "⚠️",
                "❌",
                "⌛",
                "Error",
                "failed",
                "недоступен",
                "не могу",
                "Все источники недоступны",
                "Ошибка связи",
            ]
            is_error = (
                any(indicator in str(report) for indicator in error_indicators) if report else True
            )

        # [SWISS-CLOCK] Детектируем LLM-недоступность отдельно —
        # эти случаи нужно re-queue с задержкой, а не эскалировать как логические ошибки
        is_llm_unavailable = bool(
            report
            and isinstance(report, str)
            and any(
                marker in report
                for marker in (
                    "Все источники недоступны",
                    "circuit breaker",
                    "maximum pending requests",
                    "503",
                )
            )
        )

        # Если отчет пустой или None - это ошибка (таймаут или сбой модели)
        if not report or not isinstance(report, str) or len(report.strip()) < 10:
            is_error = True
            is_llm_unavailable = True  # пустой ответ = LLM не ответил
            if not _last_failure_reason:
                _last_failure_reason = "empty_response_or_timeout"

        if is_error:
            # Безопасное логирование ошибки (Singularity 24.3 Fix)
            error_preview = report[:150] if report and isinstance(report, str) else "None/Empty"
            print(
                f"[{datetime.now()}] ⚠️ Agent returned error for task {task_id}: {error_preview}..."
            )

            attempt_count = 0
            try:
                async with pool.acquire() as conn:
                    metadata = await conn.fetchval(
                        "SELECT metadata FROM tasks WHERE id = $1", task_id
                    )
                    # metadata может быть строкой JSON или dict (зависит от asyncpg)
                    if metadata:
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)
                        if isinstance(metadata, dict) and metadata.get("attempt_count"):
                            attempt_count = int(metadata.get("attempt_count", 0))
            except (asyncpg.PostgresError, ValueError, TypeError, json.JSONDecodeError) as e:
                logger.debug(
                    f"Error reading attempt_count for task {task_id}: {e}, using default 0"
                )
                attempt_count = 0
            attempt_count += 1

            # После MAX_ATTEMPTS: rule → эскалация в Совет Директоров → complete с директивой или deferred
            # [SWISS-CLOCK] LLM-недоступность не эскалируем раньше времени — даём MAX_ATTEMPTS попыток
            should_try_rule_or_escalate = attempt_count >= MAX_ATTEMPTS
            if should_try_rule_or_escalate:
                rule_result = None
                try:
                    from task_rule_executor import can_handle as rule_can_handle
                    from task_rule_executor import execute_fallback as rule_execute

                    task_dict = dict(task) if not isinstance(task, dict) else dict(task)
                    if isinstance(task_dict.get("metadata"), str):
                        import json as _json

                        try:
                            task_dict["metadata"] = _json.loads(task_dict["metadata"])
                        except Exception:
                            task_dict["metadata"] = {}
                    if rule_can_handle(task_dict):
                        rule_result = await rule_execute(task_dict)
                except Exception as e:
                    logger.debug("Rule executor failed for task %s: %s", task_id, e)
                if rule_result:
                    from task_rule_executor import finalize_rule_result

                    final_text, meta_patch, db_status = finalize_rule_result(rule_result)
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE tasks SET status = $3, result = $2, updated_at = NOW(),
                                metadata = COALESCE(metadata, '{}'::jsonb) || $4::jsonb
                            WHERE id = $1
                        """,
                            task_id,
                            final_text,
                            db_status,
                            json.dumps(meta_patch),
                        )
                    print(
                        f"[{datetime.now()}] {'✅' if db_status == 'completed' else '⚠️'} "
                        f"Task {task_id} rule_executor → {db_status} "
                        f"(degraded={meta_patch.get('quality_degraded')})"
                    )
                    return
                report_preview = report[:500] if report and isinstance(report, str) else ""
                board_directive = await escalate_task_to_board(
                    pool,
                    task_id,
                    task_title,
                    task_description or "",
                    report_preview,
                    attempt_count,
                )
                final_result = f"""Задача: {task_title}
Статус: AI агент недоступен после {attempt_count} попыток. Задача передана в Совет Директоров.
Ошибка: {(report or "")[:300]}
[deferred_to_human: рекомендуется ручная проверка]"""
                if board_directive:
                    final_result += (
                        f"\n\n--- Решение Совета Директоров ---\n{board_directive[:2000]}"
                    )
                meta_escalation = json.dumps(
                    {
                        "attempt_count": attempt_count,
                        "deferred_to_human": True,
                        "execution_mode": "minimal_response",
                        "board_escalated": True,
                    }
                )
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = 'completed', result = $2, updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb
                        WHERE id = $1
                    """,
                        task_id,
                        final_result,
                        meta_escalation,
                    )
                print(
                    f"[{datetime.now()}] ✅ Task {task_id} completed with board escalation (attempt {attempt_count})"
                )
                return
            # attempt_count < 3 и не LLM unavailable: retry
            else:
                # Записываем неудачную попытку
                try:
                    from model_performance_tracker import get_performance_tracker

                    tracker = get_performance_tracker()
                    used_model = "phi3.5:3.8b"
                    try:
                        async with pool.acquire() as conn:
                            metadata = await conn.fetchval(
                                "SELECT metadata FROM tasks WHERE id = $1", task_id
                            )
                            if metadata and metadata.get("used_model"):
                                used_model = metadata["used_model"]
                    except:
                        pass

                    latency_ms_fail = int((time.perf_counter() - t_start) * 1000)
                    await tracker.record_attempt(
                        task_id=task_id,
                        model=used_model,
                        category="autonomous_worker",
                        success=False,
                        response_length=len(report) if report else 0,
                        latency_ms=latency_ms_fail,
                        quality_score=0.0,
                    )

                    # Проверяем, нужно ли переключиться на более мощную модель
                    should_upgrade, next_model = await tracker.should_upgrade_model(
                        task_id=task_id,
                        current_model=used_model,
                        category="autonomous_worker",
                        response=report,
                    )

                    if should_upgrade and next_model:
                        logger.info(
                            f"🔄 [AUTO UPGRADE] Автоматически переключаемся на {next_model} для задачи {task_id}"
                        )
                        # Обновляем задачу с рекомендованной моделью
                        backoff_seconds = min(300, 30 * (2 ** max(0, attempt_count - 1)))
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE tasks
                                SET status = 'pending',
                                    updated_at = NOW(),
                                    last_real_progress_at = NOW(),
                                    retry_after = NOW() + make_interval(secs => $5::int),
                                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                        'last_attempt_failed', true,
                                        'attempt_count', $2::int,
                                        'last_error', $3::text,
                                        'model_upgrade_needed', true,
                                        'recommended_model', $4::text,
                                        'next_retry_after', to_char((NOW() + make_interval(secs => $5::int)) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
                                    )
                                WHERE id = $1
                            """,
                                task_id,
                                attempt_count,
                                str(report[:500]) if report and isinstance(report, str) else "",
                                str(next_model),
                                backoff_seconds,
                            )
                        print(
                            f"[{datetime.now()}] 🔄 Task {task_id} upgraded to model {next_model} "
                            f"for retry_after={backoff_seconds}s"
                        )
                        return
                except Exception as e:
                    logger.debug(f"Model upgrade check failed: {e}")

                # Возвращаем в pending для повторной попытки
                backoff_seconds = min(300, 30 * (2 ** max(0, attempt_count - 1)))
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = 'pending',
                            updated_at = NOW(),
                            last_real_progress_at = NOW(),
                            retry_after = NOW() + make_interval(secs => $4::int),
                            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                'last_attempt_failed', true,
                                'attempt_count', $2::int,
                                'last_error', $3::text,
                                'next_retry_after', to_char((NOW() + make_interval(secs => $4::int)) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
                            )
                        WHERE id = $1
                    """,
                        task_id,
                        attempt_count,
                        str(report[:500]) if report and isinstance(report, str) else "",
                        backoff_seconds,
                    )
                print(
                    f"[{datetime.now()}] ⚠️ Task {task_id} reverted to PENDING "
                    f"(attempt {attempt_count}/{MAX_ATTEMPTS}, retry_after={backoff_seconds}s)."
                )
            return  # НЕ помечаем как completed!

            # Оптимальная архитектура: проверка результата перед отметкой completed (аналог manager_review в цепочке БД)
            # Неуспешная валидация считается попыткой; после MAX_ATTEMPTS — эскалация в Совет Директоров
            try:
                try:
                    from task_result_validator import validate_task_result
                except ImportError:
                    from app.task_result_validator import validate_task_result
                req_text = (task.get("title") or "") + " " + (task_description or "")
                is_valid, score = validate_task_result(req_text, report or "")
                if not is_valid or score < 0.5:
                    v_attempt_count = 0
                    try:
                        async with pool.acquire() as conn:
                            meta = await conn.fetchval(
                                "SELECT metadata FROM tasks WHERE id = $1", task_id
                            )
                            if meta and (
                                isinstance(meta, dict) and meta.get("attempt_count") is not None
                            ):
                                v_attempt_count = int(meta.get("attempt_count", 0))
                            elif meta and isinstance(meta, str):
                                import json as _j

                                m = _j.loads(meta) if meta else {}
                                v_attempt_count = int(m.get("attempt_count", 0))
                    except Exception:
                        pass
                    v_attempt_count += 1
                    if v_attempt_count >= MAX_ATTEMPTS:
                        last_err = (
                            f"Валидация не пройдена (score={score:.2f}); попыток: {v_attempt_count}"
                        )
                        board_directive = await escalate_task_to_board(
                            pool,
                            task_id,
                            task_title,
                            task_description or "",
                            last_err,
                            v_attempt_count,
                        )
                        final_result = f"""Задача: {task_title}
Статус: Результат не прошёл проверку после {v_attempt_count} попыток. Задача передана в Совет Директоров.
Причина: {last_err}
[deferred_to_human: рекомендуется ручная проверка]"""
                        if board_directive:
                            final_result += (
                                f"\n\n--- Решение Совета Директоров ---\n{board_directive[:2000]}"
                            )
                        meta_v = json.dumps(
                            {
                                "attempt_count": v_attempt_count,
                                "validation_failed": True,
                                "validation_score": float(score),
                                "board_escalated": True,
                                "deferred_to_human": True,
                            }
                        )
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW(),
                                    metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb
                                WHERE id = $1
                            """,
                                task_id,
                                final_result,
                                meta_v,
                            )
                        print(
                            f"[{datetime.now()}] ✅ Task {task_id} completed with board escalation after validation failure (attempt {v_attempt_count})"
                        )
                    else:
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE tasks SET status = 'pending', updated_at = NOW(),
                                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                        'validation_failed', true, 'validation_score', $2::float, 'attempt_count', $3::int
                                    )
                                WHERE id = $1
                            """,
                                task_id,
                                float(score),
                                v_attempt_count,
                            )
                        print(
                            f"[{datetime.now()}] ⚠️ Task {task_id} validation failed (attempt {v_attempt_count}/{MAX_ATTEMPTS}), reverted to pending"
                        )
                    return
            except ImportError:
                pass
            except Exception as e:
                logger.debug(f"Validation skip for task {task_id}: {e}")

        if not is_error:
            # [FIX] Мark task as completed in the success path (was dead code inside if is_error:)
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tasks SET status = 'completed', result = $1, updated_at = NOW(), completed_at = NOW() WHERE id = $2",
                    report,
                    task_id,
                )
            print(f"[{datetime.now()}] ✅ Task {task_id} COMPLETED.")
            duration = time.perf_counter() - task_start_time
            if _PROMETHEUS_AVAILABLE:
                _smart_worker_tasks_total.labels(status="completed").inc()
                _smart_worker_task_duration_seconds.labels(category=task_category).observe(duration)
                _smart_worker_active.dec()
            return
    except Exception as e:
        _last_failure_reason = str(e)[:500]
        print(f"[{datetime.now()}] ❌ Error processing task {task_id}: {e}")
        import traceback

        traceback.print_exc()
        if _PROMETHEUS_AVAILABLE:
            _smart_worker_tasks_total.labels(status="failed").inc()
            _smart_worker_active.dec()
        # Возвращаем задачу в pending при ошибке
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE tasks
                SET status = 'pending',
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('processing_error', $2::text)
                WHERE id = $1
            """,
                task_id,
                _last_failure_reason,
            )

        # [SINGULARITY 29.1] Episodic Journaling (Failure Path)
        try:
            journal_mgr = ExpertJournalManager(pool)
            await journal_mgr.add_entry(
                expert_id=task.get("assignee_expert_id"),
                task_id=task_id,
                summary=f"Task failed: {task_title}",
                learnings=f"Error: {_last_failure_reason}",
                importance=7,
                metadata={"execution_mode": "failure", "error": _last_failure_reason},
            )
        except Exception as j_err:
            logger.debug(f"Journaling failed for failure {task_id}: {j_err}")
    finally:
        # Очищаем предпочтительный источник и модель
        if router_instance:
            if hasattr(router_instance, "_preferred_source"):
                router_instance._preferred_source = None
            if hasattr(router_instance, "_preferred_model"):
                router_instance._preferred_model = None

        # Останавливаем heartbeat в любом случае
        heartbeat_stopped = True
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await asyncio.wait_for(heartbeat_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

    if not (report and isinstance(report, str) and len(report.strip()) > 5):
        # Если агент полностью не отвечает, создаем минимальный ответ и завершаем задачу
        attempt_count = 0
        metadata = None
        try:
            async with pool.acquire() as conn:
                metadata = await conn.fetchval("SELECT metadata FROM tasks WHERE id = $1", task_id)
                if metadata and (
                    isinstance(metadata, dict) and metadata.get("attempt_count") is not None
                ):
                    attempt_count = int(metadata.get("attempt_count", 0))
                elif metadata and isinstance(metadata, str):
                    try:
                        m = json.loads(metadata)
                        attempt_count = int(m.get("attempt_count", 0))
                    except (TypeError, ValueError, KeyError):
                        pass
        except Exception:
            pass
        meta_dict = metadata if isinstance(metadata, dict) else {}
        if not isinstance(meta_dict, dict):
            try:
                meta_dict = json.loads(str(metadata)) if metadata else {}
            except (TypeError, ValueError, json.JSONDecodeError):
                meta_dict = {}
        last_error_text = (
            _last_failure_reason
            or meta_dict.get("processing_error")
            or meta_dict.get("last_error")
            or "empty_or_short_response"
        )
        attempt_count += 1

        # После MAX_ATTEMPTS: rule → эскалация в Совет Директоров → complete
        if attempt_count >= MAX_ATTEMPTS:
            rule_result = None
            try:
                from task_rule_executor import can_handle as rule_can_handle
                from task_rule_executor import execute_fallback as rule_execute

                task_dict = dict(task) if not isinstance(task, dict) else dict(task)
                if isinstance(task_dict.get("metadata"), str):
                    import json as _json

                    try:
                        task_dict["metadata"] = _json.loads(task_dict["metadata"])
                    except Exception:
                        task_dict["metadata"] = {}
                if rule_can_handle(task_dict):
                    rule_result = await rule_execute(task_dict)
            except ImportError:
                pass
            except Exception as e:
                logger.debug("Rule executor failed for task %s: %s", task_id, e)

            final_result = rule_result
            exec_mode = "rule_based" if rule_result else "minimal_response"
            deferred = not rule_result
            rule_meta_patch: dict = {}
            rule_db_status = "completed"
            if rule_result:
                from task_rule_executor import finalize_rule_result

                final_result, rule_meta_patch, rule_db_status = finalize_rule_result(rule_result)
                deferred = bool(rule_meta_patch.get("quality_degraded"))

            if not final_result:
                # Эскалация в Совет Директоров (передаём причину сбоя для контекста)
                task_title = task.get("title", "")
                task_description = task.get("description", "")
                board_directive = await escalate_task_to_board(
                    pool,
                    task_id,
                    task_title,
                    task_description or "",
                    last_error_text,
                    attempt_count,
                )
                print(
                    f"[{datetime.now()}] ⚠️ Task {task_id} failed after {attempt_count} attempts, escalated to board (reason: {last_error_text[:80]}...)"
                )
                final_result = f"""Задача: {task_title}

Статус: Завершена автоматически после {attempt_count} неудачных попыток. Задача передана в Совет Директоров для выяснения причин.
Причина: {last_error_text[:500]}

[deferred_to_human: true — рекомендуется ручная проверка]"""
                if board_directive:
                    final_result += (
                        f"\n\n--- Решение Совета Директоров ---\n{board_directive[:2000]}"
                    )

            assignee_id = task.get("assignee_expert_id")
            meta_payload = {
                "auto_completed": True,
                "attempt_count": attempt_count,
                "execution_mode": exec_mode,
                "deferred_to_human": deferred,
                "board_escalated": not bool(rule_result),
                "last_error": last_error_text[:500],
                **rule_meta_patch,
            }
            # Soft rule-fallback must not look like a clean KPI success.
            final_status = rule_db_status if rule_result else "cancelled"
            if not rule_result:
                meta_payload["quality_degraded"] = True
                meta_payload["failed_requires_intervention"] = True
                meta_payload["kpi_success"] = False
            meta_extra = json.dumps(meta_payload)
            async with pool.acquire() as conn:
                if assignee_id:
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = $3, result = $2, updated_at = NOW(),
                            assignee_expert_id = $4,
                            metadata = COALESCE(metadata, '{}'::jsonb) || $5::jsonb
                        WHERE id = $1
                    """,
                        task_id,
                        final_result,
                        final_status,
                        assignee_id,
                        meta_extra,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = $3, result = $2, updated_at = NOW(),
                            assignee_expert_id = (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                            metadata = COALESCE(metadata, '{}'::jsonb) || $4::jsonb
                        WHERE id = $1
                    """,
                        task_id,
                        final_result,
                        final_status,
                        meta_extra,
                    )
            print(
                f"[{datetime.now()}] {'✅' if final_status == 'completed' else '⚠️'} "
                f"Task {task_id} AUTO-FINISHED → {final_status} after {attempt_count} attempts "
                f"(mode={exec_mode}, board_escalated={not bool(rule_result)})."
            )

            # [SINGULARITY 29.1] Episodic Journaling (Auto-Complete Path)
            try:
                journal_mgr = ExpertJournalManager(pool)
                await journal_mgr.add_entry(
                    expert_id=assignee_id or task.get("assignee_expert_id"),
                    task_id=task_id,
                    summary=f"Task auto-completed after {attempt_count} attempts: {task_title}",
                    learnings=f"Reason: {last_error_text}",
                    importance=6,
                    metadata={"execution_mode": exec_mode, "auto_completed": True},
                )
            except Exception as j_err:
                logger.debug(f"Journaling failed for auto-complete {task_id}: {j_err}")

            if _PROMETHEUS_AVAILABLE:
                _smart_worker_tasks_total.labels(status="completed").inc()
                _smart_worker_active.dec()
        else:
            # [SWISS-CLOCK] Exponential backoff with jitter (AWS best practice — предотвращает thundering herd)
            # base_delay зависит от причины: LLM недоступен → 120s (CB recovery), иначе → 90s
            import random as _random

            base_delay = (
                120 if is_llm_unavailable else int(os.getenv("SMART_WORKER_RETRY_DELAY_SEC", "90"))
            )
            # delay = min(base * 2^(attempt-1), 600) + jitter(0..30)
            exp_delay = min(base_delay * (2 ** max(attempt_count - 1, 0)), 600)
            jitter = _random.randint(0, 30)
            retry_delay_sec = exp_delay + jitter
            next_retry_after = (
                (datetime.utcnow().timestamp() + retry_delay_sec) if retry_delay_sec > 0 else None
            )
            meta_pending = {
                "last_attempt_failed": True,
                "attempt_count": attempt_count,
                "last_error": last_error_text[:500],
                "llm_unavailable": is_llm_unavailable,
            }
            if next_retry_after is not None:
                from datetime import timezone

                # ISO timestamp для фильтра в SELECT
                meta_pending["next_retry_after"] = datetime.fromtimestamp(
                    next_retry_after, tz=timezone.utc
                ).isoformat()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'pending',
                        updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                    WHERE id = $1
                """,
                    task_id,
                    json.dumps(meta_pending),
                )
            print(
                f"[{datetime.now()}] ⚠️ Task {task_id} FAILED (attempt {attempt_count}/{MAX_ATTEMPTS}, reason: {last_error_text[:60]}...). Reverted to pending (retry after {retry_delay_sec}s)."
            )
            if _PROMETHEUS_AVAILABLE:
                _smart_worker_tasks_total.labels(status="retry").inc()
                _smart_worker_active.dec()

    # Останавливаем heartbeat в любом случае
    heartbeat_stopped = True
    if heartbeat_task and not heartbeat_task.done():
        heartbeat_task.cancel()
        try:
            await asyncio.wait_for(heartbeat_task, timeout=1.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass


async def main():
    print(f"[{datetime.now()}] 🚀 AUTONOMOUS SMART WORKER v4.0 (PARALLEL) starting...")
    pool = await get_pool()

    # [SINGULARITY 25.0] Reset Ollama global slots counter on startup.
    # Анна (QA): if the worker was killed (kill -9) mid-request, slots may not have been released.
    # The TTL (60s) handles it eventually, but resetting here ensures immediate clean slate.
    try:
        from redis_manager import RedisManager as _StartupRM

        await _StartupRM().reset_ollama_slots()
    except Exception as _rst_err:
        print(f"[{datetime.now()}] ⚠️ [STARTUP] Ollama slots reset failed: {_rst_err}")

    # Конфигурация параллельной обработки (Backend/SRE: пул достаточен при динамическом N — max_size по потолку)
    MAX_CONCURRENT_TASKS = int(os.getenv("SMART_WORKER_MAX_CONCURRENT", "10"))
    BATCH_SIZE = int(os.getenv("SMART_WORKER_BATCH_SIZE", "50"))
    ADAPTIVE_CONCURRENCY = os.getenv("SMART_WORKER_ADAPTIVE_CONCURRENCY", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    print(
        f"[{datetime.now()}] ⚡ Parallel processing: max {MAX_CONCURRENT_TASKS} concurrent, batch size: {BATCH_SIZE}, adaptive={ADAPTIVE_CONCURRENCY}"
    )

    # [SINGULARITY 31.2] Global Worker Heartbeat for Orchestrator
    async def _global_worker_heartbeat():
        from redis_manager import redis_manager

        RUNTIME_WORKER_HEARTBEAT_KEY = os.getenv(
            "RUNTIME_WORKER_HEARTBEAT_KEY", "runtime:expert_heartbeats"
        )
        while True:
            try:
                client = await redis_manager.get_client()
                # Report as 'Виктория' or from env
                report_name = os.getenv("EXPERT_NAME", "Виктория")
                payload = json.dumps(
                    {
                        "ts": int(time.time()),
                        "consumer": f"smart_worker_{os.uname()[1]}",
                        "pid": os.getpid(),
                        "expert_name": report_name,
                        "last_success_ts": _last_success_ts,
                        "worker_type": "smart_autonomous",
                    }
                )
                await client.hset(RUNTIME_WORKER_HEARTBEAT_KEY, report_name, payload)
            except Exception as e:
                logger.debug(f"Global heartbeat failed: {e}")
            await asyncio.sleep(30)

    asyncio.create_task(_global_worker_heartbeat())

    # Запускаем систему самообучения корпорации (Singularity 10.0)
    try:
        from corporation_self_learning import get_corporation_learner

        learner = get_corporation_learner()
        # Запускаем в фоне
        asyncio.create_task(learner.start_continuous_learning(interval_hours=6))
        print(f"[{datetime.now()}] 🧠 [SINGULARITY 10.0] Система самообучения запущена")
    except Exception as e:
        logger.debug(f"Could not start corporation learning: {e}")

    # Интервал сброса зависших in_progress: по умолчанию 15 мин (раньше 1 ч — из‑за этого при 10 зависших только 5 pending обрабатывались за цикл, ~5 задач/час)
    STUCK_MINUTES = int(os.getenv("SMART_WORKER_STUCK_MINUTES", "15"))
    BACKLOG_STUCK_MINUTES = int(os.getenv("SMART_WORKER_BACKLOG_STUCK_MINUTES", str(STUCK_MINUTES)))
    BACKLOG_STUCK_PENDING_THRESHOLD = int(
        os.getenv("SMART_WORKER_BACKLOG_STUCK_PENDING_THRESHOLD", "5")
    )
    # [BUG FIX] RAG-loop stuck detection: сбрасываем задачи у которых нет LLM-вызова > N мин,
    # даже если heartbeat обновляет updated_at. Этот порог защищает от RAG infinite loop.
    LLM_STUCK_MINUTES = int(os.getenv("SMART_WORKER_LLM_STUCK_MINUTES", "10"))
    BACKLOG_LLM_STUCK_MINUTES = int(
        os.getenv("SMART_WORKER_BACKLOG_LLM_STUCK_MINUTES", str(LLM_STUCK_MINUTES))
    )
    HARD_INPROGRESS_TIMEOUT_MINUTES = int(
        os.getenv("SMART_WORKER_HARD_INPROGRESS_TIMEOUT_MINUTES", "8")
    )
    BACKLOG_HARD_INPROGRESS_TIMEOUT_MINUTES = int(
        os.getenv(
            "SMART_WORKER_BACKLOG_HARD_INPROGRESS_TIMEOUT_MINUTES",
            str(HARD_INPROGRESS_TIMEOUT_MINUTES),
        )
    )
    HARD_CAP_MAX_RESETS = int(os.getenv("SMART_WORKER_HARD_CAP_MAX_RESETS", "1"))
    AUTO_REQUEUE_DELEGATION = os.getenv("AUTO_REQUEUE_DELEGATION", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    AUTO_REQUEUE_BATCH = int(os.getenv("AUTO_REQUEUE_DELEGATION_BATCH", "10"))
    AUTO_REQUEUE_MAX_PER_TASK = int(os.getenv("AUTO_REQUEUE_MAX_PER_TASK", "3"))
    RAG_LOOP_MAX_RESETS = int(os.getenv("SMART_WORKER_RAG_LOOP_MAX_RESETS", "2"))
    DELEGATION_ALERT_THRESHOLD = int(os.getenv("DELEGATION_STUCK_ALERT_THRESHOLD", "3"))
    WATCHDOG_INTERVAL_SEC = int(os.getenv("SMART_WORKER_WATCHDOG_INTERVAL_SEC", "10"))
    WATCHDOG_BACKGROUND_ENABLED = os.getenv(
        "SMART_WORKER_WATCHDOG_BACKGROUND_ENABLED", "false"
    ).lower() in ("true", "1", "yes")
    WORK_ITEM_TIMEOUT_SEC = int(os.getenv("SMART_WORKER_WORK_ITEM_TIMEOUT_SEC", "420"))

    async def _watchdog_cycle():
        async with pool.acquire() as conn:
            pending_now = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'pending'")
            pending_now = int(pending_now or 0)
            effective_stuck_minutes = (
                BACKLOG_STUCK_MINUTES
                if pending_now >= BACKLOG_STUCK_PENDING_THRESHOLD
                else STUCK_MINUTES
            )
            effective_llm_stuck_minutes = (
                BACKLOG_LLM_STUCK_MINUTES
                if pending_now >= BACKLOG_STUCK_PENDING_THRESHOLD
                else LLM_STUCK_MINUTES
            )

            stuck_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'pending', updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'stuck_reset', true, 'previous_status', 'in_progress',
                        'cancel_reason', $2::jsonb
                    )
                WHERE status = 'in_progress'
                  AND updated_at < NOW() - make_interval(mins => $1::int)
            """,
                effective_stuck_minutes,
                json.dumps(
                    _structured_cancel_reason(
                        "stuck_in_progress_timeout",
                        "smart_worker_watchdog",
                        f"no progress by updated_at for >{effective_stuck_minutes} minutes",
                    )
                ),
            )
            if stuck_result and stuck_result.startswith("UPDATE"):
                n = stuck_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] 🔄 Вернуто в очередь зависших задач (>{effective_stuck_minutes} мин): {n}"
                    )

            rag_stuck_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'pending', updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'stuck_reset', true, 'reset_reason', 'rag_loop_no_llm_call',
                        'previous_status', 'in_progress',
                        'execution_profile', 'rescue_fast',
                        'progress_guard_requeue_count',
                        (
                            CASE
                                WHEN COALESCE(metadata->>'progress_guard_requeue_count', '') ~ '^[0-9]+$'
                                THEN (metadata->>'progress_guard_requeue_count')::int
                                ELSE 0
                            END
                        ) + 1,
                        'cancel_reason', $2::jsonb
                    )
                WHERE status = 'in_progress'
                  AND created_at < NOW() - make_interval(mins => $1::int)
                  AND (
                      last_llm_call_at IS NULL
                      OR last_llm_call_at < NOW() - make_interval(mins => $1::int)
                  )
            """,
                effective_llm_stuck_minutes,
                json.dumps(
                    _structured_cancel_reason(
                        "rag_loop_no_llm_call",
                        "smart_worker_watchdog",
                        f"last_llm_call_at is stale or null for >{effective_llm_stuck_minutes} minutes",
                    )
                ),
            )
            if rag_stuck_result and rag_stuck_result.startswith("UPDATE"):
                n = rag_stuck_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] 🔁 [RAG-LOOP GUARD] Сброшено задач без LLM-вызова (>{effective_llm_stuck_minutes} мин): {n}"
                    )
            rag_loop_breaker_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'cancelled', updated_at = NOW(),
                    retry_after = NULL,
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'auto_fallback_reason', 'rag_loop_no_llm_call_exhausted',
                        'failed_requires_intervention', true,
                        'diagnostic_path', 'progress_guard_manual_triage'
                    )
                WHERE status = 'pending'
                  AND COALESCE(metadata->>'reset_reason', '') = 'rag_loop_no_llm_call'
                  AND (
                    CASE
                      WHEN COALESCE(metadata->>'progress_guard_requeue_count', '') ~ '^[0-9]+$'
                      THEN (metadata->>'progress_guard_requeue_count')::int
                      ELSE 0
                    END
                  ) >= $1::int
                  AND COALESCE(result, '') = ''
                  AND completed_at IS NULL
            """,
                RAG_LOOP_MAX_RESETS,
            )
            if rag_loop_breaker_result and rag_loop_breaker_result.startswith("UPDATE"):
                n = rag_loop_breaker_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] 🧯 [RAG-LOOP BREAKER] Переведено в cancelled/manual triage: {n}"
                    )

            effective_hard_inprogress_minutes = (
                BACKLOG_HARD_INPROGRESS_TIMEOUT_MINUTES
                if pending_now >= BACKLOG_STUCK_PENDING_THRESHOLD
                else HARD_INPROGRESS_TIMEOUT_MINUTES
            )
            hard_stuck_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'pending', updated_at = NOW(),
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                            'stuck_reset', true, 'reset_reason', 'hard_in_progress_runtime_cap',
                            'previous_status', 'in_progress',
                            'cancel_reason', $2::jsonb
                        ),
                        '{attempt_count}',
                        to_jsonb(COALESCE((metadata->>'attempt_count')::int, 0) + 1),
                        true
                    )
                WHERE status = 'in_progress'
                  AND COALESCE(metadata->>'processing_started_at', '') <> ''
                  AND (metadata->>'processing_started_at')::timestamptz <
                      NOW() - make_interval(mins => $1::int)
            """,
                effective_hard_inprogress_minutes,
                json.dumps(
                    _structured_cancel_reason(
                        "hard_in_progress_runtime_cap",
                        "smart_worker_watchdog",
                        f"in_progress runtime exceeded {effective_hard_inprogress_minutes} minutes",
                    )
                ),
            )
            if hard_stuck_result and hard_stuck_result.startswith("UPDATE"):
                n = hard_stuck_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] ⛑️ [HARD CAP] Сброшено долгих in_progress задач (>{effective_hard_inprogress_minutes} мин): {n}"
                    )
            hard_cap_complete_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'completed',
                    retry_after = NULL,
                    updated_at = NOW(),
                    completed_at = COALESCE(completed_at, NOW()),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'auto_fallback_reason', 'hard_in_progress_runtime_cap_recovered',
                        'recovered_by', 'smart_worker_watchdog',
                        'recovered_at', NOW()::text
                    )
                WHERE status = 'pending'
                  AND COALESCE(metadata->>'reset_reason', '') = 'hard_in_progress_runtime_cap'
                  AND (
                    COALESCE(metadata->>'completion_reason', '') = 'worker_success'
                    OR COALESCE(result, '') <> ''
                    OR completed_at IS NOT NULL
                  )
            """
            )
            if hard_cap_complete_result and hard_cap_complete_result.startswith("UPDATE"):
                n = hard_cap_complete_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] ✅ [HARD CAP] Восстановлено в completed по готовому result: {n}"
                    )
            curiosity_defer_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'pending',
                    retry_after = NOW() + INTERVAL '3 minutes',
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'auto_fallback_reason', 'hard_in_progress_runtime_cap_curiosity_deferred',
                        'next_retry_after', to_char((NOW() + INTERVAL '3 minutes') AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
                    )
                WHERE status = 'pending'
                  AND COALESCE(metadata->>'reset_reason', '') = 'hard_in_progress_runtime_cap'
                  AND COALESCE(metadata->>'reason', '') = 'curiosity_engine_starvation'
                  AND COALESCE((metadata->>'attempt_count')::int, 0) >= $1::int
                  AND COALESCE(result, '') = ''
                  AND completed_at IS NULL
            """,
                HARD_CAP_MAX_RESETS,
            )
            if curiosity_defer_result and curiosity_defer_result.startswith("UPDATE"):
                n = curiosity_defer_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] ⏭️ [HARD CAP] Curiosity tasks deferred instead of failed: {n}"
                    )

            delegation_defer_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'pending',
                    retry_after = NOW() + INTERVAL '5 minutes',
                    updated_at = NOW(),
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                            'auto_fallback_reason', 'hard_in_progress_runtime_cap_delegation_deferred',
                            'next_retry_after', to_char((NOW() + INTERVAL '5 minutes') AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
                        ),
                        '{hard_cap_defer_count}',
                        to_jsonb(COALESCE((metadata->>'hard_cap_defer_count')::int, 0) + 1),
                        true
                    )
                WHERE status = 'pending'
                  AND COALESCE(metadata->>'reset_reason', '') = 'hard_in_progress_runtime_cap'
                  AND COALESCE(metadata->>'reason', '') <> 'curiosity_engine_starvation'
                  AND COALESCE(metadata->>'source', '') = 'victoria_monster_delegation'
                  AND COALESCE((metadata->>'attempt_count')::int, 0) >= $1::int
                  AND COALESCE((metadata->>'hard_cap_defer_count')::int, 0) < 2
                  AND COALESCE(result, '') = ''
                  AND completed_at IS NULL
            """,
                HARD_CAP_MAX_RESETS,
            )
            if delegation_defer_result and delegation_defer_result.startswith("UPDATE"):
                n = delegation_defer_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] ⏭️ [HARD CAP] Delegation tasks deferred before final fail: {n}"
                    )

            hard_fail_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'failed', updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'auto_fallback_reason', 'hard_in_progress_runtime_cap_exhausted'
                    )
                WHERE status = 'pending'
                  AND COALESCE(metadata->>'reset_reason', '') = 'hard_in_progress_runtime_cap'
                  AND COALESCE(metadata->>'reason', '') <> 'curiosity_engine_starvation'
                  AND COALESCE((metadata->>'attempt_count')::int, 0) >= $1::int
                  AND COALESCE(metadata->>'source', '') <> 'victoria_monster_delegation'
                  AND COALESCE(result, '') = ''
                  AND completed_at IS NULL
            """,
                HARD_CAP_MAX_RESETS,
            )
            if hard_fail_result and hard_fail_result.startswith("UPDATE"):
                n = hard_fail_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] 🧯 [HARD CAP] Переведено в failed после исчерпания попыток: {n}"
                    )
            delegation_manual_result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'cancelled',
                    updated_at = NOW(),
                    retry_after = NULL,
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'auto_fallback_reason', 'hard_in_progress_runtime_cap_delegation_manual_triage',
                        'failed_requires_intervention', true,
                        'diagnostic_path', 'delegation_manual_triage'
                    )
                WHERE status = 'pending'
                  AND COALESCE(metadata->>'reset_reason', '') = 'hard_in_progress_runtime_cap'
                  AND COALESCE(metadata->>'source', '') = 'victoria_monster_delegation'
                  AND COALESCE((metadata->>'attempt_count')::int, 0) >= $1::int
                  AND COALESCE((metadata->>'hard_cap_defer_count')::int, 0) >= 2
                  AND COALESCE(result, '') = ''
                  AND completed_at IS NULL
            """,
                HARD_CAP_MAX_RESETS,
            )
            if delegation_manual_result and delegation_manual_result.startswith("UPDATE"):
                n = delegation_manual_result.split()[-1]
                if n != "0":
                    print(
                        f"[{datetime.now()}] 🧭 [HARD CAP] Delegation moved to manual triage (cancelled): {n}"
                    )

            if AUTO_REQUEUE_DELEGATION:
                restored_n = await _auto_requeue_delegation(
                    conn,
                    max_rows=AUTO_REQUEUE_BATCH,
                    max_requeues_per_task=AUTO_REQUEUE_MAX_PER_TASK,
                )
                if restored_n > 0:
                    print(
                        f"[{datetime.now()}] ♻️ [AUTO_REQUEUE_DELEGATION] Restored tasks: {restored_n}"
                    )

            await _emit_delegation_metrics(conn, DELEGATION_ALERT_THRESHOLD)

    async def _watchdog_loop():
        while True:
            try:
                await _watchdog_cycle()
            except Exception as watchdog_err:
                logger.warning("Watchdog cycle failed: %s", watchdog_err)
            await asyncio.sleep(max(2, WATCHDOG_INTERVAL_SEC))

    if WATCHDOG_BACKGROUND_ENABLED:
        asyncio.create_task(_watchdog_loop())
        print(
            f"[{datetime.now()}] 🛡️ Watchdog loop started (interval={WATCHDOG_INTERVAL_SEC}s, llm_stuck={LLM_STUCK_MINUTES}m/{BACKLOG_LLM_STUCK_MINUTES}m under backlog)"
        )
    else:
        print(f"[{datetime.now()}] 🛡️ Watchdog background loop disabled; using inline watchdog path")

    while True:
        try:
            # Вернуть зависшие in_progress (> N мин) в pending, чтобы воркер их подхватил
            async with pool.acquire() as conn:
                pending_now = await conn.fetchval(
                    "SELECT count(*) FROM tasks WHERE status = 'pending'"
                )
                pending_now = int(pending_now or 0)
                effective_stuck_minutes = (
                    BACKLOG_STUCK_MINUTES
                    if pending_now >= BACKLOG_STUCK_PENDING_THRESHOLD
                    else STUCK_MINUTES
                )
                effective_llm_stuck_minutes = (
                    BACKLOG_LLM_STUCK_MINUTES
                    if pending_now >= BACKLOG_STUCK_PENDING_THRESHOLD
                    else LLM_STUCK_MINUTES
                )
                stuck_result = await conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'pending', updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                            'stuck_reset', true, 'previous_status', 'in_progress',
                            'cancel_reason', $2::jsonb
                        )
                    WHERE status = 'in_progress'
                      AND updated_at < NOW() - make_interval(mins => $1::int)
                """,
                    effective_stuck_minutes,
                    json.dumps(
                        _structured_cancel_reason(
                            "stuck_in_progress_timeout",
                            "smart_worker_watchdog",
                            f"no progress by updated_at for >{effective_stuck_minutes} minutes",
                        )
                    ),
                )
                if stuck_result and stuck_result.startswith("UPDATE"):
                    n = stuck_result.split()[-1]
                    if n != "0":
                        print(
                            f"[{datetime.now()}] 🔄 Вернуто в очередь зависших задач (>{effective_stuck_minutes} мин): {n}"
                        )

                # [BUG FIX] RAG-loop guard: задачи, у которых нет LLM-вызова > LLM_STUCK_MINUTES,
                # застряли в RAG-петле. Heartbeat маскирует их от стандартного STUCK check.
                rag_stuck_result = await conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'pending', updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                            'stuck_reset', true, 'reset_reason', 'rag_loop_no_llm_call',
                            'previous_status', 'in_progress',
                            'execution_profile', 'rescue_fast',
                            'progress_guard_requeue_count',
                            (
                                CASE
                                    WHEN COALESCE(metadata->>'progress_guard_requeue_count', '') ~ '^[0-9]+$'
                                    THEN (metadata->>'progress_guard_requeue_count')::int
                                    ELSE 0
                                END
                            ) + 1,
                            'cancel_reason', $2::jsonb
                        )
                    WHERE status = 'in_progress'
                      AND created_at < NOW() - make_interval(mins => $1::int)
                      AND (
                          last_llm_call_at IS NULL
                          OR last_llm_call_at < NOW() - make_interval(mins => $1::int)
                      )
                """,
                    effective_llm_stuck_minutes,
                    json.dumps(
                        _structured_cancel_reason(
                            "rag_loop_no_llm_call",
                            "smart_worker_watchdog",
                            f"last_llm_call_at is stale or null for >{effective_llm_stuck_minutes} minutes",
                        )
                    ),
                )
                if rag_stuck_result and rag_stuck_result.startswith("UPDATE"):
                    n = rag_stuck_result.split()[-1]
                    if n != "0":
                        print(
                            f"[{datetime.now()}] 🔁 [RAG-LOOP GUARD] Сброшено задач без LLM-вызова (>{effective_llm_stuck_minutes} мин): {n}"
                        )
                rag_loop_breaker_result = await conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'cancelled', updated_at = NOW(),
                        retry_after = NULL,
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                            'auto_fallback_reason', 'rag_loop_no_llm_call_exhausted',
                            'failed_requires_intervention', true,
                            'diagnostic_path', 'progress_guard_manual_triage'
                        )
                    WHERE status = 'pending'
                      AND COALESCE(metadata->>'reset_reason', '') = 'rag_loop_no_llm_call'
                      AND (
                        CASE
                          WHEN COALESCE(metadata->>'progress_guard_requeue_count', '') ~ '^[0-9]+$'
                          THEN (metadata->>'progress_guard_requeue_count')::int
                          ELSE 0
                        END
                      ) >= $1::int
                      AND COALESCE(result, '') = ''
                      AND completed_at IS NULL
                """,
                    RAG_LOOP_MAX_RESETS,
                )
                if rag_loop_breaker_result and rag_loop_breaker_result.startswith("UPDATE"):
                    n = rag_loop_breaker_result.split()[-1]
                    if n != "0":
                        print(
                            f"[{datetime.now()}] 🧯 [RAG-LOOP BREAKER] Переведено в cancelled/manual triage: {n}"
                        )

                # [POLICY] Автовосстановление delegation-задач из failed/cancelled в pending.
                if AUTO_REQUEUE_DELEGATION:
                    restored_n = await _auto_requeue_delegation(
                        conn,
                        max_rows=AUTO_REQUEUE_BATCH,
                        max_requeues_per_task=AUTO_REQUEUE_MAX_PER_TASK,
                    )
                    if restored_n > 0:
                        print(
                            f"[{datetime.now()}] ♻️ [AUTO_REQUEUE_DELEGATION] Restored tasks: {restored_n}"
                        )

                # Метрики + alert по stuck delegation (failed+cancelled).
                await _emit_delegation_metrics(conn, DELEGATION_ALERT_THRESHOLD)

            # ═══════════════════════════════════════════════════════════════════════════════
            # BACKPRESSURE: проверка перегрузки MLX/Ollama ПЕРЕД взятием задач (SRE, Елена)
            # Если оба бэкенда перегружены — не брать новые задачи, подождать
            # ═══════════════════════════════════════════════════════════════════════════════
            if ADAPTIVE_CONCURRENCY:
                try:
                    from adaptive_concurrency import check_backends_overload

                    is_overloaded, overload_reason = await check_backends_overload()
                    if is_overloaded:
                        allow_probe_when_idle = os.getenv(
                            "SMART_WORKER_OVERLOAD_ALLOW_PROBE", "true"
                        ).lower() in ("true", "1", "yes")
                        if allow_probe_when_idle:
                            async with pool.acquire() as conn:
                                pending_probe = int(
                                    await conn.fetchval(
                                        "SELECT count(*) FROM tasks WHERE status = 'pending'"
                                    )
                                    or 0
                                )
                                in_progress_probe = int(
                                    await conn.fetchval(
                                        "SELECT count(*) FROM tasks WHERE status = 'in_progress'"
                                    )
                                    or 0
                                )
                            if pending_probe > 0 and in_progress_probe == 0:
                                print(
                                    f"[{datetime.now()}] ⚠️ BACKPRESSURE soft-bypass: overloaded, but queue has pending={pending_probe} and no in_progress. Taking probe batch."
                                )
                                is_overloaded = False
                        if is_overloaded:
                            print(
                                f"[{datetime.now()}] ⏸️ BACKPRESSURE: {overload_reason}. Ожидание 10 сек..."
                            )
                            await asyncio.sleep(10)
                            continue  # Не брать задачи, вернуться к началу цикла
                except ImportError:
                    pass  # Функция не реализована, продолжить без проверки
                except Exception as e:
                    logger.debug(f"Backpressure check failed: {e}")

            # ═══════════════════════════════════════════════════════════════════════════════
            # BACKPRESSURE: Лимит ожидающих задач (Stability & Performance Watchdog)
            # ═══════════════════════════════════════════════════════════════════════════════
            try:
                async with pool.acquire() as conn:
                    pending_count = await conn.fetchval(
                        "SELECT count(*) FROM tasks WHERE status = 'pending'"
                    )
                    in_progress_count = await conn.fetchval(
                        "SELECT count(*) FROM tasks WHERE status = 'in_progress'"
                    )
                    llm_stuck_mins = int(os.getenv("SMART_WORKER_LLM_STUCK_MINUTES", "10"))
                    stale_in_progress = await conn.fetchval(
                        """
                        SELECT count(*)
                        FROM tasks
                        WHERE status = 'in_progress'
                          AND (
                            last_llm_call_at IS NULL
                            OR last_llm_call_at < NOW() - make_interval(mins => $1::int)
                          )
                        """,
                        llm_stuck_mins,
                    )
                    max_pending = int(os.getenv("SMART_WORKER_MAX_PENDING", "10"))
                    # [WATCHDOG FIX] Не блокируем воркер только из-за большого pending.
                    # Иначе при всплеске очередь может "замерзнуть" (starvation).
                    # Блокируем новый pick только если одновременно уже много in_progress.
                    if (
                        pending_count >= max_pending
                        and in_progress_count >= max(1, MAX_CONCURRENT_TASKS)
                        and int(stale_in_progress or 0) == 0
                    ):
                        print(
                            f"[{datetime.now()}] ⏸️ BACKPRESSURE: pending={pending_count}/{max_pending}, "
                            f"in_progress={in_progress_count}, stale_in_progress={stale_in_progress}. Waiting 10s..."
                        )
                        await asyncio.sleep(10)
                        continue
            except Exception as e:
                logger.debug(f"Pending tasks backpressure check failed: {e}")

            # Используем LEFT JOIN чтобы обрабатывать задачи даже если эксперт не найден
            # Приоритизируем задачи с высокой bug_probability (Code-Smell Predictor, Singularity 9.0)
            async with pool.acquire() as conn:
                tasks = await conn.fetch(
                    """
                    SELECT t.id, t.title, t.description, t.metadata,
                           COALESCE(e.name, 'Виктория') as assignee,
                           COALESCE(e.id, (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1)) as assignee_expert_id,
                           COALESCE((t.metadata->>'bug_probability')::float, 0.0) as bug_probability
                    FROM tasks t
                    LEFT JOIN experts e ON t.assignee_expert_id = e.id
                    WHERE t.status = 'pending'
                      AND (
                        t.metadata->>'source' IN (
                          'scout_orchestrator', 'dashboard_scout', 'enhanced_scout_orchestrator',
                          'dashboard_simulator', 'victoria_queue', 'expert_tasks',
                          'victoria_monster_delegation'
                        )
                        OR t.metadata->>'source' IS NULL
                      )
                      AND (
                        COALESCE(t.metadata->>'target_expert', '') = ''
                        OR (
                          t.assignee_expert_id IS NOT NULL
                          AND t.metadata->>'source' = 'victoria_monster_delegation'
                        )
                      )
                      AND (t.metadata->>'next_retry_after' IS NULL OR (t.metadata->>'next_retry_after')::timestamptz < NOW())
                      AND (t.retry_after IS NULL OR t.retry_after < NOW())
                      AND COALESCE(t.metadata->>'source', '') != 'orchestration_tracking'
                    ORDER BY
                        COALESCE((t.metadata->>'bug_probability')::float, 0.0) DESC,  -- Приоритет: задачи с высокой bug_probability
                        COALESCE((t.metadata->>'attempt_count')::int, 0) ASC,  -- [SWISS-CLOCK] retry-задачи ниже свежих (thundering herd guard)
                        t.created_at ASC
                    LIMIT $1
                """,
                    BATCH_SIZE,
                )

            if tasks:
                # Адаптивный параллелизм: N по CPU/памяти и MLX/Ollama (ADAPTIVE_WORKER_CONCURRENCY_PLAN, SRE/Performance)
                effective_n = MAX_CONCURRENT_TASKS
                adaptive_metrics = {}
                if ADAPTIVE_CONCURRENCY:
                    try:
                        from adaptive_concurrency import get_effective_concurrent

                        effective_n, adaptive_metrics = await get_effective_concurrent(
                            n_max=MAX_CONCURRENT_TASKS, n_min=1
                        )
                        # Логируем метрики раз в цикл (SRE: метрики для алертов)
                        print(
                            f"[{datetime.now()}] 📊 Adaptive N={effective_n} (max={MAX_CONCURRENT_TASKS}) | "
                            f"host RAM={adaptive_metrics.get('host_ram_percent', '?')}% CPU={adaptive_metrics.get('host_cpu_percent', '?')}% | "
                            f"MLX {adaptive_metrics.get('mlx_active', '?')}/{adaptive_metrics.get('mlx_max', '?')} "
                            f"Ollama active={adaptive_metrics.get('ollama_active', '?')}"
                        )
                    except Exception as e:
                        logger.debug("Adaptive concurrency failed, using max: %s", e)
                        effective_n = MAX_CONCURRENT_TASKS
                # [BURST MODE] При большом хвосте pending разрешаем мягкий burst,
                # чтобы не накапливать очередь из легких задач.
                try:
                    burst_threshold = int(os.getenv("SMART_WORKER_BURST_PENDING_THRESHOLD", "8"))
                    burst_max = int(
                        os.getenv(
                            "SMART_WORKER_BURST_MAX_CONCURRENT",
                            str(MAX_CONCURRENT_TASKS),
                        )
                    )
                    if pending_count >= burst_threshold and burst_max > effective_n:
                        prev_n = effective_n
                        effective_n = min(burst_max, len(tasks))
                        print(
                            f"[{datetime.now()}] ⚡ BURST MODE: pending={pending_count} "
                            f"-> concurrency {prev_n}→{effective_n}"
                        )
                except Exception as e:
                    logger.debug("Burst mode check failed: %s", e)

                print(
                    f"[{datetime.now()}] Found {len(tasks)} pending tasks. Processing in parallel (max {effective_n} concurrent)..."
                )

                # ВАЖНО: Преобразуем asyncpg Records в словари (Records immutable!)
                tasks = [dict(t) for t in tasks]

                # РАСПРЕДЕЛЕНИЕ: оркестратор назначает preferred_source при assign_task_to_best_expert
                # Воркер использует metadata.preferred_source от оркестратора; если нет — fallback по сложности
                mlx_tasks = []
                ollama_tasks = []
                for task in tasks:
                    meta = task.get("metadata") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta) if meta else {}
                        except Exception:
                            meta = {}
                    # Оркестратор уже назначил preferred_source — используем
                    orch_source = meta.get("preferred_source")
                    if orch_source and str(orch_source).lower() in ("mlx", "ollama"):
                        task["preferred_source"] = str(orch_source).lower()
                        task["_effective_category"] = task.get("_effective_category") or "default"
                    else:
                        # Fallback: intelligent_model_router по сложности
                        try:
                            from intelligent_model_router import get_intelligent_router

                            ir = get_intelligent_router()
                            prompt = f"{task.get('title', '')} {task.get('description', '')}"
                            tc = ir.estimate_task_complexity(prompt, category="default")
                            if getattr(tc, "requires_reasoning", False):
                                task["_effective_category"] = "reasoning"
                            elif getattr(tc, "requires_coding", False):
                                task["_effective_category"] = "coding"
                            elif getattr(tc, "task_type", "") == "fast":
                                task["_effective_category"] = "fast"
                            else:
                                task["_effective_category"] = "default"
                            if tc.complexity_score > 0.6 and (
                                tc.requires_reasoning or tc.requires_coding
                            ):
                                # Complex + reasoning/coding → ollama (heavy)
                                task["preferred_source"] = "ollama"
                            elif (
                                tc.complexity_score < 0.4 or getattr(tc, "task_type", "") == "fast"
                            ):
                                # Simple/fast → mlx (light, fast)
                                task["preferred_source"] = "mlx"
                            else:
                                # Medium - balance
                                task["preferred_source"] = (
                                    "mlx" if len(mlx_tasks) <= len(ollama_tasks) else "ollama"
                                )
                        except Exception:
                            task["_effective_category"] = "default"
                            task["preferred_source"] = (
                                "mlx" if len(mlx_tasks) <= len(ollama_tasks) else "ollama"
                            )
                    if task["preferred_source"] == "mlx":
                        mlx_tasks.append(task)
                    else:
                        ollama_tasks.append(task)

                print(
                    f"[{datetime.now()}] 📊 Интеллектуальное распределение: MLX={len(mlx_tasks)}, Ollama={len(ollama_tasks)}"
                )

                # Батчи по модели: сканер доступных моделей → назначить preferred_model → группировать по (source, model) → обрабатывать блоками (меньше load/unload на MLX/Ollama)
                BATCH_BY_MODEL = os.getenv("SMART_WORKER_BATCH_BY_MODEL", "true").lower() in (
                    "true",
                    "1",
                    "yes",
                )
                use_pairing = os.getenv("SMART_WORKER_HEAVY_LIGHT_PAIRING", "true").lower() in (
                    "true",
                    "1",
                    "yes",
                )
                all_tasks_to_process = []
                if BATCH_BY_MODEL:
                    try:
                        from available_models_scanner import (
                            get_available_models,
                            pick_mlx_for_category,
                            pick_ollama_for_category,
                        )

                        mlx_url = os.getenv("MLX_API_URL") or (
                            "http://host.docker.internal:11435"
                            if os.path.exists("/.dockerenv")
                            else "http://localhost:11435"
                        )
                        ollama_url = (
                            os.getenv("OLLAMA_API_URL")
                            or os.getenv("OLLAMA_BASE_URL")
                            or (
                                "http://host.docker.internal:11434"
                                if os.path.exists("/.dockerenv")
                                else "http://localhost:11434"
                            )
                        )
                        # Кэш сканера в главном цикле (TTL 120 сек) — меньше вызовов к Ollama/MLX, стабильность при нестабильных серверах
                        global _scanner_cache_time, _scanner_cache_mlx, _scanner_cache_ollama
                        import time as _time

                        _t = _time.time()
                        if _t - _scanner_cache_time < 120 and _scanner_cache_mlx is not None:
                            mlx_list = _scanner_cache_mlx
                            ollama_list = _scanner_cache_ollama
                        else:
                            mlx_list, ollama_list = await get_available_models(mlx_url, ollama_url)
                            _scanner_cache_time = _t
                            _scanner_cache_mlx = mlx_list
                            _scanner_cache_ollama = ollama_list
                        # Распределение только по актуальным в сканере: если источник пуст — переназначаем на другой
                        for task in mlx_tasks + ollama_tasks:
                            cat = task.get("_effective_category", "default")
                            src = task.get("preferred_source", "ollama")
                            if src == "mlx" and not mlx_list:
                                task["preferred_source"] = "ollama"
                                src = "ollama"
                            elif src == "ollama" and not ollama_list:
                                task["preferred_source"] = "mlx"
                                src = "mlx"
                            if src == "mlx" and mlx_list:
                                task["preferred_model"] = pick_mlx_for_category(cat, mlx_list)
                            elif src == "ollama" and ollama_list:
                                task["preferred_model"] = pick_ollama_for_category(cat, ollama_list)
                            else:
                                task["preferred_model"] = None
                        # Тяжёлые/лёгкие модели (ADAPTIVE_WORKER_CONCURRENCY_PLAN): лимит тяжёлых одновременно
                        try:
                            from adaptive_concurrency import is_model_heavy

                            for task in mlx_tasks + ollama_tasks:
                                task["_is_heavy"] = is_model_heavy(task.get("preferred_model"))
                        except ImportError:
                            for task in mlx_tasks + ollama_tasks:
                                task["_is_heavy"] = False
                        # Группируем по (preferred_source, preferred_model)
                        from collections import defaultdict

                        groups = defaultdict(list)
                        for task in mlx_tasks + ollama_tasks:
                            key = (task.get("preferred_source"), task.get("preferred_model") or "")
                            groups[key].append(task)
                        # Тяжёлый/лёгкий pairing (ADAPTIVE_WORKER_CONCURRENCY_PLAN): когда Ollama тяжёлая — MLX лёгкая, и наоборот
                        # Упорядочиваем блоки: (mlx/heavy, ollama/light), (mlx/light, ollama/heavy) — чтобы не грузить оба тяжёлыми
                        group_list = list(groups.items())
                        _is_heavy_fn = None
                        try:
                            from adaptive_concurrency import is_model_heavy as _is_heavy_fn
                        except ImportError:
                            _is_heavy_fn = lambda m: False
                        _is_heavy_fn_safe = _is_heavy_fn or (lambda m: False)
                        if use_pairing and len(group_list) > 1:

                            def _heavy(k):
                                return _is_heavy_fn_safe(k[1])

                            mlx_heavy = [
                                (k, v) for k, v in group_list if k[0] == "mlx" and _heavy(k)
                            ]
                            mlx_light = [
                                (k, v) for k, v in group_list if k[0] == "mlx" and not _heavy(k)
                            ]
                            ollama_heavy = [
                                (k, v) for k, v in group_list if k[0] == "ollama" and _heavy(k)
                            ]
                            ollama_light = [
                                (k, v) for k, v in group_list if k[0] == "ollama" and not _heavy(k)
                            ]
                            # Пары: mlx_heavy+ollama_light, mlx_light+ollama_heavy — чередование
                            paired = (
                                list(mlx_heavy)
                                + list(ollama_light)
                                + list(mlx_light)
                                + list(ollama_heavy)
                            )
                            sorted_groups = [g for g in paired if g[1]]
                        else:
                            sorted_groups = sorted(group_list, key=lambda x: -len(x[1]))
                        # Лог блоков
                        if sorted_groups:
                            blocks_desc = ", ".join(
                                f"{src}/{model or 'auto'}:{len(gt)}"
                                for (src, model), gt in sorted_groups
                            )
                            print(
                                f"[{datetime.now()}] 📦 Блоки (source/модель: кол-во): {blocks_desc}"
                            )
                        # Чередование: MLX и Ollama одновременно; при pairing — тяжёлый на одном, лёгкий на другом
                        INTERLEAVE = os.getenv(
                            "SMART_WORKER_INTERLEAVE_BLOCKS", "true"
                        ).lower() in ("true", "1", "yes")
                        if INTERLEAVE and len(sorted_groups) > 1:
                            max_len = max(len(gt) for _, gt in sorted_groups)
                            for i in range(max_len):
                                for (_src, _model), group_tasks in sorted_groups:
                                    if i < len(group_tasks):
                                        all_tasks_to_process.append(group_tasks[i])
                            print(
                                f"[{datetime.now()}] 📦 Чередование (MLX и Ollama одновременно, heavy/light pairing)"
                            )
                        else:
                            for (src, model), group_tasks in sorted_groups:
                                all_tasks_to_process.extend(group_tasks)
                    except Exception as e:
                        logger.debug(f"Batch by model failed: {e}, using flat order")
                        all_tasks_to_process = mlx_tasks + ollama_tasks
                else:
                    all_tasks_to_process = mlx_tasks + ollama_tasks

                # Ограничение тяжёлых одновременно (Performance: не OOM) — до 2 heavy MLX + 2 heavy Ollama в первых слотах
                if ADAPTIVE_CONCURRENCY and all_tasks_to_process:
                    try:
                        max_heavy_mlx = int(os.getenv("ADAPTIVE_MAX_HEAVY_MLX", "2"))
                        max_heavy_ollama = int(os.getenv("ADAPTIVE_MAX_HEAVY_OLLAMA", "2"))
                        heavy_mlx = [
                            t
                            for t in all_tasks_to_process
                            if t.get("preferred_source") == "mlx" and t.get("_is_heavy")
                        ]
                        heavy_ollama = [
                            t
                            for t in all_tasks_to_process
                            if t.get("preferred_source") == "ollama" and t.get("_is_heavy")
                        ]
                        first = list(heavy_mlx[:max_heavy_mlx]) + list(
                            heavy_ollama[:max_heavy_ollama]
                        )
                        rest = [t for t in all_tasks_to_process if t not in first]
                        all_tasks_to_process = first + rest
                    except Exception as e:
                        logger.debug(f"Heavy/light reorder failed: {e}")

                # Непрерывный пул: семафор на effective_n
                sem = asyncio.Semaphore(effective_n)
                # Батч по batch_group (ARCHITECTURE_IMPROVEMENTS §2.5): один вызов LLM на группу
                BATCH_GROUP_LLM = os.getenv("SMART_WORKER_BATCH_GROUP_LLM", "false").lower() in (
                    "true",
                    "1",
                    "yes",
                )
                work_items = []
                used_in_batch = set()
                if BATCH_GROUP_LLM:
                    from collections import defaultdict

                    batch_groups = defaultdict(list)
                    for t in all_tasks_to_process:
                        meta = t.get("metadata") or {}
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta) if meta else {}
                            except Exception:
                                meta = {}
                        bg = meta.get("batch_group")
                        if bg:
                            key = (bg, t.get("preferred_source"), t.get("preferred_model"))
                            batch_groups[key].append(t)
                    max_batch = int(os.getenv("SMART_WORKER_BATCH_GROUP_MAX", "3"))
                    for (bg, src, model), group in batch_groups.items():
                        if len(group) >= 2:
                            for i in range(0, len(group), max_batch):
                                batch = group[i : i + max_batch]
                                work_items.append(("batch", batch))
                                used_in_batch.update(t["id"] for t in batch)
                    for t in all_tasks_to_process:
                        if t["id"] not in used_in_batch:
                            work_items.append(("single", t))
                else:
                    work_items = [("single", t) for t in all_tasks_to_process]

                async def process_work_item(item):
                    kind, payload = item
                    async with sem:
                        try:
                            if kind == "batch":
                                ok = await asyncio.wait_for(
                                    process_batch_tasks(pool, payload),
                                    timeout=WORK_ITEM_TIMEOUT_SEC,
                                )
                                if not ok:
                                    for t in payload:
                                        await asyncio.wait_for(
                                            process_task(pool, t),
                                            timeout=WORK_ITEM_TIMEOUT_SEC,
                                        )
                            else:
                                await asyncio.wait_for(
                                    process_task(pool, payload),
                                    timeout=WORK_ITEM_TIMEOUT_SEC,
                                )
                        except asyncio.TimeoutError:
                            ids = (
                                [str(t.get("id")) for t in payload]
                                if kind == "batch"
                                else [str(payload.get("id"))]
                            )
                            print(
                                f"[{datetime.now()}] ⏱️ Work item timeout ({WORK_ITEM_TIMEOUT_SEC}s). ids={','.join(ids)}"
                            )
                            timeout_meta = json.dumps(
                                {
                                    "last_attempt_failed": True,
                                    "last_error": f"work_item_timeout_{WORK_ITEM_TIMEOUT_SEC}s",
                                    "reset_reason": "work_item_timeout",
                                }
                            )
                            async with pool.acquire() as conn:
                                for task_id in ids:
                                    await conn.execute(
                                        """
                                        UPDATE tasks
                                        SET status = 'pending',
                                            updated_at = NOW(),
                                            metadata = jsonb_set(
                                                COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                                                '{attempt_count}',
                                                to_jsonb(COALESCE((metadata->>'attempt_count')::int, 0) + 1),
                                                true
                                            )
                                        WHERE id = $1
                                          AND status = 'in_progress'
                                    """,
                                        task_id,
                                        timeout_meta,
                                    )

                await asyncio.gather(
                    *[process_work_item(w) for w in work_items], return_exceptions=True
                )

                print(f"[{datetime.now()}] ✅ Completed: {len(tasks)} tasks processed")
            else:
                print(f"[{datetime.now()}] No pending tasks found. Waiting...")

            await asyncio.sleep(5)  # Уменьшили задержку, так как обрабатываем быстрее
        except Exception as e:
            print(f"[{datetime.now()}] Main loop error: {e}")
            import traceback

            traceback.print_exc()
            await asyncio.sleep(30)


if __name__ == "__main__":
    import sys

    enable_metrics = os.getenv("ENABLE_METRICS", "false").lower() in ("true", "1", "yes")
    metrics_port = int(os.getenv("METRICS_PORT", "8002"))
    run_as_metrics_only = "--metrics-only" in sys.argv

    async def metrics_handler(request):
        from prometheus_client import REGISTRY, generate_latest

        metrics = generate_latest(REGISTRY)
        return web.Response(body=metrics, content_type="text/plain")

    async def health_handler(request):
        return web.json_response({"status": "healthy", "worker": "smart"})

    def start_metrics_server(port=8002):
        app = web.Application()
        app.router.add_get("/metrics", metrics_handler)
        app.router.add_get("/health", health_handler)
        return app

    def run_metrics_only(port=8002):
        """Запуск только HTTP сервера для метрик (без воркера)."""
        app = start_metrics_server(port)
        logger.info(f"📊 [METRICS] Starting metrics server on port {port}")
        web.run_app(app, host="0.0.0.0", port=port, print=lambda x: None)


def run_worker_with_metrics(port=8002):
    """Запуск и воркера и HTTP сервера метрик параллельно."""

    async def run_both():
        metrics_app = start_metrics_server(port)
        metrics_runner = web.AppRunner(metrics_app)
        await metrics_runner.setup()
        metrics_site = web.TCPSite(metrics_runner, "0.0.0.0", port)
        await metrics_site.start()
        logger.info(f"📊 [METRICS] Metrics server started on port {port}")
        try:
            await main()
        finally:
            await metrics_runner.cleanup()

    asyncio.get_event_loop().run_until_complete(run_both())


if __name__ == "__main__":
    import sys

    enable_metrics = os.getenv("ENABLE_METRICS", "false").lower() in ("true", "1", "yes")
    metrics_port = int(os.getenv("METRICS_PORT", "8002"))
    run_as_metrics_only = "--metrics-only" in sys.argv

    async def metrics_handler(request):
        from prometheus_client import REGISTRY, generate_latest

        metrics = generate_latest(REGISTRY)
        return web.Response(body=metrics, content_type="text/plain")

    async def health_handler(request):
        return web.json_response({"status": "healthy", "worker": "smart"})

    def start_metrics_server(port=8002):
        app = web.Application()
        app.router.add_get("/metrics", metrics_handler)
        app.router.add_get("/health", health_handler)
        return app

    def run_metrics_only(port=8002):
        """Запуск только HTTP сервера для метрик (без воркера)."""
        app = start_metrics_server(port)
        logger.info(f"📊 [METRICS] Starting metrics server on port {port}")
        web.run_app(app, host="0.0.0.0", port=port, print=lambda x: None)

    def run_worker_with_metrics(port=8002):
        """Запуск и воркера и HTTP сервера метрик параллельно."""

        async def run_both():
            metrics_app = start_metrics_server(port)
            metrics_runner = web.AppRunner(metrics_app)
            await metrics_runner.setup()
            metrics_site = web.TCPSite(metrics_runner, "0.0.0.0", port)
            await metrics_site.start()
            logger.info(f"📊 [METRICS] Metrics server started on port {port}")
            try:
                await main()
            finally:
                await metrics_runner.cleanup()

        asyncio.get_event_loop().run_until_complete(run_both())

    if "--metrics" in sys.argv or enable_metrics:
        if run_as_metrics_only:
            run_metrics_only(metrics_port)
        else:
            run_worker_with_metrics(metrics_port)
    else:
        asyncio.run(main())
