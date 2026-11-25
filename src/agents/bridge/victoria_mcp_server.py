"""
Victoria MCP Server — подключение Victoria к Cursor через MCP.
Запуск: python -m src.agents.bridge.victoria_mcp_server
"""

import asyncio
import json
import logging
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

try:
    from src.agents.bridge.execution_plan_local import (
        ALLOWED_COMMANDS as _LOCAL_ALLOWED,
        execute_plan_local,
        validate_command,
    )
    from src.agents.bridge.victoria_mcp_parse import (
        extract_text,
        format_run_result,
        is_victoria_stub,
    )
except ImportError:
    from execution_plan_local import (  # type: ignore
        ALLOWED_COMMANDS as _LOCAL_ALLOWED,
        execute_plan_local,
        validate_command,
    )
    from victoria_mcp_parse import extract_text, format_run_result, is_victoria_stub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("victoria_mcp")

# Victoria: localhost для работы с Cursor на этой машине; Mac Studio — через VICTORIA_URL.
VICTORIA_URL = os.getenv(
    "VICTORIA_URL",
    "http://localhost:8010",
)
# Таймаут для victoria_run (сек). Задачи на код (оркестратор → эксперты) часто > 10 мин. По умолчанию 30 мин.
VICTORIA_MCP_RUN_TIMEOUT_SEC = float(os.getenv("VICTORIA_MCP_RUN_TIMEOUT_SEC", "1800"))

mcp = FastMCP("VictoriaATRA")

ALLOWED_COMMANDS = _LOCAL_ALLOWED


def _validate_command(command: str) -> str:
    """Validate command against allowlist."""
    return validate_command(command)


def _is_victoria_stub(text: str, status: Optional[str] = None) -> bool:
    """Reject queue/ack/rule-fallback stubs as if they were real answers."""
    return is_victoria_stub(text, status=status)


def _prefer_run_async(message: str) -> bool:
    """Heavy/curator/file/fact goals prefer /run async+poll (pair/curator path).

    Short identity/greetings stay on /v1/chat/completions.
    """
    g = (message or "").strip().lower()
    if not g:
        return False
    short_ok = (
        "привет",
        "здравствуй",
        "кто ты",
        "ты кто",
        "что умеешь",
        "hello",
        "hi ",
        "who are you",
    )
    if len(g) < 48 and any(s in g for s in short_ok):
        return False
    try:
        from src.agents.bridge.task_detector import (
            is_curator_standard_goal,
            is_fact_seeking_question,
            is_operational_execution_goal,
        )
    except ImportError:
        try:
            from task_detector import (  # type: ignore
                is_curator_standard_goal,
                is_fact_seeking_question,
                is_operational_execution_goal,
            )
        except ImportError:
            is_fact_seeking_question = None  # type: ignore
            is_curator_standard_goal = None  # type: ignore
            is_operational_execution_goal = None  # type: ignore
    if is_fact_seeking_question and is_fact_seeking_question(message):
        return True
    if is_curator_standard_goal and is_curator_standard_goal(message):
        return True
    if is_operational_execution_goal and is_operational_execution_goal(message):
        return True
    markers = (
        "проверь файл",
        "прочитай файл",
        "check file",
        "curator",
        "по фактам",
        "health",
        "очеред",
        "/health",
        "11434",
        "11437",
        "11436",
        "/api/ps",
        "исправ",
        "аудит",
        "pytest",
        "docker",
        "миграц",
        "напиши",
        "создай",
        "разработай",
        "проанализ",
        "разбери",
        "grep",
        "read_file",
        "pending",
        "in_progress",
        "pip install",
        "eval()",
        "exec()",
        "hardcoded",
        "секрет",
    )
    if any(m in g for m in markers):
        return True
    min_chars = int(os.getenv("VICTORIA_MCP_CHAT_RUN_MIN_CHARS", "120"))
    return len(g) >= min_chars


def _parse_run_result(result: dict) -> str:
    """Разбор ответа /run: поддержка goal→output, chat completions и task_id."""
    return format_run_result(result)


async def _chat_completions(
    client: httpx.AsyncClient, message: str, history: Optional[list] = None
) -> str:
    messages: list[dict] = []
    for turn in history or []:
        if not isinstance(turn, dict):
            continue
        if turn.get("user"):
            messages.append({"role": "user", "content": str(turn["user"])})
        if turn.get("assistant"):
            messages.append({"role": "assistant", "content": str(turn["assistant"])})
    messages.append({"role": "user", "content": message})
    try:
        resp = await client.post(
            f"{VICTORIA_URL}/v1/chat/completions",
            json={"model": "victoria", "messages": messages, "max_tokens": 1200},
        )
        resp.raise_for_status()
        return format_run_result(resp.json())
    except httpx.HTTPStatusError as e:
        # Some deployments route chat/completions to a model alias that may be absent
        # (for example wisdom tag not loaded in Ollama). Fallback to /run keeps chat usable.
        if e.response is not None and e.response.status_code == 404:
            logger.warning(
                "[victoria_chat] chat/completions returned 404, fallback to /run for message"
            )
            return await _run_async_and_poll(client, message, max_steps=120, wait_sec=90)
        raise


async def _run_async_and_poll(
    client: httpx.AsyncClient,
    goal: str,
    max_steps: Optional[int],
    wait_sec: float = 90,
) -> str:
    resp = await client.post(
        f"{VICTORIA_URL}/run",
        params={"async_mode": "true"},
        json={"goal": goal, "max_steps": max_steps or 500, "project_context": "atra-web-ide"},
    )
    if resp.status_code == 422:
        resp = await client.post(f"{VICTORIA_URL}/run", json={"prompt": goal})
    resp.raise_for_status()
    data = resp.json()
    text, status = extract_text(data)
    if text and not is_victoria_stub(text, status):
        return format_run_result(data)
    task_id = data.get("task_id")
    if not task_id:
        return await _chat_completions(client, goal)
    deadline = asyncio.get_event_loop().time() + wait_sec
    while asyncio.get_event_loop().time() < deadline:
        st = await client.get(f"{VICTORIA_URL}/run/status/{task_id}")
        if st.status_code == 404:
            await asyncio.sleep(2.0)
            continue
        st.raise_for_status()
        payload = st.json()
        body, st_status = extract_text(payload)
        if body and not is_victoria_stub(body, st_status):
            return format_run_result(payload)
        if str(st_status).lower() in ("completed", "failed", "cancelled", "error"):
            return format_run_result(payload)
        await asyncio.sleep(2.5)
    return format_run_result({"status": "processing", "task_id": task_id})


@mcp.tool()
async def victoria_run(goal: str, max_steps: Optional[int] = 500) -> str:
    """Запустить задачу через Victoria Agent (Team Lead ATRA).

    Args:
        goal: Цель/задача для выполнения
        max_steps: Максимальное количество шагов (по умолчанию 500)

    Returns:
        Результат выполнения задачи от Victoria
    """
    try:
        timeout_sec = max(60.0, float(VICTORIA_MCP_RUN_TIMEOUT_SEC))
        wait_sec = min(timeout_sec, float(os.getenv("VICTORIA_MCP_RUN_WAIT_SEC", "600")))
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            return await _run_async_and_poll(client, goal, max_steps, wait_sec=wait_sec)
    except httpx.TimeoutException:
        return (
            f"⏱️ Таймаут канала {int(timeout_sec)} с. "
            "Повтори короче через victoria_chat или опроси victoria_task_status."
        )
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_run")
        return f"❌ Ошибка: {e}"


@mcp.tool()
async def victoria_chat(
    message: str,
    history_json: Optional[str] = None,
    project_context: Optional[str] = "atra-web-ide",
) -> str:
    """Написать сообщение Виктории и получить ответ (для диалога).

    Args:
        message: Сообщение/вопрос для Виктории
        history_json: Опционально — JSON история диалога [{"user":"...","assistant":"..."}]
        project_context: Контекст проекта (по умолчанию atra-web-ide)

    Returns:
        Ответ Виктории
    """
    try:
        history = None
        if history_json:
            try:
                parsed = json.loads(history_json)
                if isinstance(parsed, list):
                    history = parsed
            except json.JSONDecodeError:
                pass
        # Heavy goals always prefer /run async (even with history).
        prefer_run = _prefer_run_async(message)
        timeout_sec = 300.0 if prefer_run else 120.0
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            if prefer_run:
                wait_sec = float(os.getenv("VICTORIA_MCP_CHAT_RUN_WAIT_SEC", "180"))
                goal = message
                if history:
                    # Fold last turns into goal so /run keeps dialogue context.
                    bits = []
                    for turn in history[-4:]:
                        if not isinstance(turn, dict):
                            continue
                        if turn.get("user"):
                            bits.append(f"user: {turn['user']}")
                        if turn.get("assistant"):
                            bits.append(f"assistant: {turn['assistant']}")
                    if bits:
                        goal = (
                            "Dialog context:\n"
                            + "\n".join(bits)
                            + "\n\nCurrent request:\n"
                            + message
                        )
                logger.info(
                    "[victoria_chat] routing to /run async (len=%s wait=%.0fs history=%s)",
                    len(goal or ""),
                    wait_sec,
                    bool(history),
                )
                return await _run_async_and_poll(client, goal, max_steps=120, wait_sec=wait_sec)
            return await _chat_completions(client, message, history)
    except httpx.TimeoutException:
        return (
            "⏱️ Таймаут канала Victoria. Для длинных задач опроси victoria_task_status "
            "или повтори через victoria_run."
        )
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_chat")
        return f"❌ Ошибка: {e}"


@mcp.tool()
async def victoria_status() -> str:
    """Проверить статус Victoria Agent.

    Returns:
        Статус Victoria (online/offline, knowledge size)
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{VICTORIA_URL}/status")
            if response.status_code == 404:
                health = await client.get(f"{VICTORIA_URL}/health")
                if health.is_success:
                    return "✅ Victoria на связи (Mac Studio). Эндпоинт /status не реализован — используй victoria_health."
                health.raise_for_status()
            response.raise_for_status()
            data = response.json()
            return f"✅ Victoria: {data.get('status', 'unknown')}\nЗнаний: {data.get('knowledge_size', 0)}"
    except Exception as e:
        return f"❌ Victoria недоступна: {e}"


@mcp.tool()
async def victoria_health() -> str:
    """Проверить здоровье Victoria Agent.

    Returns:
        Health check результат
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{VICTORIA_URL}/health")
            response.raise_for_status()
            data = response.json()
            return f"✅ {data.get('status', 'ok')} — {data.get('agent', 'Victoria')}"
    except Exception as e:
        return f"❌ Victoria не отвечает: {e}"


@mcp.tool()
async def victoria_task_status(task_id: str) -> str:
    """Забрать результат фоновой задачи Victoria по task_id."""
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.get(f"{VICTORIA_URL}/run/status/{task_id}")
            if resp.status_code == 404:
                return f"❌ Задача {task_id} не найдена."
            resp.raise_for_status()
            return format_run_result(resp.json())
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_task_status")
        return f"❌ Ошибка: {e}"


def coerce_execution_plan_json(raw: Optional[str]):
    """Parse optional MCP plan JSON; None if empty. Raises ValueError if invalid."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    data = json.loads(text)
    if not isinstance(data, list) or not data:
        raise ValueError("execution_plan_json must be a non-empty JSON list")
    return data


@mcp.tool()
async def victoria_execute_plan(
    goal: str,
    workspace_path: str = "/Users/bikos/Documents/atra-web-ide",
    max_steps: Optional[int] = 500,
    approve_writes: bool = False,
    execution_plan_json: Optional[str] = None,
) -> str:
    """Получить execution_plan от Victoria и выполнить на локальном FS.

    read_file — всегда. edit/run — только при approve_writes=True (иначе needs_approve).

    Если передан execution_plan_json (JSON-список шагов) — /orchestrate не вызывается
    (быстрый IDE hands-path; plan уже готов).

    Args:
        goal: Задача для Victoria (контекст/подпись; при готовом плане не шлётся в LLM)
        workspace_path: Корень sandbox
        max_steps: Лимит шагов планирования (только путь /orchestrate)
        approve_writes: Явное разрешение mutate/run
        execution_plan_json: Готовый план [{"action":"read_file","path":"..."}, ...]
    """
    try:
        victoria_output = ""
        try:
            execution_plan = coerce_execution_plan_json(execution_plan_json)
        except (ValueError, json.JSONDecodeError) as e:
            return f"❌ bad execution_plan_json: {e}"

        if execution_plan is None:
            async with httpx.AsyncClient(timeout=VICTORIA_MCP_RUN_TIMEOUT_SEC) as client:
                resp = await client.post(
                    f"{VICTORIA_URL}/orchestrate",
                    json={
                        "goal": goal,
                        "max_steps": max_steps,
                        "return_execution_plan": True,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            execution_plan = data.get("execution_plan")
            victoria_output = str(data.get("output", "") or "")
            if not execution_plan:
                return f"⚠️ Victoria не вернула execution_plan. Ответ:\n{victoria_output}"
        else:
            logger.info(
                "[victoria_execute_plan] skip orchestrate; ready plan steps=%s goal=%s",
                len(execution_plan),
                (goal or "")[:120],
            )

        logger.info(
            "[victoria_execute_plan] steps=%s approve_writes=%s",
            len(execution_plan),
            approve_writes,
        )
        results = execute_plan_local(
            execution_plan,
            workspace_path,
            approve_writes=approve_writes,
        )
        summary = f"План ({len(execution_plan)} шагов, approve_writes={approve_writes}):\n\n"
        summary += "\n".join(results)
        if victoria_output:
            summary += f"\n\nОтвет Victoria:\n{victoria_output}"
        else:
            summary += "\n\n(local plan; /orchestrate skipped)"
        return summary

    except httpx.TimeoutException:
        return f"⏱️ Таймаут: Victoria не ответила за {int(VICTORIA_MCP_RUN_TIMEOUT_SEC)} с."
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_execute_plan")
        return f"❌ Ошибка: {e}"


@mcp.tool()
async def victoria_run_with_context(
    goal: str,
    open_files_json: Optional[str] = None,
    git_status: Optional[str] = None,
    cursor_rules_json: Optional[str] = None,
    workspace_path: Optional[str] = "/Users/bikos/Documents/atra-web-ide",
    max_steps: Optional[int] = 500,
) -> str:
    """Запустить Victoria с полным IDE-контекстом (как в Cursor assistant).

    Victoria получит информацию об открытых файлах, git status, применимых правилах —
    это даёт ей понимание текущего состояния проекта как у Cursor assistant.

    Args:
        goal: Задача для Victoria
        open_files_json: JSON массив открытых файлов [{"path": "...", "content": "...", "cursor_line": 42}, ...]
        git_status: Git status (измененные файлы, ветка): "On branch main\\nModified: src/utils.py\\n..."
        cursor_rules_json: JSON массив применимых правил ["@backend_developer", "@qa_engineer"]
        workspace_path: Путь к workspace
        max_steps: Максимальное количество шагов (по умолчанию 500)

    Returns:
        Результат выполнения задачи от Victoria с учётом IDE-контекста
    """
    try:
        payload = {
            "goal": goal,
            "max_steps": max_steps,
            "workspace_path": workspace_path,
        }

        # Парсинг JSON параметров
        if open_files_json:
            try:
                payload["open_files"] = json.loads(open_files_json)
            except json.JSONDecodeError:
                logger.warning("Failed to parse open_files_json")

        if git_status:
            payload["git_status"] = git_status

        if cursor_rules_json:
            try:
                payload["cursor_rules"] = json.loads(cursor_rules_json)
            except json.JSONDecodeError:
                logger.warning("Failed to parse cursor_rules_json")

        async with httpx.AsyncClient(timeout=VICTORIA_MCP_RUN_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{VICTORIA_URL}/run",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return _parse_run_result(data)

    except httpx.TimeoutException:
        return f"⏱️ Таймаут: Victoria не ответила за {int(VICTORIA_MCP_RUN_TIMEOUT_SEC)} с."
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_run_with_context")
        return f"❌ Ошибка: {e}"


@mcp.tool()
async def victoria_batch_read(
    file_paths_json: str,
    workspace_path: Optional[str] = "/Users/bikos/Documents/atra-web-ide",
    max_concurrent: Optional[int] = 10,
) -> str:
    """Параллельное чтение множества файлов (быстрое сканирование проекта).

    Читает несколько файлов одновременно — полезно для задач типа
    \"покажи содержимое этих 20 файлов\" или \"найди все файлы с X\".

    Args:
        file_paths_json: JSON массив путей ["src/utils.py", "src/main.py", ...]
        workspace_path: Путь к workspace
        max_concurrent: Максимум одновременных чтений (по умолчанию 10)

    Returns:
        Результаты чтения всех файлов (успешные + ошибки)
    """
    try:
        file_paths = json.loads(file_paths_json)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{VICTORIA_URL}/batch_read",
                json={
                    "file_paths": file_paths,
                    "workspace_path": workspace_path,
                    "max_concurrent": max_concurrent,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        summary = data.get("summary", {})

        # Форматируем результат
        output_lines = [
            f"✅ Прочитано {summary.get('success', 0)}/{summary.get('total', 0)} файлов\n"
        ]

        for result in results[:20]:  # Показываем первые 20
            path = result["path"]
            status = result["status"]

            if status == "success":
                content_preview = result.get("content", "")[:200]
                lines = result.get("lines", 0)
                size_kb = result.get("size_kb", 0)
                output_lines.append(
                    f"\n📄 {path} ({size_kb} KB, {lines} lines)\n   Preview: {content_preview}..."
                )
            else:
                error = result.get("error", "unknown error")
                output_lines.append(f"\n❌ {path}: {error}")

        if len(results) > 20:
            output_lines.append(f"\n... и ещё {len(results) - 20} файл(ов)")

        return "\n".join(output_lines)

    except json.JSONDecodeError:
        return "❌ Ошибка: file_paths_json должен быть валидным JSON массивом"
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_batch_read")
        return f"❌ Ошибка: {e}"


@mcp.tool()
async def victoria_batch_grep(
    pattern: str,
    file_paths_json: str,
    workspace_path: Optional[str] = "/Users/bikos/Documents/atra-web-ide",
    case_sensitive: Optional[bool] = False,
) -> str:
    """Параллельный поиск паттерна в множестве файлов (аналог grep).

    Ищет регулярное выражение в нескольких файлах одновременно — полезно для
    \"найди все упоминания функции X в проекте\".

    Args:
        pattern: Регулярное выражение для поиска (например, "validate_email|check_email")
        file_paths_json: JSON массив путей ["src/**/*.py"] (можно использовать glob)
        workspace_path: Путь к workspace
        case_sensitive: Учитывать регистр (по умолчанию False)

    Returns:
        Список всех совпадений с номерами строк
    """
    try:
        file_paths = json.loads(file_paths_json)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{VICTORIA_URL}/batch_grep",
                json={
                    "pattern": pattern,
                    "file_paths": file_paths,
                    "workspace_path": workspace_path,
                    "case_sensitive": case_sensitive,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        summary = data.get("summary", {})

        # Форматируем результат
        output_lines = [
            f"🔍 Найдено {summary.get('total_matches', 0)} совпадений "
            f"в {summary.get('files_with_matches', 0)}/{summary.get('total_files', 0)} файлах\n"
        ]

        for result in results:
            if result["match_count"] == 0:
                continue

            path = result["path"]
            matches = result.get("matches", [])[:10]  # Первые 10 совпадений
            match_count = result["match_count"]

            output_lines.append(f"\n📄 {path} ({match_count} совпадений):")

            for match in matches:
                line_num = match["line"]
                content = match["content"]
                matched_text = match["match"]
                output_lines.append(f"   {line_num}: {content}")
                output_lines.append(f"        ^^^ '{matched_text}'")

            if match_count > 10:
                output_lines.append(f"   ... и ещё {match_count - 10} совпадений")

        return "\n".join(output_lines)

    except json.JSONDecodeError:
        return "❌ Ошибка: file_paths_json должен быть валидным JSON массивом"
    except httpx.RequestError as e:
        return f"❌ Ошибка связи с Victoria: {e}"
    except Exception as e:
        logger.exception("Ошибка victoria_batch_grep")
        return f"❌ Ошибка: {e}"


def _git_tools():
    try:
        from src.agents.tools.system_tools import GitTools
    except ImportError:
        from agents.tools.system_tools import GitTools  # type: ignore
    return GitTools


@mcp.tool()
async def victoria_git_status() -> str:
    """Read-only git status for the ATRA repo (Wave2 polish)."""
    try:
        return await _git_tools().git_status()
    except Exception as e:
        return f"❌ git_status: {e}"


@mcp.tool()
async def victoria_git_diff(file_path: str = "") -> str:
    """Read-only git diff --stat (Wave2). Optional relative file_path."""
    try:
        return await _git_tools().git_diff(file_path=file_path or "")
    except Exception as e:
        return f"❌ git_diff: {e}"


@mcp.tool()
async def victoria_git_log(limit: int = 10) -> str:
    """Read-only recent git log (Wave2)."""
    try:
        return await _git_tools().git_log(count=max(1, min(int(limit or 10), 50)))
    except Exception as e:
        return f"❌ git_log: {e}"


@mcp.tool()
async def victoria_git_pr_list() -> str:
    """Read-only gh pr list (Wave2). Mutate git stays off MCP."""
    try:
        return await _git_tools().git_pr_list()
    except Exception as e:
        return f"❌ git_pr_list: {e}"


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
