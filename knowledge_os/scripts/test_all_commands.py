#!/usr/bin/env python3
"""
Скрипт для проверки всех команд Telegram бота
Проверяет регистрацию команд, наличие обработчиков и их работоспособность
"""

import sys
import os
import importlib
import inspect
import asyncio
from typing import Dict, List, Tuple, Optional

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_command_registration() -> Dict[str, bool]:
    """Проверяет регистрацию команд в bot_core.py"""
    print("🔍 Проверка регистрации команд в bot_core.py...")
    print("=" * 60)
    
    bot_core_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "telegram", "bot_core.py")
    
    if not os.path.exists(bot_core_path):
        print(f"❌ Файл {bot_core_path} не найден")
        return {}
    
    registered_commands = {}
    
    with open(bot_core_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Ищем все CommandHandler регистрации
        import re
        pattern = r'CommandHandler\("(\w+)",\s*(\w+)\)'
        matches = re.findall(pattern, content)
        
        for command, handler in matches:
            registered_commands[command] = {
                'handler': handler,
                'registered': True
            }
    
    print(f"✅ Найдено {len(registered_commands)} зарегистрированных команд")
    return registered_commands

def check_command_handlers() -> Dict[str, bool]:
    """Проверяет наличие обработчиков команд"""
    print("\n🔍 Проверка наличия обработчиков команд...")
    print("=" * 60)
    
    handlers_status = {}
    
    # Список команд и их обработчиков
    commands_map = {
        'start': ('src.telegram.handlers', 'start'),
        'help': ('src.telegram.commands', 'help_cmd'),
        'balance': ('src.telegram.commands', 'balance_cmd'),
        'positions': ('src.telegram.commands', 'positions_cmd'),
        'status': ('src.telegram.commands', 'status_cmd'),
        'myreport': ('src.telegram.commands', 'myreport_cmd'),
        'perf': ('src.telegram.handlers', 'perf'),
        'portfolio': ('src.telegram.handlers', 'portfolio'),
        'sentiment': ('src.telegram.handlers', 'sentiment'),
        'set_balance': ('src.telegram.commands', 'set_balance_cmd'),
        'set_risk': ('src.telegram.commands', 'set_risk_cmd'),
        'set_trade_mode': ('src.telegram.commands', 'set_trade_mode_cmd'),
        'set_filter_mode': ('src.telegram.commands', 'set_filter_mode_cmd'),
        'set_trading_hours': ('src.telegram.commands', 'set_trading_hours_cmd'),
        'mode': ('src.telegram.handlers', 'mode_cmd'),
        'mode_set': ('src.telegram.handlers', 'mode_set_cmd'),
        'connect_bitget': ('src.telegram.handlers', 'connect_bitget_cmd'),
        'disconnect_bitget': ('src.telegram.handlers', 'disconnect_bitget_cmd'),
        'trade_history': ('src.telegram.trading', 'trade_history_cmd'),
        'close': ('src.telegram.trading', 'close_cmd'),
        'accept_signal': ('src.telegram.trading', 'accept_signal_cmd'),
        'close_all_positions': ('src.telegram.trading', 'close_all_positions_cmd'),
        'last_signal': ('src.telegram.commands', 'last_signal_cmd'),
        'report': ('src.telegram.commands', 'report_cmd'),
        'report_week': ('src.telegram.commands', 'report_week_cmd'),
        'audit_today': ('src.telegram.commands', 'audit_today_cmd'),
        'backtest': ('src.telegram.commands', 'backtest_cmd'),
        'backtest_all': ('src.telegram.handlers', 'backtest_all_cmd'),
        'health': ('src.telegram.commands', 'health_cmd'),
        'daily_report': ('src.telegram.commands', 'daily_report_cmd'),
        'add_admin': ('src.telegram.commands', 'add_admin_cmd'),
        'remove_admin': ('src.telegram.commands', 'remove_admin_cmd'),
        'add_user': ('src.telegram.admin', 'add_user_cmd'),
        'remove_user': ('src.telegram.admin', 'remove_user_cmd'),
        'list_users': ('src.telegram.admin', 'list_users_cmd'),
        'metrics': ('src.telegram.metrics', 'metrics_cmd'),
        'performance': ('src.telegram.metrics', 'performance_cmd'),
        'trades': ('src.telegram.metrics', 'trades_cmd'),
        'signal_stats': ('src.telegram.commands', 'signal_stats_cmd'),
        'perf_sys': ('src.telegram.commands', 'perf_sys_cmd'),
    }
    
    for command, (module_path, handler_name) in commands_map.items():
        try:
            module = importlib.import_module(module_path)
            handler = getattr(module, handler_name, None)
            
            if handler is None:
                handlers_status[command] = {
                    'exists': False,
                    'is_async': False,
                    'error': f'Handler {handler_name} not found in {module_path}'
                }
            else:
                is_async = inspect.iscoroutinefunction(handler)
                handlers_status[command] = {
                    'exists': True,
                    'is_async': is_async,
                    'error': None
                }
        except ImportError as e:
            handlers_status[command] = {
                'exists': False,
                'is_async': False,
                'error': f'Module {module_path} not found: {e}'
            }
        except Exception as e:
            handlers_status[command] = {
                'exists': False,
                'is_async': False,
                'error': f'Error checking {command}: {e}'
            }
    
    return handlers_status

def check_bot_commands_list() -> List[str]:
    """Проверяет список команд в BotCommand"""
    print("\n🔍 Проверка списка команд в BotCommand...")
    print("=" * 60)
    
    bot_core_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "telegram", "bot_core.py")
    
    if not os.path.exists(bot_core_path):
        print(f"❌ Файл {bot_core_path} не найден")
        return []
    
    commands_list = []
    
    with open(bot_core_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Ищем все BotCommand регистрации
        import re
        pattern = r'BotCommand\("(\w+)",\s*"[^"]+"\)'
        matches = re.findall(pattern, content)
        commands_list = matches
    
    print(f"✅ Найдено {len(commands_list)} команд в BotCommand")
    return commands_list

def generate_report(registered: Dict, handlers: Dict, bot_commands: List) -> str:
    """Генерирует отчёт о проверке команд"""
    report = []
    report.append("# 📋 ОТЧЁТ О ПРОВЕРКЕ КОМАНД TELEGRAM БОТА\n")
    report.append("## 📊 СТАТИСТИКА\n")
    report.append(f"- Зарегистрированных команд: {len(registered)}\n")
    report.append(f"- Команд в BotCommand: {len(bot_commands)}\n")
    report.append(f"- Проверенных обработчиков: {len(handlers)}\n")
    report.append("\n## ✅ РАБОТАЮЩИЕ КОМАНДЫ\n")
    
    working = []
    broken = []
    missing = []
    
    all_commands = set(registered.keys()) | set(handlers.keys()) | set(bot_commands)
    
    for command in sorted(all_commands):
        is_registered = command in registered
        handler_info = handlers.get(command, {})
        is_in_bot_commands = command in bot_commands
        
        status = []
        if is_registered:
            status.append("✅ Зарегистрирован")
        else:
            status.append("❌ Не зарегистрирован")
        
        if handler_info.get('exists'):
            if handler_info.get('is_async'):
                status.append("✅ Обработчик (async)")
            else:
                status.append("⚠️ Обработчик (sync)")
        else:
            status.append(f"❌ Обработчик: {handler_info.get('error', 'не найден')}")
        
        if is_in_bot_commands:
            status.append("✅ В BotCommand")
        else:
            status.append("❌ Не в BotCommand")
        
        if all([is_registered, handler_info.get('exists'), is_in_bot_commands]):
            working.append(f"- `/{command}`: {' | '.join(status)}")
        elif handler_info.get('exists'):
            broken.append(f"- `/{command}`: {' | '.join(status)}")
        else:
            missing.append(f"- `/{command}`: {' | '.join(status)}")
    
    if working:
        report.append("\n".join(working))
        report.append("")
    
    if broken:
        report.append("\n## ⚠️ КОМАНДЫ С ПРОБЛЕМАМИ\n")
        report.append("\n".join(broken))
        report.append("")
    
    if missing:
        report.append("\n## ❌ ОТСУТСТВУЮЩИЕ КОМАНДЫ\n")
        report.append("\n".join(missing))
        report.append("")
    
    return "\n".join(report)

def main():
    """Основная функция"""
    print("🚀 ЗАПУСК ПРОВЕРКИ ВСЕХ КОМАНД TELEGRAM БОТА")
    print("=" * 60)
    print()
    
    # Проверяем регистрацию команд
    registered = check_command_registration()
    
    # Проверяем обработчики
    handlers = check_command_handlers()
    
    # Проверяем список BotCommand
    bot_commands = check_bot_commands_list()
    
    # Генерируем отчёт
    report = generate_report(registered, handlers, bot_commands)
    
    print("\n" + "=" * 60)
    print("📋 ОТЧЁТ:")
    print("=" * 60)
    print(report)
    
    # Сохраняем отчёт в файл
    report_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "COMMANDS_CHECK_REPORT.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ Отчёт сохранён в {report_path}")
    
    # Подсчитываем статистику
    working_count = sum(1 for cmd in set(registered.keys()) | set(handlers.keys()) | set(bot_commands)
                       if cmd in registered and handlers.get(cmd, {}).get('exists') and cmd in bot_commands)
    
    print(f"\n📊 ИТОГО:")
    print(f"   ✅ Работающих команд: {working_count}")
    print(f"   ⚠️ Команд с проблемами: {len(set(registered.keys()) | set(handlers.keys()) | set(bot_commands)) - working_count}")

if __name__ == "__main__":
    main()

