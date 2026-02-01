"""
Telegram alerts для мониторинга (6.2 плана Resilient Task Execution).
Отправка уведомлений при высоком deferred/failed ratio.
С cooldown 1 час, чтобы не спамить (мировые практики: rate limit алертов).
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_TOKEN", "")
TELEGRAM_ALERT_CHAT_ID = os.getenv("TELEGRAM_ALERT_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_USER_ID", "")
ALERT_COOLDOWN_SEC = int(os.getenv("TELEGRAM_ALERT_COOLDOWN_SEC", "3600"))  # 1 час
_ALERT_STATE_FILE = Path("/tmp/telegram_task_alert_state.json")


def _load_alert_state() -> dict:
    try:
        if _ALERT_STATE_FILE.exists():
            with open(_ALERT_STATE_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.debug("telegram_alerts: load state %s", e)
    return {}


def _save_alert_state(state: dict) -> None:
    try:
        with open(_ALERT_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.debug("telegram_alerts: save state %s", e)


def _can_send_alert(alert_type: str) -> bool:
    state = _load_alert_state()
    last = state.get(alert_type, 0)
    return (time.time() - last) >= ALERT_COOLDOWN_SEC


def _mark_alert_sent(alert_type: str) -> None:
    state = _load_alert_state()
    state[alert_type] = time.time()
    _save_alert_state(state)


async def send_task_execution_alert(deferred_ratio: float, failed_ratio: float, details: str) -> bool:
    """
    Отправка алерта в Telegram при высоком deferred/failed ratio.
    Returns True если отправлено, False если пропущено (cooldown или нет настроек).
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ALERT_CHAT_ID:
        return False
    alert_type = "task_execution_high_deferred_failed"
    if not _can_send_alert(alert_type):
        return False
    text = (
        "⚠️ Task Execution Alert\n\n"
        f"Высокий deferred/failed ratio за последние 24ч:\n"
        f"• deferred_to_human: {deferred_ratio:.0%}\n"
        f"• failed: {failed_ratio:.0%}\n\n"
        f"Детали: {details}\n\n"
        "Рекомендуется проверить доступность AI агентов и логи Smart Worker."
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_ALERT_CHAT_ID, "text": text}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                _mark_alert_sent(alert_type)
                logger.info("Telegram alert sent: task_execution")
                return True
            logger.warning("Telegram alert failed: %s %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("Telegram alert error: %s", e)
    return False
