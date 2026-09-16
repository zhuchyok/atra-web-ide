#!/usr/bin/env python3
"""
Deferred + async TTC alerts → Telegram (polling-монитор).

Рабочий канал: прямой poll → TelegramAlerter. Grafana AM→Telegram в этом runtime не стреляет.

Запуск:  python scripts/tg_deferred_alerts.py --threshold 10 --interval 300
Разово:  python scripts/tg_deferred_alerts.py --once
Тест:    python scripts/tg_deferred_alerts.py --test
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
VICTORIA_METRICS_URL = os.getenv("VICTORIA_METRICS_URL", "http://127.0.0.1:8010/metrics")
TTC_P95_THRESHOLD = float(os.getenv("VICTORIA_ASYNC_TTC_P95_SEC", "60"))
TTC_MIN_SAMPLES = int(os.getenv("VICTORIA_ASYNC_TTC_MIN_SAMPLES", "5"))
STATE_FILE = os.getenv("TG_DEFERRED_STATE", "/tmp/tg_deferred_alerts.state")
RESET_AFTER_SEC = 4 * 3600


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        import json as _j
        with open(STATE_FILE) as fh:
            return _j.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def _save_state(state: dict) -> None:
    import json as _j
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as fh:
        _j.dump(state, fh)


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


def fetch_async_ttc() -> tuple[float | None, float | None, int, float, int]:
    """p50, p95, samples, inflight_max, inflight_n from Victoria /metrics."""
    import urllib.request
    try:
        with urllib.request.urlopen(VICTORIA_METRICS_URL, timeout=5) as r:
            text = r.read().decode()
    except Exception as e:  # noqa: BLE001
        print(f"[ttc poll error] {e}")
        return None, None, 0, 0.0, 0
    p50 = p95 = None
    samples = 0
    inflight_max = 0.0
    inflight_n = 0
    for line in text.splitlines():
        if line.startswith("#") or " " not in line:
            continue
        name, _, value = line.partition(" ")
        if name == "victoria_async_ttc_p50_seconds":
            p50 = float(value)
        elif name == "victoria_async_ttc_p95_seconds":
            p95 = float(value)
        elif name == "victoria_async_ttc_samples":
            samples = int(float(value))
        elif name == "victoria_async_inflight_max_elapsed_seconds":
            inflight_max = float(value)
        elif name == "victoria_async_inflight":
            inflight_n = int(float(value))
    return p50, p95, samples, inflight_max, inflight_n


async def send_tg(text: str) -> bool:
    from telegram_alerter import get_telegram_alerter

    alerter = get_telegram_alerter()
    return await alerter.send_alert(text, priority="high", source="Deferred Monitor")


async def run_once(threshold: float) -> bool:
    value = await fetch_metric()
    if value is None:
        return False
    state = _load_state()
    already = state.get("fired_at", 0)
    fresh_enough = time.time() - already < RESET_AFTER_SEC
    if value > threshold and not fresh_enough:
        ok = await send_tg(
            f"🚨 Порог эскалаций превышен\n\n{METRIC} = {int(value)} (порог {int(threshold)})\n"
            "Проверьте дашборд Knowledge OS — задачи и last_error."
        )
        if ok:
            state["fired_at"] = time.time()
            state["value"] = value
            _save_state(state)
            print(f"[alert sent] value={value}")
            return True
    else:
        print(f"[ok] value={value} (threshold={threshold})")
    return False


async def run_ttc_once(threshold: float = TTC_P95_THRESHOLD, min_samples: int = TTC_MIN_SAMPLES) -> bool:
    p50, p95, samples, inflight_max, inflight_n = fetch_async_ttc()
    if p95 is None:
        print("[ttc] metrics unavailable")
        return False
    state = _load_state()
    p95_over = samples >= min_samples and p95 > threshold
    hung_over = inflight_max > threshold
    # [v4.2-QUALITY] отдельные дедуп-ключи: ложный p95-page не глушит hung-алерт
    now = time.time()
    fresh_p95 = now - state.get("ttc_fired_at", 0) < RESET_AFTER_SEC
    fresh_hung = now - state.get("hung_fired_at", 0) < RESET_AFTER_SEC
    over = (p95_over and not fresh_p95) or (hung_over and not fresh_hung)
    print(
        f"[ttc] p50={p50} p95={p95} samples={samples} "
        f"inflight_max={inflight_max} inflight_n={inflight_n} "
        f"threshold={threshold} min_samples={min_samples} over={over}"
    )
    if over and not fresh_enough:
        ok = await send_tg(
            "⏱ Async TTC SLA\n\n"
            f"p95={p95:.1f}s samples={samples} p50={p50:.1f}s\n"
            f"inflight_max={inflight_max:.1f}s n={inflight_n}\n"
            f"порог {threshold:.0f}s (p95_over={p95_over} hung={hung_over})\n"
            "Это accept→completed / зависание processing, не latency POST 202."
        )
        if ok:
            now2 = time.time()
            if p95_over and not fresh_p95:
                state["ttc_fired_at"] = now2
            if hung_over and not fresh_hung:
                state["hung_fired_at"] = now2
            state["ttc_p95"] = p95
            state["ttc_samples"] = samples
            _save_state(state)
            print(f"[ttc alert sent] p95={p95}")
            return True
    return False


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=10)
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--once", action="store_true", help="один проход deferred+ttc без цикла")
    parser.add_argument("--test", action="store_true", help="разово отослать тестовый алерт")
    args = parser.parse_args()

    if args.test:
        v = await send_tg(
            "🧪 Тест deferred-монитора (фейковое превышение порога). Полная цепочка: poller работает, канала живая."
        )
        print("test sent:", v)
        return

    async def _tick() -> None:
        await run_once(args.threshold)
        await run_ttc_once()

    if args.once:
        await _tick()
        return

    while True:
        try:
            await _tick()
        except Exception as e:  # noqa: BLE001
            print(f"[loop error] {e}")
        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    asyncio.run(main())
