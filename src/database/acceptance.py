"""
AcceptanceDatabase - База данных для хранения принятых сигналов, позиций и API ключей биржи
"""

import json
import logging
import sqlite3
import os
import asyncio
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from src.database.fetch_optimizer import fetch_all_optimized

logger = logging.getLogger(__name__)


class AcceptanceDatabase:
    """База данных для принятых сигналов и API ключей биржи"""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(AcceptanceDatabase, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if getattr(self, '_initialized', False):
            return
        
        # Интеллектуальный выбор пути к базе данных
        if db_path is None:
            # 1. Проверяем переменную окружения
            db_path = os.getenv("ATRA_DB_PATH")
            
            if db_path is None:
                # 2. Проверяем стандартные пути
                paths_to_check = [
                    "/root/atra/trading.db",  # Сервер
                    os.path.join(os.getcwd(), "trading.db"),  # Локально (корень проекта)
                    "trading.db"  # Текущая папка
                ]
                
                for path in paths_to_check:
                    # Проверяем, можем ли мы использовать этот путь
                    abs_path = os.path.abspath(path)
                    dir_name = os.path.dirname(abs_path)
                    
                    # Если папка существует и мы можем в нее писать, или если файл уже существует и мы можем в него писать
                    if os.path.exists(dir_name) and os.access(dir_name, os.W_OK):
                        if not os.path.exists(abs_path) or os.access(abs_path, os.W_OK):
                            db_path = abs_path
                            break
                
                if db_path is None:
                    db_path = "trading.db"

        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = None
        self.init_database()
        self._initialized = True
        logger.info("✅ AcceptanceDatabase инициализирована: %s", self.db_path)

    def _get_conn(self):
        """Ленивая инициализация и возврат соединения"""
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(self.db_path, timeout=60.0, check_same_thread=False)
                # Оптимальные настройки для параллельной работы
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA synchronous=NORMAL;")
                self._conn.execute("PRAGMA busy_timeout=60000;")
            return self._conn

    def _get_db_connection(self):
        """Метод для обратной совместимости"""
        return self._get_conn()

    def init_database(self):
        """Инициализирует базу данных"""
        try:
            conn = self._get_conn()
            with self._lock:
                cursor = conn.cursor()

                # Таблица принятых сигналов
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS accepted_signals (
                        signal_key TEXT PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        signal_time DATETIME NOT NULL,
                        user_id INTEGER NOT NULL,
                        chat_id INTEGER NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        message_id INTEGER,
                        accepted_time DATETIME,
                        accepted_by TEXT,
                        closed_time DATETIME,
                        close_price REAL,
                        pnl REAL,
                        pnl_pct REAL,
                        tp1_price REAL,
                        tp2_price REAL,
                        sl_price REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Таблица активных позиций
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS active_positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price REAL,
                        entry_time DATETIME,
                        current_price REAL,
                        pnl_percent REAL,
                        status TEXT DEFAULT 'open',
                        accepted_by TEXT,
                        user_id INTEGER,
                        message_id INTEGER,
                        chat_id INTEGER,
                        signal_key TEXT UNIQUE,
                        expires_at DATETIME,
                        ars_last_action TEXT,
                        ars_last_time DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Проверка наличия новых колонок (миграция)
                cursor.execute("PRAGMA table_info(active_positions)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'ars_last_action' not in columns:
                    cursor.execute("ALTER TABLE active_positions ADD COLUMN ars_last_action TEXT")
                if 'ars_last_time' not in columns:
                    cursor.execute("ALTER TABLE active_positions ADD COLUMN ars_last_time DATETIME")
                if 'user_id' not in columns:
                    cursor.execute("ALTER TABLE active_positions ADD COLUMN user_id INTEGER")

                # Миграция для accepted_signals
                cursor.execute("PRAGMA table_info(accepted_signals)")
                columns_accepted = [col[1] for col in cursor.fetchall()]
                if 'tp1_price' not in columns_accepted:
                    cursor.execute("ALTER TABLE accepted_signals ADD COLUMN tp1_price REAL")
                if 'tp2_price' not in columns_accepted:
                    cursor.execute("ALTER TABLE accepted_signals ADD COLUMN tp2_price REAL")
                if 'sl_price' not in columns_accepted:
                    cursor.execute("ALTER TABLE accepted_signals ADD COLUMN sl_price REAL")
                if 'accepted_by' not in columns_accepted:
                    cursor.execute("ALTER TABLE accepted_signals ADD COLUMN accepted_by TEXT")

                # Таблица статистики
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS acceptance_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date DATE,
                        total_signals INTEGER DEFAULT 0,
                        accepted_signals INTEGER DEFAULT 0,
                        closed_positions INTEGER DEFAULT 0,
                        total_pnl REAL DEFAULT 0.0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Таблица ключей биржи (Bitget/Binance)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_exchange_keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        exchange_name TEXT NOT NULL,
                        api_key TEXT NOT NULL,
                        secret_key TEXT NOT NULL,
                        passphrase TEXT,
                        is_active INTEGER DEFAULT 1,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, exchange_name)
                    )
                """)

                # Таблица настроек пользователей
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_settings (
                        user_id INTEGER PRIMARY KEY,
                        trade_mode TEXT DEFAULT 'manual',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
        except Exception as e:
            logger.error("❌ Ошибка инициализации AcceptanceDatabase: %s", e)

    async def _execute_with_retry(self, query: str, params: tuple = (), is_write: bool = True) -> Any:
        """Выполняет SQL запрос с повторными попытками при блокировке БД"""
        max_retries = 10
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                conn = self._get_conn()
                with self._lock:
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    if is_write:
                        conn.commit()
                        return True
                    else:
                        return fetch_all_optimized(cursor)
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning("⚠️ БД занята (попытка %d/%d), ждем %.1f сек...", attempt + 1, max_retries, retry_delay)
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 5.0)
                    continue
                logger.error("❌ Ошибка БД после %d попыток: %s", attempt + 1, e)
                if not is_write: return []
                return False
            except Exception as e:
                logger.error("❌ Критическая ошибка БД: %s", e)
                if not is_write: return []
                return False
        return False if is_write else []

    async def execute_with_retry(self, query: str, params: tuple = (), is_write: bool = True) -> Any:
        """Публичный алиас для обратной совместимости"""
        return await self._execute_with_retry(query, params, is_write)

    async def save_exchange_keys(self, user_id: int, exchange_name: str, api_key: str, secret_key: str, passphrase: Optional[str] = None) -> bool:
        """Сохраняет или обновляет API ключи биржи для пользователя (с ретраями)"""
        try:
            from src.utils.encryption import get_key_encryption
            encryption = get_key_encryption()
            
            # Шифруем ключи перед сохранением
            enc_api = encryption.encrypt(api_key)
            enc_secret = encryption.encrypt(secret_key)
            enc_passphrase = encryption.encrypt(passphrase) if passphrase else None
            
            query = """
                INSERT OR REPLACE INTO user_exchange_keys (
                    user_id, exchange_name, api_key, secret_key, passphrase, is_active, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """
            params = (user_id, exchange_name, enc_api, enc_secret, enc_passphrase)
            
            return await self._execute_with_retry(query, params, is_write=True)
            
        except Exception as e:
            logger.error("❌ Ошибка при сохранении ключей в БД: %s", e)
            return False

    async def get_active_exchange_keys(self, user_id: int, exchange_name: str = 'bitget') -> Optional[Dict[str, str]]:
        """Получает расшифрованные API ключи пользователя"""
        query = "SELECT api_key, secret_key, passphrase FROM user_exchange_keys WHERE user_id = ? AND exchange_name = ? AND is_active = 1"
        rows = await self._execute_with_retry(query, (user_id, exchange_name), is_write=False)
        
        if not rows:
            return None
            
        try:
            from src.utils.encryption import get_key_encryption
            encryption = get_key_encryption()
            
            row = rows[0]
            api_key = encryption.decrypt(row[0])
            secret_key = encryption.decrypt(row[1])
            passphrase = encryption.decrypt(row[2]) if row[2] else None
            
            return {
                'api_key': api_key,
                'secret_key': secret_key,
                'passphrase': passphrase
            }
        except Exception as e:
            logger.error("❌ Ошибка расшифрования ключей: %s", e)
            return None

    async def create_active_position(self, symbol: str, direction: str, entry_price: float, user_id: int, chat_id: int, message_id: int, signal_key: str):
        """Создает запись об активной позиции"""
        query = """
            INSERT INTO active_positions (symbol, direction, entry_price, entry_time, user_id, accepted_by, chat_id, message_id, signal_key, status)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, 'open')
            ON CONFLICT(signal_key) DO UPDATE SET
                status = 'open',
                entry_price = EXCLUDED.entry_price
        """
        params = (symbol, direction, entry_price, user_id, str(user_id), chat_id, message_id, signal_key)
        return await self._execute_with_retry(query, params, is_write=True)

    async def upsert_active_position(self, user_id: int, symbol: str, direction: str, entry_price: float, status: str = 'open'):
        """Обновляет или создает активную позицию (используется при синхронизации с биржей)"""
        # Сначала проверяем существование
        query_check = "SELECT id FROM active_positions WHERE user_id = ? AND symbol = ? AND status = 'open'"
        rows = await self._execute_with_retry(query_check, (user_id, symbol), is_write=False)
        
        if rows:
            # Обновляем
            query_update = """
                UPDATE active_positions 
                SET entry_price = ?, direction = ?, status = ?
                WHERE user_id = ? AND symbol = ? AND status = 'open'
            """
            return await self._execute_with_retry(query_update, (entry_price, direction, status, user_id, symbol), is_write=True)
        else:
            # Создаем новую (без signal_key, так как это внешняя позиция)
            query_insert = """
                INSERT INTO active_positions (user_id, symbol, direction, entry_price, status, entry_time)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            return await self._execute_with_retry(query_insert, (user_id, symbol, direction, entry_price, status), is_write=True)

    async def close_active_position_by_symbol(self, user_id: int, symbol: str, exit_price: float = None, exit_reason: str = 'CLOSED_BY_SYNC') -> bool:
        """Помечает позицию как закрытую в БД и обновляет signals_log"""
        # Получаем данные позиции перед закрытием
        position_query = """
            SELECT symbol, direction, entry_price, entry_time, signal_key
            FROM active_positions
            WHERE user_id = ? AND symbol = ? AND status = 'open'
            LIMIT 1
        """
        position_rows = await self._execute_with_retry(position_query, (user_id, symbol), is_write=False)
        
        if not position_rows:
            return False
        
        position_data = {
            'symbol': position_rows[0][0],
            'direction': position_rows[0][1],
            'entry_price': float(position_rows[0][2]) if position_rows[0][2] else 0.0,
            'entry_time': position_rows[0][3],
            'signal_key': position_rows[0][4] if len(position_rows[0]) > 4 else None
        }
        
        # Обновляем active_positions
        query = """
            UPDATE active_positions
            SET status = 'closed', updated_at = datetime('now')
            WHERE user_id = ? AND symbol = ? AND status = 'open'
        """
        result = await self._execute_with_retry(query, (user_id, symbol), is_write=True)
        
        # Обновляем signals_log с exit_time и result
        if result and position_data['entry_time']:
            try:
                # Рассчитываем PnL если есть exit_price
                net_profit = 0.0
                if exit_price and position_data['entry_price'] > 0:
                    if position_data['direction'].upper() == 'BUY':
                        net_profit = (exit_price - position_data['entry_price']) * 1.0  # Упрощённый расчёт
                    else:  # SELL
                        net_profit = (position_data['entry_price'] - exit_price) * 1.0
                
                # Обновляем signals_log
                update_signals_query = """
                    UPDATE signals_log
                    SET exit_time = datetime('now'),
                        result = ?,
                        net_profit = ?
                    WHERE user_id = ? AND symbol = ? AND entry_time = ?
                        AND (result IS NULL OR result = '' OR result = 'PENDING')
                """
                await self._execute_with_retry(
                    update_signals_query,
                    (exit_reason, net_profit, user_id, position_data['symbol'], position_data['entry_time']),
                    is_write=True
                )
            except Exception as e:
                # Логируем ошибку, но не прерываем выполнение
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("⚠️ Ошибка обновления signals_log при закрытии позиции %s: %s", symbol, e)
        
        return result

    async def get_active_positions_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список активных позиций пользователя"""
        query = "SELECT * FROM active_positions WHERE user_id = ? AND status = 'open'"
        rows = await self._execute_with_retry(query, (user_id,), is_write=False)
        
        positions = []
        if rows:
            for row in rows:
                positions.append({
                    'id': row[0],
                    'symbol': row[1],
                    'direction': row[2],
                    'entry_price': row[3],
                    'entry_time': row[4],
                    'user_id': row[9], # user_id column index is 9
                    'signal_key': row[12] # signal_key column index is 12
                })
        return positions

    async def get_user_mode(self, user_id: int) -> str:
        """Получает режим торговли для пользователя"""
        query = "SELECT trade_mode FROM user_settings WHERE user_id = ?"
        rows = await self._execute_with_retry(query, (user_id,), is_write=False)
        if rows and rows[0]:
            return rows[0][0]
        return 'manual'

    async def set_user_mode(self, user_id: int, trade_mode: str) -> bool:
        """Устанавливает режим торговли для пользователя"""
        query = """
            INSERT INTO user_settings (user_id, trade_mode, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                trade_mode = EXCLUDED.trade_mode,
                updated_at = EXCLUDED.updated_at
        """
        return await self._execute_with_retry(query, (user_id, trade_mode), is_write=True)

    async def get_users_by_mode(self, trade_mode: str) -> List[int]:
        """Возвращает список ID пользователей по режиму торговли"""
        # Эта информация хранится в основной таблице users_data в поле data (JSON)
        # Для простоты используем SQL с LIKE или загружаем всех и фильтруем
        query = "SELECT user_id, data FROM users_data"
        rows = await self._execute_with_retry(query, (), is_write=False)
        
        user_ids = []
        if rows:
            for row in rows:
                try:
                    data = json.loads(row[1])
                    if data.get('trade_mode') == trade_mode:
                        user_ids.append(row[0])
                except:
                    continue
        return user_ids

    async def update_signals_log_result(self, symbol: str, user_id: int, result: str, profit_pct: float = 0.0):
        """Обновляет результат сигнала в signals_log"""
        query = """
            UPDATE signals_log 
            SET result = ?, profit_pct = ?, closed_at = CURRENT_TIMESTAMP
            WHERE symbol = ? AND user_id = ? AND result IS NULL
            ORDER BY created_at DESC LIMIT 1
        """
        params = (result, profit_pct, symbol, user_id)
        return await self._execute_with_retry(query, params, is_write=True)

    async def get_signal_data(self, signal_key: str = None, user_symbol: tuple = None) -> Optional[Dict[str, Any]]:
        """Получает данные сигнала из accepted_signals"""
        if signal_key:
            query = "SELECT * FROM accepted_signals WHERE signal_key = ?"
            params = (signal_key,)
        elif user_symbol:
            query = "SELECT * FROM accepted_signals WHERE user_id = ? AND symbol = ? ORDER BY created_at DESC LIMIT 1"
            params = user_symbol
        else:
            return None
            
        rows = await self._execute_with_retry(query, params, is_write=False)
        if not rows: return None
        
        row = rows[0]
        return {
            'signal_key': row[0],
            'symbol': row[1],
            'direction': row[2],
            'entry_price': row[3],
            'tp1_price': row[15],
            'tp2_price': row[16],
            'sl_price': row[17],
            'status': row[7]
        }

    async def save_accepted_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Сохраняет принятый сигнал в БД (используется для автоисполнения и ручного принятия)"""
        query = """
            INSERT OR REPLACE INTO accepted_signals (
                signal_key, symbol, direction, entry_price, signal_time,
                user_id, chat_id, message_id, status, accepted_time,
                accepted_by, tp1_price, tp2_price, sl_price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
        """
        params = (
            signal_data.get('signal_key'),
            signal_data.get('symbol'),
            signal_data.get('direction'),
            signal_data.get('entry_price'),
            signal_data.get('signal_time', datetime.now(timezone.utc).isoformat()),
            signal_data.get('user_id'),
            signal_data.get('chat_id', 0),
            signal_data.get('message_id'),
            signal_data.get('status', 'accepted'),
            str(signal_data.get('user_id')),
            signal_data.get('tp1_price'),
            signal_data.get('tp2_price'),
            signal_data.get('sl_price')
        )
        return await self._execute_with_retry(query, params, is_write=True)
