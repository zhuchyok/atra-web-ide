import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.agents.bridge.task_detector import (
    format_live_fact_answer,
    grounded_ports_answer,
    is_fact_seeking_question,
    public_task_title,
)


def test_ports_are_fact_seeking():
    assert is_fact_seeking_question(
        "Назови три рабочих порта ATRA: Victoria, Veronica, Open WebUI. Только числа."
    )


def test_queue_and_dashboard_are_fact_seeking():
    assert is_fact_seeking_question(
        "какой порт у Corporation Dashboard и что в очереди pending и in_progress?"
    )


def test_ops_metrics_are_fact_seeking():
    assert is_fact_seeking_question(
        "дай throughput, stale-task, error rate и contract enforce по фактам"
    )
    assert is_fact_seeking_question("дай cancelled_1h и churn за 1ч")
    assert is_fact_seeking_question("дай throughput_24h и contract за сутки")
    assert is_fact_seeking_question("дай cancelled churn за 24ч")


def test_grounded_ports_match_registry():
    ans = grounded_ports_answer(
        "Назови три рабочих порта ATRA: Victoria, Veronica, Open WebUI. Только числа."
    )
    assert ans == "8010, 8011, 3005"


def test_greeting_is_not_fact_seeking():
    assert not is_fact_seeking_question("привет")
    assert not is_fact_seeking_question("кто ты?")
    assert not is_fact_seeking_question("Одно предложение: кто ты?")


def test_public_task_title_strips_method_prefix():
    raw = "проверь health Victoria"
    enriched = (
        "📋 МЕТОД CURSOR (обязателен):\n"
        "1. Факты до вывода: прочитай файлы\n"
        "ЗАДАЧА:\n" + raw
    )
    assert public_task_title(enriched) == raw
    assert "МЕТОД CURSOR" not in public_task_title(enriched)


def test_live_health_ok():
    assert format_live_fact_answer("health Victoria ok или нет?", health="ok") == "ok"


def test_live_queue_counts():
    ans = format_live_fact_answer(
        "что в очереди pending и in_progress?",
        queue={"pending": 1, "in_progress": 0, "completed": 10},
    )
    assert ans == "pending=1 in_progress=0"


def test_live_ops_metrics():
    ans = format_live_fact_answer(
        "покажи throughput stale error rate и contract enforce",
        ops={
            "throughput_1h": 4,
            "throughput_24h": 37,
            "stale_in_progress": 0,
            "failed_1h": 1,
            "completed_1h": 4,
            "error_rate_1h": 0.2,
            "contract_enforced_24h": 12,
            "completed_24h": 37,
            "cancelled_1h_total": 6,
            "cancelled_1h_work": 2,
            "cancelled_1h_policy": 4,
            "cancelled_24h_total": 134,
            "cancelled_24h_work": 48,
            "cancelled_24h_policy": 86,
            "cancelled_24h_uncategorized": 2,
        },
    )
    assert "throughput_1h=4" in ans
    assert "throughput_24h=37" in ans
    assert "stale_in_progress=0" in ans
    assert "error_rate_1h=0.2" in ans
    assert "contract_enforced_24h=12/37" in ans
    assert "cancelled_1h_total=6" in ans
    assert "cancelled_1h_work=2" in ans
    assert "cancelled_1h_policy=4" in ans
    assert "cancelled_24h_total=134" in ans
    assert "cancelled_24h_work=48" in ans
    assert "cancelled_24h_policy=86" in ans
    assert "cancelled_24h_uncategorized=2" in ans


def test_ttc_metrics_are_fact_seeking():
    assert is_fact_seeking_question(
        "curl -s http://127.0.0.1:8010/metrics | grep victoria_async_ttc_p95"
    )
    ans = format_live_fact_answer(
        "какие victoria_async_ttc p50 p95 samples",
        ttc={"p50": 11.5, "p95": 27.3, "samples": 4, "inflight_max": 0.0, "inflight_n": 0},
    )
    assert ans == "p50=11.5 p95=27.3 samples=4 inflight_max=0.0 inflight=0"
