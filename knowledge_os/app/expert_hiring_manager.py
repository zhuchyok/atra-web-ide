"""
[SINGULARITY 14.0] Dynamic Expert Hiring & Training.
Decides whether to train an existing expert or hire a new one for a new technology.
"""

import os
import logging
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ExpertHiringManager:
    """
    Dynamic Talent Management: Scaling the corporation's expertise.
    """
    
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

    async def _get_conn(self):
        import asyncpg
        return await asyncpg.connect(self.db_url)

    async def analyze_expertise_gap(self, topic: str, goal: str) -> Dict[str, Any]:
        """
        Analyzes if current experts can handle the topic or if a new one is needed.
        """
        analysis_prompt = f"""
        Analyze the following topic and goal for an AI Corporation.
        TOPIC: {topic}
        GOAL: {goal}
        
        Current team has 86 experts covering Leadership, ML, Backend, DevOps, QA, Strategy, Trading, etc.
        
        Decide:
        1. Can we TRAIN an existing expert (e.g., add knowledge to Igor for a new Backend lib)?
        2. Do we need to HIRE a new specialized expert (e.g., for a completely new domain like Quantum Computing)?
        
        Return JSON:
        {{
            "decision": "train|hire",
            "expert_name": "Name of expert to train (if train)",
            "new_expert_domain": "Domain name (if hire)",
            "reasoning": "Why this decision?"
        }}
        """
        try:
            from ai_core import run_smart_agent_async
            response = await run_smart_agent_async(analysis_prompt, expert_name="Victoria", category="reasoning")
            
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Failed to analyze expertise gap: {e}")
        return {"decision": "train", "expert_name": "Виктория"} # Fallback

    async def execute_hiring_or_training(self, gap_analysis: Dict[str, Any]):
        """
        Executes the decision to hire or train.
        """
        decision = gap_analysis.get("decision")
        
        if decision == "hire":
            domain = gap_analysis.get("new_expert_domain")
            logger.info(f"🕵️ [HIRING] Victoria decided to hire a new expert for: {domain}")
            from expert_generator import recruit_expert
            await recruit_expert(domain)
            
        elif decision == "train":
            expert = gap_analysis.get("expert_name")
            logger.info(f"🎓 [TRAINING] Victoria decided to train expert: {expert}")
            # Logic to add a specialized knowledge node for this expert
            # This is handled by the regular RAG/Knowledge system, 
            # but we could trigger a specific 'learning session' here.

    async def handle_new_technology(self, topic: str, goal: str):
        """
        Full cycle of dynamic hiring/training.
        """
        gap = await self.analyze_expertise_gap(topic, goal)
        await self.execute_hiring_or_training(gap)

_instance = None
def get_expert_hiring_manager():
    global _instance
    if _instance is None:
        _instance = ExpertHiringManager()
    return _instance
