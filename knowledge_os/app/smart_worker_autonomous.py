import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from functools import partial
from typing import List, Optional

logger = logging.getLogger(__name__)

# Маппинг role/department → папки скиллов (П.2 PRINCIPLE_EXPERTS_FIRST). Ключи — подстроки для role/department (lower).
ROLE_DEPARTMENT_TO_SKILLS = {
    "backend": ["backend-development", "code-review"],
    "qa": ["qa-regression", "webapp-testing"],
    "frontend": ["frontend-design", "webapp-testing"],
    "python": ["python-development", "code-documentation"],
    "devops": ["observability", "disaster-recovery"],
    "ml": ["llm-application-dev", "model-ensemble"],
    "documentation": ["code-documentation", "doc-coauthoring"],
    "general": ["ask-questions-if-underspecified", "code-review"],
}


def _read_skill_snippets_sync(skill_folders: List[str], max_chars_per_skill: int = 2000) -> str:
    """Читает первые max_chars_per_skill символов из SKILL.md для каждой папки. Sync — вызывать через run_in_executor."""
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    parts = []
    for folder in skill_folders[:3]:  # П.2 пушка: до 3 скиллов
        path = os.path.join(skills_dir, folder, "SKILL.md")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            # Пропускаем YAML frontmatter, берём инструкции
            if "---" in raw:
                parts_fm = raw.split("---", 2)
                text = parts_fm[2].strip() if len(parts_fm) >= 3 else raw
            else:
                text = raw
            snippet = text[:max_chars_per_skill]
            if len(text) > max_chars_per_skill:
                snippet += "\n..."
            parts.append(f"[{folder}]\n{snippet}")
        except Exception as e:
            logger.debug("Skill read failed %s: %s", path, e)
    if not parts:
        return ""
    return "\n\n📋 ИНСТРУКЦИИ ИЗ СКИЛЛОВ (используй при решении):\n" + "\n\n---\n\n".join(parts)


def _get_skill_description_sync(skills_dir: str, folder: str) -> str:
    """Читает из SKILL.md description из frontmatter или имя папки. Sync."""
    path = os.path.join(skills_dir, folder, "SKILL.md")
    if not os.path.isfile(path):
        return folder.replace("-", " ")
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read(1500)
        if "---" in raw and "description:" in raw.lower():
            for line in raw.split("\n"):
                if line.strip().lower().startswith("description:"):
                    return line.split(":", 1)[1].strip().strip('"') + " " + folder.replace("-", " ")
        return folder.replace("-", " ")
    except Exception:
        return folder.replace("-", " ")


def _select_skills_by_relevance_sync(
    task_title: str, task_description: str, max_skills: int = 3
) -> List[str]:
    """П.2 пушка: по ключевым словам задачи выбирает до max_skills скиллов (по совпадению с именем/description). Sync."""
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    if not os.path.isdir(skills_dir):
        return []
    task_text = f"{task_title} {task_description}".lower()
    task_words = set(_ for _ in task_text.replace("-", " ").split() if len(_) > 1)
    scored = []
    for folder in os.listdir(skills_dir):
        if not os.path.isdir(os.path.join(skills_dir, folder)) or folder.startswith("."):
            continue
        desc = _get_skill_description_sync(skills_dir, folder).lower()
        desc_words = set(_ for _ in desc.replace("-", " ").split() if len(_) > 1)
        overlap = len(task_words & desc_words)
        if overlap > 0 or folder.replace("-", " ") in task_text:
            scored.append((overlap + (2 if folder.replace("-", " ") in task_text else 0), folder))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored[:max_skills]]


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
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Максимум попыток выполнения задачи; после исчерпания — эскалация в Совет Директоров
MAX_ATTEMPTS = int(os.getenv("SMART_WORKER_MAX_ATTEMPTS", "3"))

# Глобальный пул соединений (singleton)
_pool = None

# Кэш сканера моделей в главном цикле воркера (TTL 120 сек) — меньше вызовов к Ollama/MLX
_scanner_cache_time = 0.0
_scanner_cache_mlx = None
_scanner_cache_ollama = None


async def get_pool():
    global _pool
    if _pool is None:
        # Пул должен покрывать: до MAX_CONCURRENT_TASKS обработок + столько же heartbeats (каждые 15 сек acquire)
        # Раньше max_size=5 при 10 конкурентных задачах → heartbeats не получали соединение → updated_at не обновлялся → задачи считались зависшими
        max_concurrent = int(os.getenv("SMART_WORKER_MAX_CONCURRENT", "10"))
        pool_size = max(15, max_concurrent + 8)
        _pool = await asyncpg.create_pool(
            DB_URL,
            min_size=1,
            max_size=pool_size,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
    return _pool


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
            from local_router import LocalAIRouter

            router_instance = LocalAIRouter()
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


async def process_task(pool, task):
    task_id = task["id"]
    expert_name = task["assignee"]
    task_title = task["title"]
    preferred_source = task.get("preferred_source")  # MLX или Ollama
    print(
        f"[{datetime.now()}] Expert {expert_name} processing: {task_title} [Source: {preferred_source or 'auto'}]"
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
            # Обновляем статус с проверкой, что задача не обрабатывается другим worker'ом
            result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'in_progress', updated_at = NOW()
                WHERE id = $1
                AND (status = 'pending' OR (status = 'in_progress' AND updated_at < NOW() - make_interval(mins => $2::int)))
            """,
                task_id,
                stuck_mins,
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
            from local_router import LocalAIRouter

            router_instance = LocalAIRouter()
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
            # Таймаут из env (по умолчанию 300 сек = 5 мин)
            llm_timeout = float(os.getenv("SMART_WORKER_LLM_TIMEOUT", "300"))
            # Для тяжёлых моделей: учесть время загрузки (30-90 сек); иначе ReadTimeout при первом запросе
            if preferred_model:
                try:
                    from adaptive_concurrency import is_model_heavy

                    if is_model_heavy(preferred_model):
                        mult = float(
                            os.getenv("SMART_WORKER_HEAVY_MODEL_TIMEOUT_MULTIPLIER", "1.5")
                        )
                        llm_timeout = max(llm_timeout, llm_timeout * mult)
                        llm_timeout = min(llm_timeout, 600)  # не больше 10 мин
                except ImportError:
                    pass
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
        if report is None:
            report = None
        elif isinstance(report, tuple):
            # Если кортеж - берем первый элемент (ответ)
            report = report[0] if report[0] else (report[1] if len(report) > 1 else None)
        elif isinstance(report, dict):
            report = report.get("response", report.get("text", str(report)))
        elif not isinstance(report, str):
            report = str(report)

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
                    # Сохраняем информацию о необходимости апгрейда
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('model_upgrade_needed', true, 'recommended_model', $2::text)
                            WHERE id = $1
                        """,
                            task_id,
                            str(next_model) if next_model else "",
                        )
            except Exception as e:
                logger.debug(f"Model performance tracking failed: {e}")

            # Проверяем, что ответ не является сообщением об ошибке
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
            is_error = any(indicator in report for indicator in error_indicators)
            # LLM unavailable — только при явных коротких сообщениях об недоступности (не длинный ответ с словом "недоступна")
            report_lower = (report or "").lower()
            report_len = len((report or "").strip())
            _unavailable_phrases = (
                "все источники недоступны",
                "модели также недоступны",
                "система временно недоступна",
                "all sources unavailable",
                "models unavailable",
                "connection refused",
            )
            is_llm_unavailable = (
                report_len < 350 and ("недоступн" in report_lower or "unavailable" in report_lower)
            ) or any(phrase in report_lower for phrase in _unavailable_phrases)

            if is_error:
                print(
                    f"[{datetime.now()}] ⚠️ Agent returned error for task {task_id}: {report[:150]}..."
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
                should_try_rule_or_escalate = (
                    is_llm_unavailable and attempt_count >= 2
                ) or attempt_count >= MAX_ATTEMPTS
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
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW(),
                                    metadata = COALESCE(metadata, '{}'::jsonb) || '{"execution_mode": "rule_based", "llm_unavailable_fallback": true}"::jsonb
                                WHERE id = $1
                            """,
                                task_id,
                                rule_result,
                            )
                        print(
                            f"[{datetime.now()}] ✅ Task {task_id} completed via rule_executor (LLM unavailable)"
                        )
                        return
                    # rule не сработал — эскалация в Совет Директоров, затем complete
                    board_directive = await escalate_task_to_board(
                        pool,
                        task_id,
                        task_title,
                        task_description or "",
                        report[:500] if report else "",
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
                            async with pool.acquire() as conn:
                                await conn.execute(
                                    """
                                    UPDATE tasks
                                    SET status = 'pending',
                                        updated_at = NOW(),
                                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                            'last_attempt_failed', true,
                                            'attempt_count', $2::int,
                                            'last_error', $3::text,
                                            'model_upgrade_needed', true,
                                            'recommended_model', $4::text
                                        )
                                    WHERE id = $1
                                """,
                                    task_id,
                                    attempt_count,
                                    str(report[:500]),
                                    str(next_model),
                                )
                            print(
                                f"[{datetime.now()}] 🔄 Task {task_id} upgraded to model {next_model} for retry"
                            )
                            return
                    except Exception as e:
                        logger.debug(f"Model upgrade check failed: {e}")

                    # Возвращаем в pending для повторной попытки
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE tasks
                            SET status = 'pending',
                                updated_at = NOW(),
                                metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('last_attempt_failed', true, 'attempt_count', $2::int, 'last_error', $3::text)
                            WHERE id = $1
                        """,
                            task_id,
                            attempt_count,
                            str(report[:500]),
                        )
                    print(
                        f"[{datetime.now()}] ⚠️ Task {task_id} reverted to PENDING (attempt {attempt_count}/{MAX_ATTEMPTS}). Will retry later."
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

            # Сохраняем результат в отдельной транзакции (только если НЕ ошибка)
            # П.1 пушка: метрика «задача получила веб-блок» — пишем в metadata для /metrics
            meta_web = json.dumps({"had_web_block": True}) if web_block else "{}"
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW(), metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb WHERE id = $1",
                        task_id,
                        report,
                        meta_web,
                    )
                    logger.info("Task %s marked completed in DB (updated_at=NOW()).", task_id)

                    # Сохраняем в knowledge_nodes с embedding (для RAG/search) — знания внедряются в систему
                    try:
                        content_for_kn = f"📊 REPORT BY {expert_name}: {task_title}\n\n{report}"
                        embedding = None
                        try:
                            from semantic_cache import get_embedding

                            embedding = await get_embedding(
                                content_for_kn[:8000]
                            )  # лимит для embedding
                        except Exception as emb_err:
                            logger.debug("Embedding skip for knowledge_node: %s", emb_err)
                        meta_kn = json.dumps(
                            {
                                "task_id": str(task_id),
                                "expert": expert_name,
                                "fallback_used": is_error,
                                "department": expert_config["department"],
                            }
                        )
                        if embedding:
                            await conn.execute(
                                """
                                INSERT INTO knowledge_nodes (content, metadata, confidence_score, source_ref, embedding)
                                VALUES ($1, $2, 0.85, $3, $4::vector)
                            """,
                                content_for_kn,
                                meta_kn,
                                "autonomous_worker",
                                str(embedding),
                            )
                        else:
                            await conn.execute(
                                """
                                INSERT INTO knowledge_nodes (content, metadata, confidence_score, source_ref)
                                VALUES ($1, $2, 0.85, $3)
                            """,
                                content_for_kn,
                                meta_kn,
                                "autonomous_worker",
                            )
                        print(
                            f"[{datetime.now()}] ✅ Knowledge saved for task {task_id}"
                            + (" (with embedding)" if embedding else "")
                        )
                    except Exception as e:
                        print(f"[{datetime.now()}] ⚠️ Error saving to knowledge_nodes: {e}")
                        import traceback

                        traceback.print_exc()
        print(f"[{datetime.now()}] ✅ Task {task_id} COMPLETED.")
    except Exception as e:
        _last_failure_reason = str(e)[:500]
        print(f"[{datetime.now()}] ❌ Error processing task {task_id}: {e}")
        import traceback

        traceback.print_exc()
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
            meta_extra = json.dumps(
                {
                    "auto_completed": True,
                    "attempt_count": attempt_count,
                    "execution_mode": exec_mode,
                    "deferred_to_human": deferred,
                    "board_escalated": not bool(rule_result),
                    "last_error": last_error_text[:500],
                }
            )
            async with pool.acquire() as conn:
                if assignee_id:
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = 'completed', result = $2, updated_at = NOW(),
                            assignee_expert_id = $4,
                            metadata = COALESCE(metadata, '{}'::jsonb) || $5::jsonb
                        WHERE id = $1
                    """,
                        task_id,
                        final_result,
                        assignee_id,
                        meta_extra,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET status = 'completed', result = $2, updated_at = NOW(),
                            assignee_expert_id = (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                            metadata = COALESCE(metadata, '{}'::jsonb) || $4::jsonb
                        WHERE id = $1
                    """,
                        task_id,
                        final_result,
                        meta_extra,
                    )
            print(
                f"[{datetime.now()}] ✅ Task {task_id} AUTO-COMPLETED after {attempt_count} attempts (mode={exec_mode}, board_escalated={not bool(rule_result)})."
            )
        else:
            # Обновляем счетчик попыток, сохраняем причину сбоя и задержку перед повтором (чтобы не бить LLM сразу)
            retry_delay_sec = int(os.getenv("SMART_WORKER_RETRY_DELAY_SEC", "90"))
            next_retry_after = (
                (datetime.utcnow().timestamp() + retry_delay_sec) if retry_delay_sec > 0 else None
            )
            meta_pending = {
                "last_attempt_failed": True,
                "attempt_count": attempt_count,
                "last_error": last_error_text[:500],
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

    while True:
        try:
            # Вернуть зависшие in_progress (> N мин) в pending, чтобы воркер их подхватил
            async with pool.acquire() as conn:
                stuck_result = await conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'pending', updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                            'stuck_reset', true, 'previous_status', 'in_progress'
                        )
                    WHERE status = 'in_progress'
                      AND updated_at < NOW() - make_interval(mins => $1::int)
                """,
                    STUCK_MINUTES,
                )
                if stuck_result and stuck_result.startswith("UPDATE"):
                    n = stuck_result.split()[-1]
                    if n != "0":
                        print(
                            f"[{datetime.now()}] 🔄 Вернуто в очередь зависших задач (>{STUCK_MINUTES} мин): {n}"
                        )

            # ═══════════════════════════════════════════════════════════════════════════════
            # BACKPRESSURE: проверка перегрузки MLX/Ollama ПЕРЕД взятием задач (SRE, Елена)
            # Если оба бэкенда перегружены — не брать новые задачи, подождать
            # ═══════════════════════════════════════════════════════════════════════════════
            if ADAPTIVE_CONCURRENCY:
                try:
                    from adaptive_concurrency import check_backends_overload

                    is_overloaded, overload_reason = await check_backends_overload()
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
                    max_pending = int(os.getenv("SMART_WORKER_MAX_PENDING", "10"))
                    if pending_count >= max_pending:
                        # [WATCHDOG] Если задач слишком много — не берем новые из очереди,
                        # чтобы дать системе разгрузиться.
                        print(
                            f"[{datetime.now()}] ⏸️ BACKPRESSURE: Too many pending tasks ({pending_count}/{max_pending}). Waiting 10s..."
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
                      AND (t.metadata->>'next_retry_after' IS NULL OR (t.metadata->>'next_retry_after')::timestamptz < NOW())
                    ORDER BY
                        COALESCE((t.metadata->>'bug_probability')::float, 0.0) DESC,  -- Приоритет: задачи с высокой bug_probability
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
                                task["preferred_source"] = "mlx"
                            elif (
                                tc.complexity_score < 0.4 or getattr(tc, "task_type", "") == "fast"
                            ):
                                task["preferred_source"] = "ollama"
                            else:
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
                        if kind == "batch":
                            ok = await process_batch_tasks(pool, payload)
                            if not ok:
                                for t in payload:
                                    await process_task(pool, t)
                        else:
                            await process_task(pool, payload)

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
    asyncio.run(main())
