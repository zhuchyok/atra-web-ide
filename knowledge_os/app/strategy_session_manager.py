"""
Strategy Session Manager - управление сессиями стратегий
Концепция из agent.md: сессионная модель для сохранения контекста между сессиями
"""

import logging
import sqlite3
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class StrategySessionManager:
    """
    Менеджер сессий стратегий для сохранения контекста и планов
    
    Функции:
    - Создание сессий
    - Управление вопросами/ответами
    - Создание планов
    - Восстановление контекста (summary)
    - Архивация старых сессий
    """
    
    def __init__(self, db_path: str = "trading.db"):
        """
        Инициализация менеджера сессий
        
        Args:
            db_path: Путь к БД (по умолчанию trading.db)
        """
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Проверяет наличие таблиц в БД (они должны быть созданы в db.py)"""
        # Таблицы создаются в Database._init_tables()
        # Здесь только проверяем, что они существуют
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_sessions'")
            if not cursor.fetchone():
                logger.warning("⚠️ [SESSION MANAGER] Таблица strategy_sessions не найдена. Таблицы должны быть созданы через Database._init_tables()")
            conn.close()
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка проверки таблиц: {e}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Получает соединение с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для доступа по имени колонок
        return conn
    
    def create_session(self, title: str, description: str = "") -> str:
        """
        Создает новую сессию стратегии
        
        Args:
            title: Название сессии
            description: Описание сессии
        
        Returns:
            str: session_id
        """
        session_id = str(uuid.uuid4())
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO strategy_sessions (id, title, description, status)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, title, description, "discovery")
            )
            conn.commit()
            conn.close()
            
            logger.info(f"✅ [SESSION MANAGER] Создана сессия: {session_id} ({title})")
            return session_id
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка создания сессии: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о сессии
        
        Args:
            session_id: ID сессии
        
        Returns:
            Dict или None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM strategy_sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка получения сессии: {e}")
            return None
    
    def update_session_status(self, session_id: str, status: str):
        """
        Обновляет статус сессии
        
        Args:
            session_id: ID сессии
            status: Новый статус (discovery/planning/decomposing/executing/done/archived)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE strategy_sessions
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, session_id)
            )
            conn.commit()
            conn.close()
            
            logger.debug(f"📝 [SESSION MANAGER] Обновлен статус сессии {session_id}: {status}")
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка обновления статуса: {e}")
            raise
    
    def add_question(self, session_id: str, role: str, question: str) -> str:
        """
        Добавляет вопрос к сессии
        
        Args:
            session_id: ID сессии
            role: Роль, которая задала вопрос (Павел/Мария/Максим/...)
            question: Текст вопроса
        
        Returns:
            str: question_id
        """
        question_id = str(uuid.uuid4())
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO strategy_questions (id, session_id, role, question_text)
                VALUES (?, ?, ?, ?)
                """,
                (question_id, session_id, role, question)
            )
            conn.commit()
            conn.close()
            
            logger.debug(f"❓ [SESSION MANAGER] Добавлен вопрос {question_id} к сессии {session_id}")
            return question_id
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка добавления вопроса: {e}")
            raise
    
    def answer_question(self, question_id: str, answer: str):
        """
        Записывает ответ на вопрос
        
        Args:
            question_id: ID вопроса
            answer: Текст ответа
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE strategy_questions
                SET answer_text = ?, answered_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (answer, question_id)
            )
            conn.commit()
            conn.close()
            
            logger.debug(f"✅ [SESSION MANAGER] Записан ответ на вопрос {question_id}")
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка записи ответа: {e}")
            raise
    
    def create_plan(
        self,
        session_id: str,
        level: str,
        title: str,
        markdown: str,
        role_hint: Optional[str] = None,
        parent_plan_id: Optional[str] = None
    ) -> str:
        """
        Создает план стратегии
        
        Args:
            session_id: ID сессии
            level: Уровень плана (master/sub/subsub)
            title: Название плана
            markdown: Содержимое плана в Markdown
            role_hint: Рекомендуемая роль для выполнения (Павел/Мария/...)
            parent_plan_id: ID родительского плана (для подпланов)
        
        Returns:
            str: plan_id
        """
        plan_id = str(uuid.uuid4())
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO strategy_plans (id, session_id, level, parent_plan_id, role_hint, title, markdown_body, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (plan_id, session_id, level, parent_plan_id, role_hint, title, markdown, "active")
            )
            conn.commit()
            conn.close()
            
            logger.info(f"📋 [SESSION MANAGER] Создан план {plan_id} для сессии {session_id}: {title} (level={level})")
            return plan_id
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка создания плана: {e}")
            raise
    
    def get_session_summary(self, session_id: str) -> str:
        """
        Получает краткий summary сессии для восстановления контекста
        
        Args:
            session_id: ID сессии
        
        Returns:
            str: Краткий summary сессии
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return ""
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Получаем вопросы и ответы
            cursor.execute(
                """
                SELECT role, question_text, answer_text
                FROM strategy_questions
                WHERE session_id = ?
                ORDER BY asked_at ASC
                """,
                (session_id,)
            )
            questions = cursor.fetchall()
            
            # Получаем планы
            cursor.execute(
                """
                SELECT level, title, status, role_hint
                FROM strategy_plans
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,)
            )
            plans = cursor.fetchall()
            
            conn.close()
            
            # Формируем summary
            summary_parts = [f"Сессия: {session['title']}", f"Статус: {session['status']}"]
            
            if questions:
                summary_parts.append("\nВопросы и ответы:")
                for q in questions[:5]:  # Максимум 5 вопросов
                    q_text = q['question_text'][:100] if len(q['question_text']) > 100 else q['question_text']
                    a_text = (q['answer_text'][:100] if q['answer_text'] and len(q['answer_text']) > 100 else q['answer_text']) or "Нет ответа"
                    summary_parts.append(f"- [{q['role']}] {q_text} → {a_text}")
            
            if plans:
                summary_parts.append("\nПланы:")
                for p in plans[:3]:  # Максимум 3 плана
                    summary_parts.append(f"- [{p['level']}] {p['title']} ({p['status']}, роль: {p['role_hint'] or 'не указана'})")
            
            summary = "\n".join(summary_parts)
            logger.debug(f"📋 [SESSION MANAGER] Сформирован summary сессии {session_id}: {len(summary)} символов")
            
            return summary
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка получения summary: {e}")
            return ""
    
    async def archive_old_sessions(self, days: int = 30):
        """
        Архивирует старые сессии (статус done, старше N дней)
        
        Args:
            days: Количество дней (по умолчанию 30)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE strategy_sessions
                SET status = 'archived', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'done'
                AND created_at < datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )
            archived_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if archived_count > 0:
                logger.info(f"📦 [SESSION MANAGER] Архивировано {archived_count} сессий (старше {days} дней)")
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка архивации сессий: {e}")

