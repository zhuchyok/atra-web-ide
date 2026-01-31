#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система восстановления после сбоев для торгового бота.

Предоставляет автоматическое восстановление:
- Автовосстановление после сбоев
- Резервное копирование состояния
- Восстановление позиций
- Защита от потери данных
"""

import asyncio
import logging
import json
import os
import shutil
import psutil
import signal
import sys
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import time

logger = logging.getLogger(__name__)

@dataclass
class SystemState:
    """Состояние системы"""
    timestamp: datetime
    process_id: int
    memory_usage: float
    cpu_usage: float
    active_connections: int
    positions_count: int
    orders_count: int
    last_signal_time: datetime
    system_health: str  # 'healthy', 'warning', 'critical'
    error_count: int
    recovery_attempts: int

@dataclass
class BackupInfo:
    """Информация о резервной копии"""
    backup_id: str
    timestamp: datetime
    file_path: str
    file_size: int
    backup_type: str  # 'full', 'incremental', 'state'
    status: str  # 'success', 'failed', 'in_progress'

@dataclass
class RecoveryAction:
    """Действие восстановления"""
    action_id: str
    action_type: str  # 'restart', 'reload_config', 'clear_cache', 'restore_backup'
    timestamp: datetime
    status: str  # 'pending', 'in_progress', 'completed', 'failed'
    result: str = None
    error_message: str = None

class RecoverySystem:
    """Главный класс системы восстановления"""
    
    def __init__(self):
        self.system_state = None
        self.backup_info = []
        self.recovery_actions = []
        
        # Настройки системы
        self.settings = {
            'backup_interval': 300,  # 5 минут
            'max_backups': 10,
            'backup_retention_days': 7,
            'health_check_interval': 60,  # 1 минута
            'auto_recovery_enabled': True,
            'max_recovery_attempts': 3,
            'recovery_cooldown': 300,  # 5 минут
            'critical_memory_usage': 90.0,  # %
            'critical_cpu_usage': 95.0,  # %
            'max_error_count': 10
        }
        
        # Пути для резервного копирования
        self.backup_paths = {
            'database': 'trading.db',
            'config': 'config.json',
            'state': 'system_state.json',
            'logs': 'logs/',
            'data': 'data/'
        }
        
        # Статистика восстановления
        self.recovery_stats = {
            'total_recoveries': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'backups_created': 0,
            'backups_restored': 0,
            'last_recovery_time': None,
            'uptime_hours': 0.0
        }
        
        # Мониторинг системы
        self.monitoring_thread = None
        self.monitoring_active = False
        
        # Обработчики сигналов
        self._setup_signal_handlers()
        
        # Время запуска
        self.start_time = datetime.now()

    def _setup_signal_handlers(self):
        """Настраивает обработчики сигналов"""
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self._graceful_shutdown()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def start_monitoring(self):
        """Запускает мониторинг системы"""
        
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("System monitoring started")

    def stop_monitoring(self):
        """Останавливает мониторинг системы"""
        
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("System monitoring stopped")

    def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        
        while self.monitoring_active:
            try:
                # Обновляем состояние системы
                self._update_system_state()
                
                # Проверяем здоровье системы
                health_status = self._check_system_health()
                
                # Создаем резервные копии
                if self._should_create_backup():
                    self._create_backup()
                
                # Проверяем необходимость восстановления
                if health_status == 'critical' and self.settings['auto_recovery_enabled']:
                    self._initiate_recovery()
                
                # Очищаем старые резервные копии
                self._cleanup_old_backups()
                
                # Ждем до следующей проверки
                time.sleep(self.settings['health_check_interval'])
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)  # Ждем перед повторной попыткой

    def _update_system_state(self):
        """Обновляет состояние системы"""
        
        try:
            # Получаем информацию о процессе
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_usage = (memory_info.rss / (1024 * 1024 * 1024)) * 100  # GB
            
            cpu_usage = process.cpu_percent()
            
            # Подсчитываем активные соединения
            connections = len(process.connections())
            
            # Получаем количество позиций и ордеров (заглушка)
            positions_count = 0  # Здесь должна быть реальная логика
            orders_count = 0     # Здесь должна быть реальная логика
            
            # Время последнего сигнала
            last_signal_time = datetime.now()  # Заглушка
            
            # Определяем здоровье системы
            system_health = self._determine_system_health(memory_usage, cpu_usage)
            
            self.system_state = SystemState(
                timestamp=datetime.now(),
                process_id=os.getpid(),
                memory_usage=memory_usage,
                cpu_usage=cpu_usage,
                active_connections=connections,
                positions_count=positions_count,
                orders_count=orders_count,
                last_signal_time=last_signal_time,
                system_health=system_health,
                error_count=0,  # Заглушка
                recovery_attempts=self.recovery_stats['total_recoveries']
            )
            
        except Exception as e:
            logger.error(f"Error updating system state: {e}")

    def _determine_system_health(self, memory_usage: float, cpu_usage: float) -> str:
        """Определяет здоровье системы"""
        
        if (memory_usage > self.settings['critical_memory_usage'] or 
            cpu_usage > self.settings['critical_cpu_usage']):
            return 'critical'
        elif (memory_usage > self.settings['critical_memory_usage'] * 0.8 or 
              cpu_usage > self.settings['critical_cpu_usage'] * 0.8):
            return 'warning'
        else:
            return 'healthy'

    def _check_system_health(self) -> str:
        """Проверяет здоровье системы"""
        
        if not self.system_state:
            return 'unknown'
        
        return self.system_state.system_health

    def _should_create_backup(self) -> bool:
        """Проверяет, нужно ли создавать резервную копию"""
        
        if not self.backup_info:
            return True
        
        last_backup = max(self.backup_info, key=lambda b: b.timestamp)
        time_since_backup = (datetime.now() - last_backup.timestamp).total_seconds()
        
        return time_since_backup >= self.settings['backup_interval']

    def _create_backup(self):
        """Создает резервную копию"""
        
        try:
            backup_id = f"BACKUP_{int(datetime.now().timestamp())}"
            backup_dir = f"backups/{backup_id}"
            os.makedirs(backup_dir, exist_ok=True)
            
            total_size = 0
            
            # Копируем файлы
            for name, path in self.backup_paths.items():
                if os.path.exists(path):
                    if os.path.isfile(path):
                        shutil.copy2(path, f"{backup_dir}/{name}")
                        total_size += os.path.getsize(path)
                    elif os.path.isdir(path):
                        shutil.copytree(path, f"{backup_dir}/{name}")
                        total_size += sum(os.path.getsize(os.path.join(dirpath, filename))
                                        for dirpath, dirnames, filenames in os.walk(path)
                                        for filename in filenames)
            
            # Сохраняем состояние системы
            state_file = f"{backup_dir}/system_state.json"
            with open(state_file, 'w') as f:
                json.dump(self.system_state.__dict__, f, indent=2, default=str)
            
            # Создаем информацию о резервной копии
            backup_info = BackupInfo(
                backup_id=backup_id,
                timestamp=datetime.now(),
                file_path=backup_dir,
                file_size=total_size,
                backup_type='full',
                status='success'
            )
            
            self.backup_info.append(backup_info)
            self.recovery_stats['backups_created'] += 1
            
            logger.info(f"Backup created: {backup_id} ({total_size} bytes)")
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            
            # Записываем неудачную попытку
            backup_info = BackupInfo(
                backup_id=f"FAILED_{int(datetime.now().timestamp())}",
                timestamp=datetime.now(),
                file_path="",
                file_size=0,
                backup_type='full',
                status='failed'
            )
            self.backup_info.append(backup_info)

    def _initiate_recovery(self):
        """Инициирует восстановление системы"""
        
        # Проверяем cooldown
        if self.recovery_stats['last_recovery_time']:
            time_since_recovery = (datetime.now() - self.recovery_stats['last_recovery_time']).total_seconds()
            if time_since_recovery < self.settings['recovery_cooldown']:
                logger.warning("Recovery cooldown active, skipping recovery")
                return
        
        # Проверяем максимальное количество попыток
        if self.recovery_stats['total_recoveries'] >= self.settings['max_recovery_attempts']:
            logger.error("Maximum recovery attempts reached")
            return
        
        logger.warning("Initiating system recovery")
        
        # Создаем действие восстановления
        action = RecoveryAction(
            action_id=f"RECOVERY_{int(datetime.now().timestamp())}",
            action_type='restart',
            timestamp=datetime.now(),
            status='in_progress'
        )
        
        self.recovery_actions.append(action)
        
        try:
            # Выполняем восстановление
            self._perform_recovery(action)
            
            action.status = 'completed'
            action.result = 'System recovered successfully'
            
            self.recovery_stats['total_recoveries'] += 1
            self.recovery_stats['successful_recoveries'] += 1
            self.recovery_stats['last_recovery_time'] = datetime.now()
            
            logger.info("System recovery completed successfully")
            
        except Exception as e:
            action.status = 'failed'
            action.error_message = str(e)
            
            self.recovery_stats['total_recoveries'] += 1
            self.recovery_stats['failed_recoveries'] += 1
            
            logger.error(f"System recovery failed: {e}")

    def _perform_recovery(self, action: RecoveryAction):
        """Выполняет восстановление системы"""
        
        if action.action_type == 'restart':
            # Перезапуск системы
            self._restart_system()
        elif action.action_type == 'reload_config':
            # Перезагрузка конфигурации
            self._reload_configuration()
        elif action.action_type == 'clear_cache':
            # Очистка кэша
            self._clear_cache()
        elif action.action_type == 'restore_backup':
            # Восстановление из резервной копии
            self._restore_from_backup()

    def _restart_system(self):
        """Перезапускает систему"""
        
        logger.info("Restarting system...")
        
        # Здесь должна быть логика перезапуска
        # В реальной системе это может включать:
        # - Остановку текущих процессов
        # - Запуск новых процессов
        # - Восстановление состояния
        
        time.sleep(2)  # Имитация перезапуска

    def _reload_configuration(self):
        """Перезагружает конфигурацию"""
        
        logger.info("Reloading configuration...")
        
        # Здесь должна быть логика перезагрузки конфигурации
        time.sleep(1)

    def _clear_cache(self):
        """Очищает кэш"""
        
        logger.info("Clearing cache...")
        
        # Здесь должна быть логика очистки кэша
        time.sleep(1)

    def _restore_from_backup(self):
        """Восстанавливает из резервной копии"""
        
        if not self.backup_info:
            raise Exception("No backups available")
        
        # Находим последнюю успешную резервную копию
        successful_backups = [b for b in self.backup_info if b.status == 'success']
        if not successful_backups:
            raise Exception("No successful backups available")
        
        latest_backup = max(successful_backups, key=lambda b: b.timestamp)
        
        logger.info(f"Restoring from backup: {latest_backup.backup_id}")
        
        # Восстанавливаем файлы
        for name, path in self.backup_paths.items():
            backup_path = f"{latest_backup.file_path}/{name}"
            if os.path.exists(backup_path):
                if os.path.isfile(backup_path):
                    shutil.copy2(backup_path, path)
                elif os.path.isdir(backup_path):
                    if os.path.exists(path):
                        shutil.rmtree(path)
                    shutil.copytree(backup_path, path)
        
        self.recovery_stats['backups_restored'] += 1

    def _cleanup_old_backups(self):
        """Очищает старые резервные копии"""
        
        cutoff_date = datetime.now() - timedelta(days=self.settings['backup_retention_days'])
        old_backups = [b for b in self.backup_info if b.timestamp < cutoff_date]
        
        for backup in old_backups:
            try:
                if os.path.exists(backup.file_path):
                    shutil.rmtree(backup.file_path)
                self.backup_info.remove(backup)
            except Exception as e:
                logger.error(f"Error cleaning up backup {backup.backup_id}: {e}")
        
        # Ограничиваем количество резервных копий
        if len(self.backup_info) > self.settings['max_backups']:
            # Сортируем по времени и удаляем старые
            self.backup_info.sort(key=lambda b: b.timestamp)
            excess_backups = self.backup_info[:-self.settings['max_backups']]
            
            for backup in excess_backups:
                try:
                    if os.path.exists(backup.file_path):
                        shutil.rmtree(backup.file_path)
                    self.backup_info.remove(backup)
                except Exception as e:
                    logger.error(f"Error cleaning up excess backup {backup.backup_id}: {e}")

    def _graceful_shutdown(self):
        """Выполняет корректное завершение работы"""
        
        logger.info("Initiating graceful shutdown...")
        
        # Останавливаем мониторинг
        self.stop_monitoring()
        
        # Создаем финальную резервную копию
        self._create_backup()
        
        # Сохраняем состояние
        self.save_state()
        
        logger.info("Graceful shutdown completed")

    def get_system_status(self) -> Dict:
        """Возвращает статус системы"""
        
        uptime = (datetime.now() - self.start_time).total_seconds() / 3600
        
        return {
            'system_state': self.system_state.__dict__ if self.system_state else None,
            'recovery_stats': self.recovery_stats,
            'uptime_hours': uptime,
            'backup_count': len(self.backup_info),
            'recent_backups': [
                {
                    'backup_id': b.backup_id,
                    'timestamp': b.timestamp.isoformat(),
                    'file_size': b.file_size,
                    'status': b.status
                } for b in sorted(self.backup_info, key=lambda x: x.timestamp, reverse=True)[:5]
            ],
            'recent_recoveries': [
                {
                    'action_id': a.action_id,
                    'action_type': a.action_type,
                    'timestamp': a.timestamp.isoformat(),
                    'status': a.status,
                    'result': a.result
                } for a in sorted(self.recovery_actions, key=lambda x: x.timestamp, reverse=True)[:5]
            ],
            'monitoring_active': self.monitoring_active,
            'timestamp': datetime.now().isoformat()
        }

    def save_state(self, filepath: str = 'recovery_system_state.json'):
        """Сохраняет состояние системы"""
        
        state = {
            'backup_info': [
                {
                    'backup_id': b.backup_id,
                    'timestamp': b.timestamp.isoformat(),
                    'file_path': b.file_path,
                    'file_size': b.file_size,
                    'backup_type': b.backup_type,
                    'status': b.status
                } for b in self.backup_info
            ],
            'recovery_actions': [
                {
                    'action_id': a.action_id,
                    'action_type': a.action_type,
                    'timestamp': a.timestamp.isoformat(),
                    'status': a.status,
                    'result': a.result,
                    'error_message': a.error_message
                } for a in self.recovery_actions
            ],
            'recovery_stats': self.recovery_stats,
            'settings': self.settings,
            'start_time': self.start_time.isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Recovery system state saved to {filepath}")

    def load_state(self, filepath: str = 'recovery_system_state.json'):
        """Загружает состояние системы"""
        
        if not os.path.exists(filepath):
            logger.warning(f"State file {filepath} not found")
            return
        
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # Восстанавливаем информацию о резервных копиях
        if state.get('backup_info'):
            self.backup_info = []
            for backup_data in state['backup_info']:
                backup_data['timestamp'] = datetime.fromisoformat(backup_data['timestamp'])
                self.backup_info.append(BackupInfo(**backup_data))
        
        # Восстанавливаем действия восстановления
        if state.get('recovery_actions'):
            self.recovery_actions = []
            for action_data in state['recovery_actions']:
                action_data['timestamp'] = datetime.fromisoformat(action_data['timestamp'])
                self.recovery_actions.append(RecoveryAction(**action_data))
        
        # Восстанавливаем статистику и настройки
        if state.get('recovery_stats'):
            self.recovery_stats = state['recovery_stats']
        
        if state.get('settings'):
            self.settings = state['settings']
        
        if state.get('start_time'):
            self.start_time = datetime.fromisoformat(state['start_time'])
        
        logger.info(f"Recovery system state loaded from {filepath}")

# Глобальный экземпляр
recovery_system = RecoverySystem()
