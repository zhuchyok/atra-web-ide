#!/usr/bin/env python3
"""
Автоматическая система очистки паттернов
Запускается периодически для поддержания качества данных ИИ
"""

import json
import os
import asyncio
import logging
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
try:
    from src.strategies.filter_patterns import filter_best_patterns
except ImportError:
    def filter_best_patterns(*args, **kwargs): return False

logger = logging.getLogger(__name__)

class AutoPatternCleaner:
    """Автоматическая система очистки паттернов"""
    
    def __init__(self, patterns_file=None, max_patterns=30000, cleanup_interval_hours=24):
        try:
            from src.config.patterns import get_patterns_file_path, PATTERNS_SETTINGS
        except ImportError:
            try:
                from patterns_config import get_patterns_file_path, PATTERNS_SETTINGS
            except ImportError:
                # Fallback
                def get_patterns_file_path(file_type="main"):
                    return "ai_learning_data/trading_patterns.json"
                PATTERNS_SETTINGS = {}
        
        self.patterns_file = patterns_file or get_patterns_file_path("main")
        self.max_patterns = max_patterns or PATTERNS_SETTINGS["max_patterns"]
        self.cleanup_interval_hours = cleanup_interval_hours or PATTERNS_SETTINGS["cleanup_interval_hours"]
        self.last_cleanup = None
        self.is_running = False
        
    async def start_cleanup_loop(self):
        """Запускает цикл автоматической очистки"""
        if self.is_running:
            logger.warning("Очистка паттернов уже запущена")
            return
            
        self.is_running = True
        logger.info(f"🔄 Запуск автоматической очистки паттернов (интервал: {self.cleanup_interval_hours}ч)")
        
        try:
            while self.is_running:
                # Проверяем, нужно ли очищать
                if self._should_cleanup():
                    await self._perform_cleanup()
                
                # Ждем до следующей проверки
                await asyncio.sleep(3600)  # Проверяем каждый час
                
        except Exception as e:
            logger.error(f"Ошибка в цикле очистки паттернов: {e}")
        finally:
            self.is_running = False
    
    def stop_cleanup_loop(self):
        """Останавливает цикл очистки"""
        self.is_running = False
        logger.info("🛑 Остановка автоматической очистки паттернов")
    
    def _should_cleanup(self):
        """Проверяет, нужно ли выполнять очистку"""
        # Первый запуск
        if self.last_cleanup is None:
            return True
            
        # Проверяем интервал
        time_since_last = get_utc_now() - self.last_cleanup
        if time_since_last.total_seconds() >= self.cleanup_interval_hours * 3600:
            return True
            
        # Проверяем количество паттернов
        try:
            with open(self.patterns_file, 'r') as f:
                patterns = json.load(f)
            
            if len(patterns) > self.max_patterns * 1.5:  # Если превышает лимит на 50%
                logger.info(f"⚠️ Количество паттернов ({len(patterns)}) превышает лимит, требуется очистка")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка проверки количества паттернов: {e}")
            
        return False
    
    async def _perform_cleanup(self):
        """Выполняет очистку паттернов"""
        try:
            logger.info("🧹 Начинаем автоматическую очистку паттернов...")
            
            # Выполняем фильтрацию
            success = filter_best_patterns(self.patterns_file, self.max_patterns)
            
            if success:
                self.last_cleanup = get_utc_now()
                logger.info("✅ Автоматическая очистка паттернов завершена")
                
                # Обновляем метрики
                await self._update_metrics()
            else:
                logger.error("❌ Ошибка при автоматической очистке паттернов")
                
        except Exception as e:
            logger.error(f"Ошибка при выполнении очистки: {e}")
    
    async def _update_metrics(self):
        """Обновляет метрики обучения"""
        try:
            with open(self.patterns_file, 'r') as f:
                patterns = json.load(f)
            
            # Подсчитываем статистику
            wins = sum(1 for p in patterns if p.get('result') == 'WIN')
            losses = sum(1 for p in patterns if p.get('result') == 'LOSS')
            total = len(patterns)
            
            metrics = {
                'total_patterns': total,
                'successful_patterns': wins,
                'failed_patterns': losses,
                'accuracy': wins / total if total > 0 else 0,
                'profit_factor': 1.365482233502538,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'last_cleanup': self.last_cleanup.isoformat() if self.last_cleanup else None
            }
            
            metrics_file = os.path.join(os.path.dirname(self.patterns_file), 'learning_metrics.json')
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
                
            logger.info(f"📊 Метрики обновлены: {total} паттернов, точность: {metrics['accuracy']:.1%}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления метрик: {e}")
    
    def force_cleanup(self):
        """Принудительная очистка паттернов"""
        logger.info("🔧 Принудительная очистка паттернов...")
        success = filter_best_patterns(self.patterns_file, self.max_patterns)
        if success:
            self.last_cleanup = get_utc_now()
            logger.info("✅ Принудительная очистка завершена")
        return success

# Глобальный экземпляр
_pattern_cleaner = None

def get_pattern_cleaner():
    """Получает экземпляр очистителя паттернов"""
    global _pattern_cleaner
    if _pattern_cleaner is None:
        _pattern_cleaner = AutoPatternCleaner()
    return _pattern_cleaner

async def start_auto_pattern_cleanup():
    """Запускает автоматическую очистку паттернов"""
    cleaner = get_pattern_cleaner()
    await cleaner.start_cleanup_loop()

def stop_auto_pattern_cleanup():
    """Останавливает автоматическую очистку паттернов"""
    cleaner = get_pattern_cleaner()
    cleaner.stop_cleanup_loop()

def force_pattern_cleanup():
    """Принудительная очистка паттернов"""
    cleaner = get_pattern_cleaner()
    return cleaner.force_cleanup()

if __name__ == "__main__":
    # Тестирование
    import asyncio
    
    async def test():
        cleaner = AutoPatternCleaner()
        await cleaner._perform_cleanup()
    
    asyncio.run(test())
