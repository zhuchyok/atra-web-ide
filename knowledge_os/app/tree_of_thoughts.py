"""
Tree of Thoughts (ToT) - Структурированное планирование
Основано на Tree of Thoughts framework: +40-50% на сложных planning задачах
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class ThoughtStatus(Enum):
    """Статус мысли"""

    PENDING = "pending"
    EXPLORING = "exploring"
    VALID = "valid"
    INVALID = "invalid"
    COMPLETED = "completed"


@dataclass
class Thought:
    """Мысль в дереве"""

    thought_id: str
    content: str
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    status: ThoughtStatus = ThoughtStatus.PENDING
    score: float = 0.0
    depth: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class ToTResult:
    """Результат Tree of Thoughts"""

    best_path: List[Thought]
    final_answer: str
    total_thoughts: int
    exploration_depth: int
    confidence: float


class TreeOfThoughts:
    """
    Tree of Thoughts Framework

    Компоненты:
    1. Prompter Agent - контекстно-адаптивные промпты
    2. Checker Module - валидация кандидатов
    3. Memory Module - запись частичных решений
    4. ToT Controller - координация исследования
    """

    def __init__(
        self,
        model_name: str = "phi3.5:3.8b",
        ollama_url: str = OLLAMA_URL,
        max_depth: int = 5,
        max_branching: int = 3,
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.max_depth = max_depth
        self.max_branching = max_branching
        self.thoughts: Dict[str, Thought] = {}
        self.root_thought_id: Optional[str] = None

    async def solve(self, problem: str, initial_context: Optional[Dict] = None) -> ToTResult:
        """
        Решить задачу используя Tree of Thoughts

        Args:
            problem: Проблема для решения
            initial_context: Начальный контекст

        Returns:
            Результат с лучшим путем
        """
        logger.info(f"🌳 ToT: Начинаю решение проблемы: {problem[:80]}")

        # 1. Создаем корневую мысль
        root_thought = self._create_thought(
            content=f"Начало решения: {problem}", parent_id=None, depth=0
        )
        self.root_thought_id = root_thought.thought_id

        # 2. Исследуем дерево
        best_path = await self._explore_tree(root_thought, problem, initial_context)

        # 3. Извлекаем финальный ответ
        final_answer = await self._extract_final_answer(best_path, problem)

        # 4. Вычисляем уверенность
        confidence = self._calculate_confidence(best_path)

        return ToTResult(
            best_path=best_path,
            final_answer=final_answer,
            total_thoughts=len(self.thoughts),
            exploration_depth=max(t.depth for t in self.thoughts.values()) if self.thoughts else 0,
            confidence=confidence,
        )

    async def _explore_tree(
        self,
        current_thought: Thought,
        problem: str,
        context: Optional[Dict],
        visited: Optional[set] = None,
    ) -> List[Thought]:
        """Исследовать дерево мыслей"""
        if visited is None:
            visited = set()

        if current_thought.thought_id in visited:
            return []

        visited.add(current_thought.thought_id)

        # Проверяем, достигли ли мы максимальной глубины
        if current_thought.depth >= self.max_depth:
            current_thought.status = ThoughtStatus.COMPLETED
            return [current_thought]

        # Генерируем следующие мысли (ветвление)
        next_thoughts = await self._generate_next_thoughts(current_thought, problem, context)

        if not next_thoughts:
            # Нет дальнейших мыслей - это лист
            current_thought.status = ThoughtStatus.COMPLETED
            return [current_thought]

        # Оцениваем каждую следующую мысль
        scored_thoughts = []
        for thought in next_thoughts:
            score = await self._evaluate_thought(thought, problem)
            thought.score = score
            thought.status = ThoughtStatus.VALID if score > 0.5 else ThoughtStatus.INVALID
            scored_thoughts.append((score, thought))

        # Сортируем по score (лучшие первыми)
        scored_thoughts.sort(reverse=True, key=lambda x: x[0])

        # Исследуем лучшие ветви (ограничиваем branching)
        best_paths = []
        for score, thought in scored_thoughts[: self.max_branching]:
            if thought.status == ThoughtStatus.VALID:
                # Рекурсивно исследуем эту ветвь
                path = await self._explore_tree(thought, problem, context, visited)
                if path:
                    best_paths.append((score, [current_thought] + path))

        if not best_paths:
            # Нет валидных путей - возвращаемся
            return [current_thought]

        # Выбираем лучший путь
        best_score, best_path = max(best_paths, key=lambda x: x[0])
        return best_path

    async def _generate_next_thoughts(
        self, current_thought: Thought, problem: str, context: Optional[Dict]
    ) -> List[Thought]:
        """Сгенерировать следующие мысли (Prompter Agent)"""
        # Строим контекстно-адаптивный промпт
        prompt = self._build_prompter_prompt(current_thought, problem, context)

        # Генерируем варианты
        response = await self._generate_response(prompt)

        # Парсим мысли
        thoughts = self._parse_thoughts(
            response, current_thought.thought_id, current_thought.depth + 1
        )

        # Сохраняем связи
        current_thought.children = [t.thought_id for t in thoughts]

        return thoughts

    async def _evaluate_thought(self, thought: Thought, problem: str) -> float:
        """Оценить мысль (Checker Module)"""
        # Строим промпт для проверки
        prompt = f"""Оцени валидность следующей мысли для решения проблемы:

ПРОБЛЕМА: {problem}
МЫСЛЬ: {thought.content}

Оцени от 0.0 до 1.0:
- 0.0-0.3: Неверная мысль
- 0.4-0.6: Частично верная
- 0.7-1.0: Верная мысль

ОЦЕНКА (только число):"""

        response = await self._generate_response(prompt)

        # Парсим оценку
        try:
            score = float(response.strip().split()[0])
            return max(0.0, min(1.0, score))
        except:
            # Fallback: простая эвристика
            return 0.5 if len(thought.content) > 20 else 0.3

    async def _extract_final_answer(self, path: List[Thought], problem: str) -> str:
        """Извлечь финальный ответ из пути"""
        # Берем последнюю мысль в пути
        if not path:
            return "Не удалось найти решение"

        final_thought = path[-1]

        # Если это не финальная мысль, генерируем ответ на основе пути
        if final_thought.status != ThoughtStatus.COMPLETED:
            prompt = f"""На основе следующего пути рассуждений, сформируй финальный ответ:

ПРОБЛЕМА: {problem}

ПУТЬ РАССУЖДЕНИЙ:
"""
            for i, thought in enumerate(path, 1):
                prompt += f"\n{i}. {thought.content}\n"

            prompt += "\nФИНАЛЬНЫЙ ОТВЕТ:"

            return await self._generate_response(prompt)

        return final_thought.content

    def _calculate_confidence(self, path: List[Thought]) -> float:
        """Рассчитать уверенность на основе пути"""
        if not path:
            return 0.0

        # Средний score пути
        scores = [t.score for t in path if t.score > 0]
        if scores:
            avg_score = sum(scores) / len(scores)
        else:
            avg_score = 0.5

        # Бонус за глубину (более глубокое исследование)
        depth_bonus = min(len(path) / self.max_depth, 0.2)

        confidence = avg_score + depth_bonus
        return min(confidence, 1.0)

    def _build_prompter_prompt(
        self, current_thought: Thought, problem: str, context: Optional[Dict]
    ) -> str:
        """Построить контекстно-адаптивный промпт (Prompter Agent)"""
        prompt = f"""Продолжи рассуждение для решения проблемы:

ПРОБЛЕМА: {problem}

ТЕКУЩАЯ МЫСЛЬ: {current_thought.content}

"""

        # Добавляем контекст пути (Memory Module)
        if current_thought.parent_id:
            parent = self.thoughts.get(current_thought.parent_id)
            if parent:
                prompt += f"ПРЕДЫДУЩАЯ МЫСЛЬ: {parent.content}\n\n"

        if context:
            prompt += f"КОНТЕКСТ: {context}\n\n"

        prompt += f"""Сгенерируй {self.max_branching} следующих мыслей для продолжения рассуждения.

ФОРМАТ (каждая мысль на новой строке):
1. [Мысль 1]
2. [Мысль 2]
...

СЛЕДУЮЩИЕ МЫСЛИ:"""

        return prompt

    def _parse_thoughts(self, response: str, parent_id: str, depth: int) -> List[Thought]:
        """Парсить мысли из ответа"""
        import re

        thoughts = []
        pattern = r"(\d+)\.\s*(.+?)(?=\d+\.|$)"
        matches = re.finditer(pattern, response, re.DOTALL)

        for match in matches:
            content = match.group(2).strip()

            thought = self._create_thought(content=content, parent_id=parent_id, depth=depth)

            thoughts.append(thought)

        return thoughts

    def _create_thought(self, content: str, parent_id: Optional[str], depth: int) -> Thought:
        """Создать мысль"""
        import uuid

        thought = Thought(
            thought_id=str(uuid.uuid4()),
            content=content,
            parent_id=parent_id,
            depth=depth,
            status=ThoughtStatus.PENDING,
        )

        self.thoughts[thought.thought_id] = thought

        if parent_id and parent_id in self.thoughts:
            self.thoughts[parent_id].children.append(thought.thought_id)

        return thought

    async def _generate_response(self, prompt: str, max_tokens: int = 2048) -> str:
        """Генерировать ответ через модель"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.7, "num_predict": max_tokens},
                    },
                )

                if response.status_code == 200:
                    return response.json().get("response", "")
                else:
                    logger.error(f"Ошибка генерации: {response.status_code}")
                    return ""
        except Exception as e:
            logger.error(f"Ошибка запроса к модели: {e}")
            return ""


async def main():
    """Пример использования"""
    tot = TreeOfThoughts(model_name="phi3.5:3.8b", max_depth=3, max_branching=2)

    result = await tot.solve("Как оптимизировать производительность веб-приложения?")

    print("Результат Tree of Thoughts:")
    print(f"  Финальный ответ: {result.final_answer[:200]}...")
    print(f"  Уверенность: {result.confidence:.2f}")
    print(f"  Всего мыслей: {result.total_thoughts}")
    print(f"  Глубина исследования: {result.exploration_depth}")
    print(f"  Длина лучшего пути: {len(result.best_path)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
