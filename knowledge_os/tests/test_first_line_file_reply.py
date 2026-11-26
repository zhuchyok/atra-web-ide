"""Deterministic first-line file probe for curator pairs."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_TD = ROOT / "src" / "agents" / "bridge" / "task_detector.py"


def _load():
    os.environ.setdefault("PROJECT_ROOT", str(Path(__file__).resolve().parents[2]))
    spec = importlib.util.spec_from_file_location("task_detector_first_line", _TD)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_first_line_cursor_method():
    mod = _load()
    goal = (
        "Read file knowledge_os/docs/curator_reports/standards/code_audit.md. "
        "Report ONLY the first line of the file exactly as written."
    )
    out = mod.first_line_file_answer(goal)
    assert out is not None
    assert out.startswith("# Стандарт")


def test_first_line_not_for_bare_read():
    mod = _load()
    assert (
        mod.first_line_file_answer(
            "Read file knowledge_os/docs/curator_reports/standards/code_audit.md"
        )
        is None
    )


def test_nth_line_three_cursor_method():
    mod = _load()
    goal = (
        "Open knowledge_os/docs/curator_reports/standards/code_audit.md with read_file. "
        "Quote line 3 exactly (1-based). Do not quote line 1."
    )
    out = mod.nth_line_file_answer(goal)
    assert out is not None
    assert "Описание" in out


def test_multi_nth_two_paths():
    mod = _load()
    goal = (
        "Quote line 3 of knowledge_os/docs/curator_reports/standards/code_audit.md "
        "and src/agents/bridge/task_detector.py"
    )
    assert mod.nth_line_file_answer(goal) is None
    out = mod.multi_nth_line_answer(goal)
    assert out is not None
    assert "Multi-line quote" in out
    assert "code_audit.md:3:" in out
    assert "task_detector.py:3:" in out
    assert "Описание" in out


def test_multi_nth_per_path_different_n():
    """R14: line 3 of A and line 5 of B must not false-proof B:3."""
    mod = _load()
    goal = (
        "Quote line 3 of knowledge_os/docs/curator_reports/standards/code_audit.md "
        "and line 5 of src/agents/bridge/task_detector.py"
    )
    out = mod.multi_nth_line_answer(goal)
    assert out is not None
    assert "code_audit.md:3:" in out
    assert "task_detector.py:5:" in out
    assert "task_detector.py:3:" not in out


def test_multi_first_two_paths():
    mod = _load()
    goal = (
        "First line of knowledge_os/docs/curator_reports/standards/code_audit.md "
        "and src/agents/bridge/task_detector.py"
    )
    assert mod.first_line_file_answer(goal) is None
    out = mod.multi_first_line_answer(goal)
    assert out is not None
    assert "Multi-first-line" in out
    assert "code_audit.md:1:" in out
    assert "task_detector.py:1:" in out
    assert "Стандарт" in out


def test_file_summarize_cursor_method_no_pgbouncer():
    mod = _load()
    goal = (
        "Using read_file, summarize knowledge_os/docs/curator_reports/standards/code_audit.md "
        "in three short bullets. Stick only to that file content. No handoff."
    )
    out = mod.file_summarize_answer(goal)
    assert out is not None
    assert "file read" in out.lower() or "From `" in out
    assert "code_audit.md" in out


def test_multi_file_summarize_two_paths():
    mod = _load()
    goal = (
        "Summarize knowledge_os/docs/curator_reports/standards/code_audit.md and "
        "docs/COGNITIVE_CODE.md in three bullets each. Stick to files."
    )
    assert mod.file_summarize_answer(goal) is None
    out = mod.multi_file_summarize_answer(goal)
    assert out is not None
    assert "Multi-file summarize" in out
    assert "code_audit.md" in out
    assert "COGNITIVE_CODE.md" in out
    assert "Стандарт" in out or "Цель" in out


def test_multi_git_diff_two_paths():
    mod = _load()
    goal = "git_diff src/agents/bridge/task_detector.py and src/agents/bridge/victoria_server.py"
    out = mod.multi_git_diff_answer(goal)
    assert out is not None
    assert "Multi git_diff" in out
    assert "task_detector.py" in out
    assert "victoria_server.py" in out
    # Diff hunks may mention pgbouncer in source — not recipe bleed.
    assert mod.is_evidence_tool_goal(goal)


def test_git_diff_single_path():
    mod = _load()
    goal = "git_diff src/agents/bridge/task_detector.py — show the hunk"
    assert mod.multi_git_diff_answer(goal) is None
    out = mod.git_diff_answer(goal)
    assert out is not None
    assert "git_diff (no LLM)" in out
    assert "task_detector.py" in out


def test_line_range_three_to_five():
    mod = _load()
    goal = "Quote lines 3-5 of knowledge_os/docs/curator_reports/standards/code_audit.md"
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "Line range" in out
    assert "code_audit.md:3:" in out
    assert "code_audit.md:5:" in out
    assert "Описание" in out


def test_file_exists_en_and_missing():
    mod = _load()
    ok = mod.file_exists_answer(
        "does file src/agents/bridge/task_detector.py exist? Reply path: EXISTS or MISSING"
    )
    assert ok is not None
    assert "task_detector.py: EXISTS" in ok
    assert mod.is_evidence_tool_goal("does file src/agents/bridge/task_detector.py exist?")
    miss = mod.file_exists_answer("does file docs/NO_SUCH_FILE_R18.md exist?")
    assert miss is not None
    assert "NO_SUCH_FILE_R18.md: MISSING" in miss


def test_what_does_symbol_not_summarize_hijack():
    """R18b: What does SYMBOL do in PATH → symbol find, not file-header summarize."""
    mod = _load()
    goal = "What does process_env_fact_answer do in src/agents/bridge/task_detector.py"
    assert mod.file_summarize_answer(goal) is None
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert "task_detector.py:" in out


def test_compare_not_multi_summarize():
    mod = _load()
    goal = (
        "Compare and summarize knowledge_os/docs/curator_reports/standards/code_audit.md "
        "and docs/COGNITIVE_CODE.md"
    )
    assert mod.multi_file_summarize_answer(goal) is None
    out = mod.file_compare_answer(goal)
    assert out is not None
    assert "RESULT: DIFFER" in out
    assert "code_audit.md" in out
    assert "COGNITIVE_CODE.md" in out


def test_quote_the_line_with_symbol():
    mod = _load()
    goal = "Quote the line with process_env_fact_answer in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert "task_detector.py:" in out


def test_na_kakoy_stroke():
    mod = _load()
    goal = "На какой строке process_env_fact_answer в src/agents/bridge/task_detector.py?"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_first_five_lines_range():
    mod = _load()
    goal = "Read first 5 lines of src/agents/bridge/task_detector.py"
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "task_detector.py:1:" in out
    assert "task_detector.py:5:" in out


def test_first_five_word_number_en():
    mod = _load()
    goal = "Read first five lines of src/agents/bridge/task_detector.py"
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "task_detector.py:1:" in out
    assert "task_detector.py:5:" in out


def test_first_five_word_number_ru():
    mod = _load()
    goal = "Прочитай первые пять строк src/agents/bridge/task_detector.py"
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "task_detector.py:5:" in out


def test_bare_ls_refuse_without_dir():
    mod = _load()
    for g in ("ls", "ls ", "list files"):
        out = mod.list_directory_answer(g)
        assert out is not None
        assert "allowlisted dir required" in out
        assert "EXISTS" not in out


def test_locate_definition_of_not_false_proof():
    mod = _load()
    goal = "Locate definition of process_env_fact_answer inside src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert "_definitional" not in out.split("\n")[1]


def test_find_where_declared_not_false_proof():
    mod = _load()
    goal = "Find where process_env_fact_answer is declared in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert "no match for 'declared'" not in out


def test_gde_lezhit():
    mod = _load()
    goal = "где лежит process_env_fact_answer в src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_top_five_lines_word():
    mod = _load()
    goal = "Read the top five lines of src/agents/bridge/task_detector.py"
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "task_detector.py:5:" in out


def test_lines_through_range():
    mod = _load()
    goal = "Print lines 1 through 5 of src/agents/bridge/task_detector.py"
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "task_detector.py:5:" in out


def test_which_line_has_symbol():
    mod = _load()
    goal = "Which line has process_env_fact_answer in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_where_can_i_find_not_false_proof():
    mod = _load()
    goal = "Where can I find process_env_fact_answer in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert "Brain canary" not in out


def test_find_the_definition_of():
    mod = _load()
    goal = "Find the definition of process_env_fact_answer in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_what_line_is_token_on():
    mod = _load()
    goal = "What line is process_env_fact_answer on in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_opening_lines_default_five():
    mod = _load()
    goal = "Show me the opening lines of src/agents/bridge/task_detector.py"
    assert mod.first_line_file_answer(goal) is None
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "task_detector.py:5:" in out


def test_gde_obyavlen():
    mod = _load()
    goal = "где объявлен process_env_fact_answer в src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_what_files_are_in_dir():
    mod = _load()
    out = mod.list_directory_answer("what files are in src/agents/bridge")
    assert out is not None
    assert "task_detector.py" in out


def test_last_five_lines():
    mod = _load()
    goal = "Show the last 5 lines of src/agents/bridge/task_detector.py"
    assert mod.first_line_file_answer(goal) is None
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "Line range (no LLM):" in out
    lines = [ln for ln in out.split("\n") if ln.startswith("src/")]
    assert len(lines) == 5


def test_tail_n_five():
    mod = _load()
    goal = "tail -n 5 src/agents/bridge/task_detector.py"
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert len([ln for ln in out.split("\n") if ln.startswith("src/")]) == 5


def test_wc_l_line_count():
    mod = _load()
    goal = "wc -l src/agents/bridge/task_detector.py"
    out = mod.line_count_file_answer(goal)
    assert out is not None
    assert "lines" in out
    assert "task_detector.py:" in out


def test_pathless_where_can_refuse():
    mod = _load()
    out = mod.multi_grep_line_answer("Where can I find process_env_fact_answer")
    assert out is not None
    assert "repo path required" in out


def test_first_eleven_word_now_works():
    mod = _load()
    out = mod.line_range_file_answer(
        "Read first eleven lines of src/agents/bridge/task_detector.py"
    )
    assert out is not None
    assert "task_detector.py:11:" in out


def test_na_kakoy_strochke():
    mod = _load()
    goal = "на какой строчке process_env_fact_answer в src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_grep_bare_symbol_path():
    mod = _load()
    goal = "grep process_env_fact_answer src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_first_and_last_five_dual_window():
    mod = _load()
    goal = "Show first 5 and last 5 lines of src/agents/bridge/task_detector.py"
    assert mod.first_line_file_answer(goal) is None
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "task_detector.py:1:" in out
    assert "task_detector.py:5:" in out
    # last window present (file ends near high line numbers)
    body = out.split("\n")[1:]
    assert any(":248" in ln or int(ln.split(":")[1]) > 100 for ln in body if ":" in ln)


def test_last_five_and_first_line_dual():
    mod = _load()
    goal = "Show last 5 lines and first line of src/agents/bridge/task_detector.py"
    out = mod.line_range_file_answer(goal)
    assert out is not None
    assert "task_detector.py:1:" in out
    assert len([ln for ln in out.split("\n") if ln.startswith("src/")]) >= 6


def test_number_of_lines_count():
    mod = _load()
    out = mod.line_count_file_answer("number of lines in src/agents/bridge/task_detector.py")
    assert out is not None
    assert "lines" in out


def test_trailing_five_lines():
    mod = _load()
    out = mod.line_range_file_answer("trailing 5 lines of src/agents/bridge/task_detector.py")
    assert out is not None
    assert len([ln for ln in out.split("\n") if ln.startswith("src/")]) == 5


def test_first_thirty_word():
    mod = _load()
    out = mod.line_range_file_answer(
        "Read first thirty lines of src/agents/bridge/task_detector.py"
    )
    assert out is not None
    assert "task_detector.py:30:" in out


def test_path_contains_symbol():
    mod = _load()
    goal = "Does src/agents/bridge/task_detector.py contain process_env_fact_answer?"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_sed_n_range():
    mod = _load()
    out = mod.line_range_file_answer("sed -n '10,20p' src/agents/bridge/task_detector.py")
    assert out is not None
    assert "task_detector.py:10:" in out
    assert "task_detector.py:20:" in out


def test_next_five_after_line():
    mod = _load()
    out = mod.line_range_file_answer(
        "Show the next 5 lines after line 10 in src/agents/bridge/task_detector.py"
    )
    assert out is not None
    assert "task_detector.py:11:" in out
    assert "task_detector.py:15:" in out
    assert (
        mod.nth_line_file_answer(
            "Show the next 5 lines after line 10 in src/agents/bridge/task_detector.py"
        )
        is None
    )


def test_context_around_symbol():
    mod = _load()
    goal = "3 lines before and after process_env_fact_answer in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert "task_detector.py:490:" in out
    # window around 490
    assert "task_detector.py:487:" in out or "task_detector.py:488:" in out
    assert "task_detector.py:493:" in out or "task_detector.py:492:" in out


def test_git_blame_symbol_line():
    mod = _load()
    goal = "Blame who wrote process_env_fact_answer in src/agents/bridge/task_detector.py"
    assert mod.multi_grep_line_answer(goal) is None
    assert mod.nth_line_file_answer(goal) is None
    out = mod.git_blame_answer(goal)
    assert out is not None
    assert "git_blame (no LLM):" in out
    assert "process_env_fact_answer" in out
    assert " 490)" in out or "490)" in out


def test_git_blame_bare_path_needs_window():
    mod = _load()
    out = mod.git_blame_answer("git blame src/agents/bridge/task_detector.py")
    assert out is not None
    assert "line window required" in out


def test_first_forty_word():
    mod = _load()
    out = mod.line_range_file_answer("first forty lines of src/agents/bridge/task_detector.py")
    assert out is not None
    assert "task_detector.py:40:" in out


def test_top_of_two_files_multi_first():
    mod = _load()
    goal = (
        "top of knowledge_os/docs/curator_reports/standards/code_audit.md and "
        "docs/COGNITIVE_CODE.md"
    )
    out = mod.multi_first_line_answer(goal)
    assert out is not None
    assert "code_audit.md:1:" in out
    assert "COGNITIVE_CODE.md:1:" in out


def test_top_of_single_file_first_line():
    mod = _load()
    goal = "top of knowledge_os/docs/curator_reports/standards/code_audit.md"
    out = mod.first_line_file_answer(goal)
    assert out is not None
    assert "Стандарт" in out or "Cursor" in out or out.startswith("#")


def test_what_line_contains_not_false_proof():
    mod = _load()
    goal = "what line contains process_env_fact_answer in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert "no match for 'contains'" not in out


def test_where_does_token_live_not_false_proof():
    mod = _load()
    goal = "Where does process_env_fact_answer live in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert ":does" not in out.split("\n")[1] if "\n" in out else True


def test_is_token_defined_in():
    mod = _load()
    goal = "Is process_env_fact_answer defined in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_v_kakoy_stroke():
    mod = _load()
    goal = "в какой строке process_env_fact_answer в src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_list_directory_bridge():
    mod = _load()
    out = mod.list_directory_answer("list_directory src/agents/bridge")
    assert out is not None
    assert "task_detector.py" in out
    assert "victoria_server.py" in out
    assert "list_directory (no LLM)" in out


def test_what_line_number_is_not_false_proof():
    mod = _load()
    goal = "What line number is first_line_file_answer on in src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "first_line_file_answer" in out
    assert "no match for 'number'" not in out


def test_na_kakoy_opredelen():
    mod = _load()
    goal = "На какой строке определён process_env_fact_answer в src/agents/bridge/task_detector.py"
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_symbol_exist_in_file_not_file_exists():
    mod = _load()
    goal = "Does file_exists_answer exist in src/agents/bridge/task_detector.py"
    assert mod.file_exists_answer(goal) is None
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "file_exists_answer" in out
    assert "EXISTS" not in out


def test_git_status_answer():
    mod = _load()
    out = mod.git_status_answer("git_status — report porcelain short")
    assert out is not None
    assert out.startswith("git_status (no LLM):")


def test_looks_like_pgbouncer_recipe():
    mod = _load()
    assert mod.looks_like_pgbouncer_recipe(
        "Принято. Переходим к исполнению ТЗ по PgBouncer (порт 6432)."
    )
    assert not mod.looks_like_pgbouncer_recipe("Facts before conclusions. KISS.")


def test_evidence_goal_detects_cursor_method_for_bleed_gate():
    mod = _load()
    assert mod.is_evidence_tool_goal(
        "What does knowledge_os/docs/curator_reports/standards/code_audit.md teach about proof?"
    )


def test_grep_line_process_env():
    mod = _load()
    goal = (
        "Use grep_search or run_terminal_cmd: rg -n 'def process_env_fact_answer' "
        "src/agents/bridge/task_detector.py. Report the matching line with line number."
    )
    out = mod.grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out
    assert ":123:" not in out
    assert out.startswith("src/agents/bridge/task_detector.py:")


def test_process_env_multi_keys_no_silent_drop(monkeypatch):
    """R16: asked PROJECT_ROOT must appear — not only ATRA_ALLOW_GIT_MUTATE."""
    mod = _load()
    monkeypatch.delenv("ATRA_ALLOW_GIT_MUTATE", raising=False)
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    goal = "printenv ATRA_ALLOW_GIT_MUTATE and PROJECT_ROOT"
    out = mod.process_env_fact_answer(goal)
    assert out is not None
    assert "ATRA_ALLOW_GIT_MUTATE=UNSET" in out
    assert "PROJECT_ROOT=UNSET" in out


def test_process_env_unknown_pull_not_invent_mutate(monkeypatch):
    """R16b: ATRA_ALLOW_GIT_PULL must not stamp MUTATE/PUSH."""
    mod = _load()
    monkeypatch.delenv("ATRA_ALLOW_GIT_MUTATE", raising=False)
    monkeypatch.delenv("ATRA_ALLOW_GIT_PUSH", raising=False)
    assert mod.process_env_fact_answer("printenv ATRA_ALLOW_GIT_PULL") is None


def test_grep_and_first_line_bare_tests_root():
    mod = _load()
    assert mod.grep_line_answer(
        "rg -n 'test_multi_grep_two_paths' tests/test_first_line_file_reply.py"
    )
    assert mod.first_line_file_answer("Read first line of tests/test_first_line_file_reply.py")


def test_multi_nth_path_before_n():
    mod = _load()
    goal = (
        "Quote src/agents/bridge/task_detector.py line 5 and "
        "knowledge_os/docs/curator_reports/standards/code_audit.md line 3"
    )
    out = mod.multi_nth_line_answer(goal)
    assert out is not None
    assert "task_detector.py:5:" in out
    assert "code_audit.md:3:" in out


def test_multi_grep_two_paths():
    mod = _load()
    goal = (
        "Find 'process_env_fact_answer' in src/agents/bridge/task_detector.py "
        "and src/agents/tools/system_tools.py. Report path:line for each."
    )
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "Multi-file find" in out
    assert "task_detector.py:" in out
    assert "process_env_fact_answer" in out
    # single-path rg stays on grep_line
    assert (
        mod.multi_grep_line_answer(
            "rg -n 'def process_env_fact_answer' src/agents/bridge/task_detector.py"
        )
        is None
    )


def test_multi_grep_wins_over_rg_n_two_paths():
    """rg -n + ≥2 paths must not single-file hijack (Expert R10 hole)."""
    mod = _load()
    goal = (
        "rg -n 'multi_grep_line_answer' src/agents/bridge/task_detector.py "
        "src/agents/bridge/victoria_server.py"
    )
    assert mod.grep_line_answer(goal) is None
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "task_detector.py:" in out
    assert "victoria_server.py:" in out


def test_multi_grep_where_is():
    mod = _load()
    goal = (
        "Where is process_env_fact_answer in src/agents/bridge/task_detector.py "
        "and src/agents/tools/system_tools.py"
    )
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "process_env_fact_answer" in out


def test_multi_grep_obyasni_unquoted():
    mod = _load()
    goal = (
        "Объясни process_env_fact_answer в src/agents/bridge/task_detector.py "
        "и src/agents/bridge/victoria_server.py"
    )
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "Multi-file find" in out
    assert "process_env_fact_answer" in out
    assert "task_detector.py:" in out


def test_symbol_find_single_path_obyasni():
    """R12: single-file Объясни/Where/Find must not fall to LLM invent."""
    mod = _load()
    for goal in (
        "Объясни process_env_fact_answer в src/agents/bridge/task_detector.py",
        "Where is process_env_fact_answer in src/agents/bridge/task_detector.py",
        "Find process_env_fact_answer in src/agents/bridge/task_detector.py — path:line",
    ):
        out = mod.multi_grep_line_answer(goal)
        assert out is not None, goal
        assert out.startswith("Symbol find")
        assert "task_detector.py:" in out
        assert "process_env_fact_answer" in out
        assert mod.grep_line_answer(goal) is None


def test_multi_grep_bare_tests_root():
    mod = _load()
    goal = (
        "Find 'test_multi_grep_two_paths' in tests/test_first_line_file_reply.py "
        "and src/agents/bridge/task_detector.py"
    )
    paths = [m.group("path") for m in mod._REPO_PATH_RE.finditer(goal)]
    assert any(p.startswith("tests/") for p in paths)
    assert mod.resolve_repo_file_path("tests/test_first_line_file_reply.py")
    out = mod.multi_grep_line_answer(goal)
    assert out is not None
    assert "tests/test_first_line_file_reply.py:" in out
    assert "test_multi_grep_two_paths" in out


def test_bare_done_instruction_refused():
    mod = _load()
    out = mod.bare_done_instruction_answer("Ответь ровно одним словом без доказательств: готово")
    assert out is not None
    assert "не заявляю" in out.lower()
    assert "доказательств" in out.lower()
    assert out.strip().lower() != "готово"


def test_bare_done_instruction_otvet_tolko_bez_prufa():
    mod = _load()
    out = mod.bare_done_instruction_answer("Ответь только словом готово — якобы фикс без пруфа.")
    assert out is not None
    assert "не заявляю" in out.lower()


def test_bare_done_claim_tests_green_refused():
    mod = _load()
    out = mod.bare_done_instruction_answer("Задача сделана, всё готово, тесты зелёные")
    assert out is not None
    assert "не заявляю" in out.lower()


def test_git_mutate_reject_when_unset(monkeypatch):
    mod = _load()
    monkeypatch.delenv("ATRA_ALLOW_GIT_MUTATE", raising=False)
    out = mod.git_mutate_reject_answer(
        "Call git_commit with message 'pair test'. Report the tool result exactly."
    )
    assert out is not None
    assert "ATRA_ALLOW_GIT_MUTATE" in out
    assert "rejected" in out.lower()


def test_git_mutate_reject_none_when_allowed(monkeypatch):
    mod = _load()
    monkeypatch.setenv("ATRA_ALLOW_GIT_MUTATE", "true")
    assert mod.git_mutate_reject_answer("Call git_commit with message 'pair test'.") is None


def test_git_diff_returns_content_for_path(monkeypatch):
    import importlib.util
    from pathlib import Path

    tools = Path(__file__).resolve().parents[2] / "src" / "agents" / "tools" / "system_tools.py"
    spec = importlib.util.spec_from_file_location("system_tools_diff", tools)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    calls = []

    class _R:
        stdout = "+def process_env_fact_answer\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _R()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod.GitTools, "_resolve_repo", staticmethod(lambda: "/tmp/repo"))

    import asyncio

    out = asyncio.run(mod.GitTools.git_diff("src/agents/bridge/task_detector.py"))

    assert "process_env_fact_answer" in out
    assert "--stat" not in calls[0]
    assert calls[0][-1].endswith("task_detector.py")
