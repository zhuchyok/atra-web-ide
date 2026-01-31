"""
Checklist Generator
Автоматическое создание чеклистов на основе опыта
AGENT IMPROVEMENTS: Автоматическое создание чеклистов
"""

import asyncio
import logging
import os
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

@dataclass
class Checklist:
    """Чеклист для задачи"""
    checklist_id: str
    task_type: str
    items: List[str]  # Пункты чеклиста
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0
    success_rate: float = 0.0  # Процент успешных выполнений с этим чеклистом

class ChecklistGenerator:
    """
    Система автоматического создания чеклистов.
    
    Функционал:
    - Генерация чеклистов для типовых задач
    - Обновление чеклистов на основе ошибок
    - Персонализация чеклистов для агентов
    - Автоматическая валидация выполнения
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._checklist_cache: Dict[str, Checklist] = {}
        
        # Дефолтные чеклисты для типовых задач
        self._default_checklists = {
            'code_review': [
                "Проверить синтаксис кода",
                "Проверить наличие тестов",
                "Проверить обработку ошибок",
                "Проверить логирование",
                "Проверить документацию"
            ],
            'bug_fix': [
                "Воспроизвести баг",
                "Определить корневую причину",
                "Написать тест для бага",
                "Исправить баг",
                "Проверить, что тест проходит",
                "Проверить, что другие тесты не сломались"
            ],
            'feature': [
                "Определить требования",
                "Спроектировать решение",
                "Реализовать функциональность",
                "Написать тесты",
                "Обновить документацию",
                "Провести code review"
            ],
            'deployment': [
                "Проверить окружение",
                "Проверить зависимости",
                "Запустить тесты",
                "Создать backup",
                "Выполнить деплой",
                "Проверить работоспособность"
            ]
        }
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [CHECKLIST GENERATOR] Ошибка подключения к БД: {e}")
            return None
    
    async def generate_checklist(
        self,
        task_type: str,
        based_on_errors: bool = False
    ) -> Optional[Checklist]:
        """
        Генерирует чеклист для типа задачи.
        
        Args:
            task_type: Тип задачи ('code_review', 'bug_fix', 'feature', etc.)
            based_on_errors: Использовать ошибки из истории для генерации
        
        Returns:
            Checklist или None
        """
        try:
            # Проверяем кэш
            cache_key = f"{task_type}:{'errors' if based_on_errors else 'default'}"
            if cache_key in self._checklist_cache:
                return self._checklist_cache[cache_key]
            
            items = []
            
            # Начинаем с дефолтного чеклиста
            if task_type in self._default_checklists:
                items = self._default_checklists[task_type].copy()
            
            # Если нужно на основе ошибок, анализируем историю
            if based_on_errors:
                error_based_items = await self._extract_items_from_errors(task_type)
                # Объединяем дефолтные и основанные на ошибках
                for item in error_based_items:
                    if item not in items:
                        items.append(item)
            
            if not items:
                logger.warning(f"⚠️ [CHECKLIST GENERATOR] Нет чеклиста для типа {task_type}")
                return None
            
            # Генерируем checklist_id
            import hashlib
            checklist_key = f"{task_type}:{':'.join(items)}"
            checklist_id = hashlib.md5(checklist_key.encode()).hexdigest()[:16]
            
            checklist = Checklist(
                checklist_id=checklist_id,
                task_type=task_type,
                items=items,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if conn:
                try:
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'agent_checklists'
                        )
                    """)
                    
                    if table_exists:
                        await conn.execute("""
                            INSERT INTO agent_checklists (checklist_id, task_type, items, created_at, updated_at, usage_count, success_rate)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT (checklist_id) DO UPDATE
                            SET items = EXCLUDED.items, updated_at = EXCLUDED.updated_at
                        """, checklist_id, task_type, json.dumps(items), checklist.created_at, checklist.updated_at, 0, 0.0)
                    
                    self._checklist_cache[checklist_id] = checklist
                    
                    logger.info(f"✅ [CHECKLIST GENERATOR] Создан чеклист {checklist_id} для {task_type} ({len(items)} пунктов)")
                    return checklist
                    
                finally:
                    await conn.close()
            
            return checklist
            
        except Exception as e:
            logger.error(f"❌ [CHECKLIST GENERATOR] Ошибка генерации чеклиста: {e}")
            return None
    
    async def _extract_items_from_errors(self, task_type: str) -> List[str]:
        """
        Извлекает пункты чеклиста на основе частых ошибок.
        
        Args:
            task_type: Тип задачи
        
        Returns:
            Список пунктов чеклиста
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return []
            
            try:
                # Получаем частые ошибки для типа задачи
                error_rows = await conn.fetch("""
                    SELECT error_message, COUNT(*) as count
                    FROM agent_tasks
                    WHERE task_type = $1
                    AND status = 'failed'
                    AND error_message IS NOT NULL
                    AND created_at > NOW() - INTERVAL '30 days'
                    GROUP BY error_message
                    ORDER BY count DESC
                    LIMIT 5
                """, task_type)
                
                items = []
                for row in error_rows:
                    error_msg = row['error_message']
                    # Генерируем пункт чеклиста на основе ошибки
                    if 'syntax' in error_msg.lower():
                        items.append("Проверить синтаксис кода перед выполнением")
                    elif 'import' in error_msg.lower():
                        items.append("Проверить наличие всех необходимых импортов")
                    elif 'permission' in error_msg.lower() or 'access' in error_msg.lower():
                        items.append("Проверить права доступа и разрешения")
                    elif 'timeout' in error_msg.lower():
                        items.append("Проверить таймауты и производительность")
                    elif 'not found' in error_msg.lower():
                        items.append("Проверить существование всех зависимостей")
                    else:
                        items.append(f"Предотвратить ошибку: {error_msg[:50]}...")
                
                return items
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.debug(f"⚠️ [CHECKLIST GENERATOR] Ошибка извлечения из ошибок: {e}")
            return []
    
    async def get_checklist_for_task(self, task_type: str) -> Optional[Checklist]:
        """
        Получает чеклист для типа задачи.
        
        Args:
            task_type: Тип задачи
        
        Returns:
            Checklist или None
        """
        # Сначала пробуем загрузить из БД
        conn = await self._get_conn()
        if conn:
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'agent_checklists'
                    )
                """)
                
                if table_exists:
                    row = await conn.fetchrow("""
                        SELECT checklist_id, task_type, items, usage_count, success_rate
                        FROM agent_checklists
                        WHERE task_type = $1
                        ORDER BY success_rate DESC, usage_count DESC
                        LIMIT 1
                    """, task_type)
                    
                    if row:
                        checklist = Checklist(
                            checklist_id=row['checklist_id'],
                            task_type=row['task_type'],
                            items=json.loads(row['items']) if isinstance(row['items'], str) else row['items'],
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                            usage_count=row['usage_count'] or 0,
                            success_rate=float(row['success_rate'] or 0)
                        )
                        self._checklist_cache[checklist.checklist_id] = checklist
                        return checklist
            finally:
                await conn.close()
        
        # Если нет в БД, генерируем новый
        return await self.generate_checklist(task_type, based_on_errors=True)
    
    async def update_checklist_from_errors(self, checklist_id: str) -> bool:
        """
        Обновляет чеклист на основе новых ошибок.
        
        Args:
            checklist_id: ID чеклиста
        
        Returns:
            True если обновление успешно
        """
        try:
            checklist = self._checklist_cache.get(checklist_id)
            if not checklist:
                return False
            
            # Извлекаем новые пункты из ошибок
            new_items = await self._extract_items_from_errors(checklist.task_type)
            
            # Добавляем новые пункты, которых еще нет
            for item in new_items:
                if item not in checklist.items:
                    checklist.items.append(item)
            
            checklist.updated_at = datetime.now(timezone.utc)
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if conn:
                try:
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'agent_checklists'
                        )
                    """)
                    
                    if table_exists:
                        await conn.execute("""
                            UPDATE agent_checklists
                            SET items = $1, updated_at = $2
                            WHERE checklist_id = $3
                        """, json.dumps(checklist.items), checklist.updated_at, checklist_id)
                    
                    logger.info(f"✅ [CHECKLIST GENERATOR] Чеклист {checklist_id} обновлен ({len(checklist.items)} пунктов)")
                    return True
                    
                finally:
                    await conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [CHECKLIST GENERATOR] Ошибка обновления чеклиста: {e}")
            return False

# Singleton instance
_checklist_generator_instance: Optional[ChecklistGenerator] = None

def get_checklist_generator(db_url: str = DB_URL) -> ChecklistGenerator:
    """Получить singleton экземпляр ChecklistGenerator"""
    global _checklist_generator_instance
    if _checklist_generator_instance is None:
        _checklist_generator_instance = ChecklistGenerator(db_url=db_url)
    return _checklist_generator_instance

