import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE = os.path.join(ROOT, "src", "agents", "bridge")
if BRIDGE not in sys.path:
    sys.path.insert(0, BRIDGE)

from async_ttc import (
    encode_ttc_sample,
    format_reason_p95_line,
    parse_ttc_sample,
    render_reason_metrics,
    sanitize_reason,
    ttc_by_reason,
)


def test_parse_bare_float_is_unknown():
    assert parse_ttc_sample("12.5") == (12.5, "unknown")
    assert parse_ttc_sample(b"480.0") == (480.0, "unknown")


def test_parse_json_keeps_reason():
    raw = encode_ttc_sample(12.5, "timeout_watchdog")
    assert parse_ttc_sample(raw) == (12.5, "timeout_watchdog")


def test_sanitize_reason_strips_junk():
    assert sanitize_reason('timeout "watchdog"') == "timeout_watchdog"
    assert sanitize_reason("") == "unknown"
    assert sanitize_reason(None) == "unknown"


def test_by_reason_p95_does_not_drop_timeouts():
    samples = [
        (10.0, "quick"),
        (12.0, "quick"),
        (11.0, "quick"),
        (400.0, "timeout_watchdog"),
        (480.0, "timeout_watchdog"),
        (500.0, "timeout_watchdog"),
    ]
    grouped = ttc_by_reason(samples)
    assert grouped["quick"]["samples"] == 3
    assert grouped["timeout_watchdog"]["samples"] == 3
    assert grouped["timeout_watchdog"]["p95"] >= 480.0


def test_fold_extra_reasons_into_other():
    samples = [(float(i), f"r{i}") for i in range(20)]
    grouped = ttc_by_reason(samples, max_reasons=16)
    assert "other" in grouped
    assert len(grouped) <= 16


def test_format_reason_line():
    line = format_reason_p95_line(
        {"quick": {"p95": 12.0, "samples": 3}, "timeout_watchdog": {"p95": 480.0, "samples": 2}}
    )
    assert "timeout_watchdog:p95=480.0/n=2" in line
    assert "quick:p95=12.0/n=3" in line


def test_render_reason_metrics_labels():
    body = render_reason_metrics(
        {"quick": {"p95": 12.0, "samples": 3}, "timeout_watchdog": {"p95": 480.0, "samples": 2}}
    )
    metric_lines = [
        line
        for line in body.splitlines()
        if line.startswith("victoria_async_ttc_p95_by_reason_seconds")
    ]
    assert metric_lines, body
    assert metric_lines[0][:8] == "victoria"
    assert ord(metric_lines[0][1]) == 105  # i, not e (typo vectoria)
    assert "timeout_watchdog" in body
    assert "480.000000" in body
    assert "handoff_reason=" in body
    assert any(line.endswith(" 3") and "samples_by_reason" in line for line in body.splitlines())
    assert "victoria_async_ttc_p95_seconds " not in body


def test_empty_by_reason_renders_nothing():
    assert render_reason_metrics({}) == ""
