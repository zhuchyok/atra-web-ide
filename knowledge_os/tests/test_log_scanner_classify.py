"""v150.89: scanner classifies noise/runbook/human/patch. No 'исправь' by default."""

import importlib.util
from pathlib import Path

_SCANNER = Path(__file__).resolve().parents[2] / "knowledge_os" / "app" / "medic" / "log_scanner.py"
_spec = importlib.util.spec_from_file_location("log_scanner_classify_under_test", _SCANNER)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def _err(message: str, typ: str = "LOG_ERROR") -> dict:
    return {"type": typ, "message": message, "timestamp": "t"}


def test_source_guard_is_noise():
    assert (
        _mod.classify_scanner_incident(
            "victoria-agent",
            _err("ERROR - 🛡️ [SOURCE_GUARD] ОТКАЗ (protected source path (src/agents/))"),
        )
        == "noise"
    )


def test_redis_disconnect_is_noise():
    assert (
        _mod.classify_scanner_incident(
            "knowledge_os-expert-worker-dynamic-1-1",
            _err("Bridge loop error: Connection closed by server."),
        )
        == "noise"
    )


def test_connection_refused_is_runbook():
    assert (
        _mod.classify_scanner_incident(
            "victoria-agent",
            _err("ConnectionRefusedError: 127.0.0.1:11434"),
        )
        == "runbook"
    )


def test_core_path_is_human_even_with_typeerror():
    msg = (
        'File "/workspace/atra-web-ide/src/agents/bridge/victoria_server.py", line 10\n'
        "TypeError: boom"
    )
    assert _mod.classify_scanner_incident("victoria-agent", _err(msg, "TypeError")) == "human"


def test_generated_src_typeerror_is_patch():
    msg = 'File "/workspace/atra-web-ide/src/auto_guard_probe.py", line 4, in add\nTypeError: bad'
    assert _mod.classify_scanner_incident("dynamic-1", _err(msg, "TypeError")) == "patch"
    assert _mod.extract_code_path(msg).endswith("src/auto_guard_probe.py")


def test_no_file_defaults_human():
    assert (
        _mod.classify_scanner_incident(
            "knowledge_os_orchestrator",
            _err("TypeError: run_smart_agent_async() got an unexpected keyword argument 'model'"),
        )
        == "human"
    )


def test_scanner_run_payload_is_async():
    err = _err("TypeError: x", "TypeError")
    payload = _mod.scanner_run_payload("c1", err, "human")
    assert payload["async_mode"] is True
    assert payload["context"]["source"] == "log_scanner"
    assert payload["scanner_class"] == "human"
    assert "исправ" not in payload["goal"].lower()


_SHELL_GIT_WRITE = (
    "run_terminal_cmd",
    "ssh_run",
    "git_add",
    "git_commit",
    "git_branch_create",
    "git_pr_create",
)


def test_blocked_tools_for_scanner_class():
    human = _mod.blocked_tools_for_scanner_class("human")
    runbook = _mod.blocked_tools_for_scanner_class("runbook")
    patch = _mod.blocked_tools_for_scanner_class("patch")
    assert "write_file" in human and "apply_patch" in human and "git_push" in human
    assert human == runbook
    assert "git_push" in patch
    assert "git_status" in patch
    assert "git_diff" in patch
    assert "git_log" in patch
    assert "write_file" not in patch
    assert _mod.blocked_tools_for_scanner_class("") == []
    assert _mod.blocked_tools_for_scanner_class("noise") == []


def test_human_runbook_block_shell_and_git_write():
    """Human/runbook diagnose without shell; patch keeps pytest shell."""
    for klass in ("human", "runbook"):
        tools = _mod.blocked_tools_for_scanner_class(klass)
        for name in _SHELL_GIT_WRITE:
            assert name in tools, name
        assert "write_file" in tools
    patch = _mod.blocked_tools_for_scanner_class("patch")
    for name in _SHELL_GIT_WRITE:
        assert name not in patch
    assert "git_push" in patch
    assert "git_status" in patch
    assert "write_file" not in patch


def test_git_push_rejected_is_noise():
    assert (
        _mod.classify_scanner_incident(
            "victoria-agent",
            _err("Error: git_push rejected (ATRA_ALLOW_GIT_PUSH not set). Human push only."),
        )
        == "noise"
    )


def test_goals_never_say_fix_or_analyze():
    for klass in ("runbook", "human", "patch"):
        goal = _mod.build_scanner_goal(
            "c1",
            _err("TypeError: x", "TypeError"),
            klass,
            "src/auto_guard_probe.py" if klass == "patch" else "",
        )
        low = goal.lower()
        assert "исправ" not in low
        assert "проанализ" not in low
        assert "анализ" not in low
        assert f"class={klass}" in goal
    patch = _mod.build_scanner_goal(
        "c1", _err("TypeError: x", "TypeError"), "patch", "src/auto_guard_probe.py"
    )
    assert "write_file" in patch
    assert "autonomous-code" in patch
    assert "git_push" in patch
    assert "git_status" in patch
    assert "HANDOFF" in patch


def test_human_and_patch_goals_require_evidence_fields():
    """Agency steal: command + output + PASS/FAIL + untested. No consilium words."""
    for klass in ("human", "patch"):
        goal = _mod.build_scanner_goal(
            "c1",
            _err("TypeError: x", "TypeError"),
            klass,
            "src/auto_guard_probe.py" if klass == "patch" else "",
        )
        assert "command" in goal
        assert "output" in goal
        assert "PASS" in goal
        assert "FAIL" in goal
        assert "untested" in goal
        low = goal.lower()
        assert "pytest" not in low
        assert "security" not in low
        assert "research" not in low
        assert "тест" not in low


def test_runbook_goal_skips_evidence_schema():
    goal = _mod.build_scanner_goal("c1", _err("connection refused"), "runbook")
    assert "untested" not in goal
    assert "PASS" not in goal


def test_patch_class_forces_direct_not_enhanced():
    assert _mod.scanner_class_forces_direct("patch") is True
    assert _mod.scanner_class_forces_direct("human") is False
    assert _mod.scanner_class_forces_direct("runbook") is False
    assert _mod.scanner_class_forces_direct("") is False


def test_patch_handoff_is_rejected_human_is_not():
    igor = (
        "HANDOFF: @Igor\n"
        "TASK: Fix TypeError in src/auto_guard_probe.py\n"
        'CONTRACT: {"expected_output": "Fixed code", "format": "text"}'
    )
    assert _mod.scanner_patch_handoff_rejected("patch", igor) is True
    assert _mod.scanner_patch_handoff_rejected("human", igor) is False
    assert _mod.scanner_patch_handoff_rejected("runbook", igor) is False
    assert (
        _mod.scanner_patch_handoff_rejected("patch", "OK: File written: src/auto_guard_probe.py")
        is False
    )
    assert _mod.scanner_patch_handoff_rejected("patch", "") is False
    assert _mod.scanner_patch_handoff_rejected("", igor) is False


def test_scanner_goals_do_not_trip_consilium():
    import sys

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from src.agents.bridge.task_detector import is_consilium_winnable_goal

    for klass in ("runbook", "human", "patch"):
        goal = _mod.build_scanner_goal(
            "c1",
            _err("TypeError: x", "TypeError"),
            klass,
            "src/auto_guard_probe.py" if klass == "patch" else "",
        )
        assert is_consilium_winnable_goal(goal) is None, klass


def test_write_file_missing_tool_is_ignored_and_noise():
    scanner = _mod.LogScanner()
    line = "ERROR src.agents.core.base_agent: ❌ Инструмент write_file не найден."
    assert scanner.extract_error(line) is None
    assert _mod.classify_scanner_incident("victoria-agent", _err(line, "LOG_ERROR")) == "noise"


def test_norm_in_typeerror_echo_is_ignored():
    scanner = _mod.LogScanner()
    line = (
        "WARNING norm_dbg: NORM_IN len=412 "
        'head=\'TypeError: unsupported operand type(s) for +: "int" and "NoneType"\' '
        "from=['executor.py:836']"
    )
    assert scanner.extract_error(line) is None
    assert _mod.classify_scanner_incident("victoria-agent", _err(line, "TypeError")) == "noise"


def test_typeerror_msg_and_thought_echo_ignored_bare_typeerror_still_hits():
    scanner = _mod.LogScanner()
    assert (
        scanner.extract_error(
            "Msg: TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'"
        )
        is None
    )
    assert scanner.extract_error("🤔 Мысль: fix TypeError: bad") is None
    live = scanner.extract_error(
        "TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'"
    )
    assert live is not None
    assert live["type"] == "TypeError"
    assert _mod.classify_scanner_incident("knowledge_os_orchestrator", live) == "human"


def test_filenotfounderror_prose_noise_colon_form_still_extracted():
    scanner = _mod.LogScanner()
    prose = "🤔 Мысль: The reason is FileNotFoundError because the probe path does not exist"
    assert scanner.extract_error(prose) is None
    assert _mod.classify_scanner_incident("victoria-agent", _err(prose, "UNKNOWN")) == "noise"
    real = "FileNotFoundError: [Errno 2] No such file or directory: '/tmp/missing.py'"
    hit = scanner.extract_error(real)
    assert hit is not None
    assert hit["type"] == "FileNotFoundError"
    assert _mod.classify_scanner_incident("victoria-agent", hit) == "human"


def test_recursion_stop_guard_is_ignored_and_noise():
    scanner = _mod.LogScanner()
    line = (
        "ERROR knowledge_os.app.task_distribution_system_complete: "
        "TaskDistribution: RECURSION-STOP — 2 вложений в промпте, задач не извлекаем"
    )
    assert scanner.extract_error(line) is None
    assert _mod.classify_scanner_incident("victoria-agent", _err(line, "LOG_ERROR")) == "noise"


def test_idle_in_transaction_and_smart_agent_none_ignored():
    scanner = _mod.LogScanner()
    idle = "FATAL:  terminating connection due to idle-in-transaction timeout"
    smart = "ERROR ⚠️ [SMART_AGENT] response=None (type=NoneType) — локальные модели не дали ответ"
    name_col = 'ERROR:  column "name" does not exist at character 12'
    ollama500 = (
        "ERROR - [ROUTER] ❌ Node Mac Studio (Ollama) returned HTTP 500: "
        '{"error":"llama-server process no longer running: unknown "}'
    )
    dna = (
        "Вы - Виктория (Team Lead). Найдите неочевидную связь между двумя фактами: "
        "ФАКТ А (Management): test"
    )
    json_err = "json.decoder.JSONDecodeError: Expecting value: line 1 column 2 (char 1)"
    judge = "ERROR:ExpertWorker:⚠️ [JUDGE-GATE] Task f45b1b3d: завершение со score=3"
    echo_err = '"reason": "Чтобы понять контекст ERROR и уровень знаний ExpertWorker"'
    ask_err = '"Какой именно ERROR нужно разобрать: команду, вывод и статус PASS/FAIL?"'
    veronica_rt = "ERROR ❌ [VERONICA] Ошибка: ReadTimeout('')"
    echo_q = '"Есть ли полный лог вокруг ERROR:asyncio:Task was destroyed but it is pending?",'
    destroyed = "ERROR:asyncio:Task was destroyed but it is pending!"
    recruit = "ERROR:__main__:❌ Error parsing recruitment output: Expecting value: line 1 column 1 (char 0)"
    for line in (
        idle,
        smart,
        name_col,
        ollama500,
        dna,
        json_err,
        judge,
        echo_err,
        ask_err,
        veronica_rt,
        echo_q,
        destroyed,
        recruit,
    ):
        assert scanner.extract_error(line) is None, line


def test_scanner_writes_last_snapshot_file():
    text = _SCANNER.read_text(encoding="utf-8")
    assert "log_scanner_last.json" in text
    assert "new_errors" in text
    assert "_SCANNER_SNAP.write_text" in text


def test_unprotected_typeerror_with_file_stays_patch():
    msg = 'File "/workspace/atra-web-ide/src/auto_guard_probe.py", line 4, in add\nTypeError: bad'
    assert _mod.classify_scanner_incident("dynamic-1", _err(msg, "TypeError")) == "patch"
    assert _mod.LogScanner().extract_error("TypeError: bad") is not None


def test_patch_blocks_git_read_keeps_write_and_pytest_shell():
    patch = _mod.blocked_tools_for_scanner_class("patch")
    for name in ("git_push", "git_status", "git_diff", "git_log"):
        assert name in patch, name
    assert "write_file" not in patch
    assert "apply_patch" not in patch
    assert "run_terminal_cmd" not in patch
    human = _mod.blocked_tools_for_scanner_class("human")
    assert "git_status" not in human
