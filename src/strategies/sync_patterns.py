#!/usr/bin/env python3
"""
Скрипт для синхронизации паттернов из signals_log и переобучения LightGBM
Использует все доступные данные из signals_log
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List

from src.shared.utils.datetime_utils import get_utc_now

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_signals_from_db(db_path: str) -> List[Dict[str, Any]]:
    """Получает все сигналы из signals_log для синхронизации паттернов"""
    signals = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем все сигналы с минимальной информацией
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
                exit_time,
                quality_score,
                mtf_score
            FROM signals_log
            WHERE entry > 0
            ORDER BY created_at DESC
            LIMIT 1000
        """)

        rows = cursor.fetchall()
        logger.info("Найдено %d сигналов в signals_log", len(rows))

        for row in rows:
            (
                symbol,
                entry,
                tp1,
                tp2,
                stop,
                result,
                net_profit,
                created_at,
                exit_time,
                quality_score,
                mtf_score,
            ) = row

            # Определяем side по ценам
            side = "LONG" if tp1 and entry and tp1 > entry else "SHORT"

            # Определяем результат
            result_upper = str(result).upper() if result else ""
            if "TP2" in result_upper:
                result_status = "WIN"
                profit_pct = 4.0
            elif "TP1" in result_upper:
                result_status = "WIN"
                profit_pct = 2.0
            elif "SL" in result_upper and "BE" not in result_upper:
                result_status = "LOSS"
                profit_pct = -2.0
            elif "SL" in result_upper and "BE" in result_upper:
                result_status = "NEUTRAL"
                profit_pct = 0.0
            elif result_upper == "CLOSED" and net_profit:
                # Если закрыто вручную с прибылью
                if net_profit > 0:
                    result_status = "WIN"
                    if entry:
                        profit_pct = (net_profit / (entry * 100)) * 100  # Приблизительно
                    else:
                        profit_pct = 2.0
                elif net_profit < 0:
                    result_status = "LOSS"
                    if entry:
                        profit_pct = (net_profit / (entry * 100)) * 100
                    else:
                        profit_pct = -2.0
                else:
                    result_status = "NEUTRAL"
                    profit_pct = 0.0
            else:
                # PENDING/EXPIRED - помечаем как NEUTRAL (не используется для обучения)
                result_status = None
                profit_pct = None

            signals.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": float(entry) if entry else 0.0,
                    "tp1": float(tp1) if tp1 else 0.0,
                    "tp2": float(tp2) if tp2 else 0.0,
                    "stop": float(stop) if stop else 0.0,
                    "result": result_status,
                    "profit_pct": profit_pct,
                    "net_profit": float(net_profit) if net_profit else 0.0,
                    "created_at": created_at,
                    "exit_time": exit_time,
                    "quality_score": float(quality_score) if quality_score else 0.5,
                    "mtf_score": float(mtf_score) if mtf_score else 0.5,
                }
            )

        conn.close()
        return signals

    except Exception as e:
        logger.error("Ошибка чтения из БД: %s", e)
        return []


def create_patterns_from_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Создает паттерны из сигналов"""
    patterns = []

    for signal in signals:
        # Пропускаем сигналы без результата (PENDING/EXPIRED)
        if signal["result"] is None:
            continue

        pattern = {
            "symbol": signal["symbol"],
            "timestamp": signal["created_at"] or get_utc_now().isoformat(),
            "signal_type": signal["side"],
            "entry_price": signal["entry_price"],
            "tp1": signal["tp1"] if signal["tp1"] > 0 else signal["entry_price"] * 1.02,
            "tp2": signal["tp2"] if signal["tp2"] > 0 else signal["entry_price"] * 1.04,
            "risk_pct": 2.0,
            "leverage": 1.0,
            "indicators": {},  # Будет заполнено из исторических данных
            "market_conditions": {},
            "result": signal["result"],
            "profit_pct": signal["profit_pct"],
            "quality_score": signal["quality_score"],
            "mtf_score": signal["mtf_score"],
        }
        patterns.append(pattern)

    return patterns


def main():
    """Основная функция"""
    logger.info("🚀 Запуск синхронизации паттернов и переобучения...")

    db_path = "trading.db"
    patterns_file = "ai_learning_data/trading_patterns.json"

    # Загружаем сигналы из БД
    logger.info("📊 Загрузка сигналов из %s...", db_path)
    signals = get_signals_from_db(db_path)
    logger.info("Загружено %d сигналов", len(signals))

    # Создаем паттерны
    logger.info("🔄 Создание паттернов...")
    new_patterns = create_patterns_from_signals(signals)
    logger.info("Создано %d паттернов с результатами", len(new_patterns))

    # Проверяем распределение
    results_dist = {}
    for p in new_patterns:
        result = p.get("result")
        results_dist[result] = results_dist.get(result, 0) + 1
    logger.info("Распределение результатов: %s", results_dist)

    # Загружаем существующие паттерны
    existing_patterns = []
    if os.path.exists(patterns_file):
        with open(patterns_file, encoding="utf-8") as f:
            existing_patterns = json.load(f)
        logger.info("Загружено %d существующих паттернов", len(existing_patterns))

    # Объединяем паттерны (новые имеют приоритет)
    # Удаляем старые паттерны без результатов
    updated_patterns = []
    for p in existing_patterns:
        if p.get("result") in ("WIN", "LOSS"):
            updated_patterns.append(p)

    # Добавляем новые паттерны
    updated_patterns.extend(new_patterns)

    logger.info("Всего паттернов после обновления: %d", len(updated_patterns))

    # Проверяем баланс классов
    win_count = sum(1 for p in updated_patterns if p.get("result") == "WIN")
    loss_count = sum(1 for p in updated_patterns if p.get("result") == "LOSS")

    logger.info("WIN: %d, LOSS: %d", win_count, loss_count)

    if win_count == 0 or loss_count == 0:
        logger.warning("⚠️ Недостаточно данных для обучения (нужны оба класса)")
        logger.warning("WIN: %d, LOSS: %d", win_count, loss_count)
        logger.info("💡 Модель будет работать в fallback режиме до накопления данных")
    else:
        # Сохраняем паттерны (с ограничением количества бэкапов)
        if os.path.exists(patterns_file):
            import glob

            # Ограничиваем количество бэкапов - храним только последние 5
            backup_pattern = f"{patterns_file}.backup_*"
            existing_backups = glob.glob(backup_pattern)
            existing_backups.sort(key=os.path.getmtime, reverse=True)

            # Удаляем старые бэкапы (оставляем только последние 5)
            if len(existing_backups) >= 5:
                for old_backup in existing_backups[4:]:  # Оставляем 5, удаляем остальные
                    try:
                        os.remove(old_backup)
                        logger.debug(
                            "Удален старый бэкап паттернов: %s", os.path.basename(old_backup)
                        )
                    except Exception:
                        pass

            # Создаем новый бэкап только если прошло достаточно времени (минимум 6 часов)
            import time

            should_backup = True
            if existing_backups:
                last_backup_time = os.path.getmtime(existing_backups[0])
                hours_since_backup = (time.time() - last_backup_time) / 3600
                if hours_since_backup < 6:
                    should_backup = False
                    logger.debug(
                        "Пропускаем бэкап паттернов (последний был %.1f часов назад)",
                        hours_since_backup,
                    )

            if should_backup:
                backup_file = f"{patterns_file}.backup_{get_utc_now().strftime('%Y%m%d_%H%M%S')}"
                import shutil

                shutil.copy2(patterns_file, backup_file)
                logger.info("Создан backup: %s", backup_file)

        with open(patterns_file, "w", encoding="utf-8") as f:
            json.dump(updated_patterns, f, indent=2, ensure_ascii=False)
        logger.info("💾 Сохранено %d паттернов в %s", len(updated_patterns), patterns_file)

        # Переобучаем модель
        if win_count >= 50 and loss_count >= 50:  # Минимум для обучения
            logger.info("🔄 Запуск переобучения модели...")
            try:
                from lightgbm_predictor import get_lightgbm_predictor

                predictor = get_lightgbm_predictor()
                success = predictor.train_models()
                if success:
                    logger.info("✅ Модель успешно переобучена!")
                else:
                    logger.error("❌ Ошибка переобучения модели")
            except Exception as e:
                logger.error("❌ Ошибка переобучения модели: %s", e)
        else:
            logger.warning(
                "⚠️ Недостаточно данных для переобучения (нужно минимум 50 WIN и 50 LOSS)"
            )


if __name__ == "__main__":
    main()
