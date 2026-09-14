"""
Victoria Medic — watchdog: детект сбоев Виктории.

Источники сигнала:
1. Health-зонд GET /health каждые HEALTH_INTERVAL сек (3 провала подряд -> SERVICE_DOWN)
2. Стрим docker-логов victoria-agent по сигнатурам
3. Canary GET /health раз в CANARY_INTERVAL сек (зависание -> SERVICE_HUNG)
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

VICTORIA_URL = "http://victoria-agent:8000"
HEALTH_INTERVAL = 15
CANARY_INTERVAL = 900
CANARY_TIMEOUT = 60
HEALTH_TIMEOUT = 10
DOWN_THRESHOLD = 3

SIGNATURES = [
    (re.compile(r"LLM call failed: No module named '?([\w.]+)'?"), "BROKEN_IMPORT"),
    (re.compile(r"LLM soft-timeout"), "LLM_TIMEOUT"),
    (re.compile(r"Ошибка вызова LLM"), "LLM_ERROR"),
    (re.compile(r"OOM|OutOfMemory|memory error|oom-kill"), "OOM"),
    (re.compile(r"Traceback \(most recent call last\)"), "UNKNOWN_ERROR"),
]

# Patterns that indicate benign/handled errors — skip these
BENIGN_PATTERNS = [
    re.compile(r"CancelledError"),
    re.compile(r"_GatheringFuture exception was never retrieved"),
    re.compile(r"asyncio\.exceptions\.cancellederror", re.IGNORECASE),
    re.compile(r"future:.*exception=cancellederror", re.IGNORECASE),
    re.compile(r"sync safe mode failed"),
    re.compile(r"background hard-timeout"),
]


@dataclass
class Incident:
    kind: str
    detail: str
    ts: float = field(default_factory=time.time)


OnIncident = Callable[[Incident], Awaitable[None]]


class Watchdog:
    def __init__(self, on_incident: OnIncident, victoria_url: str = VICTORIA_URL):
        self.on_incident = on_incident
        self.victoria_url = victoria_url
        self._consecutive_failures = 0
        self._stop = False

    async def health_probe(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT) as client:
                r = await client.get(f"{self.victoria_url}/health")
                return r.status_code == 200
        except Exception:
            return False

    async def canary_run(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=CANARY_TIMEOUT) as client:
                r = await client.get(f"{self.victoria_url}/health")
                if r.status_code != 200:
                    return False
                try:
                    payload = r.json()
                    status = str(payload.get("status", "")).lower()
                    return status in ("ok", "healthy", "up")
                except Exception:
                    # If health endpoint is non-json but 200, treat as alive.
                    return True
        except Exception:
            return False

    def classify_line(self, line: str) -> Optional[Incident]:
        # Skip benign errors (asyncio CancelledError from timeouts, etc.)
        for bp in BENIGN_PATTERNS:
            if bp.search(line):
                return None
        for pattern, kind in SIGNATURES:
            m = pattern.search(line)
            if m:
                return Incident(kind=kind, detail=m.group(0)[:200])
        return None

    async def _health_loop(self):
        while not self._stop:
            ok = await self.health_probe()
            if ok:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1
                logger.warning("health fail #%d", self._consecutive_failures)
                if self._consecutive_failures == DOWN_THRESHOLD:
                    await self.on_incident(
                        Incident(kind="SERVICE_DOWN", detail="health probe failed x3")
                    )
            await asyncio.sleep(HEALTH_INTERVAL)

    async def _canary_loop(self):
        while not self._stop:
            await asyncio.sleep(CANARY_INTERVAL)
            if not await self.health_probe():
                continue
            if not await self.canary_run():
                await self.on_incident(
                    Incident(kind="SERVICE_HUNG", detail="canary /run timeout or error")
                )

    async def _log_stream(self):
        import queue
        import threading

        import docker

        q: queue.Queue = queue.Queue(maxsize=1000)

        def _reader():
            while not self._stop:
                try:
                    client = docker.from_env()
                    container = client.containers.get("victoria-agent")
                    for chunk in container.logs(
                        stream=True, follow=True, timestamps=False, tail=0
                    ):
                        if self._stop:
                            return
                        try:
                            q.put_nowait(chunk.decode("utf-8", errors="replace"))
                        except queue.Full:
                            pass
                except Exception as e:
                    logger.error("log stream error: %s", e)
                time.sleep(5)

        threading.Thread(target=_reader, daemon=True).start()

        while not self._stop:
            try:
                line = await asyncio.to_thread(q.get, timeout=1.0)
            except Exception:
                continue
            incident = self.classify_line(line)
            if incident:
                await self.on_incident(incident)

    async def run(self):
        await asyncio.gather(
            self._health_loop(),
            self._canary_loop(),
            self._log_stream(),
        )

    def stop(self):
        self._stop = True
