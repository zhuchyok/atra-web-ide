import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "events.py"
_spec = importlib.util.spec_from_file_location("turn_harness_events", _PATH)
events = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(events)


def test_append_and_single_close(tmp_path):
    events.append_event(str(tmp_path), "t1", "turn_opened", goal="почини лог")
    events.append_event(str(tmp_path), "t1", "tool_result", status="error", text="x" * 5000)
    events.append_event(str(tmp_path), "t1", "turn_closed", reason="completed")
    rows = events.read_events(str(tmp_path), "t1")
    assert [r["type"] for r in rows] == ["turn_opened", "tool_result", "turn_closed"]
    assert rows[0]["seq"] == 1 and rows[-1]["seq"] == 3
    assert rows[-1]["reason"] == "completed"


def test_reason_for_store_prefers_explicit():
    assert events.reason_for_store({"status": "failed", "turn_end_reason": "max_steps"}) == "max_steps"
    assert events.reason_for_store({"status": "failed", "error": "Background timeout after 180s"}) == "timeout"
    assert events.reason_for_store({"status": "completed"}) == "completed"
    assert events.reason_for_store({"status": "cancelled"}) == "cancelled"
    assert events.reason_for_store({"status": "failed", "error": "boom"}) == "tool_error"


def test_derive_prompt_keeps_anchors_inside_budget():
    ev = [
        {"seq": 1, "type": "turn_opened", "goal": "цель-якорь"},
        {"seq": 2, "type": "tool_result", "status": "error", "text": "ОШИБКА-ЯКОРЬ " + ("z" * 8000)},
        {"seq": 3, "type": "approval_decided", "outcome": "allowed-once"},
        {"seq": 4, "type": "files_presented", "paths": ["src/a.py"]},
        {"seq": 5, "type": "model_message", "text": "m" * 20000},
    ]
    text = events.derive_prompt(ev, max_chars=12000, tool_max=4000)
    assert "цель-якорь" in text
    assert "allowed-once" in text
    assert "src/a.py" in text
    assert "ОШИБКА-ЯКОРЬ" in text
    assert len(text) <= 12000


def test_flag_off_means_caller_skips(tmp_path, monkeypatch):
    monkeypatch.delenv("TURN_LOG", raising=False)
    assert events.logging_enabled() is False
    monkeypatch.setenv("TURN_LOG", "1")
    assert events.logging_enabled() is True
    monkeypatch.setenv("TURN_LOG_DIR", str(tmp_path))
    assert events.log_dir() == str(tmp_path)


def test_sweep_closes_orphan_as_crashed(tmp_path):
    events.append_event(str(tmp_path), "open1", "turn_opened", goal="g")
    events.append_event(str(tmp_path), "done1", "turn_opened", goal="g")
    events.append_event(str(tmp_path), "done1", "turn_closed", reason="completed")
    n = events.sweep_open_turns(str(tmp_path))
    assert n == 1
    last = events.read_events(str(tmp_path), "open1")[-1]
    assert last["type"] == "turn_closed" and last["reason"] == "crashed"
    assert events.sweep_open_turns(str(tmp_path)) == 0
