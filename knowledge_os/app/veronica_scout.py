import asyncio
import logging
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from app.veronica_web_researcher import VeronicaWebResearcher
from app.services.knowledge_service import knowledge_service

logger = logging.getLogger("VeronicaScout")

class VeronicaScout:
    """
    Вероника-Разведчик: Автономный сбор знаний из внешних источников.
    Singularity 10.0: Global Intelligence Scouting
    """
    def __init__(self):
        self.researcher = VeronicaWebResearcher()
        self.targets = [
            "latest AI research papers 2026",
            "OpenAI Anthropic Google leaks and updates",
            "new LLM optimization techniques 2026",
            "autonomous agent architectures world class",
            "Mac Studio M4 Max AI performance benchmarks"
        ]
        self.is_running = False

    async def run_scouting_cycle(self):
        """Запуск цикла разведки."""
        logger.info(f"🕵️ [SCOUT] Начало цикла глобальной разведки: {datetime.now(timezone.utc)}")
        
        all_insights = []
        for target in self.targets:
            try:
                logger.info(f"🔍 [SCOUT] Исследование цели: {target}")
                result = await self.researcher.research_and_analyze(target, category="research", use_web=True)
                
                if result and result.get("analysis"):
                    insight = {
                        "topic": target,
                        "content": result["analysis"],
                        "sources": [r["url"] for r in result.get("web_results", [])],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    all_insights.append(insight)
                    
                    # Сохраняем в базу знаний как 'research_kb' (табу для чистки)
                    await self._save_to_knowledge(insight)
            except Exception as e:
                logger.error(f"❌ [SCOUT] Ошибка при исследовании {target}: {e}")

        logger.info(f"✅ [SCOUT] Цикл разведки завершен. Собрано инсайтов: {len(all_insights)}")
        return all_insights

    async def _save_to_knowledge(self, insight: Dict[str, Any]):
        """Сохранение инсайта в knowledge_nodes."""
        try:
            content = f"🌐 [GLOBAL SCOUT] {insight['topic']}\n\n{insight['content']}"
            metadata = {
                "type": "research_kb",
                "source": "veronica_scout",
                "urls": insight["sources"],
                "scout_version": "1.0"
            }
            
            # Используем knowledge_service для сохранения
            await knowledge_service.add_node(
                content=content,
                domain="Global Intelligence",
                confidence_score=0.95,
                metadata=metadata,
                is_verified=True
            )
            logger.info(f"💾 [SCOUT] Инсайт по теме '{insight['topic']}' сохранен в Research KB")
        except Exception as e:
            logger.error(f"❌ [SCOUT] Ошибка сохранения в БД: {e}")

async def start_scout_daemon(interval_hours: int = 12):
    """Запуск разведчика как фонового демона."""
    scout = VeronicaScout()
    while True:
        await scout.run_scouting_cycle()
        logger.info(f"💤 [SCOUT] Сон на {interval_hours} часов...")
        await asyncio.sleep(interval_hours * 3600)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(VeronicaScout().run_scouting_cycle())
