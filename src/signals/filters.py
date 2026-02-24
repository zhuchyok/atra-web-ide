#!/usr/bin/env python3
"""
Модуль фильтров сигналов
Вынесен из signal_live.py для рефакторинга
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Импорты для гибридного менеджера данных
try:
    from hybrid_data_manager import hybrid_data_manager

    HYBRID_DATA_MANAGER_AVAILABLE = True
    HYBRID_DATA_MANAGER = hybrid_data_manager
except ImportError:
    HYBRID_DATA_MANAGER_AVAILABLE = False
    HYBRID_DATA_MANAGER = None


async def check_btc_alignment(symbol: str, signal_type: str) -> bool:
    """
    Проверяет соответствие сигнала тренду BTC

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)

    Returns:
        True если сигнал соответствует тренду BTC, False если нет
    """
    try:
        # Получаем данные BTC через гибридный менеджер
        btc_df = await HYBRID_DATA_MANAGER.get_smart_data("BTCUSDT", "ohlc")

        # Проверяем тип данных и валидность
        if btc_df is None:
            logger.debug("⚠️ [%s] Нет данных BTC для проверки тренда (None)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Если это список словарей, конвертируем в DataFrame
        if isinstance(btc_df, list):
            if len(btc_df) == 0:
                logger.debug(
                    "⚠️ [%s] Данные BTC - пустой список, пропускаем проверку тренда", symbol
                )
                return True

            # Конвертируем список словарей в DataFrame
            try:
                btc_df = pd.DataFrame(btc_df)
                # Конвертируем timestamp в datetime если нужно
                if "timestamp" in btc_df.columns:
                    btc_df["timestamp"] = pd.to_datetime(
                        btc_df["timestamp"], unit="ms", errors="coerce"
                    )
                    btc_df.set_index("timestamp", inplace=True)
                logger.debug(
                    "✅ [%s] Данные BTC конвертированы из списка в DataFrame (%d строк)",
                    symbol,
                    len(btc_df),
                )
            except Exception as e:
                logger.warning("⚠️ [%s] Ошибка конвертации списка BTC в DataFrame: %s", symbol, e)
                return True

        # Проверяем, что это DataFrame и он не пустой
        if not isinstance(btc_df, pd.DataFrame):
            logger.debug(
                "⚠️ [%s] Данные BTC не являются DataFrame (тип: %s), пропускаем",
                symbol,
                type(btc_df),
            )
            return True

        if btc_df.empty or len(btc_df) < 50:
            logger.debug("⚠️ [%s] Нет данных BTC для проверки тренда (пусто или < 50 строк)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # 🆕 Оптимизированный анализ тренда BTC для интрадей
        # Используем оптимизированные EMA (10/22 вместо 12/26)
        ema_fast_period = 10  # 🆕 Оптимизировано: было 12
        ema_slow_period = 22  # 🆕 Оптимизировано: было 26

        btc_ema_fast = (
            btc_df["ema_fast"].iloc[-1]
            if "ema_fast" in btc_df.columns
            else btc_df["close"].ewm(span=ema_fast_period).mean().iloc[-1]
        )
        btc_ema_slow = (
            btc_df["ema_slow"].iloc[-1]
            if "ema_slow" in btc_df.columns
            else btc_df["close"].ewm(span=ema_slow_period).mean().iloc[-1]
        )

        # 🆕 Проверяем силу тренда
        min_trend_strength = 0.002  # Минимальная сила тренда
        trend_strength = abs(btc_ema_fast - btc_ema_slow) / btc_ema_slow if btc_ema_slow > 0 else 0

        if trend_strength < min_trend_strength:  # Слабый тренд
            logger.debug(
                "⚠️ [BTC] Слабый тренд: %.3f%% - разрешаем торговлю в боковике", trend_strength * 100
            )
            return True  # Разрешаем торговлю в боковике

        btc_trend = "BUY" if btc_ema_fast > btc_ema_slow else "SELL"

        # 🆕 Блокируем только сильные противотрендовые сигналы
        if signal_type == "BUY" and btc_trend == "SELL":
            if trend_strength > 0.01:  # Сильный медвежий тренд
                logger.warning(
                    "🚫 [BTC FILTER] %s: LONG против сильного BTC тренда (strength=%.3f%%) - блокируем",
                    symbol,
                    trend_strength * 100,
                )
                # Логируем блокировку
                try:
                    from src.utils.filter_logger import log_filter_check_async

                    log_filter_check_async(
                        symbol=symbol,
                        filter_type="btc_trend",
                        passed=False,
                        reason=f"LONG против сильного BTC тренда (strength={trend_strength * 100:.3f}%)",
                    )
                except (ImportError, Exception):
                    pass
                return False
            else:
                logger.debug(
                    "⚠️ [BTC] %s: LONG против слабого BTC тренда (strength=%.3f%%) - разрешаем",
                    symbol,
                    trend_strength * 100,
                )
                return True

        if signal_type == "SELL" and btc_trend == "BUY":
            if trend_strength > 0.01:  # Сильный бычий тренд
                logger.warning(
                    "🚫 [BTC FILTER] %s: SHORT против сильного BTC тренда (strength=%.3f%%) - блокируем",
                    symbol,
                    trend_strength * 100,
                )
                # Логируем блокировку
                try:
                    from src.utils.filter_logger import log_filter_check_async

                    log_filter_check_async(
                        symbol=symbol,
                        filter_type="btc_trend",
                        passed=False,
                        reason=f"SHORT против сильного BTC тренда (strength={trend_strength * 100:.3f}%)",
                    )
                except (ImportError, Exception):
                    pass
                return False
            else:
                logger.debug(
                    "⚠️ [BTC] %s: SHORT против слабого BTC тренда (strength=%.3f%%) - разрешаем",
                    symbol,
                    trend_strength * 100,
                )
                return True

        logger.debug("✅ [BTC FILTER] %s: тренд совпадает с BTC (%s)", symbol, btc_trend)

        # Логируем успешное прохождение фильтра
        try:
            from src.utils.filter_logger import log_filter_check_async

            log_filter_check_async(symbol=symbol, filter_type="btc_trend", passed=True, reason=None)
        except (ImportError, Exception):
            pass

        return True
    except Exception as e:
        logger.debug("⚠️ Ошибка проверки BTC тренда для %s: %s (пропускаем)", symbol, e)
        return True


async def check_eth_alignment(symbol: str, signal_type: str) -> bool:
    """
    Проверяет соответствие сигнала тренду ETH

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)

    Returns:
        True если сигнал соответствует тренду ETH, False если нет
    """
    try:
        # Получаем данные ETH через гибридный менеджер
        eth_df = await HYBRID_DATA_MANAGER.get_smart_data("ETHUSDT", "ohlc")

        # Проверяем тип данных и валидность
        if eth_df is None:
            logger.debug("⚠️ [%s] Нет данных ETH для проверки тренда (None)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Если это список словарей, конвертируем в DataFrame
        if isinstance(eth_df, list):
            if len(eth_df) == 0:
                logger.debug(
                    "⚠️ [%s] Данные ETH - пустой список, пропускаем проверку тренда", symbol
                )
                return True

            # Конвертируем список словарей в DataFrame
            try:
                eth_df = pd.DataFrame(eth_df)
                # Конвертируем timestamp в datetime если нужно
                if "timestamp" in eth_df.columns:
                    eth_df["timestamp"] = pd.to_datetime(
                        eth_df["timestamp"], unit="ms", errors="coerce"
                    )
                    eth_df.set_index("timestamp", inplace=True)
                logger.debug(
                    "✅ [%s] Данные ETH конвертированы из списка в DataFrame (%d строк)",
                    symbol,
                    len(eth_df),
                )
            except Exception as e:
                logger.warning("⚠️ [%s] Ошибка конвертации списка ETH в DataFrame: %s", symbol, e)
                return True

        # Проверяем, что это DataFrame и он не пустой
        if not isinstance(eth_df, pd.DataFrame):
            logger.debug(
                "⚠️ [%s] Данные ETH не являются DataFrame (тип: %s), пропускаем",
                symbol,
                type(eth_df),
            )
            return True

        if eth_df.empty or len(eth_df) < 50:
            logger.debug("⚠️ [%s] Нет данных ETH для проверки тренда (пусто или < 50 строк)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # 🆕 Оптимизированный анализ тренда ETH для интрадей
        ema_fast_period = 10  # 🆕 Оптимизировано: было 12
        ema_slow_period = 22  # 🆕 Оптимизировано: было 26

        eth_ema_fast = (
            eth_df["ema_fast"].iloc[-1]
            if "ema_fast" in eth_df.columns
            else eth_df["close"].ewm(span=ema_fast_period).mean().iloc[-1]
        )
        eth_ema_slow = (
            eth_df["ema_slow"].iloc[-1]
            if "ema_slow" in eth_df.columns
            else eth_df["close"].ewm(span=ema_slow_period).mean().iloc[-1]
        )

        # 🆕 Проверяем силу тренда
        min_trend_strength = 0.002
        trend_strength = abs(eth_ema_fast - eth_ema_slow) / eth_ema_slow if eth_ema_slow > 0 else 0

        if trend_strength < min_trend_strength:
            logger.debug(
                "⚠️ [ETH] Слабый тренд: %.3f%% - разрешаем торговлю в боковике", trend_strength * 100
            )
            return True

        eth_trend = "BUY" if eth_ema_fast > eth_ema_slow else "SELL"

        # 🆕 Блокируем только сильные противотрендовые сигналы (ИСПРАВЛЕНО: порог 2% вместо 1%)
        if signal_type == "BUY" and eth_trend == "SELL":
            if trend_strength > 0.02:  # 🔧 ИСПРАВЛЕНО: было 0.01 (1%), повышен до 0.02 (2%)
                logger.warning(
                    "🚫 [ETH FILTER] %s: LONG против сильного ETH тренда (strength=%.3f%%) - блокируем",
                    symbol,
                    trend_strength * 100,
                )
                # Логируем блокировку
                try:
                    from src.utils.filter_logger import log_filter_check_async

                    log_filter_check_async(
                        symbol=symbol,
                        filter_type="eth_trend",
                        passed=False,
                        reason=f"LONG против сильного ETH тренда (strength={trend_strength * 100:.3f}%)",
                    )
                except (ImportError, Exception):
                    pass
                return False
            else:
                logger.debug(
                    "⚠️ [ETH] %s: LONG против слабого ETH тренда (strength=%.3f%%) - разрешаем",
                    symbol,
                    trend_strength * 100,
                )
                return True

        if signal_type == "SELL" and eth_trend == "BUY":
            if trend_strength > 0.02:  # 🔧 ИСПРАВЛЕНО: было 0.01 (1%), повышен до 0.02 (2%)
                logger.warning(
                    "🚫 [ETH FILTER] %s: SHORT против сильного ETH тренда (strength=%.3f%%) - блокируем",
                    symbol,
                    trend_strength * 100,
                )
                # Логируем блокировку
                try:
                    from src.utils.filter_logger import log_filter_check_async

                    log_filter_check_async(
                        symbol=symbol,
                        filter_type="eth_trend",
                        passed=False,
                        reason=f"SHORT против сильного ETH тренда (strength={trend_strength * 100:.3f}%)",
                    )
                except (ImportError, Exception):
                    pass
                return False
            else:
                logger.debug(
                    "⚠️ [ETH] %s: SHORT против слабого ETH тренда (strength=%.3f%%) - разрешаем",
                    symbol,
                    trend_strength * 100,
                )
                return True

        logger.debug("✅ [ETH FILTER] %s: тренд совпадает с ETH (%s)", symbol, eth_trend)

        # Логируем успешное прохождение фильтра
        try:
            from src.utils.filter_logger import log_filter_check_async

            log_filter_check_async(symbol=symbol, filter_type="eth_trend", passed=True, reason=None)
        except (ImportError, Exception):
            pass

        return True
    except Exception as e:
        logger.debug("⚠️ Ошибка проверки ETH тренда для %s: %s (пропускаем)", symbol, e)
        return True


async def check_sol_alignment(symbol: str, signal_type: str) -> bool:
    """
    Проверяет соответствие сигнала тренду SOL

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)

    Returns:
        True если сигнал соответствует тренду SOL, False если нет
    """
    try:
        # Получаем данные SOL через гибридный менеджер
        sol_df = await HYBRID_DATA_MANAGER.get_smart_data("SOLUSDT", "ohlc")

        # Проверяем тип данных и валидность
        if sol_df is None:
            logger.debug("⚠️ [%s] Нет данных SOL для проверки тренда (None)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Если это список словарей, конвертируем в DataFrame
        if isinstance(sol_df, list):
            if len(sol_df) == 0:
                logger.debug(
                    "⚠️ [%s] Данные SOL - пустой список, пропускаем проверку тренда", symbol
                )
                return True

            # Конвертируем список словарей в DataFrame
            try:
                sol_df = pd.DataFrame(sol_df)
                # Конвертируем timestamp в datetime если нужно
                if "timestamp" in sol_df.columns:
                    sol_df["timestamp"] = pd.to_datetime(
                        sol_df["timestamp"], unit="ms", errors="coerce"
                    )
                    sol_df.set_index("timestamp", inplace=True)
                logger.debug(
                    "✅ [%s] Данные SOL конвертированы из списка в DataFrame (%d строк)",
                    symbol,
                    len(sol_df),
                )
            except Exception as e:
                logger.warning("⚠️ [%s] Ошибка конвертации списка SOL в DataFrame: %s", symbol, e)
                return True

        # Проверяем, что это DataFrame и он не пустой
        if not isinstance(sol_df, pd.DataFrame):
            logger.debug(
                "⚠️ [%s] Данные SOL не являются DataFrame (тип: %s), пропускаем",
                symbol,
                type(sol_df),
            )
            return True

        if sol_df.empty or len(sol_df) < 50:
            logger.debug("⚠️ [%s] Нет данных SOL для проверки тренда (пусто или < 50 строк)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # 🆕 Оптимизированный анализ тренда SOL для интрадей
        ema_fast_period = 10  # 🆕 Оптимизировано: было 12
        ema_slow_period = 22  # 🆕 Оптимизировано: было 26

        sol_ema_fast = (
            sol_df["ema_fast"].iloc[-1]
            if "ema_fast" in sol_df.columns
            else sol_df["close"].ewm(span=ema_fast_period).mean().iloc[-1]
        )
        sol_ema_slow = (
            sol_df["ema_slow"].iloc[-1]
            if "ema_slow" in sol_df.columns
            else sol_df["close"].ewm(span=ema_slow_period).mean().iloc[-1]
        )

        # 🆕 Проверяем силу тренда
        min_trend_strength = 0.002
        trend_strength = abs(sol_ema_fast - sol_ema_slow) / sol_ema_slow if sol_ema_slow > 0 else 0

        if trend_strength < min_trend_strength:
            logger.debug(
                "⚠️ [SOL] Слабый тренд: %.3f%% - разрешаем торговлю в боковике", trend_strength * 100
            )
            return True

        sol_trend = "BUY" if sol_ema_fast > sol_ema_slow else "SELL"

        # 🆕 Блокируем только сильные противотрендовые сигналы
        if signal_type == "BUY" and sol_trend == "SELL":
            if trend_strength > 0.01:
                logger.warning(
                    "🚫 [SOL FILTER] %s: LONG против сильного SOL тренда (strength=%.3f%%) - блокируем",
                    symbol,
                    trend_strength * 100,
                )
                # Логируем блокировку
                try:
                    from src.utils.filter_logger import log_filter_check_async

                    log_filter_check_async(
                        symbol=symbol,
                        filter_type="sol_trend",
                        passed=False,
                        reason=f"LONG против сильного SOL тренда (strength={trend_strength * 100:.3f}%)",
                    )
                except (ImportError, Exception):
                    pass
                return False
            else:
                logger.debug(
                    "⚠️ [SOL] %s: LONG против слабого SOL тренда (strength=%.3f%%) - разрешаем",
                    symbol,
                    trend_strength * 100,
                )
                return True

        if signal_type == "SELL" and sol_trend == "BUY":
            if trend_strength > 0.01:
                logger.warning(
                    "🚫 [SOL FILTER] %s: SHORT против сильного SOL тренда (strength=%.3f%%) - блокируем",
                    symbol,
                    trend_strength * 100,
                )
                # Логируем блокировку
                try:
                    from src.utils.filter_logger import log_filter_check_async

                    log_filter_check_async(
                        symbol=symbol,
                        filter_type="sol_trend",
                        passed=False,
                        reason=f"SHORT против сильного SOL тренда (strength={trend_strength * 100:.3f}%)",
                    )
                except (ImportError, Exception):
                    pass
                return False
            else:
                logger.debug(
                    "⚠️ [SOL] %s: SHORT против слабого SOL тренда (strength=%.3f%%) - разрешаем",
                    symbol,
                    trend_strength * 100,
                )
                return True

        logger.debug("✅ [SOL FILTER] %s: тренд совпадает с SOL (%s)", symbol, sol_trend)

        # Логируем успешное прохождение фильтра
        try:
            from src.utils.filter_logger import log_filter_check_async

            log_filter_check_async(symbol=symbol, filter_type="sol_trend", passed=True, reason=None)
        except (ImportError, Exception):
            pass

        return True
    except Exception as e:
        logger.debug("⚠️ Ошибка проверки SOL тренда для %s: %s (пропускаем)", symbol, e)
        return True
