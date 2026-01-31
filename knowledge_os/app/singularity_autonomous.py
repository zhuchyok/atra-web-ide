"""
Singularity Autonomous Operations Manager
Главный файл для запуска всех автономных компонентов Singularity 7.5
"""

import asyncio
import os
import logging
import signal
from typing import Optional

logger = logging.getLogger(__name__)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class SingularityAutonomousManager:
    """
    Менеджер автономных операций Singularity 7.5.
    Управляет всеми автономными компонентами системы.
    """
    
    def __init__(self):
        self._running = False
        self._tasks: list = []
        self._components = {}
    
    async def initialize_components(self):
        """Инициализирует все автономные компоненты"""
        logger.info("🚀 Инициализация автономных компонентов Singularity 7.5...")
        
        try:
            # 1. Auto Model Manager
            from auto_model_manager import get_auto_model_manager
            ollama_url = os.getenv('SERVER_LLM_URL', 'http://185.177.216.15:11434')
            auto_model_mgr = get_auto_model_manager(ollama_url)
            self._components['auto_model_manager'] = auto_model_mgr
            logger.info("✅ Auto Model Manager инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Auto Model Manager не инициализирован: {e}")
        
        try:
            # 2. Auto Backup Manager
            from auto_backup_manager import get_auto_backup_manager
            backup_mgr = get_auto_backup_manager()
            self._components['auto_backup_manager'] = backup_mgr
            logger.info("✅ Auto Backup Manager инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Auto Backup Manager не инициализирован: {e}")
        
        try:
            # 3. Anomaly Detector
            from anomaly_detector import get_anomaly_detector
            anomaly_detector = get_anomaly_detector()
            self._components['anomaly_detector'] = anomaly_detector
            logger.info("✅ Anomaly Detector инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Anomaly Detector не инициализирован: {e}")
        
        try:
            # 4. Model Validator
            from model_validator import get_model_validator
            validator = get_model_validator()
            self._components['model_validator'] = validator
            logger.info("✅ Model Validator инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Model Validator не инициализирован: {e}")
        
        try:
            # 5. Auto Prompt Optimizer
            from auto_prompt_optimizer import get_auto_prompt_optimizer
            optimizer = get_auto_prompt_optimizer()
            self._components['auto_prompt_optimizer'] = optimizer
            logger.info("✅ Auto Prompt Optimizer инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Auto Prompt Optimizer не инициализирован: {e}")
        
        try:
            # 6. Telegram Alerter
            from telegram_alerter import get_telegram_alerter
            alerter = get_telegram_alerter()
            self._components['telegram_alerter'] = alerter
            logger.info("✅ Telegram Alerter инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Telegram Alerter не инициализирован: {e}")
        
        try:
            # 7. Metrics Collector
            from metrics_collector import get_metrics_collector
            metrics_collector = get_metrics_collector()
            self._components['metrics_collector'] = metrics_collector
            logger.info("✅ Metrics Collector инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Metrics Collector не инициализирован: {e}")
        
        try:
            # 8. SLA Monitor
            from sla_monitor import get_sla_monitor
            sla_monitor = get_sla_monitor()
            self._components['sla_monitor'] = sla_monitor
            logger.info("✅ SLA Monitor инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ SLA Monitor не инициализирован: {e}")
        
        try:
            # 9. Safety Checker
            from safety_checker import SafetyChecker
            safety_checker = SafetyChecker()
            self._components['safety_checker'] = safety_checker
            logger.info("✅ Safety Checker инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Safety Checker не инициализирован: {e}")
        
        try:
            # 10. Cache Cleanup Task (Singularity 8.0)
            from cache_cleanup_task import get_cache_cleanup_task
            cleanup_task = get_cache_cleanup_task(cleanup_interval=1800)  # 30 минут
            self._components['cache_cleanup_task'] = cleanup_task
            logger.info("✅ Cache Cleanup Task инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Cache Cleanup Task не инициализирован: {e}")
        
        logger.info(f"✅ Инициализировано {len(self._components)} компонентов")
    
    async def start_all_components(self):
        """Запускает все автономные компоненты"""
        logger.info("🔄 Запуск всех автономных компонентов...")
        
        # Auto Model Manager
        if 'auto_model_manager' in self._components:
            self._components['auto_model_manager'].start_monitoring()
            logger.info("✅ Auto Model Manager запущен")
        
        # Auto Backup Manager
        if 'auto_backup_manager' in self._components:
            self._components['auto_backup_manager'].start_monitoring()
            logger.info("✅ Auto Backup Manager запущен")
        
        # Cache Cleanup Task
        if 'cache_cleanup_task' in self._components:
            cleanup_task = self._components['cache_cleanup_task']
            self._tasks.append(asyncio.create_task(cleanup_task.start()))
            logger.info("✅ Cache Cleanup Task запущен (очистка каждые 30 минут)")
        
        # Report Generator (Singularity 8.0)
        try:
            from report_generator import get_report_generator
            report_generator = get_report_generator()
            self._tasks.append(asyncio.create_task(report_generator.start_periodic_reports()))
            logger.info("✅ Report Generator запущен (периодические отчеты)")
        except Exception as e:
            logger.warning(f"⚠️ Report Generator не запущен: {e}")
        
        # Остальные компоненты работают по требованию или через enhanced_monitor
    
    async def stop_all_components(self):
        """Останавливает все автономные компоненты"""
        logger.info("🛑 Остановка всех автономных компонентов...")
        
        # Auto Model Manager
        if 'auto_model_manager' in self._components:
            self._components['auto_model_manager'].stop_monitoring()
        
        # Auto Backup Manager
        if 'auto_backup_manager' in self._components:
            self._components['auto_backup_manager'].stop_monitoring()
        
        # Cache Cleanup Task
        if 'cache_cleanup_task' in self._components:
            cleanup_task = self._components['cache_cleanup_task']
            await cleanup_task.stop()
            logger.info("✅ Cache Cleanup Task остановлен")
        
        # Отменяем все задачи
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        logger.info("✅ Все компоненты остановлены")
    
    async def run_periodic_tasks(self):
        """Запускает периодические задачи"""
        while self._running:
            try:
                # Валидация моделей (раз в день в 2:00)
                from datetime import datetime
                current_hour = datetime.now().hour
                
                if current_hour == 2 and 'model_validator' in self._components:
                    logger.info("🧪 Запуск валидации моделей...")
                    validator = self._components['model_validator']
                    results = await validator.validate_all_models()
                    if results:
                        passed = sum(1 for r in results if r.passed)
                        logger.info(f"✅ Валидация завершена: {passed}/{len(results)} моделей прошли")
                
                # Генерация ежедневного отчета (раз в день в 8:00) (Singularity 8.0)
                if current_hour == 8:
                    try:
                        from report_generator import get_report_generator
                        report_gen = get_report_generator()
                        daily_report = await report_gen.generate_daily_report()
                        await report_gen.send_report_to_telegram(daily_report, "daily")
                        logger.info("✅ Ежедневный отчет отправлен")
                    except Exception as e:
                        logger.error(f"❌ Ошибка генерации ежедневного отчета: {e}")
                
                # Генерация еженедельного отчета (раз в неделю в понедельник в 9:00) (Singularity 8.0)
                if current_hour == 9 and datetime.now().weekday() == 0:  # Понедельник
                    try:
                        from report_generator import get_report_generator
                        report_gen = get_report_generator()
                        weekly_report = await report_gen.generate_weekly_report()
                        await report_gen.send_report_to_telegram(weekly_report, "weekly")
                        logger.info("✅ Еженедельный отчет отправлен")
                    except Exception as e:
                        logger.error(f"❌ Ошибка генерации еженедельного отчета: {e}")
                
                # Оптимизация промптов (раз в день в 3:00)
                if current_hour == 3 and 'auto_prompt_optimizer' in self._components:
                    logger.info("💡 Запуск анализа промптов...")
                    optimizer = self._components['auto_prompt_optimizer']
                    # Получаем текущий промпт (пример)
                    current_prompt = "Ты - Виктория, Team Lead команды экспертов..."
                    improvements = await optimizer.suggest_improvements(current_prompt, "Виктория")
                    if improvements:
                        logger.info(f"💡 Найдено {len(improvements)} предложений по улучшению")
                        for imp in improvements[:3]:
                            await optimizer.log_improvement(imp, "Виктория", applied=False)
                
                # Повторная отправка неудачных алертов (каждый час)
                if 'telegram_alerter' in self._components:
                    alerter = self._components['telegram_alerter']
                    await alerter.retry_failed_alerts()
                
                # Ждем до следующей проверки (проверяем каждый час)
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в периодических задачах: {e}")
                await asyncio.sleep(3600)
    
    async def run(self):
        """Главный цикл работы"""
        self._running = True
        
        # Инициализация
        await self.initialize_components()
        
        # Запуск компонентов
        await self.start_all_components()
        
        # Запуск периодических задач
        periodic_task = asyncio.create_task(self.run_periodic_tasks())
        self._tasks.append(periodic_task)
        
        logger.info("✅ Singularity Autonomous Manager запущен")
        
        # Ожидание завершения
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("🛑 Получен сигнал остановки")
        finally:
            await self.stop_all_components()
            logger.info("✅ Singularity Autonomous Manager остановлен")
    
    def get_status(self) -> dict:
        """Возвращает статус всех компонентов"""
        status = {
            "running": self._running,
            "components": {}
        }
        
        for name, component in self._components.items():
            if hasattr(component, '_running'):
                status["components"][name] = {
                    "initialized": True,
                    "running": getattr(component, '_running', False)
                }
            else:
                status["components"][name] = {
                    "initialized": True,
                    "running": None
                }
        
        return status

# Глобальный экземпляр
_manager: Optional[SingularityAutonomousManager] = None

def get_autonomous_manager() -> SingularityAutonomousManager:
    """Получить глобальный экземпляр менеджера"""
    global _manager
    if _manager is None:
        _manager = SingularityAutonomousManager()
    return _manager

async def main():
    """Главная функция для запуска"""
    manager = get_autonomous_manager()
    
    # Обработка сигналов для graceful shutdown
    def signal_handler(sig, frame):
        logger.info("🛑 Получен сигнал остановки")
        manager._running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск
    await manager.run()

if __name__ == "__main__":
    asyncio.run(main())

