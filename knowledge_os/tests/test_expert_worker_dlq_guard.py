import os


def test_dlq_guard_skips_active_blackboard_heartbeat():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_path = os.path.join(root, "knowledge_os", "app", "expert_worker.py")
    src = open(src_path, encoding="utf-8").read()

    assert "🛟 [DLQ-GUARD] Skip zombie kill for active heartbeat" in src
    assert "blackboard:heartbeat:{task_id}" in src
    assert "if await client.exists(hb_key):" in src
