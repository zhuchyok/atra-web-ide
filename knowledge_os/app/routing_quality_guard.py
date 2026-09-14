from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GuardThresholds:
    min_events: int = 100
    target_win_rate: float = 0.90
    min_win_rate_rollback: float = 0.80
    target_regret_rate: float = 0.15
    max_regret_rate_rollback: float = 0.25
    # Local on-device LLM profile: stable p95 is in hundreds of seconds.
    max_p95_ms: float = 450000.0
    max_p95_ms_rollback: float = 600000.0


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    k = (len(arr) - 1) * p
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    if f == c:
        return arr[f]
    return arr[f] * (c - k) + arr[c] * (k - f)


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _parse_prefixes(raw: str) -> List[str]:
    return [p.strip().lower() for p in str(raw).split(",") if p.strip()]


def _is_synthetic_reason(reason: str, prefixes: List[str]) -> bool:
    if not prefixes:
        return False
    r = str(reason or "").strip().lower()
    return any(r.startswith(p) for p in prefixes)


def _parse_values(raw: str) -> List[str]:
    return [p.strip().lower() for p in str(raw).split(",") if p.strip()]


def _event_ts_ms(event: Dict[str, Any]) -> int:
    ts = str(event.get("ts", "")).strip()
    if ts.isdigit():
        return int(ts)
    item_id = str(event.get("_id", "0-0"))
    prefix = item_id.split("-", 1)[0]
    return int(prefix) if prefix.isdigit() else 0


def aggregate_routing_metrics(events: List[Dict[str, Any]], window_hours: float) -> Dict[str, Any]:
    include_synthetic = os.getenv("ROUTING_GUARD_INCLUDE_SYNTHETIC", "0").lower() in ("1", "true", "yes")
    prefixes = [] if include_synthetic else _parse_prefixes(os.getenv("ROUTING_EXCLUDE_REASON_PREFIXES", "quality_seed_"))
    excluded_routes = _parse_values(os.getenv("ROUTING_EXCLUDE_ROUTES", "cloud"))
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = now_ms - int(max(1.0, window_hours) * 3600 * 1000)
    filtered = [e for e in events if _event_ts_ms(e) >= cutoff]
    with_route = [e for e in filtered if str(e.get("selected_route", "")).strip()]
    invalid_count = len(filtered) - len(with_route)

    synthetic_ignored = 0
    route_ignored = 0
    valid = []
    for e in with_route:
        if _is_synthetic_reason(str(e.get("reason", "")), prefixes):
            synthetic_ignored += 1
            continue
        route = str(e.get("selected_route", "")).strip().lower()
        if excluded_routes and route in excluded_routes:
            route_ignored += 1
            continue
        valid.append(e)

    total = len(valid)
    success_rows = [e for e in valid if str(e.get("success", "0")) in ("1", "true", "True")]
    success = len(success_rows)
    win_rate = (success / total) if total else 0.0
    regret_rows = [
        e
        for e in valid
        if "regret" in str(e.get("reason", "")).lower()
        or "better" in str(e.get("reason", "")).lower()
    ]
    regret_rate = (len(regret_rows) / total) if total else 0.0
    latencies = [_safe_float(e.get("latency_ms", 0.0), 0.0) for e in success_rows]

    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "window_hours": window_hours,
        "excluded_reason_prefixes": prefixes,
        "excluded_routes": excluded_routes,
        "events_total_window": total,
        "events_invalid_ignored": invalid_count,
        "events_synthetic_ignored": synthetic_ignored,
        "events_excluded_route_ignored": route_ignored,
        "events_success_window": success,
        "routing_win_rate": round(win_rate, 4),
        "decision_regret_rate": round(regret_rate, 4),
        "latency_p50_ms": round(_percentile(latencies, 0.50), 2),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 2),
    }


def evaluate_guard_action(metrics: Dict[str, Any], th: GuardThresholds) -> Dict[str, Any]:
    events = int(metrics.get("events_total_window", 0) or 0)
    win = float(metrics.get("routing_win_rate", 0.0) or 0.0)
    regret = float(metrics.get("decision_regret_rate", 0.0) or 0.0)
    p95 = float(metrics.get("latency_p95_ms", 0.0) or 0.0)
    if events < th.min_events:
        return {
            "action": "canary_only",
            "reason": f"insufficient_events:{events}<{th.min_events}",
            "hard_fail": False,
        }
    hard_fail = (
        win < th.min_win_rate_rollback
        or regret > th.max_regret_rate_rollback
        or p95 > th.max_p95_ms_rollback
    )
    if hard_fail:
        return {
            "action": "rollback",
            "reason": f"hard_fail(win={win:.4f},regret={regret:.4f},p95={p95:.2f})",
            "hard_fail": True,
        }
    soft_fail = win < th.target_win_rate or regret > th.target_regret_rate or p95 > th.max_p95_ms
    if soft_fail:
        return {
            "action": "canary_only",
            "reason": f"soft_fail(win={win:.4f},regret={regret:.4f},p95={p95:.2f})",
            "hard_fail": False,
        }
    return {"action": "rollout", "reason": "ok", "hard_fail": False}


def _resolve_report_dir() -> Path:
    preferred = os.getenv("NIGHTLY_ROUTING_GUARD_REPORT_DIR", "/app/docs/audits")
    p = Path(preferred)
    try:
        p.mkdir(parents=True, exist_ok=True)
        t = p / ".write_test"
        t.write_text("ok", encoding="utf-8")
        t.unlink(missing_ok=True)
        return p
    except Exception:
        fb = Path("/tmp/nightly-routing-guard")
        fb.mkdir(parents=True, exist_ok=True)
        return fb


def _to_markdown(report: Dict[str, Any]) -> str:
    m = report["routing_metrics"]
    d = report["decision"]
    lines = [
        "# Nightly Routing Guard",
        "",
        f"- ts_utc: `{report['ts_utc']}`",
        f"- mode: `{report['mode']}`",
        f"- action: `{d['action']}`",
        f"- reason: `{d['reason']}`",
        "",
        "## Metrics",
        f"- events_total_window: `{m.get('events_total_window')}`",
        f"- events_invalid_ignored: `{m.get('events_invalid_ignored')}`",
        f"- routing_win_rate: `{m.get('routing_win_rate')}`",
        f"- decision_regret_rate: `{m.get('decision_regret_rate')}`",
        f"- latency_p95_ms: `{m.get('latency_p95_ms')}`",
    ]
    return "\n".join(lines) + "\n"


async def _maybe_notify_guard_decision(redis_client: Any, decision: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    """Send Telegram/ntfy escalation for non-rollout actions with cooldown."""
    if str(decision.get("action")) == "rollout":
        logger.info("routing_guard_notify_skip: action=rollout")
        return
    enabled = os.getenv("NIGHTLY_ROUTING_GUARD_NOTIFY_ENABLED", "true").lower() in ("1", "true", "yes")
    if not enabled:
        logger.info("routing_guard_notify_skip: notifications disabled")
        return
    cooldown_sec = int(os.getenv("NIGHTLY_ROUTING_GUARD_NOTIFY_COOLDOWN_SEC", "3600"))
    now_ts = int(datetime.now(timezone.utc).timestamp())
    key = "system:routing_guard:last_notify_ts"
    try:
        last_raw = await redis_client.get(key)
        last = int(last_raw) if last_raw else 0
        if (now_ts - last) < max(60, cooldown_sec):
            logger.info("routing_guard_notify_skip: cooldown active")
            return
    except Exception:
        pass

    text = (
        "ATRA Routing Guard Alert\n"
        f"action={decision.get('action')}\n"
        f"reason={decision.get('reason')}\n"
        f"events_total_window={metrics.get('events_total_window')}\n"
        f"routing_win_rate={metrics.get('routing_win_rate')}\n"
        f"decision_regret_rate={metrics.get('decision_regret_rate')}\n"
        f"latency_p95_ms={metrics.get('latency_p95_ms')}"
    )
    try:
        try:
            from app.telegram_notifications_worker import send_ntfy, send_telegram
        except Exception:
            from telegram_notifications_worker import send_ntfy, send_telegram

        ok = await send_telegram(text)
        if not ok:
            ok = await send_ntfy(text, title="ATRA Routing Guard")
        if ok:
            await redis_client.set(key, str(now_ts))
            logger.warning("routing_guard_notify_sent: action=%s reason=%s", decision.get("action"), decision.get("reason"))
        else:
            logger.warning("routing_guard_notify_failed: action=%s", decision.get("action"))
    except Exception:
        # Best effort: never fail nightly cycle due to notification channel.
        logger.exception("routing_guard_notify_exception")
        return


async def run_routing_quality_guard_once(
    redis_client: Any,
    *,
    window_hours: float = 24.0,
    count: int = 1000,
    apply_action: bool = False,
    thresholds: GuardThresholds | None = None,
) -> Dict[str, Any]:
    th = thresholds or GuardThresholds()
    rows: List[Tuple[str, Dict[str, Any]]] = await redis_client.xrevrange(
        "stream:routing_decisions",
        count=max(100, count),
    )
    events: List[Dict[str, Any]] = []
    for item_id, fields in rows:
        d = dict(fields or {})
        d["_id"] = item_id
        events.append(d)

    metrics = aggregate_routing_metrics(events, window_hours=window_hours)
    decision = evaluate_guard_action(metrics, th)
    now = datetime.now(timezone.utc).isoformat()

    # Always publish latest decision telemetry for scraping/alerts (even in dry-run).
    await redis_client.set("system:routing_guard:last_action", str(decision["action"]))
    await redis_client.set("system:routing_guard:last_reason", str(decision["reason"]))
    await redis_client.set("system:routing_guard:last_ts_utc", now)
    await redis_client.set(
        "system:routing_guard:last_events_total_window",
        str(int(metrics.get("events_total_window", 0) or 0)),
    )
    await redis_client.set(
        "system:routing_guard:last_win_rate",
        str(float(metrics.get("routing_win_rate", 0.0) or 0.0)),
    )
    await redis_client.set(
        "system:routing_guard:last_regret_rate",
        str(float(metrics.get("decision_regret_rate", 0.0) or 0.0)),
    )
    await redis_client.set(
        "system:routing_guard:last_latency_p95_ms",
        str(float(metrics.get("latency_p95_ms", 0.0) or 0.0)),
    )

    apply_result = {"applied": False, "commands": []}
    if apply_action:
        if decision["action"] == "rollout":
            commands = [
                ("system:contract_rollout_mode", "enforce"),
                ("system:contract_enforce", "1"),
            ]
        else:
            commands = [
                ("system:contract_rollout_mode", "shadow"),
                ("system:contract_enforce", "0"),
            ]
        commands.extend(
            [
                ("system:routing_guard:last_apply_action", str(decision["action"])),
                ("system:routing_guard:last_apply_reason", str(decision["reason"])),
                ("system:routing_guard:last_apply_ts_utc", now),
            ]
        )
        for k, v in commands:
            await redis_client.set(k, v)
        apply_result = {
            "applied": True,
            "commands": [f"SET {k} {v}" for (k, v) in commands],
        }

    report = {
        "ts_utc": now,
        "mode": "apply" if apply_action else "dry-run",
        "routing_metrics": metrics,
        "decision": decision,
        "thresholds": th.__dict__,
        "apply_result": apply_result,
    }

    out_dir = _resolve_report_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (out_dir / f"{stamp}-nightly-routing-guard.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / f"{stamp}-nightly-routing-guard.md").write_text(
        _to_markdown(report),
        encoding="utf-8",
    )
    await _maybe_notify_guard_decision(redis_client, decision, metrics)
    return report
