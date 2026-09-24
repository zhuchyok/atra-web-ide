"""v139: curiosity cooldown sees cancelled CB; timeout-cap keeps OK file-checks."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASES = ROOT / "knowledge_os" / "app" / "orchestrator_phases.py"
WORKER = ROOT / "knowledge_os" / "app" / "smart_worker_autonomous.py"
ENHANCED = ROOT / "knowledge_os" / "app" / "enhanced_orchestrator.py"
ORCHESTRATOR = ROOT / "knowledge_os" / "app" / "orchestrator.py"
STREAMING_ORCHESTRATOR = ROOT / "knowledge_os" / "app" / "streaming_orchestrator.py"
EXPERT_WORKER = ROOT / "knowledge_os" / "app" / "expert_worker.py"
EXECUTE_ASSIGNMENTS = ROOT / "knowledge_os" / "app" / "execute_assignments.py"
WORKER_LOGIC = ROOT / "knowledge_os" / "app" / "worker" / "worker_logic.py"


def test_curiosity_cooldown_includes_cancelled_circuit_breaker():
    text = PHASES.read_text(encoding="utf-8")
    start = text.index("recent_curiosity_failure = await conn.fetchval")
    chunk = text[start : start + 1200]
    assert "status IN ('failed', 'cancelled')" in chunk
    assert "circuit_breaker_loop_exhausted" in chunk
    assert "rag_loop_no_llm_call_exhausted" in chunk
    assert "ILIKE '%Circuit Breaker%'" in chunk


def test_curiosity_global_cb_cooldown():
    text = PHASES.read_text(encoding="utf-8")
    assert "Curiosity global cooldown" in text
    assert "curiosity_engine_starvation" in text
    assert "rag_loop_no_llm_call_exhausted" in text
    text = WORKER.read_text(encoding="utf-8")
    start = text.index("Kill zombie delegation tasks stuck in work_item_timeout")
    chunk = text[start : start + 1600]
    assert "!~* '^(ОК|OK)\\\\b'" in chunk or r"!~* '^(ОК|OK)\\b'" in chunk
    assert "completed_at IS NULL" in chunk
    assert "Delegation with OK result → completed" in text
    assert "'manual_cancel_reason', 'policy_timeout_cap'" in text
    assert "'manual_cancel_reason', 'policy_rag_loop_cap'" in text
    assert "'manual_cancel_reason', 'policy_delegation_hard_cap'" in text
    assert '"manual_cancel_reason"] = "policy_rule_fallback"' in text
    enhanced_text = ENHANCED.read_text(encoding="utf-8")
    assert "'manual_cancel_reason', 'policy_energy_depleted'" in enhanced_text
    assert "'auto_fallback_reason', 'energy_budget_time_decay'" in enhanced_text


def test_completed_paths_keep_task_contract_metadata():
    text = WORKER.read_text(encoding="utf-8")
    assert text.count("'task_contract_version', 'smart_worker_v1'") >= 6
    assert text.count("'task_contract_output_schema', 'free_text'") >= 6

    hard_cap_start = text.index("hard_cap_complete_result = await conn.execute(")
    hard_cap_chunk = text[hard_cap_start : hard_cap_start + 1200]
    assert "'task_contract_version', 'smart_worker_v1'" in hard_cap_chunk
    assert "'task_contract_output_schema', 'free_text'" in hard_cap_chunk
    assert "'manual_cancel_reason', ''" in hard_cap_chunk

    timeout_ok_start = text.index("timeout_ok_result = await conn.execute(")
    timeout_ok_chunk = text[timeout_ok_start : timeout_ok_start + 1200]
    assert "'task_contract_version', 'smart_worker_v1'" in timeout_ok_chunk
    assert "'task_contract_output_schema', 'free_text'" in timeout_ok_chunk
    assert "'manual_cancel_reason', ''" in timeout_ok_chunk
    assert "'auto_fallback_reason', 'work_item_timeout_ok_recovered'" in timeout_ok_chunk

    timeout_recover_start = text.index("timeout_recover_result = await conn.execute(")
    timeout_recover_chunk = text[timeout_recover_start : timeout_recover_start + 1200]
    assert "'task_contract_version', 'smart_worker_v1'" in timeout_recover_chunk
    assert "'task_contract_output_schema', 'free_text'" in timeout_recover_chunk
    assert "'manual_cancel_reason', ''" in timeout_recover_chunk

    fast_path_start = text.index("last_real_progress_at=NOW()")
    fast_path_chunk = text[fast_path_start : fast_path_start + 600]
    assert "'task_contract_version', 'smart_worker_v1'" in fast_path_chunk
    assert "'task_contract_output_schema', 'free_text'" in fast_path_chunk

    auto_finish_start = text.index("meta_payload = {")
    auto_finish_chunk = text[auto_finish_start : auto_finish_start + 700]
    assert '"task_contract_version": "smart_worker_v1"' in auto_finish_chunk
    assert '"task_contract_output_schema": "free_text"' in auto_finish_chunk
    assert "def _fast_skip_method_only_delegation(" in text
    assert "SKIPPED: empty delegation payload (no goal/description)" in text
    assert "'completion_reason', 'delegation_fast_skipped'" in text
    assert "def _is_simple_direct_delegation_text(" in text
    assert "simple direct goal should be handled by Victoria directly" in text
    assert "'manual_cancel_reason', ''" in text
    assert "не выдумывай" in text
    assert "корень,\\s*не\\s*сим" in text
    assert "выполни свою часть работы" in text


def test_curiosity_pending_timeout_default_is_tight():
    text = ENHANCED.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_PENDING_TIMEOUT_MIN", "30"' in text
    assert "COALESCE(metadata->>'source', '') <> 'victoria_monster_delegation'" in text


def test_curiosity_ghost_timeout_default_is_aligned_with_stale_window():
    text = ENHANCED.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_GHOST_NO_LLM_MINUTES", "10"' in text


def test_curiosity_in_progress_guard_uses_db_last_llm_call_column():
    text = ENHANCED.read_text(encoding="utf-8")
    start = text.index("curiosity_force_failed = await conn.fetchval")
    chunk = text[start : start + 1300]
    assert "SET status = 'cancelled'" in chunk
    assert "'manual_cancel_reason', 'policy_curiosity_no_llm_timeout'" in chunk
    assert "last_llm_call_at IS NULL" in chunk
    assert "last_llm_call_at < NOW() - ($1::text || ' minutes')::interval" in chunk


def test_pending_dispatch_guard_uses_db_last_llm_call_column():
    text = ENHANCED.read_text(encoding="utf-8")
    start = text.index("pending_dispatch_requeued = await conn.fetchval")
    chunk = text[start : start + 1900]
    assert "last_llm_call_at IS NULL" in chunk
    assert "last_llm_call_at < NOW() - ($3::text || ' minutes')::interval" in chunk
    assert "COALESCE(metadata->>'last_llm_call_at', '') = ''" not in chunk


def test_pending_dispatch_force_failed_guard_uses_db_last_llm_call_column():
    text = ENHANCED.read_text(encoding="utf-8")
    start = text.index("pending_dispatch_force_failed = await conn.fetchval")
    chunk = text[start : start + 1600]
    assert "last_llm_call_at IS NULL" in chunk
    assert "last_llm_call_at < NOW() - ($3::text || ' minutes')::interval" in chunk
    assert "COALESCE(metadata->>'last_llm_call_at', '') = ''" not in chunk


def test_pending_curiosity_timeout_moves_to_policy_cancel():
    text = ENHANCED.read_text(encoding="utf-8")
    start = text.index("pending_curiosity_force_failed = await conn.fetchval")
    chunk = text[start : start + 1600]
    assert "SET status = 'cancelled'" in chunk
    assert "'manual_cancel_reason', 'policy_pending_curiosity_timeout'" in chunk
    assert "COALESCE(metadata->>'dispatched_to_stream_at', '') = ''" in chunk


def test_curiosity_cancelled_with_result_is_recovered_to_completed():
    text = ENHANCED.read_text(encoding="utf-8")
    start = text.index("curiosity_cancelled_with_result_recovered = await conn.fetchval")
    chunk = text[start : start + 2300]
    assert "status = 'cancelled'" in chunk
    assert (
        "COALESCE(metadata->>'auto_fallback_reason', '') = 'circuit_breaker_loop_exhausted'"
        in chunk
    )
    assert "COALESCE(result, '') <> ''" in chunk
    assert "COALESCE(result, '') !~* '^task timed out after'" in chunk
    assert "COALESCE(result, '') !~* '^cancelled:'" in chunk
    assert "COALESCE(result, '') !~* '^\\\\[auto_fallback\\\\]'" in chunk
    assert "updated_at > NOW() - ($1::text || ' minutes')::interval" in chunk
    assert "SET status = 'completed'" in chunk
    assert "'curiosity_circuit_breaker_recovered_with_result'" in chunk
    assert "'manual_cancel_reason', ''" in chunk
    assert "'failed_requires_intervention', false" in chunk
    assert "'task_contract_version', 'smart_worker_v1'" in chunk
    assert "'task_contract_output_schema', 'free_text'" in chunk


def test_curiosity_skip_domain_cleanup_in_stale_reconcile():
    text = ENHANCED.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_SKIP_DOMAINS", "Test Domain"' in text
    start = text.index("curiosity_skip_domain_cancelled = 0")
    chunk = text[start : start + 1900]
    assert "status IN ('pending', 'in_progress')" in chunk
    assert "curiosity_skip_domain_policy" in chunk
    assert "manual_cancel_reason', 'policy_skip_domain'" in chunk
    assert (
        "lower(regexp_replace(title, '^🔥\\\\s*(СРОЧНОЕ\\\\s+)?ИССЛЕДОВАНИЕ:\\\\s*', '')) = ANY($1::text[])"
        in chunk
    )


def test_curator_circuit_breaker_degrades_to_completed_not_cancelled():
    text = EXPERT_WORKER.read_text(encoding="utf-8")
    start = text.index("if _is_circuit_breaker and circuit_breaker_count >= cb_max_retries:")
    chunk = text[start : start + 4200]
    assert 'task_source == "curator_autonomous"' in chunk
    assert "has_meaningful_existing_result" in chunk
    assert 'existing_result_lc.startswith("task timed out after")' in chunk
    assert 'existing_result_lc.startswith("cancelled:")' in chunk
    assert 'existing_result_lc.startswith("[auto_fallback]")' in chunk
    assert "should_complete = is_curator_task or has_meaningful_existing_result" in chunk
    assert '"completed" if should_complete else "cancelled"' in chunk
    assert "curator_circuit_breaker_degraded_completed" in chunk
    assert "circuit_breaker_recovered_with_existing_result" in chunk
    assert "SELECT COALESCE(result, '') FROM tasks WHERE id = $1" in chunk
    assert '"manual_cancel_reason": (' in chunk
    assert '"policy_circuit_breaker_cap" if not should_complete else ""' in chunk
    assert (
        "'task_contract_version': 'smart_worker_v1'" in chunk
        or '"task_contract_version": "smart_worker_v1"' in chunk
    )
    assert (
        "'task_contract_output_schema': 'free_text'" in chunk
        or '"task_contract_output_schema": "free_text"' in chunk
    )


def test_legacy_orchestrator_curiosity_cooldown_handles_cancelled_cb():
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    assert "Curiosity global cooldown" in text
    assert "COALESCE(metadata->>'reason', '') = 'curiosity_engine_starvation'" in text
    start = text.index("recent_curiosity_failure = await conn.fetchval")
    chunk = text[start : start + 1400]
    assert "status IN ('failed', 'cancelled')" in chunk
    assert "circuit_breaker_loop_exhausted" in chunk
    assert "rag_loop_no_llm_call_exhausted" in chunk
    assert "ILIKE '%Circuit Breaker%'" in chunk


def test_legacy_orchestrator_does_not_refresh_pending_updated_at_on_conflict():
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    start = text.index(
        "ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))"
    )
    chunk = text[start : start + 700]
    assert "WHEN tasks.status = 'in_progress' THEN NOW()" in chunk
    assert "ELSE tasks.updated_at" in chunk


def test_streaming_orchestrator_curiosity_cooldown_handles_cancelled_cb():
    text = STREAMING_ORCHESTRATOR.read_text(encoding="utf-8")
    assert "Curiosity global cooldown" in text
    assert "COALESCE(metadata->>'reason', '') = 'curiosity_engine_starvation'" in text
    start = text.index("recent_curiosity_failure = await pool.fetchval")
    chunk = text[start : start + 1400]
    assert "status IN ('failed', 'cancelled')" in chunk
    assert "circuit_breaker_loop_exhausted" in chunk
    assert "rag_loop_no_llm_call_exhausted" in chunk
    assert "ILIKE '%Circuit Breaker%'" in chunk


def test_curiosity_assignee_capacity_guard_present_in_all_orchestrators():
    phases = PHASES.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_MAX_ASSIGNEE_ACTIVE", "4"' in phases
    assert "assignee_expert_id = $1" in phases
    assert "status IN ('pending', 'in_progress')" in phases

    orchestrator = ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_MAX_ASSIGNEE_ACTIVE", "4"' in orchestrator
    assert "assignee_expert_id = $1" in orchestrator
    assert "status IN ('pending', 'in_progress')" in orchestrator

    streaming = STREAMING_ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_MAX_ASSIGNEE_ACTIVE", "4"' in streaming
    assert "assignee_expert_id = $1" in streaming
    assert "status IN ('pending', 'in_progress')" in streaming


def test_curiosity_tasks_seed_rescue_fast_profile_and_preferred_source():
    phases = PHASES.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_PREFERRED_SOURCE", "ollama"' in phases
    assert '"complex": True' in phases
    assert '"execution_profile": "rescue_fast"' in phases
    assert '"preferred_source": curiosity_preferred_source' in phases

    orchestrator = ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_PREFERRED_SOURCE", "ollama"' in orchestrator
    assert '"complex": True' in orchestrator
    assert '"execution_profile": "rescue_fast"' in orchestrator
    assert '"preferred_source": curiosity_preferred_source' in orchestrator

    streaming = STREAMING_ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_PREFERRED_SOURCE", "ollama"' in streaming
    assert '"complex": True' in streaming
    assert '"execution_profile": "rescue_fast"' in streaming
    assert '"preferred_source": curiosity_preferred_source' in streaming


def test_curiosity_skip_domains_guard_present_in_all_orchestrators():
    phases = PHASES.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_SKIP_DOMAINS", "Test Domain"' in phases
    assert "domain is in skip list" in phases

    orchestrator = ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_SKIP_DOMAINS", "Test Domain"' in orchestrator
    assert "domain in skip list" in orchestrator

    streaming = STREAMING_ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'ORCHESTRATOR_CURIOSITY_SKIP_DOMAINS", "Test Domain"' in streaming
    assert "domain in skip list" in streaming


def test_enhanced_assignment_keeps_or_sets_curiosity_rescue_profile():
    text = ENHANCED.read_text(encoding="utf-8")
    assert "if isinstance(task_meta, str):" in text
    assert "task_meta = json.loads(task_meta) if task_meta else {}" in text
    assert (
        'is_curiosity_task = str(task_meta.get("reason", "")) == "curiosity_engine_starvation"'
        in text
    )
    assert "if is_curiosity_task and not execution_profile:" in text
    assert 'execution_profile = "rescue_fast"' in text
    assert 'meta_extra["execution_profile"] = execution_profile' in text
    assert 'meta_extra["complex"] = True' in text


def test_monster_delegation_tasks_seed_rescue_profile_and_source():
    text = EXECUTE_ASSIGNMENTS.read_text(encoding="utf-8")
    assert "ORCHESTRATOR_DELEGATION_PREFERRED_SOURCE" in text
    assert "ORCHESTRATOR_DELEGATION_EXECUTION_PROFILE" in text
    assert '"source": "victoria_monster_delegation"' in text
    assert '"execution_profile": delegation_execution_profile' in text
    assert '"preferred_source": delegation_preferred_source' in text
    assert '"delegation_goal_compacted": bool(compact_goal)' in text
    assert "def _compact_goal_for_delegation(" in text
    assert "def _is_method_only_goal(" in text
    assert "def _is_simple_direct_goal(" in text
    assert "Skipping delegation: no actionable goal after compaction" in text
    assert "Skipping delegation: simple direct goal handled by Victoria directly" in text
    assert "метод cursor" in text
    assert "выведи\\s+список\\s+файл" in text
    assert "статус\\s+health.*одной\\s+строк" in text
    assert "кратк\\w*\\s+чеклист\\w*.*\\d+\\s+пункт" in text
    assert "чеклист\\w*.*runtime.*очеред" in text
    assert "def _is_status_snapshot_goal(" in text
    assert "limiting delegation fanout to" in text
    assert "ORCHESTRATOR_STATUS_SNAPSHOT_MAX_DELEGATES" in text
    assert "description = $2" in text
    assert "project_context = COALESCE($4, project_context)" in text
    assert "COALESCE(project_context, 'default') = COALESCE($4, 'default')" in text
    assert "metadata, project_context" in text
    assert "metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb" in text


def test_monster_assignment_completion_writes_contract_metadata():
    text = EXECUTE_ASSIGNMENTS.read_text(encoding="utf-8")
    assert "SET status = 'completed'" in text
    assert "metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb" in text
    assert '"completion_reason": "worker_success"' in text
    assert '"task_contract_version": "smart_worker_v1"' in text
    assert '"task_contract_output_schema": "free_text"' in text


def test_rule_fallback_cancelled_paths_are_always_policy_classified():
    text = WORKER.read_text(encoding="utf-8")
    assert 'if final_status == "cancelled":' in text
    assert 'meta_payload.setdefault("auto_fallback_reason", "rule_fallback_cancelled")' in text
    assert 'meta_payload.setdefault("manual_cancel_reason", "policy_rule_fallback")' in text


def test_auto_requeue_handles_rule_fallback_policy_cancel():
    text = WORKER_LOGIC.read_text(encoding="utf-8")
    assert "t.status = 'cancelled'" in text
    assert "COALESCE(t.metadata->>'manual_cancel_reason', '') = 'policy_rule_fallback'" in text
    assert "COALESCE(t.metadata->>'auto_fallback_reason', '') = 'rule_fallback_cancelled'" in text
    assert "OR COALESCE(t.metadata->>'manual_cancel_reason', '') = 'policy_rule_fallback'" in text
