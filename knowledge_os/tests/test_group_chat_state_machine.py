"""Tests for group_chat_state_machine.py — Group Chat State Machine."""

import random

import pytest
from app.group_chat_state_machine import (
    GroupChatMessage,
    GroupChatStateMachine,
    SpeakerRole,
    SpeakerSelectionStrategy,
    get_group_chat_state_machine,
)


class TestGroupChatStateMachine:
    """Test suite for GroupChatStateMachine."""

    def setup_method(self):
        self.machine = GroupChatStateMachine()

    # ─── Session Creation ──────────────────────────────────────────────

    def test_create_session_returns_session_id(self):
        session_id = self.machine.create_session(
            "Test topic", ["Alice", "Bob"], SpeakerSelectionStrategy.ROUND_ROBIN
        )
        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_create_session_stores_state(self):
        session_id = self.machine.create_session(
            "Test topic",
            ["Alice", "Bob"],
            SpeakerSelectionStrategy.RANDOM,
            max_rounds=5,
            consensus_threshold=0.75,
        )
        transcript = self.machine.get_transcript(session_id)
        assert transcript == []

    def test_create_session_defaults(self):
        session_id = self.machine.create_session("Test topic", ["A", "B"])
        # Should default to ROUND_ROBIN — verify by getting consecutive speakers
        assert self.machine.get_next_speaker(session_id) == "A"
        assert self.machine.get_next_speaker(session_id) == "B"

    # ─── ROUND_ROBIN Strategy ──────────────────────────────────────────

    def test_round_robin_cycles_through_participants(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B", "C"], SpeakerSelectionStrategy.ROUND_ROBIN
        )
        assert self.machine.get_next_speaker(session_id) == "A"
        assert self.machine.get_next_speaker(session_id) == "B"
        assert self.machine.get_next_speaker(session_id) == "C"
        assert self.machine.get_next_speaker(session_id) == "A"
        assert self.machine.get_next_speaker(session_id) == "B"

    def test_round_robin_with_two_participants(self):
        session_id = self.machine.create_session(
            "Topic", ["X", "Y"], SpeakerSelectionStrategy.ROUND_ROBIN
        )
        assert self.machine.get_next_speaker(session_id) == "X"
        assert self.machine.get_next_speaker(session_id) == "Y"
        assert self.machine.get_next_speaker(session_id) == "X"

    def test_round_robin_single_participant(self):
        session_id = self.machine.create_session(
            "Topic", ["Alone"], SpeakerSelectionStrategy.ROUND_ROBIN
        )
        assert self.machine.get_next_speaker(session_id) == "Alone"
        assert self.machine.get_next_speaker(session_id) == "Alone"

    # ─── CONTEXT_DRIVEN Strategy ───────────────────────────────────────

    def test_context_driven_selects_matching_expert(self):
        """When messages mention 'database', the DB expert (Роман) should be picked."""
        session_id = self.machine.create_session(
            "Database migration",
            ["Игорь", "Роман", "Анна"],
            SpeakerSelectionStrategy.CONTEXT_DRIVEN,
        )
        self.machine.add_message(
            session_id, "Игорь",
            "I think we need to optimize the database queries for postgres.",
            SpeakerRole.CONTEXT_PROVIDER,
        )
        next_speaker = self.machine.get_next_speaker(session_id)
        assert next_speaker == "Роман"

    def test_context_driven_falls_back_to_round_robin(self):
        """When no keywords match, fall back to round-robin."""
        session_id = self.machine.create_session(
            "Random topic",
            ["A", "B", "C"],
            SpeakerSelectionStrategy.CONTEXT_DRIVEN,
        )
        # First message — no context yet, should pick first participant
        next_speaker = self.machine.get_next_speaker(session_id)
        assert next_speaker == "A"

    def test_context_driven_with_security_keywords(self):
        """'security' mentions should route to Александр."""
        session_id = self.machine.create_session(
            "Security audit",
            ["Игорь", "Александр", "Анна"],
            SpeakerSelectionStrategy.CONTEXT_DRIVEN,
        )
        self.machine.add_message(
            session_id, "Игорь",
            "We need a full security audit and penetration testing.",
            SpeakerRole.CONTEXT_PROVIDER,
        )
        next_speaker = self.machine.get_next_speaker(session_id)
        assert next_speaker == "Александр"

    def test_context_driven_penalizes_last_speaker(self):
        """The last speaker gets a penalty to encourage diversity."""
        session_id = self.machine.create_session(
            "Infrastructure",
            ["Игорь", "Борис", "Анна"],
            SpeakerSelectionStrategy.CONTEXT_DRIVEN,
        )
        # Both Игорь and Борис match "docker infrastructure",
        # but Игорь just spoke, so Борис should be preferred
        self.machine.add_message(
            session_id, "Игорь",
            "We need to improve docker infrastructure deployment.",
        )
        next_speaker = self.machine.get_next_speaker(session_id)
        assert next_speaker == "Борис"

    # ─── VOTE Strategy ─────────────────────────────────────────────────

    def test_vote_returns_a_candidate(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B", "C"], SpeakerSelectionStrategy.VOTE
        )
        self.machine.add_message(session_id, "A", "Starting discussion")
        next_speaker = self.machine.get_next_speaker(session_id)
        assert next_speaker in ("B", "C")

    def test_vote_excludes_last_speaker(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B"], SpeakerSelectionStrategy.VOTE
        )
        self.machine.add_message(session_id, "A", "Hello")
        # B is the only candidate (A just spoke)
        assert self.machine.get_next_speaker(session_id) == "B"

    def test_vote_allows_any_candidate_except_last(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B", "C"], SpeakerSelectionStrategy.VOTE
        )
        self.machine.add_message(session_id, "A", "First message")
        speaker = self.machine.get_next_speaker(session_id)
        assert speaker != "A"

    # ─── RANDOM Strategy ───────────────────────────────────────────────

    def test_random_returns_a_participant(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B", "C"], SpeakerSelectionStrategy.RANDOM
        )
        speakers = {self.machine.get_next_speaker(session_id) for _ in range(30)}
        assert speakers.issubset({"A", "B", "C"})
        assert len(speakers) > 1

    def test_random_single_participant(self):
        session_id = self.machine.create_session(
            "Topic", ["Only"], SpeakerSelectionStrategy.RANDOM
        )
        assert self.machine.get_next_speaker(session_id) == "Only"
        assert self.machine.get_next_speaker(session_id) == "Only"

    # ─── Consensus Detection ──────────────────────────────────────────

    def test_consensus_detected_when_majority_agrees(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B", "C"],
            SpeakerSelectionStrategy.ROUND_ROBIN,
            consensus_threshold=0.5,
        )
        self.machine.add_message(session_id, "A", "I agree with this proposal", SpeakerRole.ANALYST)
        self.machine.add_message(session_id, "B", "I support this as well", SpeakerRole.ANALYST)
        # 2 out of 3 messages agree => score = 2/3 ≈ 0.67 >= 0.5 => consensus

        consensus, score = self.machine.check_consensus(session_id)
        assert consensus is True
        assert score >= 0.5

    def test_consensus_not_detected_when_disagreement(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B", "C"],
            SpeakerSelectionStrategy.ROUND_ROBIN,
            consensus_threshold=0.8,
        )
        self.machine.add_message(session_id, "A", "I disagree with this idea")
        self.machine.add_message(session_id, "B", "This approach has problems")

        consensus, score = self.machine.check_consensus(session_id)
        assert consensus is False
        assert score < 0.8

    def test_consensus_not_possible_with_single_message(self):
        session_id = self.machine.create_session("Topic", ["A"])
        self.machine.add_message(session_id, "A", "Hello")
        consensus, score = self.machine.check_consensus(session_id)
        assert consensus is False
        assert score == 0.0

    def test_add_message_returns_true_when_consensus_reached(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B"],
            SpeakerSelectionStrategy.ROUND_ROBIN,
            consensus_threshold=0.5,
        )
        self.machine.add_message(session_id, "A", "I agree")
        stopped = self.machine.add_message(session_id, "B", "I support this")
        assert stopped is True

    def test_add_message_returns_false_when_no_consensus(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B"],
            SpeakerSelectionStrategy.ROUND_ROBIN,
            consensus_threshold=0.9,
        )
        self.machine.add_message(session_id, "A", "I agree")
        stopped = self.machine.add_message(session_id, "B", "Not sure")
        assert stopped is False

    def test_russian_agreement_keywords_detected(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B"],
            SpeakerSelectionStrategy.ROUND_ROBIN,
            consensus_threshold=0.5,
        )
        self.machine.add_message(session_id, "A", "Я согласен с этим предложением")
        stopped = self.machine.add_message(session_id, "B", "Я полностью поддерживаю")
        assert stopped is True

    # ─── Max Rounds Auto-Stop ──────────────────────────────────────────

    def test_session_stops_after_max_rounds(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B"],
            SpeakerSelectionStrategy.ROUND_ROBIN,
            max_rounds=2,
            consensus_threshold=0.99,
        )
        self.machine.add_message(session_id, "A", "msg1")
        self.machine.add_message(session_id, "B", "msg2")
        # round 2 for A
        stopped = self.machine.add_message(session_id, "A", "msg3")
        assert stopped is True

    def test_get_next_speaker_returns_none_for_stopped_session(self):
        session_id = self.machine.create_session(
            "Topic", ["A"],
            SpeakerSelectionStrategy.ROUND_ROBIN,
            max_rounds=1,
        )
        self.machine.add_message(session_id, "A", "only message")
        assert self.machine.get_next_speaker(session_id) is None

    # ─── Transcript ────────────────────────────────────────────────────

    def test_get_transcript_returns_all_messages(self):
        session_id = self.machine.create_session("Topic", ["A", "B"])
        assert len(self.machine.get_transcript(session_id)) == 0

        self.machine.add_message(session_id, "A", "First")
        self.machine.add_message(session_id, "B", "Second")

        transcript = self.machine.get_transcript(session_id)
        assert len(transcript) == 2
        assert transcript[0].sender == "A"
        assert transcript[0].content == "First"
        assert transcript[1].sender == "B"

    def test_transcript_messages_have_roles(self):
        session_id = self.machine.create_session("Topic", ["A"])
        self.machine.add_message(
            session_id, "A", "ctx", SpeakerRole.CONTEXT_PROVIDER
        )
        self.machine.add_message(
            session_id, "A", "crit", SpeakerRole.CRITIC
        )
        transcript = self.machine.get_transcript(session_id)
        assert transcript[0].role == SpeakerRole.CONTEXT_PROVIDER
        assert transcript[1].role == SpeakerRole.CRITIC

    def test_transcript_messages_have_round_numbers(self):
        session_id = self.machine.create_session("Topic", ["A", "B"])
        self.machine.add_message(session_id, "A", "first")
        self.machine.add_message(session_id, "B", "second")
        self.machine.add_message(session_id, "A", "third")

        transcript = self.machine.get_transcript(session_id)
        assert transcript[0].round_number == 1
        assert transcript[1].round_number == 1
        assert transcript[2].round_number == 2

    # ─── close_session ─────────────────────────────────────────────────

    def test_close_session_returns_summary(self):
        session_id = self.machine.create_session(
            "My topic", ["A", "B"], SpeakerSelectionStrategy.ROUND_ROBIN
        )
        self.machine.add_message(session_id, "A", "Hello")
        self.machine.add_message(session_id, "B", "Hi")

        summary = self.machine.close_session(session_id)
        assert summary["topic"] == "My topic"
        assert summary["total_messages"] == 2
        assert summary["participants"] == ["A", "B"]
        assert "consensus_reached" in summary
        assert "consensus_score" in summary
        assert "messages" in summary

    def test_close_session_removes_state(self):
        session_id = self.machine.create_session("Topic", ["A"])
        self.machine.add_message(session_id, "A", "msg")
        self.machine.close_session(session_id)
        assert self.machine.get_transcript(session_id) == []
        assert self.machine.get_next_speaker(session_id) is None

    def test_close_session_missing_session(self):
        summary = self.machine.close_session("nonexistent")
        assert summary == {"error": "session not found"}

    def test_close_session_includes_consensus_info(self):
        session_id = self.machine.create_session(
            "Topic", ["A", "B"],
            SpeakerSelectionStrategy.ROUND_ROBIN,
            consensus_threshold=0.5,
        )
        self.machine.add_message(session_id, "A", "согласен")
        summary = self.machine.close_session(session_id)
        assert isinstance(summary["consensus_reached"], bool)
        assert isinstance(summary["consensus_score"], float)

    # ─── add_message edge cases ────────────────────────────────────────

    def test_add_message_invalid_session(self):
        result = self.machine.add_message("invalid", "A", "Hello")
        assert result is False

    def test_add_message_inactive_session(self):
        session_id = self.machine.create_session("Topic", ["A"], max_rounds=1)
        self.machine.add_message(session_id, "A", "first")
        result = self.machine.add_message(session_id, "A", "second")
        assert result is False

    # ─── get_next_speaker edge cases ──────────────────────────────────

    def test_get_next_speaker_invalid_session(self):
        assert self.machine.get_next_speaker("nonexistent") is None

    # ─── Singleton ─────────────────────────────────────────────────────

    def test_get_group_chat_state_machine_returns_same_instance(self):
        m1 = get_group_chat_state_machine()
        m2 = get_group_chat_state_machine()
        assert m1 is m2

    def test_multiple_independent_instances(self):
        m1 = GroupChatStateMachine()
        m2 = GroupChatStateMachine()
        assert m1 is not m2

    # ─── Keyword extraction ────────────────────────────────────────────

    def test_extract_keywords_filters_stopwords(self):
        text = "the quick brown fox jumps over the lazy dog near the database"
        keywords = GroupChatStateMachine._extract_keywords(text)
        assert "the" not in keywords
        assert "quick" in keywords or "brown" in keywords
        assert "database" in keywords

    def test_extract_keywords_returns_top_frequent(self):
        text = "database database database query query schema schema schema schema schema"
        keywords = GroupChatStateMachine._extract_keywords(text)
        assert "schema" in keywords
        assert "query" in keywords
        assert "database" in keywords

    def test_extract_keywords_handles_short_words(self):
        text = "a an to be or no go"
        keywords = GroupChatStateMachine._extract_keywords(text)
        assert keywords == []

    def test_extract_keywords_empty_text(self):
        keywords = GroupChatStateMachine._extract_keywords("")
        assert keywords == []
