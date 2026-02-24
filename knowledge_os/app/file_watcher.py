"""
File Watcher - Мониторинг изменений файлов
Основано на Clawdbot: watchdog для file watching, публикация событий в Event Bus
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.event_bus import Event, EventType, get_event_bus
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class FileChangeHandler(FileSystemEventHandler):
    """Обработчик изменений файлов"""

    def __init__(
        self,
        event_bus,
        watched_paths: Set[str],
        file_extensions: Optional[List[str]] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.event_bus = event_bus
        self.watched_paths = watched_paths
        self.file_extensions = file_extensions or []
        self._loop = loop  # для вызова publish из потока watchdog через run_coroutine_threadsafe
        self.ignored_patterns = {
            ".git",
            "__pycache__",
            ".pyc",
            ".pytest_cache",
            "node_modules",
            ".venv",
        }
        logger.info(
            f"📁 File Watcher инициализирован: {len(watched_paths)} путей, расширения: {file_extensions}"
        )

    def _should_ignore(self, file_path: str) -> bool:
        """Проверить, нужно ли игнорировать файл"""
        path = Path(file_path)

        # Игнорируем скрытые файлы и директории
        if any(part.startswith(".") for part in path.parts):
            return True

        # Игнорируем паттерны
        for pattern in self.ignored_patterns:
            if pattern in path.parts:
                return True

        # Фильтр по расширениям
        if self.file_extensions:
            if path.suffix not in self.file_extensions:
                return True

        return False

    def _publish_event(self, event_type: EventType, src_path: str, is_directory: bool = False):
        """Опубликовать событие в Event Bus"""
        if self._should_ignore(src_path):
            return

        try:
            event = Event(
                event_id=f"file_{event_type.value}_{os.path.basename(src_path)}",
                event_type=event_type,
                payload={
                    "file_path": src_path,
                    "file_name": os.path.basename(src_path),
                    "is_directory": is_directory,
                    "file_size": os.path.getsize(src_path)
                    if os.path.exists(src_path) and not is_directory
                    else 0,
                    "file_extension": Path(src_path).suffix if not is_directory else None,
                },
                source="file_watcher",
            )

            # Публикуем в event loop (из потока watchdog может не быть running loop — используем переданный loop)
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.event_bus.publish(event), self._loop)
                logger.debug(f"📢 Событие {event_type.value} для файла: {src_path}")
            else:
                try:
                    asyncio.create_task(self.event_bus.publish(event))
                    logger.debug(f"📢 Событие {event_type.value} для файла: {src_path}")
                except RuntimeError:
                    logger.debug("Нет running event loop для публикации (вызов из другого потока)")
        except Exception as e:
            logger.error(f"❌ Ошибка публикации события для {src_path}: {e}")

    def on_created(self, event: FileSystemEvent):
        """Обработчик создания файла"""
        if not event.is_directory:
            self._publish_event(EventType.FILE_CREATED, event.src_path)

    def on_modified(self, event: FileSystemEvent):
        """Обработчик изменения файла"""
        if not event.is_directory:
            self._publish_event(EventType.FILE_MODIFIED, event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        """Обработчик удаления файла"""
        if not event.is_directory:
            self._publish_event(EventType.FILE_DELETED, event.src_path)


class FileWatcher:
    """
    File Watcher - мониторинг изменений файлов с публикацией событий

    Основано на Clawdbot patterns:
    - Использует watchdog для эффективного мониторинга
    - Публикует события в Event Bus
    - Конфигурируемые пути и фильтры
    """

    def __init__(
        self,
        watch_paths: List[str],
        file_extensions: Optional[List[str]] = None,
        recursive: bool = True,
    ):
        """
        Инициализация File Watcher

        Args:
            watch_paths: Список путей для мониторинга
            file_extensions: Список расширений файлов для фильтрации (например, ['.py', '.md'])
            recursive: Рекурсивный мониторинг поддиректорий
        """
        self.watch_paths = [Path(p).resolve() for p in watch_paths]
        self.file_extensions = file_extensions
        self.recursive = recursive
        self.observer = Observer()
        self.event_bus = get_event_bus()
        self.handler = None
        self.running = False

        # Проверяем существование путей
        valid_paths = []
        for path in self.watch_paths:
            if path.exists():
                valid_paths.append(str(path))
            else:
                logger.warning(f"⚠️ Путь не существует, пропускаем: {path}")

        self.watched_paths = set(valid_paths)

        if not self.watched_paths:
            logger.warning("⚠️ Нет валидных путей для мониторинга")
        else:
            logger.info(f"✅ File Watcher инициализирован: {len(self.watched_paths)} путей")

    async def start(self):
        """Запустить мониторинг файлов"""
        if self.running:
            logger.warning("⚠️ File Watcher уже запущен")
            return

        if not self.watched_paths:
            logger.error("❌ Нет путей для мониторинга")
            return

        try:
            loop = asyncio.get_running_loop()
            self.handler = FileChangeHandler(
                self.event_bus, self.watched_paths, self.file_extensions, loop=loop
            )

            # Регистрируем наблюдателей для каждого пути
            for watch_path in self.watched_paths:
                self.observer.schedule(self.handler, watch_path, recursive=self.recursive)
                logger.info(f"👁️ Мониторинг: {watch_path} (recursive={self.recursive})")

            # Запускаем observer
            self.observer.start()
            self.running = True
            logger.info("🚀 File Watcher запущен")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска File Watcher: {e}", exc_info=True)
            self.running = False

    async def stop(self):
        """Остановить мониторинг файлов"""
        if not self.running:
            return

        try:
            self.observer.stop()
            self.observer.join(timeout=5.0)
            self.running = False
            logger.info("🛑 File Watcher остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки File Watcher: {e}")

    def is_running(self) -> bool:
        """Проверить, запущен ли мониторинг"""
        return self.running

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику File Watcher"""
        return {
            "running": self.running,
            "watched_paths": list(self.watched_paths),
            "file_extensions": self.file_extensions,
            "recursive": self.recursive,
            "observers_count": len(self.observer._handlers) if self.observer else 0,
        }


async def main():
    """Пример использования"""
    import logging

    logging.basicConfig(level=logging.INFO)

    # Инициализируем Event Bus
    event_bus = get_event_bus()
    await event_bus.start()

    # Подписываемся на события файлов
    async def handle_file_created(event: Event):
        print(f"📁 Файл создан: {event.payload.get('file_path')}")

    async def handle_file_modified(event: Event):
        print(f"✏️ Файл изменен: {event.payload.get('file_path')}")

    event_bus.subscribe(EventType.FILE_CREATED, handle_file_created)
    event_bus.subscribe(EventType.FILE_MODIFIED, handle_file_modified)

    # Создаем File Watcher
    watcher = FileWatcher(watch_paths=["."], file_extensions=[".py", ".md"], recursive=True)

    await watcher.start()

    # Ждем события
    print("⏳ Ожидание изменений файлов (нажмите Ctrl+C для остановки)...")
    try:
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        pass

    await watcher.stop()
    await event_bus.stop()


if __name__ == "__main__":
    asyncio.run(main())
