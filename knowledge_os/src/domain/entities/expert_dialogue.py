"""
Expert Dialogue Entity - Domain Entity

Represents an expert dialogue session with multiple participants.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID


class DialogueMode(Enum):
    SEQUENTIAL = "SEQUENTIAL"
    DEBATE = "DEBATE"
    COLLABORATION = "COLLABORATION"
    SWARM = "SWARM"


class DialogueStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ExpertOpinion:
    """Individual opinion from an expert participant"""

    id: UUID
    session_id: UUID
    expert_id: UUID
    opinion_text: str
    confidence: float
    created_at: datetime


@dataclass(frozen=True)
class ExpertDialogue:
    """
    Expert Dialogue Entity

    Represents a multi-expert dialogue session.
    """

    session_id: UUID
    topic: str
    mode: DialogueMode
    status: DialogueStatus
    participants: List[UUID]
    final_decision: Optional[str] = None
    consensus_score: Optional[float] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    opinions: Optional[List[ExpertOpinion]] = None

    def complete(self, final_decision: str, consensus_score: float) -> "ExpertDialogue":
        """Complete the dialogue with final decision"""
        return ExpertDialogue(
            session_id=self.session_id,
            topic=self.topic,
            mode=self.mode,
            status=DialogueStatus.COMPLETED,
            participants=self.participants,
            final_decision=final_decision,
            consensus_score=consensus_score,
            created_at=self.created_at,
            completed_at=datetime.utcnow(),
            opinions=self.opinions,
        )
