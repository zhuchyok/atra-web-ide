"""
[SINGULARITY 31.3] Group Chat State Machine.
Structured speaker selection for multi-agent group chat discussions.
Provides context-driven speaker selection, consensus detection, and session management.
"""

import logging
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SpeakerRole(Enum):
    """Roles a speaker can assume in a group chat."""

    CONTEXT_PROVIDER = "context_provider"
    ANALYST = "analyst"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"
    DECIDER = "decider"


class SpeakerSelectionStrategy(Enum):
    """Strategies for selecting the next speaker in a group chat."""

    ROUND_ROBIN = "round_robin"
    CONTEXT_DRIVEN = "context_driven"
    VOTE = "vote"
    RANDOM = "random"


@dataclass
class GroupChatMessage:
    """A single message in a group chat session."""

    sender: str
    role: SpeakerRole
    content: str
    round_number: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GroupChatState:
    """Persistent state for a group chat session."""

    session_id: str
    topic: str
    participants: List[str]
    messages: List[GroupChatMessage] = field(default_factory=list)
    current_speaker_index: int = 0
    strategy: SpeakerSelectionStrategy = SpeakerSelectionStrategy.ROUND_ROBIN
    max_rounds: int = 10
    consensus_threshold: float = 0.8
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_EXPERT_AREAS: Dict[str, str] = {
    "Игорь": "backend architecture docker infrastructure scalability",
    "Роман": "database sql migration postgres query",
    "Дмитрий": "machine learning ml ollama mlx performance model embedding",
    "Анна": "testing qa reliability verification quality assurance",
    "Борис": "devops infrastructure docker deploy ci cd pipeline",
    "Александр": "security audit penetration vulnerability threat",
    "Евгения": "marketing pr growth strategy communication",
    "Константин": "architecture technical lead decisions coordination",
    "Артём": "ux ui design web interface user experience",
    "Виктория": "coordination strategy synthesis leadership planning",
    "Елена": "testing security vulnerabilities stability edge cases",
    "Игорь backend": "backend architecture docker infrastructure scalability",
    "Анна frontend": "frontend ux state management svelte component",
    "Дмитрий ml": "vector search embeddings pgvector model optimization",
}


class GroupChatStateMachine:
    """
    State machine for managing multi-agent group chat discussions.

    Supports multiple speaker selection strategies:
    - ROUND_ROBIN: simple sequential rotation
    - CONTEXT_DRIVEN: select speaker based on keyword overlap with recent messages
    - VOTE: simulated voting among participants
    - RANDOM: random selection

    Includes consensus detection and automatic session termination.
    """

    def __init__(self):
        self._sessions: Dict[str, GroupChatState] = {}

    def create_session(
        self,
        topic: str,
        participants: List[str],
        strategy: SpeakerSelectionStrategy = SpeakerSelectionStrategy.ROUND_ROBIN,
        max_rounds: int = 10,
        consensus_threshold: float = 0.8,
    ) -> str:
        """
        Create a new group chat session.

        Args:
            topic: Discussion topic.
            participants: List of agent names.
            strategy: Speaker selection strategy.
            max_rounds: Maximum rounds before auto-stop.
            consensus_threshold: Fraction of recent messages that must show
                agreement for consensus to be declared (0.0 - 1.0).

        Returns:
            session_id string.

        """
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = GroupChatState(
            session_id=session_id,
            topic=topic,
            participants=participants,
            strategy=strategy,
            max_rounds=max_rounds,
            consensus_threshold=consensus_threshold,
        )
        logger.info(
            "[CHAT] Session %s created: topic=%r, participants=%s, strategy=%s",
            session_id,
            topic,
            participants,
            strategy.value,
        )
        return session_id

    def get_next_speaker(self, session_id: str) -> Optional[str]:
        """
        Determine the next speaker for a given session.

        Delegates to the appropriate strategy method.

        Args:
            session_id: The session to advance.

        Returns:
            Name of the next speaker, or None if session is invalid/inactive.

        """
        state = self._sessions.get(session_id)
        if not state or not state.is_active:
            return None

        strategy_map = {
            SpeakerSelectionStrategy.ROUND_ROBIN: self._round_robin_select,
            SpeakerSelectionStrategy.CONTEXT_DRIVEN: self._context_driven_select,
            SpeakerSelectionStrategy.VOTE: self._vote_select,
            SpeakerSelectionStrategy.RANDOM: self._random_select,
        }
        selector = strategy_map.get(state.strategy, self._round_robin_select)
        return selector(state)

    def add_message(
        self,
        session_id: str,
        sender: str,
        content: str,
        role: SpeakerRole = SpeakerRole.ANALYST,
    ) -> bool:
        """
        Add a message to the session.

        After adding, checks for consensus or max_rounds exceeded and
        deactivates the session if either condition is met.

        Args:
            session_id: Target session.
            sender: Name of the agent sending the message.
            content: Message text.
            role: The speaker's role in this message.

        Returns:
            True if the session should stop (consensus reached or max rounds
            exceeded), False otherwise.

        """
        state = self._sessions.get(session_id)
        if not state or not state.is_active:
            return False

        round_number = len([m for m in state.messages if m.sender == sender]) + 1
        msg = GroupChatMessage(
            sender=sender,
            role=role,
            content=content,
            round_number=round_number,
        )
        state.messages.append(msg)
        state.current_speaker_index = (state.current_speaker_index + 1) % len(state.participants)

        logger.debug("[CHAT] %s (%s): %s...", sender, role.value, content[:60])

        consensus_reached, score = self.check_consensus(session_id)
        rounds_completed = max(m.round_number for m in state.messages) if state.messages else 0
        if consensus_reached or rounds_completed >= state.max_rounds:
            state.is_active = False
            logger.info(
                "[CHAT] Session %s ended: consensus=%s (%.2f), rounds=%d",
                session_id,
                consensus_reached,
                score,
                rounds_completed,
            )
            return True
        return False

    def get_transcript(self, session_id: str) -> List[GroupChatMessage]:
        """Return all messages for a session in chronological order."""
        state = self._sessions.get(session_id)
        return list(state.messages) if state else []

    def check_consensus(self, session_id: str) -> Tuple[bool, float]:
        """
        Check if consensus has been reached in a session.

        Scans the most recent N messages (up to the number of participants)
        for agreement keywords. If the fraction of agreeing messages meets
        or exceeds the session's consensus_threshold, consensus is declared.

        Args:
            session_id: The session to evaluate.

        Returns:
            (consensus_reached, score) tuple.

        """
        state = self._sessions.get(session_id)
        if not state or len(state.messages) < 2:
            return False, 0.0

        window_size = min(len(state.messages), len(state.participants))
        recent = state.messages[-window_size:]

        agreement_keywords = {
            "согласен",
            "поддерживаю",
            "верно",
            "правильно",
            "да",
            "agree",
            "supported",
            "correct",
            "yes",
            "+1",
            "хорошо",
            "отлично",
            "принято",
            "одобряю",
            "согласна",
            "поддерживаю",
        }

        agreement_count = 0
        for msg in recent:
            words = set(re.findall(r"\w+", msg.content.lower()))
            if words & agreement_keywords:
                agreement_count += 1

        score = agreement_count / len(recent) if recent else 0.0
        return score >= state.consensus_threshold, score

    def close_session(self, session_id: str) -> Dict:
        """
        Close a session and return a summary.

        The session is removed from the state machine.

        Args:
            session_id: The session to close.

        Returns:
            Dict with session summary including transcript, consensus info,
            and statistics.

        """
        state = self._sessions.get(session_id)
        if not state:
            return {"error": "session not found"}

        state.is_active = False
        consensus, score = self.check_consensus(session_id)
        rounds_completed = max(m.round_number for m in state.messages) if state.messages else 0

        summary = {
            "session_id": session_id,
            "topic": state.topic,
            "messages": [
                {
                    "sender": m.sender,
                    "role": m.role.value,
                    "content": m.content,
                    "round_number": m.round_number,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in state.messages
            ],
            "round_count": rounds_completed,
            "total_messages": len(state.messages),
            "consensus_reached": consensus,
            "consensus_score": round(score, 4),
            "participants": state.participants,
            "strategy": state.strategy.value,
            "max_rounds": state.max_rounds,
        }
        del self._sessions[session_id]
        logger.info(
            "[CHAT] Session %s closed with %d messages", session_id, len(summary["messages"])
        )
        return summary

    def _round_robin_select(self, state: GroupChatState) -> str:
        """Pick the next speaker by cycling through the participant list."""
        speaker = state.participants[state.current_speaker_index % len(state.participants)]
        state.current_speaker_index = (state.current_speaker_index + 1) % len(state.participants)
        return speaker

    def _context_driven_select(self, state: GroupChatState) -> str:
        """
        Pick the next speaker based on keyword overlap with recent messages.

        Algorithm:
          1. Take the last 3 messages (or fewer if not enough).
          2. Extract meaningful keywords (nouns, technical terms) >= 4 chars.
          3. Score each participant by matching keywords against known areas.
          4. Penalize the last speaker slightly to encourage diversity.
          5. The highest-scoring participant speaks next.
          6. Fall back to round-robin if no clear match (max_score <= 0).

        """
        recent_messages = state.messages[-3:] if len(state.messages) >= 3 else state.messages
        if not recent_messages:
            return state.participants[0]

        combined = " ".join(m.content for m in recent_messages)
        keywords = self._extract_keywords(combined)
        if not keywords:
            return self._round_robin_select(state)

        speaker_scores: Dict[str, int] = {p: 0 for p in state.participants}
        for speaker in speaker_scores:
            areas = _EXPERT_AREAS.get(speaker, speaker.lower())
            for kw in keywords:
                if kw in areas:
                    speaker_scores[speaker] += 2
                if kw in speaker.lower():
                    speaker_scores[speaker] += 1

        last_speaker = state.messages[-1].sender if state.messages else None
        if last_speaker and last_speaker in speaker_scores:
            speaker_scores[last_speaker] -= 1

        max_score = max(speaker_scores.values())
        if max_score <= 0:
            return self._round_robin_select(state)

        best = [p for p, s in speaker_scores.items() if s == max_score]
        return random.choice(best)

    def _vote_select(self, state: GroupChatState) -> str:
        """
        Simulate a vote among participants for the next speaker.

        Each participant (except the last speaker) casts a weighted vote.
        Participants who have contributed more messages carry slightly
        more weight. The candidate with the most votes is selected.

        """
        last_speaker = state.messages[-1].sender if state.messages else None
        candidates = [p for p in state.participants if p != last_speaker]
        if not candidates:
            return self._random_select(state)

        votes: Dict[str, float] = {}
        for p in state.participants:
            if p == last_speaker:
                continue
            msg_count = len([m for m in state.messages if m.sender == p])
            weight = 1.0 + msg_count * 0.1
            choice = random.choices(candidates, weights=[1.0] * len(candidates))[0]
            votes[choice] = votes.get(choice, 0.0) + weight

        if not votes:
            return self._random_select(state)
        return max(votes, key=votes.get)

    def _random_select(self, state: GroupChatState) -> str:
        """Pick a random participant."""
        return random.choice(state.participants)

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """
        Extract meaningful keywords from text.

        Filters out common stopwords in Russian and English, returns the
        top 10 most frequent words of length >= 4 characters.

        """
        stop_words = {
            "это",
            "что",
            "как",
            "для",
            "все",
            "или",
            "на",
            "с",
            "по",
            "от",
            "из",
            "у",
            "к",
            "о",
            "об",
            "за",
            "не",
            "но",
            "и",
            "а",
            "то",
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "can",
            "could",
            "shall",
            "should",
            "may",
            "might",
            "must",
            "of",
            "in",
            "to",
            "for",
            "with",
            "on",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "out",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "because",
            "if",
            "while",
            "also",
            "its",
            "them",
            "they",
            "their",
            "this",
            "that",
            "these",
            "those",
            "which",
            "who",
            "whom",
            "about",
            "been",
            "being",
        }
        words = re.findall(r"[а-яА-Яa-zA-Z]{4,}", text.lower())
        words = [w for w in words if w not in stop_words]
        word_counts: Dict[str, int] = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1
        sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
        return [w for w, _ in sorted_words[:10]]


_instance: Optional[GroupChatStateMachine] = None


def get_group_chat_state_machine() -> GroupChatStateMachine:
    """
    Get the singleton GroupChatStateMachine instance.

    Returns:
        The shared GroupChatStateMachine instance.

    """
    global _instance
    if _instance is None:
        _instance = GroupChatStateMachine()
    return _instance
