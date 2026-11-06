"""v150.87: autonomous-code пишет только через SOURCE_GUARD, без escape workspace."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, "knowledge_os", "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

from source_guard import guard_workspace_write, resolve_workspace_write_path  # noqa: E402


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
