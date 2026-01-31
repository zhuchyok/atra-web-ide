"""
Strategy Discovery - Discovery фаза для торговых стратегий
Концепция из agent.md: диалог для уточнения требований до плана
"""

import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from strategy_session_manager import StrategySessionManager
except ImportError:
    StrategySessionManager = None

try:
    from query_orchestrator import QueryOrchestrator
except ImportError:
    QueryOrchestrator = None


class StrategyDiscovery:
    """
    Discovery фаза для торговых стратегий
    
    Функции:
    - Диалог с пользователем для уточнения требований (без плана)
    - Сбор ограничений (депозит, плечо, фильтры)
    - Уточнение приоритетов (быстрая прибыль vs стабильность)
    - Проверка готовности к планированию
    - Генерация summary для MASTER_PLAN
    """
    
    # Обязательные темы для Discovery фазы
    REQUIRED_TOPICS = [
        "цели",  # Доходность, время удержания, рынки
        "ограничения",  # Депозит, плечо, фильтры
        "риски",  # Максимальный риск, drawdown
        "приоритеты",  # Быстрая прибыль vs стабильность
    ]
    
    # Ключевые слова для определения закрытых тем
    TOPIC_KEYWORDS = {
        "цели": ["доходность", "прибыль", "время удержания", "рынки", "символы", "таймфрейм"],
        "ограничения": ["депозит", "баланс", "плечо", "leverage", "фильтр", "filter"],
        "риски": ["риск", "risk", "просадка", "drawdown", "stop loss", "take profit"],
        "приоритеты": ["приоритет", "прибыль vs стабильность", "быстрая прибыль", "долгосрочная"],
    }
    
    def __init__(self, session_manager: Optional[StrategySessionManager] = None, query_orch: Optional[QueryOrchestrator] = None):
        """
        Инициализация Discovery фазы
        
        Args:
            session_manager: Менеджер сессий (опционально)
            query_orch: Query Orchestrator (опционально)
        """
        self.session_manager = session_manager
        self.query_orch = query_orch or (QueryOrchestrator(session_manager) if QueryOrchestrator else None)
    
    async def start_discovery(self, session_id: str, user_query: str) -> List[str]:
        """
        Запускает Discovery фазу: генерирует первые вопросы
        
        Args:
            session_id: ID сессии
            user_query: Исходный запрос пользователя
        
        Returns:
            List[str]: Список question_ids
        """
        if not self.session_manager:
            logger.warning("⚠️ [DISCOVERY] SessionManager не доступен, пропускаем Discovery фазу")
            return []
        
        try:
            # Обновляем статус сессии
            self.session_manager.update_session_status(session_id, "discovery")
            
            # Используем Query Orchestrator для нормализации запроса
            if self.query_orch:
                normalized_query = self.query_orch.normalize_query(user_query)
                role = self.query_orch.select_role(normalized_query.query_type)
            else:
                role = "Виктория"  # Fallback на Team Lead
            
            # Генерируем вопросы через LLM (через Query Orchestrator)
            # Для начала используем базовый список вопросов
            questions = self._generate_initial_questions(user_query, role)
            
            # Сохраняем вопросы в БД
            question_ids = []
            for question_text in questions:
                question_id = self.session_manager.add_question(session_id, role, question_text)
                question_ids.append(question_id)
            
            logger.info(f"❓ [DISCOVERY] Начата Discovery фаза для сессии {session_id}: создано {len(question_ids)} вопросов")
            
            return question_ids
        except Exception as e:
            logger.error(f"❌ [DISCOVERY] Ошибка запуска Discovery фазы: {e}")
            return []
    
    def _generate_initial_questions(self, user_query: str, role: str) -> List[str]:
        """
        Генерирует начальные вопросы на основе запроса пользователя
        
        Args:
            user_query: Запрос пользователя
            role: Роль эксперта
        
        Returns:
            List[str]: Список вопросов
        """
        questions = []
        query_lower = user_query.lower()
        
        # Проверяем, какие темы не покрыты
        covered_topics = []
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                covered_topics.append(topic)
        
        # Генерируем вопросы для непокрытых тем
        if "цели" not in covered_topics:
            questions.append("Какова целевая доходность стратегии? Какой временной горизонт (краткосрочная/долгосрочная)?")
        
        if "ограничения" not in covered_topics:
            questions.append("Каков размер депозита? Какое плечо планируете использовать? Какие фильтры важны (strict/soft)?")
        
        if "риски" not in covered_topics:
            questions.append("Какой максимальный риск на сделку? Какой максимальный drawdown допустим?")
        
        if "приоритеты" not in covered_topics:
            questions.append("Что важнее: быстрая прибыль или стабильность? Какой приоритет: количество сделок или качество?")
        
        # Если все темы покрыты, задаем уточняющий вопрос
        if not questions:
            questions.append("Есть ли еще важные детали или требования к стратегии?")
        
        return questions
    
    async def process_answer(self, session_id: str, question_id: str, answer: str) -> Optional[List[str]]:
        """
        Обрабатывает ответ пользователя: сохраняет ответ и генерирует новые вопросы (если нужно)
        
        Args:
            session_id: ID сессии
            question_id: ID вопроса
            answer: Ответ пользователя
        
        Returns:
            Optional[List[str]]: Новые question_ids (если нужно уточнение), или None
        """
        if not self.session_manager:
            return None
        
        try:
            # Сохраняем ответ
            self.session_manager.answer_question(question_id, answer)
            
            # Проверяем, нужно ли задать дополнительные вопросы
            # TODO: Использовать LLM для анализа ответа и генерации новых вопросов
            
            logger.debug(f"✅ [DISCOVERY] Обработан ответ на вопрос {question_id} в сессии {session_id}")
            
            return None  # Пока не генерируем автоматически новые вопросы
        except Exception as e:
            logger.error(f"❌ [DISCOVERY] Ошибка обработки ответа: {e}")
            return None
    
    def is_ready_for_planning(self, session_id: str) -> bool:
        """
        Проверяет, готова ли сессия к планированию (все вопросы закрыты)
        
        Args:
            session_id: ID сессии
        
        Returns:
            bool: True если готово к планированию
        """
        if not self.session_manager:
            return True  # Если нет менеджера сессий, считаем готовым
        
        try:
            conn = self.session_manager._get_connection()
            cursor = conn.cursor()
            
            # Проверяем, есть ли вопросы без ответов
            cursor.execute(
                """
                SELECT COUNT(*) as unanswered
                FROM strategy_questions
                WHERE session_id = ? AND answer_text IS NULL
                """,
                (session_id,)
            )
            row = cursor.fetchone()
            unanswered = row['unanswered'] if row else 0
            conn.close()
            
            is_ready = unanswered == 0
            logger.debug(f"📋 [DISCOVERY] Сессия {session_id} готова к планированию: {is_ready} (неотвеченных: {unanswered})")
            
            return is_ready
        except Exception as e:
            logger.error(f"❌ [DISCOVERY] Ошибка проверки готовности: {e}")
            return True  # В случае ошибки считаем готовым
    
    def get_discovery_summary(self, session_id: str) -> str:
        """
        Получает краткую сводку Discovery фазы для MASTER_PLAN
        
        Args:
            session_id: ID сессии
        
        Returns:
            str: Краткая сводка Discovery фазы
        """
        if not self.session_manager:
            return ""
        
        try:
            conn = self.session_manager._get_connection()
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
            qa_pairs = cursor.fetchall()
            conn.close()
            
            # Формируем сводку
            summary_parts = ["Discovery фаза - собранные требования:"]
            
            for qa in qa_pairs:
                if qa['answer_text']:
                    summary_parts.append(f"- {qa['question_text']} → {qa['answer_text']}")
            
            summary = "\n".join(summary_parts)
            logger.debug(f"📋 [DISCOVERY] Сформирован summary для сессии {session_id}: {len(summary)} символов")
            
            return summary
        except Exception as e:
            logger.error(f"❌ [DISCOVERY] Ошибка получения summary: {e}")
            return ""

