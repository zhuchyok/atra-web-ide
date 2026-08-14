"""
Periodic refresh of curated AI Research (dashboard «Последние находки»).

Runs inside knowledge_nightly — no extra container.
  1) Re-index local cognitive docs (cheap, matches dashboard filter).
  2) One VeronicaScout topic with source=scout_research + file_path.

Does NOT git-clone system_prompts_leaks (thousands of files).
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
from pathlib import Path
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_INDEXER_PATH = Path(__file__).resolve().parent.parent / "scripts" / "index_cognitive_code.py"


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


def _load_cognitive_indexer():
    if not _INDEXER_PATH.is_file():
        raise FileNotFoundError(f"index_cognitive_code.py not found: {_INDEXER_PATH}")
    spec = importlib.util.spec_from_file_location("index_cognitive_code", _INDEXER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_INDEXER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def refresh_cognitive_docs() -> int:
    """Re-index COGNITIVE_CODE.md (+ extra docs). Returns inserted chunk count."""
    mod = _load_cognitive_indexer()
    db_url = os.getenv("DATABASE_URL") or getattr(mod, "DATABASE_URL", None)
    if not db_url:
        logger.warning("📚 [RESEARCH] skip docs: DATABASE_URL is empty")
        return 0

    files = list(getattr(mod, "DEFAULT_FILES", []))
    if _env_flag("NIGHTLY_RESEARCH_EXTRA_DOCS", "true"):
        files.extend(getattr(mod, "EXTRA_DOCS", []))

    conn = await asyncpg.connect(db_url)
    try:
        domain_id = await mod.get_or_create_domain(conn, "AI Research")
        seen: set[str] = set()
        total = 0
        for path in files:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            total += int(await mod.index_one_file(conn, path, domain_id) or 0)
        logger.info("📚 [RESEARCH] cognitive docs indexed chunks=%s files=%s", total, len(seen))
        return total
    finally:
        await conn.close()


async def refresh_scout() -> int:
    """One (or N) scout topics into AI Research with dashboard-visible metadata."""
    if not _env_flag("NIGHTLY_RESEARCH_SCOUT_ENABLED", "true"):
        logger.info("📚 [RESEARCH] scout skipped (NIGHTLY_RESEARCH_SCOUT_ENABLED=false)")
        return 0

    max_topics = max(0, int(os.getenv("NIGHTLY_RESEARCH_SCOUT_MAX_TOPICS", "1")))
    if max_topics == 0:
        return 0

    timeout_sec = max(30.0, float(os.getenv("NIGHTLY_RESEARCH_SCOUT_TIMEOUT_SEC", "180")))
    try:
        from veronica_scout import VeronicaScout
    except ImportError:
        from app.veronica_scout import VeronicaScout

    scout = VeronicaScout()
    insights = await asyncio.wait_for(
        scout.run_scouting_cycle(max_targets=max_topics),
        timeout=timeout_sec,
    )
    count = len(insights or [])
    logger.info("📚 [RESEARCH] scout insights=%s max_topics=%s", count, max_topics)
    return count


async def refresh_visual_index() -> int:
    """Bounded VisualRAG bootstrap so /health vectors > 0 (docs only, not whole repo)."""
    if not _env_flag("NIGHTLY_VISUAL_INDEX_ENABLED", "true"):
        return 0
    url = os.getenv("VISUAL_SEARCH_URL", "http://victoria-visual-search:8005").rstrip("/")
    docs = Path(os.getenv("CURATED_DOCS_DIR", "/app/docs"))
    max_n = max(1, min(int(os.getenv("NIGHTLY_VISUAL_INDEX_MAX_FILES", "15")), 40))
    preferred = [
        "COGNITIVE_CODE.md",
        "THINKING_AND_APPROACH.md",
        "MASTER_REFERENCE.md",
        "CHANGES_FROM_OTHER_CHATS.md",
        "TEAM_PERSONALITIES.md",
    ]
    files: list[Path] = []
    for name in preferred:
        path = docs / name
        if path.is_file():
            files.append(path)
    if docs.is_dir():
        for path in sorted(docs.glob("*.md")):
            if path not in files:
                files.append(path)
            if len(files) >= max_n:
                break
    files = files[:max_n]
    if not files:
        logger.warning("📚 [RESEARCH] visual skip: no markdown under %s", docs)
        return 0

    import httpx

    indexed = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            health = await client.get(f"{url}/health")
            health.raise_for_status()
        except Exception as exc:
            logger.warning("📚 [RESEARCH] visual-search unreachable: %s", exc)
            return 0
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:4000]
                if not text.strip():
                    continue
                resp = await client.post(
                    f"{url}/index",
                    json={"file_path": str(path), "text_content": text},
                )
                if resp.status_code == 200:
                    indexed += 1
                else:
                    logger.warning(
                        "📚 [RESEARCH] visual index %s -> %s", path.name, resp.status_code
                    )
            except Exception as exc:
                logger.warning("📚 [RESEARCH] visual index %s failed: %s", path.name, exc)
    logger.info("📚 [RESEARCH] visual indexed=%s/%s", indexed, len(files))
    return indexed


async def run_curated_research_refresh() -> dict[str, Any]:
    stats: dict[str, Any] = {"docs_chunks": 0, "scout_insights": 0, "visual_indexed": 0, "ok": True}
    try:
        stats["docs_chunks"] = await refresh_cognitive_docs()
    except Exception as exc:
        stats["ok"] = False
        stats["docs_error"] = str(exc)
        logger.warning("📚 [RESEARCH] cognitive docs failed: %s", exc)

    try:
        stats["scout_insights"] = await refresh_scout()
    except Exception as exc:
        stats["ok"] = False
        stats["scout_error"] = str(exc)
        logger.warning("📚 [RESEARCH] scout failed: %s", exc)

    try:
        stats["visual_indexed"] = await refresh_visual_index()
    except Exception as exc:
        stats["ok"] = False
        stats["visual_error"] = str(exc)
        logger.warning("📚 [RESEARCH] visual index failed: %s", exc)

    return stats


async def run_continuous_research_refresh() -> None:
    """Background loop for knowledge_nightly. First cycle runs immediately."""
    interval = max(300, int(os.getenv("NIGHTLY_RESEARCH_INTERVAL_SEC", "21600")))
    enabled = _env_flag("NIGHTLY_RESEARCH_REFRESH_ENABLED", "true")
    logger.info(
        "📚 [NIGHTLY] Curated research refresh started (enabled=%s interval=%ss)",
        enabled,
        interval,
    )
    while True:
        if enabled:
            try:
                stats = await run_curated_research_refresh()
                logger.info("📚 [NIGHTLY] Curated research refresh: %s", stats)
            except Exception as exc:
                logger.warning("📚 [NIGHTLY] Curated research refresh failed: %s", exc)
        await asyncio.sleep(interval)
