#!/usr/bin/env python3
"""
Мониторинг hit-rate RAG Context Cache.
Запуск: curl http://localhost:8080/api/cache/stats
Или: PYTHONPATH=backend:. python scripts/monitor_cache_performance.py
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))


def main():
    import httpx
    base = os.getenv("API_URL", "http://localhost:8080")
    url = f"{base.rstrip('/')}/api/cache/stats"
    try:
        r = httpx.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "ok":
            hr = data.get("hit_rate_pct", 0)
            print(f"RAG Cache: hit rate {hr}% | hits={data.get('hits')} misses={data.get('misses')} | uptime {data.get('uptime_sec', 0):.0f}s")
        else:
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"❌ {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
