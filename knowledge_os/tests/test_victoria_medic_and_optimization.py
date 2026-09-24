"""
Regression and Chaos Tests: Victoria Medic & Optimization Pipeline (Phase 1-5).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from medic.watchdog import Watchdog, Incident
from medic.repair import RepairToolkit, PROTECTED_FILES


def test_medic_signatures_classification():
    """Verify that Watchdog classifies all failure signatures correctly."""
    async def noop(i):
        pass

    w = Watchdog(on_incident=noop)

    # 1. Broken import signature
    inc = w.classify_line("2026-09-01 ERROR ❌ [VICTORIA] LLM call failed: No module named 'ai_pipeline'")
    assert inc is not None
    assert inc.kind == "BROKEN_IMPORT"

    # 2. Soft timeout signature
    inc = w.classify_line("2026-09-01 ERROR ❌ [VICTORIA] LLM soft-timeout after 1200s")
    assert inc is not None
    assert inc.kind == "LLM_TIMEOUT"

    # 3. LLM call error signature
    inc = w.classify_line("2026-09-01 ERROR Ошибка вызова LLM: Model connection reset")
    assert inc is not None
    assert inc.kind == "LLM_ERROR"

    # 4. Traceback signature
    inc = w.classify_line("Traceback (most recent call last):")
    assert inc is not None
    assert inc.kind == "UNKNOWN_ERROR"

    # 5. Normal log line
    inc = w.classify_line("2026-09-01 INFO ✅ [VICTORIA] Health check passed")
    assert inc is None


def test_medic_repair_toolkit_snapshot_and_rollback(tmp_path, monkeypatch):
    """Verify that RepairToolkit creates snapshots and restores last_good cleanly."""
    monkeypatch.setattr("medic.repair.SNAPSHOT_ROOT", tmp_path / "snapshots")
    monkeypatch.setattr("medic.repair.LAST_GOOD_DIR", tmp_path / "snapshots" / "last_good")

    # Create dummy protected files
    dummy_app = tmp_path / "app"
    dummy_app.mkdir(parents=True)
    monkeypatch.setattr("medic.repair.APP_DIR", dummy_app)

    file_a = dummy_app / "ai_core.py"
    file_b = dummy_app / "ai_pipeline.py"
    file_c = dummy_app / "victoria_enhanced.py"

    file_a.write_text("# version 1 (good)", encoding="utf-8")
    file_b.write_text("# version 1 (good)", encoding="utf-8")
    file_c.write_text("# version 1 (good)", encoding="utf-8")

    tk = RepairToolkit(victoria_url="http://localhost:8010")

    # 1. Mark as last good
    tk.mark_last_good()
    assert tk.has_last_good()

    # 2. Corrupt files
    file_a.write_text("# broken version", encoding="utf-8")
    file_b.write_text("# broken version", encoding="utf-8")

    # 3. Rollback
    ok = tk.rollback_last_good()
    assert ok is True
    assert file_a.read_text(encoding="utf-8") == "# version 1 (good)"
    assert file_b.read_text(encoding="utf-8") == "# version 1 (good)"


def test_ai_pipeline_prompt_diet():
    """Verify that ai_pipeline functions produce slim and compact instructions."""
    from ai_pipeline import inject_anti_hallucination

    prompt = "Тестовый вопрос"
    res = inject_anti_hallucination(prompt, "Виктория")
    assert "Ты маленький помощник" not in res
    assert "ПРАВИЛА: Отвечай строго по фактам" in res
    assert len(res) < len(prompt) + 200
