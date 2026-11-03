"""Tagged async TTC samples. Overall p95 stays for alert 420; per-reason is extra."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Optional

_REASON_RE = re.compile(r"[^a-zA-Z0-9_:\-]+")
_MAX_REASONS = 16
_METRIC_P95 = "victoria_async_ttc_p95_by_reason_seconds"
_METRIC_SAMPLES = "victoria_async_ttc_samples_by_reason"


def sanitize_reason(reason: Optional[str]) -> str:
    key = str(reason or "").strip()[:64]
    cleaned = _REASON_RE.sub("_", key).strip("_")
    return cleaned or "unknown"


def encode_ttc_sample(duration: float, reason: Optional[str] = None) -> str:
    return json.dumps(
        {"d": round(float(duration), 3), "r": sanitize_reason(reason)},
        separators=(",", ":"),
    )


def parse_ttc_sample(raw: Any) -> Optional[tuple[float, str]]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    text = str(raw).strip()
    if not text:
        return None
    if text[:1] == "{":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        try:
            duration = float(obj.get("d"))
        except (TypeError, ValueError):
            return None
        return (duration, sanitize_reason(obj.get("r")))
    try:
        return (float(text), "unknown")
    except ValueError:
        return None


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return float(ordered[idx])


def ttc_by_reason(
    samples: list[tuple[float, str]], max_reasons: int = _MAX_REASONS
) -> dict[str, dict[str, float]]:
    cap = max(2, int(max_reasons))
    counts = Counter(reason for _, reason in samples)
    keep = {reason for reason, _ in counts.most_common(cap - 1)}
    buckets: dict[str, list[float]] = {}
    for duration, reason in samples:
        key = reason if reason in keep else "other"
        buckets.setdefault(key, []).append(duration)
    return {
        key: {
            "p50": round(_percentile(vals, 0.50), 3),
            "p95": round(_percentile(vals, 0.95), 3),
            "samples": float(len(vals)),
        }
        for key, vals in buckets.items()
    }


def format_reason_p95_line(by_reason: dict[str, dict[str, float]]) -> str:
    parts = []
    for key in sorted(by_reason):
        row = by_reason[key]
        parts.append(f"{key}:p95={row.get('p95', 0.0)}/n={int(row.get('samples') or 0)}")
    return " ".join(parts)


def render_reason_metrics(by_reason: dict[str, dict[str, float]]) -> str:
    if not by_reason:
        return ""
    lines = [
        "# HELP %s Rolling p95 async TTC by handoff_reason\n" % _METRIC_P95,
        "# TYPE %s gauge\n" % _METRIC_P95,
    ]
    for key in sorted(by_reason):
        row = by_reason[key]
        lines.append(
            '%s{handoff_reason="%s"} %.6f\n'
            % (_METRIC_P95, key, float(row.get("p95") or 0.0))
        )
    lines.append("# HELP %s Rolling TTC sample count by handoff_reason\n" % _METRIC_SAMPLES)
    lines.append("# TYPE %s gauge\n" % _METRIC_SAMPLES)
    for key in sorted(by_reason):
        row = by_reason[key]
        lines.append(
            '%s{handoff_reason="%s"} %d\n' % (_METRIC_SAMPLES, key, int(row.get("samples") or 0))
        )
    return "".join(lines)
