"""
Фаза 4, День 5: сбор и анализ обратной связи от пользователей.

SQLite-хранилище отзывов и автоматическая классификация проблем качества.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _default_db_path() -> Path:
    """Путь к feedback.db относительно backend."""
    return Path(__file__).resolve().parent.parent.parent / "feedback.db"


class FeedbackCollector:
    """Сбор и анализ обратной связи от пользователей."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self._init_db()

    def _init_db(self) -> None:
        """Инициализация базы данных для обратной связи."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    query TEXT,
                    answer TEXT,
                    rating INTEGER,
                    comment TEXT,
                    corrected_answer TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT,
                    issue_type TEXT,
                    severity INTEGER,
                    resolved INTEGER DEFAULT 0,
                    feedback_id INTEGER,
                    FOREIGN KEY (feedback_id) REFERENCES feedback (id)
                )
            """
            )

    def add_feedback(
        self,
        session_id: str,
        query: str,
        answer: str,
        rating: int,
        comment: Optional[str] = None,
        corrected_answer: Optional[str] = None,
    ) -> int:
        """Добавление обратной связи от пользователя."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                INSERT INTO feedback (session_id, query, answer, rating, comment, corrected_answer)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (session_id, query, answer, rating, comment, corrected_answer),
            )
            feedback_id = cursor.lastrowid or 0
            if rating <= 2:
                self._create_quality_issue(
                    conn,
                    feedback_id,
                    query,
                    issue_type=self._classify_issue(rating, comment),
                    severity=5 - rating,
                )
            return feedback_id

    def _create_quality_issue(
        self,
        conn: sqlite3.Connection,
        feedback_id: int,
        query: str,
        issue_type: str,
        severity: int,
    ) -> None:
        """Создание записи о проблеме качества."""
        conn.execute(
            """
            INSERT INTO quality_issues (query, issue_type, severity, feedback_id)
            VALUES (?, ?, ?, ?)
        """,
            (query, issue_type, severity, feedback_id),
        )

    def _classify_issue(self, rating: int, comment: Optional[str]) -> str:
        """Классификация проблемы на основе отзыва."""
        if comment:
            comment_lower = comment.lower()
            if any(
                w in comment_lower
                for w in ["неправильно", "ошибка", "incorrect", "wrong"]
            ):
                return "incorrect"
            if any(
                w in comment_lower
                for w in ["не по теме", "irrelevant", "off-topic"]
            ):
                return "irrelevant"
            if any(
                w in comment_lower
                for w in ["неполный", "мало информации", "incomplete"]
            ):
                return "incomplete"
        return "confusing" if rating == 2 else "incorrect"

    def get_feedback_stats(self, days: int = 30) -> Dict:
        """Статистика обратной связи за последние N дней."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    AVG(rating) as avg_rating,
                    SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) as low_ratings,
                    SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) as high_ratings
                FROM feedback
                WHERE timestamp > datetime('now', ?)
            """,
                (f"-{days} days",),
            )
            row = cursor.fetchone()
        if not row or row[0] == 0:
            return {
                "total_feedback": 0,
                "avg_rating": 0.0,
                "low_ratings_count": 0,
                "high_ratings_count": 0,
                "satisfaction_rate": 0.0,
            }
        total, avg_rating, low, high = row[0], row[1] or 0, row[2] or 0, row[3] or 0
        return {
            "total_feedback": total,
            "avg_rating": float(avg_rating),
            "low_ratings_count": low,
            "high_ratings_count": high,
            "satisfaction_rate": high / total if total else 0.0,
        }

    def get_quality_issues(self, unresolved_only: bool = True) -> List[Dict]:
        """Получение списка проблем с качеством."""
        with sqlite3.connect(str(self.db_path)) as conn:
            query = """
                SELECT q.id, q.query, q.issue_type, q.severity, f.rating, f.comment
                FROM quality_issues q
                LEFT JOIN feedback f ON q.feedback_id = f.id
            """
            if unresolved_only:
                query += " WHERE q.resolved = 0"
            query += " ORDER BY q.severity DESC, q.id DESC"
            cursor = conn.execute(query)
            rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "query": r[1],
                "issue_type": r[2],
                "severity": r[3],
                "rating": r[4],
                "comment": r[5],
            }
            for r in rows
        ]
