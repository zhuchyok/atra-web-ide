import asyncio
import logging
from typing import List, Dict
from ai_core import run_smart_agent_async

logger = logging.getLogger(__name__)

class ParallelOrchestrator:
    """
    Boosts speed by decomposing complex tasks and running them in parallel.
    Part of Singularity v4.1 (Performance Leap).
    """
    
    async def process_complex_task(self, prompt: str, subtasks: List[Dict]):
        """
        Runs multiple specialized agents in parallel.
        subtasks: [{"expert": "Mark", "prompt": "..."}, ...]
        """
        logger.info(f"⚡ Parallel Orchestration: Running {len(subtasks)} subtasks...")
        
        tasks = []
        for task in subtasks:
            tasks.append(run_smart_agent_async(
                task["prompt"], 
                expert_name=task["expert"],
                category=task.get("category")
            ))
            
        results = await asyncio.gather(*tasks)
        return results

    async def auto_decompose_and_run(self, main_prompt: str):
        """Uses a fast model to split a task, then runs sub-tasks in parallel."""
        # 1. Use fast model (Phi4) to split the task
        decomposer_prompt = f"""
        ЗАДАЧА: Разбей этот сложный запрос на 2-3 независимых подзадачи для разных экспертов.
        
        ЗАПРОС: {main_prompt}
        
        ВЕРНИ ТОЛЬКО JSON СПИСОК:
        [
            {{"expert": "Кодер", "prompt": "задача по коду"}},
            {{"expert": "Аналитик", "prompt": "задача по логике"}}
        ]
        """
        # We call the core directly with 'fast' category
        plan_json = await run_smart_agent_async(decomposer_prompt, expert_name="Виктория", category="fast")
        
        try:
            import json
            plan = json.loads(plan_json)
            results = await self.process_complex_task(main_prompt, plan)
            
            # 2. Synthesize final answer
            synthesis_prompt = f"На основе этих результатов дай финальный ответ:\n"
            for i, res in enumerate(results):
                synthesis_prompt += f"Результат {i+1}: {res}\n"
                
            final_answer = await run_smart_agent_async(synthesis_prompt, expert_name="Виктория", category="reasoning")
            return final_answer
        except Exception as e:
            logger.error(f"Parallel decomposition error: {e}")
            # Fallback to normal execution
            return await run_smart_agent_async(main_prompt)

