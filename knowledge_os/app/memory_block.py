"""
Memory Block System (Singularity 21.32)
Извлекает ключевые решения и факты из истории диалога для предотвращения противоречий.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryBlockSystem:
    """Система управления блоком памяти в промптах."""

    def __init__(self):
        # Паттерны для извлечения фактов
        self.fact_patterns = [
            r"используем\s+([a-zA-Z0-9\s\.\-_]+)",
            r"стек:\s+([a-zA-Z0-9\s\.\-_]+)",
            r"выбрали\s+([a-zA-Z0-9\s\.\-_]+)",
            r"решили\s+([a-zA-Z0-9\s\.\-_]+)",
            r"база\s+данных:\s+([a-zA-Z0-9\s\.\-_]+)",
            r"порт:\s+(\d+)",
            r"файл:\s+([a-zA-Z0-9\s\.\/_\-]+)",  # [SINGULARITY 21.33] Context Anchoring
            r"doc:\s+([a-zA-Z0-9\s\.\/_\-]+)",  # [SINGULARITY 21.33] Context Anchoring
            r"lesson:\s+([a-zA-Z0-9\s\.\/_\-,\!]+)",  # [SINGULARITY 22.3] Episodic Memory
        ]

    def extract_memory(self, history: List[Dict[str, Any]]) -> str:
        """
        Извлекает ключевые факты из истории и формирует блок памяти.
        [SINGULARITY 21.35] Dual-Process Memory:
        System 1 (Fast): Факты и якоря.
        System 2 (Slow): Рефлексия и выводы.
        """
        if not history:
            return ""

        facts = set()
        anchors = set()  # [SINGULARITY 21.33] Якоря контекста
        lessons = set()  # [SINGULARITY 22.3] Episodic Memory (Lessons Learned)
        reflections = []  # [SINGULARITY 21.35] System 2: Рефлексия

        for msg in history:
            content = msg.get("content", "")
            if not content:
                continue

            # System 1: Extraction
            for pattern in self.fact_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if "файл:" in pattern or "doc:" in pattern:
                        anchors.add(match.strip())
                    elif "lesson:" in pattern:
                        lessons.add(match.strip())
                    else:
                        facts.add(match.strip())

            # System 2: Reflection (ищем блоки <thought> или явные выводы)
            reflection_match = re.search(r"<thought>(.*?)</thought>", content, re.DOTALL)
            if reflection_match:
                reflections.append(reflection_match.group(1).strip()[:200] + "...")

        if not facts and not anchors and not reflections and not lessons:
            return ""

        memory_block = "## Memory (Dual-Process Architecture)\n"

        # System 1: Fast Facts
        if facts or anchors or lessons:
            memory_block += "### [SYSTEM 1: Fast Facts & Anchors]\n"
            if facts:
                for fact in sorted(list(facts)):
                    memory_block += f"- {fact}\n"
            if anchors:
                for anchor in sorted(list(anchors)):
                    memory_block += f"- anchor: {anchor}\n"
            if lessons:
                for lesson in sorted(list(lessons)):
                    memory_block += f"- LESSON LEARNED: {lesson}\n"

        # System 2: Slow Reflection
        if reflections:
            memory_block += "\n### [SYSTEM 2: Deep Reflection & Insights]\n"
            for ref in reflections[-3:]:  # Только последние 3 инсайта
                memory_block += f"- {ref}\n"

        return memory_block + "\n"


_memory_system = MemoryBlockSystem()


def get_memory_block(history: List[Dict[str, Any]]) -> str:
    """Возвращает отформатированный блок памяти."""
    return _memory_system.extract_memory(history)
