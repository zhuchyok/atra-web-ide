"""
Log Scanner — мониторинг Docker логов и отправка ошибок в Victoria.

Сканирует логи всех контейнеров, детектит ошибки, дедуплицирует,
и отправляет в Victoria через event bus для автономного исправления.

Запуск: python -m app.medic.log_scanner
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import time
import hashlib
from collections import defaultdict
from datetime import datetime, timezone
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

# Containers to monitor (empty = all)
WATCH_CONTAINERS = os.getenv("LOG_SCANNER_CONTAINERS", "").split(",")

# Error patterns to detect
ERROR_PATTERNS = [
    re.compile(r"\b(ERROR|CRITICAL|FATAL)\b", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"Exception:|Error:|RuntimeError:|ValueError:|TypeError:"),
    re.compile(r"raise \w+Error"),
    re.compile(r"module.*not found|ImportError|ModuleNotFoundError"),
    re.compile(r"connection refused|ConnectionRefusedError"),
    re.compile(r"timeout|TimeoutError|ReadTimeout"),
    re.compile(r"OOM|OutOfMemory|memory error"),
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
    re.compile(r'column "last_exec_time" does not exist'),
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
]

# Containers to never scan (avoid self-referential loops)
SKIP_CONTAINERS = {
    "log-scanner",
    "victoria-medic",
}

# Dedup window: don't report same error in same container within N seconds
DEDUP_WINDOW = int(os.getenv("LOG_SCANNER_DEDUP_WINDOW", "300"))

# Max history per container
MAX_HISTORY = 100


class ErrorDeduplicator:
    """Дедупликация ошибок — не спамить одну и ту же ошибку."""

    def __init__(self, window_seconds: int = 300):
        self.window = window_seconds
        self.history: Dict[str, List[float]] = defaultdict(list)

    def is_duplicate(self, container: str, error_hash: str) -> bool:
        """Проверить, была ли уже такая ошибка недавно."""
        key = f"{container}:{error_hash}"
        now = time.time()

        # Очистить старые записи
        self.history[key] = [
            t for t in self.history[key] if now - t < self.window
        ]

        if self.history[key]:
            return True

        self.history[key].append(now)
        return False

    def cleanup(self):
        """Очистить историю старше window."""
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
            ts for ts in self._task_timestamps
            if now - ts < self.RATE_LIMIT_WINDOW
        ]
        if len(self._task_timestamps) >= self.MAX_TASKS_PER_HOUR:
            logger.warning(
                f"[RATE_LIMIT] Throttled: {len(self._task_timestamps)}/{self.MAX_TASKS_PER_HOUR} "
                f"tasks in last hour. Skipping Victoria notification."
            )
            return False
        self._task_timestamps.append(now)
        return True

    async def send_to_victoria(self, container: str, error: Dict) -> bool:
        """Отправить ошибку в Victoria через event bus."""
        # Rate limit check
        if not self._check_rate_limit():
            return False

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Send via /run endpoint with error context
                payload = {
                    "goal": f"[LOG_SCANNER] Обнаружена ошибка в контейнере {container}. "
                            f"Тип: {error['type']}. "
                            f"Сообщение: {error['message'][:200]}. "
                            f"Проанализируй и исправь если возможно.",
                    "context": {
                        "source": "log_scanner",
                        "container": container,
                        "error_type": error["type"],
                        "error_message": error["message"],
                        "timestamp": error["timestamp"],
                    },
                }

                response = await client.post(
                    f"{VICTORIA_URL}/run",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    result = response.json()
                    task_id = result.get("task_id", "unknown")
                    logger.info(
                        f"✅ [LOG_SCANNER] Отправлено в Victoria: {container}/{error['type']} "
                        f"→ task_id={task_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"⚠️ [LOG_SCANNER] Victoria ответила {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ [LOG_SCANNER] Ошибка отправки в Victoria: {e}")
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

            # New error found!
            errors_found += 1
            self.error_count += 1

            logger.warning(
                f"🔍 [LOG_SCANNER] {container}: {error['type']}: {error['message'][:100]}"
            )

            # Send to Victoria
            await self.send_to_victoria(container, error)

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
