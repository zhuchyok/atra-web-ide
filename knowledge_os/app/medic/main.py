"""
Victoria Medic — главный цикл: классификация, дедупликация, лестница ремонта,
L3 через Веронику, журнал инцидентов, Telegram-уведомления.

Запуск: python -m app.medic.main
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

import httpx

from medic.repair import RepairToolkit, PROTECTED_FILES, APP_DIR
from medic.watchdog import Incident, Watchdog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [MEDIC] %(message)s",
)
logger = logging.getLogger(__name__)

VERONICA_URL = os.getenv("VERONICA_URL", "http://veronica-agent:8000")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh/atra_victoria_curator")
LOG_DIR = Path(os.getenv("MEDIC_LOG_DIR", "/app/logs"))
JOURNAL = LOG_DIR / "victoria_incidents.jsonl"

DEDUP_WINDOW = 600
REPAIR_COOLDOWN = 600
MAX_ATTEMPTS = 3
LAST_GOOD_REFRESH = 600

LADDER = {
    "SERVICE_DOWN": ["L1", "L2", "L3"],
    "SERVICE_HUNG": ["L1", "L2", "L3"],
    "BROKEN_IMPORT": ["L2", "L3"],
    "LLM_TIMEOUT": ["L1", "L2", "L3"],
    "LLM_ERROR": ["L1", "L2", "L3"],
    "OOM": ["L1", "L2", "L3"],
    "UNKNOWN_ERROR": [],  # Benign — just log, no repair (asyncio CancelledError from timeouts)
}


class Medic:
    def __init__(self):
        self.toolkit = RepairToolkit()
        self.watchdog = Watchdog(on_incident=self.on_incident)
        self._last_seen: dict[str, float] = {}
        self._last_repair = 0.0
        self._repairing = False

        # Metrics dashboard
        self.metrics_dashboard = None
        try:
            from app.medic.metrics_dashboard import MetricsDashboard
            self.metrics_dashboard = MetricsDashboard()
        except Exception as e:
            logger.debug("MetricsDashboard not available: %s", e)

    def journal(self, incident: Incident, action: str, result: str):
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(JOURNAL, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "ts": incident.ts,
                            "kind": incident.kind,
                            "detail": incident.detail,
                            "action": action,
                            "result": result,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception as e:
            logger.error("journal write failed: %s", e)

    async def telegram(self, text: str):
        sent = False
        if TG_TOKEN and CHAT_ID:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.post(
                        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                        data={"chat_id": CHAT_ID, "text": text},
                    )
                    sent = r.status_code == 200
            except Exception as e:
                logger.error("telegram failed: %s", e)
        if not sent and NTFY_URL:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        NTFY_URL,
                        content=text.encode("utf-8"),
                        headers={"Title": "Victoria Medic"},
                    )
            except Exception as e:
                logger.error("ntfy failed: %s", e)

    def _dedup(self, incident: Incident) -> bool:
        last = self._last_seen.get(incident.kind, 0.0)
        if time.time() - last < DEDUP_WINDOW:
            return True
        self._last_seen[incident.kind] = time.time()
        return False

    async def on_incident(self, incident: Incident):
        logger.warning("incident: %s — %s", incident.kind, incident.detail)

        # Log incident to metrics dashboard
        if self.metrics_dashboard:
            try:
                await self.metrics_dashboard.log_action(
                    action_type="incident_detected",
                    action_data={
                        "kind": incident.kind,
                        "detail": incident.detail[:500],
                    },
                    status="detected",
                )
            except Exception as e:
                logger.debug("Metrics log incident failed: %s", e)

        if self._dedup(incident):
            logger.info("dedup: skip %s", incident.kind)
            return
        if self._repairing:
            logger.info("already repairing, skip")
            return
        if time.time() - self._last_repair < REPAIR_COOLDOWN:
            logger.info("cooldown active, skip")
            return
        self._repairing = True
        try:
            await self._heal(incident)
        finally:
            self._repairing = False

    async def _heal(self, incident: Incident):
        ladder = LADDER.get(incident.kind, ["L3"])
        if not ladder:
            logger.info("heal %s: no repair needed (benign/known pattern), logging only", incident.kind)
            self.journal(incident, "LOGGED", "benign pattern, no action")
            return
        for attempt, level in enumerate(ladder[:MAX_ATTEMPTS], start=1):
            self._last_repair = time.time()
            logger.info("heal %s: attempt %d/%d (%s)", incident.kind, attempt, len(ladder), level)

            # Log repair attempt
            if self.metrics_dashboard:
                try:
                    await self.metrics_dashboard.log_action(
                        action_type="repair_attempt",
                        action_data={
                            "incident_kind": incident.kind,
                            "level": level,
                            "attempt": attempt,
                        },
                        status="in_progress",
                    )
                except Exception as e:
                    logger.debug("Metrics log repair attempt failed: %s", e)

            ok = False
            if level == "L1":
                ok = await self._do_l1(incident)
            elif level == "L2":
                ok = await self._do_l2(incident)
            elif level == "L3":
                ok = await self._do_l3(incident)

            # Log repair result
            if self.metrics_dashboard:
                try:
                    await self.metrics_dashboard.log_action(
                        action_type="repair_attempt",
                        action_data={
                            "incident_kind": incident.kind,
                            "level": level,
                            "attempt": attempt,
                            "result": "success" if ok else "failed",
                        },
                        status="completed" if ok else "failed",
                    )
                except Exception as e:
                    logger.debug("Metrics log repair result failed: %s", e)

            self.journal(incident, level, "success" if ok else "failed")
            if ok:
                self.toolkit.mark_last_good()
                await self.telegram(
                    f"🩹 Виктория починена (уровень {level}, инцидент {incident.kind})"
                )
                return
        self.journal(incident, "ESCALATED", "all levels failed")
        await self.telegram(
            f"🔴 Викторию не удалось починить автоматически ({incident.kind}). "
            f"Нужен человек. Детали: {incident.detail}"
        )

    async def _do_l1(self, incident: Incident) -> bool:
        self.toolkit.snapshot("pre_l1")
        if not await self.toolkit.restart_victoria():
            return False
        if not await self.toolkit.wait_healthy():
            return False
        return await self.toolkit.canary()

    async def _do_l2(self, incident: Incident) -> bool:
        self.toolkit.snapshot("pre_l2")
        if not self.toolkit.rollback_last_good():
            return False
        if not await self.toolkit.restart_victoria():
            return False
        if not await self.toolkit.wait_healthy():
            return False
        return await self.toolkit.canary()

    async def _do_l3(self, incident: Incident) -> bool:
        self.toolkit.snapshot("pre_l3")
        plan = await self._consult_veronica(incident)
        if not plan:
            return False
        action = plan.get("action")
        logger.info("veronica plan: %s", plan)
        try:
            if action == "restart":
                ok = await self.toolkit.restart_victoria()
            elif action == "rollback":
                ok = self.toolkit.rollback_last_good() and await self.toolkit.restart_victoria()
            elif action == "patch":
                ok = self._apply_patch(plan) and await self.toolkit.restart_victoria()
            else:
                logger.warning("unknown veronica action: %s", action)
                return False
        except Exception as e:
            logger.error("veronica plan execution failed: %s", e)
            return False
        if not ok:
            return False
        if not await self.toolkit.wait_healthy():
            return False
        if await self.toolkit.canary():
            return True
        logger.warning("canary failed after veronica fix, rolling back")
        self.toolkit.rollback_last_good()
        await self.toolkit.restart_victoria()
        return False

    def _apply_patch(self, plan: dict) -> bool:
        name = Path(plan.get("file", "")).name
        content = plan.get("content", "")
        if name not in PROTECTED_FILES or not content:
            logger.warning("patch rejected: file=%s", name)
            return False
        (APP_DIR / name).write_text(content, encoding="utf-8")
        logger.info("patch applied to %s", name)
        return True

    async def _consult_veronica(self, incident: Incident) -> dict | None:
        prompt = (
            "Ты — врач корпорации ATRA. Виктория (агент, порт 8000) сломана.\n"
            f"Инцидент: {incident.kind}\nДетали: {incident.detail}\n"
            f"Защищённые файлы: {', '.join(PROTECTED_FILES)} (в каталоге knowledge_os/app).\n"
            "Проанализируй и верни СТРОГО один JSON без пояснений:\n"
            '{"action": "restart" | "rollback" | "patch", '
            '"file": "<имя файла, только для patch>", '
            '"content": "<полное новое содержимое файла, только для patch>", '
            '"reason": "<краткая причина>"}\n'
            "restart — если сбой временный; rollback — если недавно меняли файлы; "
            "patch — только если точно знаешь исправление."
        )
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.post(f"{VERONICA_URL}/run", json={"goal": prompt})
                if r.status_code != 200:
                    return None
                text = r.json().get("output", "")
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if not m:
                    return None
                return json.loads(m.group(0))
        except Exception as e:
            logger.error("veronica consult failed: %s", e)
            return None

    async def _last_good_refresh_loop(self):
        while True:
            await asyncio.sleep(LAST_GOOD_REFRESH)
            try:
                if await self.watchdog.health_probe() and await self.watchdog.canary_run():
                    self.toolkit.mark_last_good()
            except Exception as e:
                logger.error("last_good refresh failed: %s", e)

    async def run(self):
        self.toolkit.snapshot("startup")
        if await self.watchdog.health_probe():
            self.toolkit.mark_last_good()
        await self.telegram("🩺 victoria-medic запущен и дежурит")
        await asyncio.gather(
            self.watchdog.run(),
            self._last_good_refresh_loop(),
        )


if __name__ == "__main__":
    asyncio.run(Medic().run())
