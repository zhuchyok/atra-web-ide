import importlib.util
from pathlib import Path
import sys


def _load_task_detector():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "src" / "agents" / "bridge" / "task_detector.py"
    spec = importlib.util.spec_from_file_location("task_detector", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fact_probe_kept_for_status_query():
    td = _load_task_detector()
    assert td.is_fact_seeking_question("проверь open webui health и pending/in_progress") is True


def test_fact_probe_disabled_for_planning_prompt():
    td = _load_task_detector()
    assert (
        td.is_fact_seeking_question("сделай план фикса таймаута openwebui->victoria в 5 шагах")
        is False
    )


def test_fact_probe_disabled_for_how_to_check_prompt():
    td = _load_task_detector()
    assert td.is_fact_seeking_question("как проверить open webui connection errors пошагово") is False
