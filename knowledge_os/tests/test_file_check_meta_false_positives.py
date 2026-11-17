"""Handoff #65 / self_audit 2026-11-16: meta-check lines must not flag as runtime hits.

Exact false-positive snippets from artifacts_2026-11-16_*/task_{5,7}_*.json.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"

# Exact citations from curator artifacts (task_5 pip meta-check, task_7 eval meta-check).
TASK5_PIP_META = (
    'if "python -m pip install" in normalized and '
    '("subprocess." in normalized or "os.system(" in normalized):'
)
TASK7_EVAL_META = (
    'if "найди потенциальные проблемы" in low and "eval()" in low and "exec()" in low:'
)


def _load_victoria_file_check_helpers():
    """Load only file-check helpers from victoria_server without importing the whole module."""
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("# Quoted membership needles:")
    end = text.index("\nasync def _try_file_check_reply")
    ns: dict = {
        "re": re,
        "os": os,
        "Optional": Optional,
    }
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns


@pytest.fixture(scope="module")
def vs_helpers():
    return _load_victoria_file_check_helpers()


def test_task5_pip_meta_check_not_runtime(vs_helpers):
    assert vs_helpers["_line_has_runtime_pip_install"](TASK5_PIP_META) is False


def test_task5_negative_guard_not_runtime(vs_helpers):
    assert vs_helpers["_line_has_runtime_pip_install"]('if "pip install" not in text:') is False


def test_real_runtime_pip_still_flags(vs_helpers):
    fn = vs_helpers["_line_has_runtime_pip_install"]
    assert fn("os.system('pip install x')") is True
    assert fn("subprocess.run(['python3', '-m', 'pip', 'install', 'x'])") is True
    assert fn('subprocess.call("pip install evil", shell=True)') is True


def test_task7_eval_meta_check_file_scan_ok(tmp_path, vs_helpers):
    target = tmp_path / "curator_meta.py"
    target.write_text(TASK7_EVAL_META + "\nprint('ok')\n", encoding="utf-8")
    result = vs_helpers["_file_check_scan"](
        str(target),
        " — найди потенциальные проблемы: subprocess calls, hardcoded URLs, eval(), exec().",
    )
    assert result is not None
    assert result.startswith("ОК"), result
    assert (
        "eval()" not in result.lower()
        or "не найдено" in result.lower()
        or "ничего не найдено" in result.lower()
    )


def test_real_eval_exec_still_flags_in_file_scan(tmp_path, vs_helpers):
    target = tmp_path / "dangerous.py"
    target.write_text("x = eval(user_input)\ny = exec(code)\n", encoding="utf-8")
    result = vs_helpers["_file_check_scan"](
        str(target),
        " — найди потенциальные проблемы: subprocess calls, hardcoded URLs, eval(), exec().",
    )
    assert result is not None
    assert result.startswith("ПРОБЛЕМА"), result
    assert "eval" in result.lower()
    assert "exec" in result.lower()


def test_expert_worker_pip_meta_not_runtime():
    from app.expert_worker import _line_has_runtime_pip_install

    assert _line_has_runtime_pip_install(TASK5_PIP_META) is False
    assert _line_has_runtime_pip_install("os.system('pip install x')") is True


def test_smart_worker_fast_path_ignores_pip_and_eval_meta(tmp_path, monkeypatch):
    from app import smart_worker_autonomous as sw

    pip_target = tmp_path / "expert_worker.py"
    pip_target.write_text(TASK5_PIP_META + "\n", encoding="utf-8")
    pip_path = "/app/knowledge_os/app/expert_worker.py"

    eval_target = tmp_path / "curator_send_tasks_to_victoria.py"
    eval_target.write_text(TASK7_EVAL_META + "\n", encoding="utf-8")
    eval_path = "/app/scripts/curator_send_tasks_to_victoria.py"

    real_open = open
    real_exists = os.path.exists

    def fake_exists(p):
        return p in (pip_path, eval_path) or real_exists(p)

    def fake_open(file, *args, **kwargs):
        s = str(file)
        if s == pip_path:
            return real_open(pip_target, *args, **kwargs)
        if s == eval_path:
            return real_open(eval_target, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(sw.os.path, "exists", fake_exists)
    monkeypatch.setattr("builtins.open", fake_open)

    pip_result = sw._fast_file_check(
        f"проверь файл {pip_path} — есть ли там pip install в рантайме?"
    )
    assert pip_result == "ОК"

    eval_result = sw._fast_file_check(
        f"проверь файл {eval_path} — найди потенциальные проблемы: subprocess/eval/exec"
    )
    assert eval_result == "ОК"
