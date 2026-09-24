from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXECUTE_ASSIGNMENTS = ROOT / "knowledge_os" / "app" / "execute_assignments.py"


def test_monster_delegation_persists_goal_on_upsert_and_insert():
    text = EXECUTE_ASSIGNMENTS.read_text(encoding="utf-8")
    assert "delegation_goal = (compact_goal or \"\").strip()[:1000] or subtask_desc[:1000]" in text
    assert "goal = COALESCE(NULLIF($5, ''), goal)" in text
    assert "INSERT INTO tasks (title, description, goal, status, priority" in text
