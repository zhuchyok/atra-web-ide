#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обёртка для обратной совместимости с filter_optimizer
Использует реальную функциональность из ai_filter_optimizer
"""

import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Импортируем из ai_filter_optimizer с защитой
try:
    from ai_filter_optimizer import get_filter_optimizer, AIFilterOptimizer
    AI_FILTER_OPTIMIZER_AVAILABLE = True
    
    # Создаём экземпляр оптимизатора
    try:
        _optimizer_instance = get_filter_optimizer()
        logger.info("✅ ai_filter_optimizer успешно загружен")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации ai_filter_optimizer: {e}")
        _optimizer_instance = None
        AI_FILTER_OPTIMIZER_AVAILABLE = False
        
except ImportError as e:
    logger.error(f"❌ Модуль ai_filter_optimizer недоступен: {e}")
    logger.error("⚠️ Система будет работать без оптимизатора фильтров")
    AI_FILTER_OPTIMIZER_AVAILABLE = False
    _optimizer_instance = None
    AIFilterOptimizer = None


# Создаём обёртку для обратной совместимости
if AI_FILTER_OPTIMIZER_AVAILABLE and _optimizer_instance:
    class FilterOptimizerWrapper:
        """Обёртка для обратной совместимости с filter_optimizer"""
        
        def __init__(self, optimizer: AIFilterOptimizer):
            self._optimizer = optimizer
            self._performance_cache = None
            self._performance_cache_time = 0
        
        def get_optimization_status(self) -> Dict[str, Any]:
            """Возвращает статус оптимизации"""
            try:
                return {
                    'status': 'active',
                    'optimization_interval_hours': self._optimizer.optimization_interval_hours,
                    'min_trades_for_optimization': self._optimizer.min_trades_for_optimization,
                    'lookback_days': self._optimizer.lookback_days,
                    'optimizable_params_count': len(self._optimizer.optimizable_params),
                    'source': 'ai_filter_optimizer'
                }
            except Exception as e:
                logger.warning(f"Ошибка получения статуса оптимизации: {e}")
                return {'status': 'error', 'error': str(e)}
        
        async def get_optimized_filter_params(self, symbol: str) -> Optional[Dict[str, Any]]:
            """Возвращает оптимизированные параметры фильтров"""
            try:
                # Загружаем оптимизированные параметры
                params = self._optimizer.load_optimized_params()
                if params:
                    return {
                        'symbol': symbol,
                        'parameters': params,
                        'source': 'ai_filter_optimizer'
                    }
                return None
            except Exception as e:
                logger.warning(f"Ошибка получения оптимизированных параметров для {symbol}: {e}")
                return None
        
        async def optimize_strategy(self, symbol: str, signals_data: list, optimization_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Оптимизирует стратегию"""
            try:
                # Используем реальную оптимизацию из ai_filter_optimizer
                optimized_params = await self._optimizer.optimize_parameters()
                
                if optimized_params:
                    return {
                        'symbol': symbol,
                        'optimized_parameters': optimized_params,
                        'timestamp': asyncio.get_event_loop().time(),
                        'source': 'ai_filter_optimizer'
                    }
                return None
            except Exception as e:
                logger.warning(f"Ошибка оптимизации стратегии для {symbol}: {e}")
                return None
        
        def run_optimization_cycle(self, symbol: str) -> Dict[str, Any]:
            """Запускает цикл оптимизации (синхронная обёртка)"""
            try:
                # Пытаемся запустить асинхронную оптимизацию
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Если loop уже запущен, создаём задачу
                        asyncio.create_task(self._optimizer.optimize_parameters())
                        return {
                            'status': 'started',
                            'symbol': symbol,
                            'message': 'Optimization task created'
                        }
                    else:
                        # Если loop не запущен, запускаем синхронно
                        loop.run_until_complete(self._optimizer.optimize_parameters())
                        return {
                            'status': 'completed',
                            'symbol': symbol,
                            'message': 'Optimization completed'
                        }
                except RuntimeError:
                    # Нет event loop, создаём новый
                    asyncio.run(self._optimizer.optimize_parameters())
                    return {
                        'status': 'completed',
                        'symbol': symbol,
                        'message': 'Optimization completed'
                    }
            except Exception as e:
                logger.warning(f"Ошибка запуска цикла оптимизации для {symbol}: {e}")
                return {'status': 'error', 'error': str(e)}
        
        def get_filter_performance_report(self) -> Dict[str, Any]:
            """Возвращает отчёт о производительности фильтров"""
            try:
                import time
                # Кэшируем результаты на 5 минут
                current_time = time.time()
                if self._performance_cache and (current_time - self._performance_cache_time) < 300:
                    return self._performance_cache
                
                # Пытаемся получить асинхронно
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Если loop уже запущен, возвращаем кэш или статус
                        if self._performance_cache:
                            return self._performance_cache
                        return {
                            'status': 'async_running',
                            'message': 'Performance data will be available soon'
                        }
                    else:
                        # Если loop не запущен, запускаем синхронно
                        performance = loop.run_until_complete(self._optimizer.get_recent_performance())
                        self._performance_cache = performance
                        self._performance_cache_time = current_time
                        return performance
                except RuntimeError:
                    # Нет event loop, создаём новый
                    performance = asyncio.run(self._optimizer.get_recent_performance())
                    self._performance_cache = performance
                    self._performance_cache_time = current_time
                    return performance
            except Exception as e:
                logger.warning(f"Ошибка получения отчёта о производительности: {e}")
                return {'status': 'error', 'error': str(e)}
        
        async def optimize_filter_system(self, 
                                         filter_configs: Dict[str, Any],
                                         signals_data: list,
                                         optimization_config: Dict[str, Any]) -> Dict[str, Any]:
            """Полная оптимизация системы фильтров (совместимость со старым API)"""
            try:
                # Используем реальную оптимизацию
                optimized_params = await self._optimizer.optimize_parameters()
                performance = await self._optimizer.get_recent_performance()
                
                return {
                    'optimization_timestamp': asyncio.get_event_loop().time(),
                    'optimized_parameters': optimized_params,
                    'performance_metrics': performance,
                    'source': 'ai_filter_optimizer'
                }
            except Exception as e:
                logger.warning(f"Ошибка оптимизации системы фильтров: {e}")
                return {'status': 'error', 'error': str(e)}
    
    # Создаём глобальный экземпляр обёртки
    filter_optimizer = FilterOptimizerWrapper(_optimizer_instance)
    logger.info("✅ filter_optimizer обёртка создана из ai_filter_optimizer (реальная функциональность)")
    
else:
    # Создаём заглушку только если модуль недоступен
    class FilterOptimizerStub:
        """Заглушка для filter_optimizer (используется только если ai_filter_optimizer недоступен)"""
        
        def get_optimization_status(self):
            return {
                'status': 'unavailable',
                'message': 'ai_filter_optimizer module not available',
                'reason': 'Module not found or initialization failed'
            }
        
        async def get_optimized_filter_params(self, symbol):
            logger.warning(f"⚠️ Попытка получить параметры для {symbol}, но оптимизатор недоступен")
            return None
        
        async def optimize_strategy(self, symbol, signals_data, optimization_config):
            logger.warning(f"⚠️ Попытка оптимизировать стратегию для {symbol}, но оптимизатор недоступен")
            return None
        
        def run_optimization_cycle(self, symbol):
            logger.warning(f"⚠️ Попытка запустить цикл оптимизации для {symbol}, но оптимизатор недоступен")
            return {
                'status': 'unavailable',
                'message': 'ai_filter_optimizer module not available',
                'symbol': symbol
            }
        
        def get_filter_performance_report(self):
            logger.warning("⚠️ Попытка получить отчёт о производительности, но оптимизатор недоступен")
            return {
                'status': 'unavailable',
                'message': 'ai_filter_optimizer module not available'
            }
        
        async def optimize_filter_system(self, filter_configs, signals_data, optimization_config):
            logger.warning("⚠️ Попытка оптимизировать систему фильтров, но оптимизатор недоступен")
            return {
                'status': 'unavailable',
                'message': 'ai_filter_optimizer module not available'
            }
    
    filter_optimizer = FilterOptimizerStub()
    logger.warning("⚠️ filter_optimizer использует заглушку (ai_filter_optimizer недоступен)")
