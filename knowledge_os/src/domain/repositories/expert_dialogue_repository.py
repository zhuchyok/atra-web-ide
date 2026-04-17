"""
Expert Dialogue Repository Interface - Domain Repository

Abstract interface for expert dialogue persistence.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from ..entities.expert_dialogue import ExpertDialogue, ExpertOpinion


class ExpertDialogueRepository(ABC):
    """Abstract repository for ExpertDialogue entities"""

    @abstractmethod
    async def save_session(self, dialogue: ExpertDialogue) -> ExpertDialogue:
        """Save a dialogue session"""
        pass

    @abstractmethod
    async def save_opinion(self, opinion: ExpertOpinion) -> ExpertOpinion:
        """Save an expert opinion"""
        pass

    @abstractmethod
    async def get_session(self, session_id: UUID) -> Optional[ExpertDialogue]:
        """Get dialogue session by ID"""
        pass

    @abstractmethod
    async def list_recent_sessions(
        self, limit: int = 20, since: Optional[datetime] = None
    ) -> List[ExpertDialogue]:
        """List recent dialogue sessions"""
        pass
