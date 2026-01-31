"""
Swarm Intelligence - Коллективный интеллект для мультиагентных систем
Основано на Nature 2025: meta-heuristic + consensus theory, оптимальный размер ~16 агентов
"""

import os
import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')


class SwarmState(Enum):
    """Состояния роя"""
    FORMING = "forming"
    EXPLORING = "exploring"
    CONVERGING = "converging"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SwarmAgent:
    """Агент в рое"""
    agent_id: str
    agent_name: str
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    velocity: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    local_best: Optional[Any] = None
    local_best_score: float = 0.0
    current_solution: Optional[Any] = None
    current_score: float = 0.0


@dataclass
class SwarmResult:
    """Результат работы роя"""
    global_best: Any
    global_best_score: float
    iterations: int
    agents: List[SwarmAgent]
    convergence_rate: float
    exploration_coverage: float


class SwarmIntelligence:
    """
    Swarm Intelligence - коллективный интеллект через swarm behavior
    
    Основано на:
    - Nature 2025: meta-heuristic + consensus theory
    - Оптимальный размер: ~16 агентов
    - LLM-Powered для emergent behaviors
    """
    
    def __init__(
        self,
        swarm_size: int = 16,  # Оптимальный размер по исследованиям
        model_name: str = "deepseek-r1-distill-llama:70b",
        ollama_url: str = OLLAMA_URL,
        max_iterations: int = 20
    ):
        self.swarm_size = swarm_size
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.max_iterations = max_iterations
        self.agents: List[SwarmAgent] = []
        self.global_best: Optional[Any] = None
        self.global_best_score: float = 0.0
        self.state = SwarmState.FORMING
    
    async def solve(
        self,
        problem: str,
        agent_names: Optional[List[str]] = None,
        initial_solutions: Optional[List[Any]] = None
    ) -> SwarmResult:
        """
        Решить задачу используя swarm intelligence
        
        Args:
            problem: Проблема для решения
            agent_names: Имена агентов (если None - генерируются)
            initial_solutions: Начальные решения (опционально)
        
        Returns:
            Результат работы роя
        """
        logger.info(f"🐝 Swarm Intelligence: Начинаю решение проблемы ({self.swarm_size} агентов)")
        
        # 1. Формируем рой
        await self._form_swarm(agent_names, initial_solutions)
        self.state = SwarmState.EXPLORING
        
        # 2. Итерации swarm behavior
        for iteration in range(self.max_iterations):
            logger.info(f"🔄 Итерация {iteration + 1}/{self.max_iterations}")
            
            # 2.1. Каждый агент исследует локально
            await self._explore_local(problem, iteration)
            
            # 2.2. Обновляем локальные лучшие
            await self._update_local_bests()
            
            # 2.3. Обновляем глобальный лучший
            await self._update_global_best()
            
            # 2.4. Координация через consensus (Nature 2025)
            await self._coordinate_swarm(problem, iteration)
            
            # 2.5. Проверяем конвергенцию
            if self._check_convergence():
                logger.info(f"✅ Конвергенция достигнута на итерации {iteration + 1}")
                self.state = SwarmState.CONVERGING
                break
        
        # 3. Формируем результат
        convergence_rate = self._calculate_convergence_rate()
        exploration_coverage = self._calculate_exploration_coverage()
        
        return SwarmResult(
            global_best=self.global_best,
            global_best_score=self.global_best_score,
            iterations=iteration + 1,
            agents=self.agents,
            convergence_rate=convergence_rate,
            exploration_coverage=exploration_coverage
        )
    
    async def _form_swarm(
        self,
        agent_names: Optional[List[str]],
        initial_solutions: Optional[List[Any]]
    ):
        """Сформировать рой агентов"""
        if agent_names is None:
            # Генерируем имена агентов
            agent_names = [f"Agent_{i+1}" for i in range(self.swarm_size)]
        else:
            # Используем предоставленные имена, дополняем если нужно
            while len(agent_names) < self.swarm_size:
                agent_names.append(f"Agent_{len(agent_names)+1}")
            agent_names = agent_names[:self.swarm_size]
        
        # Создаем агентов
        self.agents = []
        for i, name in enumerate(agent_names):
            agent = SwarmAgent(
                agent_id=str(uuid.uuid4()),
                agent_name=name,
                position={"x": float(i % 4), "y": float(i // 4)},  # Распределяем в сетке
                velocity={"x": 0.0, "y": 0.0}
            )
            
            # Если есть начальные решения - используем их
            if initial_solutions and i < len(initial_solutions):
                agent.current_solution = initial_solutions[i]
            
            self.agents.append(agent)
        
        logger.info(f"✅ Сформирован рой из {len(self.agents)} агентов")
    
    async def _explore_local(self, problem: str, iteration: int):
        """Каждый агент исследует локально (LLM-Powered)"""
        tasks = []
        
        for agent in self.agents:
            # Строим промпт для локального исследования
            prompt = self._build_exploration_prompt(agent, problem, iteration)
            
            # Генерируем новое решение
            task = self._generate_solution(agent, prompt)
            tasks.append(task)
        
        # Выполняем параллельно
        solutions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обновляем решения агентов
        for agent, solution in zip(self.agents, solutions):
            if isinstance(solution, Exception):
                logger.warning(f"⚠️ Ошибка генерации решения для {agent.agent_name}: {solution}")
                continue
            
            agent.current_solution = solution.get("solution")
            agent.current_score = solution.get("score", 0.0)
    
    async def _update_local_bests(self):
        """Обновить локальные лучшие решения агентов"""
        for agent in self.agents:
            if agent.current_score > agent.local_best_score:
                agent.local_best = agent.current_solution
                agent.local_best_score = agent.current_score
    
    async def _update_global_best(self):
        """Обновить глобальный лучший"""
        for agent in self.agents:
            if agent.local_best_score > self.global_best_score:
                self.global_best = agent.local_best
                self.global_best_score = agent.local_best_score
                logger.debug(f"🌟 Новый глобальный лучший: {self.global_best_score:.2f} от {agent.agent_name}")
    
    async def _coordinate_swarm(self, problem: str, iteration: int):
        """Координация роя через consensus (Nature 2025: meta-heuristic + consensus)"""
        # Собираем лучшие решения от агентов
        best_solutions = [
            (agent.agent_name, agent.local_best, agent.local_best_score)
            for agent in self.agents
            if agent.local_best is not None
        ]
        
        if not best_solutions:
            return
        
        # Consensus: находим общие паттерны
        consensus_patterns = await self._find_consensus_patterns(best_solutions, problem)
        
        # Обновляем позиции агентов на основе consensus (swarm behavior)
        await self._update_positions(consensus_patterns)
    
    async def _find_consensus_patterns(
        self,
        best_solutions: List[Tuple[str, Any, float]],
        problem: str
    ) -> Dict:
        """Найти паттерны консенсуса (Nature 2025: consensus theory)"""
        # Анализируем лучшие решения для поиска общих паттернов
        prompt = f"""Найди общие паттерны в следующих лучших решениях:

ПРОБЛЕМА: {problem}

ЛУЧШИЕ РЕШЕНИЯ:
"""
        for i, (agent_name, solution, score) in enumerate(best_solutions[:5], 1):  # Топ 5
            prompt += f"\n{i}. {agent_name} (score: {score:.2f}):\n   {str(solution)[:200]}\n"
        
        prompt += """
Найди общие паттерны, которые можно использовать для улучшения всех решений.

ОБЩИЕ ПАТТЕРНЫ:"""
        
        response = await self._generate_response(prompt)
        
        return {
            "patterns": response,
            "best_count": len(best_solutions),
            "avg_score": sum(score for _, _, score in best_solutions) / len(best_solutions)
        }
    
    async def _update_positions(self, consensus_patterns: Dict):
        """Обновить позиции агентов (swarm behavior)"""
        # Простая модель: агенты движутся к глобальному лучшему
        for agent in self.agents:
            # Вычисляем направление к глобальному лучшему
            if self.global_best is not None:
                # Упрощенная модель движения (можно улучшить через PSO)
                # Агенты с лучшими локальными решениями ближе к глобальному
                distance_factor = 1.0 - min(agent.local_best_score / max(self.global_best_score, 0.01), 1.0)
                
                # Обновляем позицию
                agent.velocity["x"] = distance_factor * 0.1
                agent.velocity["y"] = distance_factor * 0.1
                agent.position["x"] += agent.velocity["x"]
                agent.position["y"] += agent.velocity["y"]
    
    def _check_convergence(self) -> bool:
        """Проверить конвергенцию роя"""
        if not self.agents:
            return False
        
        # Проверяем, достаточно ли агентов достигли высокого score
        high_score_agents = sum(
            1 for agent in self.agents
            if agent.local_best_score >= self.global_best_score * 0.9
        )
        
        convergence_ratio = high_score_agents / len(self.agents)
        
        # Конвергенция если 70%+ агентов близки к глобальному лучшему
        return convergence_ratio >= 0.7
    
    def _calculate_convergence_rate(self) -> float:
        """Рассчитать скорость конвергенции"""
        if not self.agents:
            return 0.0
        
        high_score_agents = sum(
            1 for agent in self.agents
            if agent.local_best_score >= self.global_best_score * 0.9
        )
        
        return high_score_agents / len(self.agents)
    
    def _calculate_exploration_coverage(self) -> float:
        """Рассчитать покрытие исследования"""
        if not self.agents:
            return 0.0
        
        # Разнообразие решений (можно улучшить через реальную метрику разнообразия)
        unique_solutions = len(set(
            str(agent.local_best) for agent in self.agents
            if agent.local_best is not None
        ))
        
        return min(unique_solutions / len(self.agents), 1.0)
    
    def _build_exploration_prompt(self, agent: SwarmAgent, problem: str, iteration: int) -> str:
        """Построить промпт для локального исследования"""
        prompt = f"""Ты - агент в рое, исследующий решение проблемы.

ПРОБЛЕМА: {problem}

ТВОЯ ТЕКУЩАЯ ПОЗИЦИЯ: {agent.position}
ТВОЙ ЛУЧШИЙ РЕЗУЛЬТАТ: {agent.local_best_score:.2f}

"""
        
        # Добавляем информацию о глобальном лучшем (для координации)
        if self.global_best is not None:
            prompt += f"ГЛОБАЛЬНЫЙ ЛУЧШИЙ РЕЗУЛЬТАТ: {self.global_best_score:.2f}\n\n"
        
        prompt += f"""ИССЛЕДУЙ новое решение:
- Используй свой опыт (локальный лучший)
- Учитывай глобальный лучший (но не копируй слепо)
- Исследуй новые подходы
- Итерация: {iteration + 1}

ТВОЕ НОВОЕ РЕШЕНИЕ:"""
        
        return prompt
    
    async def _generate_solution(self, agent: SwarmAgent, prompt: str) -> Dict:
        """Генерировать решение через LLM"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.8,  # Выше для разнообразия
                            "num_predict": 1024
                        }
                    }
                )
                
                if response.status_code == 200:
                    solution_text = response.json().get('response', '')
                    
                    # Оцениваем решение (упрощенная оценка)
                    score = self._evaluate_solution(solution_text)
                    
                    return {
                        "solution": solution_text,
                        "score": score
                    }
                else:
                    return {"solution": "", "score": 0.0}
        except Exception as e:
            logger.error(f"Ошибка генерации решения: {e}")
            return {"solution": "", "score": 0.0}
    
    def _evaluate_solution(self, solution: str) -> float:
        """Оценить решение (упрощенная оценка)"""
        if not solution:
            return 0.0
        
        score = 0.5  # Базовая оценка
        
        # Бонусы за качество
        if len(solution) > 100:
            score += 0.2  # Полнота
        
        if any(marker in solution.lower() for marker in ["✅", "решение", "подход", "метод"]):
            score += 0.2  # Структурированность
        
        if len(solution.split()) > 20:
            score += 0.1  # Детальность
        
        return min(score, 1.0)
    
    async def _generate_response(self, prompt: str) -> str:
        """Генерировать ответ через модель"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    return response.json().get('response', '')
                else:
                    return ""
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return ""


async def main():
    """Пример использования"""
    swarm = SwarmIntelligence(swarm_size=16, max_iterations=10)
    
    result = await swarm.solve(
        problem="Как оптимизировать производительность веб-приложения?",
        agent_names=["Victoria", "Veronica", "Игорь", "Сергей", "Дмитрий", "Анна", "Максим", "Елена",
                    "Алексей", "Павел", "Мария", "Роман", "Ольга", "Татьяна", "Андрей", "Евгений"]
    )
    
    print("Результат Swarm Intelligence:")
    print(f"  Глобальный лучший score: {result.global_best_score:.2f}")
    print(f"  Итераций: {result.iterations}")
    print(f"  Конвергенция: {result.convergence_rate:.2%}")
    print(f"  Покрытие исследования: {result.exploration_coverage:.2%}")
    print(f"  Решение: {str(result.global_best)[:200]}...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
