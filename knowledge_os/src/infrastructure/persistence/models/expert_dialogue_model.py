"""
Expert Dialogue Model - ORM Model

Infrastructure layer model for PostgreSQL persistence.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.domain.entities.expert_dialogue import (
    DialogueMode,
    DialogueStatus,
    ExpertDialogue,
    ExpertOpinion,
)


class ExpertOpinionModel:
    def __init__(
        self,
        id: UUID,
        session_id: UUID,
        expert_id: UUID,
        opinion_text: str,
        confidence: float,
        created_at: datetime,
    ):
        self.id = id
        self.session_id = session_id
        self.expert_id = expert_id
        self.opinion_text = opinion_text
        self.confidence = confidence
        self.created_at = created_at

    @classmethod
    def from_entity(cls, opinion: ExpertOpinion) -> "ExpertOpinionModel":
        return cls(
            id=opinion.id,
            session_id=opinion.session_id,
            expert_id=opinion.expert_id,
            opinion_text=opinion.opinion_text,
            confidence=opinion.confidence,
            created_at=opinion.created_at,
        )

    def to_entity(self) -> ExpertOpinion:
        return ExpertOpinion(
            id=self.id,
            session_id=self.session_id,
            expert_id=self.expert_id,
            opinion_text=self.opinion_text,
            confidence=self.confidence,
            created_at=self.created_at,
        )


class ExpertDialogueModel:
    """
    ORM Model for ExpertDialogue (PostgreSQL)

    Table: expert_dialogues
    """

    def __init__(
        self,
        session_id: UUID,
        topic: str,
        mode: str,
        status: str,
        participants: List[UUID],
        final_decision: Optional[str] = None,
        consensus_score: Optional[float] = None,
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ):
        self.session_id = session_id
        self.topic = topic
        self.mode = mode
        self.status = status
        self.participants = participants
        self.final_decision = final_decision
        self.consensus_score = consensus_score
        self.created_at = created_at
        self.completed_at = completed_at

    @classmethod
    def from_entity(cls, dialogue: ExpertDialogue) -> "ExpertDialogueModel":
        return cls(
            session_id=dialogue.session_id,
            topic=dialogue.topic,
            mode=dialogue.mode.value,
            status=dialogue.status.value,
            participants=dialogue.participants,
            final_decision=dialogue.final_decision,
            consensus_score=dialogue.consensus_score,
            created_at=dialogue.created_at,
            completed_at=dialogue.completed_at,
        )

    def to_entity(self, opinions: Optional[List[ExpertOpinion]] = None) -> ExpertDialogue:
        return ExpertDialogue(
            session_id=self.session_id,
            topic=self.topic,
            mode=DialogueMode(self.mode),
            status=DialogueStatus(self.status),
            participants=self.participants,
            final_decision=self.final_decision,
            consensus_score=self.consensus_score,
            created_at=self.created_at,
            completed_at=self.completed_at,
            opinions=opinions,
        )
