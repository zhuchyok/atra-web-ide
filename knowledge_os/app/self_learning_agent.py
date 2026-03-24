"""
Self-Learning Agents - Самообучающиеся агенты
Основано на Google DeepMind SIMA 2: генерация задач и самообучение
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@dataclass
class LearningTask:
    """Задача для обучения"""

    task_id: str
    description: str
    difficulty: str  # easy, medium, hard
    category: str
    generated_by: str  # agent name
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed: bool = False
    performance_score: Optional[float] = None


@dataclass
class LearningSession:
    """Сессия обучения"""

    session_id: str
    agent_name: str
    tasks: List[LearningTask] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    improvement_score: float = 0.0


class SelfLearningAgent:
    """
    Self-Learning Agent - самообучающийся агент

    Возможности:
    1. Генерация задач для обучения
    2. Self-reward система
    3. Адаптация на основе результатов
    """

    def __init__(
        self,
        agent_name: str = "Виктория",
        model_name: str = "phi3.5:3.8b",
        db_url: str = DB_URL,
        ollama_url: str = OLLAMA_URL,
    ):
        self.agent_name = agent_name
        self.model_name = model_name
        self.db_url = db_url
        self.ollama_url = ollama_url
        self.learning_history: List[LearningSession] = []

    async def generate_learning_tasks(
        self, category: str = "general", difficulty: str = "medium", count: int = 5
    ) -> List[LearningTask]:
        """
        Генерировать задачи для обучения

        Args:
            category: Категория задач
            difficulty: Сложность
            count: Количество задач

        Returns:
            Список задач для обучения
        """
        logger.info(
            f"🎓 [{self.agent_name}] Генерирую {count} задач обучения ({category}, {difficulty})"
        )

        prompt = f"""Ты - система генерации обучающих задач для агента {self.agent_name}.

Создай {count} обучающих задач со следующими параметрами:
- Категория: {category}
- Сложность: {difficulty}
- Задачи должны быть разнообразными и полезными для улучшения навыков агента

ФОРМАТ (каждая задача на новой строке):
1. [Описание задачи 1]
2. [Описание задачи 2]
...

ОБУЧАЮЩИЕ ЗАДАЧИ:"""

        response = await self._generate_response(prompt)

        # Парсим задачи
        tasks = self._parse_tasks(response, category, difficulty)

        # Сохраняем в БД
        await self._save_tasks_to_db(tasks)

        logger.info(f"✅ Сгенерировано {len(tasks)} задач")

        return tasks

    async def learn_from_tasks(self, tasks: List[LearningTask]) -> LearningSession:
        """
        Обучиться на задачах

        Args:
            tasks: Список задач для обучения

        Returns:
            Сессия обучения с результатами
        """
        session = LearningSession(
            session_id=f"session_{datetime.now(timezone.utc).isoformat()}",
            agent_name=self.agent_name,
        )

        logger.info(f"🎓 [{self.agent_name}] Начинаю обучение на {len(tasks)} задачах")

        for task in tasks:
            # Выполняем задачу
            result = await self._execute_task(task)

            # Оцениваем производительность
            performance = await self._evaluate_performance(task, result)
            task.performance_score = performance
            task.completed = True

            session.tasks.append(task)

            # Self-reward: генерируем награду на основе результата
            reward = await self._generate_reward(task, result, performance)

            logger.info(f"📊 Задача {task.task_id}: performance={performance:.2f}, reward={reward}")

        # Вычисляем общий improvement score
        session.improvement_score = self._calculate_improvement(session.tasks)
        session.end_time = datetime.now(timezone.utc)

        # Сохраняем сессию
        self.learning_history.append(session)
        await self._save_session_to_db(session)

        logger.info(f"✅ Обучение завершено, improvement score: {session.improvement_score:.2f}")

        return session

    async def adapt_from_learning(self, session: LearningSession) -> Dict:
        """
        Адаптироваться на основе результатов обучения

        Args:
            session: Сессия обучения

        Returns:
            Адаптации и улучшения
        """
        logger.info(f"🔄 [{self.agent_name}] Адаптация на основе обучения...")

        # Анализируем слабые места
        weak_areas = self._identify_weak_areas(session.tasks)

        # Генерируем рекомендации по улучшению
        improvements = await self._generate_improvements(weak_areas, session)

        # Применяем адаптации
        adaptations = await self._apply_adaptations(improvements)

        logger.info(f"✅ Адаптация завершена: {len(adaptations)} улучшений")

        return {
            "weak_areas": weak_areas,
            "improvements": improvements,
            "adaptations": adaptations,
            "improvement_score": session.improvement_score,
        }

    async def continuous_learning_loop(self, iterations: int = 10):
        """
        Непрерывный цикл обучения

        Args:
            iterations: Количество итераций
        """
        logger.info(f"🔄 [{self.agent_name}] Запуск непрерывного обучения ({iterations} итераций)")

        for i in range(iterations):
            logger.info(f"\n--- Итерация {i + 1}/{iterations} ---")

            # 1. Генерируем задачи
            tasks = await self.generate_learning_tasks(count=3)

            # 2. Обучаемся
            session = await self.learn_from_tasks(tasks)

            # 3. Адаптируемся
            adaptations = await self.adapt_from_learning(session)

            # 4. Пауза между итерациями
            await asyncio.sleep(1)

        logger.info("✅ Непрерывное обучение завершено")

    async def _execute_task(self, task: LearningTask) -> Dict:
        """Выполнить задачу обучения"""
        prompt = f"""Выполни следующую задачу:

ЗАДАЧА: {task.description}
КАТЕГОРИЯ: {task.category}
СЛОЖНОСТЬ: {task.difficulty}

Выполни задачу и верни результат."""

        result = await self._generate_response(prompt)

        return {"task_id": task.task_id, "result": result, "timestamp": datetime.now(timezone.utc)}

    async def _evaluate_performance(self, task: LearningTask, result: Dict) -> float:
        """Оценить производительность на задаче"""
        # Простая оценка на основе длины и качества ответа
        result_text = result.get("result", "")

        # Базовый score
        score = 0.5

        # Бонус за длину (более полный ответ)
        if len(result_text) > 100:
            score += 0.2

        # Бонус за структурированность
        if any(marker in result_text for marker in ["1.", "2.", "-", "•"]):
            score += 0.2

        # Бонус за конкретность
        if len(result_text.split()) > 20:
            score += 0.1

        return min(score, 1.0)

    async def _generate_reward(self, task: LearningTask, result: Dict, performance: float) -> float:
        """Генерировать награду (self-reward)"""
        # Награда пропорциональна производительности
        base_reward = performance

        # Бонус за сложные задачи
        difficulty_multiplier = {"easy": 0.5, "medium": 1.0, "hard": 1.5}.get(task.difficulty, 1.0)

        reward = base_reward * difficulty_multiplier

        return reward

    def _calculate_improvement(self, tasks: List[LearningTask]) -> float:
        """Рассчитать общий improvement score"""
        if not tasks:
            return 0.0

        scores = [t.performance_score for t in tasks if t.performance_score is not None]

        if not scores:
            return 0.0

        # Средний score
        avg_score = sum(scores) / len(scores)

        # Учитываем прогресс (улучшение со временем)
        if len(scores) > 1:
            progress = (scores[-1] - scores[0]) / len(scores)
            avg_score += progress * 0.2

        return min(avg_score, 1.0)

    def _identify_weak_areas(self, tasks: List[LearningTask]) -> List[str]:
        """Определить слабые области"""
        weak_areas = []

        # Группируем по категориям
        category_scores = {}
        for task in tasks:
            if task.performance_score is not None:
                if task.category not in category_scores:
                    category_scores[task.category] = []
                category_scores[task.category].append(task.performance_score)

        # Находим категории с низким средним score
        for category, scores in category_scores.items():
            avg_score = sum(scores) / len(scores)
            if avg_score < 0.6:
                weak_areas.append(category)

        return weak_areas

    async def _generate_improvements(
        self, weak_areas: List[str], session: LearningSession
    ) -> List[str]:
        """Генерировать рекомендации по улучшению"""
        if not weak_areas:
            return ["Продолжать обучение в текущем направлении"]

        prompt = f"""На основе результатов обучения агента {self.agent_name}, предложи улучшения:

СЛАБЫЕ ОБЛАСТИ: {", ".join(weak_areas)}
ОБЩИЙ SCORE: {session.improvement_score:.2f}

Предложи 3-5 конкретных улучшений.

УЛУЧШЕНИЯ:"""

        response = await self._generate_response(prompt)

        # Парсим улучшения
        improvements = [
            line.strip()
            for line in response.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        return improvements[:5]  # Берем первые 5

    async def _apply_adaptations(self, improvements: List[str]) -> Dict:
        """Применить адаптации"""
        # В реальной системе здесь была бы интеграция с конфигурацией агента
        return {
            "improvements_applied": len(improvements),
            "improvements": improvements,
            "timestamp": datetime.now(timezone.utc),
        }

    def _parse_tasks(self, response: str, category: str, difficulty: str) -> List[LearningTask]:
        """Парсить задачи из ответа"""
        import re
        import uuid

        tasks = []
        pattern = r"(\d+)\.\s*(.+?)(?=\d+\.|$)"
        matches = re.finditer(pattern, response, re.DOTALL)

        for match in matches:
            description = match.group(2).strip()

            task = LearningTask(
                task_id=str(uuid.uuid4()),
                description=description,
                difficulty=difficulty,
                category=category,
                generated_by=self.agent_name,
            )

            tasks.append(task)

        return tasks

    async def _save_tasks_to_db(self, tasks: List[LearningTask]):
        """Сохранить задачи в БД"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS learning_tasks (
                        task_id TEXT PRIMARY KEY,
                        description TEXT,
                        difficulty TEXT,
                        category TEXT,
                        generated_by TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)
                for task in tasks:
                    await conn.execute(
                        """
                        INSERT INTO learning_tasks
                        (task_id, description, difficulty, category, generated_by, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (task_id) DO NOTHING
                    """,
                        task.task_id,
                        task.description,
                        task.difficulty,
                        task.category,
                        task.generated_by,
                        task.created_at,
                    )
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения задач: {e}")

    async def _save_session_to_db(self, session: LearningSession):
        """Сохранить сессию в БД"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS learning_sessions (
                        session_id TEXT PRIMARY KEY,
                        agent_name TEXT,
                        start_time TIMESTAMP WITH TIME ZONE,
                        end_time TIMESTAMP WITH TIME ZONE,
                        improvement_score FLOAT DEFAULT 0
                    )
                """)
                await conn.execute(
                    """
                    INSERT INTO learning_sessions
                    (session_id, agent_name, start_time, end_time, improvement_score)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (session_id) DO UPDATE SET
                        end_time = EXCLUDED.end_time,
                        improvement_score = EXCLUDED.improvement_score
                """,
                    session.session_id,
                    session.agent_name,
                    session.start_time,
                    session.end_time,
                    session.improvement_score,
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения сессии: {e}")

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
    agent = SelfLearningAgent(agent_name="Виктория")

    # Генерируем задачи
    tasks = await agent.generate_learning_tasks(category="coding", difficulty="medium", count=3)

    # Обучаемся
    session = await agent.learn_from_tasks(tasks)

    # Адаптируемся
    adaptations = await agent.adapt_from_learning(session)

    print("Результаты обучения:")
    print(f"  Improvement score: {session.improvement_score:.2f}")
    print(f"  Weak areas: {adaptations['weak_areas']}")
    print(f"  Improvements: {adaptations['improvements'][:3]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
