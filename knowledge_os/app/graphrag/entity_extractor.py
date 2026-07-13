import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    name: str
    type: str
    confidence: float
    metadata: Dict[str, Any]


class EntityExtractor:
    """
    Извлекает сущности и связи из текста для построения GraphRAG.
    Использует гибридный подход: регулярные выражения + LLM (через ai_core).
    """

    def __init__(self):
        # Базовые паттерны для быстрой экстракции
        self.patterns = {
            "expert": r"@(\w+)",
            "file": r"`([\w\./-]+\.\w+)`",
            "tech": r"(Docker|PostgreSQL|Redis|FastAPI|Svelte|Python|MLX|Ollama|DeepSeek)",
            "concept": r"💎\s*([А-ЯA-Z\s]+)",
        }

    async def extract_entities(self, content: str) -> List[Entity]:
        """
        [SINGULARITY 23.8] Optimized Entity Extraction:
        Использует Offloading для регулярных выражений и легкие модели.
        """
        import asyncio

        entities = []

        def _extract_regex():
            found = []
            for e_type, pattern in self.patterns.items():
                matches = re.finditer(pattern, content)
                for match in matches:
                    found.append(
                        Entity(
                            name=match.group(1),
                            type=e_type,
                            confidence=0.8,
                            metadata={"source": "regex"},
                        )
                    )
            return found

        # 1. Быстрая экстракция (Offloaded)
        entities.extend(await asyncio.to_thread(_extract_regex))

        # 2. Глубокая экстракция через LLM (если текст длинный и важный)
        if len(content) > 300:  # Повышен порог для экономии ресурсов
            try:
                from app.ai_core import run_smart_agent_async

                prompt = f"""Проанализируй текст и извлеки ключевые сущности (технологии, люди, концепции, файлы).
Верни ТОЛЬКО JSON список объектов: [{{"name": "...", "type": "...", "confidence": 0.9}}]
ТЕКСТ:
{content[:1000]}"""

                # Используем легкую модель для экстракции
                response = await run_smart_agent_async(
                    prompt, expert_name="Виктория", category="fast"
                )

                # Парсинг JSON
                json_match = re.search(r"\[.*\]", response, re.DOTALL)
                if json_match:
                    llm_entities = json.loads(json_match.group(0))
                    for le in llm_entities:
                        entities.append(
                            Entity(
                                name=le["name"],
                                type=le["type"],
                                confidence=le.get("confidence", 0.7),
                                metadata={"source": "llm"},
                            )
                        )
            except Exception as e:
                logger.debug(f"LLM Entity Extraction failed: {e}")

        # Дедупликация по имени
        unique_entities = {e.name.lower(): e for e in entities}.values()
        return list(unique_entities)


_extractor = None


def get_entity_extractor():
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor
