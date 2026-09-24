"""
Expert Dialogue Repository Implementation

Infrastructure layer implementation for PostgreSQL.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.domain.entities.expert_dialogue import ExpertDialogue, ExpertOpinion
from src.domain.repositories.expert_dialogue_repository import ExpertDialogueRepository
from src.infrastructure.persistence.models.expert_dialogue_model import (
    ExpertDialogueModel,
    ExpertOpinionModel,
)


class ExpertDialogueRepositoryImpl(ExpertDialogueRepository):
    """
    PostgreSQL implementation of ExpertDialogueRepository

    Uses asyncpg for async database operations.
    """

    def __init__(self, db_pool):
        self._pool = db_pool

    async def save_session(self, dialogue: ExpertDialogue) -> ExpertDialogue:
        model = ExpertDialogueModel.from_entity(dialogue)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO expert_dialogues
                (session_id, topic, mode, status, participants, final_decision,
                 consensus_score, created_at, completed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (session_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    final_decision = EXCLUDED.final_decision,
                    consensus_score = EXCLUDED.consensus_score,
                    completed_at = EXCLUDED.completed_at
                """,
                model.session_id,
                model.topic,
                model.mode,
                model.status,
                model.participants,
                model.final_decision,
                model.consensus_score,
                model.created_at,
                model.completed_at,
            )

        return dialogue

    async def save_opinion(self, opinion: ExpertOpinion) -> ExpertOpinion:
        model = ExpertOpinionModel.from_entity(opinion)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO expert_opinions
                (id, session_id, expert_id, opinion_text, confidence, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    opinion_text = EXCLUDED.opinion_text,
                    confidence = EXCLUDED.confidence
                """,
                model.id,
                model.session_id,
                model.expert_id,
                model.opinion_text,
                model.confidence,
                model.created_at,
            )

        return opinion

    async def get_session(self, session_id: UUID) -> Optional[ExpertDialogue]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT session_id, topic, mode, status, participants,
                       final_decision, consensus_score, created_at, completed_at
                FROM expert_dialogues
                WHERE session_id = $1
                """,
                session_id,
            )

            if not row:
                return None

            model = ExpertDialogueModel(
                session_id=row["session_id"],
                topic=row["topic"],
                mode=row["mode"],
                status=row["status"],
                participants=list(row["participants"]),
                final_decision=row["final_decision"],
                consensus_score=row["consensus_score"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )

            opinions = await self._get_opinions_for_session(conn, session_id)
            return model.to_entity(opinions)

    async def list_recent_sessions(
        self,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> List[ExpertDialogue]:
        async with self._pool.acquire() as conn:
            if since:
                rows = await conn.fetch(
                    """
                    SELECT session_id, topic, mode, status, participants,
                           final_decision, consensus_score, created_at, completed_at
                    FROM expert_dialogues
                    WHERE created_at >= $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    since,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT session_id, topic, mode, status, participants,
                           final_decision, consensus_score, created_at, completed_at
                    FROM expert_dialogues
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )

            sessions = []
            for row in rows:
                model = ExpertDialogueModel(
                    session_id=row["session_id"],
                    topic=row["topic"],
                    mode=row["mode"],
                    status=row["status"],
                    participants=list(row["participants"]),
                    final_decision=row["final_decision"],
                    consensus_score=row["consensus_score"],
                    created_at=row["created_at"],
                    completed_at=row["completed_at"],
                )
                sessions.append(model.to_entity())

            return sessions

    async def _get_opinions_for_session(self, conn, session_id: UUID) -> List[ExpertOpinion]:
        rows = await conn.fetch(
            """
            SELECT id, session_id, expert_id, opinion_text, confidence, created_at
            FROM expert_opinions
            WHERE session_id = $1
            ORDER BY created_at
            """,
            session_id,
        )

        return [
            ExpertOpinion(
                id=row["id"],
                session_id=row["session_id"],
                expert_id=row["expert_id"],
                opinion_text=row["opinion_text"],
                confidence=row["confidence"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
