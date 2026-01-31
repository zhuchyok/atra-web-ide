#!/usr/bin/env python3
"""
[KNOWLEDGE OS] Expert Aliases Module

Централизованный модуль для работы с алиасами экспертов.
Заменяет жёстко закодированные списки на динамическую загрузку из БД.

Использование:
    from expert_aliases import ExpertAliasManager
    
    manager = ExpertAliasManager()
    await manager.load_aliases()
    
    expert_name = manager.resolve_alias('вика')  # -> 'Виктория'
    all_experts = manager.get_all_expert_names()

При обнаружении хардкодов экспертов в коде — используйте этот модуль!
"""

import asyncio
import getpass
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

logger = logging.getLogger(__name__)

# Конфигурация БД
USER_NAME = getpass.getuser()
DEFAULT_DB_URL = os.getenv('DATABASE_URL') or 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)


# =============================================================================
# FALLBACK КОНФИГУРАЦИЯ (используется ТОЛЬКО при недоступности БД)
# ВАЖНО: Этот список может быть неполным!
# =============================================================================
FALLBACK_ALIASES: Dict[str, str] = {
    'виктория': 'Виктория',
    'вика': 'Виктория',
    'владимир': 'Владимир',
    'вова': 'Владимир',
    'дмитрий': 'Дмитрий',
    'дима': 'Дмитрий',
    'мария': 'Мария',
    'маша': 'Мария',
    'максим': 'Максим',
    'макс': 'Максим',
}

# Стандартные сокращения имён
STANDARD_DIMINUTIVES: Dict[str, List[str]] = {
    'Виктория': ['вика', 'викуся', 'викторияа'],
    'Владимир': ['вова', 'володя', 'влад'],
    'Дмитрий': ['дима', 'димон', 'митя'],
    'Мария': ['маша', 'маруся', 'машенька'],
    'Максим': ['макс', 'максик'],
    'Сергей': ['серёжа', 'серж', 'сергейя'],
    'Елена': ['лена', 'леночка'],
    'Анна': ['аня', 'анечка', 'нюра'],
    'Алексей': ['лёша', 'алёша', 'лёха'],
    'Павел': ['паша', 'пашка'],
    'Игорь': ['игорёк', 'гоша'],
    'Роман': ['рома', 'ромка'],
    'Ольга': ['оля', 'олечка'],
    'Татьяна': ['таня', 'танюша'],
    'Екатерина': ['катя', 'катерина', 'катюша'],
    'Андрей': ['андрюша', 'андрейка'],
    'Никита': ['никитос', 'ник'],
    'Дарья': ['даша', 'дашенька'],
    'Юлия': ['юля', 'юлечка'],
    'Артём': ['тёма', 'артёмка'],
    'Глеб': ['глебушка'],
}


@dataclass
class ExpertInfo:
    """Информация об эксперте."""
    name: str
    role: str
    department: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Генерирует стандартные алиасы."""
        if not self.aliases:
            self.aliases = [self.name.lower()]
            if self.name in STANDARD_DIMINUTIVES:
                self.aliases.extend(STANDARD_DIMINUTIVES[self.name])


class ExpertAliasManager:
    """
    Менеджер алиасов экспертов.
    
    Загружает список экспертов из БД и создаёт маппинг алиасов.
    Кэширует данные для производительности.
    """
    
    def __init__(self, db_url: str = DB_URL, cache_ttl_minutes: int = 30):
        self.db_url = db_url
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._aliases: Dict[str, str] = {}  # alias -> expert_name
        self._experts: Dict[str, ExpertInfo] = {}  # name -> ExpertInfo
        self._last_load: Optional[datetime] = None
        self._using_fallback: bool = False
    
    @property
    def is_cache_valid(self) -> bool:
        """Проверяет актуальность кэша."""
        if self._last_load is None:
            return False
        return datetime.now() - self._last_load < self.cache_ttl
    
    async def load_aliases(self, force: bool = False) -> bool:
        """
        Загружает алиасы экспертов из БД.
        
        Args:
            force: Принудительная перезагрузка даже если кэш актуален
            
        Returns:
            True если загрузка успешна, False если используется fallback
        """
        if not force and self.is_cache_valid:
            return not self._using_fallback
        
        if not ASYNCPG_AVAILABLE:
            logger.debug("ℹ️ asyncpg недоступен, используется fallback")
            self._load_fallback()
            return False
        
        try:
            conn = await asyncpg.connect(self.db_url)
            rows = await conn.fetch(
                "SELECT name, role, department FROM experts ORDER BY name"
            )
            await conn.close()
            
            if not rows:
                logger.warning("Таблица experts пуста, используется fallback")
                self._load_fallback()
                return False
            
            # Очищаем и заполняем
            self._aliases.clear()
            self._experts.clear()
            
            for row in rows:
                expert = ExpertInfo(
                    name=row['name'],
                    role=row['role'],
                    department=row['department']
                )
                self._experts[expert.name] = expert
                
                # Добавляем все алиасы
                for alias in expert.aliases:
                    self._aliases[alias.lower()] = expert.name
            
            self._last_load = datetime.now()
            self._using_fallback = False
            
            logger.info(
                "Загружено %d экспертов, %d алиасов из БД",
                len(self._experts), len(self._aliases)
            )
            return True
            
        except Exception as exc:
            logger.error("Ошибка загрузки экспертов из БД: %s", exc)
            self._load_fallback()
            return False
    
    def _load_fallback(self):
        """Загружает fallback-данные."""
        self._aliases = FALLBACK_ALIASES.copy()
        self._experts.clear()
        self._last_load = datetime.now()
        self._using_fallback = True
        logger.warning(
            "⚠️ Используется FALLBACK список экспертов! "
            "Список может быть неполным. "
            "Проверьте: python scripts/quick_validate_experts.py"
        )
    
    def resolve_alias(self, text: str) -> Optional[str]:
        """
        Определяет имя эксперта по алиасу/началу сообщения.
        
        Args:
            text: Текст для анализа (обычно начало сообщения)
            
        Returns:
            Имя эксперта или None если не найден
        """
        text_lower = text.lower().strip()
        
        # Точное совпадение алиаса
        if text_lower in self._aliases:
            return self._aliases[text_lower]
        
        # Проверяем, начинается ли текст с алиаса
        for alias, name in sorted(self._aliases.items(), key=lambda x: -len(x[0])):
            if text_lower.startswith(alias):
                return name
        
        return None
    
    def extract_expert_and_message(
        self, 
        text: str
    ) -> Tuple[Optional[str], str]:
        """
        Извлекает имя эксперта и очищенное сообщение.
        
        Args:
            text: Полный текст сообщения
            
        Returns:
            Tuple[имя_эксперта_или_None, очищенный_текст]
        """
        text_stripped = text.strip()
        text_lower = text_stripped.lower()
        
        # Ищем совпадение с алиасами
        for alias, name in sorted(self._aliases.items(), key=lambda x: -len(x[0])):
            if text_lower.startswith(alias):
                # Убираем алиас из текста
                remaining = text_stripped[len(alias):].lstrip(', ').strip()
                return name, remaining
        
        return None, text_stripped
    
    def get_all_expert_names(self) -> List[str]:
        """Возвращает список всех имён экспертов."""
        return list(self._experts.keys()) if self._experts else list(set(self._aliases.values()))
    
    def get_expert_info(self, name: str) -> Optional[ExpertInfo]:
        """Получает информацию об эксперте по имени."""
        return self._experts.get(name)
    
    def get_aliases_for_expert(self, name: str) -> List[str]:
        """Возвращает все алиасы для эксперта."""
        return [alias for alias, n in self._aliases.items() if n == name]
    
    @property
    def using_fallback(self) -> bool:
        """Возвращает True если используется fallback."""
        return self._using_fallback


# =============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР (Singleton pattern)
# =============================================================================
_manager_instance: Optional[ExpertAliasManager] = None


async def get_alias_manager() -> ExpertAliasManager:
    """
    Получает глобальный экземпляр ExpertAliasManager.
    Автоматически загружает данные при первом вызове.
    """
    global _manager_instance
    
    if _manager_instance is None:
        _manager_instance = ExpertAliasManager()
    
    if not _manager_instance.is_cache_valid:
        await _manager_instance.load_aliases()
    
    return _manager_instance


async def resolve_expert_name(text: str) -> Optional[str]:
    """
    Быстрая функция для определения эксперта по тексту.
    
    Пример:
        expert = await resolve_expert_name('вика, привет!')
        # expert = 'Виктория'
    """
    manager = await get_alias_manager()
    return manager.resolve_alias(text)


async def extract_expert_from_message(
    text: str, 
    default_expert: str = 'Виктория'
) -> Tuple[str, str]:
    """
    Извлекает эксперта из сообщения с fallback на дефолтного.
    
    Пример:
        expert, msg = await extract_expert_from_message('дима, помоги с кодом')
        # expert = 'Дмитрий', msg = 'помоги с кодом'
        
        expert, msg = await extract_expert_from_message('просто текст')
        # expert = 'Виктория', msg = 'просто текст'
    """
    manager = await get_alias_manager()
    expert, message = manager.extract_expert_and_message(text)
    
    if expert is None:
        expert = default_expert
    
    return expert, message


# =============================================================================
# CLI для тестирования
# =============================================================================
if __name__ == '__main__':
    async def test():
        print("=" * 60)
        print("🔍 ТЕСТ ExpertAliasManager")
        print("=" * 60)
        
        manager = await get_alias_manager()
        
        print(f"\n📊 Статус: {'FALLBACK' if manager.using_fallback else 'DB'}")
        print(f"📋 Эксперты: {manager.get_all_expert_names()}")
        print(f"🔗 Алиасов: {len(manager._aliases)}")
        
        # Тестовые случаи
        test_cases = [
            'виктория, привет',
            'вика помоги',
            'Дима, как дела?',
            'просто текст без эксперта',
            'Макс, напиши код',
        ]
        
        print("\n" + "=" * 60)
        print("🧪 ТЕСТОВЫЕ СЛУЧАИ:")
        print("=" * 60)
        
        for case in test_cases:
            expert, msg = await extract_expert_from_message(case)
            print(f"\n   Вход: '{case}'")
            print(f"   Эксперт: {expert}")
            print(f"   Сообщение: '{msg}'")
    
    asyncio.run(test())
