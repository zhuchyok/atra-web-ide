#!/usr/bin/env python3
"""
Correlation Risk Manager - управление рисками корреляции и сегментации
ИНТЕГРАЦИЯ: Корреляция к BTC/ETH/SOL + деление по секторам
"""
# pylint: disable=too-many-lines

import time
import logging
# 🔧 СТРУКТУРИРОВАННОЕ ЛОГИРОВАНИЕ: Используем централизованный логгер
from src.shared.utils.logger import get_logger
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

# Импортируем архитектуру
try:
    from src.database.db import Database
    from config import (
        CORRELATION_COOLDOWN_ENABLED,
        CORRELATION_LOOKBACK_HOURS,
        CORRELATION_COOLDOWN_SEC,
        DATABASE
    )
    CONFIG_AVAILABLE = True
except ImportError as e:
    logging.warning("⚠️ Конфигурация не доступна: %s", e)
    CONFIG_AVAILABLE = False
    # Fallback значения
    CORRELATION_COOLDOWN_ENABLED = True
    CORRELATION_LOOKBACK_HOURS = 24
    CORRELATION_COOLDOWN_SEC = 3600
    DATABASE = "trading.db"

logger = get_logger(__name__)


class CorrelationRiskManager:
    """
    Менеджер рисков корреляции и сегментации

    Подход:
    1. Вычисляем корреляцию к BTC, ETH, SOL
    2. Группируем по уровню корреляции
    3. Делим по секторам внутри групп

    Функционал:
    - Проверка корреляционных рисков между активами
    - Сегментация по группам корреляции (HIGH/MEDIUM/LOW к BTC/ETH/SOL)
    - Ограничение сигналов по секторам
    - Хранение истории сигналов в БД
    """

    def __init__(self, db_path: str = None):
        """Инициализация менеджера рисков"""
        self.db_path = db_path or DATABASE
        self.db = None
        # БД будет инициализирована в _init_database()

        # Основные активы для сравнения
        self.base_assets = {
            'BTCUSDT': 'BTC',
            'ETHUSDT': 'ETH',
            'SOLUSDT': 'SOL'
        }

        # Пороги корреляции (базовые)
        self.correlation_thresholds = {
            'HIGH': 0.75,
            'MEDIUM': 0.50,
            'LOW': 0.25
        }

        # Сектора активов (база данных секторов)
        self.asset_sectors = {
            'AI': ['FET', 'AGIX', 'OCEAN', 'RENDER', 'NEAR', 'TAO', 'GRT'],
            'DEFI': ['UNI', 'AAVE', 'MKR', 'COMP', 'CRV', 'DYDX', 'SNX', 'LDO'],
            'MEMES': ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'POPCAT'],
            'L1': ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'AVAX', 'MATIC', 'SUI', 'APT'],
            'INFRA': ['LINK', 'FIL', 'AR', 'TIA', 'STX', 'PYTH']
        }

        # Лимиты по секторам (максимум позиций в одном секторе)
        self.sector_max_limits = {
            'AI': 3,
            'DEFI': 4,
            'MEMES': 2,  # Мемы — высокий риск, лимит жестче
            'L1': 5,
            'INFRA': 4,
            'OTHER': 3
        }

        # Лимиты по группам корреляции
        self.btc_groups = {
            'BTC_HIGH': [],      # > 0.75 к BTC (основной ход BTC)
            'BTC_MEDIUM': [],    # 0.50-0.75 к BTC
            'BTC_LOW': [],       # < 0.50 к BTC
            'BTC_INDEPENDENT': [] # < 0.25 к BTC (независимые)
        }

        # Группы по корреляции к ETH
        self.eth_groups = {
            'ETH_HIGH': [],
            'ETH_MEDIUM': [],
            'ETH_LOW': [],
            'ETH_INDEPENDENT': []
        }

        # Группы по корреляции к SOL
        self.sol_groups = {
            'SOL_HIGH': [],
            'SOL_MEDIUM': [],
            'SOL_LOW': [],
            'SOL_INDEPENDENT': []
        }

        # Лимиты по группам
        # ✅ ВОССТАНОВЛЕНО: Строгие лимиты для защиты портфеля
        self.sector_limits = {
            # 🔧 ОПТИМИЗАЦИЯ: Снижены лимиты для BTC_HIGH и ETH_HIGH (каскадные риски)
            'BTC_HIGH': {'max_signals': 2, 'cooldown': CORRELATION_COOLDOWN_SEC},  # Было: 5, стало: 2 (снижение риска на 60%)
            'BTC_MEDIUM': {'max_signals': 3, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'BTC_LOW': {'max_signals': 3, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'BTC_INDEPENDENT': {'max_signals': 5, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'ETH_HIGH': {'max_signals': 2, 'cooldown': CORRELATION_COOLDOWN_SEC},  # Было: 4, стало: 2 (снижение риска на 50%)
            'ETH_MEDIUM': {'max_signals': 3, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'ETH_LOW': {'max_signals': 3, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'ETH_INDEPENDENT': {'max_signals': 4, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'SOL_HIGH': {'max_signals': 4, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'SOL_MEDIUM': {'max_signals': 3, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'SOL_LOW': {'max_signals': 3, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'SOL_INDEPENDENT': {'max_signals': 4, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'OTHER': {'max_signals': 5, 'cooldown': CORRELATION_COOLDOWN_SEC}
        }

        # Кэш корреляций
        self.correlation_cache = {}
        self.dynamic_thresholds_cache = {'data': None, 'timestamp': 0}
        self.veronica_api_url = "http://127.0.0.1:8000"

        # История сигналов в памяти
        self.signal_history_cache: List[Dict[str, Any]] = []

        # Статистика
        self.stats = {
            'total_checked': 0,
            'blocked_signals': 0,
            'blocked_by_group_limit': 0,
            'blocked_by_correlation': 0,
            'approved_signals': 0
        }

        # Инициализируем БД
        self._init_database()

        # Загружаем историю из БД
        self._load_signal_history()

        logger.info("✅ CorrelationRiskManager инициализирован (BTC/ETH/SOL correlation mode)")

    def _init_database(self):
        """Инициализация подключения к БД и таблиц"""
        try:
            # ✅ Использование стандартной инициализации
            self.db = Database(self.db_path)
            if self.db is None:
                logger.error("❌ Не удалось создать подключение к БД")
                return

            with self.db.get_lock():
                if self.db.cursor is None:
                    logger.error("❌ Курсор БД недоступен")
                    self.db = None
                    return
                    
                self.db.cursor.execute("""
                    CREATE TABLE IF NOT EXISTS risk_signal_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        signal_type TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        sector TEXT NOT NULL,
                        user_id TEXT,
                        signal_price REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                self.db.cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp_sector
                    ON risk_signal_history(timestamp, sector)
                """)

                self.db.cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_symbol_timestamp
                    ON risk_signal_history(symbol, timestamp)
                """)

                self.db.conn.commit()
                logger.info("✅ Таблицы risk_signal_history инициализированы")

        except Exception as e:
            logger.error("❌ Ошибка инициализации БД: %s", e)
            self.db = None

    def _load_signal_history(self):
        """Загрузка истории сигналов из БД"""
        if not self.db or not CORRELATION_COOLDOWN_ENABLED:
            return

        try:
            if not self.db or not self.db.cursor:
                return
                
            lookback_timestamp = int(time.time()) - (CORRELATION_LOOKBACK_HOURS * 3600)

            with self.db.get_lock():
                if not self.db.cursor:
                    return
                self.db.cursor.execute("""
                    SELECT symbol, signal_type, timestamp, sector, user_id, signal_price
                    FROM risk_signal_history
                    WHERE timestamp > ?
                    ORDER BY timestamp DESC
                """, (lookback_timestamp,))

                rows = self.db.cursor.fetchall()

                self.signal_history_cache = [
                    {
                        'symbol': row[0],
                        'signal_type': row[1],
                        'timestamp': row[2],
                        'sector': row[3],
                        'user_id': row[4],
                        'signal_price': row[5]
                    }
                    for row in rows
                ]

                logger.info("📊 Загружено %d сигналов из истории рисков", len(self.signal_history_cache))

        except Exception as e:
            logger.error("❌ Ошибка загрузки истории: %s", e)
            self.signal_history_cache = []

    async def _get_ohlc_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Получение OHLC данных для символа"""
        try:
            # Используем доступные функции для получения данных
            # pylint: disable=import-outside-toplevel
            from src.utils.ohlc_utils import get_ohlc_binance_sync
            # pylint: disable=import-outside-toplevel
            try:
                from src.execution.exchange_base import get_ohlc_with_fallback
            except ImportError:
                # Fallback если exchange_base не найден
                get_ohlc_with_fallback = None

            # Пробуем через fallback (асинхронный)
            if get_ohlc_with_fallback:
                try:
                    ohlc_data = await get_ohlc_with_fallback(symbol, "1h", limit=200)
                    if ohlc_data and len(ohlc_data) > 50:
                        df = pd.DataFrame(ohlc_data)
                        if 'close' in df.columns:
                            return df
                except Exception as e:
                    logger.debug("Async fallback failed for %s: %s", symbol, e)

            # Синхронный fallback
            try:
                ohlc_data = get_ohlc_binance_sync(symbol, "1h", limit=200)
                if ohlc_data and len(ohlc_data) > 50:
                    df = pd.DataFrame(ohlc_data)
                    if 'close' in df.columns:
                        return df
            except Exception as e:
                logger.debug("Sync fallback failed for %s: %s", symbol, e)

            return None

        except Exception as e:
            logger.error("❌ Ошибка получения OHLC для %s: %s", symbol, e)
            return None

    async def calculate_correlation(self, symbol: str, base_symbol: str, df: pd.DataFrame = None) -> float:
        """
        Вычисляет корреляцию символа к базовому активу

        Реальный расчет:
        1. Получаем OHLC данные для обоих символов
        2. Вычисляем returns
        3. Сравниваем с помощью corrcoef
        """
        try:
            # Проверяем кэш
            cache_key = f"{symbol}_{base_symbol}"
            if cache_key in self.correlation_cache:
                return self.correlation_cache[cache_key]

            # Получаем данные для символа
            symbol_df = df if df is not None and 'close' in df.columns else None

            if symbol_df is None:
                # Пытаемся получить данные асинхронно
                symbol_df = await self._get_ohlc_data(symbol)

            if symbol_df is None or len(symbol_df) < 50:
                logger.warning("⚠️ Недостаточно данных для %s, используем оценку", symbol)
                correlation = self._estimate_correlation_from_symbol(symbol, base_symbol)
                self.correlation_cache[cache_key] = correlation
                return correlation

            # Получаем данные для базового актива
            # Проверяем, есть ли уже USDT в base_symbol
            if base_symbol.endswith('USDT'):
                base_symbol_full = base_symbol  # Уже полное имя
            else:
                base_symbol_full = f"{base_symbol}USDT"
            base_df = await self._get_ohlc_data(base_symbol_full)

            if base_df is None or len(base_df) < 50:
                logger.warning("⚠️ Недостаточно данных для %s, используем оценку", base_symbol)
                correlation = self._estimate_correlation_from_symbol(symbol, base_symbol)
                self.correlation_cache[cache_key] = correlation
                return correlation

            # Приводим к общему размеру (берем минимум)
            min_len = min(len(symbol_df), len(base_df))
            symbol_prices = symbol_df['close'].tail(min_len).values
            base_prices = base_df['close'].tail(min_len).values

            # Вычисляем returns
            symbol_returns = pd.Series(symbol_prices).pct_change().dropna().values
            base_returns = pd.Series(base_prices).pct_change().dropna().values

            # Убеждаемся, что длины совпадают
            min_returns_len = min(len(symbol_returns), len(base_returns))
            if min_returns_len < 10:
                logger.warning("⚠️ Недостаточно returns для корреляции %s к %s", symbol, base_symbol)
                correlation = self._estimate_correlation_from_symbol(symbol, base_symbol)
                self.correlation_cache[cache_key] = correlation
                return correlation

            symbol_returns = symbol_returns[:min_returns_len]
            base_returns = base_returns[:min_returns_len]

            # Вычисляем корреляцию
            correlation_matrix = np.corrcoef(symbol_returns, base_returns)
            correlation = correlation_matrix[0, 1]

            # Проверяем на NaN
            if np.isnan(correlation) or np.isinf(correlation):
                logger.warning("⚠️ Некорректная корреляция %s к %s (NaN/Inf), используем оценку", symbol, base_symbol)
                correlation = self._estimate_correlation_from_symbol(symbol, base_symbol)

            logger.debug(
                "📊 Реальная корреляция %s к %s: %.3f (данных: %d)",
                symbol,
                base_symbol,
                correlation,
                min_returns_len,
            )

            # Кэшируем
            self.correlation_cache[cache_key] = correlation

            return correlation

        except Exception as e:
            logger.error("❌ Ошибка расчета корреляции %s к %s: %s", symbol, base_symbol, e)
            # Fallback к оценке
            correlation = self._estimate_correlation_from_symbol(symbol, base_symbol)
            self.correlation_cache[cache_key] = correlation
            return correlation

    def _estimate_correlation_from_symbol(self, symbol: str, base_symbol: str) -> float:
        """Оценка корреляции по символу (fallback если данных нет)"""
        try:
            if base_symbol == 'BTC':
                # Основные альты - высокая корреляция к BTC
                if any(x in symbol for x in ['ETH', 'SOL', 'ADA', 'DOT', 'AVAX', 'LINK', 'MATIC']):
                    return 0.80
                # DeFi токены - средняя корреляция
                elif any(x in symbol for x in ['UNI', 'AAVE', 'COMP', 'MKR']):
                    return 0.65
                # Meme токены - низкая корреляция
                elif any(x in symbol for x in ['DOGE', 'SHIB', 'PEPE', 'FLOKI']):
                    return 0.30
                else:
                    return 0.50

            elif base_symbol == 'ETH':
                # DeFi на ETH - высокая корреляция
                if any(x in symbol for x in ['UNI', 'AAVE', 'LINK', 'COMP', 'MKR', 'SNX']):
                    return 0.85
                # L2 решения - высокая корреляция
                elif any(x in symbol for x in ['MATIC', 'ARB', 'OP']):
                    return 0.75
                else:
                    return 0.50

            elif base_symbol == 'SOL':
                # Экосистема SOL
                if any(x in symbol for x in ['RAY', 'SRM', 'FIDA', 'STEP']):
                    return 0.75
                else:
                    return 0.40

            return 0.50

        except Exception as e:
            logger.error("❌ Ошибка оценки корреляции %s к %s: %s", symbol, base_symbol, e)
            return 0.50

    async def calculate_fast_correlation(self, symbol: str, base_symbol: str) -> float:
        """
        Вычисляет БЫСТРУЮ корреляцию (5m timeframe) для обнаружения мгновенных дампов/пампов
        """
        try:
            # Получаем данные 5m
            symbol_df = await self._get_ohlc_data_fast(symbol)
            
            if base_symbol.endswith('USDT'):
                base_symbol_full = base_symbol
            else:
                base_symbol_full = f"{base_symbol}USDT"
            
            base_df = await self._get_ohlc_data_fast(base_symbol_full)

            if symbol_df is None or base_df is None or len(symbol_df) < 20:
                return 0.0

            min_len = min(len(symbol_df), len(base_df))
            symbol_prices = symbol_df['close'].tail(min_len).values
            base_prices = base_df['close'].tail(min_len).values

            symbol_returns = pd.Series(symbol_prices).pct_change().dropna().values
            base_returns = pd.Series(base_prices).pct_change().dropna().values

            min_returns_len = min(len(symbol_returns), len(base_returns))
            if min_returns_len < 10:
                return 0.0

            correlation_matrix = np.corrcoef(symbol_returns[:min_returns_len], base_returns[:min_returns_len])
            return correlation_matrix[0, 1]
        except Exception as e:
            logger.debug("Error in fast correlation: %s", e)
            return 0.0

    async def _get_ohlc_data_fast(self, symbol: str) -> Optional[pd.DataFrame]:
        """Вспомогательный метод для 5m данных"""
        from src.utils.ohlc_utils import get_ohlc_binance_sync
        try:
            ohlc_data = get_ohlc_binance_sync(symbol, "5m", limit=100)
            if ohlc_data and len(ohlc_data) > 20:
                return pd.DataFrame(ohlc_data)
            return None
        except Exception:
            return None

    async def get_dynamic_thresholds(self) -> Dict[str, float]:
        """
        Получает адаптивные пороги корреляции от Вероники с расширенным контекстом.
        """
        current_time = time.time()
        if (current_time - self.dynamic_thresholds_cache['timestamp'] < 1800 and 
            self.dynamic_thresholds_cache['data']):
            return self.dynamic_thresholds_cache['data']

        try:
            import httpx
            
            # Получаем быстрые данные по рынку для контекста
            btc_5m = await self.calculate_fast_correlation('BTCUSDT', 'BTCUSDT') # dummy to check volatility
            
            logger.info("📡 Запрос адаптивной стратегии у Вероники (Market Microstructure mode)...")
            async with httpx.AsyncClient(timeout=20.0) as client:
                payload = {
                    "goal": f"Проанализируй текущую ситуацию на крипторынке. "
                            f"BTC сейчас показывает волатильность на 5m. "
                            f"Определи режим рынка (Bull/Bear/Crash/Sideways). "
                            f"Выдай пороги корреляции: если Crash (корр > 0.9 на 5m), снижай пороги HIGH до 0.6. "
                            f"Верни ТОЛЬКО JSON: {{\"HIGH\": 0.XX, \"MEDIUM\": 0.XX, \"LOW\": 0.XX, \"REGIME\": \"name\"}}",
                    "max_steps": 5
                }
                response = await client.post(f"{self.veronica_api_url}/run", json=payload)
                
                if response.status_code == 200:
                    import re
                    import json
                    res_text = response.json().get('output', '')
                    match = re.search(r'\{.*\}', res_text, re.DOTALL)
                    if match:
                        dynamic_data = json.loads(match.group())
                        if all(k in dynamic_data for k in ['HIGH', 'MEDIUM', 'LOW']):
                            self.dynamic_thresholds_cache = {
                                'data': dynamic_data,
                                'timestamp': current_time
                            }
                            logger.info("✅ Вероника определила режим: %s. Пороги: %s", 
                                       dynamic_data.get('REGIME', 'UNKNOWN'), dynamic_data)
                            return dynamic_data
        except Exception as e:
            logger.warning("⚠️ Вероника не ответила, используем базовые пороги: %s", e)

        return self.correlation_thresholds

    async def get_symbol_group_async(self, symbol: str, df: pd.DataFrame = None) -> str:
        """
        Определяет группу символа на основе корреляции к BTC/ETH/SOL (асинхронный)

        Возвращает: строку группу (например, 'BTC_HIGH', 'ETH_MEDIUM')
        """
        try:
            # Получаем актуальные пороги (статические или динамические)
            thresholds = await self.get_dynamic_thresholds()

            # Вычисляем корреляции (асинхронно)
            btc_corr = await self.calculate_correlation(symbol, 'BTC', df)
            eth_corr = await self.calculate_correlation(symbol, 'ETH', df)
            sol_corr = await self.calculate_correlation(symbol, 'SOL', df)

            # Определяем максимальную корреляцию
            max_corr = max(btc_corr, eth_corr, sol_corr)
            if max_corr == btc_corr:
                base = 'BTC'
            elif max_corr == eth_corr:
                base = 'ETH'
            else:
                base = 'SOL'

            # Определяем уровень корреляции на основе текущих порогов
            if max_corr >= thresholds['HIGH']:
                level = 'HIGH'
            elif max_corr >= thresholds['MEDIUM']:
                level = 'MEDIUM'
            elif max_corr >= thresholds['LOW']:
                level = 'LOW'
            else:
                level = 'INDEPENDENT'

            group = f"{base}_{level}"

            logger.debug("📊 %s: BTC=%.2f, ETH=%.2f, SOL=%.2f → %s (пороги: %s)",
                        symbol, btc_corr, eth_corr, sol_corr, group, thresholds)

            return group

        except Exception as e:
            logger.error("❌ Ошибка определения группы для %s: %s", symbol, e)
            return 'OTHER'

    def _get_user_open_positions(self, user_id: str) -> List[Dict[str, Any]]:
        """Получение открытых позиций пользователя из БД"""
        if not self.db or not user_id:
            return []

        try:
            if not self.db or not self.db.cursor:
                return []
                
            with self.db.get_lock():
                if not self.db.cursor:
                    return []
                # Получаем открытые позиции из signals_log
                self.db.cursor.execute("""
                    SELECT user_id, symbol, entry, entry_time, result
                    FROM signals_log
                    WHERE user_id = ?
                    AND UPPER(IFNULL(result, 'OPEN')) LIKE 'OPEN%'
                    AND symbol NOT LIKE 'TEST%'
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (user_id,))

                rows = self.db.cursor.fetchall()

                positions = []
                for row in rows:
                    positions.append({
                        'symbol': row[1],
                        'entry': row[2],
                        'entry_time': row[3],
                        'result': row[4]
                    })

                return positions

        except Exception as e:
            logger.error("❌ Ошибка получения открытых позиций для %s: %s", user_id, e)
            return []

    def _get_symbol_sector(self, symbol: str) -> str:
        """Определяет сектор монеты"""
        clean_symbol = symbol.replace('USDT', '')
        for sector, symbols in self.asset_sectors.items():
            if clean_symbol in symbols:
                return sector
        return 'OTHER'

    async def check_correlation_risk_async(
        self,
        symbol: str,
        signal_type: str,
        user_id: str = None,
        df: pd.DataFrame = None
    ) -> Dict[str, Any]:
        """
        Проверка корреляционных рисков (Advanced Multi-Asset & Sectoral Mode)
        """
        self.stats['total_checked'] += 1

        if not CORRELATION_COOLDOWN_ENABLED:
            return {'allowed': True, 'reason': 'DISABLED'}

        # 1. МГНОВЕННЫЙ KILL-SWITCH (5m Correlation)
        # Если корреляция к BTC на 5м > 0.95 — рынок в панике, не входим ни во что
        fast_btc_corr = await self.calculate_fast_correlation(symbol, 'BTC')
        if fast_btc_corr > 0.95:
            logger.warning("🚨 [FAST RISK] Мгновенная корреляция %s к BTC = %.2f. ПАНИКА НА РЫНКЕ!", symbol, fast_btc_corr)
            return {
                'allowed': False,
                'reason': 'FAST_MARKET_PANIC',
                'details': f'Рыночная паника: корреляция к BTC на 5м таймфрейме > 0.95 (текущая: {fast_btc_corr:.2f})'
            }

        # 2. СЕКТОРАЛЬНАЯ ПРОВЕРКА
        symbol_sector = self._get_symbol_sector(symbol)
        open_positions = self._get_user_open_positions(user_id) if user_id else []
        
        sector_count = 0
        for pos in open_positions:
            if self._get_symbol_sector(pos['symbol']) == symbol_sector:
                sector_count += 1
        
        max_sector_limit = self.sector_max_limits.get(symbol_sector, self.sector_max_limits['OTHER'])
        if sector_count >= max_sector_limit:
            logger.warning("🚫 [SECTOR LIMIT] Сектор %s перегружен (%d/%d)", symbol_sector, sector_count, max_sector_limit)
            return {
                'allowed': False,
                'reason': 'SECTOR_LIMIT_EXCEEDED',
                'details': f'Лимит сектора {symbol_sector} исчерпан: {sector_count}/{max_sector_limit} позиций'
            }

        # 3. МУЛЬТИ-АКТИВНАЯ ГРУППИРОВКА (BTC/ETH/SOL)
        symbol_group = await self.get_symbol_group_async(symbol, df)
        thresholds = await self.get_dynamic_thresholds()
        
        # 4. ПРОВЕРКА КОРРЕЛЯЦИИ С ОТКРЫТЫМИ ПОЗИЦИЯМИ (1h)
        correlated_positions = []
        for position in open_positions:
            if position['symbol'] != symbol:
                pos_corr = await self.calculate_correlation(symbol, position['symbol'], df)
                if pos_corr >= thresholds['HIGH']:
                    correlated_positions.append(f"{position['symbol']} ({pos_corr:.2f})")

        if correlated_positions:
            return {
                'allowed': False,
                'reason': 'HIGH_CORRELATION',
                'details': f'Высокая корреляция с открытыми позициями: {", ".join(correlated_positions)}'
            }

        # 5. ЛИМИТЫ ГРУПП
        current_time = int(time.time())
        active_group_signals = [
            s for s in self.signal_history_cache 
            if s.get('sector') == symbol_group and (current_time - s['timestamp']) < CORRELATION_COOLDOWN_SEC
        ]
        
        group_limit = self.sector_limits.get(symbol_group, self.sector_limits['OTHER'])['max_signals']
        if len(active_group_signals) >= group_limit:
            return {
                'allowed': False,
                'reason': 'GROUP_LIMIT_EXCEEDED',
                'details': f'Лимит группы {symbol_group} исчерпан: {len(active_group_signals)}/{group_limit}'
            }

        self.stats['approved_signals'] += 1
        return {
            'allowed': True,
            'reason': 'NO_RISK',
            'details': f'Одобрено (Сектор: {symbol_sector}, Группа: {symbol_group})'
        }

    async def save_signal_to_history_async(
        self,
        symbol: str,
        signal_type: str,
        user_id: str = None,
        signal_price: float = None,
        df: pd.DataFrame = None
    ):
        """Сохранение сигнала в историю"""
        if not self.db:
            return

        try:
            # Определяем группу (асинхронно)
            sector = await self.get_symbol_group_async(symbol, df)

            signal_data = {
                'symbol': symbol,
                'signal_type': signal_type,
                'timestamp': int(time.time()),
                'sector': sector,
                'user_id': user_id,
                'signal_price': signal_price
            }

            self.signal_history_cache.append(signal_data)

            if not self.db or not self.db.cursor:
                return
                
            with self.db.get_lock():
                if not self.db.cursor:
                    return
                self.db.cursor.execute("""
                    INSERT INTO risk_signal_history
                    (symbol, signal_type, timestamp, sector, user_id, signal_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    signal_data['symbol'],
                    signal_data['signal_type'],
                    signal_data['timestamp'],
                    signal_data['sector'],
                    signal_data['user_id'],
                    signal_data['signal_price']
                ))
                self.db.conn.commit()

        except Exception as e:
            logger.error("❌ Ошибка сохранения сигнала в историю: %s", e)

    def get_statistics_report(self) -> str:
        """Получение отчета по статистике"""
        report_lines = [
            "📊 ОТЧЕТ УПРАВЛЕНИЯ РИСКАМИ",
            f"Всего проверено сигналов: {self.stats['total_checked']}",
            f"Одобрено: {self.stats['approved_signals']}",
            f"Заблокировано: {self.stats['blocked_signals']}",
            f"  └─ по лимитам групп: {self.stats['blocked_by_group_limit']}",
            f"  └─ по корреляции: {self.stats['blocked_by_correlation']}",
            "",
            "🏷️ ЛИМИТЫ ГРУПП КОРРЕЛЯЦИИ:"
        ]

        current_time = int(time.time())

        for group, limits in self.sector_limits.items():
            active_count = len([
                s for s in self.signal_history_cache
                if s.get('sector') == group
                and (current_time - s['timestamp']) < limits['cooldown']
            ])

            report_lines.append(
                f"  {group}: {active_count}/{limits['max_signals']} (cooldown: {limits['cooldown']//3600}ч)"
            )

        return "\n".join(report_lines)

    async def check_portfolio_correlation_risk(self, active_signals: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Проверяет корреляционный риск портфеля к основным активам (BTC, ETH, SOL)
        """
        try:
            current_time = int(time.time())
            cooldown = CORRELATION_COOLDOWN_SEC
            
            asset_stats = {}
            alerts = []
            max_risk_level = "LOW"

            for base_asset in ['BTC', 'ETH', 'SOL']:
                group_name = f'{base_asset}_HIGH'
                
                # Фильтруем сигналы в данной группе
                if active_signals is None:
                    group_signals = [
                        s for s in self.signal_history_cache
                        if s.get('sector') == group_name
                        and (current_time - s['timestamp']) < cooldown
                    ]
                else:
                    group_signals = [
                        s for s in active_signals
                        if s.get('sector') == group_name
                        and (current_time - s.get('timestamp', 0)) < cooldown
                    ]

                positions_count = len(set(s.get('symbol') for s in group_signals))
                
                # Вычисляем среднюю корреляцию
                correlations = []
                for signal in group_signals:
                    symbol = signal.get('symbol')
                    if symbol:
                        corr = await self.calculate_correlation(symbol, base_asset)
                        if corr > 0:
                            correlations.append(corr)
                
                avg_corr = np.mean(correlations) if correlations else 0.0
                
                # Оценка риска
                asset_risk = "LOW"
                if positions_count >= 6 or avg_corr > 0.9:
                    asset_risk = "CRITICAL"
                elif positions_count >= 4 or avg_corr > 0.85:
                    asset_risk = "HIGH"
                elif positions_count >= 2:
                    asset_risk = "MEDIUM"

                if asset_risk in ["HIGH", "CRITICAL"]:
                    alerts.append(f"🚨 {base_asset} RISK: {asset_risk} (Позиций: {positions_count}, Корр: {avg_corr:.2f})")

                asset_stats[base_asset] = {
                    'count': positions_count,
                    'avg_correlation': avg_corr,
                    'risk': asset_risk
                }
                
                if asset_risk == "CRITICAL": max_risk_level = "CRITICAL"
                elif asset_risk == "HIGH" and max_risk_level != "CRITICAL": max_risk_level = "HIGH"

            return {
                'asset_stats': asset_stats,
                'risk_level': max_risk_level,
                'alerts': alerts,
                'timestamp': current_time
            }

        except Exception as e:
            logger.error("❌ Ошибка проверки портфеля: %s", e)
            return {'risk_level': 'ERROR', 'alerts': [str(e)]}

    def calculate_dynamic_limit(self, base_limit: int, market_volatility: float = None) -> int:
        """
        Вычисляет динамический лимит на основе волатильности рынка
        """
        if market_volatility is None:
            return base_limit

        # Высокая волатильность (>0.15) → уменьшаем лимит
        if market_volatility > 0.15:
            return max(6, int(base_limit * 0.6))
        elif market_volatility < 0.05:
            return base_limit
        else:
            return max(8, int(base_limit * 0.8))

    async def get_risk_alerts(self, active_signals: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Получает список алертов по рискам (Multi-Asset & Sectoral)
        """
        alerts = []
        try:
            portfolio_risk = await self.check_portfolio_correlation_risk(active_signals)
            
            for msg in portfolio_risk.get('alerts', []):
                level = 'CRITICAL' if 'CRITICAL' in msg else 'WARNING'
                alerts.append({
                    'level': level,
                    'type': 'PORTFOLIO_CORRELATION',
                    'message': msg,
                    'action': 'REDUCE_EXPOSURE' if level == 'CRITICAL' else 'MONITOR'
                })
            
            # Проверка перегрева секторов
            sector_counts = {}
            for pos in self.signal_history_cache:
                if (int(time.time()) - pos['timestamp']) < CORRELATION_COOLDOWN_SEC:
                    sec = self._get_symbol_sector(pos['symbol'])
                    sector_counts[sec] = sector_counts.get(sec, 0) + 1
            
            for sector, count in sector_counts.items():
                limit = self.sector_max_limits.get(sector, self.sector_max_limits['OTHER'])
                if count >= limit:
                    alerts.append({
                        'level': 'WARNING',
                        'type': 'SECTOR_CONCENTRATION',
                        'message': f"⚠️ Сектор {sector} перегружен: {count}/{limit}",
                        'action': 'DIVERSIFY'
                    })

        except Exception as e:
            logger.error("❌ Ошибка получения алертов: %s", e)
        
        return alerts

    def clear_old_history(self):
        """Очистка старой истории"""
        try:
            if not self.db:
                return

            cutoff_timestamp = int(time.time()) - (CORRELATION_LOOKBACK_HOURS * 3600 * 2)

            if not self.db or not self.db.cursor:
                return
                
            with self.db.get_lock():
                if not self.db.cursor:
                    return
                self.db.cursor.execute(
                    "DELETE FROM risk_signal_history WHERE timestamp < ?",
                    (cutoff_timestamp,)
                )
                deleted_count = self.db.cursor.rowcount
                self.db.conn.commit()

                if deleted_count > 0:
                    logger.info("🗑️ Удалено %d устаревших записей из истории рисков", deleted_count)

        except Exception as e:
            logger.error("❌ Ошибка очистки истории: %s", e)

    async def calculate_position_multiplier(
        self,
        symbol: str,
        user_id: str = None,
        df: pd.DataFrame = None
    ) -> Dict[str, Any]:
        """
        Рассчитывает множитель размера позиции на основе корреляции с открытыми позициями

        Возвращает:
            {
                'multiplier': float (0.3-1.0),
                'reason': str,
                'max_correlation': float,
                'correlated_positions': List[Dict]
            }
        """
        try:
            # 1. Получаем открытые позиции пользователя
            open_positions = []
            if user_id:
                open_positions = self._get_user_open_positions(user_id)

            if not open_positions:
                return {
                    'multiplier': 1.0,
                    'reason': 'NO_OPEN_POSITIONS',
                    'max_correlation': 0.0,
                    'correlated_positions': []
                }

            # 2. Вычисляем корреляции с каждой открытой позицией
            correlations = []
            correlated_positions = []

            for position in open_positions:
                position_symbol = position['symbol']

                if position_symbol == symbol:
                    continue  # Пропускаем саму себя

                try:
                    # Вычисляем корреляцию
                    corr = await self.calculate_correlation(symbol, position_symbol, df)
                    correlations.append(abs(corr))

                    if abs(corr) > 0.6:  # Значимая корреляция
                        correlated_positions.append({
                            'symbol': position_symbol,
                            'correlation': corr,
                            'entry': position.get('entry'),
                            'entry_time': position.get('entry_time')
                        })

                except Exception as e:
                    logger.debug("Ошибка расчета корреляции %s к %s: %s", symbol, position_symbol, e)
                    continue

            # 3. Определяем максимальную корреляцию
            max_correlation = max(correlations) if correlations else 0.0

            # 4. Рассчитываем штраф (НЕЛИНЕЙНЫЙ)
            if max_correlation > 0.85:
                multiplier = 0.3  # -70% (очень высокая корреляция)
                reason = f'VERY_HIGH_CORRELATION ({max_correlation:.2f})'
            elif max_correlation > 0.75:
                multiplier = 0.5  # -50% (высокая корреляция)
                reason = f'HIGH_CORRELATION ({max_correlation:.2f})'
            elif max_correlation > 0.65:
                multiplier = 0.7  # -30% (средне-высокая корреляция)
                reason = f'MEDIUM_HIGH_CORRELATION ({max_correlation:.2f})'
            elif max_correlation > 0.55:
                multiplier = 0.85  # -15% (средняя корреляция)
                reason = f'MEDIUM_CORRELATION ({max_correlation:.2f})'
            else:
                multiplier = 1.0  # Без штрафа
                reason = f'LOW_CORRELATION ({max_correlation:.2f})'

            logger.info(
                "📊 [PENALTY] %s: множитель размера=%.2f (макс. корр: %.2f с %d позициями)",
                symbol,
                multiplier,
                max_correlation,
                len(correlated_positions),
            )

            return {
                'multiplier': multiplier,
                'reason': reason,
                'max_correlation': max_correlation,
                'correlated_positions': correlated_positions
            }

        except Exception as e:
            logger.error("❌ Ошибка расчета correlation penalty для %s: %s", symbol, e)
            return {
                'multiplier': 1.0,
                'reason': 'ERROR',
                'max_correlation': 0.0,
                'correlated_positions': []
            }


# Глобальный экземпляр менеджера
_CORRELATION_MANAGER = None


def get_correlation_manager() -> CorrelationRiskManager:
    """Получение глобального экземпляра менеджера"""
    global _CORRELATION_MANAGER

    if _CORRELATION_MANAGER is None:
        _CORRELATION_MANAGER = CorrelationRiskManager()

    return _CORRELATION_MANAGER
