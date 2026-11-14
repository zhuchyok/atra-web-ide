import importlib.util
from pathlib import Path


_GATE = Path(__file__).resolve().parents[2] / "scripts" / "cognitive_quality_gate.py"
_spec = importlib.util.spec_from_file_location("cognitive_gate_under_test", _GATE)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def _xinfo_payload(*, lag: int = 0, pending: int = 0, consumers: int = 1) -> str:
    return "\n".join(
        [
            "name",
            "expert_workers",
            "consumers",
            str(consumers),
            "pending",
            str(pending),
            "lag",
            str(lag),
        ]
    )


def test_queue_health_ok_across_overflow_shared_and_dedicated(monkeypatch):
    def fake_run(cmd: str, timeout: int = 30):
        if "XINFO GROUPS stream:expert_tasks:" in cmd:
            return 0, _xinfo_payload(lag=0, pending=0, consumers=2), ""
        if "XINFO GROUPS stream:expert_tasks" in cmd:
            return 0, _xinfo_payload(lag=0, pending=0, consumers=1), ""
        if "XLEN" in cmd:
            return 0, "0", ""
        return 1, "", "unexpected"

    monkeypatch.setenv("EXPERT_STREAM_DEDICATED", "true")
    monkeypatch.setenv("EXPERT_DEDICATED_WORKERS", "Анна,Виктория,heavy")
    monkeypatch.setattr(_mod, "run", fake_run)

    res = _mod.queue_health()
    assert res["ok"] is True
    assert res["lag"] == 0
    assert res["pending"] == 0
    assert len(res["streams"]) >= 2


def test_queue_health_fails_when_dedicated_stream_has_lag(monkeypatch):
    def fake_run(cmd: str, timeout: int = 30):
        if "stream:expert_tasks:Анна" in cmd and "XINFO GROUPS" in cmd:
            return 0, _xinfo_payload(lag=7, pending=0, consumers=1), ""
        if "XINFO GROUPS stream:expert_tasks:" in cmd:
            return 0, _xinfo_payload(lag=0, pending=0, consumers=1), ""
        if "XINFO GROUPS stream:expert_tasks" in cmd:
            return 0, _xinfo_payload(lag=0, pending=0, consumers=1), ""
        if "XLEN" in cmd:
            return 0, "0", ""
        return 1, "", "unexpected"

    monkeypatch.setenv("EXPERT_STREAM_DEDICATED", "true")
    monkeypatch.setenv("EXPERT_DEDICATED_WORKERS", "Анна")
    monkeypatch.setattr(_mod, "run", fake_run)

    res = _mod.queue_health()
    assert res["ok"] is False
    anna = [x for x in res["streams"] if x.get("stream") == "expert_tasks:Анна"][0]
    assert anna["lag"] == 7
    assert anna["ok"] is False


def test_queue_health_missing_group_with_backlog_is_failure(monkeypatch):
    def fake_run(cmd: str, timeout: int = 30):
        if "stream:expert_tasks:overflow" in cmd and "XINFO GROUPS" in cmd:
            return 0, _xinfo_payload(lag=0, pending=0, consumers=1), ""
        if (
            "XINFO GROUPS stream:expert_tasks" in cmd
            and "stream:expert_tasks:" not in cmd
        ):
            return 0, "", ""
        if "XLEN stream:expert_tasks" in cmd:
            return 0, "12", ""
        return 1, "", "unexpected"

    monkeypatch.setenv("EXPERT_STREAM_DEDICATED", "false")
    monkeypatch.setattr(_mod, "run", fake_run)

    res = _mod.queue_health()
    assert res["ok"] is False
    shared = [x for x in res["streams"] if x.get("stream") == "expert_tasks"][0]
    assert shared.get("missing_group") is True
    assert shared.get("xlen") == 12


def test_contract_flags_match_policy_allows_insufficient_data_mode():
    contract = {"mode": "enforce", "enforce": "1"}
    routing = {"ok": True, "sufficient_data": False, "status": "insufficient_data"}
    assert _mod._contract_flags_match_policy(contract, routing) is True
