import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# [v149.58d] Circuit breaker state — МОДУЛЬНЫЙ: экземпляр экстрактора может
# пересоздаваться (orchestrator/graphrag пути), instance-уровень терял счётчик
# и петля жила дальше (105 LOOP-BREAKER hits в orchestrator за 17-18.10).
_LLM_FAIL_STREAK = 0
_LLM_COOLDOWN_UNTIL = 0.0


def _llm_available() -> bool:
    return time.time() >= _LLM_COOLDOWN_UNTIL


def _llm_note_failure() -> None:
    global _LLM_FAIL_STREAK, _LLM_COOLDOWN_UNTIL
    _LLM_FAIL_STREAK += 1
    if _LLM_FAIL_STREAK >= 3:
        _LLM_COOLDOWN_UNTIL = time.time() + 300
        _LLM_FAIL_STREAK = 0
        logger.warning(
            "[ENTITY-EXTRACTOR] LLM недоступен (отказы ×3) — LLM-фаза на кулдауне 5 мин, работаем на regex"
        )


def _llm_note_success() -> None:
    global _LLM_FAIL_STREAK
    _LLM_FAIL_STREAK = 0


@dataclass
class Entity:
    name: str
    type: str
    confidence: float
    metadata: Dict[str, Any]


class EntityExtractor:
    """
    Извлекает сущности и связи из текста для построения GraphRAG.
    Использует гибридный подход: регулярные выражения + LLM (через руки 11437).
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

        # 2. Глубокая экстракция через LLM на РУКАХ (не мозг Victoria).
        # Раньше smart-agent Victoria Victoria → LOOP-BREAKER на 11434.
        # Kill-switch: ENTITY_EXTRACTOR_LLM=false → только regex.
        llm_on = os.getenv("ENTITY_EXTRACTOR_LLM", "true").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if llm_on and len(content) > 300 and _llm_available():
            try:
                llm_entities = await self._extract_via_hands(content[:1000])
                if llm_entities:
                    entities.extend(llm_entities)
                    _llm_note_success()
                else:
                    _llm_note_failure()
            except Exception as e:
                # [v149.58c] исключение тоже отказ LLM — иначе минуем circuit breaker
                _llm_note_failure()
                logger.debug(f"LLM Entity Extraction failed: {e}")

        # Дедупликация по имени
        unique_entities = {e.name.lower(): e for e in entities}.values()
        return list(unique_entities)

    async def _extract_via_hands(self, text: str) -> List[Entity]:
        """JSON entity extract on Ollama hands (11437 phi), not Victoria brain."""
        import httpx

        hands = (
            os.getenv("OLLAMA_HANDS_URL")
            or os.getenv("OLLAMA_EMBED_URL")
            or "http://host.docker.internal:11437"
        ).rstrip("/")
        model = os.getenv("ENTITY_EXTRACTOR_MODEL", "phi3.5:3.8b")
        prompt = (
            "Извлеки ключевые сущности (технологии, люди, концепции, файлы).\n"
            'Верни ТОЛЬКО JSON список: [{"name":"...","type":"...","confidence":0.9}]\n'
            f"ТЕКСТ:\n{text}"
        )
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{hands}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Ты парсер сущностей. Ответь только JSON-массивом.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0, "num_ctx": 2048, "num_predict": 512},
                },
            )
            resp.raise_for_status()
            data = resp.json()
        raw = ""
        if isinstance(data, dict):
            msg = data.get("message") or {}
            raw = str(msg.get("content") or data.get("response") or "")
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not json_match:
            return []
        parsed = json.loads(json_match.group(0))
        out: List[Entity] = []
        for le in parsed or []:
            if not isinstance(le, dict) or not le.get("name"):
                continue
            out.append(
                Entity(
                    name=str(le["name"]),
                    type=str(le.get("type") or "concept"),
                    confidence=float(le.get("confidence", 0.7) or 0.7),
                    metadata={"source": "llm_hands"},
                )
            )
        return out


_extractor = None


def get_entity_extractor():
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor
