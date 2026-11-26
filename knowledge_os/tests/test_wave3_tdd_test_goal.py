"""Wave 3: TDD must pass test_goal into Veronica, not bare test_path."""

from pathlib import Path

VS = Path(__file__).resolve().parents[2] / "src" / "agents" / "bridge" / "victoria_server.py"


def test_ask_veronica_uses_test_goal_not_path():
    text = VS.read_text(encoding="utf-8")
    start = text.index("# [v3 TDD] Если test_first")
    end = text.index("# === Цикл: gen → compile → runtime → test_run → fix ===", start)
    block = text[start:end]
    assert "await _ask_veronica(test_goal)" in block
    assert "await _ask_veronica(test_path)" not in block


def test_autonomous_code_emits_top_level_proof_ms():
    text = VS.read_text(encoding="utf-8")
    assert '"test_status": test_status' in text
    assert '"compile_ms": phase_ms.get("compile_ms")' in text
    assert "git_pr_list" in text and "GitTools.git_pr_list" in text


def test_deliverable_default_on_and_progress():
    text = VS.read_text(encoding="utf-8")
    assert 'os.getenv("TURN_DELIVERABLE", "1")' in text
    assert '_publish_progress("file_written")' in text
    assert '"progress": progress' in text
    assert "if test_path:" in text and "rel_paths.append(tp_rel)" in text
