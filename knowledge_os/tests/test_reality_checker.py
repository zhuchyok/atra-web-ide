"""v150.92: Reality Checker snippet on Victoria+Anna; rosters.json is metadata only."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "knowledge_os" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def test_reality_checker_snippet_is_short():
    from configs.victoria_common import PROMPT_REALITY_CHECKER

    assert "UNVERIFIED" in PROMPT_REALITY_CHECKER
    assert "command" in PROMPT_REALITY_CHECKER
    assert "output" in PROMPT_REALITY_CHECKER
    assert len(PROMPT_REALITY_CHECKER) < 280
    assert "тест" not in PROMPT_REALITY_CHECKER.lower()
    assert "pytest" not in PROMPT_REALITY_CHECKER.lower()


def test_inject_appends_checker_for_victoria_and_anna():
    from ai_pipeline import inject_anti_hallucination

    from configs.victoria_common import PROMPT_REALITY_CHECKER

    for name in ("Виктория", "victoria", "Анна", "anna"):
        out = inject_anti_hallucination("вопрос", name)
        assert PROMPT_REALITY_CHECKER in out
        assert "ПРАВИЛА: Отвечай строго по фактам" in out
        assert len(out) < len("вопрос") + 400


def test_inject_skips_checker_for_igor():
    from ai_pipeline import inject_anti_hallucination

    from configs.victoria_common import PROMPT_REALITY_CHECKER

    out = inject_anti_hallucination("вопрос", "Игорь")
    assert out == "вопрос"
    assert PROMPT_REALITY_CHECKER not in out


def test_victoria_server_appends_checker_constant():
    text = (ROOT / "src" / "agents" / "bridge" / "victoria_server.py").read_text(encoding="utf-8")
    assert "PROMPT_REALITY_CHECKER" in text


def test_rosters_json_is_metadata_not_imported():
    path = ROOT / "configs" / "experts" / "rosters.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) >= {"ops", "patch", "core-human"}
    assert data["ops"]["class"] == "runbook"
    assert data["ops"]["people"] == ["Елена", "Сергей", "Ольга"]
    assert data["ops"]["writes"] is False
    assert data["patch"]["class"] == "patch"
    assert data["patch"]["people"] == ["Игорь", "Анна"]
    assert data["patch"]["writes"] is True
    assert data["core-human"]["class"] == "human"
    assert data["core-human"]["people"] == ["Виктория", "Алексей", "Роман"]
    assert data["core-human"]["writes"] is False
    app_py = list((ROOT / "knowledge_os" / "app").rglob("*.py"))
    hits = [
        str(p.relative_to(ROOT))
        for p in app_py
        if "rosters.json" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits == []
