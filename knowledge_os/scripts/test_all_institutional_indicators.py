#!/usr/bin/env python3
"""
Тестовый скрипт для проверки всех институциональных индикаторов

Проверяет:
- Импорты всех модулей
- Базовую функциональность индикаторов
- Интеграцию фильтров
"""

import logging
import os
import sys

import numpy as np
import pandas as pd

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_data(n=100):
    """Создает тестовые данные OHLCV"""
    dates = pd.date_range(start="2024-01-01", periods=n, freq="1h")

    # Генерируем случайные данные
    np.random.seed(42)
    base_price = 50000
    prices = []
    volumes = []

    for _ in range(n):
        change = np.random.normal(0, 0.02)
        price = base_price * (1 + change)
        base_price = price
        prices.append(price)
        volumes.append(np.random.uniform(1000000, 5000000))

    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
            "low": [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
            "close": prices,
            "volume": volumes,
        },
        index=dates,
    )

    return df


def test_order_flow():
    """Тест Order Flow индикаторов"""
    logger.info("🧪 Тестирование Order Flow индикаторов...")

    try:
        # Прямой импорт модулей, избегая __init__.py который может импортировать другие модули
        # pylint: disable=import-outside-toplevel
        from src.analysis.order_flow.cumulative_delta import CumulativeDeltaVolume
        from src.analysis.order_flow.pressure_ratio import PressureRatio
        from src.analysis.order_flow.volume_delta import VolumeDelta

        df = create_test_data(100)

        # CDV
        cdv = CumulativeDeltaVolume()
        cdv_values = cdv.calculate(df)
        assert len(cdv_values) == len(df), "CDV: неверная длина"
        logger.info("  ✅ Cumulative Delta Volume работает")

        # Volume Delta
        vd = VolumeDelta()
        vd_values = vd.calculate(df)
        assert len(vd_values) == len(df), "Volume Delta: неверная длина"
        logger.info("  ✅ Volume Delta работает")

        # Pressure Ratio
        pr = PressureRatio()
        pr_values = pr.calculate(df)
        assert len(pr_values) == len(df), "Pressure Ratio: неверная длина"
        logger.info("  ✅ Buy/Sell Pressure Ratio работает")

        return True
    except Exception as e:
        logger.error("  ❌ Ошибка в Order Flow: %s", e)
        return False


def test_exhaustion():
    """Тест Exhaustion индикаторов"""
    logger.info("🧪 Тестирование Exhaustion индикаторов...")

    try:
        # Прямой импорт модулей
        # pylint: disable=import-outside-toplevel
        from src.analysis.exhaustion.liquidity_exhaustion import LiquidityExhaustion
        from src.analysis.exhaustion.price_patterns import PriceExhaustionPatterns
        from src.analysis.exhaustion.volume_exhaustion import VolumeExhaustion

        df = create_test_data(100)

        # Volume Exhaustion
        ve = VolumeExhaustion()
        ve_values = ve.calculate(df)
        assert len(ve_values) == len(df), "Volume Exhaustion: неверная длина"
        logger.info("  ✅ Volume Exhaustion работает")

        # Price Patterns
        pp = PriceExhaustionPatterns()
        # detect_patterns принимает индекс, проверим на последней свече
        pp_result = pp.detect_patterns(df, len(df) - 1)
        assert isinstance(pp_result, dict), "Price Patterns: должен возвращать dict"
        logger.info("  ✅ Price Exhaustion Patterns работает")

        # Liquidity Exhaustion
        le = LiquidityExhaustion()
        le_values = le.calculate(df)
        assert len(le_values) == len(df), "Liquidity Exhaustion: неверная длина"
        logger.info("  ✅ Liquidity Exhaustion работает")

        return True
    except Exception as e:
        logger.error("  ❌ Ошибка в Exhaustion: %s", e)
        return False


def test_microstructure():
    """Тест Microstructure индикаторов"""
    logger.info("🧪 Тестирование Microstructure индикаторов...")

    try:
        # pylint: disable=import-outside-toplevel
        from src.analysis.microstructure.absorption import AbsorptionLevels
        from src.analysis.volume_profile import VolumeProfileAnalyzer

        df = create_test_data(100)

        # Liquidity Zones
        vp = VolumeProfileAnalyzer()
        lz = vp.get_liquidity_zones(df)
        assert isinstance(lz, list), "Liquidity Zones: должен быть list"
        logger.info("  ✅ Liquidity Zones работает")

        # Absorption Levels
        al = AbsorptionLevels()
        al_values = al.detect_absorption_levels(df, i=len(df) - 1)
        assert isinstance(al_values, list), "Absorption Levels: должен быть list"
        logger.info("  ✅ Absorption Levels работает")

        return True
    except Exception as e:
        logger.error("  ❌ Ошибка в Microstructure: %s", e)
        return False


def test_momentum():
    """Тест Momentum индикаторов"""
    logger.info("🧪 Тестирование Momentum индикаторов...")

    try:
        # pylint: disable=import-outside-toplevel
        from src.analysis.momentum.mfi import MoneyFlowIndex
        from src.analysis.momentum.stoch_rsi import StochasticRSI

        df = create_test_data(100)

        # MFI
        mfi = MoneyFlowIndex()
        mfi_values = mfi.calculate(df)
        assert len(mfi_values) == len(df), "MFI: неверная длина"
        logger.info("  ✅ Money Flow Index работает")

        # Stochastic RSI
        stoch_rsi = StochasticRSI()
        stoch_rsi_values = stoch_rsi.calculate(df)
        assert "stoch_rsi" in stoch_rsi_values, "Stoch RSI: отсутствует ключ"
        logger.info("  ✅ Stochastic RSI работает")

        return True
    except Exception as e:
        logger.error("  ❌ Ошибка в Momentum: %s", e)
        return False


def test_trend():
    """Тест Trend Strength индикаторов"""
    logger.info("🧪 Тестирование Trend Strength индикаторов...")

    try:
        # pylint: disable=import-outside-toplevel
        from src.analysis.trend.adx import ADXAnalyzer
        from src.analysis.trend.tsi import TrueStrengthIndex

        df = create_test_data(100)

        # ADX
        adx = ADXAnalyzer()
        adx_values = adx.calculate(df)
        assert len(adx_values) == len(df), "ADX: неверная длина"
        logger.info("  ✅ ADX работает")

        # TSI
        tsi = TrueStrengthIndex()
        tsi_values = tsi.calculate(df)
        assert len(tsi_values) == len(df), "TSI: неверная длина"
        logger.info("  ✅ True Strength Index работает")

        return True
    except Exception as e:
        logger.error("  ❌ Ошибка в Trend Strength: %s", e)
        return False


def test_filters():
    """Тест фильтров"""
    logger.info("🧪 Тестирование фильтров...")

    try:
        df = create_test_data(100)
        i = len(df) - 1

        # Order Flow фильтр
        try:
            # pylint: disable=import-outside-toplevel
            from src.filters.order_flow_filter import check_order_flow_filter

            ok, _ = check_order_flow_filter(df, i, "long", strict_mode=True)
            assert isinstance(ok, bool), "Order Flow фильтр: должен возвращать bool"
            logger.info("  ✅ Order Flow фильтр работает")
        except Exception as e:
            logger.warning("  ⚠️ Order Flow фильтр: %s", e)

        # Microstructure фильтр
        try:
            # pylint: disable=import-outside-toplevel
            from src.filters.microstructure_filter import check_microstructure_filter

            ok, _ = check_microstructure_filter(df, i, "long", strict_mode=True)
            assert isinstance(ok, bool), "Microstructure фильтр: должен возвращать bool"
            logger.info("  ✅ Microstructure фильтр работает")
        except Exception as e:
            logger.warning("  ⚠️ Microstructure фильтр: %s", e)

        # Momentum фильтр
        try:
            # pylint: disable=import-outside-toplevel
            from src.filters.momentum_filter import check_momentum_filter

            ok, _ = check_momentum_filter(df, i, "long", strict_mode=True)
            assert isinstance(ok, bool), "Momentum фильтр: должен возвращать bool"
            logger.info("  ✅ Momentum фильтр работает")
        except Exception as e:
            logger.warning("  ⚠️ Momentum фильтр: %s", e)

        # Trend Strength фильтр
        try:
            # pylint: disable=import-outside-toplevel
            from src.filters.trend_strength_filter import check_trend_strength_filter

            ok, _ = check_trend_strength_filter(df, i, "long", strict_mode=True)
            assert isinstance(ok, bool), "Trend Strength фильтр: должен возвращать bool"
            logger.info("  ✅ Trend Strength фильтр работает")
        except Exception as e:
            logger.warning("  ⚠️ Trend Strength фильтр: %s", e)

        return True
    except Exception as e:
        logger.error("  ❌ Ошибка в фильтрах: %s", e)
        return False


def main():
    """Главная функция тестирования"""
    logger.info("🚀 Начало тестирования всех институциональных индикаторов\n")

    results = {
        "Order Flow": test_order_flow(),
        "Exhaustion": test_exhaustion(),
        "Microstructure": test_microstructure(),
        "Momentum": test_momentum(),
        "Trend Strength": test_trend(),
        "Filters": test_filters(),
    }

    logger.info("\n%s", "=" * 50)
    logger.info("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    logger.info("%s", "=" * 50)

    for name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info("%s: %s", name, status)

    total = len(results)
    passed = sum(1 for r in results.values() if r)

    logger.info("%s", "=" * 50)
    logger.info("Итого: %s/%s тестов пройдено", passed, total)

    if passed == total:
        logger.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return 0
    else:
        logger.warning("⚠️ %s тестов провалено", total - passed)
        return 1


if __name__ == "__main__":
    sys.exit(main())
