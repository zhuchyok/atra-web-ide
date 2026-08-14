import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("VeronicaScout")

try:
    from veronica_web_researcher import VeronicaWebResearcher
except ImportError:
    from app.veronica_web_researcher import VeronicaWebResearcher


def _slug(text: str, max_len: int = 60) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return (raw or "insight")[:max_len]


def select_scout_targets(targets: list[str], max_targets: int, day_of_year: int) -> list[str]:
    """Rotate topics by day so a 1-topic cycle does not always hit the same query."""
    if not targets:
        return []
    n = max(0, int(max_targets))
    if n == 0:
        return []
    n = min(n, len(targets))
    start = int(day_of_year) % len(targets)
    rotated = targets[start:] + targets[:start]
    return rotated[:n]


def scout_knowledge_payload(insight: dict[str, Any]) -> dict[str, Any]:
    """Metadata that matches dashboard curated AI Research filter."""
    topic = str(insight.get("topic") or "insight")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_path = f"scout/{stamp}-{_slug(topic)}.md"
    content = f"🌐 [GLOBAL SCOUT] {topic}\n\n{insight.get('content') or ''}"
    return {
        "domain": "AI Research",
        "content": content,
        "metadata": {
            "type": "research_kb",
            "source": "scout_research",
            "file_path": file_path,
            "urls": insight.get("sources") or [],
            "scout_version": "1.1",
            "topic": topic,
        },
    }


def is_usable_scout_analysis(text: str) -> bool:
    """Skip empty/error LLM stubs so they never land in curated feed."""
    t = (text or "").strip()
    if len(t) < 80:
        return False
    if t.startswith("❌"):
        return False
    lowered = t.lower()
    if "ошибка локальной модели" in lowered or "нет доступных локальных моделей" in lowered:
        return False
    return True


class VeronicaScout:
    """Вероника-Разведчик: автономный сбор знаний (Singularity 10.0 Global Intelligence)."""

    def __init__(self):
        self.researcher = VeronicaWebResearcher()
        self.targets = [
            "latest AI research papers 2026",
            "OpenAI Anthropic Google leaks and updates",
            "new LLM optimization techniques 2026",
            "autonomous agent architectures world class",
            "Mac Studio M4 Max AI performance benchmarks",
        ]
        self.is_running = False

    async def run_scouting_cycle(self, max_targets: Optional[int] = None):
        """Запуск цикла разведки. max_targets=1 keeps MLX load bounded (nightly)."""
        logger.info(f"🕵️ [SCOUT] Начало цикла глобальной разведки: {datetime.now(timezone.utc)}")
        if max_targets is None:
            max_targets = int(os.getenv("SCOUT_MAX_TARGETS", str(len(self.targets))))
        day_of_year = datetime.now(timezone.utc).timetuple().tm_yday
        targets = select_scout_targets(self.targets, max_targets, day_of_year)

        all_insights = []
        for target in targets:
            try:
                logger.info(f"🔍 [SCOUT] Исследование цели: {target}")
                result = await self.researcher.research_and_analyze(
                    target, category="research", use_web=True
                )

                if result and is_usable_scout_analysis(result.get("analysis") or ""):
                    insight = {
                        "topic": target,
                        "content": result["analysis"],
                        "sources": [r["url"] for r in result.get("web_results", [])],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    all_insights.append(insight)

                    await self._save_to_knowledge(insight)
                else:
                    preview = ((result or {}).get("analysis") or "")[:80]
                    logger.warning("⚠️ [SCOUT] Пропуск пустого/ошибочного анализа: %s", preview)
            except Exception as e:
                logger.error(f"❌ [SCOUT] Ошибка при исследовании {target}: {e}")

        logger.info(f"✅ [SCOUT] Цикл разведки завершен. Собрано инсайтов: {len(all_insights)}")
        return all_insights

    async def _save_to_knowledge(self, insight: dict[str, Any]):
        """Сохранение инсайта в knowledge_nodes (AI Research, dashboard-visible)."""
        payload = scout_knowledge_payload(insight)
        try:
            try:
                from db_pool import get_pool
                from semantic_cache import get_embedding
            except ImportError:
                from app.db_pool import get_pool
                from app.semantic_cache import get_embedding

            embedding = await get_embedding(payload["content"][:8000])
            if not embedding:
                embedding = [0.0] * 768
            if isinstance(embedding, list):
                if len(embedding) > 768:
                    embedding = embedding[:768]
                elif len(embedding) < 768:
                    embedding = embedding + [0.0] * (768 - len(embedding))
                embedding_str = "[" + ",".join(map(str, embedding)) + "]"
            else:
                embedding_str = embedding

            pool = await get_pool()
            async with pool.acquire() as conn:
                domain_id = await conn.fetchval(
                    "SELECT id FROM domains WHERE name = $1", payload["domain"]
                )
                if not domain_id:
                    domain_id = await conn.fetchval(
                        "INSERT INTO domains (name, description) VALUES ($1, $2) RETURNING id",
                        payload["domain"],
                        "Curated AI research for dashboard feed",
                    )
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes
                        (content, embedding, domain_id, metadata, confidence_score, is_verified)
                    VALUES ($1, $2::vector, $3, $4::jsonb, $5, $6)
                    """,
                    payload["content"],
                    embedding_str,
                    domain_id,
                    json.dumps(payload["metadata"]),
                    0.90,
                    True,
                )
            logger.info(
                "💾 [SCOUT] Инсайт '%s' → AI Research (%s)",
                insight.get("topic"),
                payload["metadata"]["file_path"],
            )
        except Exception as e:
            logger.error(f"❌ [SCOUT] Ошибка сохранения в БД: {e}")


async def start_scout_daemon(interval_hours: int = 6):
    """Запуск разведчика как фонового демона (Slow Mode)."""
    scout = VeronicaScout()
    while True:
        logger.info("🐢 [SCOUT] Запуск цикла разведки в фоновом режиме (не спеша)...")
        await scout.run_scouting_cycle(max_targets=int(os.getenv("SCOUT_MAX_TARGETS", "1")))
        logger.info(f"💤 [SCOUT] Сон на {interval_hours} часов до следующего цикла...")
        await asyncio.sleep(interval_hours * 3600)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(VeronicaScout().run_scouting_cycle(max_targets=1))
