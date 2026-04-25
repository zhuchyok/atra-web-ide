"""
Swarm Intelligence - Коллективный интеллект для мультиагентных систем
Основано на Nature 2025: meta-heuristic + consensus theory, оптимальный размер ~16-32 агентов
[SINGULARITY 28.2] Island Model & Adversarial Skeptics.
"""

import asyncio
import logging
import os
import uuid
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


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
    role: str = "explorer"  # explorer, skeptic, elite
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    velocity: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    local_best: Optional[Any] = None
    local_best_score: float = 0.0
    current_solution: Optional[Any] = None
    current_score: float = 0.0
    group_id: Optional[str] = None


@dataclass
class SwarmGroup:
    """Группа агентов (Island/Cluster) [SINGULARITY 28.2]"""
    group_id: str
    group_name: str
    agents: List[SwarmAgent] = field(default_factory=list)
    group_best: Optional[Any] = None
    group_best_score: float = 0.0
    synthesis: Optional[str] = None
    generation: int = 0


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
    [SINGULARITY 28.2] Swarm Intelligence with Island Model.
    Prevents groupthink by evolving specialized clusters independently.
    """

    def __init__(
        self,
        swarm_size: int = 32,
        model_name: str = "smollm2:360m",  # [SINGULARITY 28.2] Ultra-fast worker model
        ollama_url: str = OLLAMA_URL,
        max_iterations: int = 20,
    ):
        self.swarm_size = swarm_size
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.max_iterations = max_iterations
        self.agents: List[SwarmAgent] = []
        self.groups: List[SwarmGroup] = []
        self.global_best: Optional[Any] = None
        self.global_best_score: float = 0.0
        self.state = SwarmState.FORMING
        self._llm_semaphore = asyncio.Semaphore(8)

        try:
            from app.resource_monitor import get_resource_monitor
            self.resource_monitor = get_resource_monitor()
        except ImportError:
            self.resource_monitor = None

    async def solve(
        self,
        problem: str,
        agent_names: Optional[List[str]] = None,
        initial_solutions: Optional[List[Any]] = None,
        enable_evolution: bool = True,
    ) -> SwarmResult:
        """
        [SINGULARITY 28.2] Solve using Island Model Swarm.
        """
        logger.info(f"🐝 Swarm Intelligence (Level 8 100%): {self.swarm_size} agents on Islands")

        # 1. Формируем рой и группы (Islands)
        await self._form_swarm(agent_names, initial_solutions)
        self.state = SwarmState.EXPLORING

        # 2. Итерации
        for iteration in range(self.max_iterations):
            logger.info(f"🔄 Iteration {iteration + 1}/{self.max_iterations}")

            # 2.1. Локальное исследование внутри островов
            await self._explore_islands(problem, iteration)

            # 2.2. Эволюция внутри островов (каждые 2 итерации)
            if enable_evolution and iteration % 2 == 0:
                await self._evolve_islands(problem)

            # 2.3. Миграция между островами (каждые 5 итераций)
            if iteration % 5 == 0 and iteration > 0:
                await self._migrate_between_islands()

            # 2.4. Обновление глобального лучшего
            await self._update_global_best()

            # 2.5. Проверка конвергенции (Consensus)
            if self._check_consensus():
                logger.info(f"✅ Consensus reached on iteration {iteration + 1}")
                break

        return self._build_result(iteration)

    async def _form_swarm(self, agent_names: Optional[List[str]], initial_solutions: Optional[List[Any]]):
        """Создает агентов и распределяет их по островам (Tech, Logic, Security, Creative)."""
        group_configs = [
            ("tech", "Technical Island"),
            ("logic", "Logical Island"),
            ("sec", "Security Island"),
            ("creative", "Creative Island"),
        ]
        self.groups = [SwarmGroup(group_id=g_id, group_name=g_name) for g_id, g_name in group_configs]
        
        self.agents = []
        for i in range(self.swarm_size):
            # Каждая 4-я роль - Скептик (Adversarial)
            role = "skeptic" if i % 4 == 0 else "explorer"
            name = agent_names[i] if agent_names and i < len(agent_names) else f"Agent_{i+1}"
            
            agent = SwarmAgent(
                agent_id=str(uuid.uuid4()),
                agent_name=name,
                role=role,
                position={"x": float(i % 4), "y": float(i // 4)}
            )
            
            if initial_solutions and i < len(initial_solutions):
                agent.current_solution = initial_solutions[i]
                
            # Распределяем по группам
            group = self.groups[i % len(self.groups)]
            agent.group_id = group.group_id
            group.agents.append(agent)
            self.agents.append(agent)

    async def _explore_islands(self, problem: str, iteration: int):
        """Агенты исследуют задачу, скептики критикуют."""
        tasks = []
        for agent in self.agents:
            prompt = self._build_island_prompt(agent, problem, iteration)
            tasks.append(self._generate_solution(agent, prompt))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for agent, solution in zip(self.agents, results):
            if not isinstance(solution, Exception):
                agent.current_solution = solution.get("solution")
                agent.current_score = solution.get("score", 0.0)
                
                # Обновляем локальный лучший
                if agent.current_score > agent.local_best_score:
                    agent.local_best = agent.current_solution
                    agent.local_best_score = agent.current_score

    async def _evolve_islands(self, problem: str):
        """Внутри каждого острова происходит свой отбор."""
        for group in self.groups:
            sorted_agents = sorted(group.agents, key=lambda a: a.current_score, reverse=True)
            elite = sorted_agents[0]
            group.group_best = elite.local_best
            group.group_best_score = elite.local_best_score
            
            # Заменяем худшего мутацией элиты
            weakest = sorted_agents[-1]
            weakest.current_solution = f"Island Mutation from {elite.agent_name}: " + str(elite.local_best)[:100]
            weakest.current_score = elite.local_best_score * 0.9

    async def _migrate_between_islands(self):
        """Обмен лучшими агентами между островами для предотвращения стагнации."""
        logger.info("🌉 [MIGRATION] Exchanging elite agents between islands...")
        for i in range(len(self.groups)):
            source = self.groups[i]
            target = self.groups[(i + 1) % len(self.groups)]
            
            # Перемещаем одного случайного агента
            if source.agents:
                migrant = source.agents.pop(random.randrange(len(source.agents)))
                migrant.group_id = target.group_id
                target.agents.append(migrant)

    async def _update_global_best(self):
        for agent in self.agents:
            if agent.local_best_score > self.global_best_score:
                self.global_best = agent.local_best
                self.global_best_score = agent.local_best_score

    def _build_island_prompt(self, agent: SwarmAgent, problem: str, iteration: int) -> str:
        role_desc = "Ты - КРИТИК. Твоя задача - найти слабые места в текущих решениях и предложить контр-аргументы." if agent.role == "skeptic" else "Ты - ИССЛЕДОВАТЕЛЬ. Твоя задача - найти инновационное решение."
        
        prompt = f"""{role_desc}
ПРОБЛЕМА: {problem}
ОСТРОВ: {agent.group_id}
ИТЕРАЦИЯ: {iteration + 1}

ТВОЕ ТЕКУЩЕЕ ЛУЧШЕЕ: {str(agent.local_best)[:200]}
ГЛОБАЛЬНОЕ ЛУЧШЕЕ: {str(self.global_best)[:200]}

### ИНСТРУКЦИЯ:
Предложи улучшение или критику. Используй мировые практики.
"""
        return prompt

    async def _generate_solution(self, agent: SwarmAgent, prompt: str) -> Dict:
        import httpx
        try:
            async with self._llm_semaphore:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": self.model_name,
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0.8, "num_predict": 1024},
                        },
                    )
                    if response.status_code == 200:
                        text = response.json().get("response", "")
                        score = self._evaluate_solution(text, agent.role)
                        return {"solution": text, "score": score}
            return {"solution": "", "score": 0.0}
        except Exception:
            return {"solution": "", "score": 0.0}

    def _evaluate_solution(self, solution: str, role: str) -> float:
        if not solution: return 0.0
        score = 0.5
        
        # [SINGULARITY 28.5] Socratic Voting & Weighted Consensus
        # Skeptics have higher weight in detecting risks
        if role == "skeptic":
            if any(m in solution.lower() for m in ["ошибка", "риск", "проблема", "уязвимость", "баг"]):
                score += 0.4 # Skeptic found a problem
            else:
                score -= 0.2 # Skeptic was too soft
        
        # [SINGULARITY 28.5] Contract-based validation
        if "expert_name" in solution and "confidence_score" in solution:
            score += 0.1 # Solution follows the contract
            
        if len(solution) > 300: score += 0.1
        return min(score, 1.0)

    def _check_consensus(self) -> bool:
        """
        [SINGULARITY 28.5] Weighted Consensus Logic.
        Requires 80% agreement AND no critical veto from skeptics.
        """
        if not self.agents: return False
        
        # 1. Check for Skeptic Veto
        skeptics = [a for a in self.agents if a.role == "skeptic"]
        for s in skeptics:
            if s.current_score > 0.8 and "критическая" in str(s.current_solution).lower():
                logger.warning(f"🚫 [CONSENSUS] Critical Veto from Skeptic: {s.agent_name}")
                return False # Veto blocks consensus
        
        # 2. Check for General Agreement
        high_score_count = sum(1 for a in self.agents if a.local_best_score >= self.global_best_score * 0.95)
        return (high_score_count / len(self.agents)) >= 0.8

    def _build_result(self, iterations: int) -> SwarmResult:
        return SwarmResult(
            global_best=self.global_best,
            global_best_score=self.global_best_score,
            iterations=iterations + 1,
            agents=self.agents,
            convergence_rate=sum(1 for a in self.agents if a.local_best_score >= self.global_best_score * 0.9) / len(self.agents),
            exploration_coverage=len(set(str(a.local_best) for a in self.agents)) / len(self.agents)
        )

async def main():
    swarm = SwarmIntelligence(swarm_size=32)
    result = await swarm.solve("Оптимизация высоконагруженных систем на Python")
    print(f"Result: {result.global_best_score}")

if __name__ == "__main__":
    asyncio.run(main())
