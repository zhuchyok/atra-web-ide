#!/usr/bin/env python3
"""
Скрипт оптимизации производительности торгового бота ATRA
"""

import time
import logging
import argparse
from pathlib import Path
from src.optimization.performance_optimizer import PerformanceOptimizer, PerformanceConfig
from src.optimization.cache_manager import CacheManager
from src.optimization.performance_monitor import PerformanceMonitor, start_performance_monitoring
from src.metrics.dashboard import generate_dashboard

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def optimize_system():
    """Оптимизация системы"""
    logger.info("🚀 Запуск оптимизации производительности")
    
    try:
        # 1. Настройка конфигурации
        config = PerformanceConfig(
            max_workers=4,
            max_processes=2,
            chunk_size=1000,
            cache_size=128,
            memory_limit_mb=1024,
            enable_async=True,
            enable_caching=True,
            enable_parallel=True
        )
        
        # 2. Инициализация оптимизатора
        optimizer = PerformanceOptimizer(config)
        logger.info("✅ Оптимизатор производительности инициализирован")
        
        # 3. Настройка кэширования
        cache_manager = CacheManager(
            cache_dir="cache",
            max_size=1000,
            ttl=3600
        )
        logger.info("✅ Менеджер кэширования настроен")
        
        # 4. Запуск мониторинга
        start_performance_monitoring()
        logger.info("✅ Мониторинг производительности запущен")
        
        # 5. Оптимизация памяти
        optimizer.optimize_memory_usage()
        logger.info("✅ Память оптимизирована")
        
        # 6. Получение метрик
        metrics = optimizer.get_performance_metrics()
        logger.info(f"📊 Метрики производительности: {metrics}")
        
        # 7. Генерация отчета
        dashboard_files = generate_dashboard()
        if dashboard_files:
            logger.info(f"📈 Дашборд сгенерирован: {dashboard_files}")
        
        logger.info("🎉 Оптимизация завершена успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка оптимизации: {e}")
        return False


def benchmark_system():
    """Бенчмарк системы"""
    logger.info("🏁 Запуск бенчмарка системы")
    
    try:
        from src.optimization.performance_optimizer import performance_optimizer
        
        # Тестовые данные
        import pandas as pd
        import numpy as np
        
        # Создание тестового DataFrame
        test_data = pd.DataFrame({
            'close': np.random.uniform(40000, 60000, 10000),
            'volume': np.random.uniform(1000, 10000, 10000),
            'timestamp': pd.date_range('2024-01-01', periods=10000, freq='1min')
        })
        
        # Тестовая функция обработки
        def test_processing_func(df):
            return df['close'].rolling(20).mean()
        
        # Бенчмарк обработки DataFrame
        start_time = time.time()
        
        result = performance_optimizer.optimize_dataframe_processing(
            test_data, 
            test_processing_func,
            chunk_size=1000
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"⏱️ Время обработки: {processing_time:.2f}s")
        logger.info(f"📊 Размер результата: {len(result)} строк")
        logger.info(f"🚀 Скорость: {len(test_data) / processing_time:.0f} строк/сек")
        
        # Бенчмарк генерации сигналов
        def test_signal_func(df, i):
            return df.iloc[i]['close'] > df.iloc[i]['close'] * 1.01
        
        start_time = time.time()
        
        signal_results = performance_optimizer.optimize_signal_generation(
            test_data,
            test_signal_func,
            batch_size=100
        )
        
        end_time = time.time()
        signal_time = end_time - start_time
        
        successful_signals = sum(1 for success, _ in signal_results if success)
        total_signals = len(signal_results)
        
        logger.info(f"⏱️ Время генерации сигналов: {signal_time:.2f}s")
        logger.info(f"📊 Успешных сигналов: {successful_signals}/{total_signals}")
        logger.info(f"🚀 Скорость сигналов: {total_signals / signal_time:.0f} сигналов/сек")
        
        logger.info("🎉 Бенчмарк завершен успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка бенчмарка: {e}")
        return False


def cleanup_system():
    """Очистка системы"""
    logger.info("🧹 Запуск очистки системы")
    
    try:
        # Очистка кэша
        cache_dir = Path("cache")
        if cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir)
            logger.info("✅ Кэш очищен")
        
        # Очистка логов
        log_dir = Path("logs")
        if log_dir.exists():
            for log_file in log_dir.glob("*.log"):
                if log_file.stat().st_size > 100 * 1024 * 1024:  # 100MB
                    log_file.unlink()
                    logger.info(f"✅ Удален большой лог файл: {log_file}")
        
        # Очистка временных файлов
        temp_dir = Path("temp")
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)
            logger.info("✅ Временные файлы очищены")
        
        logger.info("🎉 Очистка завершена успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки: {e}")
        return False


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Оптимизация производительности ATRA")
    parser.add_argument("--optimize", action="store_true", help="Запустить оптимизацию")
    parser.add_argument("--benchmark", action="store_true", help="Запустить бенчмарк")
    parser.add_argument("--cleanup", action="store_true", help="Запустить очистку")
    parser.add_argument("--all", action="store_true", help="Запустить все операции")
    
    args = parser.parse_args()
    
    if not any([args.optimize, args.benchmark, args.cleanup, args.all]):
        parser.print_help()
        return
    
    success_count = 0
    total_operations = 0
    
    if args.all or args.cleanup:
        total_operations += 1
        if cleanup_system():
            success_count += 1
    
    if args.all or args.optimize:
        total_operations += 1
        if optimize_system():
            success_count += 1
    
    if args.all or args.benchmark:
        total_operations += 1
        if benchmark_system():
            success_count += 1
    
    # Итоговый отчет
    logger.info("=" * 60)
    logger.info(f"📊 ИТОГОВЫЙ ОТЧЕТ: {success_count}/{total_operations} операций выполнено успешно")
    
    if success_count == total_operations:
        logger.info("🎉 Все операции выполнены успешно!")
        return 0
    else:
        logger.warning(f"⚠️ {total_operations - success_count} операций завершились с ошибками")
        return 1


if __name__ == "__main__":
    exit(main())
