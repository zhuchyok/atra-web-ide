"""
Skill Loader - Динамическая загрузка и валидация skills
Основано на Clawdbot: SKILL.md парсинг, Skills Watcher для auto-refresh
Поддерживает hot-reload skills без перезапуска
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable
from datetime import datetime, timezone

# Опциональный импорт watchdog для hot-reload
logger = logging.getLogger(__name__)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None
    FileSystemEvent = None
    logger.warning("⚠️ watchdog не установлен — hot-reload skills отключен. Установите: pip install watchdog (есть в requirements.txt)")

from app.skill_registry import SkillRegistry, Skill, SkillSource, get_skill_registry
from app.event_bus import get_event_bus, Event, EventType


# SkillFileHandler только если watchdog доступен
if WATCHDOG_AVAILABLE and FileSystemEventHandler is not None:
    class SkillFileHandler(FileSystemEventHandler):
        """Обработчик изменений SKILL.md файлов"""
        
        def __init__(self, skill_loader, debounce_ms: int = 250):
            self.skill_loader = skill_loader
            self.debounce_ms = debounce_ms
            self.pending_reloads: Set[str] = set()
            self._reload_tasks: Dict[str, asyncio.Task] = {}
        
        def _should_ignore(self, file_path: str) -> bool:
            """Проверить, нужно ли игнорировать файл"""
            path = Path(file_path)
            return path.name != "SKILL.md" or ".git" in path.parts or "__pycache__" in path.parts
        
        async def _debounced_reload(self, skill_dir: str):
            """Перезагрузить skill с debounce"""
            await asyncio.sleep(self.debounce_ms / 1000.0)
            
            if skill_dir in self.pending_reloads:
                self.pending_reloads.remove(skill_dir)
                await self.skill_loader.reload_skill(skill_dir)
        
        def on_modified(self, event: FileSystemEvent):
            """Обработчик изменения файла"""
            if event.is_directory:
                return
            
            if self._should_ignore(event.src_path):
                return
            
            skill_dir = str(Path(event.src_path).parent)
            
            # Отменяем предыдущую задачу перезагрузки для этого skill
            if skill_dir in self._reload_tasks:
                self._reload_tasks[skill_dir].cancel()
            
            # Добавляем в очередь перезагрузки
            self.pending_reloads.add(skill_dir)
            
            # Создаем новую задачу с debounce
            task = asyncio.create_task(self._debounced_reload(skill_dir))
            self._reload_tasks[skill_dir] = task
else:
    # Без watchdog SkillFileHandler не нужен - hot-reload не работает
    SkillFileHandler = None


class SkillLoader:
    """
    Skill Loader - динамическая загрузка и валидация skills
    
    Основано на Clawdbot patterns:
    - Парсинг SKILL.md с YAML frontmatter
    - Skills Watcher для auto-refresh
    - Hot-reload без перезапуска
    - Gating на основе метаданных
    """
    
    def __init__(
        self,
        skill_registry: Optional[SkillRegistry] = None,
        watch_enabled: bool = True,
        watch_debounce_ms: int = 250
    ):
        """
        Инициализация Skill Loader
        
        Args:
            skill_registry: Экземпляр Skill Registry (если None, используется глобальный)
            watch_enabled: Включить Skills Watcher
            watch_debounce_ms: Debounce для watcher в миллисекундах
        """
        self.skill_registry = skill_registry or get_skill_registry()
        # Отключаем watch если watchdog недоступен
        self.watch_enabled = watch_enabled and WATCHDOG_AVAILABLE
        self.watch_debounce_ms = watch_debounce_ms
        
        if self.watch_enabled and Observer is not None:
            try:
                self.observer = Observer()
                self.handler = None
            except Exception as e:
                logger.error(f"❌ Ошибка создания Observer: {e}")
                self.observer = None
                self.handler = None
                self.watch_enabled = False
        else:
            self.observer = None
            self.handler = None
            if watch_enabled and not WATCHDOG_AVAILABLE:
                logger.warning("⚠️ watch_enabled=True, но watchdog недоступен. Hot-reload отключен. Установите: pip install watchdog")
        
        self.running = False
        self.event_bus = get_event_bus()
        
        # Отслеживаемые директории
        self.watched_dirs: Set[str] = set()
        
        logger.info(f"✅ Skill Loader инициализирован (watch: {self.watch_enabled})")
    
    async def load_all_skills(self):
        """Загрузить все skills из реестра"""
        self.skill_registry.load_skills()
        logger.info(f"📦 Загружено skills: {len(self.skill_registry.skills)}")
    
    async def reload_skill(self, skill_dir: str):
        """Перезагрузить skill из директории"""
        try:
            skill_path = Path(skill_dir)
            if not (skill_path / "SKILL.md").exists():
                logger.warning(f"⚠️ SKILL.md не найден: {skill_dir}")
                return
            
            # Определяем source
            source = self._determine_source(skill_path)
            
            # Загружаем skill
            skill = self.skill_registry._load_skill_from_directory(skill_path, source)
            
            if skill:
                # Обновляем в реестре
                old_skill = self.skill_registry.get_skill(skill.name)
                self.skill_registry.register_skill(skill)
                
                # Публикуем событие
                event_type = EventType.SKILL_UPDATED if old_skill else EventType.SKILL_ADDED
                await self._publish_skill_event(event_type, skill)
                
                logger.info(f"🔄 Skill перезагружен: {skill.name}")
            else:
                logger.warning(f"⚠️ Не удалось перезагрузить skill: {skill_dir}")
        except Exception as e:
            logger.error(f"❌ Ошибка перезагрузки skill {skill_dir}: {e}", exc_info=True)
    
    def _determine_source(self, skill_path: Path) -> SkillSource:
        """Определить source skill по пути"""
        path_str = str(skill_path)
        
        if "workspace" in path_str or "skills" in path_str and "app" not in path_str:
            return SkillSource.WORKSPACE
        elif ".atra" in path_str:
            return SkillSource.MANAGED
        elif "app/skills" in path_str:
            return SkillSource.BUILTIN
        else:
            return SkillSource.MANAGED
    
    async def _publish_skill_event(self, event_type: EventType, skill: Skill):
        """Опубликовать событие о skill"""
        event = Event(
            event_id=f"skill_{event_type.value}_{skill.name}",
            event_type=event_type,
            payload={
                "skill_name": skill.name,
                "skill_description": skill.description,
                "skill_category": skill.category,
                "skill_source": skill.source.value,
                "skill_path": skill.skill_path
            },
            source="skill_loader"
        )
        
        await self.event_bus.publish(event)
    
    async def start_watcher(self):
        """Запустить Skills Watcher"""
        if not self.watch_enabled:
            return
        
        if self.running:
            logger.warning("⚠️ Skills Watcher уже запущен")
            return
        
        if SkillFileHandler is None:
            logger.error("❌ SkillFileHandler недоступен (watchdog не установлен)")
            return
        
        try:
            # Создаем обработчик
            self.handler = SkillFileHandler(self, self.watch_debounce_ms)
            
            # Регистрируем наблюдателей для всех директорий skills
            dirs_to_watch = []
            
            if self.skill_registry.bundled_skills_dir.exists():
                dirs_to_watch.append(str(self.skill_registry.bundled_skills_dir))
            
            if self.skill_registry.managed_skills_dir.exists():
                dirs_to_watch.append(str(self.skill_registry.managed_skills_dir))
            
            if self.skill_registry.workspace_skills_dir and self.skill_registry.workspace_skills_dir.exists():
                dirs_to_watch.append(str(self.skill_registry.workspace_skills_dir))
            
            for extra_dir in self.skill_registry.extra_dirs:
                if extra_dir.exists():
                    dirs_to_watch.append(str(extra_dir))
            
            for watch_dir in dirs_to_watch:
                if self.observer is not None and self.handler is not None:
                    self.observer.schedule(self.handler, watch_dir, recursive=True)
                self.watched_dirs.add(watch_dir)
                logger.info(f"👁️ Мониторинг skills: {watch_dir}")
            
            if dirs_to_watch:
                if self.observer is not None:
                    self.observer.start()
                self.running = True
                logger.info("🚀 Skills Watcher запущен")
            else:
                logger.warning("⚠️ Нет директорий для мониторинга skills")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Skills Watcher: {e}", exc_info=True)
            self.running = False
    
    async def stop_watcher(self):
        """Остановить Skills Watcher"""
        if not self.running:
            return
        
        try:
            if self.observer is not None:
                self.observer.stop()
                self.observer.join(timeout=5.0)
            self.running = False
            self.watched_dirs.clear()
            logger.info("🛑 Skills Watcher остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки Skills Watcher: {e}")
    
    def is_watching(self) -> bool:
        """Проверить, запущен ли watcher"""
        return self.running
    
    def get_stats(self) -> Dict:
        """Получить статистику Skill Loader"""
        return {
            "watching": self.running,
            "watched_dirs": list(self.watched_dirs),
            "watch_debounce_ms": self.watch_debounce_ms,
            "registry_stats": self.skill_registry.get_stats()
        }


async def main():
    """Пример использования"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Инициализируем Event Bus
    event_bus = get_event_bus()
    await event_bus.start()
    
    # Подписываемся на события skills
    async def handle_skill_added(event: Event):
        print(f"➕ Skill добавлен: {event.payload.get('skill_name')}")
    
    async def handle_skill_updated(event: Event):
        print(f"🔄 Skill обновлен: {event.payload.get('skill_name')}")
    
    event_bus.subscribe(EventType.SKILL_ADDED, handle_skill_added)
    event_bus.subscribe(EventType.SKILL_UPDATED, handle_skill_updated)
    
    # Создаем Skill Loader
    loader = SkillLoader(watch_enabled=True)
    
    # Загружаем все skills
    await loader.load_all_skills()
    
    # Запускаем watcher
    await loader.start_watcher()
    
    # Ждем события
    print("⏳ Мониторинг skills (нажмите Ctrl+C для остановки)...")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        pass
    
    print(f"\n📊 Статистика: {loader.get_stats()}")
    
    await loader.stop_watcher()
    await event_bus.stop()


if __name__ == "__main__":
    asyncio.run(main())
