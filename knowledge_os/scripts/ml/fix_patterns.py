#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для исправления паттернов LightGBM
Синхронизирует trading_patterns.json с signals_log из базы данных
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_patterns(patterns_file: str) -> List[Dict[str, Any]]:
    """Загружает паттерны из файла"""
    if not os.path.exists(patterns_file):
        logger.warning("Файл паттернов не найден: %s", patterns_file)
        return []
    
    try:
        with open(patterns_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error("Ошибка загрузки паттернов: %s", e)
        return []


def get_closed_trades_from_db(db_path: str) -> List[Dict[str, Any]]:
    """Получает закрытые сделки из signals_log"""
    trades = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем все закрытые сделки с результатами
        # Проверяем разные варианты результатов: TP1_PARTIAL, TP1, TP2, SL, SL_BE
        cursor.execute("""
            SELECT 
                symbol, 
                entry,
                tp1,
                tp2,
                stop,
                result,
                net_profit,
                created_at,
                exit_time
            FROM signals_log
            WHERE result IS NOT NULL 
              AND result != ''
              AND entry > 0
              AND (result LIKE 'TP%' OR result LIKE 'SL%' OR result LIKE 'tp%' OR result LIKE 'sl%')
            ORDER BY created_at DESC
        """)
        
        rows = cursor.fetchall()
        logger.info("Найдено %d закрытых сделок в signals_log с TP/SL", len(rows))
        
        for row in rows:
            symbol, entry, tp1, tp2, stop, result, net_profit, created_at, exit_time = row
            
            # Определяем side по ценам (если tp1 > entry, то LONG)
            side = 'LONG' if tp1 and entry and tp1 > entry else 'SHORT'
            
            # Нормализуем result
            result_upper = str(result).upper() if result else ''
            
            # Определяем результат и profit_pct
            if 'TP2' in result_upper or result_upper == 'TP2':
                result_status = 'WIN'
                profit_pct = 4.0  # TP2 = 4%
            elif 'TP1' in result_upper or result_upper == 'TP1':
                result_status = 'WIN'
                profit_pct = 2.0  # TP1 = 2%
            elif 'SL' in result_upper and 'BE' not in result_upper:
                result_status = 'LOSS'
                # Используем net_profit если доступен для расчета profit_pct
                if net_profit and entry:
                    profit_pct = (net_profit / (entry * 100)) * 100  # Приблизительный расчет
                else:
                    profit_pct = -2.0  # SL = -2%
            elif 'SL' in result_upper and 'BE' in result_upper:
                result_status = 'NEUTRAL'  # SL_BE = безубыток
                profit_pct = 0.0
            else:
                result_status = 'NEUTRAL'
                profit_pct = 0.0
            
            # Если есть net_profit, используем его для более точного расчета
            if net_profit and entry:
                # Приблизительный расчет profit_pct из net_profit
                # Предполагаем стандартный размер позиции
                if 'TP2' in result_upper:
                    profit_pct = max(profit_pct, (net_profit / (entry * 100)) * 100)
                elif 'TP1' in result_upper:
                    profit_pct = max(profit_pct, (net_profit / (entry * 50)) * 100)  # 50% позиции
            
            # Используем net_profit если доступен для более точного расчета
            if net_profit and entry:
                # Приблизительный расчет profit_pct из net_profit
                # (net_profit обычно в USDT, нужно знать размер позиции)
                # Но для простоты используем фиксированные значения
                pass
            
            trades.append({
                'symbol': symbol,
                'side': side,
                'entry_price': float(entry) if entry else 0.0,
                'exit_price': float(tp1) if tp1 else (float(tp2) if tp2 else float(entry) * 1.02),
                'result': result_status,
                'profit_pct': profit_pct,
                'net_profit': float(net_profit) if net_profit else 0.0,
                'created_at': created_at,
                'exit_time': exit_time
            })
        
        conn.close()
        return trades
        
    except Exception as e:
        logger.error("Ошибка чтения из БД: %s", e)
        return []


def update_patterns_from_trades(patterns: List[Dict[str, Any]], trades: List[Dict[str, Any]]) -> tuple:
    """Обновляет паттерны результатами из сделок"""
    updated_count = 0
    created_count = 0
    
    # Создаем индекс паттернов по symbol + timestamp (приблизительно)
    pattern_index = {}
    for i, pattern in enumerate(patterns):
        symbol = pattern.get('symbol', '')
        timestamp = pattern.get('timestamp', '')
        key = f"{symbol}_{timestamp[:10]}"  # Дата без времени
        if key not in pattern_index:
            pattern_index[key] = []
        pattern_index[key].append(i)
    
    # Обновляем паттерны
    for trade in trades:
        symbol = trade['symbol']
        side = trade['side']
        entry_price = trade['entry_price']
        result = trade['result']
        profit_pct = trade['profit_pct']
        created_at = trade['created_at']
        
        # Ищем паттерн для обновления
        found = False
        date_key = created_at[:10] if created_at else ''
        key = f"{symbol}_{date_key}"
        
        if key in pattern_index:
            for idx in pattern_index[key]:
                pattern = patterns[idx]
                # Проверяем совпадение
                if (pattern.get('symbol') == symbol and
                    pattern.get('signal_type', '').upper() == side.upper() and
                    abs(pattern.get('entry_price', 0) - entry_price) < entry_price * 0.01):  # В пределах 1%
                    
                    # Обновляем паттерн
                    if pattern.get('result') in (None, 'NEUTRAL', ''):
                        pattern['result'] = result
                        pattern['profit_pct'] = profit_pct
                        updated_count += 1
                        found = True
                        logger.debug("Обновлен паттерн: %s %s -> %s", symbol, side, result)
                        break
        
        # Если паттерн не найден, создаем новый (только для WIN/LOSS)
        if not found and result in ('WIN', 'LOSS'):
            new_pattern = {
                'symbol': symbol,
                'timestamp': created_at or datetime.now().isoformat(),
                'signal_type': side.upper(),
                'entry_price': entry_price,
                'tp1': trade.get('exit_price', entry_price * 1.02),
                'tp2': trade.get('exit_price', entry_price * 1.04),
                'risk_pct': 2.0,
                'leverage': 1.0,
                'indicators': {},
                'market_conditions': {},
                'result': result,
                'profit_pct': profit_pct
            }
            patterns.append(new_pattern)
            created_count += 1
            logger.debug("Создан новый паттерн: %s %s -> %s", symbol, side, result)
    
    return updated_count, created_count


def save_patterns(patterns: List[Dict[str, Any]], patterns_file: str):
    """Сохраняет паттерны в файл"""
    try:
        # Создаем backup
        if os.path.exists(patterns_file):
            backup_file = f"{patterns_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            import shutil
            shutil.copy2(patterns_file, backup_file)
            logger.info("Создан backup: %s", backup_file)
        
        with open(patterns_file, 'w', encoding='utf-8') as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False)
        
        logger.info("Сохранено %d паттернов в %s", len(patterns), patterns_file)
    except Exception as e:
        logger.error("Ошибка сохранения паттернов: %s", e)


def main():
    """Основная функция"""
    logger.info("🚀 Запуск исправления паттернов LightGBM...")
    
    # Пути
    db_path = "trading.db"
    patterns_file = "ai_learning_data/trading_patterns.json"
    
    # Загружаем паттерны
    logger.info("📂 Загрузка паттернов из %s...", patterns_file)
    patterns = load_patterns(patterns_file)
    logger.info("Загружено %d паттернов", len(patterns))
    
    # Проверяем текущее состояние
    results_before = {}
    for p in patterns:
        result = p.get('result')
        results_before[result] = results_before.get(result, 0) + 1
    logger.info("Текущее распределение результатов: %s", results_before)
    
    # Получаем закрытые сделки из БД
    logger.info("📊 Загрузка закрытых сделок из %s...", db_path)
    trades = get_closed_trades_from_db(db_path)
    logger.info("Загружено %d закрытых сделок", len(trades))
    
    if not trades:
        logger.warning("⚠️ Нет закрытых сделок в БД. Модель не может быть обучена правильно.")
        return
    
    # Обновляем паттерны
    logger.info("🔄 Обновление паттернов...")
    updated_count, created_count = update_patterns_from_trades(patterns, trades)
    logger.info("Обновлено: %d, Создано: %d", updated_count, created_count)
    
    # Проверяем новое состояние
    results_after = {}
    for p in patterns:
        result = p.get('result')
        results_after[result] = results_after.get(result, 0) + 1
    logger.info("Новое распределение результатов: %s", results_after)
    
    # Сохраняем паттерны
    logger.info("💾 Сохранение паттернов...")
    save_patterns(patterns, patterns_file)
    
    # Проверяем баланс классов
    win_count = results_after.get('WIN', 0)
    loss_count = results_after.get('LOSS', 0)
    
    if win_count == 0 or loss_count == 0:
        logger.error("❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Все еще нет WIN или LOSS паттернов!")
        logger.error("WIN: %d, LOSS: %d", win_count, loss_count)
        logger.error("Модель не может быть обучена правильно без обоих классов.")
    else:
        logger.info("✅ Баланс классов: WIN=%d (%.1f%%), LOSS=%d (%.1f%%)",
                   win_count, win_count/(win_count+loss_count)*100,
                   loss_count, loss_count/(win_count+loss_count)*100)
        logger.info("✅ Теперь можно переобучить модель: python3 train_lightgbm_models.py")


if __name__ == "__main__":
    main()

