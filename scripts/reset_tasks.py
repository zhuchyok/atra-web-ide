import redis
import json

r = redis.Redis(host='localhost', port=6381, db=0)

tasks_to_reset = [
    "RD_20260429_183113_rd_002",
    "RD_20260429_183048_rd_002",
    "RD_20260429_183048_rd_001",
    "VERIFY_RD_20260429_183113_rd_002_4dbecd70"
]

goals = r.hgetall("blackboard:goals")

for task_id_bytes, data_bytes in goals.items():
    task_id = task_id_bytes.decode()
    if task_id in tasks_to_reset:
        data = json.loads(data_bytes.decode())
        print(f"Resetting task {task_id} (current status: {data.get('status')})")
        data["status"] = "bidding_open"
        data["assignee"] = None
        if "claimed_at" in data:
            del data["claimed_at"]
        r.hset("blackboard:goals", task_id, json.dumps(data))
        # Also delete any stale heartbeats
        r.delete(f"blackboard:heartbeat:{task_id}")

print("Done.")
