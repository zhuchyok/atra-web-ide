import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

try:
    import asyncpg
except ImportError:
    asyncpg = None

try:
    from local_router import LocalAIRouter
except ImportError:
    from app.local_router import LocalAIRouter

logger = logging.getLogger("ShadowEvaluator")


class ShadowEvaluator:
    """
    [SINGULARITY 14.0] Shadow Evaluator
    Сравнивает ответы основной модели (Production) и теневой (Shadow)
    с помощью локальной модели-судьи (Judge).
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os"
        )
        self.router = LocalAIRouter()
        self.judge_model = os.getenv("SHADOW_JUDGE_MODEL", "victoria-wisdom-v3.5:latest")
        self._pool = None

    async def _get_pool(self):
        if self._pool is None and asyncpg:
            try:
                self._pool = await asyncpg.create_pool(self.db_url)
            except Exception as e:
                logger.error(f"❌ [EVALUATOR] Failed to create DB pool: {e}")
        return self._pool

    async def compare_responses(
        self, query: str, prod_resp: str, shadow_resp: str
    ) -> Dict[str, Any]:
        """
        Сравнивает два ответа с помощью модели-судьи.
        Возвращает вердикт (Win/Loss/Draw) и обоснование.
        """
        logger.info(f"⚖️ [EVALUATOR] Comparing responses for query: {query[:50]}...")

        judge_prompt = f"""### ROLE: AI Judge / Quality Auditor
### TASK: Compare two AI responses to the same user query and decide which one is better.

USER QUERY:
{query}

RESPONSE A (Production):
{prod_resp}

RESPONSE B (Shadow Mutation):
{shadow_resp}

### EVALUATION CRITERIA:
1. Accuracy: Which response is more factually correct?
2. Completeness: Which response addresses all parts of the query?
3. Reasoning: Which response shows better logical steps?
4. Conciseness: Which response is more efficient without losing quality?

### OUTPUT FORMAT (JSON ONLY):
{{
  "verdict": "Win" | "Loss" | "Draw",
  "reasoning": "Brief explanation of why",
  "winner": "Shadow" | "Production" | "None"
}}

NOTE:
- "Win" means Shadow (B) is better than Production (A).
- "Loss" means Production (A) is better than Shadow (B).
- "Draw" means they are equal in quality.

VERDICT:"""

        try:
            # Вызываем локальную модель-судью
            result = await self.router.run_local_llm(
                judge_prompt, category="reasoning", model_hint=self.judge_model, timeout=1800.0
            )

            raw_response = result[0] if isinstance(result, tuple) else result

            if not raw_response:
                return {"verdict": "Draw", "reasoning": "Judge failed to respond", "winner": "None"}

            # Парсим JSON из ответа
            try:
                # Находим JSON в тексте (на случай если модель добавила лишний текст)
                start_idx = raw_response.find("{")
                end_idx = raw_response.rfind("}") + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = raw_response[start_idx:end_idx]
                    evaluation = json.loads(json_str)
                else:
                    evaluation = {
                        "verdict": "Draw",
                        "reasoning": f"Invalid JSON format: {raw_response[:100]}",
                        "winner": "None",
                    }
            except json.JSONDecodeError:
                evaluation = {
                    "verdict": "Draw",
                    "reasoning": f"Failed to parse JSON: {raw_response[:100]}",
                    "winner": "None",
                }

            return evaluation

        except Exception as e:
            logger.error(f"❌ [EVALUATOR] Error during comparison: {e}")
            return {"verdict": "Draw", "reasoning": f"Error: {str(e)}", "winner": "None"}

    async def update_mutation_stats(self, mutation_id: str, verdict: str):
        """
        Обновляет статистику мутации в таблице expert_mutations.
        """
        pool = await self._get_pool()
        if not pool:
            logger.error("❌ [EVALUATOR] No DB pool available for update")
            return

        column = {"Win": "win_count", "Loss": "loss_count", "Draw": "draw_count"}.get(verdict)

        if not column:
            logger.warning(f"⚠️ [EVALUATOR] Unknown verdict: {verdict}")
            return

        try:
            async with pool.acquire() as conn:
                # Инкрементируем счетчик и обновляем total_evaluations
                await conn.execute(
                    f"""
                    UPDATE expert_mutations
                    SET {column} = {column} + 1,
                        total_evaluations = total_evaluations + 1,
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    mutation_id,
                )
                logger.info(f"✅ [EVALUATOR] Updated {column} for mutation {mutation_id}")
        except Exception as e:
            logger.error(f"❌ [EVALUATOR] Failed to update DB: {e}")

    async def evaluate_and_update(
        self, mutation_id: str, query: str, prod_resp: str, shadow_resp: str
    ):
        """
        Полный цикл: сравнение + обновление БД.
        """
        evaluation = await self.compare_responses(query, prod_resp, shadow_resp)
        verdict = evaluation.get("verdict", "Draw")
        await self.update_mutation_stats(mutation_id, verdict)
        return evaluation
