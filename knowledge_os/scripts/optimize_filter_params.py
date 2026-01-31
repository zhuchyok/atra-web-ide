#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 СКРИПТ ОПТИМИЗАЦИИ ПАРАМЕТРОВ ОДНОГО ФИЛЬТРА
Добавляет фильтр, тестирует разные параметры, находит оптимальные
"""

import os
import sys
import json
import traceback
import glob
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from src.shared.utils.datetime_utils import get_utc_now

try:
    from tqdm import tqdm
except ImportError:
    # Fallback если tqdm не установлен
    def tqdm(iterable=None, **kwargs):
        """Fallback функция для tqdm если модуль не установлен"""
        if iterable is None:
            class FakeTqdm:
                """Fake tqdm класс для замены если tqdm не установлен"""
                def __init__(self, *args, **kwargs):
                    """Инициализация FakeTqdm"""
                    self.total = kwargs.get('total', 0)
                    self.n = 0
                def update(self, n=1):
                    """Обновление прогресса"""
                    self.n += n
                def set_postfix(self, **kwargs):
                    """Установка постфикса"""
                    return None
                def __enter__(self):
                    """Вход в контекстный менеджер"""
                    return self
                def __exit__(self, *args):
                    """Выход из контекстного менеджера"""
                    return None
            return FakeTqdm(**kwargs)
        return iterable

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# 🔧 ВКЛЮЧАЕМ RUST УСКОРЕНИЕ
os.environ['USE_RUST'] = 'true'
try:
    from src.infrastructure.performance.rust_accelerator import is_rust_available, get_rust_accelerator
    if is_rust_available():
        print("✅ Rust acceleration доступен")
        RUST_ACCELERATOR = get_rust_accelerator()
    else:
        print("⚠️ Rust acceleration недоступен, используем Python")
        RUST_ACCELERATOR = None
except ImportError:
    print("⚠️ Rust модуль не найден, используем Python")
    RUST_ACCELERATOR = None

# pylint: disable=wrong-import-position
from scripts.backtest_5coins_intelligent import (
    load_yearly_data, run_backtest,
    get_intelligent_filter_system
)
# pylint: enable=wrong-import-position

# 🔧 10 МОНЕТ ДЛЯ ОПТИМИЗАЦИИ (ТОП-10)
TEST_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",  # Топ 5
    "XRPUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT"  # Топ 6-10
]

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

PERIOD_DAYS = 30  # 🔧 ОПТИМИЗАЦИЯ: Месячные данные для статистики
FILTER_NAME = os.environ.get('FILTER_TO_OPTIMIZE', 'volume_profile')  # Фильтр для оптимизации
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', '20'))  # 🔧 Многопоточность: 20 потоков
# 🔧 По умолчанию используем сохраненный baseline
SKIP_BASELINE = os.environ.get('SKIP_BASELINE', 'true').lower() == 'true'

# Параметры для оптимизации (зависит от фильтра)
OPTIMIZATION_PARAMS = {
    'volume_profile': {
        'param_name': 'volume_profile_threshold',
        'values': [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]  # Пороги для тестирования
    },
    'vwap': {
        'param_name': 'vwap_threshold',
        'values': [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
    },
    # Добавить другие фильтры по мере необходимости
}

# ============================================================================
# ФУНКЦИИ
# ============================================================================

def load_saved_baseline() -> Optional[dict]:
    """Загружает сохраненный baseline из файла baseline_results.json или последнего файла оптимизации"""
    try:
        # Сначала пытаемся загрузить из baseline_results.json
        baseline_file = Path("backtests/baseline_results.json")
        if baseline_file.exists():
            with open(baseline_file, 'r', encoding='utf-8') as f:
                baseline = json.load(f)
                print(f"   📄 Загружен из: {baseline_file}")
                return baseline

        # Если нет, ищем в последнем файле оптимизации
        pattern = f"backtests/optimize_{FILTER_NAME}_*.json"
        files = sorted(glob.glob(pattern), reverse=True)

        if files:
            with open(files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
                baseline = data.get('baseline')
                if baseline:
                    print(f"   📄 Загружен из: {files[0]}")
                    return baseline
    except Exception as e:
        print(f"   ⚠️ Ошибка загрузки baseline: {e}")
    return None

def set_filter_enabled(filter_name: str, enabled: bool = True):
    """Включает/отключает фильтр"""
    filter_flag_map = {
        'volume_profile': 'USE_VP_FILTER',
        'vwap': 'USE_VWAP_FILTER',
        'order_flow': 'USE_ORDER_FLOW_FILTER',
        'microstructure': 'USE_MICROSTRUCTURE_FILTER',
        'momentum': 'USE_MOMENTUM_FILTER',
        'trend_strength': 'USE_TREND_STRENGTH_FILTER',
        'amt': 'USE_AMT_FILTER',
        'market_profile': 'USE_MARKET_PROFILE_FILTER',
    }

    # Сбрасываем все флаги
    for flag in filter_flag_map.values():
        os.environ[flag] = 'False'

    # Устанавливаем нужный флаг
    if enabled and filter_name in filter_flag_map:
        os.environ[filter_flag_map[filter_name]] = 'True'

    # 🔧 КРИТИЧНО: Volume Profile и VWAP проверяются отдельно от DISABLE_EXTRA_FILTERS
    # Они проверяются через USE_VP_FILTER и USE_VWAP_FILTER напрямую
    # DISABLE_EXTRA_FILTERS влияет только на Order Flow, Microstructure, Momentum, Trend Strength, AMT
    # Поэтому для Volume Profile и VWAP мы НЕ меняем DISABLE_EXTRA_FILTERS
    if enabled and filter_name in ['volume_profile', 'vwap']:
        # Volume Profile и VWAP работают независимо от DISABLE_EXTRA_FILTERS
        # Оставляем DISABLE_EXTRA_FILTERS = 'true', чтобы отключить остальные фильтры
        os.environ['DISABLE_EXTRA_FILTERS'] = 'true'
    elif enabled:
        # Для остальных фильтров (Order Flow, Microstructure и т.д.) нужно разрешить дополнительные фильтры
        # но они уже включены через USE_*_FILTER флаги выше
        os.environ['DISABLE_EXTRA_FILTERS'] = 'false'
    else:
        # Отключаем все
        os.environ['DISABLE_EXTRA_FILTERS'] = 'true'

    # Перезагружаем модули
    if 'src.signals.core' in sys.modules:
        del sys.modules['src.signals.core']
    if 'src.signals' in sys.modules:
        del sys.modules['src.signals']
    if 'config' in sys.modules:
        del sys.modules['config']

def test_symbol_backtest(args) -> dict:
    """Тестирует один символ (для многопоточности)"""
    symbol, filter_name, param_value = args

    try:
        print(f"    🔵 Начало теста {symbol}...", flush=True)

        # Для baseline не включаем фильтры, для остальных - включаем
        if filter_name != 'baseline':
            set_filter_enabled(filter_name, enabled=True)

        # Устанавливаем параметр через переменную окружения (если нужно)
        if param_value is not None and filter_name in OPTIMIZATION_PARAMS:
            param_name = OPTIMIZATION_PARAMS[filter_name]['param_name']
            os.environ[param_name] = str(param_value)

        # Инициализируем интеллектуальную систему
        intelligent_system = get_intelligent_filter_system()

        print(f"    📥 Загрузка данных {symbol}...", flush=True)
        df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
        if df is None or len(df) < 50:
            print(f"    ❌ Недостаточно данных для {symbol}", flush=True)
            return None

        print(f"    🚀 Запуск бэктеста {symbol}...", flush=True)
        stats = run_backtest(df, symbol=symbol, mode="soft", intelligent_system=intelligent_system)
        metrics = stats.get_metrics()
        metrics['symbol'] = symbol

        print(f"    ✅ Завершен {symbol}: {metrics.get('total_return', 0):+.2f}%", flush=True)
        return metrics
    except Exception as e:
        print(f"    ❌ Ошибка для {symbol}: {e}", flush=True)
        traceback.print_exc()
        return None

def test_filter_with_params(filter_name: str, param_value: float = None) -> dict:
    """Тестирует фильтр с заданными параметрами (с многопоточностью)"""
    param_str = f"параметр={param_value}" if param_value is not None else "baseline"
    print(f"\n🔍 Тестирование {filter_name} с {param_str}")

    # Для baseline не включаем фильтры, для остальных - включаем
    if filter_name != 'baseline':
        set_filter_enabled(filter_name, enabled=True)

    # Устанавливаем параметр через переменную окружения (если нужно)
    if param_value is not None and filter_name in OPTIMIZATION_PARAMS:
        param_name = OPTIMIZATION_PARAMS[filter_name]['param_name']
        os.environ[param_name] = str(param_value)

    results = []

    # 🔧 МНОГОПОТОЧНОЕ ТЕСТИРОВАНИЕ СИМВОЛОВ
    print(f"  🚀 Запуск тестирования {len(TEST_SYMBOLS)} символов на {MAX_WORKERS} потоках...")

    # Подготавливаем аргументы для каждого символа
    test_args = [(symbol, filter_name, param_value) for symbol in TEST_SYMBOLS]

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(TEST_SYMBOLS))) as executor:
        # Запускаем задачи
        futures = {
            executor.submit(test_symbol_backtest, args): args[0]
            for args in test_args
        }

        # Собираем результаты с прогресс-баром и онлайн-выводом
        with tqdm(total=len(TEST_SYMBOLS), desc="  Тестирование", unit="символ", ncols=100) as pbar:
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    metrics = future.result(timeout=300)  # 5 минут таймаут

                    # 🔧 ОНЛАЙН ВЫВОД: показываем результат каждого символа
                    return_pct = metrics.get('total_return', 0)
                    trades = metrics.get('total_trades', 0)
                    print(f"    ✅ Завершен {symbol}: {return_pct:+.2f}% ({trades} сделок)")
                    sys.stdout.flush()  # Принудительно выводим в консоль
                    if metrics:
                        results.append(metrics)
                        pbar.set_postfix({symbol: f"{metrics.get('total_return', 0):+.2f}%"})
                    else:
                        pbar.set_postfix({symbol: "❌"})
                except Exception as e:
                    print(f"\n  ❌ Ошибка для {symbol}: {e}")
                    traceback.print_exc()
                finally:
                    pbar.update(1)

    # Агрегируем результаты
    total_return = sum(r.get('total_return', 0) for r in results)
    total_trades = sum(r.get('total_trades', 0) for r in results)
    total_signals = sum(r.get('signals_generated', 0) for r in results)
    total_executed = sum(r.get('signals_executed', 0) for r in results)
    avg_win_rate = sum(r.get('win_rate', 0) for r in results) / len(results) if results else 0
    avg_profit_factor = sum(r.get('profit_factor', 0) for r in results) / len(results) if results else 0
    avg_sharpe = sum(r.get('sharpe_ratio', 0) for r in results) / len(results) if results else 0

    return {
        'filter_name': filter_name,
        'param_value': param_value,
        'total_return': total_return,
        'total_trades': total_trades,
        'total_signals': total_signals,
        'total_executed': total_executed,
        'rejection_rate': (total_signals - total_executed) / total_signals * 100 if total_signals > 0 else 0,
        'avg_win_rate': avg_win_rate,
        'avg_profit_factor': avg_profit_factor,
        'avg_sharpe': avg_sharpe,
        'results': results
    }

def optimize_filter(filter_name: str):
    """Оптимизирует параметры фильтра"""
    print("="*80)
    print(f"🔧 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ ФИЛЬТРА: {filter_name.upper()}")
    print("="*80)
    print(f"📅 Период: {PERIOD_DAYS} дней (месячные данные)")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("="*80)

    # 🔧 Baseline: загружаем сохраненный или вычисляем новый
    skip_baseline = SKIP_BASELINE
    if skip_baseline:
        print("\n📊 ШАГ 1: Baseline (используем сохраненный)")
        # Пытаемся загрузить последний baseline из предыдущих результатов
        baseline_result = load_saved_baseline()
        if baseline_result:
            print("   ✅ Загружен сохраненный baseline")
            print(f"   📈 Доходность: {baseline_result['total_return']:+.2f}%")
            print(f"   📊 Сделок: {baseline_result['total_trades']}")
            print(f"   🎯 Сигналов: {baseline_result['total_signals']} "
                  f"(исп: {baseline_result['total_executed']})")
        else:
            print("   ⚠️ Сохраненный baseline не найден, вычисляем новый...")
            skip_baseline = False

    if not skip_baseline:
        print("\n📊 ШАГ 1: Baseline (без фильтра)")
        # Явно отключаем все фильтры для baseline
        for flag in ['USE_VP_FILTER', 'USE_VWAP_FILTER', 'USE_ORDER_FLOW_FILTER',
                     'USE_MICROSTRUCTURE_FILTER', 'USE_MOMENTUM_FILTER',
                     'USE_TREND_STRENGTH_FILTER', 'USE_AMT_FILTER', 'USE_MARKET_PROFILE_FILTER']:
            os.environ[flag] = 'False'
        os.environ['DISABLE_EXTRA_FILTERS'] = 'true'  # Отключаем дополнительные фильтры
        # Перезагружаем модули
        if 'src.signals.core' in sys.modules:
            del sys.modules['src.signals.core']
        if 'src.signals' in sys.modules:
            del sys.modules['src.signals']
        if 'config' in sys.modules:
            del sys.modules['config']
        baseline_result = test_filter_with_params('baseline', None)

        print("\n✅ Baseline результаты:")
        print(f"   📈 Доходность: {baseline_result['total_return']:+.2f}%")
        print(f"   📊 Сделок: {baseline_result['total_trades']}")
        print(f"   🎯 Сигналов: {baseline_result['total_signals']} "
              f"(исп: {baseline_result['total_executed']})")

        # 🔧 Сохраняем baseline для будущего использования
        baseline_file = Path("backtests/baseline_results.json")
        with open(baseline_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_result, f, indent=2)
        print(f"   💾 Сохранен в {baseline_file}")

    # Если фильтр не в списке оптимизации, просто тестируем включенным
    if filter_name not in OPTIMIZATION_PARAMS:
        print(f"\n📊 ШАГ 2: Тест с фильтром {filter_name} (стандартные параметры)")
        result = test_filter_with_params(filter_name, None)

        print("\n✅ Результаты с фильтром:")
        print(f"   📈 Доходность: {result['total_return']:+.2f}%")
        print(f"   📊 Сделок: {result['total_trades']}")
        print(f"   🎯 Сигналов: {result['total_signals']} "
              f"(исп: {result['total_executed']}, откл: {result['rejection_rate']:.1f}%)")
        print(f"   ✅ Win Rate: {result['avg_win_rate']:.1f}% | "
              f"PF: {result['avg_profit_factor']:.2f} | "
              f"Sharpe: {result['avg_sharpe']:.2f}")

        diff = result['total_return'] - baseline_result['total_return']
        baseline_pct = (diff / baseline_result['total_return'] * 100
                        if baseline_result['total_return'] != 0 else 0)
        print(f"\n   📊 vs baseline: {diff:+.2f}% ({baseline_pct:+.1f}%)")

        return {
            'baseline': baseline_result,
            'with_filter': result,
            'best_param': None,
            'optimization_results': []
        }

    # Оптимизация параметров
    print(f"\n📊 ШАГ 2: Оптимизация параметров {OPTIMIZATION_PARAMS[filter_name]['param_name']}")
    print(f"🚀 Используем {MAX_WORKERS} потоков для ускорения")
    param_values = OPTIMIZATION_PARAMS[filter_name]['values']

    optimization_results = []
    best_result: Optional[dict] = None
    best_param = None

    # 🔧 МНОГОПОТОЧНАЯ ОПТИМИЗАЦИЯ ПАРАМЕТРОВ
    print(f"\n  Тестируем {len(param_values)} значений параметров...")
    print(f"  📊 Параметры: {', '.join(map(str, param_values))}")

    completed_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Запускаем задачи для каждого параметра
        futures = {
            executor.submit(test_filter_with_params, filter_name, param_value): param_value
            for param_value in param_values
        }

        # 🔧 ОНЛАЙН МОНИТОРИНГ: выводим прогресс по мере завершения
        print("\n  ⏳ Ожидание завершения параметров...")
        print("  📈 Прогресс будет обновляться по мере завершения каждого параметра\n")

        # Собираем результаты с прогресс-баром
        with tqdm(total=len(param_values), desc="  Оптимизация", unit="параметр", ncols=100) as pbar:
            completed_count = 0
            for future in as_completed(futures):
                param_value = futures[future]
                try:
                    print(f"\n⏳ Ожидание завершения параметра {param_value}...")
                    result = future.result(timeout=600)  # 10 минут таймаут на параметр
                    completed_count += 1
                    optimization_results.append(result)

                    diff = result['total_return'] - baseline_result['total_return']
                    print(f"\n   ✅ Параметр {param_value}: {result['total_return']:+.2f}% "
                          f"(vs baseline: {diff:+.2f}%) | Сделок: {result['total_trades']} | "
                          f"Прогресс: {completed_count}/{len(param_values)}")
                    pbar.set_postfix({'param': param_value, 'return': f"{result['total_return']:+.2f}%"})

                    # Сохраняем лучший результат
                    if best_result is None:
                        best_result = result
                        best_param = param_value
                    else:
                        # Используем get() для безопасного доступа
                        current_best_return = best_result.get('total_return', float('-inf'))
                        if result.get('total_return', float('-inf')) > current_best_return:
                            best_result = result
                            best_param = param_value
                except Exception as e:
                    print(f"\n   ❌ Ошибка для параметра {param_value}: {e}")
                finally:
                    pbar.update(1)

    # Сортируем результаты по параметру для удобства
    optimization_results.sort(key=lambda x: x['param_value'] if x['param_value'] is not None else 0)

    # Выводим результаты
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ")
    print("="*80 + "\n")

    if best_result is None:
        print("❌ Не удалось получить результаты оптимизации")
        return {
            'filter_name': filter_name,
            'baseline': baseline_result,
            'best_param': None,
            'best_result': None,
            'all_results': optimization_results,
            'timestamp': get_utc_now().strftime('%Y%m%d_%H%M%S')
        }

    # После проверки best_result гарантированно не None
    # pylint: disable=unsubscriptable-object
    print(f"🏆 ЛУЧШИЙ ПАРАМЕТР: {best_param}")
    print(f"   📈 Доходность: {best_result['total_return']:+.2f}%")
    print(f"   📊 Сделок: {best_result['total_trades']}")
    print(f"   🎯 Сигналов: {best_result['total_signals']} "
          f"(исп: {best_result['total_executed']}, откл: {best_result['rejection_rate']:.1f}%)")
    print(f"   ✅ Win Rate: {best_result['avg_win_rate']:.1f}% | "
          f"PF: {best_result['avg_profit_factor']:.2f} | "
          f"Sharpe: {best_result['avg_sharpe']:.2f}")

    diff = best_result['total_return'] - baseline_result['total_return']
    baseline_pct = (diff / baseline_result['total_return'] * 100
                    if baseline_result['total_return'] != 0 else 0)
    print(f"\n   📊 vs baseline: {diff:+.2f}% ({baseline_pct:+.1f}%)")

    # Сохраняем результаты
    timestamp = get_utc_now().strftime('%Y%m%d_%H%M%S')
    output_file = f"backtests/optimize_{filter_name}_{timestamp}.json"
    os.makedirs('backtests', exist_ok=True)

    summary = {
        'filter_name': filter_name,
        'baseline': baseline_result,
        'best_param': best_param,
        'best_result': best_result,
        'all_results': optimization_results,
        'timestamp': timestamp
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Результаты сохранены в {output_file}")

    return summary

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Главная функция"""
    filter_name = FILTER_NAME

    print("="*80)
    print("🔧 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ ФИЛЬТРА")
    print("="*80)
    print(f"📅 Дата запуска: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔍 Фильтр: {filter_name}")
    print("="*80)

    result = optimize_filter(filter_name)

    print("\n" + "="*80)
    print("🎉 ОПТИМИЗАЦИЯ ЗАВЕРШЕНА!")
    print("="*80)

    if result['best_param']:
        print("\n💡 РЕКОМЕНДАЦИЯ:")
        print(f"   Использовать параметр: {result['best_param']}")
        if result['best_result']:
            print(f"   Ожидаемая доходность: {result['best_result']['total_return']:+.2f}%")
            baseline_diff = (result['best_result']['total_return'] -
                           result['baseline']['total_return'])
            print(f"   vs baseline: {baseline_diff:+.2f}%")
    else:
        print("\n💡 РЕКОМЕНДАЦИЯ:")
        if 'with_filter' in result:
            if result['with_filter']['total_return'] > result['baseline']['total_return']:
                print("   ✅ Фильтр улучшает результаты!")
            else:
                print("   ⚠️  Фильтр ухудшает результаты. "
                      "Нужно ослабить параметры или отключить.")

if __name__ == '__main__':
    main()

