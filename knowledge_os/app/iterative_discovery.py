"""
[SINGULARITY 22.8] Iterative Discovery Engine.
Implements Recursive Context Enrichment (RAG 3.0).
Cycles: Agent Asks -> System Answers -> Context Grows -> Final Response.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class IterativeDiscovery:
    """
    Recursive Context Enrichment (RAG 3.0).
    Allows the agent to ask clarifying questions about the codebase or data
    before providing a final answer.
    """
    
    def __init__(self, ai_processor, max_iterations: int = 3):
        self.ai_processor = ai_processor
        self.max_iterations = max_iterations
        
    async def run(self, 
                  initial_prompt: str, 
                  expert_name: str, 
                  category: str, 
                  context: str = "",
                  project_context: Optional[str] = None) -> str:
        """
        Runs the iterative discovery loop.
        """
        logger.info(f"🕵️ [ITERATIVE DISCOVERY] Starting for {expert_name}...")
        
        current_context = context
        history: List[Tuple[str, str]] = []
        
        for i in range(self.max_iterations):
            logger.info(f"🔄 [ITERATIVE DISCOVERY] Iteration {i+1}/{self.max_iterations}")
            
            # 1. Ask the agent if it needs more info
            discovery_prompt = self._build_discovery_prompt(
                initial_prompt, expert_name, current_context, history
            )
            
            # Use the AI processor to get the next step (question or done)
            response = await self.ai_processor._run_cloud_agent_async(
                discovery_prompt, category="reasoning"
            )
            
            if "DONE" in response.upper()[:10] or "ФИНАЛЬНЫЙ ОТВЕТ" in response.upper():
                logger.info("✅ [ITERATIVE DISCOVERY] Agent signaled completion.")
                break
                
            # 2. Extract the question/query
            query = self._extract_query(response)
            if not query:
                logger.warning("⚠️ [ITERATIVE DISCOVERY] Could not extract query, stopping.")
                break
                
            logger.info(f"🔍 [ITERATIVE DISCOVERY] Agent query: {query[:100]}...")
            
            # 3. Get answers (RAG / Search)
            answer = await self.ai_processor._get_knowledge_context(query, project_context)
            
            # 4. Update context and history
            history.append((query, answer))
            current_context += f"\n\n--- DISCOVERY STEP {i+1} ---\nQUERY: {query}\nANSWER: {answer}\n"
            
        # Final step: Generate the actual response with all gathered context
        final_prompt = f"""
        ИСХОДНАЯ ЗАДАЧА: {initial_prompt}
        
        СОБРАННЫЙ КОНТЕКСТ (DISCOVERY):
        {current_context}
        
        На основе собранных данных дай финальный, максимально точный ответ.
        """
        
        return await self.ai_processor._run_cloud_agent_async(final_prompt, category=category)

    def _build_discovery_prompt(self, goal: str, expert: str, context: str, history: List[Tuple[str, str]]) -> str:
        history_str = "\n".join([f"Q: {q}\nA: {a[:200]}..." for q, a in history])
        return f"""
        Ты - {expert}. Твоя задача: {goal}.
        
        ТЕКУЩИЙ КОНТЕКСТ:
        {context}
        
        ИСТОРИЯ РАЗВЕДКИ:
        {history_str}
        
        ИНСТРУКЦИЯ (RAG 3.0):
        1. Если тебе НУЖНО больше информации (код файлов, данные из БД, документация), напиши 'QUERY: <твой запрос для поиска>'.
        2. Если информации ДОСТАТОЧНО для идеального ответа, напиши 'DONE'.
        
        ВАЖНО: Будь лаконичен. Если запрашиваешь данные, делай это точечно.
        """

    def _extract_query(self, response: str) -> Optional[str]:
        if "QUERY:" in response:
            return response.split("QUERY:")[1].strip()
        return None
