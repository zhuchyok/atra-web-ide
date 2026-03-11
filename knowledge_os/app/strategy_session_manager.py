"""
Strategy Session Manager - управление сессиями стратегий
Концепция из agent.md: сессионная модель для сохранения контекста между сессиями
"""

import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

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
        """Проверяет наличие таблиц в БД и инициализирует их при необходимости"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_sessions'"
            )
            if not cursor.fetchone():
                logger.info("🔧 [SESSION MANAGER] Таблица strategy_sessions не найдена. Инициализация...")
                    try:
                        from db import Database
                    except ImportError:
                        try:
                            import sys
                            import os
                            # Добавляем пути для поиска db.py (Knowledge OS структура)
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            project_root = os.path.dirname(os.path.dirname(current_dir)) # atra-web-ide
                            
                            paths_to_add = [
                                os.path.join(current_dir, "src/database"),
                                os.path.join(os.path.dirname(current_dir), "src/database"),
                                os.path.join(project_root, "knowledge_os/src/database"),
                                os.path.join(project_root, "src/database"),
                                "/app/knowledge_os/src/database",
                                "/app/src/database",
                            ]
                            
                            for p in paths_to_add:
                                if os.path.exists(p) and p not in sys.path:
                                    sys.path.insert(0, p)
                            
                            from db import Database
                        except ImportError:
                            try:
                                from src.database.db import Database
                            except ImportError:
                                try:
                                    from knowledge_os.src.database.db import Database
                                except ImportError:
                                    # Последний шанс: пробуем импортировать через абсолютный путь в контейнере
                                    import importlib.util
                                    db_path_abs = "/app/knowledge_os/src/database/db.py"
                                    if os.path.exists(db_path_abs):
                                        spec = importlib.util.spec_from_file_location("db", db_path_abs)
                                        module = importlib.util.module_from_spec(spec)
                                        spec.loader.exec_module(module)
                                        Database = module.Database
                                    else:
                                        raise ImportError("Could not find db.py in any known location")
                    
                    db = Database(self.db_path)
                    db._init_tables()
                    logger.info("✅ [SESSION MANAGER] Таблицы стратегий инициализированы")
                except Exception as e2:
                    logger.error(f"❌ [SESSION MANAGER] Не удалось инициализировать таблицы: {e2}")
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
                (session_id, title, description, "discovery"),
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
            cursor.execute("SELECT * FROM strategy_sessions WHERE id = ?", (session_id,))
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
                (status, session_id),
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
                (question_id, session_id, role, question),
            )
            conn.commit()
            conn.close()

            logger.debug(
                f"❓ [SESSION MANAGER] Добавлен вопрос {question_id} к сессии {session_id}"
            )
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
                (answer, question_id),
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
        parent_plan_id: Optional[str] = None,
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
                (plan_id, session_id, level, parent_plan_id, role_hint, title, markdown, "active"),
            )
            conn.commit()
            conn.close()

            logger.info(
                f"📋 [SESSION MANAGER] Создан план {plan_id} для сессии {session_id}: {title} (level={level})"
            )
            return plan_id
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка создания плана: {e}")
            raise

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает план по id.

        Returns:
            Dict с ключами id, session_id, level, title, markdown_body, role_hint, status и т.д. или None.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, session_id, level, parent_plan_id, role_hint, title, markdown_body, status FROM strategy_plans WHERE id = ?",
                (plan_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return dict(row)
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка получения плана: {e}")
            return None

    def update_plan(
        self,
        plan_id: str,
        *,
        markdown: Optional[str] = None,
        title: Optional[str] = None,
        status: Optional[str] = None,
        role_hint: Optional[str] = None,
    ) -> bool:
        """
        Обновляет поля плана. Передавать только те поля, которые нужно изменить.

        Returns:
            True если план найден и обновлён, иначе False.
        """
        if not any(x is not None for x in (markdown, title, status, role_hint)):
            return False
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            updates = []
            params = []
            if markdown is not None:
                updates.append("markdown_body = ?")
                params.append(markdown)
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if role_hint is not None:
                updates.append("role_hint = ?")
                params.append(role_hint)
            params.append(plan_id)
            cursor.execute(
                "UPDATE strategy_plans SET " + ", ".join(updates) + " WHERE id = ?",
                params,
            )
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            if affected:
                logger.info(f"📋 [SESSION MANAGER] План {plan_id} обновлён")
            return affected > 0
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка обновления плана: {e}")
            return False

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
                (session_id,),
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
                (session_id,),
            )
            plans = cursor.fetchall()

            conn.close()

            # Формируем summary
            summary_parts = [f"Сессия: {session['title']}", f"Статус: {session['status']}"]

            if questions:
                summary_parts.append("\nВопросы и ответы:")
                for q in questions[:5]:  # Максимум 5 вопросов
                    q_text = (
                        q["question_text"][:100]
                        if len(q["question_text"]) > 100
                        else q["question_text"]
                    )
                    a_text = (
                        q["answer_text"][:100]
                        if q["answer_text"] and len(q["answer_text"]) > 100
                        else q["answer_text"]
                    ) or "Нет ответа"
                    summary_parts.append(f"- [{q['role']}] {q_text} → {a_text}")

            if plans:
                summary_parts.append("\nПланы:")
                for p in plans[:3]:  # Максимум 3 плана
                    summary_parts.append(
                        f"- [{p['level']}] {p['title']} ({p['status']}, роль: {p['role_hint'] or 'не указана'})"
                    )

            summary = "\n".join(summary_parts)
            logger.debug(
                f"📋 [SESSION MANAGER] Сформирован summary сессии {session_id}: {len(summary)} символов"
            )

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
                (days,),
            )
            archived_count = cursor.rowcount
            conn.commit()
            conn.close()

            if archived_count > 0:
                logger.info(
                    f"📦 [SESSION MANAGER] Архивировано {archived_count} сессий (старше {days} дней)"
                )
        except Exception as e:
            logger.error(f"❌ [SESSION MANAGER] Ошибка архивации сессий: {e}")
