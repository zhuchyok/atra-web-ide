#!/usr/bin/env python3
"""
E2E smoke check for routing decision journal stream.

Runs from host:
1) read baseline XLEN in Redis
2) publish one event from knowledge_os_worker via LocalAIRouter helper
3) verify XLEN increased and show latest event
"""

from __future__ import annotations

import subprocess
import sys


def run(cmd: list[str]) -> str:
    out = subprocess.check_output(cmd, text=True).strip()
    return out


def main() -> int:
    try:
        before = int(
            run(
                [
                    "docker",
                    "exec",
                    "knowledge_os_redis",
                    "redis-cli",
                    "-s",
                    "/data/redis.sock",
                    "XLEN",
                    "stream:routing_decisions",
                ]
            )
            or "0"
        )
    except Exception as e:
        print(f"FAIL baseline_xlen: {e}")
        return 2

    publish_code = r"""
import asyncio
from app.local_router import LocalAIRouter

async def main():
    r = LocalAIRouter()
    await r._publish_routing_journal(
        task_type='e2e_smoke',
        category='chat',
        selected_route='ollama_studio',
        selected_model='victoria-wisdom-24k:latest',
        selected_node='Mac Studio (Ollama)',
        candidate_nodes=['Mac Studio (MLX)', 'Mac Studio (Ollama)'],
        latency_ms=5.55,
        success=True,
        reason='script_e2e',
    )

asyncio.run(main())
print('published')
""".strip()

    try:
        publish = subprocess.run(
            ["docker", "exec", "-i", "knowledge_os_worker", "python", "-"],
            input=publish_code,
            text=True,
            capture_output=True,
            check=True,
        )
        if publish.stdout.strip():
            print(publish.stdout.strip())
    except subprocess.CalledProcessError as e:
        print("FAIL publish")
        print(e.stdout or "")
        print(e.stderr or "")
        return 3

    try:
        after = int(
            run(
                [
                    "docker",
                    "exec",
                    "knowledge_os_redis",
                    "redis-cli",
                    "-s",
                    "/data/redis.sock",
                    "XLEN",
                    "stream:routing_decisions",
                ]
            )
            or "0"
        )
        latest = run(
            [
                "docker",
                "exec",
                "knowledge_os_redis",
                "redis-cli",
                "-s",
                "/data/redis.sock",
                "XREVRANGE",
                "stream:routing_decisions",
                "+",
                "-",
                "COUNT",
                "1",
            ]
        )
    except Exception as e:
        print(f"FAIL post_check: {e}")
        return 4

    delta = after - before
    print(f"xlen_before={before} xlen_after={after} delta={delta}")
    if delta < 1:
        print("FAIL stream_did_not_grow")
        return 5
    print("OK routing_journal_e2e")
    print(latest)
    return 0


if __name__ == "__main__":
    sys.exit(main())

