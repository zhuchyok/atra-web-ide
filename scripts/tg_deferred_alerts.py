#!/usr/bin/env python3
"""
Deferred + async TTC alerts → Telegram (polling-монитор).

Рабочий канал: прямой poll → TelegramAlerter. Grafana AM→Telegram в этом runtime не стреляет.

Запуск:  python scripts/tg_deferred_alerts.py --threshold 10 --interval 300
Разово:  python scripts/tg_deferred_alerts.py --once
Тест:    python scripts/tg_deferred_alerts.py --test
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "knowledge_os" / "app"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "knowledge_os"))

PROM_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9091")
METRIC = "knowledge_os_tasks_deferred_new_24h_total"
VICTORIA_METRICS_URL = os.getenv("VICTORIA_METRICS_URL", "http://127.0.0.1:8010/metrics")
TTC_P95_THRESHOLD = float(os.getenv("VICTORIA_ASYNC_TTC_P95_SEC", "420"))
TTC_COMPLEX_P95_THRESHOLD = float(os.getenv("VICTORIA_ASYNC_TTC_COMPLEX_P95_SEC", "900"))
CONSILIUM_P95_THRESHOLD = float(os.getenv("VICTORIA_CONSILIUM_TTC_P95_SEC", "300"))
TTC_MIN_SAMPLES = int(os.getenv("VICTORIA_ASYNC_TTC_MIN_SAMPLES", "20"))
TTC_HUNG_THRESHOLD = float(os.getenv("VICTORIA_ASYNC_TTC_HUNG_SEC", "600"))
# Do not use a bare "async" marker: it matches request_async_mode (all /run)
# and silently moves typical p95 onto the 900s complex lane.
_COMPLEX_MARKERS = ("timeout_", "enhanced_solve", "consilium", "deep")
_P95_REASON_RE = re.compile(
    r'victoria_async_ttc_p95_by_reason_seconds\{handoff_reason="([^"]+)"\}\s+(\S+)'
)
_N_REASON_RE = re.compile(
    r'victoria_async_ttc_samples_by_reason\{handoff_reason="([^"]+)"\}\s+(\S+)'
)


def is_complex_reason(reason: str) -> bool:
    key = (reason or "").lower()
    return any(m in key for m in _COMPLEX_MARKERS)


def parse_reason_metrics(text: str) -> dict[str, dict[str, float]]:
    p95: dict[str, float] = {}
    samples: dict[str, float] = {}
    for reason, value in _P95_REASON_RE.findall(text or ""):
        p95[reason] = float(value)
    for reason, value in _N_REASON_RE.findall(text or ""):
        samples[reason] = float(value)
    keys = set(p95) | set(samples)
    return {
        key: {"p95": p95.get(key, 0.0), "samples": samples.get(key, 0.0)}
        for key in keys
    }


def split_typical_complex(
    by_reason: dict[str, dict[str, float]],
) -> tuple[float | None, int, float | None, int]:
    typical_p95s: list[float] = []
    complex_p95s: list[float] = []
    typical_n = 0
    complex_n = 0
    for reason, row in (by_reason or {}).items():
        n = int(row.get("samples") or 0)
        p95 = float(row.get("p95") or 0.0)
        if is_complex_reason(reason):
            complex_p95s.append(p95)
            complex_n += n
        else:
            typical_p95s.append(p95)
            typical_n += n
    return (
        max(typical_p95s) if typical_p95s else None,
        typical_n,
        max(complex_p95s) if complex_p95s else None,
        complex_n,
    )


def ttc_p95_over(
    typical_p95: float | None,
    typical_n: int,
    complex_p95: float | None,
    complex_n: int,
    typical_threshold: float,
    complex_threshold: float,
    min_samples: int,
) -> tuple[bool, bool]:
    typical_over = (
        typical_p95 is not None
        and typical_n >= min_samples
        and typical_p95 > typical_threshold
    )
    complex_over = (
        complex_p95 is not None
        and complex_n >= min_samples
        and complex_p95 > complex_threshold
    )
    return typical_over, complex_over
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


def fetch_async_ttc() -> tuple[float | None, float | None, int, float, int, dict]:
    """p50, p95, samples, inflight_max, inflight_n, by_reason from Victoria /metrics."""
    import urllib.request
    try:
        with urllib.request.urlopen(VICTORIA_METRICS_URL, timeout=5) as r:
            text = r.read().decode()
    except Exception as e:  # noqa: BLE001
        print(f"[ttc poll error] {e}")
        return None, None, 0, 0.0, 0, {}
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
    return p50, p95, samples, inflight_max, inflight_n, parse_reason_metrics(text)


async def send_tg(text: str) -> bool:
    from telegram_alerter import get_telegram_alerter

    alerter = get_telegram_alerter()
    return await alerter.send_alert(text, priority="high", source="Deferred Monitor")



def _fmt_sec(s: float) -> str:
    """Человеческая длительность: 45 с / 2 мин 21 с / 4 ч 05 мин."""
    s = int(round(s))
    if s < 60:
        return f"{s} с"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m} мин {sec:02d} с"
    h, m = divmod(m, 60)
    return f"{h} ч {m:02d} мин"


def _build_ttc_text(
    typical_threshold: float,
    complex_threshold: float,
    hung_threshold: float,
    typical_over: bool,
    complex_over: bool,
    hung_over: bool,
    p50: float | None,
    typical_p95: float | None,
    complex_p95: float | None,
    typical_n: int,
    complex_n: int,
    inflight_max: float,
    inflight_n: int,
) -> str:
    """Человекочитаемый алерт скорости ответов Виктории."""
    lines = []
    if hung_over:
        lines.append("⚠️ Одна из задач Виктории висит без ответа слишком долго.")
    if typical_over:
        lines.append("🐢 Обычные ответы Виктории медленнее нормы.")
    if complex_over:
        lines.append("🐢 Сложные ответы Виктории дольше 15 минут.")
    if not lines:
        lines.append("⏱ Замечено отклонение скорости ответов Виктории.")
    lines.append("")
    if p50 is not None:
        lines.append(f"• Обычный ответ (середина): ~{_fmt_sec(p50)}")
    if typical_p95 is not None:
        lines.append(
            f"• Обычный медленный: ~{_fmt_sec(typical_p95)} "
            f"(норма до {_fmt_sec(typical_threshold)}, n={typical_n})"
        )
    if complex_p95 is not None:
        lines.append(
            f"• Сложный «объясни…»: ~{_fmt_sec(complex_p95)} "
            f"(норма до {_fmt_sec(complex_threshold)}, n={complex_n})"
        )
    if hung_over:
        lines.append(
            f"• ⚠️ Задача в работе уже {_fmt_sec(inflight_max)} "
            f"(порог зависания {_fmt_sec(hung_threshold)}) — похоже на зависание"
        )
    elif inflight_n:
        lines.append(f"• Сейчас в работе: {inflight_n}")
    lines.append("")
    lines.append("Что это значит:")
    if hung_over:
        lines.append("• Зависшая задача погаснет при следующем рестарте Виктории;")
        lines.append("  если ответ всё ещё нужен — отправьте запрос заново.")
    if typical_over:
        lines.append(
            f"• Обычные ответы не должны занимать больше {_fmt_sec(typical_threshold)}."
        )
    if complex_over:
        lines.append("• Сложные ответы могут идти до 15 минут. Этот алерт — только если дольше.")
        lines.append("  Dashboard 8501 → «Задачи и SLA».")
    lines.append("")
    lines.append(
        f"Технически: typical_p95={typical_p95 if typical_p95 is not None else 0:.1f}s "
        f"complex_p95={complex_p95 if complex_p95 is not None else 0:.1f}s "
        f"p50={p50 if p50 is not None else 0:.1f}s typical_n={typical_n} complex_n={complex_n} "
        f"inflight_max={inflight_max:.1f}s inflight_n={inflight_n} "
        f"порог_обычный={typical_threshold:.0f}s порог_сложный={complex_threshold:.0f}s "
        f"порог_hung={hung_threshold:.0f}s"
    )
    return "\n".join(lines).replace("\\n", "\n")


async def run_once(threshold: float) -> bool:
    value = await fetch_metric()
    if value is None:
        return False
    state = _load_state()
    already = state.get("fired_at", 0)
    fresh_enough = time.time() - already < RESET_AFTER_SEC
    if value > threshold and not fresh_enough:
        ok = await send_tg(
            f"📥 Накопились задачи, требующие человека\n\n"
            f"За сутки их появилось: {int(value)} (норма до {int(threshold)})\n"
            f"Что делать: дашборд 8501 → «Задачи и SLA» → фильтр deferred;\n"
            f"разобрать или закрыть вручную.\n\n"
            f"Технически: {METRIC}"
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


async def run_ttc_once(
    threshold: float = TTC_P95_THRESHOLD,
    complex_threshold: float = TTC_COMPLEX_P95_THRESHOLD,
    min_samples: int = TTC_MIN_SAMPLES,
    hung_threshold: float = TTC_HUNG_THRESHOLD,
) -> bool:
    p50, p95, samples, inflight_max, inflight_n, by_reason = fetch_async_ttc()
    if p95 is None:
        print("[ttc] metrics unavailable")
        return False
    typical_p95, typical_n, complex_p95, complex_n = split_typical_complex(by_reason)
    if not by_reason:
        typical_p95, typical_n = p95, samples
        complex_p95, complex_n = None, 0
    typical_over, complex_over = ttc_p95_over(
        typical_p95,
        typical_n,
        complex_p95,
        complex_n,
        threshold,
        complex_threshold,
        min_samples,
    )
    p95_over = typical_over or complex_over
    hung_over = inflight_n > 0 and inflight_max > hung_threshold
    now = time.time()
    state = _load_state()
    fresh_p95 = now - state.get("ttc_fired_at", 0) < RESET_AFTER_SEC
    fresh_hung = now - state.get("hung_fired_at", 0) < RESET_AFTER_SEC
    over = (p95_over and not fresh_p95) or (hung_over and not fresh_hung)
    print(
        f"[ttc] p50={p50} unlabeled_p95={p95} samples={samples} "
        f"typical_p95={typical_p95} typical_n={typical_n} "
        f"complex_p95={complex_p95} complex_n={complex_n} "
        f"inflight_max={inflight_max} inflight_n={inflight_n} "
        f"typical_threshold={threshold} complex_threshold={complex_threshold} "
        f"hung_threshold={hung_threshold} min_samples={min_samples} over={over}"
    )
    if over:
        ok = await send_tg(
            _build_ttc_text(
                threshold,
                complex_threshold,
                hung_threshold,
                typical_over,
                complex_over,
                hung_over,
                p50,
                typical_p95,
                complex_p95,
                typical_n,
                complex_n,
                inflight_max,
                inflight_n,
            )
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
            print(f"[ttc alert sent] typical_over={typical_over} complex_over={complex_over}")
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
