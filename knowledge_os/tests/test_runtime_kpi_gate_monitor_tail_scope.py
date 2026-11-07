from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_monitor_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "runtime_kpi_gate_monitor.py"
    spec = importlib.util.spec_from_file_location("runtime_kpi_gate_monitor", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample(
    *,
    completed_total: int,
    eligible_now: int,
    campaign_in_progress: int = 0,
) -> dict:
    return {
        "completed_total": completed_total,
        "pending": 0,
        "in_progress": 0,
        "stale_in_progress": 0,
        "dynamic_alert_count": 0,
        "failure_rate_10m_gate_pct": 0.0,
        "containers_healthy": True,
        "contract_enforce": "1",
        "contract_rollout_mode": "enforce",
        "completed_10m": 0,
        "eligible_now": eligible_now,
        "campaign_done": 0,
        "campaign_in_progress": campaign_in_progress,
        "campaign_retry": 0,
    }


def test_tail_scope_inactive_campaign_is_not_a_violation():
    monitor = _load_monitor_module()
    samples = [
        _sample(completed_total=10, eligible_now=29800),
        _sample(completed_total=10, eligible_now=29800),
        _sample(completed_total=10, eligible_now=29800),
    ]

    res = monitor.evaluate_window(
        window_name="15m",
        window_minutes=15,
        interval_sec=300,
        samples=samples,
        min_completed_per_hour=3,
        distill_target=8,
        distill_high_watermark=12,
        distill_consecutive_breach=2,
    )

    assert res.pass_ok is True
    assert res.distill_tail_ok is True
    assert res.reason == "insufficient_load_n_a"


def test_tail_scope_active_campaign_keeps_violation_signal():
    monitor = _load_monitor_module()
    samples = [
        _sample(completed_total=10, eligible_now=29800, campaign_in_progress=1),
        _sample(completed_total=10, eligible_now=29801, campaign_in_progress=1),
        _sample(completed_total=10, eligible_now=29802, campaign_in_progress=1),
    ]

    res = monitor.evaluate_window(
        window_name="15m",
        window_minutes=15,
        interval_sec=300,
        samples=samples,
        min_completed_per_hour=3,
        distill_target=8,
        distill_high_watermark=12,
        distill_consecutive_breach=2,
    )

    assert res.pass_ok is False
    assert res.distill_tail_ok is False
    assert res.reason == "distillation_tail_violation"


def test_sustained_tail_slo_inactive_campaign_returns_na_green():
    monitor = _load_monitor_module()
    samples = [
        _sample(completed_total=10, eligible_now=29800),
        _sample(completed_total=10, eligible_now=29800),
        _sample(completed_total=10, eligible_now=29800),
    ]

    slo = monitor.evaluate_sustained_tail_slo(
        samples=samples,
        distill_target=8,
        distill_high_watermark=12,
        max_consecutive_breach=3,
        max_above_target_ratio=0.35,
        min_samples_required=12,
    )

    assert slo.ok is True
    assert slo.reason == "inactive_campaign_n_a"
