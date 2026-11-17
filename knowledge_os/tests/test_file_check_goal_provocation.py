"""Handoff #65 / self_audit 2026-11-16 items 5-8: provocation — pattern ONLY in goal.

Invariant: detectors match ONLY real file content. Goal/prompt text with
'pip install' / 'eval()' must never become a hit or a cited finding.
Citations must be path:line from the real file.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path
from typing import Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"
CURATOR_SEND = ROOT / "scripts" / "curator_send_tasks_to_victoria.py"

# Unique markers that live ONLY in the goal/task text (never in the clean file).
PIP_MARKER = "PROVOCATION_PIP_INSTALL_ONLY_IN_GOAL"
EVAL_MARKER = "PROVOCATION_EVAL_ONLY_IN_GOAL"


def _load_victoria_file_check_helpers():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    start = text.index("# Quoted membership needles:")
    end = text.index("\nasync def _try_file_check_reply")
    ns: dict = {"re": re, "os": os, "Optional": Optional}
    exec(compile(text[start:end], str(VICTORIA_SERVER), "exec"), ns)
    return ns


def _load_curator_local_fallback():
    spec = importlib.util.spec_from_file_location("curator_send_provocation", CURATOR_SEND)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid running CLI side effects: load only until after helpers by exec of file
    # under a guarded __name__.
    code = CURATOR_SEND.read_text(encoding="utf-8")
    # Script may touch network on import in some setups; execute with __name__ != "__main__".
    ns = {"__name__": "curator_send_provocation", "__file__": str(CURATOR_SEND)}
    exec(compile(code, str(CURATOR_SEND), "exec"), ns)
    return ns


@pytest.fixture(scope="module")
def vs_helpers():
    return _load_victoria_file_check_helpers()


@pytest.fixture(scope="module")
def curator():
    return _load_curator_local_fallback()


def _assert_ok_not_finding(result: str) -> None:
    assert result is not None
    low = result.lower()
    assert result.startswith("ОК") or result.upper().startswith("OK"), result
    assert not result.startswith("ПРОБЛЕМА"), result
    # Unique goal markers must never appear as cited code.
    assert PIP_MARKER not in result
    assert EVAL_MARKER not in result
    # Finding-style bullets for eval/exec must not appear on clean file.
    assert re.search(r"[«\"]eval\(\)[»\"].*строка|eval: L\d+|\[eval/exec\]", low) is None


def _assert_citation_from_file(result: str, path: Path, lineno: int, needle: str) -> None:
    """Citations must be path:line and quote real file content."""
    assert result.startswith("ПРОБЛЕМА"), result
    cite = f"{path}:{lineno}:"
    assert cite in result, f"missing citation {cite!r} in {result!r}"
    file_line = path.read_text(encoding="utf-8").splitlines()[lineno - 1]
    assert needle in file_line
    # Quoted snippet after path:line must come from that file line.
    after = result.split(cite, 1)[1]
    snippet = after.splitlines()[0].strip()
    assert snippet
    assert snippet in file_line or file_line.strip()[:80] in snippet


def test_victoria_provocation_pip_and_eval_clean_file(tmp_path, vs_helpers):
    target = tmp_path / "clean_provocation.py"
    target.write_text('print("clean")\nx = 1 + 2\n', encoding="utf-8")
    pip_task = (
        f" — есть ли там pip install в рантайме ({PIP_MARKER} subprocess pip или os.system pip)?"
    )
    eval_task = (
        f" — найди потенциальные проблемы: subprocess calls, hardcoded URLs, "
        f"eval(), exec(). {EVAL_MARKER}"
    )
    pip_result = vs_helpers["_file_check_scan"](str(target), pip_task)
    eval_result = vs_helpers["_file_check_scan"](str(target), eval_task)
    _assert_ok_not_finding(pip_result)
    _assert_ok_not_finding(eval_result)


def test_victoria_real_hits_cite_file_line(tmp_path, vs_helpers):
    target = tmp_path / "dangerous.py"
    target.write_text(
        "import os\nos.system('pip install evil')\nx = eval(user_input)\n",
        encoding="utf-8",
    )
    pip_result = vs_helpers["_file_check_scan"](
        str(target),
        " — есть ли там pip install в рантайме?",
    )
    eval_result = vs_helpers["_file_check_scan"](
        str(target),
        " — найди потенциальные проблемы: subprocess calls, hardcoded URLs, eval(), exec().",
    )
    _assert_citation_from_file(pip_result, target, 2, "os.system")
    _assert_citation_from_file(eval_result, target, 3, "eval(")


def test_victoria_never_scans_concatenated_goal_plus_file(tmp_path, vs_helpers):
    """If haystack were goal+file, eval() in the goal line would false-positive."""
    target = tmp_path / "clean_concat.py"
    target.write_text("print('ok')\n", encoding="utf-8")
    goal = f"проверь файл {target} — найди потенциальные проблемы: eval(), exec(). {EVAL_MARKER}"
    # Correct API: task_text is query-only; file is read from path.
    result = vs_helpers["_file_check_scan"](
        str(target),
        " — найди потенциальные проблемы: eval(), exec().",
    )
    _assert_ok_not_finding(result)
    # Demonstrate the bug class: scanning goal lines would hit eval().
    bogus_hits = [
        i
        for i, ln in enumerate(goal.splitlines())
        if vs_helpers["_line_matches_audit_item"](ln, "eval()")
    ]
    assert bogus_hits, "sanity: goal text alone would match eval() if scanned"
    assert result.startswith("ОК")


def test_expert_worker_provocation_pip_clean_file(tmp_path, monkeypatch):
    from app.expert_worker import _run_monster_pip_runtime_audit

    monkeypatch.setenv("MONSTER_AUDIT_FAST_PATH", "true")
    target = tmp_path / "clean_expert.py"
    target.write_text("print('clean')\n", encoding="utf-8")
    goal = f"проверь файл {target} — есть ли там pip install в рантайме ({PIP_MARKER})?"
    result = _run_monster_pip_runtime_audit(
        goal, {"source": "victoria_monster_delegation", "source_path": str(target)}
    )
    _assert_ok_not_finding(result)
    assert str(target) in result or target.name in result


def test_expert_worker_real_pip_cites_file_line(tmp_path, monkeypatch):
    from app.expert_worker import _run_monster_pip_runtime_audit

    monkeypatch.setenv("MONSTER_AUDIT_FAST_PATH", "true")
    target = tmp_path / "runtime_pip.py"
    target.write_text("import os\nos.system('pip install x')\n", encoding="utf-8")
    goal = f"проверь файл {target} — есть ли там pip install в рантайме?"
    result = _run_monster_pip_runtime_audit(
        goal, {"source": "victoria_monster_delegation", "source_path": str(target)}
    )
    _assert_citation_from_file(result, target, 2, "os.system")


def test_smart_worker_provocation_pip_and_eval_clean_file(tmp_path, monkeypatch):
    from app import smart_worker_autonomous as sw

    clean = tmp_path / "clean_smart.py"
    clean.write_text("print('clean')\n", encoding="utf-8")
    app_path = "/app/knowledge_os/app/clean_smart_provocation.py"
    real_open = open
    real_exists = os.path.exists

    def fake_exists(p):
        return p == app_path or real_exists(p)

    def fake_open(file, *args, **kwargs):
        if str(file) == app_path:
            return real_open(clean, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(sw.os.path, "exists", fake_exists)
    monkeypatch.setattr("builtins.open", fake_open)

    pip_result = sw._fast_file_check(
        f"проверь файл {app_path} — есть ли там pip install в рантайме? {PIP_MARKER}"
    )
    eval_result = sw._fast_file_check(
        f"проверь файл {app_path} — найди потенциальные проблемы: "
        f"subprocess/eval/exec {EVAL_MARKER}"
    )
    assert pip_result == "ОК" or (pip_result and pip_result.startswith("ОК")), pip_result
    assert eval_result == "ОК" or (eval_result and eval_result.startswith("ОК")), eval_result
    assert PIP_MARKER not in (pip_result or "")
    assert EVAL_MARKER not in (eval_result or "")


def test_smart_worker_real_hits_cite_file_line(tmp_path, monkeypatch):
    from app import smart_worker_autonomous as sw

    dangerous = tmp_path / "dangerous_smart.py"
    dangerous.write_text(
        "import os\nos.system('pip install x')\ny = eval(user)\n",
        encoding="utf-8",
    )
    app_path = "/app/knowledge_os/app/dangerous_smart_provocation.py"
    real_open = open
    real_exists = os.path.exists

    def fake_exists(p):
        return p == app_path or real_exists(p)

    def fake_open(file, *args, **kwargs):
        if str(file) == app_path:
            return real_open(dangerous, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(sw.os.path, "exists", fake_exists)
    monkeypatch.setattr("builtins.open", fake_open)

    pip_result = sw._fast_file_check(
        f"проверь файл {app_path} — есть ли там pip install в рантайме?"
    )
    eval_result = sw._fast_file_check(
        f"проверь файл {app_path} — найди потенциальные проблемы: subprocess/eval/exec"
    )
    assert pip_result and pip_result.startswith("ПРОБЛЕМА"), pip_result
    assert f"{app_path}:2:" in pip_result, pip_result
    assert eval_result and eval_result.startswith("ПРОБЛЕМА"), eval_result
    assert f"{app_path}:3:" in eval_result, eval_result


def test_task_rule_executor_provocation_pip_clean_file(tmp_path, monkeypatch):
    import builtins

    from app import task_rule_executor as tre

    clean = tmp_path / "clean_rule.py"
    clean.write_text("print('clean')\n", encoding="utf-8")
    virtual = "/app/knowledge_os/app/clean_rule_provocation.py"
    real_open = builtins.open

    def fake_open(file, *args, **kwargs):
        if str(file) == virtual:
            return real_open(clean, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    result = tre._execute_file_audit(
        f"проверь файл {virtual} — есть ли там pip install в рантайме {PIP_MARKER}",
        "",
    )
    _assert_ok_not_finding(result)


def test_task_rule_executor_real_pip_cites_file_line(tmp_path, monkeypatch):
    import builtins

    from app import task_rule_executor as tre

    target = tmp_path / "runtime_rule.py"
    target.write_text("import os\nos.system('pip install x')\n", encoding="utf-8")
    virtual = "/app/knowledge_os/app/runtime_rule_provocation.py"
    real_open = builtins.open

    def fake_open(file, *args, **kwargs):
        if str(file) == virtual:
            return real_open(target, *args, **kwargs)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    result = tre._execute_file_audit(
        f"проверь файл {virtual} — есть ли там pip install в рантайме",
        "",
    )
    assert result.startswith("ПРОБЛЕМА"), result
    assert f"{virtual}:2:" in result, result


def test_curator_provocation_pip_and_eval_clean_file(tmp_path, curator, monkeypatch):
    clean = tmp_path / "clean_curator.py"
    clean.write_text("print('clean')\n", encoding="utf-8")
    rel = "knowledge_os/app/clean_curator_provocation.py"
    app_path = f"/app/{rel}"
    dest = ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Use tmp content via monkeypatch on Path.read_text for that path.
    real_read = Path.read_text

    def fake_read(self, *args, **kwargs):
        if self.resolve() == (ROOT / rel).resolve() or str(self).endswith(rel):
            return clean.read_text(encoding="utf-8")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    # Ensure extract resolves under ROOT
    monkeypatch.setattr(curator["Path"], "read_text", fake_read, raising=False)

    pip_goal = f"проверь файл {app_path} — есть ли там pip install в рантайме? {PIP_MARKER}"
    eval_goal = (
        f"прочитай файл {app_path} — найди потенциальные проблемы: "
        f"subprocess calls, hardcoded URLs, eval(), exec(). {EVAL_MARKER}"
    )
    # Point extract at tmp file by writing real dest temporarily if needed
    wrote = False
    if not dest.exists():
        dest.write_text(clean.read_text(encoding="utf-8"), encoding="utf-8")
        wrote = True
    try:
        pip_out = curator["_local_fallback_for_goal"](pip_goal, "prov-pip")
        eval_out = curator["_local_fallback_for_goal"](eval_goal, "prov-eval")
    finally:
        if wrote and dest.exists():
            dest.unlink()

    assert pip_out and pip_out.get("output"), pip_out
    assert eval_out and eval_out.get("output"), eval_out
    _assert_ok_not_finding(pip_out["output"])
    _assert_ok_not_finding(eval_out["output"])


def test_curator_real_hits_cite_file_line(tmp_path, curator):
    rel = "knowledge_os/app/_provocation_runtime_hit.py"
    dest = ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "import os\nos.system('pip install x')\nz = eval(user)\n",
        encoding="utf-8",
    )
    app_path = f"/app/{rel}"
    try:
        pip_out = curator["_local_fallback_for_goal"](
            f"проверь файл {app_path} — есть ли там pip install в рантайме?",
            "hit-pip",
        )
        eval_out = curator["_local_fallback_for_goal"](
            f"прочитай файл {app_path} — найди потенциальные проблемы: "
            f"subprocess calls, hardcoded URLs, eval(), exec().",
            "hit-eval",
        )
        pip_text = pip_out["output"]
        eval_text = eval_out["output"]
        assert pip_text.startswith("ПРОБЛЕМА"), pip_text
        assert f"{app_path}:2:" in pip_text, pip_text
        assert eval_text.startswith("ПРОБЛЕМА"), eval_text
        assert f"{app_path}:3:" in eval_text, eval_text
    finally:
        if dest.exists():
            dest.unlink()
