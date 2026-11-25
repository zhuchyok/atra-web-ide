"""Wave 2: local FS plan executor + approve gate."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOD = ROOT / "src" / "agents" / "bridge" / "execution_plan_local.py"


def _load():
    spec = importlib.util.spec_from_file_location("execution_plan_local", MOD)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_resolve_blocks_escape(tmp_path: Path):
    m = _load()
    try:
        m.resolve_workspace_path(str(tmp_path), "../outside.txt")
        assert False, "expected escape error"
    except ValueError:
        pass


def test_read_real_file(tmp_path: Path):
    m = _load()
    (tmp_path / "hello.txt").write_text("alpha-beta", encoding="utf-8")
    out = m.execute_plan_local(
        [{"action": "read_file", "path": "hello.txt"}],
        str(tmp_path),
        approve_writes=False,
    )
    assert "alpha-beta" in out[0]
    assert out[0].startswith("✅")


def test_edit_needs_approve(tmp_path: Path):
    m = _load()
    f = tmp_path / "x.txt"
    f.write_text("old", encoding="utf-8")
    out = m.execute_plan_local(
        [{"action": "edit", "path": "x.txt", "content": "new"}],
        str(tmp_path),
        approve_writes=False,
    )
    assert "needs_approve" in out[0]
    assert f.read_text(encoding="utf-8") == "old"


def test_edit_with_approve(tmp_path: Path):
    m = _load()
    f = tmp_path / "x.txt"
    f.write_text("old", encoding="utf-8")
    out = m.execute_plan_local(
        [{"action": "edit", "path": "x.txt", "content": "new"}],
        str(tmp_path),
        approve_writes=True,
    )
    assert out[0].startswith("✅")
    assert f.read_text(encoding="utf-8") == "new"


def test_run_git_not_allowed_even_with_approve(tmp_path: Path):
    """approve_writes ≠ ATRA_ALLOW_GIT_MUTATE — no git shell via plan."""
    m = _load()
    assert "git" not in m.ALLOWED_COMMANDS
    out = m.execute_plan_local(
        [{"action": "run", "command": "git commit -m x"}],
        str(tmp_path),
        approve_writes=True,
    )
    assert "not allowed" in out[0].lower() or "❌" in out[0]


def test_python_cannot_smuggle_git_without_mutate_env(tmp_path: Path, monkeypatch):
    m = _load()
    monkeypatch.delenv("ATRA_ALLOW_GIT_MUTATE", raising=False)
    out = m.execute_plan_local(
        [
            {
                "action": "run",
                "command": "python -c \"__import__('os').system('git add -A')\"",
            }
        ],
        str(tmp_path),
        approve_writes=True,
    )
    assert "ATRA_ALLOW_GIT_MUTATE" in out[0] or "blocked" in out[0].lower() or "❌" in out[0]
