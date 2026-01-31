#!/usr/bin/env python3
"""
Correlation Risk Manager - управление рисками корреляции и сегментации
ИНТЕГРАЦИЯ: Корреляция к BTC/ETH/SOL + деление по секторам
"""
# pylint: disable=too-many-lines

import time
import logging
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

logger = logging.getLogger(__name__)


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

        # Пороги корреляции для группировки
        self.correlation_thresholds = {
            'HIGH': 0.75,    # Высокая корреляция (работают вместе)
            'MEDIUM': 0.50,  # Средняя корреляция
            'LOW': 0.25      # Низкая корреляция
        }

        # Группы по корреляции к BTC
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
            'BTC_HIGH': {'max_signals': 5, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'BTC_MEDIUM': {'max_signals': 3, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'BTC_LOW': {'max_signals': 3, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'BTC_INDEPENDENT': {'max_signals': 5, 'cooldown': CORRELATION_COOLDOWN_SEC},
            'ETH_HIGH': {'max_signals': 4, 'cooldown': CORRELATION_COOLDOWN_SEC},
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

    async def get_symbol_group_async(self, symbol: str, df: pd.DataFrame = None) -> str:
        """
        Определяет группу символа на основе корреляции к BTC/ETH/SOL (асинхронный)

        Возвращает: строку группу (например, 'BTC_HIGH', 'ETH_MEDIUM')
        """
        try:
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

            # Определяем уровень корреляции
            if max_corr >= self.correlation_thresholds['HIGH']:
                level = 'HIGH'
            elif max_corr >= self.correlation_thresholds['MEDIUM']:
                level = 'MEDIUM'
            elif max_corr >= self.correlation_thresholds['LOW']:
                level = 'LOW'
            else:
                level = 'INDEPENDENT'

            group = f"{base}_{level}"

            logger.debug("📊 %s: BTC=%.2f, ETH=%.2f, SOL=%.2f → %s",
                        symbol, btc_corr, eth_corr, sol_corr, group)

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

    async def check_correlation_risk_async(
        self,
        symbol: str,
        signal_type: str,
        user_id: str = None,
        df: pd.DataFrame = None
    ) -> Dict[str, Any]:
        """
        Проверка корреляционных рисков

        НОВАЯ ЛОГИКА:
        1. Получаем ОТКРЫТЫЕ ПОЗИЦИИ пользователя из БД
        2. Вычисляем корреляцию для каждой открытой позиции
        3. Если корреляция высокая → блокируем сигнал
        4. Также проверяем историю сигналов (для лимитов)

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'details': str,
                'active_signals': List[Dict],
                'open_positions': List[Dict]
            }
        """

        self.stats['total_checked'] += 1

        if not CORRELATION_COOLDOWN_ENABLED:
            self.stats['approved_signals'] += 1
            return {
                'allowed': True,
                'reason': 'DISABLED',
                'details': 'Корреляционный фильтр отключен',
                'active_signals': []
            }

        # 1. ПОЛУЧАЕМ ОТКРЫТЫЕ ПОЗИЦИИ ПОЛЬЗОВАТЕЛЯ
        open_positions = []
        if user_id:
            open_positions = self._get_user_open_positions(user_id)
            logger.debug("📊 Пользователь %s: %d открытых позиций", user_id, len(open_positions))

        # 2. 🆕 КРИТИЧЕСКАЯ ПРОВЕРКА: ПРОТИВОПОЛОЖНЫЙ СИГНАЛ НА ТОТ ЖЕ СИМВОЛ
        for position in open_positions:
            position_symbol = position['symbol']

            # БЛОКИРУЕМ противоположные сигналы на тот же актив!
            if position_symbol == symbol:
                # Определяем направление открытой позиции
                # Если в result есть LONG/SHORT - используем их
                position_result = position.get('result', '').upper()

                # Определяем направление открытой позиции
                if 'LONG' in position_result or 'BUY' in position_result:
                    position_side = 'LONG'
                elif 'SHORT' in position_result or 'SELL' in position_result:
                    position_side = 'SHORT'
                else:
                    # Fallback: пытаемся определить по signal_type
                    position_side = 'LONG'  # По умолчанию

                # Определяем направление нового сигнала
                new_signal_side = 'LONG' if signal_type in ['BUY', 'LONG'] else 'SHORT'

                # Проверяем на конфликт
                if position_side != new_signal_side:
                    self.stats['blocked_signals'] += 1
                    self.stats['blocked_by_correlation'] += 1

                    logger.warning(
                        "🚨 [OPPOSITE SIGNAL BLOCKED] %s %s заблокирован: уже открыта позиция %s %s!",
                        symbol, signal_type, symbol, position_side
                    )

                    return {
                        'allowed': False,
                        'reason': 'OPPOSITE_SIGNAL_ON_SAME_ASSET',
                        'details': f'Уже открыта позиция {symbol} {position_side}, нельзя открыть {signal_type}',
                        'open_positions': [position],
                        'conflict': True
                    }

                # Если сигнал в том же направлении - РАЗРЕШАЕМ (усреднение)
                else:
                    logger.info(
                        "✅ [SAME DIRECTION] %s %s разрешен (усреднение с открытой позицией %s)",
                        symbol, signal_type, position_side
                    )
                    # Продолжаем проверку корреляции и лимитов (не return, просто break)
                    break

        # 3. ВЫЧИСЛЯЕМ КОРРЕЛЯЦИЮ ДЛЯ КАЖДОЙ ОТКРЫТОЙ ПОЗИЦИИ (других символов)
        symbol_group = await self.get_symbol_group_async(symbol, df)
        correlated_positions = []

        for position in open_positions:
            position_symbol = position['symbol']

            # Вычисляем корреляцию новой позиции к открытой позиции (только для РАЗНЫХ символов)
            if position_symbol != symbol:
                # Получаем данные для расчета корреляции
                pos_corr = await self.calculate_correlation(symbol, position_symbol, df)

                if pos_corr >= self.correlation_thresholds['HIGH']:
                    correlated_positions.append({
                        'symbol': position_symbol,
                        'correlation': pos_corr,
                        'group': await self.get_symbol_group_async(position_symbol, df),
                        'entry': position.get('entry'),
                        'entry_time': position.get('entry_time')
                    })

        # 4. БЛОКИРУЕМ ЕСЛИ ЕСТЬ ВЫСОКАЯ КОРРЕЛЯЦИЯ С ОТКРЫТЫМИ ПОЗИЦИЯМИ
        if correlated_positions:
            corr_details = ", ".join([f"{cp['symbol']} (корр: {cp['correlation']:.2f})" for cp in correlated_positions])

            self.stats['blocked_signals'] += 1
            self.stats['blocked_by_correlation'] += 1

            logger.warning(
                "🚫 [CORRELATION] Сигнал %s %s заблокирован: высокая корреляция с открытыми позициями: %s",
                symbol, signal_type, corr_details
            )

            return {
                'allowed': False,
                'reason': 'CORRELATED_WITH_OPEN_POSITIONS',
                'details': f'Высокая корреляция с открытыми позициями: {corr_details}',
                'open_positions': correlated_positions,
                'correlation_threshold': self.correlation_thresholds['HIGH']
            }

        # 5. ПРОВЕРЯЕМ ИСТОРИЮ СИГНАЛОВ (для лимитов по группе)
        current_time = int(time.time())
        max_age = CORRELATION_LOOKBACK_HOURS * 3600

        # Удаляем старые записи
        self.signal_history_cache = [
            s for s in self.signal_history_cache
            if current_time - s['timestamp'] < max_age
        ]

        # Проверяем активные сигналы в той же группе
        group_cooldown = self.sector_limits.get(symbol_group, self.sector_limits['OTHER'])['cooldown']
        active_signals = []
        seen_signals = set()  # 🔧 ИСПРАВЛЕНО: Предотвращение дубликатов

        for signal in self.signal_history_cache:
            signal_group = signal.get('sector', 'OTHER')
            time_diff = current_time - signal['timestamp']

            if signal_group == symbol_group and time_diff < group_cooldown:
                if user_id and signal.get('user_id') and signal['user_id'] != user_id:
                    continue

                # 🔧 ИСПРАВЛЕНО: Проверка на дубликаты по символу и timestamp
                signal_key = f"{signal['symbol']}_{signal.get('user_id', 'all')}_{signal['timestamp']}"
                if signal_key not in seen_signals:
                    active_signals.append(signal)
                    seen_signals.add(signal_key)

        # Проверяем лимит группы
        group_limit = self.sector_limits.get(symbol_group, self.sector_limits['OTHER'])['max_signals']

        if len(active_signals) >= group_limit:
            self.stats['blocked_signals'] += 1
            self.stats['blocked_by_group_limit'] += 1

            # 🔧 ИСПРАВЛЕНО: Убираем дубликаты из active_signals перед возвратом (для логирования)
            unique_active_signals = []
            seen_unique = set()
            for sig in active_signals:
                unique_key = f"{sig['symbol']}_{sig.get('user_id', 'all')}"
                if unique_key not in seen_unique:
                    unique_active_signals.append(sig)
                    seen_unique.add(unique_key)

            return {
                'allowed': False,
                'reason': 'GROUP_LIMIT_EXCEEDED',
                'details': (
                    f'Группа {symbol_group}: '
                    f'{len(unique_active_signals)}/{group_limit} сигналов (лимит достигнут)'
                ),
                'active_signals': unique_active_signals,  # 🔧 Возвращаем только уникальные
                'group': symbol_group,
                'limit': group_limit
            }

        self.stats['approved_signals'] += 1

        # 🔧 ИСПРАВЛЕНО: Убираем дубликаты из active_signals перед возвратом
        unique_active_signals = []
        seen_unique = set()
        for sig in active_signals:
            unique_key = f"{sig['symbol']}_{sig.get('user_id', 'all')}"
            if unique_key not in seen_unique:
                unique_active_signals.append(sig)
                seen_unique.add(unique_key)

        return {
            'allowed': True,
            'reason': 'NO_RISK',
            'details': (
                'Сигнал разрешен '
                f'(группа: {symbol_group}, активных: {len(unique_active_signals)}/{group_limit}, '
                f'открытых: {len(open_positions)})'
            ),
            'active_signals': unique_active_signals,  # 🔧 Возвращаем только уникальные
            'open_positions': open_positions
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
        Проверяет корреляционный риск портфеля к SOL

        Возвращает:
        - correlation_to_sol: средняя корреляция портфеля к SOL
        - sol_positions_count: количество позиций в SOL_HIGH
        - risk_level: уровень риска (LOW/MEDIUM/HIGH/CRITICAL)
        - alerts: список предупреждений
        """
        try:
            current_time = int(time.time())
            cooldown = CORRELATION_COOLDOWN_SEC

            # Получаем активные сигналы из SOL_HIGH
            if active_signals is None:
                active_signals = [
                    s for s in self.signal_history_cache
                    if s.get('sector') == 'SOL_HIGH'
                    and (current_time - s['timestamp']) < cooldown
                ]
            else:
                # Фильтруем только SOL_HIGH
                active_signals = [
                    s for s in active_signals
                    if s.get('sector') == 'SOL_HIGH'
                    and (current_time - s.get('timestamp', 0)) < cooldown
                ]

            sol_positions_count = len(set(s.get('symbol') for s in active_signals))

            # Вычисляем среднюю корреляцию к SOL
            correlations = []
            for signal in active_signals:
                symbol = signal.get('symbol')
                if symbol:
                    try:
                        corr = await self.calculate_correlation(symbol, 'SOL')
                        if corr > 0:
                            correlations.append(corr)
                    except Exception as e:
                        logger.debug("Ошибка расчета корреляции для %s: %s", symbol, e)

            correlation_to_sol = np.mean(correlations) if correlations else 0.0

            # Определяем уровень риска
            risk_level = "LOW"
            alerts = []

            if sol_positions_count >= 8:
                risk_level = "HIGH"
                alerts.append(f"🚨 ВЫСОКАЯ КОНЦЕНТРАЦИЯ: {sol_positions_count} позиций в SOL_HIGH (лимит: 10)")
            elif sol_positions_count >= 6:
                risk_level = "MEDIUM"
                alerts.append(f"⚠️ Средняя концентрация: {sol_positions_count} позиций в SOL_HIGH")

            if correlation_to_sol > 0.9:
                risk_level = "CRITICAL"
                alerts.append(f"🚨 КРИТИЧЕСКАЯ КОРРЕЛЯЦИЯ: {correlation_to_sol:.2f} к SOL (порог: 0.90)")
            elif correlation_to_sol > 0.85:
                if risk_level == "LOW":
                    risk_level = "MEDIUM"
                alerts.append(f"⚠️ Высокая корреляция: {correlation_to_sol:.2f} к SOL (порог: 0.85)")

            return {
                'correlation_to_sol': correlation_to_sol,
                'sol_positions_count': sol_positions_count,
                'risk_level': risk_level,
                'alerts': alerts,
                'timestamp': current_time
            }

        except Exception as e:
            logger.error("❌ Ошибка проверки корреляционного риска портфеля: %s", e)
            return {
                'correlation_to_sol': 0.0,
                'sol_positions_count': 0,
                'risk_level': 'UNKNOWN',
                'alerts': [f"Ошибка расчета: {str(e)}"],
                'timestamp': int(time.time())
            }

    def calculate_dynamic_limit(self, base_limit: int, market_volatility: float = None) -> int:
        """
        Вычисляет динамический лимит на основе волатильности рынка

        Args:
            base_limit: базовый лимит (например, 10 для SOL_HIGH)
            market_volatility: волатильность рынка (0.0-1.0), если None - использует базовый лимит

        Returns:
            Динамический лимит
        """
        if market_volatility is None:
            return base_limit

        # Высокая волатильность (>0.15) → уменьшаем лимит
        if market_volatility > 0.15:
            return max(6, int(base_limit * 0.6))  # Минимум 6
        # Низкая волатильность (<0.05) → полный лимит
        elif market_volatility < 0.05:
            return base_limit
        # Средняя волатильность → средний лимит
        else:
            return max(8, int(base_limit * 0.8))  # Минимум 8

    async def get_risk_alerts(self, active_signals: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Получает список алертов по рискам

        Returns:
            Список алертов с уровнем критичности
        """
        alerts = []

        try:
            # Проверяем корреляционный риск портфеля
            portfolio_risk = await self.check_portfolio_correlation_risk(active_signals)

            # Алерты по корреляции
            if portfolio_risk['correlation_to_sol'] > 0.9:
                alerts.append({
                    'level': 'CRITICAL',
                    'type': 'CORRELATION',
                    'message': f"🚨 КРИТИЧЕСКАЯ КОРРЕЛЯЦИЯ: {portfolio_risk['correlation_to_sol']:.2f} к SOL",
                    'action': 'REDUCE: Рассмотреть снижение лимита SOL_HIGH'
                })
            elif portfolio_risk['correlation_to_sol'] > 0.85:
                alerts.append({
                    'level': 'WARNING',
                    'type': 'CORRELATION',
                    'message': f"⚠️ Высокая корреляция: {portfolio_risk['correlation_to_sol']:.2f} к SOL",
                    'action': 'MONITOR: Требуется диверсификация'
                })

            # Алерты по количеству позиций
            if portfolio_risk['sol_positions_count'] >= 8:
                alerts.append({
                    'level': 'WARNING',
                    'type': 'CONCENTRATION',
                    'message': f"⚠️ Высокая концентрация: {portfolio_risk['sol_positions_count']} позиций в SOL_HIGH",
                    'action': 'MONITOR: Следить за рисками'
                })

            # Добавляем алерты из portfolio_risk
            for alert_msg in portfolio_risk.get('alerts', []):
                if '🚨' in alert_msg:
                    level = 'CRITICAL'
                elif '⚠️' in alert_msg:
                    level = 'WARNING'
                else:
                    level = 'INFO'

                alerts.append({
                    'level': level,
                    'type': 'PORTFOLIO',
                    'message': alert_msg,
                    'action': 'MONITOR'
                })

        except Exception as e:
            logger.error("❌ Ошибка получения алертов: %s", e)
            alerts.append({
                'level': 'ERROR',
                'type': 'SYSTEM',
                'message': f"Ошибка системы мониторинга: {str(e)}",
                'action': 'CHECK: Проверить логи'
            })

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
