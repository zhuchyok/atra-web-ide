"""
[SINGULARITY 13.0] Self-Distillation Engine.
Analyzes interaction logs to extract learned rules, best practices, and anti-patterns.
Implements Recursive Self-Distillation (DeepSeek/o3 pattern).
"""

import os
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

class DistillationEngine:
    """
    Analyzes past interactions to improve future performance.
    """
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def _get_conn(self):
        import asyncpg
        return await asyncpg.connect(self.db_url)

    async def fetch_recent_interactions(self, limit: int = 100, days: int = 7) -> List[Dict[str, Any]]:
        """Fetch recent interactions with feedback or metadata."""
        conn = await self._get_conn()
        try:
            # Fetch interactions from the last N days
            since = datetime.now(timezone.utc) - timedelta(days=days)
            rows = await conn.fetch("""
                SELECT i.*, e.name as expert_name, e.role as expert_role
                FROM interaction_logs i
                LEFT JOIN experts e ON i.expert_id = e.id
                WHERE i.created_at > $1
                ORDER BY i.created_at DESC
                LIMIT $2
            """, since, limit)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    async def distill_experience(self, interactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Uses an LLM to analyze interactions and extract rules.
        """
        if not interactions:
            return []
            
        logger.info(f"🧠 [DISTILLATION] Analyzing {len(interactions)} interactions...")
        
        # Group by expert or category
        # For now, we'll do a global analysis for Victoria
        
        formatted_interactions = ""
        for i, interaction in enumerate(interactions):
            score = interaction.get('feedback_score', 'N/A')
            query = interaction.get('user_query', '')[:200]
            response = interaction.get('assistant_response', '')[:300]
            formatted_interactions += f"\n--- Interaction {i+1} (Score: {score}) ---\nQUERY: {query}\nRESPONSE: {response}\n"

        distillation_prompt = f"""
        You are the Principal AI Coordination Architect. 
        Analyze the following recent interactions between users and the AI Corporation.
        Identify:
        1. RECURRING PATTERNS: What does the user keep asking for?
        2. SUCCESSES: What responses got high scores or positive feedback?
        3. FAILURES/ANTI-PATTERNS: What patterns led to errors or user dissatisfaction?
        4. LEARNED RULES: Formulate 3-5 specific rules to improve future responses.
        
        INTERACTIONS:
        {formatted_interactions}
        
        Return JSON list of rules:
        [
            {{
                "rule_name": "Short name",
                "description": "Detailed rule description",
                "type": "best_practice|anti_pattern|preference",
                "confidence": 0.0-1.0
            }}
        ]
        """
        try:
            from ai_core import run_smart_agent_async
            response = await run_smart_agent_async(distillation_prompt, expert_name="Victoria", category="reasoning")
            
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Distillation analysis failed: {e}")
        return []

    async def save_learned_rules(self, rules: List[Dict[str, Any]]):
        """Save extracted rules to knowledge_nodes for RAG and prompt injection."""
        conn = await self._get_conn()
        try:
            for rule in rules:
                content = f"LEARNED RULE: {rule['rule_name']}\nDescription: {rule['description']}\nType: {rule['type']}"
                metadata = json.dumps({
                    "type": "learned_rule",
                    "rule_type": rule['type'],
                    "confidence": rule['confidence'],
                    "source": "self_distillation",
                    "distilled_at": datetime.now(timezone.utc).isoformat()
                })
                
                # Check for existing rule by name to update
                existing_id = await conn.fetchval("""
                    SELECT id FROM knowledge_nodes 
                    WHERE metadata->>'type' = 'learned_rule' 
                    AND metadata->>'rule_name' = $1
                """, rule['rule_name'])
                
                if existing_id:
                    await conn.execute("""
                        UPDATE knowledge_nodes 
                        SET content = $1, metadata = metadata || $2::jsonb, confidence_score = $3
                        WHERE id = $4
                    """, content, metadata, rule['confidence'], existing_id)
                else:
                    # Add rule_name to metadata for future checks
                    meta_dict = json.loads(metadata)
                    meta_dict['rule_name'] = rule['rule_name']
                    
                    await conn.execute("""
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score, metadata)
                        VALUES ($1, 'architecture', $2, $3)
                    """, content, rule['confidence'], json.dumps(meta_dict))
                    
            logger.info(f"✅ [DISTILLATION] Saved {len(rules)} learned rules to Knowledge Base.")
        finally:
            await conn.close()

    async def get_active_rules(self, limit: int = 5) -> str:
        """Fetch active learned rules for prompt injection."""
        try:
            import asyncpg
            conn = await asyncpg.connect(self.db_url)
            try:
                rows = await conn.fetch("""
                    SELECT content FROM knowledge_nodes 
                    WHERE metadata->>'type' = 'learned_rule' 
                    AND confidence_score >= 0.7
                    ORDER BY created_at DESC
                    LIMIT $1
                """, limit)
                if not rows:
                    return ""
                
                rules_text = "\nВЫУЧЕННЫЕ ПРАВИЛА (Self-Distillation):\n"
                for r in rows:
                    rules_text += f"- {r['content']}\n"
                return rules_text
            finally:
                await conn.close()
        except Exception:
            return ""

    async def run_cycle(self):
        """Full distillation cycle."""
        interactions = await self.fetch_recent_interactions()
        if interactions:
            rules = await self.distill_experience(interactions)
            if rules:
                await self.save_learned_rules(rules)
                return True
        return False

_instance = None
def get_distillation_engine():
    global _instance
    if _instance is None:
        _instance = DistillationEngine()
    return _instance

if __name__ == "__main__":
    # Manual run
    logging.basicConfig(level=logging.INFO)
    engine = get_distillation_engine()
    asyncio.run(engine.run_cycle())
