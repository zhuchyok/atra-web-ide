#!/usr/bin/env python3
"""
Куратор Victoria: отправить список задач Victoria, сохранить ответы и трассировку для анализа.

Использование:
  python3 scripts/curator_send_tasks_to_victoria.py
  python3 scripts/curator_send_tasks_to_victoria.py --tasks "привет" "статус проекта"
  python3 scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks.txt
  python3 scripts/curator_send_tasks_to_victoria.py --max-wait 120

Результат: docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json (и .md превью).
Cursor-агент может читать отчёт и писать выводы в FINDINGS.

Таймаут среды запуска (VERIFICATION §3, §5): при запуске из IDE/CI/runner с ограничением
времени задавать timeout не меньше: для --quick ≥ 10 мин (600000 ms), для полного прогона
(5 задач) ≥ 30 мин. Иначе процесс будет убит по внешнему лимиту до завершения. См. CURATOR_RUNBOOK §1.
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
# Локальный куратор: явный 127.0.0.1, иначе Docker на macOS иногда логирует GitHub CDN (185.199.x.x)
CURATOR_REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "X-Forwarded-For": "127.0.0.1",
}
REPORTS_DIR = ROOT / "docs/curator_reports"
SYNC_TIMEOUT = int(os.getenv("CURATOR_SYNC_TIMEOUT", "3600"))
POST_RUN_TIMEOUT = int(os.getenv("CURATOR_POST_RUN_TIMEOUT", "1200"))
POLL_INTERVAL = 5.0
POLL_INTERVAL_MIN = float(os.getenv("CURATOR_POLL_INTERVAL_MIN_SEC", str(POLL_INTERVAL)))
POLL_INTERVAL_MAX = float(os.getenv("CURATOR_POLL_INTERVAL_MAX_SEC", "20"))
POLL_BACKOFF_FACTOR = float(os.getenv("CURATOR_POLL_BACKOFF_FACTOR", "1.25"))
POLL_JITTER_RATIO = float(os.getenv("CURATOR_POLL_JITTER_RATIO", "0.1"))
POLL_GRACE_SEC = float(os.getenv("CURATOR_POLL_GRACE_SEC", "120"))
STATUS_404_MAX_RETRIES = int(os.getenv("CURATOR_STATUS_404_MAX_RETRIES", "6"))
STATUS_READ_TIMEOUT_SEC = float(os.getenv("CURATOR_STATUS_READ_TIMEOUT_SEC", "25"))
HEALTH_TIMEOUT_SEC = float(os.getenv("CURATOR_HEALTH_TIMEOUT_SEC", "8"))
HEALTH_RETRIES = int(os.getenv("CURATOR_HEALTH_RETRIES", "3"))
TRANSPORT_ERROR_STREAK_THRESHOLD = int(
    os.getenv("CURATOR_TRANSPORT_ERROR_STREAK_THRESHOLD", "3")
)
TRANSPORT_RECOVERY_COOLDOWN_SEC = float(
    os.getenv("CURATOR_TRANSPORT_RECOVERY_COOLDOWN_SEC", "10")
)
TRANSPORT_RECOVERY_HEALTH_RETRIES = int(
    os.getenv("CURATOR_TRANSPORT_RECOVERY_HEALTH_RETRIES", "3")
)
DEFAULT_MAX_WAIT_SEC = 3600.0
COMPLEX_TASK_MIN_WAIT_SEC = 3600.0  # 60 минут
VERY_COMPLEX_TASK_MIN_WAIT_SEC = 3600.0  # 60 минут
TIMEOUT_ESCALATION_RETRIES = int(os.getenv("CURATOR_TIMEOUT_ESCALATION_RETRIES", "1"))
TIMEOUT_ESCALATION_FACTOR = float(os.getenv("CURATOR_TIMEOUT_ESCALATION_FACTOR", "1.5"))
TIMEOUT_ESCALATION_MAX_WAIT_SEC = float(
    os.getenv("CURATOR_TIMEOUT_ESCALATION_MAX_WAIT_SEC", "7200")
)
ATOMIC_TASK_MIN_CHARS = int(os.getenv("CURATOR_ATOMIC_TASK_MIN_CHARS", "3"))
STILL_RUNNING_RETRY_LIMIT = int(os.getenv("CURATOR_STILL_RUNNING_RETRY_LIMIT", "2"))
STILL_RUNNING_RECOVERY_COOLDOWN_SEC = float(
    os.getenv("CURATOR_STILL_RUNNING_RECOVERY_COOLDOWN_SEC", "12")
)
DEFAULT_TASKS = [
    "привет",
    "какой статус проекта?",
    "покажи список файлов в корне проекта",
    "что ты умеешь?",
]


def _load_tasks_from_file(path: Path) -> list[str]:
    """
    Загружает задачи из файла с защитой от «разрыва» одного большого ТЗ на несколько строк.

    Режимы:
    - если есть пустые строки -> считаем абзацы отдельными задачами;
    - иначе для 2-3 очень длинных строк считаем это одним ТЗ (склеиваем);
    - в остальных случаях сохраняем legacy-поведение (одна строка = одна задача).
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return []

    has_blank_separators = any(not line.strip() for line in lines)
    if has_blank_separators:
        tasks: list[str] = []
        buf: list[str] = []
        for raw in lines:
            s = raw.strip()
            if not s:
                if buf:
                    tasks.append(" ".join(buf).strip())
                    buf = []
                continue
            buf.append(s)
        if buf:
            tasks.append(" ".join(buf).strip())
        return [t for t in tasks if t]

    # Защита: короткий файл из длинных строк часто является одним многострочным ТЗ.
    long_lines = sum(1 for line in non_empty if len(line) >= 100)
    if len(non_empty) <= 3 and long_lines >= 2:
        return [" ".join(non_empty).strip()]

    # Защита: критическое ТЗ без пустых строк, но с no-clarify/execution маркерами.
    merged_lower = " ".join(non_empty).lower()
    no_clarify_markers = (
        "без уточнений",
        "не задавай уточняющие",
        "не задавай встречные вопросы",
        "начинай выполнение сразу",
    )
    execution_markers = ("аудит", "исправ", "проверь", "дашборд", "quality gate", "sql")
    if len(non_empty) <= 3 and any(m in merged_lower for m in no_clarify_markers):
        if sum(1 for m in execution_markers if m in merged_lower) >= 2:
            return [" ".join(non_empty).strip()]

    return non_empty


def _normalize_tasks_atomic(tasks: list[str]) -> list[str]:
    """
    Приводит задачи к атомарному списку:
    - trim + схлопывание пробелов;
    - удаление дублей (case-insensitive);
    - отбрасывание шумовых/пустых записей.
    """
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in tasks:
        item = " ".join((raw or "").split()).strip()
        if len(item) < ATOMIC_TASK_MIN_CHARS:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _is_complex_goal(goal: str) -> bool:
    """Определяет сложные задачи, которым нужен увеличенный max_wait."""
    g = (goal or "").strip().lower()
    if len(g) >= 220:
        return True
    markers = (
        "аудит",
        "ре-аудит",
        "исправ",
        "миграц",
        "дашборд",
        "вкладк",
        "quality gate",
        "контейнер",
        "метрик",
        "сверь",
        "проверь полностью",
    )
    return sum(1 for m in markers if m in g) >= 2


def _is_very_complex_goal(goal: str) -> bool:
    """Определяет очень сложные задачи, которым нужен максимум до 60 минут."""
    g = (goal or "").strip().lower()
    if len(g) >= 600:
        return True
    markers = (
        "каждый пункт",
        "каждый винтик",
        "полностью",
        "от и до",
        "production-ready",
        "все вкладки",
        "все блоки",
        "каждый блок",
        "quality gate",
        "контейнер",
        "миграц",
        "sql",
    )
    return sum(1 for m in markers if m in g) >= 4


def _effective_max_wait(goal: str, configured_wait: float, quick_mode: bool) -> float:
    """Для сложных задач поднимает max_wait минимум до 60 минут."""
    if quick_mode:
        return configured_wait
    if _is_very_complex_goal(goal):
        return max(configured_wait, VERY_COMPLEX_TASK_MIN_WAIT_SEC)
    if _is_complex_goal(goal):
        return max(configured_wait, COMPLEX_TASK_MIN_WAIT_SEC)
    return configured_wait


def _violates_output_quality_gate(goal: str, out: dict) -> Optional[str]:
    """
    Возвращает причину нарушения quality gate или None.
    Не позволяет засчитать формальный success без содержательного выполнения.
    """
    if (out or {}).get("status") != "success":
        return None
    output = ((out or {}).get("output") or "").strip()
    knowledge = (out or {}).get("knowledge") or {}
    output_lower = output.lower()
    goal_lower = (goal or "").lower()

    if not output:
        return "empty_output_for_success"

    # Контракт one-line Python: в ответе не должно быть многострочного мусора.
    if "одну строку" in goal_lower and "python" in goal_lower:
        non_empty_lines = [ln for ln in output.splitlines() if ln.strip()]
        if len(non_empty_lines) > 1:
            return "not_one_line_python_output"
        if "except " in output_lower:
            return "malformed_one_line_python_output"

    no_clarify_markers = (
        "без уточнений",
        "не задавай уточняющие",
        "не задавай встречные вопросы",
        "начинай выполнение сразу",
    )
    operational_markers = (
        "аудит",
        "dashboard",
        "дашборд",
        "sql",
        "миграц",
        "quality gate",
        "проверь",
        "исправ",
    )
    if any(m in goal_lower for m in no_clarify_markers):
        if knowledge.get("needs_clarification") or "уточняет" in output_lower:
            return "clarification_returned_for_no_clarify_goal"
    # Для операционных задач уточнения считаются неполным исполнением.
    if any(m in goal_lower for m in operational_markers):
        if knowledge.get("needs_clarification") or "уточняет" in output_lower:
            return "clarification_returned_for_operational_goal"
        # Контракт релевантности: операционная задача должна содержательно
        # попадать в предметную область dashboard/sql/health, а не в оффтоп.
        operational_domain_markers = (
            "dashboard",
            "дашборд",
            "обзор",
            "sql",
            "миграц",
            "health",
            "postgresql",
            "victoria agent",
            "postgre",
            "ollama",
            "mlx",
            "stale",
            "quality gate",
            "failed",
            "pending",
            "in_progress",
        )
        obvious_offtopic_markers = (
            "project golden standard",
            "корпоративного золотого стандарта",
            "стратегического планирования 2026",
            "singularity 14.0",
        )
        has_domain_signal = any(m in output_lower for m in operational_domain_markers)
        has_offtopic_signal = any(m in output_lower for m in obvious_offtopic_markers)
        if has_offtopic_signal and not has_domain_signal:
            return "offtopic_output_for_operational_goal"
        pseudo_success_markers = (
            "необходимо получить",
            "нужно получить",
            "не предоставил",
            "не предоставлены",
            "не могу выполнить",
            "должен сообщить о необходимости",
            "предоставьте исходные данные",
            "доступны только:",
            "\"tool_input\"",
            "\"action\": \"read_file\"",
            "\"action\": \"list_directory\"",
            "execution plan",
            "```json",
        )
        if any(m in output_lower for m in pseudo_success_markers):
            return "insufficient_data_pseudo_success_for_operational_goal"

    # Простая защита от мусорных ответов (шумовые символы/think-dump без сути).
    if output:
        bang_ratio = output.count("!") / max(1, len(output))
        if bang_ratio > 0.2 and "<think>" in output_lower:
            return "malformed_think_dump_output"

    # Слишком короткий output на явно сложной задаче — вероятный ложный success.
    if _is_complex_goal(goal) and len(output) < 80:
        return "too_short_output_for_complex_goal"

    # Явный фейл-текст не должен считаться success.
    failure_markers = (
        "не удалось",
        "ошибка",
        "таймаут",
        "timed out",
        "failed",
    )
    if _is_complex_goal(goal) and any(m in output_lower for m in failure_markers):
        return "failure_text_inside_success_output"

    return None


def _is_timeout_like_error(err: Optional[str]) -> bool:
    low = (err or "").lower()
    timeout_markers = (
        "poll timeout",
        "timed out",
        "timeout",
        "не уложилась",
        "enhanced_solve_timeout",
        "enhanced_llm_timeout",
        "victoria_still_running",
        "victoria_stale",
    )
    return any(marker in low for marker in timeout_markers)


def _is_victoria_still_running_error(err: Optional[str]) -> bool:
    low = (err or "").lower()
    return "victoria_still_running:" in low


def _extract_still_running_state(err: Optional[str]) -> str:
    low = (err or "").lower()
    if "victoria_still_running:" not in low:
        return ""
    return low.split("victoria_still_running:", 1)[1].strip()


def _is_transport_like_error(err: Optional[str]) -> bool:
    low = (err or "").lower()
    transport_markers = (
        "connection refused",
        "connection reset",
        "connection aborted",
        "max retries exceeded",
        "failed to establish a new connection",
        "newconnectionerror",
        "remoteprotocolerror",
        "httpconnectionpool",
    )
    return any(marker in low for marker in transport_markers)


def _is_transport_error(err: Optional[str]) -> bool:
    low = (err or "").lower()
    transport_markers = (
        "connection reset",
        "connection refused",
        "connection aborted",
        "max retries exceeded",
        "failed to establish a new connection",
        "remoteprotocolerror",
        "read timeout",
    )
    return any(marker in low for marker in transport_markers)


def _is_hard_server_timeout(err: Optional[str]) -> bool:
    """
    Таймауты, где увеличение client-side max-wait бесполезно:
    сервер уже завершил задачу по внутреннему фиксированному лимиту.
    """
    low = (err or "").lower()
    hard_markers = (
        "не уложилась в 1200s",
        "enhanced_solve_timeout",
        "enhanced_llm_timeout",
        "victoria enhanced не уложилась",
    )
    return any(marker in low for marker in hard_markers)


def _should_escalate_timeout(
    *,
    async_mode: bool,
    status: str,
    error: Optional[str],
    escalation_attempt: int,
) -> bool:
    """Единая проверка: эскалировать ли max-wait для текущей ошибки."""
    if not async_mode:
        return False
    if status != "error":
        return False
    if not _is_timeout_like_error(error):
        return False
    if _is_hard_server_timeout(error):
        return False
    return escalation_attempt < TIMEOUT_ESCALATION_RETRIES


def _bounded_poll_interval(v: float) -> float:
    return max(POLL_INTERVAL_MIN, min(POLL_INTERVAL_MAX, v))


def _next_poll_interval(current: float, *, reset: bool = False) -> float:
    if reset:
        return _bounded_poll_interval(POLL_INTERVAL_MIN)
    return _bounded_poll_interval(current * POLL_BACKOFF_FACTOR)


def _sleep_poll(interval: float) -> None:
    if POLL_JITTER_RATIO <= 0:
        time.sleep(_bounded_poll_interval(interval))
        return
    jitter = interval * POLL_JITTER_RATIO
    delay = interval + random.uniform(-jitter, jitter)
    time.sleep(_bounded_poll_interval(delay))


def _extract_goal_file_path(goal: str) -> Optional[Path]:
    m = re.search(r"(/app/\S+)", goal or "")
    if not m:
        return None
    raw = m.group(1).rstrip(").,!?;:\"'»…")
    if raw.startswith("/app/"):
        return ROOT / raw[len("/app/") :]
    return Path(raw)


def _local_fallback_for_goal(goal: str, correlation_id: Optional[str]) -> Optional[dict]:
    low = (goal or "").lower()
    path = _extract_goal_file_path(goal)
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return {
            "status": "error",
            "error": f"local_fallback_file_read_error:{e}",
            "output": None,
            "knowledge": {
                "method": "curator_local_fallback",
                "metadata": {"model_used": "curator_local_fallback", "source": "local"},
            },
            "correlation_id": correlation_id,
        }

    lines = text.splitlines()
    path_label = f"/app/{path.relative_to(ROOT)}"

    if "pip install в рантайме" in low:
        markers = (
            "pip install",
            "python -m pip install",
            "python3 -m pip install",
        )
        hits = []
        for idx, line in enumerate(lines, 1):
            norm = line.lower()
            if any(marker in norm for marker in markers):
                hits.append((idx, line.strip()))
        if hits:
            body = "\n".join(f"- L{n}: {s}" for n, s in hits[:8])
            output = (
                f"ПРОБЛЕМА\nФайл: {path_label}\n"
                f"Найдены признаки runtime pip install:\n{body}"
            )
        else:
            output = (
                f"ОК\nФайл: {path_label}\n"
                "Runtime вызовов pip install через subprocess/os.system/python -m pip install не обнаружено."
            )
        return {
            "status": "success",
            "output": output,
            "knowledge": {
                "method": "curator_local_fallback",
                "metadata": {"model_used": "curator_local_fallback", "source": "local"},
                "execution_trace": {
                    "task_type": "local_fallback",
                    "method": "local_file_audit_pip_install",
                    "goal_preview": goal[:120],
                },
            },
            "correlation_id": correlation_id,
        }

    if "hardcoded секреты или пароли в первых 30 строках" in low:
        top = lines[:30]
        bad = []
        pat = re.compile(
            r"(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"]+['\"]",
            re.IGNORECASE,
        )
        for i, ln in enumerate(top, 1):
            ln_low = ln.lower()
            if "os.getenv(" in ln_low or "environ.get(" in ln_low:
                continue
            if pat.search(ln):
                bad.append((i, ln.strip()))
        if bad:
            body = "\n".join(f"- L{n}: {s}" for n, s in bad[:6])
            output = (
                f"ПРОБЛЕМА\nФайл: {path_label}\n"
                f"В первых 30 строках найдены потенциальные hardcoded секреты/пароли:\n{body}"
            )
        else:
            output = (
                f"ОК\nФайл: {path_label}\n"
                "В первых 30 строках hardcoded секреты/пароли не обнаружены."
            )
        return {
            "status": "success",
            "output": output,
            "knowledge": {
                "method": "curator_local_fallback",
                "metadata": {"model_used": "curator_local_fallback", "source": "local"},
                "execution_trace": {
                    "task_type": "local_fallback",
                    "method": "local_file_audit_secrets",
                    "goal_preview": goal[:120],
                },
            },
            "correlation_id": correlation_id,
        }

    if "найди потенциальные проблемы" in low and "eval()" in low and "exec()" in low:
        findings = []
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            l = s.lower()
            if "subprocess." in l or "popen(" in l:
                findings.append(f"- subprocess: L{i}: {s}")
            if re.search(r"https?://", s):
                findings.append(f"- hardcoded_url: L{i}: {s}")
            if "eval(" in l:
                findings.append(f"- eval: L{i}: {s}")
            if re.search(r"\bexec\(", l):
                findings.append(f"- exec: L{i}: {s}")
        if findings:
            output = (
                f"ПРОБЛЕМА\nФайл: {path_label}\n"
                "Найдены потенциальные риски:\n" + "\n".join(findings[:12])
            )
        else:
            output = (
                f"ОК\nФайл: {path_label}\n"
                "Потенциальные проблемы (subprocess/hardcoded URL/eval/exec) не обнаружены."
            )
        return {
            "status": "success",
            "output": output,
            "knowledge": {
                "method": "curator_local_fallback",
                "metadata": {"model_used": "curator_local_fallback", "source": "local"},
                "execution_trace": {
                    "task_type": "local_fallback",
                    "method": "local_file_audit_risk_scan",
                    "goal_preview": goal[:120],
                },
            },
            "correlation_id": correlation_id,
        }

    return None


def check_health(url: str) -> bool:
    for attempt in range(1, HEALTH_RETRIES + 1):
        try:
            r = requests.get(f"{url}/health", timeout=HEALTH_TIMEOUT_SEC)
            if r.status_code == 200:
                return True
            print(f"Health check non-200: {r.status_code} (attempt {attempt}/{HEALTH_RETRIES})")
        except Exception as e:
            print(f"Health check error (attempt {attempt}/{HEALTH_RETRIES}): {e}")
        if attempt < HEALTH_RETRIES:
            time.sleep(1)
    return False


def run_sync(
    url: str, goal: str, project_context: str = "atra-web-ide", max_steps: int = 50
) -> dict:
    """Синхронный POST /run (без async_mode). Возвращает полный ответ с correlation_id и knowledge."""
    payload = {"goal": goal, "max_steps": max_steps, "project_context": project_context}
    try:
        r = requests.post(
            f"{url}/run",
            json=payload,
            params={"async_mode": "false"},
            headers=CURATOR_REQUEST_HEADERS,
            timeout=SYNC_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "error": "timeout",
            "output": None,
            "knowledge": None,
            "correlation_id": None,
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": str(e),
            "output": None,
            "knowledge": None,
            "correlation_id": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "output": None,
            "knowledge": None,
            "correlation_id": None,
        }


def _classify_terminal_error(rec: dict, fallback: str) -> str:
    """Классификация ошибок poll/failed для отчёта куратора."""
    err = (rec or {}).get("error") or fallback
    err_s = str(err)
    low = err_s.lower()
    if "timed out" in low or "auto-cleanup" in low or "timeout after" in low:
        return f"victoria_stale:{err_s}"
    return err_s


def _poll_run_status_once(url: str, task_id: str) -> Tuple[int, Optional[dict]]:
    """Один GET /run/status с короткими ретраями на connection reset."""
    last_err = None
    for _ in range(3):
        try:
            s = requests.get(
                f"{url}/run/status/{task_id}",
                headers=CURATOR_REQUEST_HEADERS,
                timeout=STATUS_READ_TIMEOUT_SEC,
            )
            if s.status_code == 200:
                return s.status_code, s.json()
            return s.status_code, None
        except requests.exceptions.RequestException as e:
            last_err = e
            err_str = str(e).lower()
            if (
                "connection" in err_str
                or "reset" in err_str
                or "aborted" in err_str
                or "timed out" in err_str
            ):
                time.sleep(2)
                continue
            raise
    if last_err is not None:
        raise last_err
    return 0, None


def run_async_poll(
    url: str, goal: str, project_context: str, max_steps: int, max_wait: float
) -> dict:
    """POST async_mode=true, затем опрос GET /run/status/{task_id}. Возвращает тот же формат что и sync."""
    payload = {"goal": goal, "max_steps": max_steps, "project_context": project_context}
    try:
        r = requests.post(
            f"{url}/run",
            json=payload,
            params={"async_mode": "true"},
            headers=CURATOR_REQUEST_HEADERS,
            timeout=POST_RUN_TIMEOUT,
        )
        if r.status_code == 200:
            # Fast Track или мгновенный ответ
            data = r.json()
            return {
                "status": "success",
                "output": data.get("output") or "",
                "knowledge": data.get("knowledge") or {},
                "correlation_id": data.get("correlation_id"),
            }
        if r.status_code != 202:
            r.raise_for_status()
        data = r.json()
        task_id = data.get("task_id")
        correlation_id = data.get("correlation_id")
        if not task_id:
            return {
                "status": "error",
                "error": "202 without task_id",
                "output": None,
                "knowledge": None,
                "correlation_id": correlation_id,
            }
        deadline = time.monotonic() + max_wait
        last_log = 0.0
        last_rec: Optional[dict] = None
        not_found_streak = 0
        poll_interval = _bounded_poll_interval(POLL_INTERVAL)
        while time.monotonic() < deadline:
            status_code, rec = _poll_run_status_once(url, task_id)
            if status_code == 404:
                not_found_streak += 1
                if not_found_streak >= STATUS_404_MAX_RETRIES:
                    return {
                        "status": "error",
                        "error": f"victoria_task_not_found:{task_id}",
                        "output": None,
                        "knowledge": None,
                        "correlation_id": correlation_id,
                    }
                _sleep_poll(poll_interval)
                poll_interval = _next_poll_interval(poll_interval)
                continue
            if status_code != 200 or rec is None:
                _sleep_poll(poll_interval)
                poll_interval = _next_poll_interval(poll_interval)
                continue
            not_found_streak = 0
            last_rec = rec
            st = rec.get("status", "")
            # Прогресс раз в 15 сек, чтобы видеть что не зависли
            now = time.monotonic()
            if now - last_log >= 15.0:
                elapsed = int(deadline - now)
                print(
                    f"      ... ждём Victoria (status={st}, poll={poll_interval:.1f}s, осталось ~{elapsed}s)"
                )
                last_log = now
            if st == "completed":
                out = rec.get("output") or ""
                know = rec.get("knowledge") or {}
                if correlation_id is None:
                    correlation_id = rec.get("correlation_id")
                return {
                    "status": "success",
                    "output": out,
                    "knowledge": know,
                    "correlation_id": correlation_id,
                }
            if st == "failed":
                return {
                    "status": "error",
                    "error": _classify_terminal_error(rec, "failed"),
                    "output": None,
                    "knowledge": rec.get("knowledge"),
                    "correlation_id": correlation_id,
                }
            _sleep_poll(poll_interval)
            poll_interval = _next_poll_interval(poll_interval)

        # Grace poll: Victoria cleanup может выставить failed через 1–3 мин после max_wait
        if POLL_GRACE_SEC > 0:
            grace_deadline = time.monotonic() + POLL_GRACE_SEC
            print(
                f"      ... grace poll {int(POLL_GRACE_SEC)}s (ждём completed/failed после основного таймаута)"
            )
            poll_interval = _bounded_poll_interval(POLL_INTERVAL)
            while time.monotonic() < grace_deadline:
                status_code, rec = _poll_run_status_once(url, task_id)
                if status_code == 404:
                    not_found_streak += 1
                    if not_found_streak >= STATUS_404_MAX_RETRIES:
                        return {
                            "status": "error",
                            "error": f"victoria_task_not_found:{task_id}",
                            "output": None,
                            "knowledge": None,
                            "correlation_id": correlation_id,
                        }
                    _sleep_poll(poll_interval)
                    poll_interval = _next_poll_interval(poll_interval)
                    continue
                if status_code == 200 and rec:
                    not_found_streak = 0
                    last_rec = rec
                    st = rec.get("status", "")
                    if st == "completed":
                        out = rec.get("output") or ""
                        know = rec.get("knowledge") or {}
                        if correlation_id is None:
                            correlation_id = rec.get("correlation_id")
                        return {
                            "status": "success",
                            "output": out,
                            "knowledge": know,
                            "correlation_id": correlation_id,
                        }
                    if st == "failed":
                        return {
                            "status": "error",
                            "error": _classify_terminal_error(rec, "failed"),
                            "output": None,
                            "knowledge": rec.get("knowledge"),
                            "correlation_id": correlation_id,
                        }
                _sleep_poll(poll_interval)
                poll_interval = _next_poll_interval(poll_interval)

        if last_rec and last_rec.get("status") == "failed":
            return {
                "status": "error",
                "error": _classify_terminal_error(last_rec, "failed"),
                "output": None,
                "knowledge": last_rec.get("knowledge"),
                "correlation_id": correlation_id,
            }
        if last_rec and last_rec.get("status") in ("running", "processing", "queued"):
            return {
                "status": "error",
                "error": f"victoria_still_running:{last_rec.get('status')}",
                "output": None,
                "knowledge": last_rec.get("knowledge"),
                "correlation_id": correlation_id,
            }
        return {
            "status": "error",
            "error": "poll timeout",
            "output": None,
            "knowledge": None,
            "correlation_id": correlation_id,
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": str(e),
            "output": None,
            "knowledge": None,
            "correlation_id": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "output": None,
            "knowledge": None,
            "correlation_id": None,
        }


def main():
    import argparse

    p = argparse.ArgumentParser(description="Куратор: отправить задачи Victoria и сохранить отчёт")
    p.add_argument("--tasks", nargs="*", help="Цели (по одной); если не задано — встроенный список")
    p.add_argument("--file", type=str, help="Файл с целями (одна на строку)")
    p.add_argument(
        "--async", dest="async_mode", action="store_true", help="Использовать async 202 + poll"
    )
    p.add_argument(
        "--max-wait",
        type=float,
        default=DEFAULT_MAX_WAIT_SEC,
        help="Макс. сек ожидания при async (по умолчанию 3600). Для сложных задач авто-повышается до 3600.",
    )
    p.add_argument(
        "--quick",
        action="store_true",
        help="Быстрый прогон: только 2 задачи, max-wait 180 с (для проверки)",
    )
    p.add_argument(
        "--project",
        type=str,
        default=os.getenv("PROJECT_CONTEXT", "atra-web-ide"),
        help="project_context",
    )
    args = p.parse_args()

    if args.quick:
        args.max_wait = 180.0

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            print(f"❌ Файл не найден: {path}")
            sys.exit(1)
        tasks = _load_tasks_from_file(path)
        if not tasks:
            print("❌ В файле нет непустых строк с задачами.")
            sys.exit(1)
    elif args.tasks:
        tasks = args.tasks
    else:
        tasks = DEFAULT_TASKS

    tasks = _normalize_tasks_atomic(tasks)
    if not tasks:
        print("❌ Нет валидных атомарных задач после нормализации входа.")
        sys.exit(1)

    if args.quick and len(tasks) > 2:
        tasks = tasks[:2]
        print("--quick: только первые 2 задачи, max-wait 180 с")

    print(
        f"Задач: {len(tasks)}, макс. ожидание на задачу: {args.max_wait:.0f} с (одна задача ~1–5 мин на Mac Studio)"
    )
    if args.async_mode:
        print("Режим: async (202 + опрос /run/status каждые 2.5 с, прогресс раз в 15 с)")

    if not check_health(VICTORIA_URL):
        print(f"❌ Victoria недоступна: {VICTORIA_URL}")
        print(
            "   Запустите: docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent"
        )
        sys.exit(1)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    report_json = REPORTS_DIR / f"curator_{ts}.json"
    report_md = REPORTS_DIR / f"curator_{ts}.md"
    artifacts_dir = REPORTS_DIR / f"artifacts_{ts}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    results = []
    transport_error_streak = 0
    rec_ts = ts  # Используем общую метку времени для артефактов
    for i, goal in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {goal[:60]}...")
        start = time.perf_counter()
        effective_wait = _effective_max_wait(goal, args.max_wait, args.quick)
        if args.async_mode and effective_wait != args.max_wait:
            wait_label = (
                "60 мин"
                if effective_wait >= VERY_COMPLEX_TASK_MIN_WAIT_SEC
                else "20 мин"
            )
            print(
                f"    сложная задача: max-wait повышен до {effective_wait:.0f} с ({wait_label})"
            )
        current_wait = effective_wait
        escalation_attempt = 0
        still_running_retry_attempt = 0
        while True:
            if args.async_mode:
                out = run_async_poll(
                    VICTORIA_URL, goal, args.project, max_steps=50, max_wait=current_wait
                )
            else:
                out = run_sync(VICTORIA_URL, goal, args.project, max_steps=50)

            # До двух повторов при обрыве соединения или read timeout (холодный старт Victoria)
            for _retry in range(2):
                if out.get("status") != "error" or not out.get("error"):
                    break
                err_str = str(out.get("error")).lower()
                if (
                    "connection" not in err_str
                    and "reset" not in err_str
                    and "aborted" not in err_str
                    and "timed out" not in err_str
                ):
                    break
                print("    повтор через 3 с (обрыв соединения или таймаут)...")
                time.sleep(3)
                if args.async_mode:
                    out = run_async_poll(
                        VICTORIA_URL,
                        goal,
                        args.project,
                        max_steps=50,
                        max_wait=current_wait,
                    )
                else:
                    out = run_sync(VICTORIA_URL, goal, args.project, max_steps=50)

            if _should_escalate_timeout(
                async_mode=args.async_mode,
                status=str(out.get("status") or ""),
                error=out.get("error"),
                escalation_attempt=escalation_attempt,
            ):
                escalation_attempt += 1
                next_wait = min(
                    max(current_wait + 1, current_wait * TIMEOUT_ESCALATION_FACTOR),
                    TIMEOUT_ESCALATION_MAX_WAIT_SEC,
                )
                if next_wait > current_wait:
                    print(
                        "    escalation: timeout-like error,"
                        f" увеличиваем max-wait {current_wait:.0f}s -> {next_wait:.0f}s"
                    )
                    current_wait = next_wait
                    continue
            if (
                args.async_mode
                and out.get("status") == "error"
                and _is_victoria_still_running_error(out.get("error"))
                and still_running_retry_attempt < STILL_RUNNING_RETRY_LIMIT
            ):
                still_running_retry_attempt += 1
                state = _extract_still_running_state(out.get("error"))
                cooldown = STILL_RUNNING_RECOVERY_COOLDOWN_SEC
                if state == "queued":
                    cooldown = max(cooldown, STILL_RUNNING_RECOVERY_COOLDOWN_SEC * 2)
                print(
                    "    still-running recovery:"
                    f" retry {still_running_retry_attempt}/{STILL_RUNNING_RETRY_LIMIT}"
                    f", state={state or 'unknown'}, cooldown {cooldown:.0f}s"
                )
                # KISS: перед повтором коротко проверяем health и даём Victoria завершить зависшие воркеры.
                check_health(VICTORIA_URL)
                time.sleep(cooldown)
                continue
            break

        if (
            args.async_mode
            and out.get("status") == "error"
            and _is_victoria_still_running_error(out.get("error"))
        ):
            fallback = _local_fallback_for_goal(goal, out.get("correlation_id"))
            if fallback is not None:
                print("    fallback-local: применён deterministic file-audit fallback")
                out = fallback

        # P0 fail-fast/recover: не сыпем длинную серию транспортных ошибок подряд.
        if out.get("status") == "error" and _is_transport_like_error(out.get("error")):
            transport_error_streak += 1
        else:
            transport_error_streak = 0

        if transport_error_streak >= TRANSPORT_ERROR_STREAK_THRESHOLD:
            print(
                "    transport-failfast: серия сетевых ошибок, запускаем recovery "
                f"(streak={transport_error_streak})"
            )
            recovered = False
            for attempt in range(1, TRANSPORT_RECOVERY_HEALTH_RETRIES + 1):
                if check_health(VICTORIA_URL):
                    recovered = True
                    print(f"    recovery-ok: Victoria health восстановлен (attempt {attempt})")
                    break
                print(
                    "    recovery-wait: Victoria health still failing "
                    f"(attempt {attempt}/{TRANSPORT_RECOVERY_HEALTH_RETRIES}), "
                    f"sleep {TRANSPORT_RECOVERY_COOLDOWN_SEC:.0f}s"
                )
                time.sleep(TRANSPORT_RECOVERY_COOLDOWN_SEC)
            if not recovered:
                print(
                    "    recovery-failed: Victoria health unstable, продолжаем с пониженной скоростью."
                )
                time.sleep(TRANSPORT_RECOVERY_COOLDOWN_SEC)
            transport_error_streak = 0

        quality_violation = _violates_output_quality_gate(goal, out)
        if quality_violation:
            out = {
                "status": "error",
                "error": f"quality_gate_failed:{quality_violation}",
                "output": out.get("output"),
                "knowledge": out.get("knowledge"),
                "correlation_id": out.get("correlation_id"),
            }
        elapsed = time.perf_counter() - start
        trace = (out.get("knowledge") or {}).get("execution_trace") or (out.get("knowledge") or {})

        # [SINGULARITY 22.8] Artifact-Driven Reporting
        artifact_path = None
        if out.get("output") or out.get("knowledge"):
            artifact_filename = f"task_{i}_{rec_ts}.json"
            artifact_path = artifacts_dir / artifact_filename
            artifact_data = {
                "goal": goal,
                "output": out.get("output"),
                "knowledge": out.get("knowledge"),
                "correlation_id": out.get("correlation_id"),
            }
            artifact_path.write_text(
                json.dumps(artifact_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        rec = {
            "goal": goal,
            "status": out.get("status"),
            "error": out.get("error"),
            "output_preview": (out.get("output") or "")[:500] if out.get("output") else None,
            "output_length": len(out.get("output") or ""),
            "correlation_id": out.get("correlation_id"),
            "execution_trace": trace,
            "elapsed_seconds": round(elapsed, 2),
            "artifact_file": str(artifact_path.name) if artifact_path else None,
        }
        results.append(rec)
        print(
            f"    -> {rec['status']} ({elapsed:.1f}s) correlation_id={(rec.get('correlation_id') or '')[:8]}"
        )

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "victoria_url": VICTORIA_URL,
        "project_context": args.project,
        "async_mode": args.async_mode,
        "tasks_count": len(tasks),
        "results": results,
    }
    success_count = sum(1 for r in results if r.get("status") == "success")
    error_count = len(results) - success_count
    total_elapsed = sum(float(r.get("elapsed_seconds") or 0) for r in results)
    throughput_tasks_per_min = (
        round((len(results) / total_elapsed) * 60, 3) if total_elapsed > 0 else 0.0
    )
    report["summary"] = {
        "success_count": success_count,
        "error_count": error_count,
        "error_rate_pct": round((error_count / max(1, len(results))) * 100, 2),
        "throughput_tasks_per_min": throughput_tasks_per_min,
        "timeout_like_errors": sum(
            1 for r in results if _is_timeout_like_error(str(r.get("error") or ""))
        ),
        "quality_gate_failed": sum(
            1
            for r in results
            if str(r.get("error") or "").startswith("quality_gate_failed:")
        ),
        "stale_like_errors": sum(
            1 for r in results if "victoria_stale" in str(r.get("error") or "")
        ),
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Кураторский прогон {ts}",
        "",
        f"- Victoria: {VICTORIA_URL}",
        f"- Задач: {len(tasks)}",
        "",
        "## KPI",
        "",
        f"- Success: {report['summary']['success_count']}",
        f"- Error: {report['summary']['error_count']}",
        f"- Error rate: {report['summary']['error_rate_pct']}%",
        f"- Throughput: {report['summary']['throughput_tasks_per_min']} tasks/min",
        f"- Timeout-like errors: {report['summary']['timeout_like_errors']}",
        f"- Quality gate failed: {report['summary']['quality_gate_failed']}",
        f"- Stale-like errors: {report['summary']['stale_like_errors']}",
        "",
        "## Результаты",
        "",
    ]
    for r in results:
        md_lines.append(f"### {r['goal'][:80]}")
        md_lines.append(f"- **Статус:** {r['status']}")
        md_lines.append(f"- **Время:** {r['elapsed_seconds']} с")
        if r.get("correlation_id"):
            md_lines.append(f"- **correlation_id:** {r['correlation_id']}")
        if r.get("execution_trace"):
            md_lines.append(
                f"- **Трассировка:** `{json.dumps(r['execution_trace'], ensure_ascii=False)[:200]}...`"
            )
        if r.get("output_preview"):
            md_lines.append(f"- **Превью ответа:** {r['output_preview'][:300]}...")
        md_lines.append("")
    report_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n✅ Отчёт сохранён: {report_json}")
    print(f"   Превью: {report_md}")
    print(
        "   Куратор (Cursor) может проанализировать отчёт и записать выводы в docs/curator_reports/FINDINGS_*.md"
    )


if __name__ == "__main__":
    main()
