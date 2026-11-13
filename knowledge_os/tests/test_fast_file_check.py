"""v136: file-check fast path must read description/parent_goal, not only title."""

from app.smart_worker_autonomous import _fast_file_check, _fast_file_check_from_task


def test_delegated_title_alone_is_not_a_file_check():
    assert _fast_file_check("🤖 Делегировано: Алексей (main)") is None


def test_fast_file_check_from_delegated_task(tmp_path, monkeypatch):
    target = tmp_path / "ui_audit_agent.py"
    target.write_text("print('hello')\n", encoding="utf-8")
    path = "/app/knowledge_os/app/ui_audit_agent.py"
    task = {
        "title": "🤖 Делегировано: Алексей (main)",
        "description": f"проверь файл {path} — есть ли там pip install в рантайме?",
        "metadata": {
            "source": "victoria_monster_delegation",
            "parent_goal": f"проверь файл {path} — есть ли там pip install в рантайме?",
        },
    }

    import builtins

    import app.smart_worker_autonomous as sw

    real_open = builtins.open
    orig_exists = sw.os.path.exists

    def fake_exists(p):
        return p == path

    def fake_open(file, *args, **kwargs):
        if str(file) == path:
            return real_open(target, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(sw.os.path, "exists", fake_exists)
    monkeypatch.setattr(builtins, "open", fake_open)

    result = _fast_file_check_from_task(task)
    assert result is not None
    assert result.startswith("ОК")
    assert orig_exists is not None


def test_fast_file_check_reports_missing_file():
    result = _fast_file_check(
        "проверь файл /app/knowledge_os/app/definitely_missing_target.py — есть ли там pip install в рантайме?"
    )
    assert result == "ФАЙЛ НЕ НАЙДЕН: /app/knowledge_os/app/definitely_missing_target.py"


def test_fast_file_check_ignores_negative_guard_condition(tmp_path, monkeypatch):
    target = tmp_path / "guard_only.py"
    target.write_text('if "pip install" not in text:\\n    return "ok"\\n', encoding="utf-8")
    path = "/app/knowledge_os/app/guard_only.py"

    import builtins
    import app.smart_worker_autonomous as sw

    real_open = builtins.open

    def fake_exists(p):
        return p == path

    def fake_open(file, *args, **kwargs):
        if str(file) == path:
            return real_open(target, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(sw.os.path, "exists", fake_exists)
    monkeypatch.setattr(builtins, "open", fake_open)

    result = _fast_file_check(
        f"проверь файл {path} — есть ли там pip install в рантайме?"
    )
    assert result == "ОК"
