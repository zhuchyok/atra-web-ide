"""File-audit rule results are substantive (not soft DEGRADED)."""

from app.task_rule_executor import finalize_rule_result, is_substantive_rule_result


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
    assert "[DEGRADED_RULE_FALLBACK]" not in out


def test_soft_status_template_still_degraded():
    text = "Rule-based статусный ответ (AI временно недоступен, 2026-01-01):\nЗапрос: ping"
    assert is_substantive_rule_result(text) is False
    out, meta, status = finalize_rule_result(text)
    assert status == "cancelled"
    assert meta.get("quality_degraded") is True
    assert out.lstrip().startswith("[DEGRADED_RULE_FALLBACK]")
