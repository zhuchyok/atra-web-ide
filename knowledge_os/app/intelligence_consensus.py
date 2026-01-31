import asyncio
import logging
from ai_core import run_smart_agent_async, _run_cloud_agent_async
from local_router import LocalAIRouter

logger = logging.getLogger(__name__)

class IntelligenceConsensus:
    """
    High-stakes decision engine. Runs both Local (L1) and Cloud (L2) 
    models and compares results to ensure maximum quality.
    """
    
    async def get_consensus(self, prompt: str, expert_name: str = "Виктория"):
        """Run both models and find agreement."""
        router = LocalAIRouter()
        
        # For consensus, always use the most powerful local model (Reasoning)
        local_task = router.run_local_llm(prompt, category="reasoning")
        cloud_task = _run_cloud_agent_async(prompt)
        
        local_resp, cloud_resp = await asyncio.gather(local_task, cloud_task)
        
        if not local_resp:
            return cloud_resp, "Cloud only (Local failed)"
            
        # Cross-check prompt
        cross_check_prompt = f"""
        ВЫ - ВЫСШИЙ СУДЬЯ ИИ (УРОВЕНЬ 5).
        ЗАДАЧА: Сравните два ответа эксперта {expert_name} на один и тот же запрос и сформируйте финальный, идеальный ответ.
        
        ЗАПРОС: {prompt}
        ОТВЕТ А (Локальный): {local_resp}
        ОТВЕТ Б (Облачный): {cloud_resp}
        
        ИНСТРУКЦИЯ:
        1. Если они согласны, объедините их в лучший текст.
        2. Если они противоречат, выберите более логичный и безопасный (обычно облачный).
        3. Сохраните стиль ATRA.
        """
        
        final_resp = await _run_cloud_agent_async(cross_check_prompt)
        return final_resp, "Consensus (Local + Cloud)"

if __name__ == "__main__":
    consensus = IntelligenceConsensus()
    # asyncio.run(consensus.get_consensus("Проверь стратегию risk-management"))

