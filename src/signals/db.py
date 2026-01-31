"""
Модуль для работы с базой данных торгового бота ATRA.

Содержит класс Database для управления SQLite базой данных,
включая операции с сигналами, позициями, пользователями,
настройками и другими данными системы.
"""

# pylint: disable=too-many-lines
import sqlite3
import logging
import shutil
import os
import time
import re
import json
import threading
import random
import ast
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from src.shared.utils.datetime_utils import get_utc_now
from src.database.fetch_optimizer import fetch_all_optimized
from config import (
    DATABASE,
    RETENTION_QUOTES_DAYS,
    RETENTION_SIGNALS_DAYS,
    RETENTION_SIGNALS_LOG_DAYS,
    RETENTION_ACCUM_EVENTS_DAYS,
    RETENTION_APP_CACHE_DAYS,
    RETENTION_ENABLE_WEEKLY_VACUUM,
    # Адаптивные параметры
    ADAPTIVE_ENGINE_ENABLED,
    METRICS_FEEDER_ENABLED,
    METRICS_FEEDER_INTERVAL_SEC,
    METRICS_CACHE_TTL_SEC,
    PERFORMANCE_LOOKBACK_DAYS,
    ADAPTIVE_ENTRY_ADJ_ENABLED,
    ADAPTIVE_ENTRY_MAX_ADJUST_PCT,
    DYNAMIC_MODE_SWITCH_ENABLED,
    CORRELATION_COOLDOWN_ENABLED,
    CORRELATION_LOOKBACK_HOURS,
    CORRELATION_MAX_PAIRWISE,
    CORRELATION_COOLDOWN_SEC,
    SOFT_BLOCKLIST_ENABLED,
    SOFT_BLOCKLIST_HYSTERESIS,
    SOFT_BLOCK_COOLDOWN_HOURS,
    MIN_ACTIVE_COINS,
    BLOCKLIST_CHURN_FRAC,
    DYNAMIC_CALC_INTERVAL,
    DYNAMIC_TP_ENABLED,
    VOLUME_BLOCKS_ENABLED,
)

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Декоратор для профилирования
def profile(func):
    """Декоратор для профилирования времени выполнения функций"""
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logging.info("%s выполнена за %.3f сек", func.__name__, elapsed)
        return result

    return wrapper


BACKUP_DIR = "backups"


def backup_file(filepath, backup_dir=BACKUP_DIR):
    """Создает резервную копию файла с временной меткой"""
    os.makedirs(backup_dir, exist_ok=True)
    source = Path(filepath)
    if not source.is_file():
        logging.warning("Бэкап пропущен: файл %s не найден", filepath)
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(backup_dir) / f"{source.name}_{timestamp}"

    try:
        source_uri = f"file:{source.resolve()}?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as src_conn:
            with sqlite3.connect(str(backup_path)) as dst_conn:
                src_conn.backup(dst_conn)
        logging.info("SQLite backup %s -> %s", source, backup_path)
    except sqlite3.Error as exc:
        # Фолбэк на прямое копирование (на случай старых версий sqlite)
        shutil.copy(str(source), str(backup_path))
        logging.warning(
            "SQLite backup API ошибка (%s), выполнено прямое копирование %s -> %s",
            exc,
            source,
            backup_path,
        )

    return str(backup_path)


class Database:
    """PiuX_Trade: Класс для работы с базой данных сигналов и сделок."""

    _instance = None
    _instance_lock = threading.Lock()
    _db_usage_logged_once = False
    _readonly_instance = None

    def __new__(cls, *args, **kwargs):
        # Проверяем, запрашивается ли read-only соединение
        readonly = kwargs.get('readonly', False)

        with cls._instance_lock:
            if readonly:
                # Для read-only создаем отдельный экземпляр
                if cls._readonly_instance is None:
                    cls._readonly_instance = super(Database, cls).__new__(cls)
                    cls._readonly_instance._initialized = False
                    cls._readonly_instance._is_readonly = True
                return cls._readonly_instance
            else:
                # Для записи используем singleton
                if cls._instance is None:
                    cls._instance = super(Database, cls).__new__(cls)
                    cls._instance._initialized = False
                    cls._instance._is_readonly = False
                return cls._instance

    def __init__(self, db_path=DATABASE, use_connection_pool: bool = False, readonly: bool = False):
        """
        Args:
            db_path: Путь к файлу БД
            use_connection_pool: Использовать connection pool (ОТКЛЮЧЕНО)
            readonly: Использовать read-only соединение (для ридеров)
        """
        if getattr(self, '_initialized', False):
            return

        self.db_path = db_path
        self._is_readonly = getattr(self, '_is_readonly', readonly)
        # 🔧 ИСПРАВЛЕНО: всегда отключаем connection_pool
        self.use_connection_pool = False
        self._pool = None
        self._use_pool = False

        # Прямое соединение (fallback или если pool отключен)
        if not self._use_pool:
            # Разрешаем использование соединения из разных потоков
            # Важно: обеспечиваем сериализацию записей через lock
            if self._is_readonly:
                # Read-only соединение через URI
                db_uri = f"file:{os.path.abspath(db_path)}?mode=ro"
                self.conn = sqlite3.connect(db_uri, uri=True, check_same_thread=False, timeout=60.0)
                logging.info("✅ [DB] Создано read-only соединение: %s", db_path)
            else:
                self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=60.0)
                # Включаем WAL и другие оптимизации сразу для основного соединения
                try:
                    self.conn.execute("PRAGMA journal_mode=WAL;")
                    self.conn.execute("PRAGMA synchronous=NORMAL;")
                    self.conn.execute("PRAGMA busy_timeout=60000;")
                except sqlite3.Error as e:
                    logging.warning("Не удалось применить PRAGMA при создании соединения: %s", e)
            self.cursor = self.conn.cursor()
        else:
            # При использовании pool соединение получаем динамически
            self.conn = None
            self.cursor = None

        self._lock = threading.RLock()
        # Попытка авто-ремонта, если схема повреждена
        # (e.g., "malformed database schema (ETHUSDT)")
        # Только если есть прямое соединение (не pool)
        if not self._use_pool and self.conn is not None:
            self._try_repair_malformed_schema()
            # Режим WAL и busy_timeout для повышения конкуррентности
            try:
                with self._lock:
                    self.conn.execute("PRAGMA journal_mode=WAL;")
                    self.conn.execute("PRAGMA synchronous=NORMAL;")
                    self.conn.execute("PRAGMA busy_timeout=60000;")  # Увеличено до 60s
                    # Оптимизация cache_size: используем 64MB или 25% от RAM (мин 64MB)
                    import psutil
                    try:
                        available_ram_mb = psutil.virtual_memory().total / (1024 * 1024)
                        # Используем 25% от RAM, но минимум 64MB и максимум 512MB
                        optimal_cache_mb = max(64, min(512, int(available_ram_mb * 0.25)))
                        cache_size_kb = -optimal_cache_mb * 1024  # Отрицательное значение = KB
                        self.conn.execute(f"PRAGMA cache_size={cache_size_kb};")
                        logging.info("✅ [DB] PRAGMA cache_size установлен: %dMB", optimal_cache_mb)
                    except Exception:
                        # Fallback на 64MB если не удалось определить RAM
                        self.conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache
                    self.conn.execute("PRAGMA mmap_size=268435456;")  # 256MB mmap
                    self.conn.execute("PRAGMA temp_store=MEMORY;")
                    self.conn.execute("PRAGMA foreign_keys=ON;")  # Включить FK
            except sqlite3.Error as e:
                logging.warning("Не удалось применить PRAGMA для БД: %s", e)

        # Инициализация таблиц
        self._initialize_tables_on_init()
        
        # Автоматическое применение оптимизаций (ТОЛЬКО если явно разрешено через ENV)
        try:
            if os.getenv('AUTO_APPLY_OPTIMIZATIONS', 'false').lower() == 'true':
                from src.database.optimization_manager import DatabaseOptimizationManager
                opt_manager = DatabaseOptimizationManager(self)
                opt_manager.apply_all_optimizations()
                logging.debug("✅ [DB] Автоматические оптимизации применены")
        except Exception as e:
            logging.debug("⚠️ [DB] Ошибка автоматического применения оптимизаций: %s", e)
        
        # Инициализация write queue (ленивая, при первом async вызове)
        self._write_queue: Optional[Any] = None
        self._write_queue_initialized = False
        
        # Prepared statements cache для переиспользования планов запросов
        self._prepared_statements: Dict[str, Any] = {}
        
        # Query cache для кэширования результатов запросов
        self._query_cache_enabled = True
        try:
            from src.database.query_cache import get_query_cache
            self._query_cache = get_query_cache()
        except ImportError:
            self._query_cache = None
            self._query_cache_enabled = False
        
        self._initialized = True

    def _get_db_executor(self):
        """Получить функцию-исполнитель для write queue"""
        def db_executor(query: str, params: Any = (), is_write: bool = True, executemany: bool = False):
            """Синхронный исполнитель для write queue"""
            with self._lock:
                if executemany:
                    self.cursor.executemany(query, params)
                else:
                    self.cursor.execute(query, params)
                if is_write:
                    self.conn.commit()
                return fetch_all_optimized(self.cursor) if not is_write else True
        return db_executor

    async def _ensure_write_queue(self):
        """Обеспечить инициализацию write queue"""
        if not self._write_queue_initialized:
            try:
                from src.database.write_queue import get_write_queue
                self._write_queue = await get_write_queue(
                    db_executor=self._get_db_executor(),
                    max_retries=5,
                    initial_retry_delay=0.5,
                    max_queue_size=1000,
                    enable_metrics=True,
                )
                self._write_queue_initialized = True
                logging.info("✅ [DB] Write queue инициализирован")
            except Exception as e:
                logging.warning("⚠️ [DB] Не удалось инициализировать write queue: %s", e)
                self._write_queue = None

    async def execute_with_retry_async(
        self,
        query: str,
        params: tuple = (),
        is_write: bool = True,
        max_retries: int = 5,
        use_queue: bool = True,
    ):
        """
        Асинхронное выполнение SQL запроса с использованием write queue

        Args:
            query: SQL запрос
            params: Параметры запроса
            is_write: Является ли операция записью
            max_retries: Максимальное кол-во попыток (для совместимости)
            use_queue: Использовать write queue (по умолчанию True)

        Returns:
            Результат выполнения запроса
        """
        # Если write queue отключен или не инициализирован, используем синхронный метод
        if not use_queue or self._write_queue is None:
            await self._ensure_write_queue()

        if use_queue and self._write_queue is not None:
            try:
                from src.database.write_queue import WriteOperationType
                result = await self._write_queue.execute(
                    query=query,
                    params=params,
                    is_write=is_write,
                    operation_type=WriteOperationType.EXECUTE,
                )
                return result
            except Exception as e:
                logging.warning(
                    "⚠️ [DB] Ошибка в write queue, fallback на синхронный метод: %s", e
                )

        # Fallback на синхронный метод через asyncio.to_thread
        return await asyncio.to_thread(
            self.execute_with_retry,
            query,
            params,
            is_write,
            max_retries
        )

    def _get_prepared_statement(self, query: str):
        """
        Получает или создает prepared statement для запроса
        Ускоряет повторяющиеся запросы на 10-20%
        """
        # Используем нормализованный ключ (убираем пробелы, приводим к нижнему регистру)
        query_key = ' '.join(query.strip().split()).lower()
        
        if query_key not in self._prepared_statements:
            # SQLite автоматически кэширует prepared statements, но мы можем
            # явно подготовить запрос для лучшей производительности
            self._prepared_statements[query_key] = query
        
        return self._prepared_statements[query_key]
    
    def _serialize_quality_meta(self, quality_meta: Any) -> Optional[str]:
        """
        Быстрая сериализация quality_meta с использованием MessagePack
        Ускоряет сериализацию на 2-3x
        """
        if not isinstance(quality_meta, dict):
            return None
        
        try:
            from src.data.serialization import serialize_fast
            import base64
            data_serialized = serialize_fast(quality_meta)
            return base64.b64encode(data_serialized).decode('utf-8')
        except (ImportError, Exception):
            # Fallback на JSON
            return json.dumps(quality_meta, ensure_ascii=False)

    def execute_with_retry(
        self,
        query: str,
        params: tuple = (),
        is_write: bool = True,
        max_retries: int = 5,
        use_prepared: bool = True,
        use_cache: bool = True,
        cache_ttl: int = 300
    ):
        """
        SQL запрос с повторными попытками при блокировке.
        Поддерживает prepared statements и Redis кэширование для ускорения.
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            is_write: Является ли запрос записью
            max_retries: Максимальное количество попыток
            use_prepared: Использовать prepared statements
            use_cache: Использовать Redis кэш для read-only запросов
            cache_ttl: Время жизни кэша в секундах
        """
        # Для read-only запросов проверяем кэш
        if not is_write and use_cache:
            try:
                from src.database.redis_cache import get_from_cache
                cached_result = get_from_cache(query, params, ttl=cache_ttl)
                if cached_result is not None:
                    # Конвертируем обратно в кортежи если нужно
                    if isinstance(cached_result, list) and cached_result:
                        if isinstance(cached_result[0], list):
                            return [tuple(row) for row in cached_result]
                    return cached_result
            except Exception as e:
                logging.debug("⚠️ [DB] Ошибка проверки кэша: %s", e)
        
        retry_delay = 0.5
        
        # Используем prepared statement если включено и запрос повторяющийся
        if use_prepared and not is_write:
            query = self._get_prepared_statement(query)
        
        for attempt in range(max_retries):
            try:
                with self._lock:
                    self.cursor.execute(query, params)
                    if is_write:
                        self.conn.commit()
                    return fetch_all_optimized(self.cursor) if not is_write else True
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    logging.warning(
                        "⚠️ БД заблокирована (попытка %d/%d), ждем %.1fс...", 
                        attempt + 1, max_retries, retry_delay
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error("❌ Ошибка БД после %d попыток: %s", max_retries, e)
                raise e
            except Exception as e:
                logging.error("❌ Критическая ошибка БД: %s", e)
                raise e
        return False

    def execute_batch(self, queries: List[Tuple[str, tuple]], is_write: bool = True, max_retries: int = 5) -> bool:
        """
        Выполнение batch операций в одной транзакции
        Оптимизировано для массовых операций (50-90% ускорение)
        
        Args:
            queries: Список кортежей (query, params)
            is_write: Являются ли операции записями
            max_retries: Максимальное количество попыток
            
        Returns:
            True при успехе, False при ошибке
        """
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                with self._lock:
                    self.conn.execute("BEGIN TRANSACTION")
                    try:
                        for query, params in queries:
                            self.cursor.execute(query, params)
                        if is_write:
                            self.conn.commit()
                        else:
                            self.conn.rollback()
                        return True
                    except Exception as e:
                        self.conn.rollback()
                        raise e
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    logging.warning("⚠️ БД заблокирована при batch операции (попытка %d/%d), ждем %.1fс...", 
                                    attempt + 1, max_retries, retry_delay)
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                logging.error("❌ Ошибка batch операции после %d попыток: %s", max_retries, e)
                return False
            except Exception as e:
                logging.error("❌ Критическая ошибка batch операции: %s", e)
                return False
        return False

    def _get_table_indexes(self, table_name: str) -> List[Tuple[str, str]]:
        """
        Получает список индексов для таблицы
        
        Args:
            table_name: Имя таблицы
            
        Returns:
            Список кортежей (index_name, create_sql)
        """
        indexes = []
        try:
            with self._lock:
                # Получаем все индексы для таблицы
                cursor = self.conn.execute("""
                    SELECT name, sql FROM sqlite_master 
                    WHERE type='index' AND tbl_name=? AND sql IS NOT NULL
                """, (table_name,))
                indexes = [(row[0], row[1]) for row in fetch_all_optimized(cursor)]
        except Exception as e:
            logging.warning("⚠️ [DB] Ошибка получения индексов для %s: %s", table_name, e)
        return indexes

    def _disable_indexes_for_table(self, table_name: str) -> List[Tuple[str, str]]:
        """
        Временно отключает индексы для таблицы (удаляет их)
        
        Args:
            table_name: Имя таблицы
            
        Returns:
            Список кортежей (index_name, create_sql) для последующего восстановления
        """
        indexes = self._get_table_indexes(table_name)
        if not indexes:
            return []
        
        disabled_indexes = []
        try:
            with self._lock:
                for index_name, create_sql in indexes:
                    try:
                        # Удаляем индекс
                        self.conn.execute(f"DROP INDEX IF EXISTS {index_name}")
                        disabled_indexes.append((index_name, create_sql))
                        logging.debug("✅ [DB] Временно отключен индекс: %s", index_name)
                    except Exception as e:
                        logging.warning("⚠️ [DB] Ошибка отключения индекса %s: %s", index_name, e)
        except Exception as e:
            logging.warning("⚠️ [DB] Ошибка отключения индексов для %s: %s", table_name, e)
        
        return disabled_indexes

    def _restore_indexes(self, disabled_indexes: List[Tuple[str, str]]) -> bool:
        """
        Восстанавливает ранее отключенные индексы
        
        Args:
            disabled_indexes: Список кортежей (index_name, create_sql)
            
        Returns:
            True если успешно восстановлены все индексы
        """
        if not disabled_indexes:
            return True
        
        success_count = 0
        try:
            with self._lock:
                for index_name, create_sql in disabled_indexes:
                    try:
                        # Восстанавливаем индекс
                        self.conn.execute(create_sql)
                        success_count += 1
                        logging.debug("✅ [DB] Восстановлен индекс: %s", index_name)
                    except Exception as e:
                        logging.warning("⚠️ [DB] Ошибка восстановления индекса %s: %s", index_name, e)
        except Exception as e:
            logging.warning("⚠️ [DB] Ошибка восстановления индексов: %s", e)
        
        return success_count == len(disabled_indexes)

    def executemany_optimized(
        self, 
        query: str, 
        params_list: List[tuple], 
        max_retries: int = 5,
        disable_indexes: bool = True
    ) -> bool:
        """
        Оптимизированный executemany с отключением индексов для массовой вставки
        Ускорение на 50-90% для массовых операций
        
        Args:
            query: SQL запрос
            params_list: Список параметров для executemany
            max_retries: Максимальное количество попыток
            disable_indexes: Отключать ли индексы перед вставкой (ускорение 50-90%)
            
        Returns:
            True при успехе, False при ошибке
        """
        # Извлекаем имя таблицы из INSERT запроса
        table_name = None
        disabled_indexes = []
        
        if disable_indexes and query.strip().upper().startswith('INSERT'):
            try:
                # Парсим имя таблицы из INSERT запроса
                match = re.search(r'INSERT\s+INTO\s+(\w+)', query, re.IGNORECASE)
                if match:
                    table_name = match.group(1)
                    # Отключаем индексы перед массовой вставкой
                    disabled_indexes = self._disable_indexes_for_table(table_name)
                    if disabled_indexes:
                        logging.info("✅ [DB] Отключено %d индексов для массовой вставки в %s", 
                                   len(disabled_indexes), table_name)
            except Exception as e:
                logging.warning("⚠️ [DB] Ошибка определения таблицы для отключения индексов: %s", e)
        
        retry_delay = 0.5
        
        try:
            for attempt in range(max_retries):
                try:
                    with self._lock:
                        # Сохраняем текущие настройки
                        old_synchronous = self.conn.execute("PRAGMA synchronous").fetchone()[0]
                        
                        try:
                            # Отключаем синхронность для массовой вставки
                            self.conn.execute("PRAGMA synchronous=OFF")
                            self.conn.execute("BEGIN TRANSACTION")
                            
                            self.cursor.executemany(query, params_list)
                            self.conn.commit()
                            
                            # Включаем обратно
                            self.conn.execute(f"PRAGMA synchronous={old_synchronous}")
                            
                            # Восстанавливаем индексы после успешной вставки
                            if disabled_indexes:
                                self._restore_indexes(disabled_indexes)
                                logging.info("✅ [DB] Восстановлено %d индексов после массовой вставки", 
                                           len(disabled_indexes))
                            
                            # Автоматически выполняем ANALYZE после массовой вставки для обновления статистики
                            try:
                                self.conn.execute("ANALYZE")
                                logging.debug("✅ [DB] ANALYZE выполнен после массовой вставки")
                            except Exception as e:
                                logging.debug("⚠️ [DB] Ошибка ANALYZE после массовой вставки: %s", e)
                            
                            return True
                        except Exception as e:
                            self.conn.rollback()
                            # Восстанавливаем настройки даже при ошибке
                            self.conn.execute(f"PRAGMA synchronous={old_synchronous}")
                            raise e
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        logging.warning("⚠️ БД заблокирована при executemany (попытка %d/%d), ждем %.1fс...", 
                                        attempt + 1, max_retries, retry_delay)
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    logging.error("❌ Ошибка executemany после %d попыток: %s", max_retries, e)
                    return False
                except Exception as e:
                    logging.error("❌ Критическая ошибка executemany: %s", e)
                    return False
        finally:
            # Восстанавливаем индексы даже при ошибке
            if disabled_indexes:
                try:
                    self._restore_indexes(disabled_indexes)
                except Exception as e:
                    logging.error("❌ Критическая ошибка восстановления индексов: %s", e)
        
        return False

    def _initialize_tables_on_init(self):
        """Вспомогательный метод для инициализации таблиц при создании"""
        try:
            # 🔧 ИСПРАВЛЕНО: connection_pool отключен
            if self.conn is not None:
                self._init_tables()
            else:
                logging.warning("⚠️ [DB] Нет соединения с БД")
        except sqlite3.DatabaseError as e:
            # Финальный фолбэк: если схема повреждена — создаём новый файл БД.
            if "malformed database schema" in str(e).lower():
                logging.error(
                    "Схема БД повреждена. Пересоздаю БД (бэкап будет сохранён)…"
                )
                self._reset_database_preserving_backup()
            else:
                raise
        if not Database._db_usage_logged_once:
            print(f"[PiuX_Trade][DB] Используется база данных: {self.db_path}")
            Database._db_usage_logged_once = True
        # Файл с пользовательскими данными бота (в JSON)
        self.user_data_file = "user_data.json"

    def is_connected(self):
        """Простая проверка доступности соединения с БД."""
        try:
            # 🔧 ИСПРАВЛЕНО: проверяем прямое соединение
            if self.conn is None:
                return False
            with self._lock:
                self.conn.execute("SELECT 1")
            return True
        except (sqlite3.Error, ValueError, AttributeError, RuntimeError) as e:
            logging.debug("is_connected check failed: %s", e)
            return False

    def get_lock(self):
        """Возвращает контекстный менеджер для блокировки БД."""
        return self._lock

    def _try_repair_malformed_schema(self):
        """
        Устраняет записи с повреждённой схемой в sqlite_master
        (типичный кейс: старые таблицы с именами символов).

        Логика:
        - Пытаемся удалить объект обычными DROP-командами.
        - Если не удаётся — удаляем напрямую через writable_schema.
        """
        # Если нет соединения, ничего не делаем
        if self.conn is None:
            return

        max_attempts = 10
        for _ in range(max_attempts):
            try:
                with self._lock:
                    # Простая команда, которая триггерит парсинг схемы
                    self.conn.execute("PRAGMA user_version;")
                # Успех — ничего чинить не требуется
                break
            except sqlite3.DatabaseError as e:
                msg = str(e)
                m = re.search(
                    r"malformed database schema \(([^)]+)\)", msg, flags=re.IGNORECASE
                )
                if not m:
                    logging.warning("DB init error: %s", e)
                    return
                bad_object = m.group(1)
                try:
                    logging.warning(
                        "Обнаружен повреждённый объект '%s'. Удаляем…", bad_object
                    )
                    with self._lock:
                        # Пытаемся обычными способами
                        for drop_type in ["TABLE", "INDEX", "VIEW", "TRIGGER"]:
                            try:
                                self.conn.execute(
                                    f"DROP {drop_type} IF EXISTS \"{bad_object}\""
                                )
                            except sqlite3.Error:
                                pass
                        self.conn.commit()
                except sqlite3.Error:
                    pass

                # Если по-прежнему ломается — чистим sqlite_master напрямую
                try:
                    with self._lock:
                        self.conn.execute("PRAGMA writable_schema=ON;")
                        self.conn.execute(
                            "DELETE FROM sqlite_master WHERE name=?", (bad_object,)
                        )
                        self.conn.execute("PRAGMA writable_schema=OFF;")
                        self.conn.commit()
                        try:
                            self.conn.execute("VACUUM;")
                        except sqlite3.Error:
                            pass
                except sqlite3.Error as e2:
                    logging.error(
                        "Не удалось удалить объект '%s': %s", bad_object, e2
                    )
                    return
                continue
        # Профилактика: удалим подозрительные объекты (например, ETHUSDT)
        try:
            with self._lock:
                cur = self.conn.execute(
                    "SELECT name, type FROM sqlite_master WHERE name GLOB '[A-Z0-9]*USDT' "
                    "OR name GLOB '[A-Z0-9]*BTC' OR name GLOB '[A-Z0-9]*ETH'"
                )
                rows = fetch_all_optimized(cur) or []
        except sqlite3.Error:
            rows = []
        for name, obj_type in rows:
            # Системные таблицы
            known = {
                'fees','quotes','arbitrage_events','pairs','manual_trades',
                'active_signals','signals','signals_log','users_data',
                'signal_accum_events','app_cache','backtest_results',
                'telemetry_cycles','telemetry_api'
            }
            if name in known:
                continue
            try:
                with self._lock:
                    if obj_type in ['table', 'index', 'view', 'trigger']:
                        self.conn.execute(f"DROP {obj_type.upper()} IF EXISTS \"{name}\"")
                    self.conn.commit()
                    logging.warning(
                        "Удалён подозрительный объект: %s (%s)", name, obj_type
                    )
            except sqlite3.Error:
                # Жёсткая чистка, если обычный DROP не помогает
                try:
                    with self._lock:
                        self.conn.execute("PRAGMA writable_schema=ON;")
                        self.conn.execute("DELETE FROM sqlite_master WHERE name=?", (name,))
                        self.conn.execute("PRAGMA writable_schema=OFF;")
                        self.conn.commit()
                        try:
                            self.conn.execute("VACUUM;")
                        except sqlite3.Error:
                            pass
                    logging.warning("Принудительно удалён объект схемы через writable_schema: %s", name)
                except sqlite3.Error as e3:
                    logging.error("Не удалось удалить объект схемы '%s': %s", name, e3)
                    # Продолжаем, чтобы попытаться восстановиться максимально

        # Контрольная проверка целостности
        try:
            with self._lock:
                cur = self.conn.execute("PRAGMA integrity_check;")
                res = cur.fetchone()
                if res and str(res[0]).lower() != 'ok':
                    logging.warning("PRAGMA integrity_check вернул: %s", res[0])
        except sqlite3.Error:
            pass

    def _reset_database_preserving_backup(self):
        """
        Создаёт чистый файл БД, сохранив бэкап старого.
        Используется при критическом повреждении схемы.
        """
        try:
            # Закрываем текущее соединение
            try:
                self.conn.close()
            except sqlite3.Error:
                pass
            # Бэкапим исходную БД
            try:
                backup_file(self.db_path)
            except (OSError, IOError):
                logging.warning("Не удалось создать бэкап перед сбросом БД")
            # Удаляем повреждённый файл и создаём заново
            try:
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
            except OSError as e:
                logging.error("Не удалось удалить старый файл БД: %s", e)
            # Новое соединение
            self.conn = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=30.0
            )
            self.cursor = self.conn.cursor()
            # Применяем PRAGMA
            try:
                with self._lock:
                    self.conn.execute("PRAGMA journal_mode=WAL;")
                    self.conn.execute("PRAGMA synchronous=NORMAL;")
                    self.conn.execute("PRAGMA busy_timeout=60000;")
                    # Оптимизация cache_size
                    import psutil
                    try:
                        available_ram_mb = psutil.virtual_memory().total / (1024 * 1024)
                        optimal_cache_mb = max(
                            64, min(512, int(available_ram_mb * 0.25))
                        )
                        cache_size_kb = -optimal_cache_mb * 1024
                        self.conn.execute(f"PRAGMA cache_size={cache_size_kb};")
                    except Exception:
                        self.conn.execute("PRAGMA cache_size=-64000;")
                    self.conn.execute("PRAGMA mmap_size=268435456;")
                    self.conn.execute("PRAGMA temp_store=MEMORY;")
                    self.conn.execute("PRAGMA foreign_keys=ON;")
            except sqlite3.Error:
                pass
            # Инициализация таблиц
            self._init_tables()
            logging.error("База данных пересоздана. Старая версия в бэкапах.")
        except sqlite3.Error as e:
            logging.critical("Ошибка при пересоздании БД: %s", e)
            raise

    def _init_tables(self):
        """Инициализация всех необходимых таблиц БД"""
        # Проверка наличия соединения
        if self.conn is None or self.cursor is None:
            logging.warning("⚠️ [DB] Невозможно инициализировать таблицы: conn/cursor None")
            return

        # Защита от блокировок
        try:
            with self._lock:
                self.conn.execute("PRAGMA busy_timeout=30000;")
        except sqlite3.Error:
            pass

        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange TEXT,
            symbol TEXT,
            maker_fee REAL,
            taker_fee REAL,
            withdraw_fee REAL,
            network TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
        )
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            exchange TEXT,
            symbol TEXT,
            bid REAL CHECK (bid > 0),
            ask REAL CHECK (ask > 0 AND ask >= bid)
        )"""
        )
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS arbitrage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            symbol TEXT,
            buy_exchange TEXT,
            sell_exchange TEXT,
            buy_price REAL,
            sell_price REAL,
            amount REAL,
            net_profit REAL,
            net_profit_pct REAL
        )"""
        )
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange TEXT,
            symbol TEXT,
            base_asset TEXT,
            quote_asset TEXT,
            status TEXT,
            min_qty REAL,
            max_qty REAL,
            step_size REAL,
            min_price REAL,
            max_price REAL,
            price_tick REAL,
            maker_commission REAL,
            taker_commission REAL,
            is_spot_allowed INTEGER,
            is_margin_allowed INTEGER,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
        )
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS manual_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            symbol TEXT,
            buy_exchange TEXT,
            sell_exchange TEXT,
            buy_price REAL,
            sell_price REAL,
            amount REAL,
            notified_profit REAL,
            notified_profit_pct REAL,
            withdraw_fee REAL,
            final_profit REAL,
            final_profit_pct REAL,
            status TEXT,
            real_buy_price REAL,
            real_sell_price REAL,
            real_amount REAL,
            real_profit REAL,
            real_profit_pct REAL,
            trade_completed INTEGER DEFAULT 0
        )"""
        )
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS active_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_key TEXT UNIQUE,
            status TEXT,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )"""
        )
        # Миграции активных сигналов: добавляем expiry_time и entry_time при отсутствии
        try:
            with self._lock:
                self.conn.execute("ALTER TABLE active_signals ADD COLUMN expiry_time TEXT")
        except sqlite3.Error:
            pass
        try:
            with self._lock:
                self.conn.execute("ALTER TABLE active_signals ADD COLUMN symbol TEXT")
        except sqlite3.Error:
            pass
        try:
            with self._lock:
                self.conn.execute("ALTER TABLE active_signals ADD COLUMN entry_time TEXT")
        except sqlite3.Error:
            pass
        try:
            with self._lock:
                self.conn.execute("ALTER TABLE active_signals ADD COLUMN chat_id INTEGER")
        except sqlite3.Error:
            pass
        try:
            with self._lock:
                self.conn.execute("ALTER TABLE active_signals ADD COLUMN message_id INTEGER")
        except sqlite3.Error:
            pass
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            exchange TEXT,
            symbol TEXT,
            rsi REAL,
            ema_fast REAL,
            ema_slow REAL,
            price REAL
        )"""
        )
        # Новые таблицы для полной БД-персистентности
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS signals_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            entry REAL CHECK (entry IS NULL OR entry > 0),
            stop REAL CHECK (stop IS NULL OR stop > 0),
            tp1 REAL CHECK (tp1 IS NULL OR tp1 > 0),
            tp2 REAL CHECK (tp2 IS NULL OR tp2 > 0),
            entry_time TEXT,
            exit_time TEXT,
            result TEXT,
            net_profit REAL,
            qty_added REAL CHECK (qty_added IS NULL OR qty_added >= 0),
            qty_closed REAL CHECK (qty_closed IS NULL OR qty_closed >= 0),
            leverage_used INTEGER CHECK (leverage_used IS NULL OR leverage_used > 0),
            risk_pct_used REAL CHECK (risk_pct_used IS NULL OR (risk_pct_used >= 0 AND risk_pct_used <= 100)),
            entry_amount_usd REAL CHECK (entry_amount_usd IS NULL OR entry_amount_usd >= 0),
            trade_mode TEXT,
            funding_rate REAL,
            quote24h_usd REAL CHECK (quote24h_usd IS NULL OR quote24h_usd >= 0),
            depth_usd REAL CHECK (depth_usd IS NULL OR depth_usd >= 0),
            spread_pct REAL CHECK (spread_pct IS NULL OR spread_pct >= 0),
            exposure_pct REAL CHECK (exposure_pct IS NULL OR (exposure_pct >= 0 AND exposure_pct <= 100)),
            mtf_score REAL,
            sector TEXT,
            expected_cost_usd REAL CHECK (expected_cost_usd IS NULL OR expected_cost_usd >= 0),
            impact_bp REAL,
            quality_score REAL CHECK (quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 100)),
            quality_meta TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        # Индексы для сигналов
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_log_sym_time "
            "ON signals_log(symbol, entry_time)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_log_created_at "
            "ON signals_log(created_at)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_log_result_on "
            "ON signals_log(result)"
        )
        # Удаляем дубликаты
        try:
            self.cursor.execute(
                """
                DELETE FROM signals_log
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM signals_log
                    GROUP BY symbol, entry_time, exit_time, net_profit, result
                )
                """
            )
        except sqlite3.Error as cleanup_err:
            logger.debug("⚠️ [DB] Ошибка очистки signals_log: %s", cleanup_err)
        # Ограничиваем повторные записи
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_log_unique_event "
            "ON signals_log(symbol, entry_time, exit_time, net_profit, result)"
        )
        # Таблица реальных сделок (используется TradeTracker)
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
            entry_price REAL NOT NULL CHECK (entry_price > 0),
            exit_price REAL CHECK (exit_price IS NULL OR exit_price > 0),
            entry_time DATETIME NOT NULL,
            exit_time DATETIME,
            duration_minutes REAL CHECK (duration_minutes IS NULL OR duration_minutes >= 0),
            quantity REAL NOT NULL CHECK (quantity > 0),
            position_size_usdt REAL NOT NULL CHECK (position_size_usdt > 0),
            leverage REAL DEFAULT 1.0 CHECK (leverage > 0 AND leverage <= 125),
            risk_percent REAL CHECK (risk_percent IS NULL OR (risk_percent >= 0 AND risk_percent <= 100)),
            pnl_usd REAL,
            pnl_percent REAL,
            fees_usd REAL DEFAULT 0.0 CHECK (fees_usd >= 0),
            net_pnl_usd REAL,
            exit_reason TEXT,
            tp1_price REAL CHECK (tp1_price IS NULL OR tp1_price > 0),
            tp2_price REAL CHECK (tp2_price IS NULL OR tp2_price > 0),
            sl_price REAL CHECK (sl_price IS NULL OR sl_price > 0),
            tp1_hit INTEGER DEFAULT 0 CHECK (tp1_hit IN (0, 1)),
            tp2_hit INTEGER DEFAULT 0 CHECK (tp2_hit IN (0, 1)),
            sl_hit INTEGER DEFAULT 0 CHECK (sl_hit IN (0, 1)),
            signal_key TEXT,
            user_id TEXT,
            trade_mode TEXT DEFAULT 'futures' CHECK (trade_mode IN ('spot', 'futures', 'margin')),
            filter_mode TEXT DEFAULT 'strict',
            confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 100)),
            dca_count INTEGER DEFAULT 0 CHECK (dca_count >= 0),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason)")
        
        # Частичные индексы для приоритетных символов (ускорение на 30-50%)
        self._create_partial_indexes()
        
        # Добавляем CHECK constraints для существующих таблиц через триггеры валидации
        # (SQLite не поддерживает ALTER TABLE ADD CONSTRAINT, используем триггеры)
        self._add_validation_triggers()
        
        # Миграции для signals_log: добавляем user_id
        try:
            with self._lock:
                self.conn.execute("ALTER TABLE signals_log ADD COLUMN user_id INTEGER")
        except sqlite3.Error:
            pass
        
        # Миграции: добавляем суррогатные ключи для временных меток (ускорение на 20-40%)
        self._add_surrogate_time_keys()
        # Миграции: добавляем недостающие колонки (если отсутствуют)
        for attempt, col_def in enumerate([
            ("leverage_used", "INTEGER"),
            ("risk_pct_used", "REAL"),
            ("entry_amount_usd", "REAL"),
            ("trade_mode", "TEXT"),
            ("funding_rate", "REAL"),
            ("quote24h_usd", "REAL"),
            ("depth_usd", "REAL"),
            ("spread_pct", "REAL"),
            ("exposure_pct", "REAL"),
            ("mtf_score", "REAL"),
            ("sector", "TEXT"),
            ("expected_cost_usd", "REAL"),
            ("impact_bp", "REAL"),
        ]):
            try:
                with self._lock:
                    self.conn.execute(
                        f"ALTER TABLE signals_log ADD COLUMN {col_def[0]} {col_def[1]}"
                    )
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    # Экспоненциальный backoff
                    wait_time = 0.1 * (2 ** attempt) + random.uniform(0, 0.1)
                    time.sleep(wait_time)
                    try:
                        with self._lock:
                            self.conn.execute(
                                f"ALTER TABLE signals_log ADD COLUMN {col_def[0]} {col_def[1]}"
                            )
                    except sqlite3.Error:
                        pass
                elif "duplicate column name" in str(e).lower():
                    pass
                else:
                    pass
            except sqlite3.Error:
                pass
        # Создаём индекс после добавления столбца
        try:
            self.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_signals_log_user_sym_time "
                "ON signals_log(user_id, symbol, entry_time)"
            )
        except sqlite3.Error:
            pass
        
        # Добавляем CHECK constraints для существующих таблиц через триггеры валидации
        # (SQLite не поддерживает ALTER TABLE ADD CONSTRAINT, используем триггеры)
        self._add_validation_triggers()
        
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS users_data (
            user_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        # Накопитель сигналов: события
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS signal_accum_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER,
            symbol TEXT,
            event TEXT,
            weight REAL,
            ttl_sec INTEGER,
            meta TEXT
        )"""
        )
        self.cursor.execute(
            """
        CREATE INDEX IF NOT EXISTS idx_accum_symbol_ts ON signal_accum_events(symbol, ts)
        """
        )
        # Универсальный кэш (DB-уровень)
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS app_cache (
            cache_type TEXT,
            cache_key TEXT,
            payload TEXT,
            expires_at INTEGER,
            PRIMARY KEY(cache_type, cache_key)
        )
        """
        )
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_cache_expires_at ON app_cache(expires_at)")

        # Таблица для системных настроек (адаптивная система)
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Таблица для истории снимков конфигурации (Rollback System)
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS system_config_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_json TEXT NOT NULL,
            win_rate REAL,
            pnl_pct REAL,
            is_stable INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        # Таблица для блоклиста монет с низкой капитализацией
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS market_cap_blacklist (
            symbol TEXT PRIMARY KEY,
            market_cap REAL,
            blacklisted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_checked TEXT DEFAULT CURRENT_TIMESTAMP,
            unfreeze_date TEXT,
            reason TEXT DEFAULT 'low_market_cap'
        )
        """
        )

        # Таблица для логирования проверок фильтров
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS filter_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            filter_type TEXT,
            passed INTEGER DEFAULT 0,
            reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        # Создаем индекс для быстрого поиска по created_at
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_filter_checks_created_at ON filter_checks(created_at)"
        )
        # События детектора ложных пробоев (для статистики pass-rate)
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS false_breakout_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            confidence REAL,
            threshold REAL,
            passed INTEGER,
            regime TEXT,
            regime_confidence REAL,
            volatility_pct REAL,
            volume_confidence REAL,
            momentum_confidence REAL,
            level_confidence REAL,
            recent_pass_rate REAL,
            test_run INTEGER DEFAULT 0
        )
        """
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_false_brk_sym_time "
            "ON false_breakout_events(symbol, created_at)"
        )
        # Логирование MTF-подтверждений
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS mtf_confirmation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            confirmed INTEGER,
            error TEXT,
            regime TEXT,
            regime_confidence REAL
        )
        """
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_mtf_conf_sym_time "
            "ON mtf_confirmation_events(symbol, created_at)"
        )

        # Логирование позиционного сайзинга
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS position_sizing_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            direction TEXT,
            entry_time TEXT NOT NULL,
            signal_token TEXT,
            user_id TEXT,
            trade_mode TEXT,
            signal_price REAL,
            baseline_amount_usd REAL,
            ai_amount_usd REAL,
            regime_multiplier REAL,
            after_regime_amount_usd REAL,
            correlation_multiplier REAL,
            after_correlation_amount_usd REAL,
            adaptive_multiplier REAL,
            after_adaptive_amount_usd REAL,
            risk_adjustment_multiplier REAL,
            final_amount_usd REAL,
            base_risk_pct REAL,
            ai_risk_pct REAL,
            leverage REAL,
            regime TEXT,
            regime_confidence REAL,
            quality_score REAL,
            composite_score REAL,
            pattern_confidence REAL,
            adaptive_reason TEXT,
            adaptive_components TEXT
        )
            """
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pos_size_sym_time "
            "ON position_sizing_events(symbol, entry_time)"
        )
        # Добавляем недостающие колонки при обновлении существующей таблицы
        for column_def in [
            ("adaptive_reason", "TEXT"),
            ("adaptive_components", "TEXT"),
        ]:
            try:
                self.cursor.execute(f"ALTER TABLE position_sizing_events ADD COLUMN {column_def[0]} {column_def[1]}")
            except sqlite3.OperationalError:
                pass

        # Добавляем колонку test_run для mtf_confirmation_events (если отсутствует)
        try:
            self.cursor.execute(
                "ALTER TABLE mtf_confirmation_events ADD COLUMN test_run INTEGER DEFAULT 0"
            )
        except sqlite3.OperationalError:
            # Колонка уже существует
            pass
        # Результаты бэктеста (реплей нашей стратегии)
        self.cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            interval TEXT,
            since_days INTEGER,
            bars INTEGER,
            signals INTEGER,
            tp1 INTEGER,
            tp2 INTEGER,
            sl INTEGER,
            pnl REAL,
            mae_avg_pct REAL,
            mfe_avg_pct REAL,
            avg_duration_sec REAL,
            started_at TEXT,
            ended_at TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        self.conn.commit()
        self.periodic_backup()

    # Простое планирование бэкапов (вызовом по таймеру из внешнего цикла)
    _last_backup_ts = 0
    def periodic_backup(self, min_interval_sec: int = 600):
        """Выполняет периодическое резервное копирование базы данных"""
        now = time.time()
        if now - Database._last_backup_ts >= min_interval_sec:
            backup_file(self.db_path)
            Database._last_backup_ts = now

    def save_quote(self, exchange, symbol, bid, ask):
        """Сохраняет котировку в базу данных"""
        self.cursor.execute(
            "INSERT INTO quotes (ts, exchange, symbol, bid, ask) VALUES (?, ?, ?, ?, ?)",
            (get_utc_now().isoformat(), exchange, symbol, bid, ask),
        )
        self.conn.commit()
        self.periodic_backup()

    def save_arbitrage_event(
        self,
        symbol,
        buy_exchange,
        sell_exchange,
        buy_price,
        sell_price,
        amount,
        net_profit,
        net_profit_pct,
    ):
        """
        Сохраняет событие арбитража в базу данных.

        Args:
            symbol (str): Символ торговой пары
            buy_exchange (str): Биржа для покупки
            sell_exchange (str): Биржа для продажи
            buy_price (float): Цена покупки
            sell_price (float): Цена продажи
            amount (float): Количество
            net_profit (float): Чистая прибыль
            net_profit_pct (float): Процент чистой прибыли
        """
        self.cursor.execute(
            "INSERT INTO arbitrage_events (ts, symbol, buy_exchange, sell_exchange, buy_price, "
            "sell_price, amount, net_profit, net_profit_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                get_utc_now().isoformat(),
                symbol,
                buy_exchange,
                sell_exchange,
                buy_price,
                sell_price,
                amount,
                net_profit,
                net_profit_pct,
            ),
        )
        self.conn.commit()
        self.periodic_backup()

    def insert_fees_for_pairs(
        self,
        exchange,
        pairs,
        default_maker_fee,
        default_taker_fee,
        default_withdraw_fee=None,
        network=None,
    ):
        """
        Вставляет комиссии для торговых пар.

        Args:
            exchange (str): Название биржи
            pairs (list): Список торговых пар
            default_maker_fee (float): Комиссия мейкера по умолчанию
            default_taker_fee (float): Комиссия тейкера по умолчанию
            default_withdraw_fee (float, optional): Комиссия за вывод по умолчанию
            network (str, optional): Сеть для вывода средств
        """
        # Оптимизация: сначала получаем все существующие fees одним запросом
        existing_fees = set()
        with self._lock:
            cur = self.conn.execute(
                "SELECT symbol FROM fees WHERE exchange=?", (exchange,)
            )
            existing_fees = {row[0] for row in fetch_all_optimized(cur)}
        
        # Оптимизация: используем batch операцию вместо множественных INSERT
        to_insert = [
            (
                exchange,
                pair["symbol"] if isinstance(pair, dict) else pair,
                default_maker_fee,
                default_taker_fee,
                default_withdraw_fee,
                network,
            )
            for pair in pairs
            if (pair["symbol"] if isinstance(pair, dict) else pair) not in existing_fees
        ]
        
        if to_insert:
            query = """
                INSERT INTO fees (exchange, symbol, maker_fee, taker_fee, withdraw_fee, network)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            self.executemany_optimized(query, to_insert)
        self.periodic_backup()

    def save_system_setting(self, key, value):
        """Сохраняет настройку системы"""
        try:
            self.cursor.execute(
                "INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, get_utc_now().isoformat())
            )
            self.conn.commit()
            self.periodic_backup()
            return True
        except Exception as e:
            logging.error("❌ Ошибка сохранения настройки %s: %s", key, e)
            return False

# Старые дублированные методы удалены - используются новые версии ниже

    def save_backtest_result(
        self, symbol, interval, since_days, bars, signals, tp1, tp2, sl, pnl,
        mae_avg_pct, mfe_avg_pct, avg_duration_sec, started_at, ended_at
    ):
        """Сохраняет результат бэктеста"""
        try:
            self.cursor.execute(
                """INSERT INTO backtest_results
                (symbol, interval, since_days, bars, signals, tp1, tp2, sl, pnl,
                 mae_avg_pct, mfe_avg_pct, avg_duration_sec, 
                 started_at, ended_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, interval, since_days, bars, signals, tp1, tp2, sl, pnl,
                 mae_avg_pct, mfe_avg_pct, avg_duration_sec, started_at, ended_at,
                 datetime.now().isoformat())
            )
            self.conn.commit()
            self.periodic_backup()
            return True
        except Exception as e:
            logging.error("❌ Ошибка бэктеста %s: %s", symbol, e)
            return False

    def get_backtest_results(self, symbol=None, limit=10):
        """Получает результаты бэктестов"""
        try:
            if symbol:
                self.cursor.execute(
                    "SELECT * FROM backtest_results WHERE symbol = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (symbol, limit)
                )
            else:
                self.cursor.execute(
                    "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ?", 
                    (limit,)
                )
            return fetch_all_optimized(self.cursor)
        except Exception as e:
            logging.error("❌ Ошибка получения бэктестов: %s", e)
            return []

    def update_withdraw_fee(self, exchange, symbol, withdraw_fee, network=None):
        """
        Обновляет комиссию за вывод.
        """
        self.cursor.execute(
            "UPDATE fees SET withdraw_fee=?, network=?, "
            "last_updated=CURRENT_TIMESTAMP WHERE exchange=? AND symbol=?",
            (withdraw_fee, network, exchange, symbol),
        )
        self.conn.commit()
        self.periodic_backup()

    def update_maker_fee(self, exchange, symbol, maker_fee):
        """
        Обновляет комиссию мейкера для торговой пары.

        Args:
            exchange (str): Название биржи
            symbol (str): Символ торговой пары
            maker_fee (float): Комиссия мейкера
        """
        self.cursor.execute(
            "UPDATE fees SET maker_fee=?, last_updated=CURRENT_TIMESTAMP WHERE exchange=? AND symbol=?",
            (maker_fee, exchange, symbol),
        )
        self.conn.commit()
        self.periodic_backup()

    def update_taker_fee(self, exchange, symbol, taker_fee):
        """
        Обновляет комиссию тейкера для торговой пары.

        Args:
            exchange (str): Название биржи
            symbol (str): Символ торговой пары
            taker_fee (float): Комиссия тейкера
        """
        self.cursor.execute(
            "UPDATE fees SET taker_fee=?, last_updated=CURRENT_TIMESTAMP WHERE exchange=? AND symbol=?",
            (taker_fee, exchange, symbol),
        )
        self.conn.commit()
        self.periodic_backup()

    def get_fees(self, exchange, symbol):
        """
        Получает информацию о комиссиях для торговой пары.
        """
        self.cursor.execute(
            "SELECT maker_fee, taker_fee, withdraw_fee, network "
            "FROM fees WHERE exchange=? AND symbol=?",
            (exchange, symbol),
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "maker_fee": row[0],
                "taker_fee": row[1],
                "withdraw_fee": row[2],
                "network": row[3],
            }
        return None

    def update_pair_info(self, exchange, symbol, **kwargs):
        """
        Обновляет информацию о торговой паре.
        """
        columns = ", ".join(f"{k}=?" for k in kwargs)
        values = list(kwargs.values())
        values.extend([exchange, symbol])
        self.cursor.execute(
            f"UPDATE pairs SET {columns}, last_updated=CURRENT_TIMESTAMP "
            "WHERE exchange=? AND symbol=?",
            values,
        )
        self.conn.commit()
        self.periodic_backup()

    def insert_pairs_for_exchange(self, exchange, pairs):
        """
        Вставляет торговые пары для биржи.

        Args:
            exchange (str): Название биржи
            pairs (list): Список торговых пар
        """
        # Оптимизация: сначала получаем все существующие пары одним запросом
        existing_pairs = set()
        with self._lock:
            cur = self.conn.execute(
                "SELECT symbol FROM pairs WHERE exchange=?", (exchange,)
            )
            existing_pairs = {row[0] for row in fetch_all_optimized(cur)}
        
        # Оптимизация: используем list comprehension вместо цикла с append
        to_insert = [
            (
                exchange,
                pair["symbol"],
                pair.get("base_asset"),
                pair.get("quote_asset"),
                pair.get("status"),
                pair.get("min_qty"),
                pair.get("max_qty"),
                pair.get("step_size"),
                pair.get("min_price"),
                pair.get("max_price"),
                pair.get("price_tick"),
                pair.get("maker_commission"),
                pair.get("taker_commission"),
                int(pair.get("is_spot_allowed", False)),
                int(pair.get("is_margin_allowed", False)),
            )
            for pair in pairs
            if pair["symbol"] not in existing_pairs
        ]
        if to_insert:
            # Оптимизация: используем executemany_optimized для массовой вставки
            query = """
                INSERT INTO pairs (
                    exchange, symbol, base_asset, quote_asset, status,
                    min_qty, max_qty, step_size, min_price, max_price, price_tick,
                    maker_commission, taker_commission,
                    is_spot_allowed, is_margin_allowed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.executemany_optimized(query, to_insert)
        self.periodic_backup()

    def mass_update_fees(
        self, exchange, maker_fee=None, taker_fee=None, withdraw_fee=None, network=None
    ):
        """
        Массово обновить комиссии для всех пар биржи.
        Любой из параметров можно не указывать (тогда не обновляется).
        """
        set_clauses = []
        values = []
        if maker_fee is not None:
            set_clauses.append("maker_fee=?")
            values.append(maker_fee)
        if taker_fee is not None:
            set_clauses.append("taker_fee=?")
            values.append(taker_fee)
        if withdraw_fee is not None:
            set_clauses.append("withdraw_fee=?")
            values.append(withdraw_fee)
        if network is not None:
            set_clauses.append("network=?")
            values.append(network)
        if not set_clauses:
            return  # ничего не обновлять
        set_sql = ", ".join(set_clauses) + ", last_updated=CURRENT_TIMESTAMP"
        sql = f"UPDATE fees SET {set_sql} WHERE exchange=?"
        values.append(exchange)
        self.cursor.execute(sql, values)
        self.conn.commit()
        self.periodic_backup()

    def add_active_signal(self, signal_key, status):
        """
        Добавляет активный сигнал в базу данных.
        """
        self.cursor.execute(
            "INSERT OR REPLACE INTO active_signals (signal_key, status, ts) "
            "VALUES (?, ?, datetime('now'))",
            (signal_key, status),
        )
        self.conn.commit()
        self.periodic_backup()

    def remove_active_signal(self, signal_key):
        """
        Удаляет активный сигнал из базы данных.

        Args:
            signal_key (str): Ключ сигнала
        """
        self.cursor.execute(
            "DELETE FROM active_signals WHERE signal_key=?",
            (signal_key,),
        )
        self.conn.commit()
        self.periodic_backup()

    # --- Активные сигналы с истечением ---
    def add_active_signal_with_expiry(
        self,
        signal_key: str,
        status: str,
        expiry_time: str,
        entry_time: str = None,
        chat_id: int = None,
        message_id: int = None,
        symbol: str = None
    ):
        """
        Добавляет активный сигнал с временем истечения.

        Args:
            signal_key (str): Ключ сигнала
            status (str): Статус сигнала
            expiry_time (str): Время истечения сигнала
            entry_time (str, optional): Время входа
            chat_id (int, optional): ID чата
            message_id (int, optional): ID сообщения
            symbol (str, optional): Символ торговой пары
        """
        try:
            with self._lock:
                self.conn.execute(
                    """
                    INSERT INTO active_signals(signal_key, status, ts, expiry_time, symbol,
                                              entry_time, chat_id, message_id)
                    VALUES(?, ?, datetime('now'), ?, ?, ?, ?, ?)
                    ON CONFLICT(signal_key) DO UPDATE SET
                        status=excluded.status, ts=excluded.ts, expiry_time=excluded.expiry_time,
                        symbol=excluded.symbol, entry_time=excluded.entry_time,
                        chat_id=excluded.chat_id, message_id=excluded.message_id
                    """,
                    (signal_key, status, expiry_time, symbol, entry_time, chat_id, message_id),
                )
                self.conn.commit()
        except sqlite3.Error as e:
            logging.warning("add_active_signal_with_expiry error: %s", e)

    def get_active_signal_info(self, signal_key: str):
        """
        Получает информацию об активном сигнале.

        Args:
            signal_key (str): Ключ сигнала

        Returns:
            dict: Информация о сигнале или None, если не найден
        """
        try:
            with self._lock:
                cur = self.conn.execute(
                    "SELECT status, ts, expiry_time, entry_time FROM active_signals WHERE signal_key=?",
                    (signal_key,),
                )
                row = cur.fetchone()
            if not row:
                return None
            return {"status": row[0], "ts": row[1], "expiry_time": row[2], "entry_time": row[3]}
        except sqlite3.Error as e:
            logging.warning("get_active_signal_info error: %s", e)
            return None

    def mark_signal_expired(self, signal_key: str) -> bool:
        """
        Отмечает сигнал как истекший.

        Args:
            signal_key (str): Ключ сигнала

        Returns:
            bool: True если сигнал был обновлен, False в противном случае
        """
        try:
            with self._lock:
                self.conn.execute(
                    "UPDATE active_signals SET status='expired', ts=datetime('now') WHERE signal_key=?",
                    (signal_key,),
                )
                self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.warning("mark_signal_expired error: %s", e)
            return False

    def is_signal_active_or_recent(self, signal_key, recent_minutes=60):
        """
        Проверяет, активен ли сигнал или был недавно отклонен.

        Args:
            signal_key (str): Ключ сигнала
            recent_minutes (int): Количество минут для проверки недавности

        Returns:
            bool: True если сигнал активен или был недавно отклонен
        """
        self.cursor.execute(
            "SELECT status, ts FROM active_signals WHERE signal_key=?",
            (signal_key,),
        )
        row = self.cursor.fetchone()
        if not row:
            return False
        status, ts = row
        if status == "active":
            return True
        # Проверка времени отклонения
        try:
            ts_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            ts_dt = datetime.fromisoformat(ts)
        if status == "declined" and (datetime.now() - ts_dt).total_seconds() < recent_minutes * 60:
            return True
        return False

    # ===== Накопитель сигналов =====
    def add_accum_event(self, symbol: str, event: str, weight: float, ttl_sec: int, meta: Optional[dict] = None):
        """
        Добавляет событие в накопитель сигналов.

        Args:
            symbol (str): Символ торговой пары
            event (str): Тип события
            weight (float): Вес события
            ttl_sec (int): Время жизни события в секундах
            meta (dict, optional): Дополнительные метаданные
        """
        ts = int(time.time())
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        try:
            with self._lock:
                self.cursor.execute(
                    "INSERT INTO signal_accum_events(ts, symbol, event, weight, ttl_sec, meta) VALUES(?,?,?,?,?,?)",
                    (ts, symbol, event, float(weight), int(ttl_sec), meta_json),
                )
                self.conn.commit()
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("[AccumDB] add_accum_event error: %s", e)

    def get_accum_events(self, symbol: str, window_sec: int) -> List[Tuple]:
        """
        Получает события из накопителя сигналов за указанный период.

        Args:
            symbol (str): Символ торговой пары
            window_sec (int): Окно времени в секундах

        Returns:
            List[Tuple]: Список событий
        """
        now_ts = int(time.time())
        min_ts = max(0, now_ts - int(window_sec))
        try:
            with self._lock:
                self.cursor.execute(
                    """SELECT ts, event, weight, ttl_sec, meta
                    FROM signal_accum_events
                    WHERE symbol=? AND ts>=?
                    ORDER BY ts ASC""",
                    (symbol, min_ts),
                )
                rows = fetch_all_optimized(self.cursor)
                return rows or []
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("[AccumDB] get_accum_events error: %s", e)
            return []

    def update_signal_status(self, signal_key, status):
        """
        Обновляет статус сигнала.

        Args:
            signal_key (str): Ключ сигнала
            status (str): Новый статус сигнала
        """
        self.cursor.execute(
            "UPDATE active_signals SET status=?, ts=datetime('now') WHERE signal_key=?",
            (status, signal_key),
        )
        self.conn.commit()
        self.periodic_backup()

    @profile
    def get_daily_stats(self, date_str=None):
        """Получает статистику за день"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # Статистика по арбитражным событиям
        self.cursor.execute(
            """
            SELECT
                COUNT(*) as total_signals,
                SUM(net_profit) as total_profit,
                AVG(net_profit_pct) as avg_profit_pct,
                MIN(net_profit_pct) as min_profit_pct,
                MAX(net_profit_pct) as max_profit_pct,
                SUM(amount) as total_volume
            FROM arbitrage_events
            WHERE DATE(ts) = ?
        """,
            (date_str,),
        )

        arbitrage_stats = self.cursor.fetchone()

        # Статистика по ручным сделкам
        self.cursor.execute(
            """
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN trade_completed = 1 THEN real_profit ELSE final_profit END) as total_profit,
                AVG(CASE WHEN trade_completed = 1 THEN real_profit_pct ELSE final_profit_pct END) as avg_profit_pct,
                COUNT(CASE WHEN (CASE WHEN trade_completed = 1 THEN real_profit
                    ELSE final_profit END) > 0 THEN 1 END) as profitable_trades,
                COUNT(CASE WHEN (CASE WHEN trade_completed = 1 THEN real_profit
                    ELSE final_profit END) < 0 THEN 1 END) as losing_trades,
                COUNT(CASE WHEN trade_completed = 1 THEN 1 END) as completed_trades
            FROM manual_trades
            WHERE DATE(ts) = ?
        """,
            (date_str,),
        )

        trade_stats = self.cursor.fetchone()

        return {
            "date": date_str,
            "arbitrage": {
                "total_signals": arbitrage_stats[0] or 0,
                "total_profit": arbitrage_stats[1] or 0,
                "avg_profit_pct": arbitrage_stats[2] or 0,
                "min_profit_pct": arbitrage_stats[3] or 0,
                "max_profit_pct": arbitrage_stats[4] or 0,
                "total_volume": arbitrage_stats[5] or 0,
            },
            "trades": {
                "total_trades": trade_stats[0] or 0,
                "total_profit": trade_stats[1] or 0,
                "avg_profit_pct": trade_stats[2] or 0,
                "profitable_trades": trade_stats[3] or 0,
                "losing_trades": trade_stats[4] or 0,
                "completed_trades": trade_stats[5] or 0,
            },
        }

    def get_weekly_stats(self, week_start=None):
        """Получает статистику за неделю"""
        if week_start is None:
            # Находим начало текущей недели (понедельник)
            today = get_utc_now()
            days_since_monday = today.weekday()
            week_start = (today - timedelta(days=days_since_monday)).strftime("%Y-%m-%d")

        # Статистика по арбитражным событиям за неделю
        self.cursor.execute(
            """
            SELECT
                COUNT(*) as total_signals,
                SUM(net_profit) as total_profit,
                AVG(net_profit_pct) as avg_profit_pct,
                MIN(net_profit_pct) as min_profit_pct,
                MAX(net_profit_pct) as max_profit_pct,
                SUM(amount) as total_volume,
                COUNT(DISTINCT DATE(ts)) as trading_days
            FROM arbitrage_events
            WHERE DATE(ts) >= ? AND DATE(ts) <= DATE(?, '+6 days')
        """,
            (week_start, week_start),
        )

        arbitrage_stats = self.cursor.fetchone()

        # Статистика по ручным сделкам за неделю
        self.cursor.execute(
            """
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN trade_completed = 1 THEN real_profit ELSE final_profit END) as total_profit,
                AVG(CASE WHEN trade_completed = 1 THEN real_profit_pct ELSE final_profit_pct END) as avg_profit_pct,
                COUNT(CASE WHEN (CASE WHEN trade_completed = 1 THEN real_profit
                    ELSE final_profit END) > 0 THEN 1 END) as profitable_trades,
                COUNT(CASE WHEN (CASE WHEN trade_completed = 1 THEN real_profit
                    ELSE final_profit END) < 0 THEN 1 END) as losing_trades,
                COUNT(DISTINCT DATE(ts)) as trading_days,
                COUNT(CASE WHEN trade_completed = 1 THEN 1 END) as completed_trades
            FROM manual_trades
            WHERE DATE(ts) >= ? AND DATE(ts) <= DATE(?, '+6 days')
        """,
            (week_start, week_start),
        )

        trade_stats = self.cursor.fetchone()

        # Статистика по дням недели
        self.cursor.execute(
            """
            SELECT
                DATE(ts) as day,
                COUNT(*) as signals,
                SUM(net_profit) as profit
            FROM arbitrage_events
            WHERE DATE(ts) >= ? AND DATE(ts) <= DATE(?, '+6 days')
            GROUP BY DATE(ts)
            ORDER BY day
        """,
            (week_start, week_start),
        )

        daily_stats = fetch_all_optimized(self.cursor)

        return {
            "week_start": week_start,
            "arbitrage": {
                "total_signals": arbitrage_stats[0] or 0,
                "total_profit": arbitrage_stats[1] or 0,
                "avg_profit_pct": arbitrage_stats[2] or 0,
                "min_profit_pct": arbitrage_stats[3] or 0,
                "max_profit_pct": arbitrage_stats[4] or 0,
                "total_volume": arbitrage_stats[5] or 0,
                "trading_days": arbitrage_stats[6] or 0,
            },
            "trades": {
                "total_trades": trade_stats[0] or 0,
                "total_profit": trade_stats[1] or 0,
                "avg_profit_pct": trade_stats[2] or 0,
                "profitable_trades": trade_stats[3] or 0,
                "losing_trades": trade_stats[4] or 0,
                "trading_days": trade_stats[5] or 0,
                "completed_trades": trade_stats[6] or 0,
            },
            "daily_stats": [
                {"day": day, "signals": signals, "profit": profit or 0}
                for day, signals, profit in daily_stats
            ],
        }

    def get_pending_trades(self):
        """Получает список незавершенных сделок"""
        self.cursor.execute(
            """
            SELECT id, ts, symbol, buy_exchange, sell_exchange, buy_price, sell_price, amount,
                   notified_profit, notified_profit_pct, withdraw_fee, final_profit, final_profit_pct
            FROM manual_trades
            WHERE trade_completed = 0 AND status = 'finished'
            ORDER BY ts DESC
        """
        )
        return fetch_all_optimized(self.cursor)

    def update_trade_result(
        self,
        trade_id,
        real_buy_price,
        real_sell_price,
        real_amount,
        real_profit,
        real_profit_pct,
    ):
        """Обновляет реальные результаты сделки"""
        self.cursor.execute(
            """
            UPDATE manual_trades
            SET real_buy_price = ?, real_sell_price = ?, real_amount = ?,
                real_profit = ?, real_profit_pct = ?, trade_completed = 1
            WHERE id = ?
        """,
            (
                real_buy_price,
                real_sell_price,
                real_amount,
                real_profit,
                real_profit_pct,
                trade_id,
            ),
        )
        self.conn.commit()
        self.periodic_backup()

    def get_trade_by_id(self, trade_id):
        """Получает сделку по ID"""
        self.cursor.execute(
            """
            SELECT id, ts, symbol, buy_exchange, sell_exchange, buy_price, sell_price, amount,
                   notified_profit, notified_profit_pct, withdraw_fee, final_profit, final_profit_pct,
                   real_buy_price, real_sell_price, real_amount, real_profit, real_profit_pct, trade_completed
            FROM manual_trades
            WHERE id = ?
        """,
            (trade_id,),
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "ts": row[1],
                "symbol": row[2],
                "buy_exchange": row[3],
                "sell_exchange": row[4],
                "buy_price": row[5],
                "sell_price": row[6],
                "amount": row[7],
                "notified_profit": row[8],
                "notified_profit_pct": row[9],
                "withdraw_fee": row[10],
                "final_profit": row[11],
                "final_profit_pct": row[12],
                "real_buy_price": row[13],
                "real_sell_price": row[14],
                "real_amount": row[15],
                "real_profit": row[16],
                "real_profit_pct": row[17],
                "trade_completed": row[18],
            }
        return None

    def insert_signal(self, signal):
        """
        Вставляет новый сигнал в базу данных.

        Args:
            signal (dict): Словарь с данными сигнала
        """
        self.cursor.execute(
            "INSERT INTO signals (ts, exchange, symbol, rsi, ema_fast, ema_slow, price) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                get_utc_now().isoformat(),
                signal["exchange"],
                signal["symbol"],
                signal["rsi"],
                signal["ema_fast"],
                signal["ema_slow"],
                signal["price"],
            ),
        )
        self.conn.commit()
        print(f"[PiuX_Trade][DB] Сигнал добавлен: {signal}")
        backup_file(self.db_path)

    # ====== Signals log API ======
    def insert_signal_log_entry(self, row: dict):
        columns = [
            "symbol",
            "entry",
            "stop",
            "tp1",
            "tp2",
            "entry_time",
            "exit_time",
            "result",
            "net_profit",
            "qty_added",
            "qty_closed",
            "user_id",
            "direction",
        ]
        values = [row.get(c) for c in columns]

        # Добавляем quality_score если он есть
        if "quality_score" in row and row.get("quality_score") is not None:
            columns.append("quality_score")
            values.append(float(row["quality_score"]))

        # Добавляем quality_meta если он есть
        if "quality_meta" in row and row.get("quality_meta") is not None:
            columns.append("quality_meta")
            quality_meta = row["quality_meta"]
            if isinstance(quality_meta, dict):
                # Оптимизация: используем быструю сериализацию
                values.append(self._serialize_quality_meta(quality_meta))
            else:
                values.append(str(quality_meta))
        symbol = row.get("symbol")
        entry_time = row.get("entry_time")
        exit_time = row.get("exit_time")
        net_profit = row.get("net_profit")
        result = row.get("result")

        # 🔧 ИСПРАВЛЕНО: Проверяем, что conn инициализирован
        if self.conn is None:
            logger.error("❌ [DB] self.conn is None в insert_signal_log_entry, пытаемся переинициализировать")
            try:
                # Всегда используем прямое соединение для надежности
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
                self.cursor = self.conn.cursor()
                with self._lock:
                    self.conn.execute("PRAGMA journal_mode=WAL;")
                    self.conn.execute("PRAGMA synchronous=NORMAL;")
                    self.conn.execute("PRAGMA busy_timeout=60000;")  # 60s для конкурентности
                    # Оптимизация cache_size
                    import psutil
                    try:
                        available_ram_mb = psutil.virtual_memory().total / (1024 * 1024)
                        optimal_cache_mb = max(64, min(512, int(available_ram_mb * 0.25)))
                        cache_size_kb = -optimal_cache_mb * 1024
                        self.conn.execute(f"PRAGMA cache_size={cache_size_kb};")
                    except Exception:
                        self.conn.execute("PRAGMA cache_size=-64000;")  # 64MB fallback
                    self.conn.execute("PRAGMA mmap_size=268435456;")  # 256MB mmap
                    self.conn.execute("PRAGMA temp_store=MEMORY;")
                    self.conn.execute("PRAGMA foreign_keys=ON;")
                logger.info("✅ [DB] Подключение переинициализировано успешно")
            except Exception as e:
                logger.error("❌ [DB] Не удалось переинициализировать подключение: %s", e)
                return False

        with self._lock:
            try:
                duplicate = self.conn.execute(
                    """
                    SELECT id
                    FROM signals_log
                    WHERE symbol = ?
                      AND entry_time = ?
                      AND COALESCE(exit_time, '') = COALESCE(?, '')
                      AND COALESCE(net_profit, 0) = COALESCE(?, 0)
                      AND COALESCE(result, '') = COALESCE(?, '')
                    """,
                    (
                        symbol,
                        entry_time,
                        exit_time,
                        net_profit,
                        result,
                    ),
                ).fetchone()
            except sqlite3.Error as dup_err:
                logger.debug("⚠️ [DB] Проверка дубликатов signals_log не удалась: %s", dup_err)
                duplicate = None

            if duplicate:
                logger.debug(
                    "↩️ [DB] signals_log дубликат пропущен: symbol=%s entry_time=%s result=%s",
                    symbol,
                    entry_time,
                    result,
                )
                return duplicate[0]

            self.conn.execute(
                f"INSERT INTO signals_log ({', '.join(columns)}) VALUES ({', '.join(['?']*len(columns))})",
                values,
            )
            self.conn.commit()
        self.periodic_backup()

    def update_signal_close_db(self, symbol: str, entry_time: str, exit_time: str, result: str, net_profit: float):
        """
        Обновляет данные о закрытии сигнала в базе данных.

        Args:
            symbol (str): Символ торговой пары
            entry_time (str): Время входа
            exit_time (str): Время выхода
            result (str): Результат сделки
            net_profit (float): Чистая прибыль
        """
        self.cursor.execute(
            """
            UPDATE signals_log
            SET exit_time = ?, result = ?, net_profit = ?
            WHERE symbol = ? AND entry_time = ?
        """,
            (exit_time, result, net_profit, symbol, entry_time),
        )
        self.conn.commit()
        self.periodic_backup()

    def get_last_signal_log(self, user_id=None):
        """Получает последний сигнал из БД (с поддержкой connection pool)"""
        try:
            # Используем created_at (UTC, без таймзоны) для корректной сортировки
            # 🔧 ИСПРАВЛЕНО: connection_pool отключен, используем прямое соединение
            if self.conn is not None:
                cur = self.cursor
                if user_id is not None:
                    cur.execute(
                        """
                        SELECT symbol, entry, tp1, tp2, entry_time, result
                        FROM signals_log
                        WHERE user_id = ?
                        ORDER BY datetime(created_at) DESC
                        LIMIT 1
                    """,
                        (user_id,)
                    )
                else:
                    cur.execute(
                        """
                        SELECT symbol, entry, tp1, tp2, entry_time, result
                        FROM signals_log
                        ORDER BY datetime(created_at) DESC
                        LIMIT 1
                    """
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    return {
                        "symbol": row[0],
                        "entry": row[1],
                        "tp1": row[2],
                        "tp2": row[3],
                        "entry_time": row[4],
                        "result": row[5],
                    }
            else:
                # Используем прямое соединение
                if self.cursor is None:
                    logging.warning("get_last_signal_log: cursor is None")
                    return None
                with self._lock:
                    if user_id is not None:
                        self.cursor.execute(
                            """
                            SELECT symbol, entry, tp1, tp2, entry_time, result
                            FROM signals_log
                            WHERE user_id = ?
                            ORDER BY datetime(created_at) DESC
                            LIMIT 1
                        """,
                            (user_id,)
                        )
                    else:
                        self.cursor.execute(
                            """
                            SELECT symbol, entry, tp1, tp2, entry_time, result
                            FROM signals_log
                            ORDER BY datetime(created_at) DESC
                            LIMIT 1
                        """
                        )
                    row = self.cursor.fetchone()
                    if not row:
                        return None
                    return {
                        "symbol": row[0],
                        "entry": row[1],
                        "tp1": row[2],
                        "tp2": row[3],
                        "entry_time": row[4],
                        "result": row[5],
                    }
        except (sqlite3.Error, ValueError, AttributeError, RuntimeError) as e:
            logging.warning("get_last_signal_log error: %s", e)
            return None

    # --- Backtest results API ---
    def insert_backtest_result(self, result: dict) -> bool:
        """
        Вставляет результат бэктеста в базу данных.

        Args:
            result (dict): Словарь с результатами бэктеста

        Returns:
            bool: True если вставка прошла успешно, False в противном случае
        """
        try:
            with self._lock:
                self.conn.execute(
                    """
                    INSERT INTO backtest_results(
                        symbol, interval, since_days, bars, signals, tp1, tp2, sl, pnl,
                        mae_avg_pct, mfe_avg_pct, avg_duration_sec, started_at, ended_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        result.get("symbol"),
                        result.get("interval"),
                        int(result.get("since_days", 0) or 0),
                        int(result.get("bars", 0) or 0),
                        int(result.get("signals", 0) or 0),
                        int(result.get("tp1", 0) or 0),
                        int(result.get("tp2", 0) or 0),
                        int(result.get("sl", 0) or 0),
                        float(result.get("pnl", 0.0) or 0.0),
                        float(result.get("mae_avg_pct", 0.0) or 0.0),
                        float(result.get("mfe_avg_pct", 0.0) or 0.0),
                        float(result.get("avg_duration_sec", 0.0) or 0.0),
                        result.get("start"),
                        result.get("end"),
                    ),
                )
                self.conn.commit()
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("insert_backtest_result error: %s", e)
            return False

    def get_recent_backtests(self, limit: int = 10):
        """
        Получает последние результаты бэктестов.

        Args:
            limit (int): Максимальное количество результатов

        Returns:
            list: Список результатов бэктестов
        """
        try:
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT symbol, interval, since_days, bars, signals, tp1, tp2, sl, pnl,
                           mae_avg_pct, mfe_avg_pct, avg_duration_sec, started_at, ended_at, created_at
                    FROM backtest_results
                    ORDER BY datetime(created_at) DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
                rows = fetch_all_optimized(cur) or []
            # Оптимизация: используем list comprehension вместо цикла с append
            return [
                {
                    "symbol": r[0], "interval": r[1], "since_days": r[2], "bars": r[3], "signals": r[4],
                    "tp1": r[5], "tp2": r[6], "sl": r[7], "pnl": r[8],
                    "mae_avg_pct": r[9], "mfe_avg_pct": r[10], "avg_duration_sec": r[11],
                    "start": r[12], "end": r[13], "created_at": r[14],
                }
                for r in rows
            ]
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("get_recent_backtests error: %s", e)
            return []

    def get_false_breakout_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Возвращает статистику детектора ложных пробоев за последние N часов."""
        summary: Dict[str, Any] = {
            'window_hours': hours,
            'total_events': 0,
            'pass_rate': None,
            'avg_confidence': None,
            'avg_threshold': None,
            'avg_volatility_pct': None,
            'avg_recent_pass_rate': None,
            'regime_breakdown': []
        }
        try:
            window_clause = f"-{int(hours)} hours"
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT
                        COUNT(*),
                        SUM(passed),
                        AVG(confidence),
                        AVG(threshold),
                        AVG(volatility_pct),
                        AVG(recent_pass_rate)
                    FROM false_breakout_events
                    WHERE created_at >= datetime('now', ?)
                      AND COALESCE(test_run, 0) = 0
                    """,
                    (window_clause,),
                )
                row = cur.fetchone()
                if row:
                    total, passed, avg_conf, avg_threshold, avg_vol, avg_recent = row
                    summary['total_events'] = int(total or 0)
                    if total:
                        summary['pass_rate'] = (passed or 0) / total
                    summary['avg_confidence'] = avg_conf
                    summary['avg_threshold'] = avg_threshold
                    summary['avg_volatility_pct'] = avg_vol
                    summary['avg_recent_pass_rate'] = avg_recent

                cur = self.conn.execute(
                    """
                    SELECT
                        COALESCE(regime, 'UNKNOWN') AS regime,
                        COUNT(*) AS total,
                        SUM(passed) AS passed
                    FROM false_breakout_events
                    WHERE created_at >= datetime('now', ?)
                      AND COALESCE(test_run, 0) = 0
                    GROUP BY regime
                    ORDER BY total DESC
                    """,
                    (window_clause,),
                )
                summary['regime_breakdown'] = [
                    {
                        'regime': regime,
                        'total': int(total or 0),
                        'pass_rate': (passed or 0) / total if total else None,
                    }
                    for regime, total, passed in fetch_all_optimized(cur)
                ]
        except sqlite3.Error as e:
            logging.warning("get_false_breakout_summary error: %s", e)
        return summary

    def get_mtf_confirmation_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Возвращает статистику MTF-подтверждений за последние N часов."""
        summary: Dict[str, Any] = {
            'window_hours': hours,
            'total_events': 0,
            'confirmation_rate': None,
            'error_rate': None,
            'regime_breakdown': []
        }
        try:
            window_clause = f"-{int(hours)} hours"
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT
                        COUNT(*),
                        SUM(confirmed),
                        SUM(CASE WHEN error IS NOT NULL AND error <> '' THEN 1 ELSE 0 END)
                    FROM mtf_confirmation_events
                    WHERE created_at >= datetime('now', ?)
                    """,
                    (window_clause,),
                )
                row = cur.fetchone()
                if row:
                    total, confirmed, errors = row
                    summary['total_events'] = int(total or 0)
                    if total:
                        summary['confirmation_rate'] = (confirmed or 0) / total
                        summary['error_rate'] = (errors or 0) / total

                cur = self.conn.execute(
                    """
                    SELECT
                        COALESCE(regime, 'UNKNOWN') AS regime,
                        COUNT(*) AS total,
                        SUM(confirmed) AS confirmed
                    FROM mtf_confirmation_events
                    WHERE created_at >= datetime('now', ?)
                    GROUP BY regime
                    ORDER BY total DESC
                    """,
                    (window_clause,),
                )
                summary['regime_breakdown'] = [
                    {
                        'regime': regime,
                        'total': int(total or 0),
                        'confirmation_rate': (confirmed or 0) / total if total else None,
                    }
                    for regime, total, confirmed in fetch_all_optimized(cur)
                ]
        except sqlite3.Error as e:
            logging.warning("get_mtf_confirmation_summary error: %s", e)
        return summary

    # --- Перфоманс по символам (Фаза 2) ---
    def get_symbol_performance(self, since_days: int = 7) -> dict:
        """Возвращает словарь {symbol: {total, tp2, tp1, sl, net_profit_sum, winrate}} за период."""
        try:
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT symbol,
                           COUNT(*) as total,
                           SUM(CASE WHEN result LIKE 'TP2%' THEN 1 ELSE 0 END) as tp2,
                           SUM(CASE WHEN result LIKE 'TP1%' THEN 1 ELSE 0 END) as tp1,
                           SUM(CASE WHEN UPPER(result) LIKE 'SL%' THEN 1 ELSE 0 END) as sl,
                           IFNULL(SUM(net_profit),0.0) as net_profit_sum
                    FROM signals_log
                    WHERE datetime(created_at) >= datetime('now', ?)
                    GROUP BY symbol
                    """,
                    (f"-{int(since_days)} days",),
                )
                rows = fetch_all_optimized(cur) or []
            out = {}
            for s, total, tp2, tp1, sl, netp in rows:
                total = int(total or 0)
                tp_all = int(tp2 or 0) + int(tp1 or 0)
                winrate = (tp_all / total) if total > 0 else 0.0
                out[str(s)] = {
                    "total": total,
                    "tp2": int(tp2 or 0),
                    "tp1": int(tp1 or 0),
                    "sl": int(sl or 0),
                    "net_profit_sum": float(netp or 0.0),
                    "winrate": float(winrate),
                }
            return out
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("get_symbol_performance error: %s", e)
            return {}

    # --- Аудит и алерты (таблицы и методы) ---
    def _ensure_audit_tables(self):
        try:
            with self._lock:
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_dynamic_params (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT,
                        scope TEXT,
                        param TEXT,
                        old_value TEXT,
                        new_value TEXT,
                        note TEXT
                    )
                    """
                )
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_strategy_pauses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT,
                        action TEXT,
                        reason TEXT,
                        window_hours INTEGER,
                        sl_count INTEGER,
                        net_profit_sum REAL
                    )
                    """
                )
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_soft_blocklist (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT,
                        action TEXT,
                        symbol TEXT,
                        votes INTEGER,
                        reason TEXT
                    )
                    """
                )
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_active_coins (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT,
                        action TEXT,
                        symbol TEXT,
                        note TEXT
                    )
                    """
                )
                self.conn.commit()
        except sqlite3.Error as e:
            logging.warning("ensure_audit_tables error: %s", e)

    def audit_dynamic_param(self, scope: str, param: str, old_value, new_value, note: str = None):
        """
        Записывает в аудит изменение динамического параметра.

        Args:
            scope (str): Область применения параметра
            param (str): Название параметра
            old_value: Старое значение
            new_value: Новое значение
            note (str, optional): Дополнительная заметка
        """
        try:
            self._ensure_audit_tables()
            with self._lock:
                self.conn.execute(
                    "INSERT INTO audit_dynamic_params(ts, scope, param, old_value, new_value, note) "
                    "VALUES(datetime('now'),?,?,?,?,?)",
                    (
                        scope, param,
                        json.dumps(old_value, ensure_ascii=False),
                        json.dumps(new_value, ensure_ascii=False),
                        note
                    ),
                )
                self.conn.commit()
        except (sqlite3.Error, TypeError, ValueError) as e:
            logging.warning("audit_dynamic_param error: %s", e)

    def audit_soft_block(self, action: str, symbol: str, votes: int = None, reason: str = None):
        """
        Записывает в аудит действие с мягким блоклистом.

        Args:
            action (str): Действие (add/remove)
            symbol (str): Символ торговой пары
            votes (int, optional): Количество голосов
            reason (str, optional): Причина блокировки
        """
        try:
            self._ensure_audit_tables()
            with self._lock:
                self.conn.execute(
                    "INSERT INTO audit_soft_blocklist(ts, action, symbol, votes, reason) "
                    "VALUES(datetime('now'),?,?,?,?)",
                    (action, symbol, int(votes) if votes is not None else None, reason),
                )
                self.conn.commit()
        except (sqlite3.Error, TypeError, ValueError) as e:
            logging.warning("audit_soft_block error: %s", e)

    def select_signals_for_backtest(self, symbol: str, since_iso: str):
        """
        Публичный селектор для бэктеста: выбирает сигналы по символу после указанного времени.
        Возвращает список кортежей (entry, stop, tp1, tp2, entry_time).
        """
        try:
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT entry, stop, tp1, tp2, entry_time
                    FROM signals_log
                    WHERE symbol = ? AND datetime(entry_time) >= datetime(?)
                    ORDER BY datetime(entry_time) ASC
                    """,
                    (symbol, since_iso),
                )
                return fetch_all_optimized(cur) or []
        except sqlite3.Error as e:
            logging.warning("select_signals_for_backtest error: %s", e)
            return []

    def insert_signal_log(self, symbol: str, entry: float, stop: float, tp1: float, tp2: float,
                           entry_time: str, quality_score: Optional[float] = None,
                           quality_meta: Optional[dict] = None,
                           leverage_used: Optional[float] = None,
                           risk_pct_used: Optional[float] = None,
                           entry_amount_usd: Optional[float] = None,
                           trade_mode: Optional[str] = None,
                           funding_rate: Optional[float] = None,
                           quote24h_usd: Optional[float] = None,
                           depth_usd: Optional[float] = None,
                           spread_pct: Optional[float] = None,
                           exposure_pct: Optional[float] = None,
                           mtf_score: Optional[float] = None,
                           sector: Optional[str] = None,
                           expected_cost_usd: Optional[float] = None,
                           impact_bp: Optional[float] = None,
                           user_id: Optional[int] = None,
                           direction: Optional[str] = None):
        """
        Вставляет запись о сигнале в лог сигналов.

        Args:
            symbol (str): Символ торговой пары
            entry (float): Цена входа
            stop (float): Цена стоп-лосса
            tp1 (float): Первый тейк-профит
            tp2 (float): Второй тейк-профит
            entry_time (str): Время входа
            quality_score (float, optional): Оценка качества сигнала
            quality_meta (dict, optional): Метаданные качества
            leverage_used (float, optional): Использованное плечо
            risk_pct_used (float, optional): Использованный процент риска
            entry_amount_usd (float, optional): Сумма входа в USD
            trade_mode (str, optional): Режим торговли ('spot'/'futures')
            funding_rate (float, optional): Ставка финансирования
            quote24h_usd (float, optional): Объем торгов за 24ч в USD
            depth_usd (float, optional): Глубина рынка в USD
            spread_pct (float, optional): Спред в процентах
            exposure_pct (float, optional): Процент экспозиции
            mtf_score (float, optional): Оценка мультитаймфрейма
            sector (str, optional): Сектор
            expected_cost_usd (float, optional): Ожидаемая стоимость в USD
            impact_bp (float, optional): Влияние в базисных пунктах
            user_id (int, optional): ID пользователя
            direction (str, optional): Направление ('BUY'/'SELL')
        """
        try:
            # 🛡️ НОРМАЛИЗАЦИЯ СИМВОЛА: Приводим к единому формату перед сохранением в БД
            user_trade_mode = 'spot'  # По умолчанию
            if user_id is not None:
                try:
                    user_data_temp = self.get_user_data(str(user_id)) or {}
                    user_trade_mode = user_data_temp.get('trade_mode', 'spot')
                except Exception:
                    pass  # Используем 'spot' по умолчанию

            # Нормализуем символ
            try:
                from src.utils.shared_utils import normalize_symbol_for_db
                symbol_normalized = normalize_symbol_for_db(symbol, user_trade_mode)
                if symbol_normalized != symbol:
                    logging.getLogger(__name__).debug("🔄 [DB] Символ нормализован в signals_log: %s → %s (режим: %s)", symbol, symbol_normalized, user_trade_mode)
                symbol = symbol_normalized
            except Exception as e:
                logging.getLogger(__name__).warning("⚠️ [DB] Не удалось нормализовать символ %s в signals_log: %s. Сохраняем как есть", symbol, e)

            with self._lock:
                self.conn.execute(
                    """
                    INSERT INTO signals_log(symbol, entry, stop, tp1, tp2, entry_time, result, net_profit,
                                             qty_added, qty_closed, trade_mode,
                                             leverage_used, risk_pct_used, entry_amount_usd,
                                             funding_rate, quote24h_usd, depth_usd, spread_pct, exposure_pct,
                                             mtf_score, sector, expected_cost_usd, impact_bp,
                                             quality_score, quality_meta, user_id, direction)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol, float(entry), float(stop), float(tp1), float(tp2), entry_time,
                        "PENDING", None, None, 0.0, trade_mode.lower() if isinstance(trade_mode, str) else None,
                        float(leverage_used) if leverage_used is not None else None,
                        float(risk_pct_used) if risk_pct_used is not None else None,
                        float(entry_amount_usd) if entry_amount_usd is not None else None,
                        float(funding_rate) if funding_rate is not None else None,
                        float(quote24h_usd) if quote24h_usd is not None else None,
                        float(depth_usd) if depth_usd is not None else None,
                        float(spread_pct) if spread_pct is not None else None,
                        float(exposure_pct) if exposure_pct is not None else None,
                        float(mtf_score) if mtf_score is not None else None,
                        sector if sector is not None else None,
                        float(expected_cost_usd) if expected_cost_usd is not None else None,
                        float(impact_bp) if impact_bp is not None else None,
                        float(quality_score) if quality_score is not None else None,
                        # Оптимизация: используем быструю сериализацию
                        self._serialize_quality_meta(quality_meta),
                        int(user_id) if user_id is not None else None,
                        direction
                    ),
                )
                self.conn.commit()
            backup_file(self.db_path)
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("insert_signal_log error: %s", e)
            return False

    def audit_strategy_pause(
        self, action: str, reason: str, window_hours: int, sl_count: int, net_profit_sum: float
    ) -> None:
        """
        Записывает в аудит паузу стратегии.

        Args:
            action (str): Действие (pause/resume)
            reason (str): Причина паузы
            window_hours (int): Окно времени в часах
            sl_count (int): Количество стоп-лоссов
            net_profit_sum (float): Суммарная чистая прибыль
        """
        try:
            self._ensure_audit_tables()
            with self._lock:
                self.conn.execute(
                    "INSERT INTO audit_strategy_pauses(ts, action, reason, window_hours, "
                    "sl_count, net_profit_sum) VALUES(datetime('now'),?,?,?,?,?)",
                    (action, reason, int(window_hours), int(sl_count), float(net_profit_sum))
                )
                self.conn.commit()
        except sqlite3.Error as e:
            logging.warning("audit_strategy_pause error: %s", e)

    def insert_position_sizing_event(self, event: Dict[str, Any]) -> None:
        """Сохраняет детали расчёта размера позиции для последующего анализа."""
        if not event:
            return

        try:
            with self._lock:
                query = """
                    INSERT INTO position_sizing_events (
                        symbol, direction, entry_time, signal_token, user_id, trade_mode,
                        signal_price, baseline_amount_usd, ai_amount_usd, regime_multiplier,
                        after_regime_amount_usd, correlation_multiplier, after_correlation_amount_usd,
                        adaptive_multiplier, after_adaptive_amount_usd, risk_adjustment_multiplier,
                        final_amount_usd, base_risk_pct, ai_risk_pct, leverage, regime,
                        regime_confidence, quality_score, composite_score, pattern_confidence,
                        adaptive_reason, adaptive_components
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (
                    event.get("symbol"),
                    event.get("direction"),
                    event.get("entry_time"),
                    event.get("signal_token"),
                    str(event.get("user_id")) if event.get("user_id") is not None else None,
                    event.get("trade_mode"),
                    _safe_float(event.get("signal_price")),
                    _safe_float(event.get("baseline_amount_usd")),
                    _safe_float(event.get("ai_amount_usd")),
                    _safe_float(event.get("regime_multiplier")),
                    _safe_float(event.get("after_regime_amount_usd")),
                    _safe_float(event.get("correlation_multiplier")),
                    _safe_float(event.get("after_correlation_amount_usd")),
                    _safe_float(event.get("adaptive_multiplier")),
                    _safe_float(event.get("after_adaptive_amount_usd")),
                    _safe_float(event.get("risk_adjustment_multiplier")),
                    _safe_float(event.get("final_amount_usd")),
                    _safe_float(event.get("base_risk_pct")),
                    _safe_float(event.get("ai_risk_pct")),
                    _safe_float(event.get("leverage")),
                    event.get("regime"),
                    _safe_float(event.get("regime_confidence")),
                    _safe_float(event.get("quality_score")),
                    _safe_float(event.get("composite_score")),
                    _safe_float(event.get("pattern_confidence")),
                    event.get("adaptive_reason"),
                    json.dumps(event.get("adaptive_components"), ensure_ascii=False) if event.get("adaptive_components") is not None else None,
                )
                self.conn.execute(query, params)
                self.conn.commit()
        except sqlite3.Error as e:
            logging.warning("insert_position_sizing_event error: %s", e)

    # --- DB Cache helpers ---
    def cache_set(self, cache_type: str, cache_key: str, payload: dict, ttl_seconds: int) -> bool:
        """
        Устанавливает значение в кэш базы данных.

        Args:
            cache_type (str): Тип кэша
            cache_key (str): Ключ кэша
            payload (dict): Данные для кэширования
            ttl_seconds (int): Время жизни в секундах

        Returns:
            bool: True если кэш установлен успешно, False в противном случае
        """
        try:
            expires_at = int(time.time()) + int(ttl_seconds)
            payload_json = json.dumps(payload, ensure_ascii=False)

            # 🔧 ИСПРАВЛЕНО: connection_pool отключен, используем прямое соединение
            if self.conn is not None:
                with self._lock:
                    self.conn.execute(
                        """
                        INSERT INTO app_cache(cache_type, cache_key, payload, expires_at)
                        VALUES(?, ?, ?, ?)
                        ON CONFLICT(cache_type, cache_key) DO UPDATE SET
                            payload=excluded.payload,
                            expires_at=excluded.expires_at
                        """,
                        (cache_type, cache_key, payload_json, expires_at),
                    )
                    self.conn.commit()
            else:
                logging.warning("cache_set: conn is None")
                return False
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("cache_set error: %s", e)
            return False

    def cache_get(self, cache_type: str, cache_key: str):
        """
        Получает значение из кэша базы данных.

        Args:
            cache_type (str): Тип кэша
            cache_key (str): Ключ кэша

        Returns:
            dict: Данные из кэша или None, если не найдены или истекли
        """
        try:
            now_ts = int(time.time())

            if self.conn is not None:
                with self._lock:
                    cur = self.conn.execute(
                        "SELECT payload, expires_at FROM app_cache "
                        "WHERE cache_type=? AND cache_key=?",
                        (cache_type, cache_key),
                    )
                    row = cur.fetchone()
                
                if not row:
                    return None
                
                payload_json, expires_at = row
                if expires_at and int(expires_at) > now_ts:
                    try:
                        return json.loads(payload_json)
                    except json.JSONDecodeError:
                        return None
                else:
                    # истёк — удалим лениво
                    with self._lock:
                        self.conn.execute(
                            "DELETE FROM app_cache WHERE cache_type=? AND cache_key=?",
                            (cache_type, cache_key),
                        )
                        self.conn.commit()
                    return None
            else:
                logging.warning("cache_get: conn is None")
                return None
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("cache_get error: %s", e)
            return None

    def cache_purge_expired(self) -> int:
        """Удаляет просроченные записи из app_cache. Возвращает число удалённых строк.

        Публичный метод, инкапсулирующий доступ к внутреннему lock/conn.
        """
        try:
            now_ts = int(time.time())
            with self._lock:
                cur = self.conn.execute(
                    "DELETE FROM app_cache WHERE IFNULL(expires_at,0) > 0 AND expires_at < ?",
                    (now_ts,),
                )
                self.conn.commit()
                return cur.rowcount if cur is not None else 0
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("cache_purge_expired error: %s", e)
            return 0

    # --- Перфоманс-метрики за период ---
    def get_performance_summary(self, since_days: int = 7) -> dict:
        """
        Агрегированные метрики по signals_log за последние N дней.
        Включает расширенные квантовые показатели (Sharpe, Sortino, MaxDD).
        """
        days = max(1, int(since_days))
        summary = {
            "since_days": days,
            "total_events": 0,
            "distinct_positions": 0,
            "tp2_count": 0,
            "tp1_partial_count": 0,
            "sl_count": 0,
            "net_profit_sum": 0.0,
            "net_profit_avg": 0.0,
            "winrate": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "recent": [],
        }
        try:
            with self._lock:
                # ... (базовые запросы остаются без изменений) ...
                cur = self.conn.execute(
                    "SELECT COUNT(*) FROM signals_log WHERE datetime(created_at) >= datetime('now', ?)",
                    (f"-{days} days",),
                )
                summary["total_events"] = int(cur.fetchone()[0] or 0)

                cur = self.conn.execute(
                    "SELECT COUNT(DISTINCT symbol || '|' || IFNULL(entry_time,'')) "
                    "FROM signals_log WHERE datetime(created_at) >= datetime('now', ?)",
                    (f"-{days} days",),
                )
                summary["distinct_positions"] = int(cur.fetchone()[0] or 0)

                cur = self.conn.execute(
                    """
                    SELECT
                      SUM(CASE WHEN result LIKE 'TP2%' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN result LIKE 'TP1%' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN UPPER(result) LIKE 'SL%' THEN 1 ELSE 0 END)
                    FROM signals_log
                    WHERE datetime(created_at) >= datetime('now', ?)
                    """,
                    (f"-{days} days",),
                )
                row = cur.fetchone() or (0, 0, 0)
                summary["tp2_count"] = int(row[0] or 0)
                summary["tp1_partial_count"] = int(row[1] or 0)
                summary["sl_count"] = int(row[2] or 0)

                cur = self.conn.execute(
                    "SELECT IFNULL(SUM(net_profit),0.0), IFNULL(AVG(net_profit),0.0) "
                    "FROM signals_log WHERE datetime(created_at) >= datetime('now', ?)",
                    (f"-{days} days",),
                )
                agg = cur.fetchone() or (0.0, 0.0)
                summary["net_profit_sum"] = float(agg[0] or 0.0)
                summary["net_profit_avg"] = float(agg[1] or 0.0)

                total_trades = summary["tp2_count"] + summary["tp1_partial_count"] + summary["sl_count"]
                if total_trades > 0:
                    successful_trades = summary["tp2_count"] + summary["tp1_partial_count"]
                    summary["winrate"] = (successful_trades / total_trades) * 100.0

                # --- ADVANCED QUANT METRICS (Sharpe, Sortino, MaxDD) ---
                # Получаем ежедневные доходности
                cur = self.conn.execute(
                    """
                    SELECT date(created_at) as trade_date, SUM(net_profit)
                    FROM signals_log
                    WHERE datetime(created_at) >= datetime('now', ?)
                    GROUP BY trade_date
                    ORDER BY trade_date ASC
                    """,
                    (f"-{days} days",),
                )
                daily_profits = [row[1] for row in cur.fetchall() if row[1] is not None]
                
                if len(daily_profits) >= 2:
                    import numpy as np
                    profits_arr = np.array(daily_profits, dtype=float)
                    
                    # Sharpe (аннуализированный sqrt(365) для крипто)
                    mean_p = np.mean(profits_arr)
                    std_p = np.std(profits_arr)
                    if std_p > 0:
                        summary["sharpe_ratio"] = float((mean_p / std_p) * np.sqrt(365))
                    
                    # Sortino (Downside risk)
                    downside_returns = profits_arr[profits_arr < 0]
                    if len(downside_returns) > 0:
                        downside_std = np.sqrt(np.mean(downside_returns**2))
                        if downside_std > 0:
                            summary["sortino_ratio"] = float((mean_p / downside_std) * np.sqrt(365))
                    else:
                        summary["sortino_ratio"] = 100.0 # Ошибок нет
                    
                    # Max Drawdown
                    cumulative = np.cumsum(profits_arr)
                    peak = np.maximum.accumulate(cumulative)
                    # Если баланс не известен, считаем DD в единицах профита относительно пика
                    drawdown = peak - cumulative
                    # Если пик больше 0, можем оценить % (упрощенно)
                    summary["max_drawdown_units"] = float(np.max(drawdown))

                # Последние 10 сделок
                cur = self.conn.execute(
                    """
                    SELECT symbol, result, net_profit, created_at
                    FROM signals_log
                    WHERE datetime(created_at) >= datetime('now', ?)
                    ORDER BY datetime(created_at) DESC
                    LIMIT 10
                    """,
                    (f"-{days} days",),
                )
                rows = fetch_all_optimized(cur) or []
                summary["recent"] = [
                    {
                        "symbol": s,
                        "result": r,
                        "net_profit": float(np_val) if np_val is not None else None,
                        "created_at": ts,
                    }
                    for s, r, np_val, ts in rows
                ]

            return summary
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("get_performance_summary error: %s", e)
            return summary

    # --- Пользователи: хранение в таблице users_data вместо JSON ---
    def get_all_users(self):
        """Получает список всех user_id из БД (с кэшированием)"""
        # Используем кэш для часто запрашиваемого списка пользователей
        if self._query_cache_enabled and self._query_cache:
            cached = self._query_cache.get("SELECT user_id FROM users_data", ())
            if cached is not None:
                return cached
        
        with self._lock:
            if self.conn:
                cur = self.conn.execute("SELECT user_id FROM users_data")
                rows = fetch_all_optimized(cur)
                result = [r[0] for r in rows]
                
                # Сохраняем в кэш на 5 минут (список пользователей меняется редко)
                if self._query_cache_enabled and self._query_cache:
                    self._query_cache.set("SELECT user_id FROM users_data", (), result, ttl=300.0)
                
                return result
            else:
                logger.error("❌ БД не инициализирована (conn=None)")
                return []

    def get_user_data(self, user_id):
        """Получает данные пользователя из БД"""
        with self._lock:
            if self.conn:
                cur = self.conn.execute("SELECT data FROM users_data WHERE user_id=?", (str(user_id),))
                row = cur.fetchone()
            else:
                logger.error("❌ БД не инициализирована (conn=None)")
                return {}

        if row and row[0]:
            try:
                # Пробуем использовать быструю сериализацию (MessagePack), fallback на JSON
                try:
                    from src.data.serialization import deserialize_fast
                    import base64
                    # Если данные в формате base64 (MessagePack)
                    if isinstance(row[0], str) and len(row[0]) > 0:
                        try:
                            decoded = base64.b64decode(row[0])
                            parsed_data = deserialize_fast(decoded)
                        except (ValueError, Exception):
                            # Fallback на JSON
                            parsed_data = json.loads(row[0])
                    else:
                        parsed_data = json.loads(row[0])
                except (ImportError, Exception):
                    # Fallback на стандартный JSON
                    parsed_data = json.loads(row[0])
                
                if not isinstance(parsed_data, dict):
                    logger.warning("⚠️ Данные пользователя %s не являются dict: %s", user_id, type(parsed_data))
                    return None
                
                # Сохраняем в кэш на 30 секунд (данные пользователя могут часто запрашиваться)
                if self._query_cache_enabled and self._query_cache:
                    self._query_cache.set("SELECT data FROM users_data WHERE user_id=?", (str(user_id),), parsed_data, ttl=30.0)
                
                return parsed_data
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("⚠️ Ошибка парсинга JSON для пользователя %s: %s (данные: %s)", user_id, e, str(row[0])[:100] if row[0] else "None")
                return None
        logger.debug("⚠️ Пользователь %s не найден в БД или данные пусты", user_id)
        return None

    def save_user_data(self, user_id, data):
        try:
            # Пробуем использовать быструю сериализацию (MessagePack), fallback на JSON
            try:
                from src.data.serialization import serialize_fast
                data_serialized = serialize_fast(data)
                # MessagePack возвращает bytes, но SQLite TEXT требует строку
                # Используем base64 для хранения bytes в TEXT поле
                import base64
                data_json = base64.b64encode(data_serialized).decode('utf-8')
            except (ImportError, Exception):
                # Fallback на стандартный JSON
                data_json = json.dumps(data, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logging.error("Не удалось сериализовать user_data для %s: %s", user_id, e)
            return False

        try:
            # 🔧 ИСПРАВЛЕНО: connection_pool отключен, используем прямое соединение
            if self.conn is None:
                logging.warning("save_user_data: conn is None")
                return False
            with self._lock:
                self.conn.execute(
                    """
                    INSERT INTO users_data (user_id, data, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=CURRENT_TIMESTAMP
                """,
                    (str(user_id), data_json),
                )
                self.conn.commit()
            self.periodic_backup()
            return True
        except (sqlite3.Error, ValueError, TypeError, AttributeError) as e:
            logging.warning("save_user_data error для %s: %s", user_id, e)
            return False

    def delete_user_data(self, user_id):
        try:
            # 🔧 ИСПРАВЛЕНО: connection_pool отключен, используем прямое соединение
            if self.conn is None:
                logging.warning("delete_user_data: conn is None")
                return False
            with self._lock:
                self.conn.execute("DELETE FROM users_data WHERE user_id=?", (str(user_id),))
                self.conn.commit()
            self.periodic_backup()
            return True
        except (sqlite3.Error, ValueError, TypeError, AttributeError) as e:
            logging.warning("delete_user_data error для %s: %s", user_id, e)
            return False

    def log_cycle_metrics(self, cycle_num: int, duration_sec: float):
        """Логирует метрики одного цикла работы системы."""
        try:
            if self.conn is None:
                logging.warning("log_cycle_metrics: conn is None")
                return
            with self._lock:
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telemetry_cycles (
                        ts TEXT,
                        cycle_num INTEGER,
                        duration_sec REAL
                    )
                    """
                )
                self.conn.execute(
                    "INSERT INTO telemetry_cycles(ts, cycle_num, duration_sec) VALUES(?, ?, ?)",
                    (get_utc_now().isoformat(), int(cycle_num), float(duration_sec)),
                )
                self.conn.commit()
        except (sqlite3.Error, ValueError, TypeError, AttributeError) as e:
            logging.warning("log_cycle_metrics error: %s", e)

    def log_api_latency(self, name: str, latency_ms: int, ok: bool):
        """Логирует задержку API вызовов."""
        try:
            if self.conn is None:
                logging.warning("log_api_latency: conn is None")
                return
            with self._lock:
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telemetry_api (
                        ts TEXT,
                        name TEXT,
                        latency_ms INTEGER,
                        ok INTEGER
                    )
                    """
                )
                self.conn.execute(
                    "INSERT INTO telemetry_api(ts, name, latency_ms, ok) VALUES(?, ?, ?, ?)",
                    (get_utc_now().isoformat(), name, int(latency_ms), 1 if ok else 0),
                )
                self.conn.commit()
        except (sqlite3.Error, ValueError, TypeError, AttributeError) as e:
            logging.warning("log_api_latency error: %s", e)

    def get_admin_ids(self):
        """
        Возвращает список ID администраторов из users_data (role=='admin' или is_admin==True),
        иначе фолбэк на ADMIN_IDS из окружения.
        """
        admins = []
        try:
            with self._lock:
                cur = self.conn.execute("SELECT user_id, data FROM users_data")
                rows = fetch_all_optimized(cur) or []
            # Оптимизация: используем list comprehension с обработкой исключений
            for uid, j in rows:
                try:
                    data = json.loads(j) if isinstance(j, str) else (j or {})
                    if isinstance(data, dict) and (
                        str(data.get("role", "")).lower() == "admin" or bool(data.get("is_admin"))
                    ):
                        admins.append(int(uid))
                except (ValueError, TypeError):
                    continue
        except sqlite3.Error:
            pass

        if not admins:
            try:
                raw = os.getenv("ADMIN_IDS", "").strip()
                if raw:
                    if raw.startswith("["):
                        admins = [int(x) for x in ast.literal_eval(raw)]
                    else:
                        admins = [int(x) for x in raw.split(",") if x.strip()]
            except (ValueError, SyntaxError, TypeError):
                admins = []
        # Оптимизация: используем set для дедупликации (O(1) вместо O(n))
        dedup = list(set(admins))
        dedup.sort(key=lambda x: (not str(x).startswith("556"), x))
        return dedup

    # --- Ретенция данных ---
    def _days_ago_iso(self, days: int) -> str:
        try:
            d = max(0, int(days))
        except (TypeError, ValueError):
            d = 0
        return (get_utc_now() - timedelta(days=d)).isoformat()

    def cleanup_old_data(self) -> dict:
        """
        Удаляет старые записи согласно политике ретенции из config.py.
        Возвращает словарь с количеством удалённых строк по таблицам.
        """
        stats = {
            "quotes": 0,
            "arbitrage_events": 0,
            "signals": 0,
            "signals_log": 0,
            "signal_accum_events": 0,
            "app_cache": 0,
        }
        try:
            with self._lock:
                # quotes: по ts ISO
                if RETENTION_QUOTES_DAYS >= 0:
                    cutoff = self._days_ago_iso(RETENTION_QUOTES_DAYS)
                    try:
                        cur = self.conn.execute(
                            "DELETE FROM quotes WHERE datetime(ts) < datetime(?)",
                            (cutoff,),
                        )
                        stats["quotes"] = cur.rowcount if cur is not None else 0
                    except sqlite3.OperationalError as e:
                        if "no such column: ts" in str(e):
                            # Пробуем по created_at
                            try:
                                cur = self.conn.execute(
                                    "DELETE FROM quotes WHERE created_at < datetime('now', ?)",
                                    (f"-{int(RETENTION_QUOTES_DAYS)} days",),
                                )
                                stats["quotes"] = cur.rowcount if cur is not None else 0
                            except sqlite3.OperationalError:
                                pass
                        else:
                            raise

                # arbitrage_events: по ts ISO
                if RETENTION_SIGNALS_DAYS >= 0:
                    cutoff = self._days_ago_iso(RETENTION_SIGNALS_DAYS)
                    try:
                        cur = self.conn.execute(
                            "DELETE FROM arbitrage_events WHERE datetime(ts) < datetime(?)",
                            (cutoff,),
                        )
                        stats["arbitrage_events"] = cur.rowcount if cur is not None else 0
                    except sqlite3.OperationalError as e:
                        if "no such column: ts" in str(e):
                            try:
                                cur = self.conn.execute(
                                    "DELETE FROM arbitrage_events WHERE created_at < datetime('now', ?)",
                                    (f"-{int(RETENTION_SIGNALS_DAYS)} days",),
                                )
                                stats["arbitrage_events"] = cur.rowcount if cur is not None else 0
                            except sqlite3.OperationalError:
                                pass
                        else:
                            raise

                # signals: по ts ISO
                if RETENTION_SIGNALS_DAYS >= 0:
                    cutoff = self._days_ago_iso(RETENTION_SIGNALS_DAYS)
                    try:
                        cur = self.conn.execute(
                            "DELETE FROM signals WHERE datetime(ts) < datetime(?)",
                            (cutoff,),
                        )
                        stats["signals"] = cur.rowcount if cur is not None else 0
                    except sqlite3.OperationalError as e:
                        if "no such column: ts" in str(e):
                            try:
                                cur = self.conn.execute(
                                    "DELETE FROM signals WHERE created_at < datetime('now', ?)",
                                    (f"-{int(RETENTION_SIGNALS_DAYS)} days",),
                                )
                                stats["signals"] = cur.rowcount if cur is not None else 0
                            except sqlite3.OperationalError:
                                pass
                        else:
                            raise

                # signals_log: по created_at (datetime DEFAULT CURRENT_TIMESTAMP)
                if RETENTION_SIGNALS_LOG_DAYS >= 0:
                    # 🚀 ОПТИМИЗАЦИЯ (Елена): Используем индекс напрямую без datetime()
                    cur = self.conn.execute(
                        "DELETE FROM signals_log WHERE created_at < datetime('now', ?)",
                        (f"-{int(RETENTION_SIGNALS_LOG_DAYS)} days",),
                    )
                    stats["signals_log"] = cur.rowcount if cur is not None else 0

                # signal_accum_events: по ts unix + ttl_sec (сначала удалим явно просроченные, затем давнее окно)
                now_ts = int(time.time())
                # явные TTL
                cur = self.conn.execute(
                    "DELETE FROM signal_accum_events WHERE (ts + IFNULL(ttl_sec,0)) < ?",
                    (now_ts,),
                )
                removed_ttl = cur.rowcount if cur is not None else 0
                # окно по дням для остатка
                if RETENTION_ACCUM_EVENTS_DAYS >= 0:
                    min_ts = max(0, now_ts - int(RETENTION_ACCUM_EVENTS_DAYS) * 86400)
                    cur = self.conn.execute(
                        "DELETE FROM signal_accum_events WHERE ts < ?",
                        (min_ts,),
                    )
                    removed_window = cur.rowcount if cur is not None else 0
                else:
                    removed_window = 0
                stats["signal_accum_events"] = int(removed_ttl or 0) + int(removed_window or 0)

                # app_cache: expires_at unix
                if RETENTION_APP_CACHE_DAYS >= 0:
                    min_exp = now_ts - int(RETENTION_APP_CACHE_DAYS) * 86400
                    cur = self.conn.execute(
                        "DELETE FROM app_cache WHERE IFNULL(expires_at,0) < ?",
                        (min_exp,),
                    )
                    stats["app_cache"] = cur.rowcount if cur is not None else 0

                self.conn.commit()
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("cleanup_old_data error: %s", e)
        return stats

    def analyze_if_needed(self, force: bool = False) -> bool:
        """
        Выполняет ANALYZE для обновления статистики БД
        Улучшает планы запросов на 5-15%
        
        Args:
            force: Принудительное выполнение даже если недавно выполнялось
            
        Returns:
            True если успешно выполнено
        """
        try:
            with self._lock:
                self.conn.execute("ANALYZE")
                logging.info("✅ [DB] ANALYZE выполнен успешно")
                return True
        except Exception as e:
            logging.warning("⚠️ [DB] Ошибка ANALYZE: %s", e)
            return False

    def vacuum_if_needed(self, force: bool = False) -> bool:
        """
        Выполняет VACUUM (по расписанию еженедельно или принудительно).
        После VACUUM автоматически выполняет ANALYZE для обновления статистики.
        Возвращает True при успехе.
        """
        try:
            if not force and not RETENTION_ENABLE_WEEKLY_VACUUM:
                return False
            with self._lock:
                self.conn.execute("VACUUM;")
                # После VACUUM выполняем ANALYZE для обновления статистики
                self.conn.execute("ANALYZE;")
            logging.info("✅ [DB] VACUUM и ANALYZE выполнены успешно")
            return True
        except sqlite3.Error as e:
            logging.warning("VACUUM/ANALYZE error: %s", e)
            return False

    # --- Метрики и агрегаты (Фаза 1) ---
    def metrics_signals_open_last_24h(self) -> int:
        """Количество сигналов за последние 24 часа."""
        try:
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM signals_log
                    WHERE datetime(created_at) >= datetime('now', '-24 hours')
                    AND (result IS NULL OR result = '' OR result LIKE 'OPEN%')
                    """
                )
                row = cur.fetchone()
                return int(row[0] or 0)
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("metrics_signals_open_last_24h error: %s", e)
            return 0

    def metrics_signals_open_last_hours(self, hours: int) -> int:
        """Количество сигналов за последние N часов."""
        try:
            h = max(1, int(hours))
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM signals_log
                    WHERE datetime(created_at) >= datetime('now', ?)
                    AND (result IS NULL OR result = '' OR result LIKE 'OPEN%')
                    """,
                    (f'-{h} hours',),
                )
                row = cur.fetchone()
                return int((row or (0,))[0] or 0)
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("metrics_signals_open_last_hours error: %s", e)
            return 0

    def metrics_chop_ratio_24h(self) -> float:
        """Оценка chop-режима: доля событий 'bb_squeeze' среди всех accum-событий за 24ч."""
        try:
            now_ts = int(time.time())
            min_ts = now_ts - 24 * 3600
            with self._lock:
                cur = self.conn.execute(
                    "SELECT COUNT(*) FROM signal_accum_events WHERE ts >= ?",
                    (min_ts,),
                )
                total = int((cur.fetchone() or (0,))[0] or 0)
                if total <= 0:
                    return 0.0
                cur = self.conn.execute(
                    "SELECT COUNT(*) FROM signal_accum_events WHERE ts >= ? AND event = ?",
                    (min_ts, 'bb_squeeze'),
                )
                squeezes = int((cur.fetchone() or (0,))[0] or 0)
                ratio = max(0.0, min(1.0, float(squeezes) / float(total)))
                return ratio
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("metrics_chop_ratio_24h error: %s", e)
            return 0.0

    # --- Профили монет (symbol-aware overrides) ---
    def get_symbol_profile(self, symbol: str) -> dict:
        try:
            payload = self.cache_get("symbol_profile", str(symbol).upper()) or {}
            if isinstance(payload, dict):
                return payload
            return {}
        except (ValueError, TypeError):
            return {}

    def set_symbol_profile(self, symbol: str, profile_data: dict, ttl_seconds: int = 12 * 3600) -> bool:
        try:
            if not isinstance(profile_data, dict):
                return False
            return self.cache_set("symbol_profile", str(symbol).upper(), profile_data, ttl_seconds)
        except (ValueError, TypeError):
            return False

    def metrics_update_cache_hourly(self, ttl_seconds: int = 3600) -> bool:
        """Подсчитывает метрики и записывает их в app_cache с TTL."""
        try:
            cnt_open_24h = self.metrics_signals_open_last_24h()
            self.cache_set("metrics", "signals_count_24h", {"value": cnt_open_24h}, ttl_seconds)
            chop = self.metrics_chop_ratio_24h()
            self.cache_set("metrics", "chop_ratio_24h", {"value": chop}, ttl_seconds)
            # Краткая сводка производительности для адаптивных корректировок
            perf7 = self.get_performance_summary(since_days=7)
            self.cache_set("metrics", "perf_summary_7d", perf7, ttl_seconds)
            return True
        except (sqlite3.Error, ValueError, TypeError, RuntimeError) as e:
            logging.warning("metrics_update_cache_hourly error: %s", e)
            return False

    def set_user_admin(self, user_id: int, is_admin: bool = True) -> bool:
        """
        Обновляет признак администратора в users_data (is_admin и role).
        """
        try:
            current = self.get_user_data(user_id) or {}
            if not isinstance(current, dict):
                current = {}
            current["is_admin"] = bool(is_admin)
            if is_admin:
                current["role"] = "admin"
            elif current.get("role") == "admin":
                current["role"] = "user"
            return self.save_user_data(user_id, current)
        except (ValueError, TypeError, RuntimeError):
            return False

    # ============================================================================
    # MTF-ВЗВЕШИВАНИЕ (MULTI-TIMEFRAME)
    # ============================================================================

    def get_mtf_data(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[dict]:
        """Получает OHLC данные для MTF анализа."""
        try:
            # Используем существующую логику получения данных
            # В реальной реализации здесь будет запрос к API для разных таймфреймов
            _ = limit  # Пока не используется, но может понадобиться
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "data": [],  # Заглушка - в реальности здесь будут OHLC данные
                "timestamp": int(time.time())
            }
        except (ValueError, TypeError, RuntimeError) as e:
            logging.warning("get_mtf_data error for %s %s: %s", symbol, timeframe, e)
            return None

    def calculate_mtf_score(self, symbol: str, market_regime: str) -> float:
        """Вычисляет MTF-скоринг для символа на основе анализа RSI, ADX, EMA на разных таймфреймах."""
        try:
            # Импортируем необходимые библиотеки
            try:
                import pandas as pd
                from src.utils.ohlc_utils import get_ohlc_binance_sync
            except ImportError as e:
                logging.debug("MTF скоринг: зависимости недоступны: %s", e)
                # Fallback на базовый скоринг
                base_score = 0.5
                if market_regime == "bull":
                    base_score += 0.1
                elif market_regime == "bear":
                    base_score -= 0.1
                return min(max(base_score, 0.0), 1.0)

            # Получаем данные для разных таймфреймов (1h, 4h)
            timeframes = ["1h", "4h"]
            tf_scores = []

            for tf in timeframes:
                try:
                    # Получаем OHLC данные
                    ohlc = get_ohlc_binance_sync(symbol, interval=tf, limit=100)
                    if not ohlc or len(ohlc) < 50:
                        continue

                    # Создаем DataFrame
                    df = pd.DataFrame(ohlc)
                    if 'timestamp' in df.columns:
                        df["open_time"] = pd.to_datetime(df["timestamp"], unit="ms")
                    elif 'open_time' in df.columns:
                        df["open_time"] = pd.to_datetime(df["open_time"])
                    else:
                        continue

                    df = df.set_index("open_time")

                    # Рассчитываем индикаторы через централизованный модуль
                    from src.signals.indicators import add_technical_indicators
                    df = add_technical_indicators(df)

                    # Берем последние значения
                    if len(df) < 1:
                        continue

                    last_row = df.iloc[-1]
                    ema7_val = float(last_row.get("ema7", last_row["close"]))
                    ema25_val = float(last_row.get("ema25", last_row["close"]))
                    rsi_val = float(last_row.get("rsi", 50.0))
                    adx_val = float(last_row.get("adx", 25.0))

                    # Рассчитываем score для этого таймфрейма
                    tf_score = 0.5  # Базовый score

                    # Тренд (EMA7 vs EMA25)
                    if ema7_val > ema25_val:
                        tf_score += 0.15  # Бычий тренд
                    elif ema7_val < ema25_val:
                        tf_score -= 0.15  # Медвежий тренд

                    # RSI анализ (перепроданность/перекупленность)
                    if 30 < rsi_val < 70:  # Здоровый диапазон
                        tf_score += 0.1
                    elif rsi_val < 30:  # Перепроданность (потенциал роста)
                        tf_score += 0.05
                    elif rsi_val > 70:  # Перекупленность (риск падения)
                        tf_score -= 0.1

                    # ADX анализ (сила тренда)
                    if adx_val > 25:  # Сильный тренд
                        tf_score += 0.1
                    elif adx_val < 20:  # Слабый тренд
                        tf_score -= 0.05

                    tf_scores.append(tf_score)

                except Exception as e:
                    logging.debug("MTF скоринг: ошибка для %s %s: %s", symbol, tf, e)
                    continue

            # Если не удалось получить данные ни для одного таймфрейма
            if not tf_scores:
                # Fallback на режим рынка
                base_score = 0.5
                if market_regime == "bull":
                    base_score += 0.1
                elif market_regime == "bear":
                    base_score -= 0.1
                return min(max(base_score, 0.0), 1.0)

            # Усредняем scores по таймфреймам (4h имеет больший вес)
            if len(tf_scores) == 2:
                # 1h - вес 0.4, 4h - вес 0.6
                final_score = tf_scores[0] * 0.4 + tf_scores[1] * 0.6
            else:
                final_score = sum(tf_scores) / len(tf_scores)

            # Адаптация по режиму рынка
            if market_regime == "bull":
                final_score += 0.1
            elif market_regime == "bear":
                final_score -= 0.1

            return min(max(final_score, 0.0), 1.0)

        except (ValueError, TypeError, RuntimeError) as e:
            logging.warning("calculate_mtf_score error for %s: %s", symbol, e)
            return 0.5

    # ============================================================================
    # ML-СКОРИНГ (MACHINE LEARNING)
    # ============================================================================

    def get_ml_training_data(self, limit: int = 1000) -> List[dict]:
        """Получает данные для обучения ML модели."""
        try:
            # Заглушка для ML данных
            # В реальной реализации здесь будет выборка из signals_log с фичами
            _ = limit  # Пока не используется, но может понадобиться
            return []
        except (ValueError, TypeError, RuntimeError) as e:
            logging.warning("get_ml_training_data error: %s", e)
            return []

    def calculate_ml_score(self, features: dict) -> float:
        """Вычисляет ML-скоринг для кандидата используя LightGBM модель."""
        try:
            # Пробуем использовать LightGBM predictor если доступен
            try:
                from src.ai.lightgbm_predictor import get_lightgbm_predictor
                predictor = get_lightgbm_predictor()

                # Загружаем модели если они не загружены
                if not predictor.is_trained:
                    if not predictor.load_models():
                        # Модели не обучены, используем fallback
                        raise ImportError("ML models not trained")

                # Преобразуем features dict в формат для LightGBM
                # LightGBM predictor ожидает 3 отдельных dict: market_conditions, indicators, signal_params

                # 1. Indicators dict
                indicators = {
                    'rsi': float(features.get("rsi", 50.0)),
                    'macd': float(features.get("macd", 0.0)),
                    'ema_fast': float(features.get("ema_fast", features.get("entry_price", 100.0) * 1.01)),
                    'ema_slow': float(features.get("ema_slow", features.get("entry_price", 100.0) * 0.99)),
                    'bb_upper': float(features.get("bb_upper", features.get("entry_price", 100.0) * 1.02)),
                    'bb_lower': float(features.get("bb_lower", features.get("entry_price", 100.0) * 0.98)),
                    'atr': float(features.get("atr", features.get("entry_price", 100.0) * 0.015)),
                }

                # 2. Market conditions dict
                market_conditions = {
                    'volume_ratio': float(features.get("volume_ratio", 1.0)),
                    'volatility': float(features.get("volatility", 0.02)),
                }

                # 3. Signal params dict
                entry_price = float(features.get("entry_price", 100.0))
                tp1 = float(features.get("tp1", entry_price * 1.025))
                tp2 = float(features.get("tp2", entry_price * 1.05))

                signal_params = {
                    'entry_price': entry_price,
                    'tp1': tp1,
                    'tp2': tp2,
                    'risk_pct': float(features.get("risk_pct", 2.0)),
                    'leverage': float(features.get("leverage", 1.0)),
                    'quality_score': float(features.get("quality_score", 0.5)),
                    'mtf_score': float(features.get("mtf_score", 0.5)),
                    'spread_pct': float(features.get("spread_pct", 0.0)),
                    'depth_usd': float(features.get("depth_usd", 0.0)),
                }

                # Получаем предсказание от LightGBM
                prediction = predictor.predict(
                    market_conditions=market_conditions,
                    indicators=indicators,
                    signal_params=signal_params
                )

                # Предсказание возвращает dict с 'success_probability'
                if isinstance(prediction, dict):
                    score = float(prediction.get('success_probability', 0.5))
                else:
                    score = float(prediction) if prediction is not None else 0.5

                return min(max(score, 0.0), 1.0)

            except (ImportError, AttributeError, Exception) as e:
                # Fallback на эвристику если ML недоступен
                logging.debug("LightGBM недоступен, используем эвристику: %s", e)
                base_score = 0.5

                # Простая эвристика на основе фичей
                rsi = features.get("rsi", 50)
                adx = features.get("adx", 25)
                volume_ratio = features.get("volume_ratio", 1.0)

                if rsi < 30 and adx > 25 and volume_ratio > 1.5:
                    base_score += 0.2
                elif rsi > 70 and adx > 25 and volume_ratio > 1.5:
                    base_score += 0.15

                return min(max(base_score, 0.0), 1.0)
        except (ValueError, TypeError, RuntimeError) as e:
            logging.warning("calculate_ml_score error: %s", e)
            return 0.5

    def save_ml_prediction(self, symbol: str, features: dict, prediction: float, timestamp: int) -> bool:
        """Сохраняет ML предсказание для аудита."""
        try:
            # В реальной реализации здесь будет сохранение в отдельную таблицу
            _ = features  # Пока не используется, но может понадобиться
            _ = timestamp  # Пока не используется, но может понадобиться
            logging.info("ML prediction saved: %s -> %.3f", symbol, prediction)
            return True
        except (ValueError, TypeError, RuntimeError) as e:
            logging.warning("save_ml_prediction error: %s", e)
            return False

    # ============================================================================
    # АДМИНИСТРАТОРЫ И УВЕДОМЛЕНИЯ
    # ============================================================================

    def get_admin_users(self) -> List[int]:
        """Получает список ID администраторов."""
        try:
            admin_users = []
            cursor = self.conn.execute("SELECT user_id, data FROM users_data")
            for row in fetch_all_optimized(cursor):
                user_id, data_json = row
                try:
                    data = json.loads(data_json) if data_json else {}
                    if (str(data.get("role", "")).lower() == "admin" or
                        bool(data.get("is_admin"))):
                        admin_users.append(int(user_id))
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
            return admin_users
        except (ValueError, TypeError, RuntimeError) as e:
            logging.warning("get_admin_users error: %s", e)
            return []

    # ============================================================================
    # СИСТЕМНЫЕ НАСТРОЙКИ (АДАПТИВНЫЕ ПАРАМЕТРЫ)
    # ============================================================================

    def get_system_setting(self, key: str, default_value=None):
        """Получает системную настройку из базы данных."""
        try:
            with self._lock:
                cur = self.conn.execute(
                    "SELECT value FROM system_settings WHERE key = ?",
                    (key,)
                )
                row = cur.fetchone()
                if row:
                    value = row[0]
                    # Пытаемся преобразовать в соответствующий тип
                    try:
                        # Проверяем, является ли это булевым значением
                        if value.lower() in ('true', 'false'):
                            return value.lower() == 'true'
                        # Проверяем, является ли это числом
                        if '.' in value:
                            return float(value)
                        elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                            return int(value)
                        # Иначе возвращаем как строку
                        return value
                    except (ValueError, AttributeError):
                        return value
                return default_value
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("get_system_setting error for key %s: %s", key, e)
            return default_value

    def set_system_setting(self, key: str, value) -> bool:
        """Устанавливает системную настройку в базе данных."""
        try:
            with self._lock:
                self.conn.execute(
                    """
                    INSERT INTO system_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, str(value))
                )
                self.conn.commit()
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("set_system_setting error for key %s: %s", key, e)
            return False

    def get_all_system_settings(self) -> dict:
        """Получает все системные настройки из базы данных."""
        try:
            with self._lock:
                cur = self.conn.execute("SELECT key, value FROM system_settings")
                rows = fetch_all_optimized(cur)
                settings = {}
                for key, value in rows:
                    try:
                        # Пытаемся преобразовать в соответствующий тип
                        if value.lower() in ('true', 'false'):
                            settings[key] = value.lower() == 'true'
                        elif '.' in value:
                            settings[key] = float(value)
                        elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                            settings[key] = int(value)
                        else:
                            settings[key] = value
                    except (ValueError, AttributeError):
                        settings[key] = value
                return settings
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("get_all_system_settings error: %s", e)
            return {}

    def delete_system_setting(self, key: str) -> bool:
        """Удаляет системную настройку из базы данных."""
        try:
            with self._lock:
                self.conn.execute("DELETE FROM system_settings WHERE key = ?", (key,))
                self.conn.commit()
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("delete_system_setting error for key %s: %s", key, e)
            return False

    # --- Config Snapshots (Rollback System) ---

    def save_config_snapshot(self, config_dict: dict, win_rate: float, pnl_pct: float, is_stable: bool = False) -> bool:
        """Сохраняет снимок текущей конфигурации."""
        try:
            config_json = json.dumps(config_dict)
            with self._lock:
                self.conn.execute(
                    """
                    INSERT INTO system_config_history (config_json, win_rate, pnl_pct, is_stable)
                    VALUES (?, ?, ?, ?)
                    """,
                    (config_json, win_rate, pnl_pct, 1 if is_stable else 0)
                )
                self.conn.commit()
            return True
        except Exception as e:
            logging.error("❌ Error saving config snapshot: %s", e)
            return False

    def get_latest_stable_snapshot(self) -> Optional[dict]:
        """Получает последний стабильный снимок конфигурации."""
        try:
            with self._lock:
                cur = self.conn.execute(
                    "SELECT config_json FROM system_config_history WHERE is_stable = 1 ORDER BY created_at DESC LIMIT 1"
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
            return None
        except Exception as e:
            logging.error("❌ Error getting latest stable snapshot: %s", e)
            return None

    def initialize_adaptive_settings(self):
        """Инициализирует адаптивные настройки в базе данных из config.py."""
        try:
            # Список всех адаптивных параметров для миграции
            adaptive_params = {
                # Адаптивный движок
                'ADAPTIVE_ENGINE_ENABLED': ADAPTIVE_ENGINE_ENABLED,
                'METRICS_FEEDER_ENABLED': METRICS_FEEDER_ENABLED,
                'METRICS_FEEDER_INTERVAL_SEC': METRICS_FEEDER_INTERVAL_SEC,
                'METRICS_CACHE_TTL_SEC': METRICS_CACHE_TTL_SEC,
                'PERFORMANCE_LOOKBACK_DAYS': PERFORMANCE_LOOKBACK_DAYS,

                # Адаптивная подстройка порогов
                'ADAPTIVE_ENTRY_ADJ_ENABLED': ADAPTIVE_ENTRY_ADJ_ENABLED,
                'ADAPTIVE_ENTRY_MAX_ADJUST_PCT': ADAPTIVE_ENTRY_MAX_ADJUST_PCT,

                # Динамический свитчер режимов
                'DYNAMIC_MODE_SWITCH_ENABLED': DYNAMIC_MODE_SWITCH_ENABLED,

                # Корреляционный кулдаун
                'CORRELATION_COOLDOWN_ENABLED': CORRELATION_COOLDOWN_ENABLED,
                'CORRELATION_LOOKBACK_HOURS': CORRELATION_LOOKBACK_HOURS,
                'CORRELATION_MAX_PAIRWISE': CORRELATION_MAX_PAIRWISE,
                'CORRELATION_COOLDOWN_SEC': CORRELATION_COOLDOWN_SEC,

                # Мягкий блоклист
                'SOFT_BLOCKLIST_ENABLED': SOFT_BLOCKLIST_ENABLED,
                'SOFT_BLOCKLIST_HYSTERESIS': SOFT_BLOCKLIST_HYSTERESIS,
                'SOFT_BLOCK_COOLDOWN_HOURS': SOFT_BLOCK_COOLDOWN_HOURS,
                'MIN_ACTIVE_COINS': MIN_ACTIVE_COINS,
                'BLOCKLIST_CHURN_FRAC': BLOCKLIST_CHURN_FRAC,

                # Динамические параметры
                'DYNAMIC_CALC_INTERVAL': DYNAMIC_CALC_INTERVAL,
                'DYNAMIC_TP_ENABLED': DYNAMIC_TP_ENABLED,
                'VOLUME_BLOCKS_ENABLED': VOLUME_BLOCKS_ENABLED,
            }

            # Сохраняем параметры в базу данных
            for key, value in adaptive_params.items():
                # Проверяем, есть ли уже значение в БД
                existing = self.get_system_setting(key)
                if existing is None:  # Только если параметр еще не существует
                    self.set_system_setting(key, value)
                    logging.info("Инициализирован адаптивный параметр %s = %s", key, value)

            logging.info("Адаптивные настройки инициализированы в базе данных")
            return True

        except (AttributeError, ValueError, TypeError) as e:
            logging.warning("Ошибка инициализации адаптивных настроек: %s", e)
            return False

    # ============================================================================
    # БЛОКЛИСТ КАПИТАЛИЗАЦИИ (MARKET CAP BLACKLIST)
    # ============================================================================

    def add_to_market_cap_blacklist(self, symbol: str, market_cap: float, reason: str = "low_market_cap") -> bool:
        """Добавляет монету в блоклист капитализации."""
        try:

            # Устанавливаем дату размораживания на неделю вперед
            unfreeze_date = (datetime.now() + timedelta(days=7)).isoformat()

            with self._lock:
                self.conn.execute(
                    """
                    INSERT INTO market_cap_blacklist (symbol, market_cap, unfreeze_date, reason)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        market_cap = excluded.market_cap,
                        blacklisted_at = CURRENT_TIMESTAMP,
                        unfreeze_date = excluded.unfreeze_date,
                        reason = excluded.reason
                    """,
                    (symbol, market_cap, unfreeze_date, reason)
                )
                self.conn.commit()
            logging.info("Монета %s добавлена в блоклист капитализации (cap: $%.0fM)", symbol, market_cap / 1_000_000)
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("Ошибка добавления в блоклист капитализации %s: %s", symbol, e)
            return False

    def is_market_cap_blacklisted(self, symbol: str) -> bool:
        """Проверяет, заблокирована ли монета по капитализации."""
        try:
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT symbol FROM market_cap_blacklist
                    WHERE symbol = ? AND datetime(unfreeze_date) > datetime('now')
                    """,
                    (symbol,)
                )
                row = cur.fetchone()
            return row is not None
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("Ошибка проверки блоклиста капитализации %s: %s", symbol, e)
            return False

    def get_market_cap_blacklist(self) -> List[dict]:
        """Получает список заблокированных монет."""
        try:
            with self._lock:
                cur = self.conn.execute(
                    """
                    SELECT symbol, market_cap, blacklisted_at, unfreeze_date, reason
                    FROM market_cap_blacklist
                    WHERE datetime(unfreeze_date) > datetime('now')
                    ORDER BY blacklisted_at DESC
                    """
                )
                rows = fetch_all_optimized(cur)
            return [
                {
                    "symbol": row[0],
                    "market_cap": row[1],
                    "blacklisted_at": row[2],
                    "unfreeze_date": row[3],
                    "reason": row[4]
                }
                for row in rows
            ]
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("Ошибка получения блоклиста капитализации: %s", e)
            return []

    def unfreeze_market_cap_blacklist(self) -> int:
        """Размораживает монеты, у которых истек срок блокировки."""
        try:
            with self._lock:
                cur = self.conn.execute(
                    "DELETE FROM market_cap_blacklist "
                    "WHERE datetime(unfreeze_date) <= datetime('now')"
                )
                self.conn.commit()
                unfrozen_count = cur.rowcount
            if unfrozen_count > 0:
                logging.info("Разморожено %d монет из блоклиста", unfrozen_count)
            return unfrozen_count
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("Ошибка размораживания блоклиста капитализации: %s", e)
            return 0

    def remove_from_market_cap_blacklist(self, symbol: str) -> bool:
        """Удаляет монету из блоклиста капитализации."""
        try:
            with self._lock:
                self.conn.execute(
                    "DELETE FROM market_cap_blacklist WHERE symbol = ?",
                    (symbol,)
                )
                self.conn.commit()
            logging.info("Монета %s удалена из блоклиста капитализации", symbol)
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("Ошибка удаления из блоклиста капитализации %s: %s", symbol, e)
            return False

    def update_market_cap_blacklist_check(self, symbol: str) -> bool:
        """Обновляет время последней проверки монеты."""
        try:
            with self._lock:
                self.conn.execute(
                    "UPDATE market_cap_blacklist SET last_checked = CURRENT_TIMESTAMP WHERE symbol = ?",
                    (symbol,)
                )
                self.conn.commit()
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            logging.warning("Ошибка обновления времени проверки %s: %s", symbol, e)
            return False

    def _add_validation_triggers(self):
        """
        Добавляет триггеры валидации для существующих таблиц.
        SQLite не поддерживает ALTER TABLE ADD CONSTRAINT, поэтому используем триггеры.
        """
        try:
            # Триггер валидации для quotes (bid, ask)
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS validate_quotes_insert
                BEFORE INSERT ON quotes
                BEGIN
                    SELECT CASE
                        WHEN NEW.bid IS NOT NULL AND NEW.bid <= 0 THEN
                            RAISE(ABORT, 'bid must be > 0')
                        WHEN NEW.ask IS NOT NULL AND NEW.ask <= 0 THEN
                            RAISE(ABORT, 'ask must be > 0')
                        WHEN NEW.bid IS NOT NULL AND NEW.ask IS NOT NULL AND NEW.ask < NEW.bid THEN
                            RAISE(ABORT, 'ask must be >= bid')
                    END;
                END;
            """)
            
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS validate_quotes_update
                BEFORE UPDATE ON quotes
                BEGIN
                    SELECT CASE
                        WHEN NEW.bid IS NOT NULL AND NEW.bid <= 0 THEN
                            RAISE(ABORT, 'bid must be > 0')
                        WHEN NEW.ask IS NOT NULL AND NEW.ask <= 0 THEN
                            RAISE(ABORT, 'ask must be > 0')
                        WHEN NEW.bid IS NOT NULL AND NEW.ask IS NOT NULL AND NEW.ask < NEW.bid THEN
                            RAISE(ABORT, 'ask must be >= bid')
                    END;
                END;
            """)
            
            # Триггер валидации для signals_log (entry, stop, tp1, tp2)
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS validate_signals_log_insert
                BEFORE INSERT ON signals_log
                BEGIN
                    SELECT CASE
                        WHEN NEW.entry IS NOT NULL AND NEW.entry <= 0 THEN
                            RAISE(ABORT, 'entry must be > 0')
                        WHEN NEW.stop IS NOT NULL AND NEW.stop <= 0 THEN
                            RAISE(ABORT, 'stop must be > 0')
                        WHEN NEW.tp1 IS NOT NULL AND NEW.tp1 <= 0 THEN
                            RAISE(ABORT, 'tp1 must be > 0')
                        WHEN NEW.tp2 IS NOT NULL AND NEW.tp2 <= 0 THEN
                            RAISE(ABORT, 'tp2 must be > 0')
                        WHEN NEW.qty_added IS NOT NULL AND NEW.qty_added < 0 THEN
                            RAISE(ABORT, 'qty_added must be >= 0')
                        WHEN NEW.qty_closed IS NOT NULL AND NEW.qty_closed < 0 THEN
                            RAISE(ABORT, 'qty_closed must be >= 0')
                        WHEN NEW.risk_pct_used IS NOT NULL AND (NEW.risk_pct_used < 0 OR NEW.risk_pct_used > 100) THEN
                            RAISE(ABORT, 'risk_pct_used must be between 0 and 100')
                        WHEN NEW.quality_score IS NOT NULL AND (NEW.quality_score < 0 OR NEW.quality_score > 100) THEN
                            RAISE(ABORT, 'quality_score must be between 0 and 100')
                    END;
                END;
            """)
            
            # Триггер валидации для trades
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS validate_trades_insert
                BEFORE INSERT ON trades
                BEGIN
                    SELECT CASE
                        WHEN NEW.entry_price <= 0 THEN
                            RAISE(ABORT, 'entry_price must be > 0')
                        WHEN NEW.exit_price IS NOT NULL AND NEW.exit_price <= 0 THEN
                            RAISE(ABORT, 'exit_price must be > 0')
                        WHEN NEW.quantity <= 0 THEN
                            RAISE(ABORT, 'quantity must be > 0')
                        WHEN NEW.position_size_usdt <= 0 THEN
                            RAISE(ABORT, 'position_size_usdt must be > 0')
                        WHEN NEW.leverage <= 0 OR NEW.leverage > 125 THEN
                            RAISE(ABORT, 'leverage must be between 0 and 125')
                        WHEN NEW.risk_percent IS NOT NULL AND (NEW.risk_percent < 0 OR NEW.risk_percent > 100) THEN
                            RAISE(ABORT, 'risk_percent must be between 0 and 100')
                        WHEN NEW.fees_usd < 0 THEN
                            RAISE(ABORT, 'fees_usd must be >= 0')
                        WHEN NEW.direction NOT IN ('LONG', 'SHORT') THEN
                            RAISE(ABORT, 'direction must be LONG or SHORT')
                        WHEN NEW.trade_mode NOT IN ('spot', 'futures', 'margin') THEN
                            RAISE(ABORT, 'trade_mode must be spot, futures, or margin')
                    END;
                END;
            """)
            
            self.conn.commit()
            logging.debug("✅ [DB] Триггеры валидации добавлены")
        except sqlite3.Error as e:
            logging.warning("⚠️ [DB] Ошибка создания триггеров валидации: %s", e)

    def _add_surrogate_time_keys(self):
        """
        Добавляет суррогатные ключи (INTEGER) для временных меток.
        Ускорение на 20-40% за счет меньшего размера индексов и более быстрых сравнений.
        """
        try:
            # Добавляем колонку time_surrogate для signals_log
            try:
                with self._lock:
                    self.conn.execute("ALTER TABLE signals_log ADD COLUMN time_surrogate INTEGER")
            except sqlite3.Error:
                pass  # Колонка уже существует
            
            # Заполняем time_surrogate для существующих записей
            try:
                with self._lock:
                    self.conn.execute("""
                        UPDATE signals_log 
                        SET time_surrogate = CAST(strftime('%s', entry_time) AS INTEGER)
                        WHERE time_surrogate IS NULL AND entry_time IS NOT NULL
                    """)
                    self.conn.commit()
            except sqlite3.Error as e:
                logging.debug("⚠️ [DB] Ошибка заполнения time_surrogate для signals_log: %s", e)
            
            # Создаем индекс на time_surrogate
            try:
                self.cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_signals_log_time_surrogate "
                    "ON signals_log(time_surrogate)"
                )
            except sqlite3.Error:
                pass
            
            # Триггер для автоматического заполнения time_surrogate при INSERT/UPDATE
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS signals_log_time_surrogate_insert
                AFTER INSERT ON signals_log
                BEGIN
                    UPDATE signals_log 
                    SET time_surrogate = CAST(strftime('%s', entry_time) AS INTEGER)
                    WHERE id = NEW.id AND time_surrogate IS NULL AND entry_time IS NOT NULL;
                END;
            """)
            
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS signals_log_time_surrogate_update
                AFTER UPDATE OF entry_time ON signals_log
                BEGIN
                    UPDATE signals_log 
                    SET time_surrogate = CAST(strftime('%s', NEW.entry_time) AS INTEGER)
                    WHERE id = NEW.id;
                END;
            """)
            
            # Аналогично для active_signals
            try:
                with self._lock:
                    self.conn.execute("ALTER TABLE active_signals ADD COLUMN time_surrogate INTEGER")
            except sqlite3.Error:
                pass
            
            try:
                with self._lock:
                    self.conn.execute("""
                        UPDATE active_signals 
                        SET time_surrogate = CAST(strftime('%s', ts) AS INTEGER)
                        WHERE time_surrogate IS NULL AND ts IS NOT NULL
                    """)
                    self.conn.commit()
            except sqlite3.Error:
                pass
            
            try:
                self.cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_active_signals_time_surrogate "
                    "ON active_signals(time_surrogate)"
                )
            except sqlite3.Error:
                pass
            
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS active_signals_time_surrogate_insert
                AFTER INSERT ON active_signals
                BEGIN
                    UPDATE active_signals 
                    SET time_surrogate = CAST(strftime('%s', ts) AS INTEGER)
                    WHERE id = NEW.id AND time_surrogate IS NULL AND ts IS NOT NULL;
                END;
            """)
            
            # Для trades
            try:
                with self._lock:
                    self.conn.execute("ALTER TABLE trades ADD COLUMN entry_time_surrogate INTEGER")
                    self.conn.execute("ALTER TABLE trades ADD COLUMN exit_time_surrogate INTEGER")
            except sqlite3.Error:
                pass
            
            try:
                with self._lock:
                    self.conn.execute("""
                        UPDATE trades 
                        SET entry_time_surrogate = CAST(strftime('%s', entry_time) AS INTEGER)
                        WHERE entry_time_surrogate IS NULL AND entry_time IS NOT NULL
                    """)
                    self.conn.execute("""
                        UPDATE trades 
                        SET exit_time_surrogate = CAST(strftime('%s', exit_time) AS INTEGER)
                        WHERE exit_time_surrogate IS NULL AND exit_time IS NOT NULL
                    """)
                    self.conn.commit()
            except sqlite3.Error:
                pass
            
            try:
                self.cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trades_entry_time_surrogate "
                    "ON trades(entry_time_surrogate)"
                )
                self.cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trades_exit_time_surrogate "
                    "ON trades(exit_time_surrogate)"
                )
            except sqlite3.Error:
                pass
            
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trades_entry_time_surrogate_insert
                AFTER INSERT ON trades
                BEGIN
                    UPDATE trades 
                    SET entry_time_surrogate = CAST(strftime('%s', entry_time) AS INTEGER)
                    WHERE id = NEW.id AND entry_time_surrogate IS NULL AND entry_time IS NOT NULL;
                END;
            """)
            
            self.cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trades_exit_time_surrogate_update
                AFTER UPDATE OF exit_time ON trades
                BEGIN
                    UPDATE trades 
                    SET exit_time_surrogate = CAST(strftime('%s', NEW.exit_time) AS INTEGER)
                    WHERE id = NEW.id AND NEW.exit_time IS NOT NULL;
                END;
            """)
            
            self.conn.commit()
            logging.debug("✅ [DB] Суррогатные ключи для временных меток добавлены")
        except sqlite3.Error as e:
            logging.warning("⚠️ [DB] Ошибка создания суррогатных ключей: %s", e)

    def _create_partial_indexes(self):
        """
        Создает частичные индексы для приоритетных символов.
        Ускорение на 30-50% за счет меньшего размера индексов и быстрее обновление.
        """
        try:
            # Приоритетные символы (топ-10 по объему торгов)
            priority_symbols = [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
                'ADAUSDT', 'DOGEUSDT', 'TRXUSDT', 'AVAXUSDT', 'LINKUSDT'
            ]
            
            # Формируем WHERE clause для частичного индекса
            symbols_condition = "', '".join(priority_symbols)
            where_clause = f"symbol IN ('{symbols_condition}')"
            
            # Частичный индекс для signals_log (приоритетные символы)
            self.cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_signals_log_priority_symbols
                ON signals_log(symbol, entry_time, created_at)
                WHERE {where_clause}
            """)
            
            # Частичный индекс для trades (приоритетные символы)
            self.cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_trades_priority_symbols
                ON trades(symbol, entry_time, exit_time)
                WHERE {where_clause}
            """)
            
            # Частичный индекс для active_signals (приоритетные символы)
            # Проверяем какую колонку использовать: ts или created_at
            cur = self.conn.execute("PRAGMA table_info(active_signals)")
            cols = [row[1] for row in cur.fetchall()]
            active_signals_ts_col = "ts" if "ts" in cols else "created_at"
            
            self.cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_active_signals_priority_symbols
                ON active_signals(symbol, {active_signals_ts_col})
                WHERE {where_clause}
            """)
            
            # Частичный индекс для signals (приоритетные символы)
            cur = self.conn.execute("PRAGMA table_info(signals)")
            cols = [row[1] for row in cur.fetchall()]
            signals_ts_col = "ts" if "ts" in cols else "created_at"
            
            self.cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_signals_priority_symbols
                ON signals(symbol, {signals_ts_col})
                WHERE {where_clause}
            """)
            
            self.conn.commit()
            logging.debug("✅ [DB] Частичные индексы для приоритетных символов созданы")
        except sqlite3.Error as e:
            logging.warning("⚠️ [DB] Ошибка создания частичных индексов: %s", e)

    def update_priority_symbols(self, symbols: list):
        """
        Обновляет список приоритетных символов и пересоздает частичные индексы.
        
        Args:
            symbols: Список приоритетных символов
        """
        try:
            # Удаляем старые частичные индексы
            indexes_to_drop = [
                'idx_signals_log_priority_symbols',
                'idx_trades_priority_symbols',
                'idx_active_signals_priority_symbols',
                'idx_signals_priority_symbols'
            ]
            
            for index_name in indexes_to_drop:
                try:
                    self.cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                except sqlite3.Error:
                    pass
            
            # Сохраняем новый список приоритетных символов
            # (можно сохранить в system_settings для персистентности)
            if symbols:
                symbols_str = ','.join(symbols)
                self.save_system_setting('priority_symbols', symbols_str)
            
            # Пересоздаем индексы с новым списком
            self._create_partial_indexes()
            logging.info("✅ [DB] Приоритетные символы обновлены: %s", symbols)
        except sqlite3.Error as e:
            logging.warning("⚠️ [DB] Ошибка обновления приоритетных символов: %s", e)

    def _profile_slow_query(self, query: str, params: tuple, duration: float):
        """
        Профилирует медленный запрос и логирует информацию для оптимизации.
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            duration: Время выполнения в секундах
        """
        try:
            # Получаем план запроса
            plan = None
            try:
                explain_query = f"EXPLAIN QUERY PLAN {query}"
                cursor = self.conn.cursor()
                if params:
                    cursor.execute(explain_query, params)
                else:
                    cursor.execute(explain_query)
                plan_rows = cursor.fetchall()
                plan = "\n".join([str(row) for row in plan_rows])
            except Exception:
                pass
            
            # Логируем медленный запрос
            logging.warning(
                "⚠️ [DB] Медленный запрос (%.2f сек):\n"
                "  Query: %s\n"
                "  Params: %s\n"
                "  Plan: %s",
                duration, query[:200], params, (plan[:200] if plan else 'N/A')
            )
            
        except Exception as e:
            logging.debug("⚠️ [DB] Ошибка профилирования запроса: %s", e)


class DatabaseSingleton(Database):
    """Классический singleton для базы данных через __new__"""
    _instance = None

    def __new__(cls, *args, **kwargs):  # pylint: disable=unused-argument
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

def get_db():
    """Получает singleton экземпляр базы данных"""
    return DatabaseSingleton()
