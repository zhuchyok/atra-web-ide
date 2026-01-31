#!/usr/bin/env python3
"""
Скрипт для проверки интеграции всех фильтров

Проверяет:
- Что все фильтры правильно интегрированы в код
- Что все импорты работают
- Что все флаги конфигурации используются
"""

import sys
import os
import re

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_file_for_patterns(filepath, patterns, description):
    """Проверяет наличие паттернов в файле"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        results = {}
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, content, re.MULTILINE)
            results[pattern_name] = len(matches) > 0
        
        return results
    except Exception as e:
        print(f"❌ Ошибка чтения {filepath}: {e}")
        return {}

print("=" * 80)
print("🔍 ПРОВЕРКА ИНТЕГРАЦИИ ВСЕХ ФИЛЬТРОВ")
print("=" * 80)
print()

# Проверка 1: Интеграция AMT фильтра в core.py
print("1️⃣ Проверка интеграции AMT фильтра в src/signals/core.py:")
core_patterns = {
    "Импорт AMT": r"from src\.filters\.amt_filter import check_amt_filter",
    "Проверка доступности": r"AMT_FILTER_AVAILABLE",
    "Проверка флага": r"USE_AMT_FILTER",
    "Вызов фильтра LONG strict": r"check_amt_filter\(df, i, \"long\", strict_mode=True\)",
    "Вызов фильтра SHORT strict": r"check_amt_filter\(df, i, \"short\", strict_mode=True\)",
    "Вызов фильтра LONG soft": r"check_amt_filter\(df, i, \"long\", strict_mode=False\)",
    "Вызов фильтра SHORT soft": r"check_amt_filter\(df, i, \"short\", strict_mode=False\)",
}
core_results = check_file_for_patterns("src/signals/core.py", core_patterns, "AMT фильтр")
for pattern, found in core_results.items():
    status = "✅" if found else "❌"
    print(f"   {status} {pattern}")

print()

# Проверка 2: Интеграция Market Profile фильтра в core.py
print("2️⃣ Проверка интеграции Market Profile фильтра в src/signals/core.py:")
mp_patterns = {
    "Импорт Market Profile": r"from src\.filters\.market_profile_filter import check_market_profile_filter",
    "Проверка доступности": r"MARKET_PROFILE_FILTER_AVAILABLE",
    "Проверка флага": r"USE_MARKET_PROFILE_FILTER",
    "Вызов фильтра LONG strict": r"check_market_profile_filter\(df, i, \"long\", strict_mode=True\)",
    "Вызов фильтра SHORT strict": r"check_market_profile_filter\(df, i, \"short\", strict_mode=True\)",
    "Вызов фильтра LONG soft": r"check_market_profile_filter\(df, i, \"long\", strict_mode=False\)",
    "Вызов фильтра SHORT soft": r"check_market_profile_filter\(df, i, \"short\", strict_mode=False\)",
}
mp_results = check_file_for_patterns("src/signals/core.py", mp_patterns, "Market Profile фильтр")
for pattern, found in mp_results.items():
    status = "✅" if found else "❌"
    print(f"   {status} {pattern}")

print()

# Проверка 3: Интеграция Institutional Patterns фильтра в signal_live.py
print("3️⃣ Проверка интеграции Institutional Patterns фильтра в signal_live.py:")
ip_patterns = {
    "Импорт Institutional Patterns": r"from src\.filters\.institutional_patterns_filter import check_institutional_patterns_filter",
    "Проверка доступности": r"INSTITUTIONAL_PATTERNS_FILTER_AVAILABLE",
    "Проверка флага": r"USE_INSTITUTIONAL_PATTERNS_FILTER",
    "Вызов фильтра": r"check_institutional_patterns_filter\(",
    "В функции check_new_filters": r"check_new_filters",
}
ip_results = check_file_for_patterns("signal_live.py", ip_patterns, "Institutional Patterns фильтр")
for pattern, found in ip_results.items():
    status = "✅" if found else "❌"
    print(f"   {status} {pattern}")

print()

# Проверка 4: Конфигурация в config.py
print("4️⃣ Проверка конфигурации в config.py:")
config_patterns = {
    "USE_AMT_FILTER": r"USE_AMT_FILTER\s*=",
    "USE_MARKET_PROFILE_FILTER": r"USE_MARKET_PROFILE_FILTER\s*=",
    "USE_INSTITUTIONAL_PATTERNS_FILTER": r"USE_INSTITUTIONAL_PATTERNS_FILTER\s*=",
    "AMT_FILTER_CONFIG": r"AMT_FILTER_CONFIG\s*=",
    "MARKET_PROFILE_FILTER_CONFIG": r"MARKET_PROFILE_FILTER_CONFIG\s*=",
    "INSTITUTIONAL_PATTERNS_FILTER_CONFIG": r"INSTITUTIONAL_PATTERNS_FILTER_CONFIG\s*=",
}
config_results = check_file_for_patterns("config.py", config_patterns, "Конфигурация")
for pattern, found in config_results.items():
    status = "✅" if found else "❌"
    print(f"   {status} {pattern}")

print()

# Проверка 5: Prometheus метрики
print("5️⃣ Проверка Prometheus метрик:")
prometheus_patterns = {
    "record_amt_phase": r"def record_amt_phase",
    "record_tpo_poc": r"def record_tpo_poc",
    "record_institutional_pattern": r"def record_institutional_pattern",
    "record_filter_check": r"def record_filter_check",
    "record_indicator_processing_time": r"def record_indicator_processing_time",
}
prometheus_results = check_file_for_patterns("src/monitoring/prometheus.py", prometheus_patterns, "Prometheus метрики")
for pattern, found in prometheus_results.items():
    status = "✅" if found else "❌"
    print(f"   {status} {pattern}")

print()

# Проверка 6: Использование метрик в фильтрах
print("6️⃣ Проверка использования Prometheus метрик в фильтрах:")
amt_metrics = {
    "Импорт метрик": r"from src\.monitoring\.prometheus import",
    "record_amt_phase": r"record_amt_phase\(",
    "record_filter_check": r"record_filter_check\(",
    "record_indicator_processing_time": r"record_indicator_processing_time\(",
}
amt_metrics_results = check_file_for_patterns("src/filters/amt_filter.py", amt_metrics, "AMT метрики")
for pattern, found in amt_metrics_results.items():
    status = "✅" if found else "❌"
    print(f"   {status} {pattern} (AMT)")

mp_metrics = {
    "Импорт метрик": r"from src\.monitoring\.prometheus import",
    "record_tpo_poc": r"record_tpo_poc\(",
    "record_filter_check": r"record_filter_check\(",
    "record_indicator_processing_time": r"record_indicator_processing_time\(",
}
mp_metrics_results = check_file_for_patterns("src/filters/market_profile_filter.py", mp_metrics, "Market Profile метрики")
for pattern, found in mp_metrics_results.items():
    status = "✅" if found else "❌"
    print(f"   {status} {pattern} (Market Profile)")

ip_metrics = {
    "Импорт метрик": r"from src\.monitoring\.prometheus import",
    "record_institutional_pattern": r"record_institutional_pattern\(",
    "record_filter_check": r"record_filter_check\(",
    "record_indicator_processing_time": r"record_indicator_processing_time\(",
}
ip_metrics_results = check_file_for_patterns("src/filters/institutional_patterns_filter.py", ip_metrics, "Institutional Patterns метрики")
for pattern, found in ip_metrics_results.items():
    status = "✅" if found else "❌"
    print(f"   {status} {pattern} (Institutional Patterns)")

print()

# Итоговая сводка
print("=" * 80)
print("📊 ИТОГОВАЯ СВОДКА")
print("=" * 80)

all_checks = {
    "AMT интеграция": all(core_results.values()),
    "Market Profile интеграция": all(mp_results.values()),
    "Institutional Patterns интеграция": all(ip_results.values()),
    "Конфигурация": all(config_results.values()),
    "Prometheus метрики": all(prometheus_results.values()),
    "AMT метрики": all(amt_metrics_results.values()),
    "Market Profile метрики": all(mp_metrics_results.values()),
    "Institutional Patterns метрики": all(ip_metrics_results.values()),
}

passed = sum(1 for v in all_checks.values() if v)
total = len(all_checks)

for check_name, passed_check in all_checks.items():
    status = "✅" if passed_check else "❌"
    print(f"{status} {check_name}")

print()
print("=" * 80)
print(f"📊 ИТОГО: {passed}/{total} проверок пройдено")
print("=" * 80)

if passed == total:
    print()
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Все фильтры правильно интегрированы.")
else:
    print()
    print("⚠️  Обнаружены проблемы. Проверьте детали выше.")

