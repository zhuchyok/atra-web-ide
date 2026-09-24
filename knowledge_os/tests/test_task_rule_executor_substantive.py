"""Rule executor behavior for substantive and delegation tasks."""

import pytest
from app.task_rule_executor import (
    can_handle,
    execute_fallback,
    finalize_rule_result,
    is_substantive_rule_result,
)


def test_file_audit_ok_is_substantive():
    text = (
        "ОК\n"
        "Файл: /app/knowledge_os/app/expert_stream_routing.py\n"
        "Проверка: pip install в рантайме (первые 30 строк)\n"
        "Нарушений не найдено."
    )
    assert is_substantive_rule_result(text) is True
    out, meta, status = finalize_rule_result(text)
    assert status == "completed"
    assert meta.get("kpi_success") is True
    assert meta.get("task_contract_version") == "smart_worker_v1"
    assert meta.get("task_contract_output_schema") == "free_text"
    assert "[DEGRADED_RULE_FALLBACK]" not in out


def test_soft_status_template_still_degraded():
    text = "Rule-based статусный ответ (AI временно недоступен, 2026-01-01):\nЗапрос: ping"
    assert is_substantive_rule_result(text) is False
    out, meta, status = finalize_rule_result(text)
    assert status == "cancelled"
    assert meta.get("quality_degraded") is True
    assert meta.get("auto_fallback_reason") == "rule_fallback_cancelled"
    assert meta.get("manual_cancel_reason") == "policy_rule_fallback"
    assert out.lstrip().startswith("[DEGRADED_RULE_FALLBACK]")


def test_monster_delegation_wrapper_not_misclassified_as_status_task():
    task = {
        "metadata": {"source": "victoria_monster_delegation"},
        "title": "🤖 Делегировано: Алексей (main)",
        "description": (
            "Задача от Team Lead Victoria: Факты до вывода: прочитай файлы, логи, health, статус."
        ),
    }
    assert can_handle(task) is False


@pytest.mark.asyncio
async def test_monster_delegation_allows_file_audit_fast_path():
    task = {
        "metadata": {"source": "victoria_monster_delegation"},
        "title": "🤖 Делегировано: QA",
        "description": "проверь файл /app/file.py — есть ли секреты",
    }
    assert can_handle(task) is True
    result = await execute_fallback(task)
    assert result is not None
