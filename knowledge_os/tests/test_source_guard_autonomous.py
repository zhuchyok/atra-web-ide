"""v150.87: autonomous-code пишет только через SOURCE_GUARD, без escape workspace."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, "knowledge_os", "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

from source_guard import (  # noqa: E402
    PROTECTED_SOURCE_PREFIXES,
    guard_file_write,
    guard_workspace_write,
    resolve_workspace_write_path,
)


def test_relative_core_path_refused(tmp_path):
    ws = str(tmp_path)
    os.makedirs(os.path.join(ws, "src", "agents", "bridge"), exist_ok=True)
    ok, reason, _resolved = guard_workspace_write(
        ws,
        "src/agents/bridge/victoria_server.py",
        "def ping():\n    return 1\n",
        overwrite_check=False,
    )
    assert ok is False
    assert "protected source path" in reason
    assert "src/agents/" in reason


def test_absolute_core_path_refused(tmp_path):
    ws = str(tmp_path)
    target = os.path.join(ws, "src", "agents", "core.py")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    ok, reason, _resolved = guard_workspace_write(
        ws, target, "def ping():\n    return 1\n", overwrite_check=False
    )
    assert ok is False
    assert "protected source path" in reason


def test_absolute_escape_refused(tmp_path):
    ws = str(tmp_path)
    ok, reason, resolved = resolve_workspace_write_path(ws, "/etc/passwd")
    assert ok is False
    assert "escapes workspace" in reason
    assert resolved == ""


def test_dotdot_escape_refused(tmp_path):
    ws = str(tmp_path)
    ok, reason, resolved = resolve_workspace_write_path(ws, "../../etc/passwd")
    assert ok is False
    assert "escapes workspace" in reason
    assert resolved == ""


def test_generated_src_py_allowed(tmp_path):
    ws = str(tmp_path)
    os.makedirs(os.path.join(ws, "src"), exist_ok=True)
    code = "def add(a, b):\n    return a + b\n"
    ok, reason, resolved = guard_workspace_write(ws, "src/auto_guard_probe.py", code)
    assert ok is True, reason
    assert reason == "ok"
    assert resolved.endswith("src/auto_guard_probe.py")
    assert os.path.commonpath([ws, resolved]) == os.path.realpath(ws)


def test_empty_path_refused(tmp_path):
    ok, reason, resolved = resolve_workspace_write_path(str(tmp_path), "")
    assert ok is False
    assert "empty" in reason
    assert resolved == ""


def test_autonomous_code_calls_workspace_guard():
    src = (
        __import__("pathlib").Path(ROOT) / "src" / "agents" / "bridge" / "victoria_server.py"
    ).read_text(encoding="utf-8")
    fn = src.split("def _autonomous_guard_write", 1)[1].split(
        "async def _fetch_experience_lessons", 1
    )[0]
    assert "guard_workspace_write" in fn
    assert "SOURCE_GUARD" in fn
    assert "source_guard unavailable" in fn


def test_scripts_prefix_in_protected_list():
    assert "scripts/" in PROTECTED_SOURCE_PREFIXES
    assert "knowledge_os/scripts/" in PROTECTED_SOURCE_PREFIXES


def test_scripts_avito_lead_responder_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("ATRA_ALLOW_SOURCE_WRITE", raising=False)
    ws = str(tmp_path)
    os.makedirs(os.path.join(ws, "scripts"), exist_ok=True)
    code = "print('should not write')\n"
    ok, reason, _resolved = guard_workspace_write(
        ws, "scripts/avito_lead_responder.py", code, overwrite_check=False
    )
    assert ok is False
    assert "protected source path" in reason
    assert "scripts/" in reason

    allowed, g_reason = guard_file_write(
        os.path.join(ws, "scripts", "avito_lead_responder.py"), code, overwrite_check=False
    )
    assert allowed is False
    assert "protected source path" in g_reason


def test_non_protected_tmp_probe_allowed(tmp_path, monkeypatch):
    monkeypatch.delenv("ATRA_ALLOW_SOURCE_WRITE", raising=False)
    ws = str(tmp_path)
    os.makedirs(os.path.join(ws, "tmp"), exist_ok=True)
    code = "def ping():\n    return 1\n"
    ok, reason, resolved = guard_workspace_write(ws, "tmp/safe_probe.py", code)
    assert ok is True, reason
    assert reason == "ok"
    assert resolved.endswith("tmp/safe_probe.py")


def test_react_agent_write_file_calls_source_guard():
    src = (__import__("pathlib").Path(ROOT) / "knowledge_os" / "app" / "react_agent.py").read_text(
        encoding="utf-8"
    )
    assert "_source_guard_write_error" in src
    assert "guard_file_write" in src
    # create_file/write_file + smart-patch/patch_file must call the guard helper
    assert src.count("self._source_guard_write_error(") >= 3
    assert 'action == "smart-patch" or action == "patch_file"' in src


def test_react_smart_patch_refuses_scripts_avito(tmp_path, monkeypatch):
    """smart-patch must refuse scripts/avito_lead_responder.py via SOURCE_GUARD."""
    import asyncio

    monkeypatch.delenv("ATRA_ALLOW_SOURCE_WRITE", raising=False)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    target = scripts_dir / "avito_lead_responder.py"
    original = "def ping():\n    return 1\n"
    target.write_text(original, encoding="utf-8")

    from react_agent import ReActAgent

    agent = ReActAgent(agent_name="test-guard", max_iterations=1)
    patch = (
        "<<<<<<< SEARCH\n"
        "def ping():\n    return 1\n"
        "=======\n"
        "def ping():\n    return 2\n"
        ">>>>>>> REPLACE"
    )
    result = asyncio.run(
        agent._execute_action(
            "smart-patch",
            {"file_path": str(target), "patch_content": patch},
        )
    )
    assert "SOURCE_GUARD" in str(result)
    assert "protected source path" in str(result) or "scripts/" in str(result)
    assert target.read_text(encoding="utf-8") == original
