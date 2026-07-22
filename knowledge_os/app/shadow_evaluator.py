import asyncio
import json
import logging
import os
from typing import Any

try:
    import asyncpg
except ImportError:
    asyncpg = None

try:
    from local_router import LocalAIRouter
except ImportError:
    from app.local_router import LocalAIRouter

logger = logging.getLogger("ShadowEvaluator")
_LOCAL_ROUTER_SINGLETON = None


def _get_local_router_singleton():
    global _LOCAL_ROUTER_SINGLETON
    if _LOCAL_ROUTER_SINGLETON is None:
        _LOCAL_ROUTER_SINGLETON = LocalAIRouter()
    return _LOCAL_ROUTER_SINGLETON


class ShadowEvaluator:
    """
    [SINGULARITY 14.0] Shadow Evaluator
    Сравнивает ответы основной модели (Production) и теневой (Shadow)
    с помощью локальной модели-судьи (Judge).
    """

    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL",
            "postgresql://admin:secret@localhost:6432/knowledge_os",  # pragma: allowlist secret
        )
        self.router = _get_local_router_singleton()
        self.judge_model = os.getenv("SHADOW_JUDGE_MODEL", "victoria-wisdom-v3.5:latest")
        self._pool = None

    async def _get_pool(self):
        if self._pool is None and asyncpg:
            try:
                self._pool = await asyncpg.create_pool(self.db_url)
            except Exception as e:
                logger.error(f"❌ [EVALUATOR] Failed to create DB pool: {e}")
        return self._pool

    @staticmethod
    def heuristic_compare(prod_resp: str, shadow_resp: str) -> dict[str, Any]:
        """Fast judge without LLM (aligned with canary_router heuristics)."""
        prod = (prod_resp or "").strip()
        shadow = (shadow_resp or "").strip()
        if not prod or prod.startswith("[SYSTEM:"):
            return {
                "verdict": "Win",
                "reasoning": "heuristic: production empty/error",
                "winner": "Shadow",
            }
        if not shadow or shadow.startswith("[SYSTEM:"):
            return {
                "verdict": "Loss",
                "reasoning": "heuristic: shadow empty/error",
                "winner": "Production",
            }
        if prod == shadow:
            return {
                "verdict": "Draw",
                "reasoning": "heuristic: identical responses",
                "winner": "None",
            }
        if len(shadow) > len(prod) * 1.2:
            return {
                "verdict": "Win",
                "reasoning": "heuristic: shadow substantially longer",
                "winner": "Shadow",
            }
        if len(prod) > len(shadow) * 1.2:
            return {
                "verdict": "Loss",
                "reasoning": "heuristic: production substantially longer",
                "winner": "Production",
            }
        return {
            "verdict": "Draw",
            "reasoning": "heuristic: similar quality/length",
            "winner": "None",
        }

    async def compare_responses(
        self, query: str, prod_resp: str, shadow_resp: str
    ) -> dict[str, Any]:
        """
        Сравнивает два ответа с помощью модели-судьи.
        Возвращает вердикт (Win/Loss/Draw) и обоснование.
        """
        logger.info(f"⚖️ [EVALUATOR] Comparing responses for query: {query[:50]}...")

        if os.getenv("SHADOW_JUDGE_MODE", "").lower() in ("heuristic", "fast"):
            return self.heuristic_compare(prod_resp, shadow_resp)

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
                return self.heuristic_compare(prod_resp, shadow_resp)

            # Парсим JSON из ответа
            try:
                # Находим JSON в тексте (на случай если модель добавила лишний текст)
                start_idx = raw_response.find("{")
                end_idx = raw_response.rfind("}") + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = raw_response[start_idx:end_idx]
                    evaluation = json.loads(json_str)
                else:
                    evaluation = self.heuristic_compare(prod_resp, shadow_resp)
                    evaluation["reasoning"] = (
                        f"Invalid JSON from judge; heuristic used. Raw: {raw_response[:80]}"
                    )
            except json.JSONDecodeError:
                evaluation = self.heuristic_compare(prod_resp, shadow_resp)
                evaluation["reasoning"] = (
                    f"JSON parse failed; heuristic used. Raw: {raw_response[:80]}"
                )

            return evaluation

        except Exception as e:
            logger.error(f"❌ [EVALUATOR] Error during comparison: {e}")
            evaluation = self.heuristic_compare(prod_resp, shadow_resp)
            evaluation["reasoning"] = f"Judge error; heuristic used: {e}"
            return evaluation

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
                        total_tests = total_tests + 1,
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    mutation_id,
                )
                logger.info(f"✅ [EVALUATOR] Updated {column} for mutation {mutation_id}")
        except Exception as e:
            logger.error(f"❌ [EVALUATOR] Failed to update DB: {e}")

    async def _log_battle(
        self,
        mutation_id: str,
        query: str,
        prod_resp: str,
        shadow_resp: str,
        evaluation: dict[str, Any],
    ) -> None:
        """Persist battle for Prompt Battle UI (interaction_logs.metadata.shadow_execution)."""
        pool = await self._get_pool()
        if not pool:
            return
        try:
            async with pool.acquire() as conn:
                expert_id = await conn.fetchval(
                    "SELECT expert_id FROM expert_mutations WHERE id = $1",
                    mutation_id,
                )
                meta = {
                    "shadow_execution": "true",
                    "shadow_verdict": evaluation.get("verdict", "Draw"),
                    "shadow_reason": evaluation.get("reasoning", ""),
                    "shadow_response": (shadow_resp or "")[:4000],
                    "production_response": (prod_resp or "")[:2000],
                    "mutation_id": str(mutation_id),
                    "source": "shadow_evaluator",
                }
                await conn.execute(
                    """
                    INSERT INTO interaction_logs (expert_id, user_query, assistant_response, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    expert_id,
                    (query or "")[:2000] or "(empty query)",
                    (shadow_resp or "")[:8000] or "(empty shadow)",
                    json.dumps(meta, ensure_ascii=False),
                )
        except Exception as e:
            logger.warning(f"⚠️ [EVALUATOR] Battle log failed: {e}")

    async def evaluate_and_update(
        self, mutation_id: str, query: str, prod_resp: str, shadow_resp: str
    ):
        """
        Полный цикл: сравнение + обновление БД + лог битвы.
        """
        evaluation = await self.compare_responses(query, prod_resp, shadow_resp)
        verdict = evaluation.get("verdict", "Draw")
        await self.update_mutation_stats(mutation_id, verdict)
        await self._log_battle(mutation_id, query, prod_resp, shadow_resp, evaluation)
        return evaluation
