"""
Фаза 4, День 6: автоматическое улучшение системы на основе обратной связи.

Анализ feedback, корректировка порогов и лимитов RAG.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "auto_improve_config.json"


class AutoImprover:
    """Автоматическое улучшение системы на основе обратной связи."""

    def __init__(
        self,
        feedback_collector: Any,
        rag_service: Any,
        config_path: Optional[str] = None,
    ):
        self.feedback_collector = feedback_collector
        self.rag_service = rag_service
        self.config_path = Path(config_path) if config_path else _default_config_path()
        self.improvements_log: List[Dict] = []
        self._load_config()

    def _load_config(self) -> None:
        """Загрузка конфигурации автоулучшений."""
        default_config = {
            "min_feedback_for_improvement": 3,
            "improvement_cooldown_hours": 24,
            "auto_adjust_thresholds": True,
            "threshold_adjustment_step": 0.05,
            "max_threshold_adjustment": 0.2,
        }
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = {**default_config, **json.load(f)}
            else:
                self.config = default_config
                self._save_config()
        except Exception as e:
            logger.warning("Auto-improve config load failed: %s", e)
            self.config = default_config

    def _save_config(self) -> None:
        """Сохранение конфигурации."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Auto-improve config save failed: %s", e)

    async def analyze_and_improve(self) -> Dict[str, Any]:
        """Анализ обратной связи и применение улучшений."""
        logger.info("Starting automatic improvement analysis")

        feedback_stats = self.feedback_collector.get_feedback_stats(days=7)
        quality_issues = self.feedback_collector.get_quality_issues(
            unresolved_only=True
        )

        improvements: List[Dict] = []

        if (
            feedback_stats["total_feedback"] > self.config["min_feedback_for_improvement"]
            and feedback_stats["satisfaction_rate"] < 0.8
        ):
            if self.config.get("auto_adjust_thresholds"):
                adjustment = self._calculate_threshold_adjustment(feedback_stats)
                if adjustment:
                    improvements.append({
                        "type": "threshold_adjustment",
                        "adjustment": adjustment,
                        "reason": f"Low satisfaction rate: {feedback_stats['satisfaction_rate']:.2%}",
                    })

        for issue in quality_issues[:5]:
            improvement = await self._analyze_specific_issue(issue)
            if improvement:
                improvements.append(improvement)

        for improvement in improvements:
            await self._apply_improvement(improvement)

        self._log_improvements(improvements)

        return {
            "analyzed_feedback": feedback_stats["total_feedback"],
            "satisfaction_rate": feedback_stats["satisfaction_rate"],
            "improvements_applied": len(improvements),
            "improvements": improvements,
        }

    def _calculate_threshold_adjustment(self, feedback_stats: Dict) -> Optional[Dict]:
        """Расчёт корректировки порогов (информационно, без изменения runtime)."""
        step = self.config.get("threshold_adjustment_step", 0.05)
        return {
            "similarity_threshold": min(
                step,
                self.config.get("max_threshold_adjustment", 0.2),
            ),
            "note": "Apply manually or via config reload",
        }

    async def _analyze_specific_issue(self, issue: Dict) -> Optional[Dict]:
        """Анализ конкретной проблемы."""
        issue_type = issue.get("issue_type", "")

        if issue_type == "irrelevant":
            current = getattr(
                self.rag_service, "similarity_threshold", 0.75
            )
            return {
                "type": "increase_similarity_threshold",
                "current_threshold": current,
                "new_threshold": min(current + 0.1, 0.9),
                "reason": f"Irrelevant answer for query: {issue.get('query', '')[:50]}...",
            }

        if issue_type == "incomplete":
            current = getattr(self.rag_service, "chunk_limit", 1)
            return {
                "type": "increase_chunk_limit",
                "current_limit": current,
                "new_limit": min(current + 1, 3),
                "reason": f"Incomplete answer for query: {issue.get('query', '')[:50]}...",
            }

        return None

    async def _apply_improvement(self, improvement: Dict) -> None:
        """Применение улучшения (логирование; реальные изменения — через конфиг)."""
        logger.info("Auto-improvement suggested: %s", improvement)
        self.improvements_log.append(improvement)

    def _log_improvements(self, improvements: List[Dict]) -> None:
        """Логирование применённых улучшений."""
        for imp in improvements:
            self.improvements_log.append(imp)
