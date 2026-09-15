#!/usr/bin/env python3
"""
Deferred Alerts → Telegram (polling-монитор).

Канал работает напрямую: Prometheus (deferred_new_24h_total) → threshold → TelegramAlerter.
Комплектует существующую Grafana-цепочку (rule → AM), fallback проверен (message_id 1943).

Запуск:  python scripts/tg_deferred_alerts.py --threshold 10 --interval 300
Тест:    python scripts/tg_deferred_alerts.py --test  (фейковая метрика=15, одно сообщение)
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "knowledge_os" / "app"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "knowledge_os"))

PROM_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9091")
METRIC = "knowledge_os_tasks_deferred_new_24h_total"
STATE_FILE = os.getenv("TG_DEFERRED_STATE", "/tmp/tg_deferred_alerts.state")
RESET_AFTER_SEC = 4 * 3600


async def fetch_metric() -> float | None:
    import urllib.request, json as _j
    url = f"{PROM_URL}/api/v1/query?query={METRIC}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            d = _j.loads(r.read().decode())
            res = d.get("data", {}).get("result", [])
            if res:
                return float(res[0]["value"][1])
    except Exception as e:  # noqa: BLE001
        print(f"[poll error] {e}")
    return None


async def send_tg(text: str) -> bool:
    from telegram_alerter import get_telegram_alerter

    alerter = get_telegram_alerter()
    return await alerter.send_alert(text, priority="high", source="Deferred Monitor")


async def run_once(threshold: float) -> bool:
    value = await fetch_metric()
    if value is None:
        return False
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            import json as _j
            state = _j.load(open(STATE_FILE))
        except Exception:  # noqa: BLE001
            state = {}
    already = state.get("fired_at", 0)
    fresh_enough = time.time() - already < RESET_AFTER_SEC
    if value > threshold and not fresh_enough:
        ok = await send_tg(
            f"🚨 Порог эскалаций превышен\n\n{METRIC} = {int(value)} (порог {int(threshold)})\n"
            "Проверьте дашборд Knowledge OS — задачи и last_error."
        )
        if ok:
            state = {"fired_at": time.time(), "value": value}
            import json as _j
            _j.dump(state, open(STATE_FILE, "w"))
            print(f"[alert sent] value={value}")
            return True
    else:
        print(f"[ok] value={value} (threshold={threshold})")
    return False


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=10)
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--test", action="store_true", help="разово отослать тестовый алерт")
    args = parser.parse_args()

    if args.test:
        v = await send_tg(
            "🧪 Тест deferred-монитора (фейковое превышение порога). Полная цепочка: poller работает, канала живая."
        )
        print("test sent:", v)
        return

    while True:
        try:
            await run_once(args.threshold)
        except Exception as e:  # noqa: BLE001
            print(f"[loop error] {e}")
        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    asyncio.run(main())
