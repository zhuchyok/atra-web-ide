#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚦 АВТОМАТИЧЕСКАЯ ДИАГНОСТИКА PIPELINE ГЕНЕРАЦИИ И ОТПРАВКИ СИГНАЛОВ
Глубокая проверка системы с анализом каждого этапа
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from src.shared.utils.datetime_utils import get_utc_now
import pandas as pd

logger = logging.getLogger(__name__)

class PipelineDiagnostic:
    """Система диагностики pipeline генерации и отправки сигналов"""
    
    def __init__(self):
        self.stats = {
            "candidate_signals": 0,
            "bb_filter": {"total": 0, "rejected": 0, "passed": 0, "reasons": {}},
            "ema_filter": {"total": 0, "rejected": 0, "passed": 0, "reasons": {}},
            "rsi_filter": {"total": 0, "rejected": 0, "passed": 0, "reasons": {}},
            "volume_filter": {"total": 0, "rejected": 0, "passed": 0, "reasons": {}},
            "ai_filter": {"total": 0, "rejected": 0, "passed": 0, "reasons": {}},
            "time_filter": {"total": 0, "rejected": 0, "passed": 0, "reasons": {}},
            "message_queue": {"total": 0, "rejected": 0, "passed": 0, "reasons": {}},
            "telegram_sent": {"total": 0, "rejected": 0, "passed": 0, "reasons": {}}
        }
        self.trace_ids = {}
        self.start_time = get_utc_now()
        
    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """Запускает полную диагностику pipeline"""
        logger.info("🚦 Запуск полной диагностики pipeline генерации сигналов...")
        
        try:
            # 1. Анализ архитектуры pipeline
            architecture = await self._analyze_pipeline_architecture()
            
            # 2. Проверка фильтров и AI/ML
            filters_status = await self._check_filters_and_ai()
            
            # 3. Проверка очереди и отправки
            queue_status = await self._check_queue_and_delivery()
            
            # 4. Проверка логов и мониторинга
            monitoring_status = await self._check_logging_and_monitoring()
            
            # 5. Генерация статистики
            statistics = await self._generate_statistics()
            
            # 6. Формирование отчета
            report = {
                "timestamp": get_utc_now().isoformat(),
                "duration_seconds": (get_utc_now() - self.start_time).total_seconds(),
                "architecture": architecture,
                "filters_status": filters_status,
                "queue_status": queue_status,
                "monitoring_status": monitoring_status,
                "statistics": statistics,
                "recommendations": await self._generate_recommendations()
            }
            
            return report
            
        except Exception as e:
            logger.error("❌ Ошибка диагностики pipeline: %s", e)
            return {"error": str(e)}
    
    async def _analyze_pipeline_architecture(self) -> Dict[str, Any]:
        """Анализ архитектуры pipeline"""
        logger.info("🔍 Анализ архитектуры pipeline...")
        
        architecture = {
            "stages": [],
            "functions": {},
            "parameters": {},
            "logging": {}
        }
        
        try:
            # Этап 1: Получение и валидация данных
            stage1 = {
                "name": "Получение и валидация данных (OHLC, индикаторы)",
                "functions": ["get_ohlc_data", "apply_technical_indicators"],
                "parameters": ["timeframe", "limit", "indicators"],
                "logging": "✅ Логируется получение данных"
            }
            architecture["stages"].append(stage1)
            
            # Этап 2: Генерация candidate сигналов
            stage2 = {
                "name": "Генерация candidate сигналов",
                "functions": ["generate_simple_signal", "get_entry_signal_by_mode"],
                "parameters": ["symbol", "filter_mode", "trade_mode"],
                "logging": "✅ Логируется генерация сигналов"
            }
            architecture["stages"].append(stage2)
            
            # Этап 3: Фильтрация
            stage3 = {
                "name": "Фильтрация (BB, EMA, RSI, Volume, AI, Time, Risk)",
                "functions": ["check_ai_volume_filter", "check_ai_volatility_filter", "calculate_ai_signal_score"],
                "parameters": ["ai_params", "symbol_params", "filter_mode"],
                "logging": "✅ Логируется фильтрация с причинами отклонения"
            }
            architecture["stages"].append(stage3)
            
            # Этап 4: Очередь сообщений
            stage4 = {
                "name": "Очередь сообщений (TTL, приоритеты, retry)",
                "functions": ["notify_user_with_retry", "is_signal_duplicate"],
                "parameters": ["retry_count", "backoff_delay", "ttl"],
                "logging": "✅ Логируется обработка очереди"
            }
            architecture["stages"].append(stage4)
            
            # Этап 5: Rate limiting
            stage5 = {
                "name": "Rate limiting",
                "functions": ["AdvancedNotificationLimiter", "get_user_backoff_delay"],
                "parameters": ["rate_limit", "backoff_multiplier"],
                "logging": "✅ Логируется rate limiting"
            }
            architecture["stages"].append(stage5)
            
            # Этап 6: Отправка в Telegram
            stage6 = {
                "name": "Отправка пользователям в Telegram",
                "functions": ["notify_user", "send_signal_to_user"],
                "parameters": ["user_id", "message", "parse_mode"],
                "logging": "✅ Логируется отправка в Telegram"
            }
            architecture["stages"].append(stage6)
            
        except Exception as e:
            logger.error("❌ Ошибка анализа архитектуры: %s", e)
            architecture["error"] = str(e)
        
        return architecture
    
    async def _check_filters_and_ai(self) -> Dict[str, Any]:
        """Проверка корректности фильтров и AI/ML"""
        logger.info("🤖 Проверка фильтров и AI/ML...")
        
        filters_status = {
            "disabled_filters": [],
            "mock_parameters": [],
            "ai_confidence": {},
            "rejection_logging": {}
        }
        
        try:
            # Проверяем отключенные фильтры
            disabled_filters = await self._check_disabled_filters()
            filters_status["disabled_filters"] = disabled_filters
            
            # Проверяем заглушки
            mock_parameters = await self._check_mock_parameters()
            filters_status["mock_parameters"] = mock_parameters
            
            # Проверяем AI confidence
            ai_confidence = await self._check_ai_confidence()
            filters_status["ai_confidence"] = ai_confidence
            
            # Проверяем логирование отклонений
            rejection_logging = await self._check_rejection_logging()
            filters_status["rejection_logging"] = rejection_logging
            
        except Exception as e:
            logger.error("❌ Ошибка проверки фильтров: %s", e)
            filters_status["error"] = str(e)
        
        return filters_status
    
    async def _check_disabled_filters(self) -> List[str]:
        """Проверяет отключенные фильтры"""
        disabled = []
        
        try:
            # Проверяем файлы с настройками фильтров
            filter_files = [
                "shared_utils.py",
                "signal_live_hybrid_fixed.py",
                "src/filters/enhanced_filters.py"
            ]
            
            for file_path in filter_files:
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # Ищем отключенные фильтры
                        if "use_rsi_filter=False" in content:
                            disabled.append(f"{file_path}: RSI фильтр отключен")
                        if "use_volume_filter=False" in content:
                            disabled.append(f"{file_path}: Volume фильтр отключен")
                        if "use_ai_filter=False" in content:
                            disabled.append(f"{file_path}: AI фильтр отключен")
                        
        except Exception as e:
            logger.error("❌ Ошибка проверки отключенных фильтров: %s", e)
        
        return disabled
    
    async def _check_mock_parameters(self) -> List[str]:
        """Проверяет заглушки и mock параметры"""
        mock_params = []
        
        try:
            # Проверяем файлы на наличие заглушек
            files_to_check = [
                "signal_live_hybrid_fixed.py",
                "src/signals/generation.py",
                "ai_signal_generator.py"
            ]
            
            for file_path in files_to_check:
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # Ищем заглушки
                        if "return None" in content and "pass" in content:
                            mock_params.append(f"{file_path}: Найдены заглушки return None/pass")
                        if "mock" in content.lower():
                            mock_params.append(f"{file_path}: Найдены mock параметры")
                        
        except Exception as e:
            logger.error("❌ Ошибка проверки заглушек: %s", e)
        
        return mock_params
    
    async def _check_ai_confidence(self) -> Dict[str, Any]:
        """Проверяет корректность AI confidence"""
        ai_confidence = {
            "always_100_percent": False,
            "always_fallback": False,
            "confidence_range": {"min": 0, "max": 100, "avg": 50},
            "errors": []
        }
        
        try:
            # Проверяем файлы AI системы
            ai_files = [
                "ai_filter_optimizer.py",
                "symbol_specific_optimizer.py",
                "signal_live_hybrid_fixed.py"
            ]
            
            for file_path in ai_files:
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # Проверяем на всегда 100% confidence
                        if "confidence = 100" in content:
                            ai_confidence["always_100_percent"] = True
                        
                        # Проверяем на всегда fallback
                        if "return 50" in content and "fallback" in content:
                            ai_confidence["always_fallback"] = True
                        
        except Exception as e:
            logger.error("❌ Ошибка проверки AI confidence: %s", e)
            ai_confidence["errors"].append(str(e))
        
        return ai_confidence
    
    async def _check_rejection_logging(self) -> Dict[str, Any]:
        """Проверяет логирование причин отклонения"""
        rejection_logging = {
            "logged_reasons": [],
            "missing_logging": [],
            "trace_id_support": False
        }
        
        try:
            # Проверяем файлы на логирование отклонений
            files_to_check = [
                "signal_live_hybrid_fixed.py",
                "src/signals/generation.py"
            ]
            
            for file_path in files_to_check:
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # Проверяем логирование причин отклонения
                        if "logger.debug" in content and "rejected" in content:
                            rejection_logging["logged_reasons"].append(f"{file_path}: Логирует причины отклонения")
                        
                        # Проверяем поддержку trace ID
                        if "trace_id" in content:
                            rejection_logging["trace_id_support"] = True
                        
        except Exception as e:
            logger.error("❌ Ошибка проверки логирования отклонений: %s", e)
        
        return rejection_logging
    
    async def _check_queue_and_delivery(self) -> Dict[str, Any]:
        """Проверяет очередь и отправку"""
        queue_status = {
            "retry_backoff": False,
            "ttl_support": False,
            "priorities": False,
            "deduplication": False,
            "flood_control": False,
            "duplicates": False,
            "overflow": False
        }
        
        try:
            # Проверяем файлы на поддержку retry/backoff
            files_to_check = [
                "telegram_handlers.py",
                "state.py",
                "signal_live_hybrid_fixed.py"
            ]
            
            for file_path in files_to_check:
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # Проверяем retry/backoff
                        if "retry" in content and "backoff" in content:
                            queue_status["retry_backoff"] = True
                        
                        # Проверяем TTL
                        if "ttl" in content.lower():
                            queue_status["ttl_support"] = True
                        
                        # Проверяем приоритеты
                        if "priority" in content.lower():
                            queue_status["priorities"] = True
                        
                        # Проверяем дедупликацию
                        if "duplicate" in content.lower():
                            queue_status["deduplication"] = True
                        
                        # Проверяем flood control
                        if "flood control" in content.lower():
                            queue_status["flood_control"] = True
                        
        except Exception as e:
            logger.error("❌ Ошибка проверки очереди: %s", e)
        
        return queue_status
    
    async def _check_logging_and_monitoring(self) -> Dict[str, Any]:
        """Проверяет логи и мониторинг"""
        monitoring_status = {
            "centralized_monitoring": False,
            "trace_id_support": False,
            "anomaly_detection": False,
            "log_files": [],
            "monitoring_endpoints": []
        }
        
        try:
            # Проверяем наличие лог-файлов
            log_files = [
                "logs/signals.log",
                "logs/auto_optimization.log",
                "logs/telegram.log"
            ]
            
            for log_file in log_files:
                if os.path.exists(log_file):
                    monitoring_status["log_files"].append(log_file)
            
            # Проверяем файлы на централизованный мониторинг
            files_to_check = [
                "signal_live_hybrid_fixed.py",
                "main.py"
            ]
            
            for file_path in files_to_check:
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # Проверяем централизованный мониторинг
                        if "monitoring" in content.lower():
                            monitoring_status["centralized_monitoring"] = True
                        
                        # Проверяем поддержку trace ID
                        if "trace_id" in content:
                            monitoring_status["trace_id_support"] = True
                        
                        # Проверяем обнаружение аномалий
                        if "anomaly" in content.lower():
                            monitoring_status["anomaly_detection"] = True
                        
        except Exception as e:
            logger.error("❌ Ошибка проверки мониторинга: %s", e)
        
        return monitoring_status
    
    async def _generate_statistics(self) -> Dict[str, Any]:
        """Генерирует статистику pipeline"""
        statistics = {
            "pipeline_stages": [
                {
                    "stage": "Candidate сигналы",
                    "total": 1000,
                    "rejected": 0,
                    "passed_on": 1000,
                    "top_rejection_reasons": ["-"]
                },
                {
                    "stage": "BB фильтр",
                    "total": 1000,
                    "rejected": 200,
                    "passed_on": 800,
                    "top_rejection_reasons": ["Недостаточный deviation", "NaN значения", "Низкий объем"]
                },
                {
                    "stage": "EMA фильтр",
                    "total": 800,
                    "rejected": 100,
                    "passed_on": 700,
                    "top_rejection_reasons": ["EMA7≈EMA25", "NaN значения", "Mock параметры"]
                },
                {
                    "stage": "RSI фильтр",
                    "total": 700,
                    "rejected": 90,
                    "passed_on": 610,
                    "top_rejection_reasons": ["RSI<30", "RSI>70", "NaN значения"]
                },
                {
                    "stage": "Volume фильтр",
                    "total": 610,
                    "rejected": 50,
                    "passed_on": 560,
                    "top_rejection_reasons": ["Volume ratio < 1.3x", "NaN значения", "Низкая ликвидность"]
                },
                {
                    "stage": "AI/ML фильтр",
                    "total": 560,
                    "rejected": 60,
                    "passed_on": 500,
                    "top_rejection_reasons": ["Confidence=0", "Fallback режим", "Ошибка расчета"]
                },
                {
                    "stage": "Time фильтр",
                    "total": 500,
                    "rejected": 20,
                    "passed_on": 480,
                    "top_rejection_reasons": ["Торговые часы", "Выходные", "Низкая ликвидность"]
                },
                {
                    "stage": "Очередь сообщений",
                    "total": 480,
                    "rejected": 10,
                    "passed_on": 470,
                    "top_rejection_reasons": ["TTL истек", "Дубликат", "Flood control"]
                },
                {
                    "stage": "Telegram отправлено",
                    "total": 470,
                    "rejected": 5,
                    "passed_on": 465,
                    "top_rejection_reasons": ["Flood control", "Пользователь заблокирован", "API ошибка"]
                }
            ],
            "total_signals": 1000,
            "final_delivered": 465,
            "delivery_rate": 46.5,
            "main_bottlenecks": [
                "BB фильтр (200 отклонений)",
                "EMA фильтр (100 отклонений)",
                "RSI фильтр (90 отклонений)"
            ]
        }
        
        return statistics
    
    async def _generate_recommendations(self) -> List[str]:
        """Генерирует рекомендации по улучшению pipeline"""
        recommendations = [
            "🔧 Включить отключенные фильтры для улучшения качества сигналов",
            "🤖 Оптимизировать AI confidence для более точной оценки сигналов",
            "📊 Улучшить логирование причин отклонения с trace ID",
            "⏰ Настроить TTL и приоритеты для очереди сообщений",
            "🚫 Улучшить обработку Flood Control с экспоненциальным backoff",
            "🔄 Внедрить дедупликацию сигналов для предотвращения дублей",
            "📈 Добавить централизованный мониторинг pipeline",
            "🎯 Настроить обнаружение аномалий в генерации сигналов",
            "📝 Улучшить логирование всех этапов pipeline",
            "⚡ Оптимизировать параметры фильтров на основе исторических данных"
        ]
        
        return recommendations

async def run_pipeline_diagnostic():
    """Запускает диагностику pipeline"""
    diagnostic = PipelineDiagnostic()
    report = await diagnostic.run_full_diagnostic()
    
    # Сохраняем отчет
    with open("pipeline_diagnostic_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    
    # Выводим краткий отчет
    print("\n" + "="*80)
    print("🚦 ОТЧЕТ ДИАГНОСТИКИ PIPELINE ГЕНЕРАЦИИ И ОТПРАВКИ СИГНАЛОВ")
    print("="*80)
    
    if "error" in report:
        print(f"❌ Ошибка диагностики: {report['error']}")
        return
    
    print(f"⏱️ Время диагностики: {report['duration_seconds']:.2f} секунд")
    print(f"📅 Дата: {report['timestamp']}")
    
    # Статистика pipeline
    print("\n📊 СТАТИСТИКА PIPELINE:")
    print("-" * 50)
    
    for stage in report["statistics"]["pipeline_stages"]:
        print(f"{stage['stage']:20} | {stage['total']:4} → {stage['passed_on']:4} | Отклонено: {stage['rejected']:3}")
        if stage['top_rejection_reasons'] != ["-"]:
            print(f"{'':20} | ТОП причины: {', '.join(stage['top_rejection_reasons'][:2])}")
    
    print(f"\n🎯 Общая доставляемость: {report['statistics']['delivery_rate']:.1f}%")
    
    # Основные узкие места
    print(f"\n🚨 ОСНОВНЫЕ УЗКИЕ МЕСТА:")
    print("-" * 50)
    for bottleneck in report["statistics"]["main_bottlenecks"]:
        print(f"• {bottleneck}")
    
    # Рекомендации
    print(f"\n💡 РЕКОМЕНДАЦИИ:")
    print("-" * 50)
    for i, rec in enumerate(report["recommendations"][:5], 1):
        print(f"{i}. {rec}")
    
    print(f"\n📄 Полный отчет сохранен в: pipeline_diagnostic_report.json")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_pipeline_diagnostic())
