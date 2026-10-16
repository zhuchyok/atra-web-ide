import json
import logging
import re
import time
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
        # [v149.55] LLM circuit breaker state
        self._llm_fail_streak = 0
        self._llm_cooldown_until = 0.0

    def _llm_available(self) -> bool:
        return time.time() >= self._llm_cooldown_until

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
        # [v149.55] Circuit breaker: при недоступном LLM (стаб/пусто) LLM-фаза
        # отключается на кулдаун — иначе каждый вызов тащит полный RAG-прогон
        # впустую (LOOP-BREAKER резал 6+ попыток/10мин в orchestrator/nightly,
        # 15.10). Regex-сущности извлекаются всегда.
        if len(content) > 300 and self._llm_available():
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

                json_match = re.search(r"\[.*\]", str(response or ""), re.DOTALL)
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
                    self._llm_fail_streak = 0
                else:
                    # Стаб/не-JSON — LLM не дал сущностей: копим отказ
                    self._llm_fail_streak = getattr(self, "_llm_fail_streak", 0) + 1
                    if self._llm_fail_streak >= 3:
                        self._llm_cooldown_until = time.time() + 300
                        self._llm_fail_streak = 0
                        logger.warning(
                            "[ENTITY-EXTRACTOR] LLM недоступен (стаб/не-JSON ×3) — "
                            "LLM-фаза на кулдауне 5 мин, работаем на regex"
                        )
            except Exception as e:
                # [v149.58c] исключение (например, loop-breaker) тоже отказ LLM:
                # иначе цикл живёт на loop-breaker'е, минуя circuit breaker
                self._llm_fail_streak = getattr(self, "_llm_fail_streak", 0) + 1
                if self._llm_fail_streak >= 3:
                    self._llm_cooldown_until = time.time() + 300
                    self._llm_fail_streak = 0
                    logger.warning(
                        "[ENTITY-EXTRACTOR] LLM недоступен (exception ×3) — LLM-фаза на кулдауне 5 мин"
                    )
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
