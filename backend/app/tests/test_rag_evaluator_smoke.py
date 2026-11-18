"""Offline quality-gate smoke: RAGEvaluator + reference_smoke path (no Ollama/DB)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from app.evaluation.rag_evaluator import DEFAULT_THRESHOLDS, RAGEvaluator

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.asyncio
async def test_evaluator_rejects_empty_response():
    ev = RAGEvaluator()
    metrics = await ev.evaluate_response(
        "сколько стоит подписка",
        "",
        [],
        reference="Стоимость подписки составляет 999 рублей в месяц.",
    )
    assert metrics["faithfulness"] == 0.0
    assert metrics["relevance"] == 0.0
    assert metrics["coherence"] == 0.0
    passed, failed = RAGEvaluator.check_thresholds(metrics, DEFAULT_THRESHOLDS)
    assert passed is False
    assert failed


@pytest.mark.asyncio
async def test_evaluator_accepts_faithful_answer():
    ev = RAGEvaluator()
    query = "сколько стоит подписка"
    reference = (
        "Стоимость подписки составляет 999 рублей в месяц. Доступна пробная версия на 14 дней."
    )
    context = [f"Вопрос: {query}\nОтвет: {reference}"]
    metrics = await ev.evaluate_response(query, reference, context, reference=reference)
    passed, failed = RAGEvaluator.check_thresholds(metrics, DEFAULT_THRESHOLDS)
    assert passed is True, failed
    assert metrics["faithfulness"] >= 0.8
    assert metrics["relevance"] >= 0.85
    assert metrics["coherence"] >= 0.7


def test_reference_smoke_cli_passes_thresholds(tmp_path: Path):
    """Local proof mirroring CI: reference_smoke report must clear threshold gate."""
    out = tmp_path / "validation_report.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "evaluate_rag_quality.py"),
        "--mode",
        "reference_smoke",
        "--dataset",
        str(REPO_ROOT / "data" / "validation_queries.json"),
        "--threshold",
        "faithfulness:0.8,relevance:0.85,coherence:0.7",
        "--output",
        str(out),
    ]
    env = {**os.environ, "PYTHONPATH": f"{REPO_ROOT / 'backend'}:{REPO_ROOT}"}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data.get("mode") == "reference_smoke"
    assert data.get("skipped") is not True
    assert int(data.get("total_queries") or 0) >= 1
    assert data.get("passed") is True

    gate = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "check_quality_thresholds.py"),
            str(out),
            "--threshold",
            "faithfulness:0.8,relevance:0.85,coherence:0.7",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert gate.returncode == 0, gate.stdout + "\n" + gate.stderr
    assert "All thresholds passed" in gate.stdout


def test_skipped_report_still_fail_closed(tmp_path: Path):
    report = tmp_path / "skipped.json"
    report.write_text(
        json.dumps(
            {
                "skipped": True,
                "avg_metrics": {"faithfulness": 1.0, "relevance": 1.0, "coherence": 1.0},
                "total_queries": 3,
            }
        ),
        encoding="utf-8",
    )
    gate = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_quality_thresholds.py"), str(report)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert gate.returncode == 1
    assert "skipped" in gate.stderr.lower()


def test_require_mode_live_rejects_reference_smoke(tmp_path: Path):
    report = tmp_path / "ref.json"
    report.write_text(
        json.dumps(
            {
                "mode": "reference_smoke",
                "avg_metrics": {"faithfulness": 1.0, "relevance": 1.0, "coherence": 1.0},
                "total_queries": 3,
                "skipped": False,
            }
        ),
        encoding="utf-8",
    )
    gate = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "check_quality_thresholds.py"),
            str(report),
            "--require-mode",
            "live",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert gate.returncode == 1
    assert "mode" in gate.stderr.lower()


def test_live_preflight_fails_closed_without_ollama(tmp_path: Path):
    """Honest fail: live gate must not green-pass when Ollama is unreachable."""
    out = tmp_path / "live_fail.json"
    env = {
        **os.environ,
        "LIVE_RAG_QUALITY": "1",
        "OLLAMA_URL": "http://127.0.0.1:9",
        "PYTHONPATH": f"{REPO_ROOT / 'backend'}:{REPO_ROOT}",
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "evaluate_rag_quality.py"),
            "--mode",
            "live",
            "--require-live",
            "--dataset",
            str(REPO_ROOT / "data" / "validation_queries.json"),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + "\n" + proc.stderr
    assert "preflight FAIL" in (proc.stderr + proc.stdout)
