from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"


def test_planning_goal_helper_and_execution_override_present():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "def _is_planning_guidance_goal(goal: str) -> bool:" in text
    assert "planning_markers = (" in text
    assert "hard_exec_markers = (" in text
    assert "_is_planning_goal = _is_planning_guidance_goal(_user_msg_text)" in text
    assert "and not _is_planning_goal" in text
    assert "if _is_planning_goal:" in text
    assert '_model = os.getenv("VICTORIA_SYNC_SAFE_MODEL", "phi3.5:3.8b")' in text
    assert "def _build_openwebui_victoria_plan_response(goal_text: str) -> Optional[str]:" in text
    assert "operational_plan = _build_openwebui_victoria_plan_response(goal)" in text
    assert 'if any(m in g for m in ("timeout", "таймаут")):' in text
    assert 'if any(m in g for m in ("connection error", "server connection error", "cannot connect")):' in text
    assert 'if any(m in g for m in ("stabiliz", "стабилиз", "стабильност")):' in text
