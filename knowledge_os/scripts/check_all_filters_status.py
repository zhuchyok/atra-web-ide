#!/usr/bin/env python3
"""
Скрипт для проверки статуса всех фильтров

Проверяет:
- Какие фильтры включены/выключены
- Доступность модулей фильтров
- Интеграцию в систему сигналов
"""

import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import config

    print("=" * 80)
    print("📊 СТАТУС ВСЕХ ФИЛЬТРОВ ATRA")
    print("=" * 80)
    print()

    # Список всех фильтров
    filters = [
        ("USE_BTC_TREND_FILTER", "BTC Trend Filter"),
        ("USE_ETH_TREND_FILTER", "ETH Trend Filter"),
        ("USE_SOL_TREND_FILTER", "SOL Trend Filter"),
        ("USE_DOMINANCE_TREND_FILTER", "Dominance Trend Filter"),
        ("USE_INTEREST_ZONE_FILTER", "Interest Zone Filter"),
        ("USE_FIBONACCI_ZONE_FILTER", "Fibonacci Zone Filter"),
        ("USE_VOLUME_IMBALANCE_FILTER", "Volume Imbalance Filter"),
        ("USE_VP_FILTER", "Volume Profile Filter"),
        ("USE_VWAP_FILTER", "VWAP Filter"),
        ("USE_ORDER_FLOW_FILTER", "Order Flow Filter"),
        ("USE_EXHAUSTION_FILTER", "Exhaustion Filter"),
        ("USE_MICROSTRUCTURE_FILTER", "Microstructure Filter"),
        ("USE_MOMENTUM_FILTER", "Momentum Filter"),
        ("USE_TREND_STRENGTH_FILTER", "Trend Strength Filter"),
        ("USE_AMT_FILTER", "AMT Filter (Auction Market Theory)"),
        ("USE_MARKET_PROFILE_FILTER", "Market Profile Filter (TPO)"),
        ("USE_INSTITUTIONAL_PATTERNS_FILTER", "Institutional Patterns Filter"),
    ]

    enabled_count = 0
    disabled_count = 0

    print("📋 СТАТУС ФИЛЬТРОВ:")
    print()

    for filter_var, filter_name in filters:
        status = getattr(config, filter_var, False)
        status_icon = "✅" if status else "❌"
        status_text = "ВКЛЮЧЕН" if status else "ВЫКЛЮЧЕН"

        print(f"{status_icon} {filter_name:50s} {status_text}")

        if status:
            enabled_count += 1
        else:
            disabled_count += 1

    print()
    print("=" * 80)
    print(f"📊 ИТОГО: {enabled_count} включено, {disabled_count} выключено")
    print("=" * 80)
    print()

    # Проверка доступности модулей
    print("🔍 ПРОВЕРКА ДОСТУПНОСТИ МОДУЛЕЙ:")
    print()

    modules_to_check = [
        ("src.filters.amt_filter", "AMT Filter"),
        ("src.filters.market_profile_filter", "Market Profile Filter"),
        ("src.filters.institutional_patterns_filter", "Institutional Patterns Filter"),
        ("src.analysis.auction_market_theory", "Auction Market Theory"),
        ("src.analysis.market_profile", "Market Profile (TPO)"),
        ("src.analysis.institutional_patterns", "Institutional Patterns"),
    ]

    available_count = 0
    unavailable_count = 0

    for module_name, module_display in modules_to_check:
        try:
            __import__(module_name)
            print(f"✅ {module_display:50s} Доступен")
            available_count += 1
        except ImportError as e:
            print(f"❌ {module_display:50s} Недоступен: {e}")
            unavailable_count += 1

    print()
    print("=" * 80)
    print(f"📊 ИТОГО: {available_count} доступно, {unavailable_count} недоступно")
    print("=" * 80)

    # Рекомендации
    print()
    print("💡 РЕКОМЕНДАЦИИ:")
    print()

    if disabled_count > 0:
        print(f"⚠️  Обнаружено {disabled_count} выключенных фильтров")
        print("   Рекомендуется включить все фильтры для максимальной эффективности")
        print()

    if unavailable_count > 0:
        print(f"⚠️  Обнаружено {unavailable_count} недоступных модулей")
        print("   Проверьте установку зависимостей и структуру проекта")
        print()

    if disabled_count == 0 and unavailable_count == 0:
        print("✅ Все фильтры включены и доступны!")
        print()

except Exception as e:
    print(f"❌ Ошибка при проверке фильтров: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
