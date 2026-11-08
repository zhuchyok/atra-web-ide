import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from tg_deferred_alerts import (  # noqa: E402
    TTC_P95_THRESHOLD,
    _build_ttc_text,
    is_complex_reason,
    parse_reason_metrics,
    split_typical_complex,
    ttc_p95_over,
)


def test_parse_reason_metrics_from_prometheus_text():
    text = (
        'victoria_async_ttc_p95_by_reason_seconds{handoff_reason="timeout_enhanced_solve"} 899.978\n'
        'victoria_async_ttc_samples_by_reason{handoff_reason="timeout_enhanced_solve"} 1\n'
        'victoria_async_ttc_p95_by_reason_seconds{handoff_reason="quick"} 12.5\n'
        'victoria_async_ttc_samples_by_reason{handoff_reason="quick"} 8\n'
    )
    got = parse_reason_metrics(text)
    assert got["timeout_enhanced_solve"]["p95"] == 899.978
    assert got["timeout_enhanced_solve"]["samples"] == 1
    assert got["quick"]["p95"] == 12.5
    assert got["quick"]["samples"] == 8


def test_request_async_mode_is_typical_not_complex():
    assert is_complex_reason("request_async_mode") is False
    assert is_complex_reason("timeout_enhanced_solve") is True
    typical_p95, typical_n, complex_p95, complex_n = split_typical_complex(
        {"request_async_mode": {"p95": 458.705, "samples": 49}}
    )
    assert typical_n == 49
    assert typical_p95 == 458.705
    assert complex_n == 0
    assert complex_p95 is None


def test_timeouts_are_complex_not_typical():
    by_reason = {
        "timeout_enhanced_solve": {"p95": 900.0, "samples": 1},
        "timeout_sync_safe_mode": {"p95": 225.0, "samples": 4},
    }
    typical_p95, typical_n, complex_p95, complex_n = split_typical_complex(by_reason)
    assert typical_n == 0
    assert typical_p95 is None
    assert complex_n == 5
    assert complex_p95 == 900.0


def test_tonight_alert_does_not_page_on_complex_under_15min():
    typical_over, complex_over = ttc_p95_over(
        typical_p95=None,
        typical_n=0,
        complex_p95=900.0,
        complex_n=5,
        typical_threshold=180,
        complex_threshold=900,
        min_samples=5,
    )
    assert typical_over is False
    assert complex_over is False


def test_typical_slow_still_pages():
    typical_over, complex_over = ttc_p95_over(
        typical_p95=200.0,
        typical_n=20,
        complex_p95=400.0,
        complex_n=4,
        typical_threshold=180,
        complex_threshold=900,
        min_samples=20,
    )
    assert typical_over is True
    assert complex_over is False


def test_complex_pages_only_past_15min_with_enough_samples():
    typical_over, complex_over = ttc_p95_over(
        typical_p95=40.0,
        typical_n=20,
        complex_p95=901.0,
        complex_n=20,
        typical_threshold=180,
        complex_threshold=900,
        min_samples=20,
    )
    assert typical_over is False
    assert complex_over is True


def test_production_typical_threshold_is_420_not_180():
    assert TTC_P95_THRESHOLD == 420


def test_alert_copy_uses_typical_threshold_not_hardcoded_3min():
    text = _build_ttc_text(
        typical_threshold=420,
        complex_threshold=900,
        hung_threshold=600,
        typical_over=True,
        complex_over=False,
        hung_over=False,
        p50=209.0,
        typical_p95=458.0,
        complex_p95=None,
        typical_n=49,
        complex_n=0,
        inflight_max=0.0,
        inflight_n=0,
    )
    assert "3 минут" not in text
    assert "7 мин" in text
    assert "норма до 7 мин" in text
