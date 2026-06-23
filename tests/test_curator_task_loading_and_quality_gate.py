import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "curator_send_tasks_to_victoria.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("curator_send", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_multiline_strict_task_file_loaded_as_single_goal(tmp_path):
    mod = _load_module()
    task_file = tmp_path / "tasks.txt"
    task_file.write_text(
        "\n".join(
            [
                "Критический режим без уточнений: начинай выполнение сразу.",
                "Проверь дашборд полностью и исправь SQL/миграции/метрики.",
                "Верни quality gate и файлы изменений.",
            ]
        ),
        encoding="utf-8",
    )

    tasks = mod._load_tasks_from_file(task_file)
    assert len(tasks) == 1
    assert "Критический режим без уточнений" in tasks[0]
    assert "quality gate" in tasks[0].lower()


def test_effective_wait_escalates_to_60_minutes_for_complex_goal():
    mod = _load_module()
    goal = "Выполни полный аудит дашборда, исправь SQL, миграции и quality gate по всем вкладкам."
    wait = mod._effective_max_wait(goal, configured_wait=300.0, quick_mode=False)
    assert wait == 3600.0


def test_effective_wait_escalates_to_60_minutes_for_very_complex_goal():
    mod = _load_module()
    goal = (
        "Критическая задача: проверь полностью от и до каждый пункт и каждый блок всех вкладок дашборда, "
        "внеси исправления SQL и миграций, проверь контейнеры, выдай quality gate production-ready отчет, "
        "доделай полностью каждый винтик."
    )
    wait = mod._effective_max_wait(goal, configured_wait=300.0, quick_mode=False)
    assert wait == 3600.0


def test_classify_terminal_error_marks_victoria_stale():
    mod = _load_module()
    err = mod._classify_terminal_error(
        {"error": "Task timed out after 60m (auto-cleanup)"}, "failed"
    )
    assert err.startswith("victoria_stale:")


def test_quality_gate_rejects_clarification_for_no_clarify_goal():
    mod = _load_module()
    goal = "Без уточнений: выполни полный аудит и исправления."
    out = {
        "status": "success",
        "output": "Victoria уточняет: ...",
        "knowledge": {"needs_clarification": True},
    }
    reason = mod._violates_output_quality_gate(goal, out)
    assert reason == "clarification_returned_for_no_clarify_goal"


def test_quality_gate_rejects_clarification_for_operational_goal():
    mod = _load_module()
    goal = "Проверь SQL и метрики дашборда Обзор."
    out = {
        "status": "success",
        "output": "Victoria уточняет: Какие требования к результату?",
        "knowledge": {"needs_clarification": True},
    }
    reason = mod._violates_output_quality_gate(goal, out)
    assert reason == "clarification_returned_for_operational_goal"


def test_quality_gate_rejects_obvious_offtopic_for_operational_goal():
    mod = _load_module()
    goal = "Проверь SQL и health-статусы dashboard Обзор."
    out = {
        "status": "success",
        "output": (
            "Принято ТЗ по Project Golden Standard для стратегического планирования 2026. "
            "Выполняю архитектурный прототип уровня Singularity 14.0."
        ),
        "knowledge": {},
    }
    reason = mod._violates_output_quality_gate(goal, out)
    assert reason == "offtopic_output_for_operational_goal"


def test_quality_gate_rejects_insufficient_data_pseudo_success_for_operational_goal():
    mod = _load_module()
    goal = "Проверь SQL и health-статусы dashboard Обзор."
    out = {
        "status": "success",
        "output": (
            "Для выполнения сверки необходимо получить фактические значения. "
            "Пользователь не предоставил исходные данные, поэтому сообщаю о необходимости их предоставить."
        ),
        "knowledge": {},
    }
    reason = mod._violates_output_quality_gate(goal, out)
    assert reason == "insufficient_data_pseudo_success_for_operational_goal"


def test_is_hard_server_timeout_detects_enhanced_cap():
    mod = _load_module()
    err = "Victoria Enhanced не уложилась в 1200s. Проверьте RAG_RERANKER_ENABLED и MLX/Ollama."
    assert mod._is_timeout_like_error(err) is True
    assert mod._is_hard_server_timeout(err) is True


def test_should_escalate_timeout_only_for_transient_errors():
    mod = _load_module()
    transient_err = "HTTPConnectionPool(host='localhost', port=8010): Read timed out. (read timeout=10)"
    hard_err = "Victoria Enhanced не уложилась в 1200s. Проверьте RAG_RERANKER_ENABLED и MLX/Ollama."

    assert (
        mod._should_escalate_timeout(
            async_mode=True,
            status="error",
            error=transient_err,
            escalation_attempt=0,
        )
        is True
    )
    assert (
        mod._should_escalate_timeout(
            async_mode=True,
            status="error",
            error=hard_err,
            escalation_attempt=0,
        )
        is False
    )


def test_poll_interval_helpers_respect_bounds():
    mod = _load_module()
    assert mod._bounded_poll_interval(0.1) == mod.POLL_INTERVAL_MIN
    assert mod._bounded_poll_interval(999.0) == mod.POLL_INTERVAL_MAX
    # reset must return min, normal step must stay bounded.
    assert mod._next_poll_interval(17.0, reset=True) == mod.POLL_INTERVAL_MIN
    stepped = mod._next_poll_interval(mod.POLL_INTERVAL_MAX, reset=False)
    assert stepped == mod.POLL_INTERVAL_MAX
