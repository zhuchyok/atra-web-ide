"""
Log Scanner — мониторинг Docker логов и отправка ошибок в Victoria.

Сканирует логи всех контейнеров, детектит ошибки, дедуплицирует,
и отправляет в Victoria через event bus для автономного исправления.

Запуск: python -m app.medic.log_scanner
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [LOG_SCANNER] %(message)s",
)
logger = logging.getLogger(__name__)

# Victoria URL
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://victoria-agent:8000")

# Scan interval in seconds
SCAN_INTERVAL = int(os.getenv("LOG_SCANNER_INTERVAL", "30"))
_SCANNER_SNAP = Path(__file__).resolve().parents[2] / "tmp" / "log_scanner_last.json"

# Containers to monitor (empty = all)
WATCH_CONTAINERS = os.getenv("LOG_SCANNER_CONTAINERS", "").split(",")

# Error patterns to detect
ERROR_PATTERNS = [
    # Log-level markers only. Bare "Error de respuesta" is LLM prose, not an incident.
    re.compile(r"(?:^|[\s\"'])ERROR[:\s]|- ERROR -|\bCRITICAL\b|FATAL:"),
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"Exception:|RuntimeError:|ValueError:|TypeError:"),
    re.compile(r"raise \w+Error"),
    re.compile(r"module.*not found|ImportError|ModuleNotFoundError"),
    re.compile(r"connection refused|ConnectionRefusedError"),
    # TimeoutError/ReadTimeout as bare tokens fire on WARNING audits and
    # Ollama retries. Real hangs still match ERROR: / Traceback / Exception:.
    # Bare "OOM" fires on SQL/RAG "OOM guards". Real killer is oom-kill / OOMKilled.
    re.compile(r"OutOfMemoryError|OOMKilled|oom-kill"),
    re.compile(r"signal \d+|SIGKILL|SIGTERM"),
    re.compile(r"killed|oom-kill"),
    re.compile(r"assert.*failed|AssertionError"),
    re.compile(r"permission denied|PermissionError"),
    re.compile(r"file not found|FileNotFoundError"),
    re.compile(r"json\.decoder\.JSONDecodeError"),
    re.compile(r"AttributeError:.*has no attribute"),
    re.compile(r"KeyError:"),
    re.compile(r"IndexError:.*out of range"),
]

# Patterns to ignore (false positives)
IGNORE_PATTERNS = [
    re.compile(r"INFO|DEBUG|WARNING.*httpx"),
    re.compile(r"level=info.*flag evaluation succeeded", re.IGNORECASE),
    re.compile(r"DeprecationWarning"),
    re.compile(r"ResourceWarning"),
    re.compile(r"RuntimeWarning"),
    re.compile(r"token_auditor"),
    re.compile(r"MEM WATCHDOG"),
    re.compile(r"DELEGATION_METRICS"),
    re.compile(r"HTTP Request:"),
    re.compile(r"\[LOG_SCANNER\]"),  # Ignore own logs
    re.compile(r"log-scanner"),  # Ignore own container
    re.compile(r"CancelledError"),  # Benign asyncio timeout cancellation
    re.compile(r"_GatheringFuture exception was never retrieved"),
    re.compile(r"Future exception was never retrieved"),
    re.compile(r"sync safe mode failed"),
    re.compile(r"background hard-timeout"),
    # Warmup saturation is transient startup pressure, not a remediation incident.
    re.compile(r"\[VICTORIA\]\s+Прогрев .*вернул 503", re.IGNORECASE),
    re.compile(r"\[VICTORIA\]\s+Прогрев .*busy \(503\)", re.IGNORECASE),
    # Grafana plugin auto-update failures are non-critical for ATRA runtime.
    re.compile(r"plugin\.backgroundinstaller.*failed to install plugin", re.IGNORECASE),
    # Watchdog EXPLAIN ANALYZE on pg_stat_statements $n → postgres type errors.
    re.compile(r"operator does not exist: (double precision \* text|text \* double precision)"),
    re.compile(r"canceling statement due to user request"),
    re.compile(r"FATAL:\s+connection to client lost"),
    # Curator/skill SQL against the wrong table: not a schema outage.
    re.compile(r'column "[^"]+" does not exist'),
    # Curator/skill SQL: GROUP BY mistake, not a schema outage.
    re.compile(r"aggregate functions are not allowed in GROUP BY"),
    # Postgres prints STATEMENT: after ERROR; SQL text (OOM guards, etc.) is not an incident.
    re.compile(r"\] STATEMENT:"),
    # RAG score lines, not crashes.
    re.compile(r"\[hybrid\] Sim "),
    re.compile(r"password authentication failed"),
    re.compile(r"\[MISMATCH-RECOVERY\]"),
    # Truncated corp module / parse self-loop (root is restored file).
    re.compile(r"Ошибка парсинга промпта"),
    re.compile(r"IndentationError.*corporation_knowledge_system"),
    # PG pool hiccups are transient, not remediation incidents.
    re.compile(r"\[HEARTBEAT\] Loop failed.*Too many connections"),
    re.compile(r"Too many connections"),
    re.compile(r"Too many conn"),  # docker/scanner line may truncate "connections"
    # pgbouncer-only config errors surfaced by SHOW; not a ATRA incident
    re.compile(r'unrecognized configuration parameter "default_pool_size"'),
    re.compile(r"password authentication failed for user"),
    re.compile(r"FATAL:  password authentication failed"),
    re.compile(r"task_identity_map.*violates foreign key constraint"),
    re.compile(r"Sandbox bind path .* is container-local"),
    re.compile(r"SandboxManager: Docker not available"),
    # Header alone is not an incident; the exception line is. CancelledError
    # traces were creating a task from this line while the next line was ignored.
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"_receive_event\(timeout=timeout\)"),
    re.compile(r"Ollama timeout, retry \d+/\d+"),
    re.compile(
        r"Exception calling Node .*(ReadTimeout|RemoteProtocolError|ConnectError|Server disconnected)"
    ),
    re.compile(r"\[LLM_ERROR\] HTTP 500:.*unexpected EOF"),
    # LLM snippet QA is expected to fail; not a runtime incident.
    re.compile(r"\[SANDBOX GROUNDING\]"),
    re.compile(r"\[QUALITY CHECK\]"),
    re.compile(r"Sandbox Grounding Failed"),
    re.compile(r"No module named 'pytest'"),
    re.compile(r"\[INFERENCE\] Ошибка прогрева модели"),
    re.compile(r"Все модели недоступны"),
    re.compile(r'"content":\s*"#'),
    re.compile(r"\[WORKER\] I am identified as:"),
    re.compile(r"Blackboard monitor started"),
    re.compile(r"Error de respuesta"),
    re.compile(r"Посмотрите в браузере / Network или в логах Open WebUI"),
    re.compile(r"RAG retrieval превысил таймаут"),
    re.compile(r"продолжаем без контекста"),
    re.compile(r'terminating background worker "parallel worker"'),
    # Guard refusal is success — do not open a fix loop on the lock.
    re.compile(r"\[SOURCE_GUARD\]"),
    re.compile(r"SOURCE_GUARD:"),
    re.compile(r"git_push rejected"),
    re.compile(r"\[RATE_LIMIT\] Throttled"),
    re.compile(r"Ошибка отправки в Victoria"),
    # visual-search 404 when nomic is not on the probed host.
    re.compile(r"Ollama embed failed(?::| after)"),
    re.compile(r'model ["\']nomic-embed-text["\'] not found'),
    re.compile(r"\[OLLAMA-DIRECT\] Failed to call Ollama"),
    re.compile(r"\[DISTILLATION\] Failed to get response"),
    re.compile(r"\[DISTILLATION\] Failed to parse wisdom"),
    re.compile(r"server busy, please try again"),
    # Redis UDS flap: worker/watchdog reconnect, not a code patch.
    re.compile(r"Connection closed by server"),
    re.compile(r"Error 111 connecting to"),
    re.compile(r"\[FALLBACK\] Max fallback attempts reached"),
    # Nightly WARNING, not a crash. Bare TimeoutError must not open a task.
    re.compile(r"ai_core audit failed/timeout"),
    re.compile(r"TimeoutError\(\)"),
    # Worker ops logged at ERROR: recovery/auction/breaker are not incidents.
    re.compile(r"\[RESURRECTION\] (?!Recovery failed)"),
    re.compile(r"🏆 \[AUCTION\].*WON task"),
    re.compile(r"\[HEARTBEAT\] Loop failed.*Lost task own"),
    re.compile(r"\[LOOP-BREAKER\]"),
    re.compile(r'role "postgres" does not exist'),
    # Agent-loop / echo, not a crash in unprotected src/*.py.
    re.compile(r"Инструмент write_file не найден"),
    re.compile(r"\bNORM_IN\b"),
    re.compile(r"(?:Мысль|Результат|Msg:).*TypeError:"),
    re.compile(r"FileNotFoundError(?!:)"),
    re.compile(r"RECURSION-STOP"),
    re.compile(r"idle-in-transaction"),
    re.compile(r"\[SMART_AGENT\] response=None"),
    re.compile(r"\[DNA-INJ\].*откат"),
    # Evolution sanity reject is the gate working, not an incident to /run.
    re.compile(r"\[EEVOL\] sanity gate rejected"),
    # Wrapper logs empty Exception/TimeoutError(); cycle still returns True.
    re.compile(r"\[EVOLUTION\] Ошибка эволюции экспертов:\s*$"),
    re.compile(r"llama-server process no longer running"),
    re.compile(r"Node Mac Studio \(Ollama\) returned HTTP 500"),
    re.compile(r"JSONDecodeError"),
    re.compile(r"Найдите неочевидную связь между двумя фактами"),
    re.compile(r"\[JUDGE-GATE\].*score="),
    re.compile(r"контекст ERROR"),
    re.compile(r"ERROR нужно разобрать"),
    re.compile(r"\[VERONICA\] Ошибка: ReadTimeout"),
    re.compile(r'"[^"]*ERROR[^"]*\?"'),
    re.compile(r"Task was destroyed but it is pending"),
    re.compile(r"Error parsing recruitment output"),
]

try:
    from source_guard import PROTECTED_SOURCE_PREFIXES as _PROTECTED_PREFIXES
except ImportError:  # pragma: no cover — same prefixes as source_guard
    _PROTECTED_PREFIXES = (
        "knowledge_os/app/",
        "src/agents/",
        "backend/app/",
        "src/api/",
        "src/core/",
        "src/middleware/",
        "knowledge_os/scripts/",
    )

_FILE_IN_LOG = re.compile(
    r"""(?:File\s+")([^"]+\.py)|(?:/workspace/atra-web-ide/|/app/)([^\s:"']+\.py)""",
    re.I,
)
_NOISE_MARKERS = (
    "[SOURCE_GUARD]",
    "SOURCE_GUARD:",
    "git_push rejected",
    "[RATE_LIMIT] Throttled",
    "Ошибка отправки в Victoria",
    "nomic-embed-text",
    "connection closed by server",
    "error 111 connecting to",
    'column "tokens_used" does not exist',
    "NORM_IN",
    "Инструмент write_file не найден",
    "msg: typeerror:",
    "RECURSION-STOP",
)
_RUNBOOK_MARKERS = (
    "connection refused",
    "connectionrefusederror",
    "server busy",
    "out of memory",
    "out-of-memory",
    "oom-kill",
    "sigkill",
    "connection closed by server",
    "error 111 connecting",
)
_PATCH_TYPES = frozenset(
    {
        "TypeError",
        "SyntaxError",
        "NameError",
        "ImportError",
        "ModuleNotFoundError",
        "AttributeError",
        "KeyError",
        "IndentationError",
    }
)


def extract_code_path(message: str) -> str:
    """Путь .py из traceback, без корня workspace/app."""
    if not message:
        return ""
    m = _FILE_IN_LOG.search(message)
    if not m:
        return ""
    raw = (m.group(1) or m.group(2) or "").replace("\\", "/")
    for prefix in ("/workspace/atra-web-ide/", "/app/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
    return raw.lstrip("/")


def _is_protected_code_path(path: str) -> bool:
    normalized = (path or "").replace("\\", "/").lstrip("/")
    if not normalized:
        return False
    blob = f"/{normalized}"
    return any(f"/{prefix}" in blob for prefix in _PROTECTED_PREFIXES)


def classify_scanner_incident(container: str, error: Dict) -> str:
    """noise | runbook | human | patch. Default human: no file = no write."""
    msg = str((error or {}).get("message") or "")
    et = str((error or {}).get("type") or "")
    low = msg.lower()
    path = extract_code_path(msg)
    if any(m.lower() in low for m in _NOISE_MARKERS):
        return "noise"
    if et == "UNKNOWN" and "filenotfounderror" in low and not path:
        return "noise"
    if any(m in low for m in _RUNBOOK_MARKERS):
        return "runbook"
    if path and _is_protected_code_path(path):
        return "human"
    if path and (et in _PATCH_TYPES or any(t in msg for t in _PATCH_TYPES)):
        return "patch"
    return "human"


_EVIDENCE = (
    "Evidence: command, output, PASS or FAIL, untested. "
    "No «готово» without those four."
)

_HUMAN_BLOCKED_TOOLS = (
    "write_file",
    "apply_patch",
    "git_push",
    "run_terminal_cmd",
    "ssh_run",
    "git_add",
    "git_commit",
    "git_branch_create",
    "git_pr_create",
)
_PATCH_BLOCKED_TOOLS = (
    "git_push",
    "git_status",
    "git_diff",
    "git_log",
)


def blocked_tools_for_scanner_class(klass: str) -> list:
    """Tools /run must not offer. Lookup slave of classify; no consilium."""
    k = (klass or "").strip().lower()
    if k in ("human", "runbook"):
        return list(_HUMAN_BLOCKED_TOOLS)
    if k == "patch":
        return list(_PATCH_BLOCKED_TOOLS)
    return []


_HANDOFF_LINE = re.compile(r"HANDOFF:\s*@?", re.IGNORECASE)


def scanner_patch_handoff_rejected(klass: str, output: str) -> bool:
    """Patch class must write_file or fail — not delegate with HANDOFF."""
    if (klass or "").strip().lower() != "patch":
        return False
    return bool(_HANDOFF_LINE.search(output or ""))


def scanner_class_forces_direct(klass: str) -> bool:
    """Patch writes via agent.run tools. Enhanced swarm only HANDOFFs."""
    return (klass or "").strip().lower() == "patch"


def build_scanner_goal(container: str, error: Dict, klass: str, code_path: str = "") -> str:
    """Goal for /run: no consilium triggers, no default 'исправь'."""
    typ = (error or {}).get("type") or "?"
    msg = str((error or {}).get("message") or "")[:160]
    head = f"[LOG_SCANNER] class={klass} container={container} type={typ}."
    if klass == "runbook":
        return (
            f"{head} Ops signal, not a code change. "
            f"If a known runbook exists (pin/kickstart), name it. Else escalate to human. Msg: {msg}"
        )
    if klass == "patch":
        return (
            f"{head} file={code_path}. {_EVIDENCE} Propose a patch only via write_file with SOURCE_GUARD. "
            f"Do not call autonomous-code. Do not git_push. Do not git_status/git_diff/git_log. "
            f"Do not HANDOFF. Do not touch src/agents. Msg: {msg}"
        )
    return (
        f"{head} Do not write files. {_EVIDENCE} "
        f"Short: what broke and whether a human is needed. Msg: {msg}"
    )


def scanner_run_payload(
    container: str, error: Dict, klass: str, code_path: str = ""
) -> Dict:
    """POST /run body: async accept, no sync 30s hang."""
    return {
        "goal": build_scanner_goal(container, error, klass, code_path),
        "async_mode": True,
        "scanner_class": klass,
        "context": {
            "source": "log_scanner",
            "class": klass,
            "code_path": code_path,
            "container": container,
            "error_type": error["type"],
            "error_message": error["message"],
            "timestamp": error["timestamp"],
        },
    }


# Containers to never scan (avoid self-referential loops)
SKIP_CONTAINERS = {
    "log-scanner",
    "victoria-medic",
}

# Dedup window: don't report same error in same container within N seconds
DEDUP_WINDOW = int(os.getenv("LOG_SCANNER_DEDUP_WINDOW", "21600"))

# Max history per container
MAX_HISTORY = 100


class ErrorDeduplicator:
    """Дедупликация ошибок — не спамить одну и ту же ошибку.

    История персистентна (JSON-файл): рестарт сканера больше не сбрасывает
    дедуп и не плодит дубли задач по тем же ошибкам контейнеров.
    """

    def __init__(self, window_seconds: int = 300, state_path: Optional[str] = None):
        self.window = window_seconds
        self.state_path = state_path or os.getenv(
            "LOG_SCANNER_DEDUP_STATE", "/tmp/log_scanner_dedup.json"
        )
        self.history: Dict[str, List[float]] = defaultdict(list)
        self._load()

    def is_duplicate(self, container: str, error_hash: str) -> bool:
        """Проверить, была ли уже такая ошибка недавно."""
        key = f"{container}:{error_hash}"
        now = time.time()

        # Очистить старые записи
        self.history[key] = [t for t in self.history[key] if now - t < self.window]

        if self.history[key]:
            return True

        self.history[key].append(now)
        self._save()
        return False

    def _load(self):
        try:
            with open(self.state_path) as f:
                raw = json.load(f)
            now = time.time()
            for key, stamps in raw.items():
                fresh = [t for t in stamps if now - t < self.window]
                if fresh:
                    self.history[key] = fresh
        except (OSError, ValueError):
            pass

    def _save(self):
        try:
            with open(self.state_path, "w") as f:
                json.dump({k: v for k, v in self.history.items() if v}, f)
        except OSError:
            pass

    def cleanup(self):
        """Очистить историю старше window."""
        self._save()
        now = time.time()
        keys_to_delete = []
        for key, timestamps in self.history.items():
            self.history[key] = [t for t in timestamps if now - t < self.window]
            if not self.history[key]:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del self.history[key]


class LogScanner:
    """Сканер логов Docker контейнеров."""

    # Rate limiting: max 5 tasks per hour to Victoria
    MAX_TASKS_PER_HOUR = 5
    RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds

    def __init__(self):
        self.dedup = ErrorDeduplicator(DEDUP_WINDOW)
        self.last_scan: Dict[str, str] = {}  # container -> last timestamp
        self.running = False
        self.error_count = 0
        self.scan_count = 0
        self._task_timestamps: List[float] = []  # For rate limiting

    def get_containers(self) -> List[str]:
        """Получить список контейнеров для мониторинга."""
        if WATCH_CONTAINERS and WATCH_CONTAINERS != [""]:
            return [c.strip() for c in WATCH_CONTAINERS if c.strip()]

        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            containers = result.stdout.strip().split("\n")
            # Skip containers that would cause self-referential loops
            return [c for c in containers if c not in SKIP_CONTAINERS]
        except Exception as e:
            logger.error(f"Failed to get containers: {e}")
            return []

    def get_container_logs(self, container: str, since: Optional[str] = None) -> str:
        """Получить логи контейнера."""
        try:
            cmd = ["docker", "logs", "--tail", "100"]
            if since:
                cmd.extend(["--since", since])
            cmd.append(container)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.stdout + result.stderr
        except Exception as e:
            logger.debug(f"Failed to get logs for {container}: {e}")
            return ""

    def extract_error(self, line: str) -> Optional[Dict]:
        """Извлечь информацию об ошибке из строки лога."""
        ll = line.lower()
        # Fast skip for explicit non-error structured levels
        if "level=info" in ll or "level=debug" in ll:
            return None

        # Skip ignored patterns
        for pattern in IGNORE_PATTERNS:
            if pattern.search(line):
                return None

        # Check error patterns
        for pattern in ERROR_PATTERNS:
            if pattern.search(line):
                # Extract error type
                error_type = "UNKNOWN"
                if "Traceback" in line:
                    error_type = "TRACEBACK"
                elif re.search(r"(error|exception):", line, re.IGNORECASE):
                    match = re.search(r"(\w*(?:Error|Exception))", line)
                    if match:
                        error_type = match.group(1)
                    else:
                        error_type = "EXCEPTION"
                elif re.search(r"\berror\b", line, re.IGNORECASE):
                    error_type = "LOG_ERROR"
                elif "killed" in line.lower():
                    error_type = "PROCESS_KILLED"

                return {
                    "type": error_type,
                    "message": line.strip()[:500],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        return None

    def make_error_hash(self, container: str, error: Dict) -> str:
        """Создать хеш ошибки для дедупликации."""
        # Normalize dynamic log noise (timestamps, UUIDs, PIDs, request ids)
        # so identical incidents deduplicate within the same time window.
        msg = str(error.get("message", "")).lower()
        patterns = (
            # 2026-09-04 03:33:44.169 or ISO-like
            r"\b\d{4}-\d{2}-\d{2}[ t]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:z|[+\-]\d{2}:?\d{2})?\b",
            # UUIDs
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            # [53415], request ids and similar counters
            r"\[\d+\]",
            r"\btask\s+[0-9a-f]{8,}\b",
            # collapse standalone numbers to avoid per-event cardinality spikes
            r"\b\d+\b",
        )
        for pat in patterns:
            msg = re.sub(pat, "<n>", msg)
        msg = re.sub(r"\s+", " ", msg).strip()
        key = f"{error.get('type', 'UNKNOWN')}:{msg[:180]}"
        return hashlib.sha1(key.encode("utf-8", errors="ignore")).hexdigest()

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits. Returns True if OK to send."""
        now = time.time()
        # Remove timestamps older than window
        self._task_timestamps = [
            ts for ts in self._task_timestamps if now - ts < self.RATE_LIMIT_WINDOW
        ]
        if len(self._task_timestamps) >= self.MAX_TASKS_PER_HOUR:
            logger.warning(
                f"[RATE_LIMIT] Throttled: {len(self._task_timestamps)}/{self.MAX_TASKS_PER_HOUR} "
                f"tasks in last hour. Skipping Victoria notification."
            )
            return False
        self._task_timestamps.append(now)
        return True

    async def send_to_victoria(
        self,
        container: str,
        error: Dict,
        *,
        klass: str = "human",
        code_path: str = "",
    ) -> bool:
        """Отправить ошибку в Victoria через event bus."""
        if klass == "noise":
            return False
        # Rate limit check
        if not self._check_rate_limit():
            return False

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # [v149.55d] без «Проанализируй» — consilium.
                # [v150.89] без «Исправь» — класс сигнала, не автопатч.
                payload = scanner_run_payload(container, error, klass, code_path)

                response = await client.post(
                    f"{VICTORIA_URL}/run",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code in (200, 202):
                    result = response.json() if response.content else {}
                    task_id = result.get("task_id") or result.get("id") or "unknown"
                    logger.info(
                        f"✅ [LOG_SCANNER] Отправлено в Victoria: {container}/{error['type']} "
                        f"→ task_id={task_id} http={response.status_code}"
                    )
                    return True
                else:
                    logger.warning(
                        f"⚠️ [LOG_SCANNER] Victoria ответила {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    return False

        except Exception as e:
            logger.error(
                "❌ [LOG_SCANNER] Ошибка отправки в Victoria: %s: %r",
                type(e).__name__,
                e,
            )
            return False

    async def scan_container(self, container: str) -> int:
        """Сканировать один контейнер. Возвращает кол-во новых ошибок."""
        logs = self.get_container_logs(container, since=self.last_scan.get(container))

        if not logs:
            return 0

        # Update last scan timestamp
        self.last_scan[container] = datetime.now(timezone.utc).isoformat()

        errors_found = 0
        for line in logs.split("\n"):
            if not line.strip():
                continue

            error = self.extract_error(line)
            if not error:
                continue

            # Dedup
            error_hash = self.make_error_hash(container, error)
            if self.dedup.is_duplicate(container, error_hash):
                continue

            klass = classify_scanner_incident(container, error)
            code_path = extract_code_path(error.get("message") or "")
            if klass == "noise":
                continue

            # New error found!
            errors_found += 1
            self.error_count += 1

            logger.warning(
                f"🔍 [LOG_SCANNER] class={klass} {container}: {error['type']}: {error['message'][:100]}"
            )

            await self.send_to_victoria(container, error, klass=klass, code_path=code_path)

        return errors_found

    async def scan_all(self) -> int:
        """Сканировать все контейнеры. Возвращает кол-во новых ошибок."""
        containers = self.get_containers()
        total_errors = 0

        for container in containers:
            try:
                errors = await self.scan_container(container)
                total_errors += errors
            except Exception as e:
                logger.debug(f"Error scanning {container}: {e}")

        self.scan_count += 1

        # Periodic cleanup
        if self.scan_count % 10 == 0:
            self.dedup.cleanup()

        try:
            _SCANNER_SNAP.parent.mkdir(parents=True, exist_ok=True)
            _SCANNER_SNAP.write_text(
                json.dumps(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "scan": self.scan_count,
                        "new_errors": int(total_errors),
                        "total_errors": int(self.error_count),
                    }
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("scanner snapshot write failed", exc_info=True)

        return total_errors

    async def run(self):
        """Главный цикл сканера."""
        self.running = True
        # On startup, begin from "now" to avoid replaying historical logs after restarts.
        now_iso = datetime.now(timezone.utc).isoformat()
        for container in self.get_containers():
            self.last_scan.setdefault(container, now_iso)
        logger.info(
            f"🚀 [LOG_SCANNER] Запущен. Интервал: {SCAN_INTERVAL}s, "
            f"Контейнеры: {WATCH_CONTAINERS or 'all'}"
        )

        while self.running:
            try:
                errors = await self.scan_all()
                if errors > 0:
                    logger.info(
                        f"📊 [LOG_SCANNER] Scan #{self.scan_count}: "
                        f"{errors} новых ошибок (всего: {self.error_count})"
                    )
            except Exception as e:
                logger.error(f"❌ [LOG_SCANNER] Ошибка в цикле: {e}")

            await asyncio.sleep(SCAN_INTERVAL)

    def stop(self):
        """Остановить сканер."""
        self.running = False
        logger.info("🛑 [LOG_SCANNER] Остановлен")


async def main():
    """Точка входа."""
    scanner = LogScanner()
    try:
        await scanner.run()
    except KeyboardInterrupt:
        scanner.stop()


if __name__ == "__main__":
    asyncio.run(main())
