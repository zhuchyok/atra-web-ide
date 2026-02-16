"""
[SINGULARITY 10.0+] Multi-Agent Debate V2.
Orchestrates a debate between multiple expert models to reach an optimal solution for critical tasks.
"""

import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class DebateParticipant:
    name: str
    model: str
    role: str

@dataclass
class DebateResult:
    topic: str
    final_decision: str
    consensus_score: float
    history: List[Dict[str, str]]
    timestamp: datetime = datetime.now(timezone.utc)

class MultiAgentDebate:
    """
    Orchestrates a debate between different models/experts.
    """
    
    def __init__(self):
        # Default participants with different strengths
        self.participants = [
            DebateParticipant("Architect", "qwen2.5-coder:32b", "Focus on structure, scalability, and patterns."),
            DebateParticipant("Security", "phi3.5:3.8b", "Focus on safety, vulnerabilities, and edge cases."),
            DebateParticipant("Pragmatist", "phi3:mini-4k", "Focus on simplicity, speed, and immediate results.")
        ]

    async def run_debate(self, topic: str, context: Optional[str] = None, rounds: int = 2) -> DebateResult:
        """
        Run a multi-round debate on a specific topic.
        """
        logger.info(f"🗣️ [DEBATE] Starting debate on: {topic[:100]}...")
        
        history = []
        current_context = context or ""
        
        for r in range(1, rounds + 1):
            logger.info(f"🔄 [DEBATE] Round {r}/{rounds}")
            round_responses = []
            
            # Each participant gives their view
            tasks = []
            for p in self.participants:
                prompt = self._build_debate_prompt(p, topic, current_context, history, r)
                tasks.append(self._get_expert_opinion(p, prompt))
            
            opinions = await asyncio.gather(*tasks)
            
            for p, opinion in zip(self.participants, opinions):
                history.append({
                    "round": r,
                    "expert": p.name,
                    "opinion": opinion
                })
                round_responses.append(f"[{p.name}]: {opinion}")
            
            # Update context for next round
            current_context += "\n\n" + "\n".join(round_responses)

        # Final synthesis by Victoria (Team Lead)
        final_decision = await self._synthesize_decision(topic, history)
        
        return DebateResult(
            topic=topic,
            final_decision=final_decision,
            consensus_score=0.85, # Heuristic for now
            history=history
        )

    def _build_debate_prompt(self, participant: DebateParticipant, topic: str, context: str, history: List[Dict], round_num: int) -> str:
        history_str = ""
        if history:
            history_str = "\n".join([f"Round {h['round']} - {h['expert']}: {h['opinion']}" for h in history])

        if round_num == 1:
            return f"""
You are the {participant.name}. {participant.role}
Topic for debate: {topic}
Context: {context}

Provide your initial expert opinion on how to solve this. Be concise but thorough.
"""
        else:
            return f"""
You are the {participant.name}. {participant.role}
Topic: {topic}
Previous rounds:
{history_str}

Analyze the opinions of other experts. Point out flaws in their logic or support good ideas. 
Refine your own position to reach the best possible solution.
"""

    async def _get_expert_opinion(self, participant: DebateParticipant, prompt: str) -> str:
        try:
            # Use local router if available, else direct Ollama
            from local_router import LocalAIRouter
            router = LocalAIRouter()
            result = await router.run_local_llm(prompt, model_hint=participant.model, category="reasoning")
            if isinstance(result, tuple):
                return result[0]
            return result
        except Exception as e:
            logger.error(f"Debate expert {participant.name} failed: {e}")
            return "Failed to provide opinion."

    async def _synthesize_decision(self, topic: str, history: List[Dict]) -> str:
        history_text = "\n".join([f"{h['expert']}: {h['opinion']}" for h in history])
        synthesis_prompt = f"""
You are Victoria, Team Lead. You have listened to a debate between experts on the topic: {topic}

EXPERT OPINIONS:
{history_text}

Based on the debate, provide the FINAL AUTHORITATIVE DECISION and implementation plan. 
Select the best ideas and mitigate the risks mentioned.
"""
        try:
            from ai_core import run_smart_agent_async
            return await run_smart_agent_async(synthesis_prompt, expert_name="Виктория", category="reasoning")
        except Exception as e:
            logger.error(f"Debate synthesis failed: {e}")
            return "Failed to synthesize decision."

_instance = None
def get_multi_agent_debate():
    global _instance
    if _instance is None:
        _instance = MultiAgentDebate()
    return _instance
