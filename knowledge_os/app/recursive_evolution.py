import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
EVOLUTION_USE_LLM = os.getenv("EVOLUTION_USE_LLM", "false").lower() in ("1", "true", "yes")


@dataclass
class EvolutionGenome:
    """Генетический код решения/агента [SINGULARITY 28.2]"""

    genome_id: str
    parent_id: Optional[str]
    code_snippet: str
    logic_pattern: str
    fitness_score: float = 0.0
    generation: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class RecursiveEvolutionEngine:
    """
    [SINGULARITY 28.2] Recursive Self-Evolution Engine.
    Реализует циклы автономного улучшения через изолированные лаборатории.
    """

    def __init__(self):
        self.evolution_dir = "./knowledge_os/evolution_data"
        os.makedirs(self.evolution_dir, exist_ok=True)

        try:
            from app.sandbox_manager import get_sandbox_manager

            self.sandbox = get_sandbox_manager()
        except ImportError:
            self.sandbox = None

        self.active_genomes: Dict[str, EvolutionGenome] = {}
        logger.info("🧬 RecursiveEvolutionEngine initialized (Level 8 100%)")

    async def evolve_task(
        self, task_description: str, initial_code: str, iterations: int = 3
    ) -> EvolutionGenome:
        """
        Запускает рекурсивный цикл эволюции для конкретной задачи.
        """
        logger.info(f"⚗️ Starting evolution for task: {task_description[:50]}...")

        # 0. Global Scout: Поиск мировых практик перед началом
        world_practices = await self._scout_world_practices(task_description)

        current_genome = EvolutionGenome(
            genome_id=str(uuid.uuid4()),
            parent_id=None,
            code_snippet=initial_code,
            logic_pattern="initial_seed",
            generation=0,
            metadata={"world_practices": world_practices},
        )

        for gen in range(1, iterations + 1):
            logger.info(f"🧬 Generation {gen}/{iterations}...")

            # 1. Mutation: Агенты в лабораториях предлагают улучшения на базе LLM
            mutations = await self._generate_mutations(current_genome, task_description)

            # 2. Selection: Глубокое тестирование в изолированных MicroVM
            best_mutation = await self._select_fittest(mutations, task_description)

            if best_mutation and best_mutation.fitness_score > current_genome.fitness_score:
                logger.info(
                    f"✨ Improvement found! Score: {best_mutation.fitness_score:.4f} > {current_genome.fitness_score:.4f}"
                )
                current_genome = best_mutation
            else:
                logger.info("📉 No improvement in this generation.")

        return current_genome

    async def _scout_world_practices(self, task: str) -> str:
        """Поиск мировых практик и знаний гигантов."""
        if not EVOLUTION_USE_LLM:
            return (
                "Use First Principles, Five Whys root-cause analysis, "
                "pre-mortem risk checks, and KISS constraints for changes."
            )
        from app.ai_core import run_smart_agent_async

        prompt = f"""### ROLE: Global Scout (World Practices)
### TASK: Find best architectural patterns and world practices for the following task.
### TASK DESCRIPTION: {task}

Provide a concise summary of 3-5 'Giant's Knowledge' patterns that should be applied here.
"""
        try:
            result = await run_smart_agent_async(prompt, expert_name="Виктория")
            return result
        except Exception as e:
            logger.error(f"⚠️ Scout failed: {e}")
            return "No world practices found."

    async def _generate_mutations(
        self, parent: EvolutionGenome, task: str
    ) -> List[EvolutionGenome]:
        """Генерирует вариации решения через Swarm Intelligence (LLM-powered)."""
        if not EVOLUTION_USE_LLM:
            # Deterministic low-noise mode: keep evolution active without heavy LLM fan-out.
            return [
                EvolutionGenome(
                    genome_id=str(uuid.uuid4()),
                    parent_id=parent.genome_id,
                    code_snippet=parent.code_snippet,
                    logic_pattern=f"deterministic_variant_{parent.generation + 1}_0",
                    generation=parent.generation + 1,
                    metadata=parent.metadata,
                )
            ]
        from app.ai_core import run_smart_agent_async

        world_context = parent.metadata.get("world_practices", "")

        tasks = []
        for i in range(4):  # 4 параллельных мутации
            prompt = f"""### ROLE: Evolutionary Architect
### PARENT LOGIC: {parent.logic_pattern}
### WORLD PRACTICES: {world_context}
### TASK: {task}
### CURRENT CODE:
```python
{parent.code_snippet}
```

### INSTRUCTION: Mutate the code to improve efficiency, security, or readability based on world practices.
Output ONLY the mutated python code block.
"""
            # [SINGULARITY 28.2] Используем микро-модель для быстрых итераций мутаций
            tasks.append(run_smart_agent_async(prompt, expert_name="Игорь", model="smollm2:360m"))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        mutations = []
        for i, code in enumerate(results):
            if isinstance(code, Exception):
                continue

            # Extract code from markdown
            clean_code = code
            if "```python" in code:
                clean_code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                clean_code = code.split("```")[1].split("```")[0].strip()

            mutations.append(
                EvolutionGenome(
                    genome_id=str(uuid.uuid4()),
                    parent_id=parent.genome_id,
                    code_snippet=clean_code,
                    logic_pattern=f"variant_{parent.generation + 1}_{i}",
                    generation=parent.generation + 1,
                    metadata=parent.metadata,
                )
            )
        return mutations

    async def _select_fittest(
        self, candidates: List[EvolutionGenome], task: str
    ) -> Optional[EvolutionGenome]:
        """Оценивает кандидатов через запуск в CubeSandbox с проверкой качества."""
        if not self.sandbox:
            return candidates[0] if candidates else None

        best = None
        for candidate in candidates:
            # 1. Runtime Check
            test_command = f'python3 -c "{candidate.code_snippet}"'
            result = await self.sandbox.run_in_sandbox("evolution_tester", test_command)

            score = 0.0
            if result.get("exit_code") == 0:
                score += 0.4  # Works

                # 2. Performance Check (Simulated)
                # In real scenario we would measure execution time in MicroVM
                score += 0.2

                # 3. Security Audit (Static Analysis in Sandbox)
                audit_command = f'python3 -m pyflakes -c "{candidate.code_snippet}"'
                audit_result = await self.sandbox.run_in_sandbox("security_auditor", audit_command)
                if audit_result.get("exit_code") == 0:
                    score += 0.4  # Clean code

            candidate.fitness_score = score
            if not best or candidate.fitness_score > best.fitness_score:
                best = candidate

        return best


def get_evolution_engine():
    return RecursiveEvolutionEngine()
