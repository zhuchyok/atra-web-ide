#!/usr/bin/env python3
"""
Aggregate routing quality metrics from Redis stream:routing_decisions.

Data source:
- Reads events through knowledge_os_worker Redis client to avoid host Redis mismatch.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], input_text: str | None = None) -> str:
    p = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    )
    return p.stdout.strip()


def fetch_events(count: int) -> list[dict[str, Any]]:
    code = f"""
import asyncio, json
from app.redis_manager import redis_manager

async def main():
    c = await redis_manager.get_client()
    rows = await c.xrevrange("stream:routing_decisions", count={count})
    out = []
    for item_id, fields in rows:
        d = dict(fields)
        d["_id"] = item_id
        out.append(d)
    print(json.dumps(out, ensure_ascii=False))

asyncio.run(main())
""".strip()
    out = _run(["docker", "exec", "-i", "knowledge_os_worker", "python", "-"], input_text=code)
    if not out:
        return []
    return json.loads(out)


def _event_ts_ms(event: dict[str, Any]) -> int:
    ts = str(event.get("ts", "")).strip()
    if ts.isdigit():
        return int(ts)
    event_id = str(event.get("_id", "0-0"))
    prefix = event_id.split("-", 1)[0]
    if prefix.isdigit():
        return int(prefix)
    return 0


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    k = (len(arr) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return arr[int(k)]
    d0 = arr[f] * (c - k)
    d1 = arr[c] * (k - f)
    return d0 + d1


def _parse_prefixes(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def _is_synthetic_reason(reason: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return False
    r = reason.lower().strip()
    return any(r.startswith(p.lower()) for p in prefixes)


def _parse_values(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def aggregate(
    events: list[dict[str, Any]],
    window_hours: float,
    *,
    exclude_reason_prefixes: list[str] | None = None,
    exclude_routes: list[str] | None = None,
) -> dict[str, Any]:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    window_ms = int(window_hours * 3600 * 1000)
    cutoff = now_ms - window_ms
    filtered = [e for e in events if _event_ts_ms(e) >= cutoff]
    with_route = [e for e in filtered if str(e.get("selected_route", "")).strip()]
    invalid_count = len(filtered) - len(with_route)

    prefixes = exclude_reason_prefixes or []
    excluded_routes = [r.lower() for r in (exclude_routes or [])]
    synthetic_ignored = 0
    route_ignored = 0
    valid: list[dict[str, Any]] = []
    for e in with_route:
        reason = str(e.get("reason", "")).strip()
        route = str(e.get("selected_route", "")).strip().lower()
        if _is_synthetic_reason(reason, prefixes):
            synthetic_ignored += 1
            continue
        if excluded_routes and route in excluded_routes:
            route_ignored += 1
            continue
        valid.append(e)

    total = len(valid)
    success_rows = [e for e in valid if str(e.get("success", "0")) in ("1", "true", "True")]
    success = len(success_rows)
    success_rate = (success / total) if total else 0.0

    regret_rows = [
        e
        for e in valid
        if "regret" in str(e.get("reason", "")).lower()
        or "better" in str(e.get("reason", "")).lower()
    ]
    regret_rate = (len(regret_rows) / total) if total else 0.0

    latencies = [_f(e.get("latency_ms", 0.0), 0.0) for e in success_rows]
    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)

    by_route: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "success": 0, "latencies": []}
    )
    by_model: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "success": 0, "latencies": []}
    )
    for e in valid:
        route = str(e.get("selected_route", "unknown")) or "unknown"
        model = str(e.get("selected_model", "unknown")) or "unknown"
        ok = str(e.get("success", "0")) in ("1", "true", "True")
        lat = _f(e.get("latency_ms", 0.0), 0.0)

        by_route[route]["total"] += 1
        by_model[model]["total"] += 1
        if ok:
            by_route[route]["success"] += 1
            by_model[model]["success"] += 1
            by_route[route]["latencies"].append(lat)
            by_model[model]["latencies"].append(lat)

    def _finalize(group: dict[str, dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in group.items():
            t = v["total"]
            s = v["success"]
            out[k] = {
                "total": t,
                "success": s,
                "success_rate": round((s / t) if t else 0.0, 4),
                "p95_latency_ms": round(_percentile(v["latencies"], 0.95), 2),
            }
        return out

    result = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "window_hours": window_hours,
        "excluded_reason_prefixes": prefixes,
        "excluded_routes": excluded_routes,
        "events_total_window": total,
        "events_invalid_ignored": invalid_count,
        "events_synthetic_ignored": synthetic_ignored,
        "events_excluded_route_ignored": route_ignored,
        "events_success_window": success,
        "routing_win_rate": round(success_rate, 4),
        "decision_regret_rate": round(regret_rate, 4),
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "by_route": _finalize(by_route),
        "by_model": _finalize(by_model),
    }
    return result


def build_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Routing Quality Report",
        "",
        f"- ts_utc: `{data.get('ts_utc')}`",
        f"- window_hours: `{data.get('window_hours')}`",
        f"- excluded_reason_prefixes: `{data.get('excluded_reason_prefixes')}`",
        f"- excluded_routes: `{data.get('excluded_routes')}`",
        f"- events_total_window: `{data.get('events_total_window')}`",
        f"- events_synthetic_ignored: `{data.get('events_synthetic_ignored')}`",
        f"- events_excluded_route_ignored: `{data.get('events_excluded_route_ignored')}`",
        f"- routing_win_rate: `{data.get('routing_win_rate')}`",
        f"- decision_regret_rate: `{data.get('decision_regret_rate')}`",
        f"- latency_p50_ms: `{data.get('latency_p50_ms')}`",
        f"- latency_p95_ms: `{data.get('latency_p95_ms')}`",
        "",
        "## By Route",
    ]
    for route, r in sorted((data.get("by_route") or {}).items()):
        lines.append(
            f"- `{route}` total=`{r['total']}` success=`{r['success']}` "
            f"win_rate=`{r['success_rate']}` p95_ms=`{r['p95_latency_ms']}`"
        )
    lines.extend(["", "## By Model"])
    for model, r in sorted((data.get("by_model") or {}).items()):
        lines.append(
            f"- `{model}` total=`{r['total']}` success=`{r['success']}` "
            f"win_rate=`{r['success_rate']}` p95_ms=`{r['p95_latency_ms']}`"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--window-hours", type=float, default=24.0)
    parser.add_argument("--json-out", type=str, default="")
    parser.add_argument("--md-out", type=str, default="")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument(
        "--exclude-reason-prefixes",
        type=str,
        default="quality_seed_",
        help="Comma-separated reason prefixes to exclude from production quality metrics",
    )
    parser.add_argument(
        "--exclude-routes",
        type=str,
        default="cloud",
        help="Comma-separated routes to exclude for local production KPI (e.g. cloud)",
    )
    parser.add_argument(
        "--include-synthetic",
        action="store_true",
        help="Disable synthetic filtering and include all events",
    )
    args = parser.parse_args()

    events = fetch_events(args.count)
    prefixes = [] if args.include_synthetic else _parse_prefixes(args.exclude_reason_prefixes)
    routes = _parse_values(args.exclude_routes)
    data = aggregate(
        events,
        args.window_hours,
        exclude_reason_prefixes=prefixes,
        exclude_routes=routes,
    )

    if args.json_out:
        jp = Path(args.json_out)
        if not jp.is_absolute():
            jp = ROOT / jp
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.md_out:
        mp = Path(args.md_out)
        if not mp.is_absolute():
            mp = ROOT / mp
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(build_markdown(data), encoding="utf-8")

    if args.print_json or (not args.json_out and not args.md_out):
        print(json.dumps(data, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

