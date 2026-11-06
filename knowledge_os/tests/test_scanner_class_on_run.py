"""v150.99: /run keeps scanner_class; BaseAgent.run honors blocked_tools."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_task_request_has_scanner_class_field():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(encoding="utf-8")
    chunk = text.split("class TaskRequest", 1)[1].split("class TaskResponse", 1)[0]
    assert "scanner_class" in chunk


def test_victoria_run_passes_blocked_tools_to_super():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(encoding="utf-8")
    fn = text.split("async def run(\n        self,", 1)[1].split(
        "def _extract_last_answer_from_long", 1
    )[0]
    assert "blocked_tools" in fn
    assert "blocked_tools=blocked_tools" in fn
    assert "_blocked_tools_for_scanner_class" in text


def test_base_agent_run_seeds_blocked_tools():
    text = (ROOT / "src" / "agents" / "core" / "base_agent.py").read_text(encoding="utf-8")
    fn = text.split("async def run(", 1)[1].split("Превышен лимит шагов", 1)[0]
    assert "blocked_tools" in fn
    assert "agent._blocked_tools[tool]" in fn


def test_victoria_fallback_human_blocks_shell():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    fn = text.split("def _blocked_tools_for_scanner_class", 1)[1].split(
        "def _format_ide_context", 1
    )[0]
    for name in (
        "run_terminal_cmd",
        "ssh_run",
        "git_add",
        "git_commit",
        "git_branch_create",
        "git_pr_create",
    ):
        assert name in fn
    human_list = fn.split('if k in ("human", "runbook")', 1)[1].split("elif k ==", 1)[0]
    assert "run_terminal_cmd" in human_list
    patch_list = fn.split('elif k == "patch"', 1)[1].split("else:", 1)[0]
    assert "run_terminal_cmd" not in patch_list
    assert "write_file" not in patch_list
    assert "git_push" in patch_list
    assert "git_status" in patch_list
    assert "git_diff" in patch_list
    assert "git_log" in patch_list


def test_victoria_run_gates_patch_handoff():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    assert "scanner_patch_handoff_rejected" in text
    assert "cannot HANDOFF" in text
    assert "scanner_class_forces_direct" in text


def test_victoria_registers_write_file_and_apply_patch():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    init = text.split("class VictoriaAgent", 1)[1].split("async def _get_db_pool", 1)[0]
    assert 'add_tool("write_file"' in init
    assert 'add_tool("apply_patch"' in init
    assert "SystemTools.write_file" in init


def test_scanner_patch_verify_used_after_tool_loop():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    assert "def _scanner_patch_verify" in text
    fn = text.split("async def run(\n        self,", 1)[1].split(
        "def _extract_last_answer_from_long", 1
    )[0]
    assert "_scanner_patch_verify(inject, result)" in fn


def test_victoria_run_patch_skips_orchestrate_and_uses_json():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    fn = text.split("async def run(\n        self,", 1)[1].split(
        "def _extract_last_answer_from_long", 1
    )[0]
    assert "scanner_class" in fn
    assert "scanner_class_forces_direct" in fn
    assert "skip swarm/plan" in fn
    assert "PATCH_JSON_ONLY" in text
    assert "scanner_class=scanner_class" in text
    assert "scanner_class=body.scanner_class" in text
    orch_idx = fn.find("orchestrate_task")
    skip_idx = fn.find("skip swarm/plan")
    assert skip_idx != -1
    assert skip_idx < orch_idx


def test_executor_patch_json_retries_not_finish_raw():
    text = (ROOT / "src" / "agents" / "core" / "executor.py").read_text(encoding="utf-8")
    assert "PATCH_JSON_ONLY" in text
    assert "FORMAT_RETRY" in text
    parse = text.split("def _parse_response", 1)[1]
    retry_idx = parse.find("PATCH_JSON_ONLY")
    raw_idx = parse.find("Returning raw text response")
    assert retry_idx != -1
    assert retry_idx < raw_idx


def test_base_agent_format_retry_continues():
    text = (ROOT / "src" / "agents" / "core" / "base_agent.py").read_text(encoding="utf-8")
    fn = text.split("async def run(", 1)[1].split("Превышен лимит шагов", 1)[0]
    assert "FORMAT_RETRY" in fn
    assert "continue" in fn[fn.find("FORMAT_RETRY") :]


def test_orphan_resume_default_matches_ttc_not_hard_timeout():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    fn = text.split("async def _fail_orphaned_inflight_on_startup", 1)[1].split(
        "def _percentile", 1
    )[0]
    assert 'VICTORIA_ORPHAN_RESUME_MAX_AGE_SEC", "420"' in fn
    lifespan = text.split("async def lifespan", 1)[1].split("app = FastAPI", 1)[0]
    assert "delete(_ASYNC_TTC_REDIS_KEY)" in lifespan
    assert "delete(_ASYNC_INFLIGHT_REDIS_KEY)" not in lifespan


def test_async_complete_sets_status_before_sync_store():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(
        encoding="utf-8"
    )
    fn = text.split("async def _run_task_background(", 1)[1].split(
        '@app.get("/run/status/{task_id}")', 1
    )[0]
    assert 'store["status"] = "completed"' in fn
    assert "await _sync_store()" in fn
    assert "await _sync_store()\n                store[\"status\"] = \"completed\"" not in fn
    assert "await _sync_store()\n                    store[\"status\"] = \"failed\"" not in fn
    finally_chunk = fn.split("finally:", 1)[1]
    assert "_clear_async_inflight(task_id)" in finally_chunk
    assign = fn.split("route=expert_assignments", 1)[0]
    status_idx = assign.rfind('store["status"] = "completed"')
    sync_idx = assign.rfind("await _sync_store()")
    assert status_idx != -1 and sync_idx != -1
    assert status_idx < sync_idx


def test_execution_phase_skips_patch_templates():
    text = (ROOT / "knowledge_os" / "app" / "execution_phase.py").read_text(
        encoding="utf-8"
    )
    fn = text.split("async def execute_plan_commands", 1)[1]
    skip = fn.split("execution_log = []", 1)[0]
    assert "class=patch" in skip
    assert 'skipped": "patch"' in skip
