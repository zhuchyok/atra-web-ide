import importlib.util
from pathlib import Path

import pytest

_SCANNER = Path(__file__).resolve().parents[2] / "knowledge_os" / "app" / "medic" / "log_scanner.py"
_spec = importlib.util.spec_from_file_location("log_scanner_runtime_under_test", _SCANNER)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def _mk_scanner(tmp_path):
    scanner = _mod.LogScanner()
    scanner.dedup.state_path = str(tmp_path / "dedup_state.json")
    scanner.dedup.history.clear()
    scanner._task_timestamps = []
    return scanner


@pytest.mark.asyncio
async def test_send_to_victoria_rate_limit_consumed_only_on_success(tmp_path, monkeypatch):
    scanner = _mk_scanner(tmp_path)

    class _Resp:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = "x"
            self.content = b"{}"

        def json(self):
            return {"task_id": "t1"}

    class _Client:
        def __init__(self, status_code):
            self._status_code = status_code

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return _Resp(self._status_code)

    # First request fails -> must not consume a slot.
    monkeypatch.setattr(_mod.httpx, "AsyncClient", lambda timeout=30.0: _Client(500))
    err = {"type": "TypeError", "message": "TypeError: x", "timestamp": "t"}
    ok = await scanner.send_to_victoria("c1", err)
    assert ok is False
    assert scanner._task_timestamps == []

    # Second request succeeds -> consumes exactly one slot.
    monkeypatch.setattr(_mod.httpx, "AsyncClient", lambda timeout=30.0: _Client(200))
    ok = await scanner.send_to_victoria("c1", err)
    assert ok is True
    assert len(scanner._task_timestamps) == 1


@pytest.mark.asyncio
async def test_scan_container_retries_same_error_until_success_then_dedups(tmp_path, monkeypatch):
    scanner = _mk_scanner(tmp_path)
    calls = {"send": 0}

    def fake_logs(container, since=None):
        return "ERROR TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'\n"

    async def fake_send(container, error, **kwargs):
        calls["send"] += 1
        # first attempt fails, second succeeds
        return calls["send"] >= 2

    monkeypatch.setattr(scanner, "get_container_logs", fake_logs)
    monkeypatch.setattr(scanner, "send_to_victoria", fake_send)

    # 1st scan: send fails => no dedup mark, should retry next time
    assert await scanner.scan_container("worker-1") == 1
    # 2nd scan: same error retried and succeeds => dedup mark written
    assert await scanner.scan_container("worker-1") == 1
    # 3rd scan: same error now deduplicated
    assert await scanner.scan_container("worker-1") == 0
    assert calls["send"] == 2


def test_watch_containers_still_excludes_self_scanner_containers(tmp_path, monkeypatch):
    scanner = _mk_scanner(tmp_path)
    monkeypatch.setattr(
        _mod,
        "WATCH_CONTAINERS",
        ["log-scanner", "victoria-medic", "knowledge_os_orchestrator"],
    )
    assert scanner.get_containers() == ["knowledge_os_orchestrator"]
