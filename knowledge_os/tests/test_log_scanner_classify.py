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
    assert "исправ" not in payload["goal"].lower()


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
