"""db_query must run SQL only, not the rest of the prompt."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_TOOLS = ROOT / "src" / "agents" / "tools" / "system_tools.py"


def _load():
    spec = importlib.util.spec_from_file_location("system_tools_sql_extract", _TOOLS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.DataTools


def test_extract_strips_russian_instruction_after_sql():
    blob = (
        "db_query: SELECT status::text AS status, count(*)::int AS n "
        "FROM tasks WHERE status IN ('pending','in_progress','queued') GROUP BY 1. "
        "Верни сырой результат SQL дословно. Не пиши файлы. Не git_push. Не HANDOFF."
    )
    sql = _load().extract_readonly_sql(blob)
    assert sql.upper().startswith("SELECT")
    assert "Верни" not in sql
    assert "HANDOFF" not in sql
    assert "GROUP BY 1" in sql.upper()


def test_extract_stops_at_semicolon():
    blob = "db_query: SELECT 1; DROP TABLE tasks; Верни всё"
    sql = _load().extract_readonly_sql(blob)
    assert sql == "SELECT 1"


def test_quick_tools_use_extract_readonly_sql():
    server = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
    text = server.read_text(encoding="utf-8")
    fn = text.split("async def _run_quick_tools_for_goal", 1)[1].split(
        "def _is_direct_tool_reply_candidate", 1
    )[0]
    assert "DataTools.extract_readonly_sql(goal)" in fn


def test_extract_keeps_clean_sql():
    blob = "SELECT status, count(*) FROM tasks WHERE status = 'pending' GROUP BY 1"
    assert _load().extract_readonly_sql(blob) == blob
