#!/usr/bin/env python3
"""
🔍 АНАЛИЗ ОТКЛОНЕНИЙ VOLUME PROFILE ФИЛЬТРА
Анализирует, почему Volume Profile блокирует сигналы
"""

import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Dict

import pandas as pd

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импорты после добавления пути
from scripts.backtest_5coins_intelligent import TEST_SYMBOLS, load_yearly_data
from src.analysis.volume_profile import (
    VolumeProfileAnalyzer,  # pylint: disable=import-outside-toplevel
)
from src.signals.core import soft_entry_signal
from src.signals.filters_volume_vwap import check_volume_profile_filter
from src.signals.indicators import add_technical_indicators

# Включаем ТОЛЬКО Volume Profile фильтр для анализа
os.environ["USE_VP_FILTER"] = "True"
os.environ["USE_VWAP_FILTER"] = "False"
os.environ["USE_ORDER_FLOW_FILTER"] = "False"
os.environ["USE_MICROSTRUCTURE_FILTER"] = "False"
os.environ["USE_MOMENTUM_FILTER"] = "False"
os.environ["USE_TREND_STRENGTH_FILTER"] = "False"
os.environ["USE_AMT_FILTER"] = "False"
os.environ["USE_MARKET_PROFILE_FILTER"] = "False"
os.environ["DISABLE_EXTRA_FILTERS"] = "true"  # Отключаем дополнительные фильтры
os.environ["volume_profile_threshold"] = "0.6"  # Используем оптимальный параметр


def analyze_volume_profile_rejections(symbol: str, limit_days: int = 30) -> Dict:
    """Анализирует отклонения Volume Profile фильтра для символа"""
    # Определяем режим работы фильтра
    strict_mode = False

    print(f"\n{'=' * 80}")
    print(f"🔍 АНАЛИЗ VOLUME PROFILE ДЛЯ {symbol}")
    print(f"{'=' * 80}")

    # Загружаем данные
    df = load_yearly_data(symbol, limit_days=limit_days)
    if df is None or len(df) < 100:
        print(f"❌ Недостаточно данных для {symbol}")
        return {}

    df = add_technical_indicators(df)

    # 🔧 ВКЛЮЧАЕМ ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ
    logging.basicConfig(level=logging.DEBUG)

    # Статистика
    total_signals = 0
    signals_passed_base = 0
    signals_passed_vp = 0
    vp_rejections = []

    # Анализируем каждую свечу
    for i in range(100, len(df)):
        # Генерируем сигнал
        signal_side, _signal_price = soft_entry_signal(df, i)

        if signal_side is None:
            continue

        total_signals += 1
        signals_passed_base += 1

        # Проверяем Volume Profile фильтр
        vp_ok, vp_reason = check_volume_profile_filter(
            df, i, signal_side.lower(), strict_mode=strict_mode
        )
        if vp_ok:
            signals_passed_vp += 1
        else:
            # Собираем информацию об отклонении
            current_price = df["close"].iloc[i]
            try:
                # Используем тот же threshold, что в оптимизации
                os.environ["volume_profile_threshold"] = "0.6"
                vp_analyzer = VolumeProfileAnalyzer()
                volume_profile = vp_analyzer.calculate_volume_profile(
                    df.iloc[: i + 1], lookback_periods=50
                )
                poc = volume_profile.get("poc") if volume_profile else None
                val = volume_profile.get("value_area_low") if volume_profile else None
                vah = volume_profile.get("value_area_high") if volume_profile else None
                # 🔧 ДЕТАЛЬНЫЙ АНАЛИЗ: проверяем все условия
                tolerance_pct = float(os.environ.get("volume_profile_threshold", "1.0"))
                tolerance_pct = (
                    max(1.0, min(10.0, (1.0 / tolerance_pct) * 3.0)) if tolerance_pct > 0 else 1.0
                )
                distance_from_val_pct = (
                    abs(current_price - val) / current_price * 100 if val else None
                )
                distance_from_vah_pct = (
                    abs(current_price - vah) / current_price * 100 if vah else None
                )
                distance_from_poc_pct = (
                    abs(current_price - poc) / current_price * 100 if poc else None
                )
                # Проверяем условия для LONG
                long_conditions = {}
                if signal_side.lower() == "long":
                    if val:
                        long_conditions["near_val"] = distance_from_val_pct <= tolerance_pct
                        long_conditions["val_distance"] = distance_from_val_pct
                    long_conditions["below_poc"] = current_price <= poc if poc else False
                    if not strict_mode and vah and val:
                        long_conditions["in_value_area"] = val <= current_price <= vah
                # Проверяем условия для SHORT
                short_conditions = {}
                if signal_side.lower() == "short":
                    if vah:
                        short_conditions["near_vah"] = distance_from_vah_pct <= tolerance_pct
                        short_conditions["vah_distance"] = distance_from_vah_pct
                    short_conditions["above_poc"] = current_price >= poc if poc else False
                    if not strict_mode and vah and val:
                        short_conditions["in_value_area"] = val <= current_price <= vah
                vp_rejections.append(
                    {
                        "candle": i,
                        "side": signal_side,
                        "price": current_price,
                        "poc": poc,
                        "val": val,
                        "vah": vah,
                        "reason": vp_reason,
                        "tolerance_pct": tolerance_pct,
                        "distance_from_val_pct": distance_from_val_pct,
                        "distance_from_vah_pct": distance_from_vah_pct,
                        "distance_from_poc_pct": distance_from_poc_pct,
                        "long_conditions": long_conditions if signal_side.lower() == "long" else {},
                        "short_conditions": short_conditions
                        if signal_side.lower() == "short"
                        else {},
                        "strict_mode": False,
                    }
                )
            except Exception as e:
                vp_rejections.append(
                    {
                        "candle": i,
                        "side": signal_side,
                        "price": current_price,
                        "reason": f"Ошибка расчета VP: {e}",
                        "traceback": traceback.format_exc(),
                    }
                )

    # Выводим статистику
    rejection_rate = (
        (signals_passed_base - signals_passed_vp) / signals_passed_base * 100
        if signals_passed_base > 0
        else 0
    )

    print("\n📊 СТАТИСТИКА:")
    print(f"   Всего сигналов (базовые условия): {signals_passed_base}")
    print(f"   Прошло через VP фильтр: {signals_passed_vp}")
    print(f"   Отклонено VP фильтром: {signals_passed_base - signals_passed_vp}")
    print(f"   Процент отклонений: {rejection_rate:.1f}%")

    if vp_rejections:
        print("\n🔍 ПРИМЕРЫ ОТКЛОНЕНИЙ (первые 10):")
        for idx, rejection in enumerate(vp_rejections[:10], 1):
            print(f"\n   {idx}. Свеча {rejection['candle']}, {rejection['side']}:")
            print(f"      Цена: {rejection['price']:.2f}")
            if rejection.get("poc"):
                poc_dist = rejection.get("distance_from_poc_pct", 0)
                poc_price = rejection["poc"]
                print(f"      POC: {poc_price:.2f} (расстояние: {poc_dist:.2f}%)")
            if rejection.get("val"):
                val_dist = rejection.get("distance_from_val_pct", 0)
                val_price = rejection["val"]
                print(f"      VAL: {val_price:.2f} (расстояние: {val_dist:.2f}%)")
            if rejection.get("vah"):
                vah_dist = rejection.get("distance_from_vah_pct", 0)
                vah_price = rejection["vah"]
                print(f"      VAH: {vah_price:.2f} (расстояние: {vah_dist:.2f}%)")
            print(f"      Причина: {rejection['reason']}")

        # Анализ расстояний
        distances_val = [
            r["distance_from_val_pct"]
            for r in vp_rejections
            if r.get("distance_from_val_pct") is not None
        ]
        distances_vah = [
            r["distance_from_vah_pct"]
            for r in vp_rejections
            if r.get("distance_from_vah_pct") is not None
        ]
        distances_poc = [
            r["distance_from_poc_pct"]
            for r in vp_rejections
            if r.get("distance_from_poc_pct") is not None
        ]

        if distances_val:
            val_series = pd.Series(distances_val)
            val_mean = val_series.mean()
            val_median = val_series.median()
            val_min = val_series.min()
            val_max = val_series.max()
            print("\n📈 СРЕДНИЕ РАССТОЯНИЯ ОТ VAL:")
            print(f"   Среднее: {val_mean:.2f}%")
            print(f"   Медиана: {val_median:.2f}%")
            print(f"   Мин: {val_min:.2f}%")
            print(f"   Макс: {val_max:.2f}%")

        if distances_vah:
            vah_series = pd.Series(distances_vah)
            vah_mean = vah_series.mean()
            vah_median = vah_series.median()
            vah_min = vah_series.min()
            vah_max = vah_series.max()
            print("\n📈 СРЕДНИЕ РАССТОЯНИЯ ОТ VAH:")
            print(f"   Среднее: {vah_mean:.2f}%")
            print(f"   Медиана: {vah_median:.2f}%")
            print(f"   Мин: {vah_min:.2f}%")
            print(f"   Макс: {vah_max:.2f}%")

        if distances_poc:
            poc_series = pd.Series(distances_poc)
            poc_mean = poc_series.mean()
            poc_median = poc_series.median()
            poc_min = poc_series.min()
            poc_max = poc_series.max()
            print("\n📈 СРЕДНИЕ РАССТОЯНИЯ ОТ POC:")
            print(f"   Среднее: {poc_mean:.2f}%")
            print(f"   Медиана: {poc_median:.2f}%")
            print(f"   Мин: {poc_min:.2f}%")
            print(f"   Макс: {poc_max:.2f}%")
    return {
        "symbol": symbol,
        "total_signals": signals_passed_base,
        "signals_passed_vp": signals_passed_vp,
        "rejection_rate": rejection_rate,
        "rejections": vp_rejections[:20],  # Первые 20 для анализа
    }


if __name__ == "__main__":
    print("=" * 80)
    print("🔍 АНАЛИЗ ОТКЛОНЕНИЙ VOLUME PROFILE ФИЛЬТРА")
    print("=" * 80)

    results = []
    for test_symbol in TEST_SYMBOLS:
        result = analyze_volume_profile_rejections(test_symbol, limit_days=30)
        if result:
            results.append(result)

    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)

    total_signals_all = sum(r["total_signals"] for r in results)
    total_passed_all = sum(r["signals_passed_vp"] for r in results)
    AVG_REJECTION_RATE = sum(r["rejection_rate"] for r in results) / len(results) if results else 0

    print(f"\nВсего сигналов (базовые условия): {total_signals_all}")
    print(f"Прошло через VP фильтр: {total_passed_all}")
    print(f"Отклонено: {total_signals_all - total_passed_all}")
    print(f"Средний процент отклонений: {AVG_REJECTION_RATE:.1f}%")

    print("\n💡 ВЫВОДЫ:")
    if AVG_REJECTION_RATE > 90:
        print("   ❌ Фильтр слишком строгий - блокирует >90% сигналов")
        print("   💡 Рекомендация: увеличить tolerance_pct или уменьшить требования к Value Area")
    elif AVG_REJECTION_RATE > 50:
        print("   ⚠️ Фильтр строгий - блокирует >50% сигналов")
        print("   💡 Рекомендация: ослабить параметры фильтра")
    else:
        print("   ✅ Фильтр работает нормально")
