import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from app.db_pool import get_pool
    from app.ingestion.quality_gate import IngestionQualityGate
    from app.semantic_cache import get_embedding
except ImportError:
    from db_pool import get_pool
    from ingestion.quality_gate import IngestionQualityGate
    from semantic_cache import get_embedding

logger = logging.getLogger("LongTermMemory")


class LongTermMemory:
    """
    [SINGULARITY 28.0] Persistent Long-term Memory.
    Saves context, decisions, and insights between sessions using Vector DB and Graph relations.
    """

    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.quality_gate = IngestionQualityGate()
        self._default_domain = os.getenv("LTM_DOMAIN_NAME", "AI Research")

    @staticmethod
    def _embedding_to_vector(embedding: Optional[List[float]]) -> Optional[str]:
        if not embedding:
            return None
        try:
            return "[" + ",".join(map(str, embedding)) + "]"
        except Exception:
            return None

    @staticmethod
    def _clip(text: Optional[str], max_chars: int) -> str:
        value = (text or "").strip()
        if max_chars <= 0:
            return value
        return value[:max_chars]

    @staticmethod
    def _is_unusable_memory(content: Optional[str]) -> Optional[str]:
        """Hard reject runtime/agent dumps — never shadow-pass into research KB."""
        text = (content or "").strip()
        if not text:
            return "empty_content"
        lower = text.lower()
        hard_markers = (
            "ошибка парсинга ответа модели",
            "извините, сейчас я не могу",
            '{"action": "create_file"',
            '"action": "create_file"',
            "все источники недоступны",
            "traceback (most recent call last)",
        )
        for marker in hard_markers:
            if marker in lower:
                return f"hard_reject:{marker[:40]}"
        return None

    async def store_memory(self, content: str, source: str, metadata: Dict[str, Any] = None):
        """Store a memory node and generate its embedding."""
        hard_reason = self._is_unusable_memory(content)
        pool = await get_pool()
        if hard_reason:
            async with pool.acquire() as conn:
                await self.quality_gate.log_reject(
                    conn,
                    content=content,
                    source_type=source or "unknown",
                    reason=hard_reason,
                    gate_stage="long_term_memory_hard",
                    metadata={"decision": "reject", "enforce": "always"},
                )
            logger.warning(f"⛔ [LTM] Hard-rejected from {source}: {hard_reason}")
            return None

        decision = await self.quality_gate.evaluate_async(content, source_type=source or "unknown")
        if self.quality_gate.should_block(decision):
            async with pool.acquire() as conn:
                await self.quality_gate.log_reject(
                    conn,
                    content=content,
                    source_type=source or "unknown",
                    reason=decision.reason,
                    gate_stage="long_term_memory",
                    metadata={
                        "quality_score": decision.quality_score,
                        "decision": decision.decision,
                    },
                )
            logger.warning(f"⛔ [LTM] Rejected candidate from {source}: {decision.reason}")
            return None

        embedding = await get_embedding(content[:2000])
        if not embedding:
            embedding = [0.0] * 768  # Fallback

        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        domain_name = self._default_domain or "AI Research"

        async with pool.acquire() as conn:
            memory_id = await conn.fetchval(
                """
                INSERT INTO knowledge_nodes (content, domain_id, confidence_score, embedding, is_verified, metadata)
                VALUES (
                    $1,
                    (SELECT id FROM domains WHERE name = $4 LIMIT 1),
                    1.0,
                    $2,
                    TRUE,
                    $3::jsonb
                )
                RETURNING id
                """,
                content,
                embedding_str,
                json.dumps({**(metadata or {}), "source": source, "type": "long_term_memory"}),
                domain_name,
            )
            logger.info(f"💾 [LTM] Stored memory from {source}: {memory_id}")
            return memory_id

    async def recall_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recall relevant memories using vector similarity."""
        embedding = await get_embedding(query)
        if not embedding:
            return []

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT content, metadata, (1 - (embedding <=> $1::vector)) as similarity
                FROM knowledge_nodes
                WHERE metadata->>'type' = 'long_term_memory'
                AND (1 - (embedding <=> $1::vector)) > 0.7
                ORDER BY similarity DESC
                LIMIT $2
                """,
                embedding,
                limit,
            )
            return [dict(r) for r in rows]

    async def link_memories(self, source_id: Any, target_id: Any, relation: str):
        """Create a graph edge between two memory nodes."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO knowledge_edges (source_id, target_id, relation_type) VALUES ($1, $2, $3)",
                source_id,
                target_id,
                relation,
            )
            logger.info(f"🔗 [LTM] Linked memories {source_id} -> {target_id} ({relation})")

    async def save_thread(
        self,
        user_key: str,
        project_context: str,
        user_message: str,
        assistant_message: str,
        embedding: Optional[List[float]] = None,
    ) -> Optional[Any]:
        """
        Backward-compatible thread persistence API used by victoria_server.
        Stores compact dialogue exchanges in knowledge_nodes with metadata filters.
        """
        user_key = (user_key or "anonymous").strip() or "anonymous"
        project_context = (project_context or "unknown").strip() or "unknown"
        user_message = self._clip(user_message, 2000)
        assistant_message = self._clip(assistant_message, 3000)
        content = (
            f"USER: {user_message}\nASSISTANT: {assistant_message}"
            if user_message or assistant_message
            else ""
        )
        if not content:
            return None

        metadata = {
            "type": "long_term_memory_thread",
            "user_key": user_key,
            "project_context": project_context,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        vector = self._embedding_to_vector(embedding)
        if vector is None:
            emb = await get_embedding(content[:2000])
            vector = self._embedding_to_vector(emb)
        if vector is None:
            vector = self._embedding_to_vector([0.0] * 768)

        pool = await get_pool()
        async with pool.acquire() as conn:
            memory_id = await conn.fetchval(
                """
                INSERT INTO knowledge_nodes (content, domain_id, confidence_score, embedding, is_verified, metadata)
                VALUES (
                    $1,
                    (SELECT id FROM domains WHERE name = $2 LIMIT 1),
                    1.0,
                    $3::vector,
                    TRUE,
                    $4::jsonb
                )
                RETURNING id
                """,
                content,
                self._default_domain,
                vector,
                json.dumps(metadata),
            )
            return memory_id

    async def get_recent_threads(
        self,
        user_key: str,
        project_context: str,
        limit: int = 5,
        max_chars: int = 600,
    ) -> str:
        """
        Backward-compatible API expected by victoria_server/openai route.
        Returns compact text block of recent exchanges.
        """
        user_key = (user_key or "anonymous").strip() or "anonymous"
        project_context = (project_context or "unknown").strip() or "unknown"
        limit = max(1, min(int(limit or 5), 50))
        max_chars = max(100, min(int(max_chars or 600), 6000))

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT content
                FROM knowledge_nodes
                WHERE metadata->>'type' = 'long_term_memory_thread'
                  AND metadata->>'user_key' = $1
                  AND metadata->>'project_context' = $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                user_key,
                project_context,
                limit,
            )
        if not rows:
            return ""
        ordered = list(reversed(rows))
        text = "\n\n".join((r.get("content") or "").strip() for r in ordered if r.get("content"))
        return self._clip(text, max_chars)

    async def get_relevant_threads(
        self,
        embedding: List[float],
        project_context: str,
        user_key: Optional[str] = None,
        limit: int = 5,
        max_chars: int = 600,
    ) -> str:
        """
        Semantic LTM retrieval API expected by victoria_server.
        Filters by project (and optionally user) and ranks by vector similarity.
        """
        vector = self._embedding_to_vector(embedding)
        if not vector:
            return ""
        project_context = (project_context or "unknown").strip() or "unknown"
        limit = max(1, min(int(limit or 5), 50))
        max_chars = max(100, min(int(max_chars or 600), 6000))

        pool = await get_pool()
        async with pool.acquire() as conn:
            if user_key:
                rows = await conn.fetch(
                    """
                    SELECT content, (1 - (embedding <=> $1::vector)) AS similarity
                    FROM knowledge_nodes
                    WHERE metadata->>'type' = 'long_term_memory_thread'
                      AND metadata->>'project_context' = $2
                      AND metadata->>'user_key' = $3
                    ORDER BY embedding <=> $1::vector
                    LIMIT $4
                    """,
                    vector,
                    project_context,
                    user_key,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT content, (1 - (embedding <=> $1::vector)) AS similarity
                    FROM knowledge_nodes
                    WHERE metadata->>'type' = 'long_term_memory_thread'
                      AND metadata->>'project_context' = $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                    """,
                    vector,
                    project_context,
                    limit,
                )
        if not rows:
            return ""
        text = "\n\n".join((r.get("content") or "").strip() for r in rows if r.get("content"))
        return self._clip(text, max_chars)


_ltm = None


def get_ltm() -> LongTermMemory:
    global _ltm
    if _ltm is None:
        _ltm = LongTermMemory()
    return _ltm


def get_long_term_memory_manager() -> LongTermMemory:
    """Alias for backwards compatibility."""
    return get_ltm()
