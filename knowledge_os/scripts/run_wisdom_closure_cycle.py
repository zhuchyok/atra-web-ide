#!/usr/bin/env python3
"""One-shot: mentorship → success retrieval → SOP (Wisdom tab closure)."""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure app imports resolve inside containers and local runs
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "app")
for path in (ROOT, APP, "/app", "/app/knowledge_os/app"):
    if path not in sys.path and (os.path.isdir(path) or path.startswith("/app")):
        sys.path.insert(0, path)


async def main() -> None:
    os.environ.setdefault("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    os.environ.setdefault("MENTORSHIP_AUDIT_TIMEOUT_SEC", "60")
    os.environ.setdefault("SOP_GENERATE_TIMEOUT_SEC", "60")

    print("=== MENTORSHIP ===", flush=True)
    from mentorship_engine import run_mentorship_cycle

    await run_mentorship_cycle(limit=3)

    print("=== SUCCESS RETRIEVER ===", flush=True)
    from success_retriever import SuccessRetriever

    out = await SuccessRetriever().get_relevant_successes(
        "проверь статус проекта и health сервисов",
        limit=3,
        min_similarity=0.35,
    )
    print(f"sra_text_len={len(out or '')}", flush=True)

    print("=== SOP ===", flush=True)
    from sop_generator import SOPGenerator

    await SOPGenerator().run_sop_cycle(limit=2)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
