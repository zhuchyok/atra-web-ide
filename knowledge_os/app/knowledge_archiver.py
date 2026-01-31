"""
Knowledge Archiver - автоматическая архивация знаний
Концепция из agent.md: архивация старых сессий/планов, сжатие в summary
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from strategy_session_manager import StrategySessionManager
except ImportError:
    StrategySessionManager = None

try:
    from ai_core import run_smart_agent_async
except ImportError:
    run_smart_agent_async = None


class KnowledgeArchiver:
    """
    Архиватор знаний для автоматической очистки и архивации
    
    Функции:
    - Архивирование старых сессий
    - Архивирование завершённых планов
    - Архивирование устаревших планов
    - Сжатие детальных планов в summary
    """
    
    def __init__(self, session_manager: Optional[StrategySessionManager] = None):
        """
        Инициализация архиватора
        
        Args:
            session_manager: Strategy Session Manager (опционально)
        """
        self.session_manager = session_manager or (
            StrategySessionManager() if StrategySessionManager else None
        )
    
    async def archive_old_sessions(self, days: int = 30) -> int:
        """
        Архивирует старые сессии (статус done, старше N дней)
        
        Args:
            days: Количество дней (по умолчанию 30)
        
        Returns:
            int: Количество архивированных сессий
        """
        if not self.session_manager:
            return 0
        
        try:
            # Используем метод из StrategySessionManager
            await self.session_manager.archive_old_sessions(days)
            
            # Получаем количество архивированных
            conn = self.session_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM strategy_sessions
                WHERE status = 'archived'
                AND updated_at >= datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )
            row = cursor.fetchone()
            archived_count = row['count'] if row else 0
            conn.close()
            
            logger.info(f"📦 [ARCHIVER] Архивировано {archived_count} сессий (старше {days} дней)")
            return archived_count
        except Exception as e:
            logger.error(f"❌ [ARCHIVER] Ошибка архивации сессий: {e}")
            return 0
    
    async def archive_completed_plans(self, days: int = 7) -> int:
        """
        Архивирует завершённые планы (статус completed, старше N дней)
        
        Args:
            days: Количество дней (по умолчанию 7)
        
        Returns:
            int: Количество архивированных планов
        """
        if not self.session_manager:
            return 0
        
        try:
            conn = self.session_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE strategy_plans
                SET status = 'archived', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'completed'
                AND created_at < datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )
            archived_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if archived_count > 0:
                logger.info(f"📦 [ARCHIVER] Архивировано {archived_count} завершённых планов (старше {days} дней)")
            
            return archived_count
        except Exception as e:
            logger.error(f"❌ [ARCHIVER] Ошибка архивации планов: {e}")
            return 0
    
    async def archive_obsolete_plans(self) -> int:
        """
        Архивирует устаревшие планы (статус obsolete)
        
        Returns:
            int: Количество архивированных планов
        """
        if not self.session_manager:
            return 0
        
        try:
            conn = self.session_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE strategy_plans
                SET status = 'archived', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'obsolete'
                """
            )
            archived_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if archived_count > 0:
                logger.info(f"📦 [ARCHIVER] Архивировано {archived_count} устаревших планов")
            
            return archived_count
        except Exception as e:
            logger.error(f"❌ [ARCHIVER] Ошибка архивации устаревших планов: {e}")
            return 0
    
    async def summarize_session(self, session_id: str) -> str:
        """
        Создаёт краткий summary сессии для хранения
        
        Args:
            session_id: ID сессии
        
        Returns:
            str: Краткий summary
        """
        if not self.session_manager:
            return ""
        
        try:
            # Получаем summary через SessionManager
            summary = self.session_manager.get_session_summary(session_id)
            
            # Если summary слишком длинный, сжимаем через LLM
            if len(summary) > 500 and run_smart_agent_async:
                try:
                    compression_prompt = f"""Создай краткий summary (максимум 200 слов) этой сессии стратегии:

{summary}

Формат: Краткое описание цели, ключевых решений и результатов."""
                    
                    compressed_summary = await run_smart_agent_async(
                        compression_prompt,
                        expert_name="Виктория",
                        category="fast"
                    )
                    
                    if compressed_summary and len(compressed_summary) < len(summary):
                        summary = compressed_summary
                        logger.debug(f"📉 [ARCHIVER] Summary сжат с {len(summary)} до {len(compressed_summary)} символов")
                except Exception as e:
                    logger.debug(f"⚠️ [ARCHIVER] Ошибка сжатия summary: {e}")
            
            return summary
        except Exception as e:
            logger.error(f"❌ [ARCHIVER] Ошибка создания summary: {e}")
            return ""
    
    async def compress_old_plans(self, plan_ids: List[str]) -> Dict[str, str]:
        """
        Сжимает старые планы в summary
        
        Args:
            plan_ids: Список ID планов
        
        Returns:
            Dict[str, str]: plan_id -> summary
        """
        if not self.session_manager:
            return {}
        
        compressed = {}
        
        for plan_id in plan_ids:
            try:
                conn = self.session_manager._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT markdown_body FROM strategy_plans WHERE id = ?",
                    (plan_id,)
                )
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    markdown = row['markdown_body']
                    
                    # Если план длинный, сжимаем
                    if len(markdown) > 1000 and run_smart_agent_async:
                        try:
                            compression_prompt = f"""Создай краткий summary (максимум 100 слов) этого плана стратегии:

{markdown[:2000]}

Формат: Краткое описание основных разделов и задач."""
                            
                            summary = await run_smart_agent_async(
                                compression_prompt,
                                expert_name="Виктория",
                                category="fast"
                            )
                            
                            if summary:
                                compressed[plan_id] = summary
                        except Exception as e:
                            logger.debug(f"⚠️ [ARCHIVER] Ошибка сжатия плана {plan_id}: {e}")
                            compressed[plan_id] = markdown[:200] + "..."
                    else:
                        compressed[plan_id] = markdown
            except Exception as e:
                logger.debug(f"⚠️ [ARCHIVER] Ошибка обработки плана {plan_id}: {e}")
        
        logger.info(f"📦 [ARCHIVER] Сжато {len(compressed)} планов")
        
        return compressed
    
    async def periodic_archive_task(self):
        """
        Периодическая задача архивации (запускается раз в день)
        """
        logger.info("📦 [ARCHIVER] Запуск периодической архивации...")
        
        try:
            # Архивируем старые сессии (30 дней)
            await self.archive_old_sessions(days=30)
            
            # Архивируем завершённые планы (7 дней)
            await self.archive_completed_plans(days=7)
            
            # Архивируем устаревшие планы
            await self.archive_obsolete_plans()
            
            logger.info("✅ [ARCHIVER] Периодическая архивация завершена")
        except Exception as e:
            logger.error(f"❌ [ARCHIVER] Ошибка периодической архивации: {e}")

