#!/usr/bin/env python3
"""One-shot priority re-distill smoke (default limit=2)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def _setup_path() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = os.path.join(root, "app")
    for p in (root, app):
        if p not in sys.path:
            sys.path.insert(0, p)


async def main(limit: int) -> int:
    _setup_path()
    from distillation_engine import KnowledgeDistiller

    stats = await KnowledgeDistiller().redistill_priority_batch(limit=limit)
    print(stats)
    return 0 if stats.get("updated", 0) >= 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.limit)))
