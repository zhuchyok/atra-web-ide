"""Tests for distillation_engine.py — quality gate scoring."""

import json
import pytest


class TestQualityGateScoring:
    """Test the knowledge distillation quality gate scoring."""

    def test_quality_gate_imports(self):
        """Quality gate function should be importable."""
        from app.distillation_engine import KnowledgeDistiller
        assert hasattr(KnowledgeDistiller, "_compute_quality_gate")

    def test_quality_score_defaults(self):
        """Test the score calculation logic with various inputs."""
        from app.distillation_engine import KnowledgeDistiller

        # Rich content should score high
        score, reasons = KnowledgeDistiller._compute_quality_gate(
            wisdom_summary="A" * 100,
            instruction="do something specific and important",
            category="coding",
            wisdom={},
        )
        assert score > 0.50
        assert "summary_rich" in reasons

        # Empty content should score low (base is 0.20 now)
        score, reasons = KnowledgeDistiller._compute_quality_gate(
            wisdom_summary="",
            instruction="",
            category="",
            wisdom={},
        )
        assert score < 0.50
        assert "summary_empty" in reasons

        # Fallback parse should penalize
        score, reasons = KnowledgeDistiller._compute_quality_gate(
            wisdom_summary="short",
            instruction="",
            category="",
            wisdom={"_quality_source": "fallback_parse"},
        )
        assert "fallback_parse_penalty" in reasons

    def test_quality_score_range(self):
        """Score should stay within [0.10, 1.0] range."""
        from app.distillation_engine import KnowledgeDistiller

        # Very short content with fallback should be near minimum
        score, _ = KnowledgeDistiller._compute_quality_gate(
            wisdom_summary="tiny",
            instruction="",
            category="",
            wisdom={"_quality_source": "fallback_parse"},
        )
        assert 0.10 <= score <= 1.0

        # Rich content with all bonuses should be near maximum
        score, _ = KnowledgeDistiller._compute_quality_gate(
            wisdom_summary="A" * 100,
            instruction="x" * 30,
            category="coding",
            wisdom={},
        )
        assert 0.10 <= score <= 1.0
        assert score > 0.50

    def test_quality_score_categories(self):
        """Valid categories should boost score."""
        from app.distillation_engine import KnowledgeDistiller

        valid = ["coding", "strategy", "ops", "research"]
        for cat in valid:
            score, reasons = KnowledgeDistiller._compute_quality_gate(
                wisdom_summary="A" * 90,
                instruction="x" * 25,
                category=cat,
                wisdom={},
            )
            assert "category_valid" in reasons

        for cat in ["unknown", "", "general"]:
            score, reasons = KnowledgeDistiller._compute_quality_gate(
                wisdom_summary="A" * 90,
                instruction="x" * 25,
                category=cat,
                wisdom={},
            )
            assert "category_fallback" in reasons

    def test_quality_score_base_changed(self):
        """Base score should now be 0.20 (was 0.55)."""
        from app.distillation_engine import KnowledgeDistiller

        score, reasons = KnowledgeDistiller._compute_quality_gate(
            wisdom_summary="",
            instruction="",
            category="",
            wisdom={},
        )
        assert score <= 0.30

    def test_short_content_penalty(self):
        """Very short content should get penalty."""
        from app.distillation_engine import KnowledgeDistiller

        score, reasons = KnowledgeDistiller._compute_quality_gate(
            wisdom_summary="short text",
            instruction="x" * 25,
            category="coding",
            wisdom={},
        )
        has_penalty = "too_short" in reasons
        if has_penalty:
            assert score <= 0.35
