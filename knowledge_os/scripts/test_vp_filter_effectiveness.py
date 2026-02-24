#!/usr/bin/env python3
"""
Тест эффективности Volume Profile фильтра
Сравнение: baseline vs только VP фильтр vs VP+VWAP
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

import pandas as pd

from scripts.backtest_5coins_intelligent import (
    FEE,
    RISK_PER_TRADE,
    START_BALANCE,
    add_technical_indicators,
    get_symbol_tp_sl_multipliers,
    load_yearly_data,
)
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

logging.basicConfig(level=logging.WARNING)  # Уменьшаем логирование
logger = logging.getLogger(__name__)

# Тестовые символы
TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]

# Период для теста
PERIOD_DAYS = 7


def count_signals_baseline(df, symbol):
    """Подсчитывает сигналы baseline (без фильтров)"""
    import src.signals.core as core_module
    from src.signals.core import soft_entry_signal

    # Отключаем фильтры
    os.environ["USE_VP_FILTER"] = "False"
    os.environ["USE_VWAP_FILTER"] = "False"
    os.environ["DISABLE_EXTRA_FILTERS"] = "true"

    # Очищаем кэш модулей
    if "src.signals.core" in sys.modules:
        del sys.modules["src.signals.core"]
    if "src.signals" in sys.modules:
        del sys.modules["src.signals"]
    if "config" in sys.modules:
        del sys.modules["config"]

    # Импортируем заново

    df = add_technical_indicators(df)
    start_idx = 25

    if len(df) < start_idx:
        return 0

    signals = 0
    for i in range(start_idx, len(df)):
        side, entry_price = soft_entry_signal(df, i)
        if side and entry_price:
            signals += 1

    return signals


def count_signals_vp_only(df, symbol):
    """Подсчитывает сигналы с только Volume Profile фильтром"""
    import src.signals.core as core_module
    from config import USE_VP_FILTER
    from src.signals.filters_volume_vwap import check_volume_profile_filter

    # Включаем только VP фильтр
    os.environ["USE_VP_FILTER"] = "True"
    os.environ["USE_VWAP_FILTER"] = "False"
    os.environ["DISABLE_EXTRA_FILTERS"] = "true"
    os.environ["volume_profile_threshold"] = "0.6"

    # Очищаем кэш модулей
    if "src.signals.core" in sys.modules:
        del sys.modules["src.signals.core"]
    if "src.signals" in sys.modules:
        del sys.modules["src.signals"]
    if "config" in sys.modules:
        del sys.modules["config"]

    # Импортируем заново
    from src.signals.core import soft_entry_signal

    df = add_technical_indicators(df)
    start_idx = 25

    if len(df) < start_idx:
        return 0, 0

    signals_baseline = 0
    signals_after_vp = 0
    vp_blocked = 0

    for i in range(start_idx, len(df)):
        # Проверяем baseline сигнал
        side, entry_price = soft_entry_signal(df, i)

        if side and entry_price:
            signals_baseline += 1

            # Проверяем VP фильтр
            vp_ok, vp_reason = check_volume_profile_filter(df, i, "long", strict_mode=False)

            if vp_ok:
                signals_after_vp += 1
            else:
                vp_blocked += 1

    return signals_baseline, signals_after_vp, vp_blocked


def count_signals_vp_vwap(df, symbol):
    """Подсчитывает сигналы с VP и VWAP фильтрами"""
    import src.signals.core as core_module
    from config import USE_VP_FILTER, USE_VWAP_FILTER
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter

    # Включаем оба фильтра
    os.environ["USE_VP_FILTER"] = "True"
    os.environ["USE_VWAP_FILTER"] = "True"
    os.environ["DISABLE_EXTRA_FILTERS"] = "true"
    os.environ["volume_profile_threshold"] = "0.6"
    os.environ["vwap_threshold"] = "0.8"

    # Очищаем кэш модулей
    if "src.signals.core" in sys.modules:
        del sys.modules["src.signals.core"]
    if "src.signals" in sys.modules:
        del sys.modules["src.signals"]
    if "config" in sys.modules:
        del sys.modules["config"]

    # Импортируем заново
    from src.signals.core import soft_entry_signal

    df = add_technical_indicators(df)
    start_idx = 25

    if len(df) < start_idx:
        return 0, 0, 0, 0

    signals_baseline = 0
    signals_after_vp = 0
    signals_after_vwap = 0
    vp_blocked = 0
    vwap_blocked = 0

    for i in range(start_idx, len(df)):
        # Проверяем baseline сигнал
        side, entry_price = soft_entry_signal(df, i)

        if side and entry_price:
            signals_baseline += 1

            # Проверяем VP фильтр
            vp_ok, vp_reason = check_volume_profile_filter(df, i, "long", strict_mode=False)

            if vp_ok:
                signals_after_vp += 1

                # Проверяем VWAP фильтр
                vwap_ok, vwap_reason = check_vwap_filter(df, i, "long", strict_mode=False)

                if vwap_ok:
                    signals_after_vwap += 1
                else:
                    vwap_blocked += 1
            else:
                vp_blocked += 1

    return signals_baseline, signals_after_vp, signals_after_vwap, vp_blocked, vwap_blocked


def test_vp_effectiveness():
    """Тестирует эффективность Volume Profile фильтра"""
    print("=" * 80)
    print("🔍 АНАЛИЗ ЭФФЕКТИВНОСТИ VOLUME PROFILE ФИЛЬТРА")
    print("=" * 80)
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("=" * 80)
    print()

    total_baseline = 0
    total_vp_only = 0
    total_vp_vwap = 0
    total_vp_blocked = 0
    total_vwap_blocked = 0

    for symbol in TEST_SYMBOLS:
        print(f"\n📊 Анализ {symbol}...")
        try:
            df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
            if df is None or len(df) < 25:
                print("   ❌ Недостаточно данных")
                continue

            # 1. Baseline (без фильтров)
            baseline_signals = count_signals_baseline(df, symbol)
            total_baseline += baseline_signals

            # 2. Только VP фильтр
            baseline_vp, vp_signals, vp_blocked = count_signals_vp_only(df, symbol)
            total_vp_only += vp_signals
            total_vp_blocked += vp_blocked

            # 3. VP + VWAP фильтры
            baseline_vp_vwap, vp_signals_vwap, vwap_signals, vp_blocked_vwap, vwap_blocked_vwap = (
                count_signals_vp_vwap(df, symbol)
            )
            total_vp_vwap += vwap_signals
            total_vwap_blocked += vwap_blocked_vwap

            print(f"   📈 Baseline сигналов: {baseline_signals}")
            print(
                f"   🔵 После VP фильтра: {vp_signals} (заблокировано: {vp_blocked}, {vp_blocked / baseline_signals * 100:.1f}%)"
            )
            print(
                f"   🟢 После VP+VWAP: {vwap_signals} (VWAP заблокировал: {vwap_blocked_vwap}, {vwap_blocked_vwap / vp_signals_vwap * 100:.1f}%)"
            )

        except Exception as e:
            print(f"   ❌ Ошибка для {symbol}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    print(f"📈 Baseline сигналов (без фильтров): {total_baseline}")
    print(
        f"🔵 После VP фильтра: {total_vp_only} (заблокировано: {total_vp_blocked}, {total_vp_blocked / total_baseline * 100:.1f}%)"
    )
    print(
        f"🟢 После VP+VWAP: {total_vp_vwap} (VWAP заблокировал: {total_vwap_blocked}, {total_vwap_blocked / total_vp_only * 100:.1f}%)"
    )
    print("=" * 80)
    print()

    if total_baseline > 0:
        vp_effectiveness = (total_vp_blocked / total_baseline) * 100
        print("💡 ВЫВОД:")
        print(f"   - Volume Profile блокирует {vp_effectiveness:.1f}% сигналов")
        if vp_effectiveness < 5:
            print("   ⚠️ Фильтр практически не работает (блокирует <5%)")
        elif vp_effectiveness < 20:
            print("   ⚠️ Фильтр слабо эффективен (блокирует <20%)")
        else:
            print("   ✅ Фильтр эффективен (блокирует >20%)")

    return {
        "baseline": total_baseline,
        "vp_only": total_vp_only,
        "vp_vwap": total_vp_vwap,
        "vp_blocked": total_vp_blocked,
        "vwap_blocked": total_vwap_blocked,
    }


if __name__ == "__main__":
    test_vp_effectiveness()
