import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

from stream_reclaim import classify_pending, live_consumers_from_hash, pending_id


def _entry(msg_id, *, idle_ms, deliveries=1, consumer="worker_dead"):
    return {
        "message_id": msg_id,
        "time_since_delivered": idle_ms,
        "times_delivered": deliveries,
        "consumer": consumer,
    }


def test_live_consumer_idle_is_keep_not_reclaim():
    entries = [_entry("1-0", idle_ms=600_000, consumer="worker_live")]
    out = classify_pending(entries, live_consumers={"worker_live"}, min_idle_ms=300_000)
    assert pending_id(out["keep"][0]) == "1-0"
    assert out["reclaim"] == []
    assert out["zombies"] == []


def test_dead_consumer_idle_is_reclaim():
    entries = [_entry("2-0", idle_ms=400_000, consumer="worker_dead")]
    out = classify_pending(entries, live_consumers={"worker_live"}, min_idle_ms=300_000)
    assert pending_id(out["reclaim"][0]) == "2-0"
    assert out["keep"] == []


def test_missing_heartbeat_idle_still_reclaims():
    entries = [_entry("3-0", idle_ms=400_000, consumer="worker_gone")]
    out = classify_pending(entries, live_consumers=set(), min_idle_ms=300_000)
    assert pending_id(out["reclaim"][0]) == "3-0"


def test_fresh_idle_is_keep():
    entries = [_entry("4-0", idle_ms=1_000, consumer="worker_dead")]
    out = classify_pending(entries, live_consumers=set(), min_idle_ms=300_000)
    assert pending_id(out["keep"][0]) == "4-0"
    assert out["reclaim"] == []


def test_high_delivery_live_consumer_is_keep_not_zombie():
    entries = [_entry("5-0", idle_ms=400_000, deliveries=11, consumer="worker_live")]
    out = classify_pending(entries, live_consumers={"worker_live"}, min_idle_ms=300_000)
    assert pending_id(out["keep"][0]) == "5-0"
    assert out["reclaim"] == []
    assert out["zombies"] == []


def test_high_delivery_dead_consumer_is_zombie():
    entries = [_entry("5-1", idle_ms=400_000, deliveries=11, consumer="worker_dead")]
    out = classify_pending(entries, live_consumers={"worker_live"}, min_idle_ms=300_000)
    assert pending_id(out["zombies"][0]) == "5-1"
    assert out["reclaim"] == []


def test_inflight_is_keep_not_drop_or_reclaim():
    entries = [_entry("6-0", idle_ms=800_000, consumer="worker_self")]
    out = classify_pending(
        entries,
        live_consumers=set(),
        inflight_ids={"6-0"},
        min_idle_ms=300_000,
    )
    assert pending_id(out["keep"][0]) == "6-0"
    assert out["reclaim"] == []
    assert out["zombies"] == []


def test_worker_uses_classify_and_acks_after_process():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = open(
        os.path.join(root, "knowledge_os", "app", "expert_worker.py"), encoding="utf-8"
    ).read()
    assert "classify_pending(" in src
    assert "live_consumers_from_hash(" in src
    assert "_inflight_msg_ids" in src
    assert "Failed to early-xack" not in src
    assert "Dropped {len(_stale_ids)} stale pending messages" not in src
    assert "worker_dropped_stale_pending" not in src
    run_at = src.find("async def _run_task")
    process_at = src.find("await process_task(_p)", run_at)
    ack_at = src.find("await client.xack(", process_at)
    assert run_at > 0 and process_at > run_at and ack_at > process_at


def test_live_consumers_from_hash_ttl():
    now = 1_000_000.0
    mapping = {
        "Анна".encode("utf-8"): json.dumps(
            {"consumer": "worker_anna_1", "ts": int(now) - 10}
        ).encode(),
        "Инна": json.dumps({"consumer": "worker_dead", "ts": int(now) - 200}),
    }
    live = live_consumers_from_hash(mapping, now=now, ttl_sec=90)
    assert "worker_anna_1" in live
    assert "worker_dead" not in live
