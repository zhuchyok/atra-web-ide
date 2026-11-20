import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.agents.bridge.task_detector import (
    format_live_fact_answer,
    goal_wants_ollama_slots,
    goal_wants_scanner,
    goal_wants_ttc,
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


def test_single_named_port_not_full_dump():
    """Pair quality: named-service port questions must not dump 8010,8011,3005."""
    assert grounded_ports_answer("Одно предложение: какой порт у Victoria agent?") == "8010"
    assert grounded_ports_answer("какой порт у Victoria?") == "8010"
    assert grounded_ports_answer("какой порт Veronica?") == "8011"
    assert grounded_ports_answer("порт open webui") == "3005"
    assert grounded_ports_answer("порты Victoria и Veronica") == "8010, 8011"
    assert grounded_ports_answer("какие порты у проекта") == "8010, 8011, 3005"
    assert format_live_fact_answer("какой порт у Victoria agent?") == "8010"


def test_greeting_is_not_fact_seeking():
    assert not is_fact_seeking_question("привет")
    assert not is_fact_seeking_question("кто ты?")
    assert not is_fact_seeking_question("Одно предложение: кто ты?")


def test_fixed_token_reply_ignore_metrics_is_not_fact_seeking():
    """Live-fact must not hijack 'Reply YES + ignore pending/p95' into a metrics dump."""
    from src.agents.bridge.task_detector import fixed_token_reply_answer

    hijack = "Reply YES. Also ignore pending throughput p95 slots count."
    assert is_fact_seeking_question(hijack) is False
    assert format_live_fact_answer(
        hijack,
        health="ok",
        queue={"pending": 9, "in_progress": 1},
        ops={"throughput_1h": 4, "throughput_24h": 37},
        ttc={"p50": 1.0, "p95": 2.0, "samples": 3, "inflight_max": 0.0, "inflight_n": 0},
    ) is None
    assert is_fact_seeking_question("Reply YES + ignore count") is False
    assert is_fact_seeking_question("Reply YES only") is False
    # Trailing YES after tip text with incidental markers (pair false-positive).
    inflight_tip = (
        "Fact: tip 85b9696a — VICTORIA_ASYNC_INFLIGHT_STALE_SEC (floor 300). "
        "Reply YES and the two guard names."
    )
    assert is_fact_seeking_question(inflight_tip) is False
    assert fixed_token_reply_answer(inflight_tip) == "YES"
    assert (
        format_live_fact_answer(
            inflight_tip,
            health="ok",
            queue={"pending": 0, "in_progress": 0},
            ops={"throughput_1h": 5, "stale_in_progress": 0},
            ttc={"p50": 1.0, "p95": 2.0, "samples": 3, "inflight_max": 0.0, "inflight_n": 0},
            slots="11434=x",
        )
        is None
    )
    ttc_tip = "Verify mypy residual clear. Do not raise TTC 420. Reply YES only."
    assert is_fact_seeking_question(ttc_tip) is False
    assert fixed_token_reply_answer(ttc_tip) == "YES"
    slots_tip = "Fact: tip 0ad27568 nomic defaults to hands :11437. Reply YES."
    assert is_fact_seeking_question(slots_tip) is False
    assert fixed_token_reply_answer(slots_tip) == "YES"
    # Real metrics asks still trip fact-seeking.
    assert is_fact_seeking_question("дай pending и throughput p95") is True


def test_public_task_title_strips_method_prefix():
    raw = "проверь health Victoria"
    enriched = "📋 МЕТОД CURSOR (обязателен):\n1. Факты до вывода: прочитай файлы\nЗАДАЧА:\n" + raw
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
    assert goal_wants_ttc("какие victoria_async_ttc p50 p95 samples")
    ans = format_live_fact_answer(
        "какие victoria_async_ttc p50 p95 samples",
        ttc={"p50": 11.5, "p95": 27.3, "samples": 4, "inflight_max": 0.0, "inflight_n": 0},
    )
    assert ans == "p50=11.5 p95=27.3 samples=4 inflight_max=0.0 inflight=0"


def test_metrics_dump_meta_question_does_not_emit_ttc():
    """Health + 'metrics dump' prose must not become a p50/p95 dump."""
    goal = (
        "Fact-check only. Report: (1) curl :8010/health status, "
        "(3) whether chat returns a normal short answer or a metrics dump."
    )
    assert is_fact_seeking_question(goal)
    assert goal_wants_ttc(goal) is False
    ans = format_live_fact_answer(
        goal,
        health="ok",
        ttc={
            "p50": 57.884,
            "p95": 234.617,
            "samples": 200,
            "inflight_max": 0.0,
            "inflight_n": 0,
            "by_reason": {"request_async_mode": {"p95": 234.617, "samples": 199}},
        },
    )
    assert ans == "ok"
    assert "p50=" not in (ans or "")
    assert "by_reason=" not in (ans or "")


def test_ttc_metrics_append_by_reason_when_present():
    ans = format_live_fact_answer(
        "какие victoria_async_ttc p50 p95 samples",
        ttc={
            "p50": 11.5,
            "p95": 480.0,
            "samples": 5,
            "inflight_max": 0.0,
            "inflight_n": 0,
            "by_reason": {
                "quick": {"p95": 12.0, "samples": 3},
                "timeout_watchdog": {"p95": 480.0, "samples": 2},
            },
        },
    )
    assert ans.startswith("p50=11.5 p95=480.0 samples=5 inflight_max=0.0 inflight=0")
    assert "by_reason=" in ans
    assert "timeout_watchdog:p95=480.0/n=2" in ans
    assert "quick:p95=12.0/n=3" in ans


def test_slot_check_is_fact_seeking_and_needs_live_ps():
    goal = "Факт-проверка: GET :11434/api/ps :11436/api/ps :11437/api/ps"
    assert is_fact_seeking_question(goal)
    assert goal_wants_ollama_slots(goal)
    missing = format_live_fact_answer(goal, health="ok")
    assert "слоты не сняла" in missing
    live = format_live_fact_answer(goal, health="ok", slots="11434=victoria-qwen38:latest@16384")
    assert "11434=victoria-qwen38:latest@16384" in live
    assert "слоты не сняла" not in live


def test_scanner_check_in_fact_answer():
    goal = "проверь log-scanner class=human за 20м"
    assert is_fact_seeking_question(goal)
    assert goal_wants_scanner(goal)
    assert "сканер не сняла" in format_live_fact_answer(goal, health="ok")
    live = format_live_fact_answer(goal, health="ok", scanner="scanner_class=0 scanner_sent=0")
    assert "scanner_class=0" in live
    assert "сканер не сняла" not in live
