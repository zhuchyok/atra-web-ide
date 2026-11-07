import asyncio
import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "approval.py"
_spec = importlib.util.spec_from_file_location("turn_harness_approval", _PATH)
approval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(approval)


def test_never_rejects_without_answerer():
    called = {"n": 0}

    async def answerer(_req):
        called["n"] += 1
        return "allowed-once"

    out = asyncio.run(
        approval.decide(
            task_id="t",
            tool_name="git_push",
            call_id="c1",
            reason="push",
            policy="never",
            answerer=answerer,
        )
    )
    assert out == "rejected"
    assert called["n"] == 0


def test_missing_answerer_is_unavailable():
    out = asyncio.run(
        approval.decide(
            task_id="t",
            tool_name="git_push",
            call_id="c1",
            reason="push",
            policy="ask",
            answerer=None,
        )
    )
    assert out == "unavailable"


def test_only_allowed_once_passes():
    async def ok(_req):
        return "allowed-once"

    async def junk(_req):
        return "yes"

    assert (
        asyncio.run(
            approval.decide(
                task_id="t",
                tool_name="sh",
                call_id="c",
                reason="r",
                policy="ask",
                answerer=ok,
            )
        )
        == "allowed-once"
    )
    assert (
        asyncio.run(
            approval.decide(
                task_id="t",
                tool_name="sh",
                call_id="c",
                reason="r",
                policy="ask",
                answerer=junk,
            )
        )
        == "unavailable"
    )
