#!/usr/bin/env python3
"""
Скрипт для показа последних сигналов из базы данных
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd


def get_recent_signals(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Получение последних сигналов из базы данных

    Args:
        limit: Количество сигналов для показа

    Returns:
        List[Dict]: Список сигналов
    """
    try:
        # Подключение к базе данных
        conn = sqlite3.connect("trading.db")
        cursor = conn.cursor()

        print(f"🔍 Поиск последних {limit} сигналов")
        print("=" * 80)

        # Запрос последних сигналов
        query = """
        SELECT
            id,
            symbol,
            entry as price,
            stop as sl,
            tp1,
            tp2,
            entry_time,
            exit_time,
            result as status,
            net_profit,
            leverage_used as leverage,
            risk_pct_used as risk_pct,
            quality_score,
            quality_meta,
            created_at,
            user_id
        FROM signals_log
        ORDER BY created_at DESC
        LIMIT ?
        """

        cursor.execute(query, (limit,))
        signals = cursor.fetchall()

        # Получение колонок
        columns = [description[0] for description in cursor.description]

        # Преобразование в список словарей
        signals_list = []
        for signal in signals:
            signal_dict = dict(zip(columns, signal))
            signals_list.append(signal_dict)

        conn.close()

        return signals_list

    except Exception as e:
        print(f"❌ Ошибка получения сигналов: {e}")
        return []


def display_signals(signals: List[Dict[str, Any]]):
    """
    Отображение сигналов в удобном формате

    Args:
        signals: Список сигналов
    """
    if not signals:
        print("📭 Сигналов не найдено")
        return

    print(f"📊 Найдено сигналов: {len(signals)}")
    print("=" * 80)

    for i, signal in enumerate(signals, 1):
        print(f"\n🔹 Сигнал #{i}")
        print(f"   ID: {signal['id']}")
        print(f"   Символ: {signal['symbol']}")
        print(f"   Цена входа: {signal['price']}")
        print(f"   Пользователь: {signal['user_id']}")
        print(f"   Время создания: {signal['created_at']}")
        print(f"   Время входа: {signal['entry_time']}")
        if signal["exit_time"]:
            print(f"   Время выхода: {signal['exit_time']}")
        print(f"   Результат: {signal['status']}")

        if signal["tp1"]:
            print(f"   TP1: {signal['tp1']}")
        if signal["tp2"]:
            print(f"   TP2: {signal['tp2']}")
        if signal["sl"]:
            print(f"   SL: {signal['sl']}")

        if signal["net_profit"]:
            profit_emoji = "💰" if signal["net_profit"] > 0 else "📉"
            print(f"   {profit_emoji} Прибыль: {signal['net_profit']:.4f}")

        if signal["risk_pct"]:
            print(f"   Риск: {signal['risk_pct']}%")
        if signal["leverage"]:
            print(f"   Плечо: {signal['leverage']}x")

        if signal["quality_score"]:
            print(f"   Качество: {signal['quality_score']:.2f}")

        # Парсинг quality_meta для AI метрик
        if signal["quality_meta"]:
            try:
                meta = json.loads(signal["quality_meta"])
                if "tech" in meta:
                    tech = meta["tech"]
                    if "rsi" in tech:
                        print(f"   RSI: {tech['rsi']:.2f}")
                    if "macd_status" in tech:
                        print(f"   MACD: {tech['macd_status']}")
                    if "ema_status" in tech:
                        print(f"   EMA: {tech['ema_status']}")
                    if "volume_status" in tech:
                        print(f"   Объем: {tech['volume_status']}")
                    if "bb_position" in tech:
                        print(f"   BB позиция: {tech['bb_position']}")

                if "btc_trend" in meta:
                    print(f"   BTC тренд: {'✅' if meta['btc_trend'] else '❌'}")
                if "eth_trend" in meta:
                    print(f"   ETH тренд: {'✅' if meta['eth_trend'] else '❌'}")
                if "fgi" in meta:
                    print(f"   FGI: {meta['fgi']}")
                if "anomaly_circles" in meta:
                    print(f"   Аномалии: {meta['anomaly_circles']}")
            except:
                pass

        print("-" * 40)


def get_signals_statistics(signals: List[Dict[str, Any]]):
    """
    Получение статистики по сигналам

    Args:
        signals: Список сигналов
    """
    if not signals:
        return

    print("\n📈 СТАТИСТИКА СИГНАЛОВ")
    print("=" * 50)

    # Общая статистика
    total_signals = len(signals)
    print(f"Всего сигналов: {total_signals}")

    # Статистика по результатам
    result_counts = {}
    for signal in signals:
        result = signal["status"] or "unknown"
        result_counts[result] = result_counts.get(result, 0) + 1

    print("\nРезультаты торговли:")
    for result, count in result_counts.items():
        percentage = (count / total_signals) * 100
        print(f"  {result}: {count} ({percentage:.1f}%)")

    # Статистика по символам
    symbol_counts = {}
    for signal in signals:
        symbol = signal["symbol"]
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

    print("\nТоп-5 символов:")
    sorted_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)
    for symbol, count in sorted_symbols[:5]:
        percentage = (count / total_signals) * 100
        print(f"  {symbol}: {count} ({percentage:.1f}%)")

    # Статистика по прибыли
    profitable_signals = [s for s in signals if s["net_profit"] and s["net_profit"] > 0]
    losing_signals = [s for s in signals if s["net_profit"] and s["net_profit"] < 0]

    if profitable_signals or losing_signals:
        total_profit = sum(s["net_profit"] for s in signals if s["net_profit"])
        avg_profit = (
            total_profit / len([s for s in signals if s["net_profit"]])
            if any(s["net_profit"] for s in signals)
            else 0
        )

        print("\n💰 Финансовая статистика:")
        print(f"  Прибыльных сигналов: {len(profitable_signals)}")
        print(f"  Убыточных сигналов: {len(losing_signals)}")
        print(f"  Общая прибыль: {total_profit:.4f}")
        print(f"  Средняя прибыль: {avg_profit:.4f}")

        if profitable_signals:
            max_profit = max(s["net_profit"] for s in profitable_signals)
            print(f"  Максимальная прибыль: {max_profit:.4f}")

        if losing_signals:
            max_loss = min(s["net_profit"] for s in losing_signals)
            print(f"  Максимальный убыток: {max_loss:.4f}")

    # Временная статистика
    if signals:
        first_signal = min(signals, key=lambda x: x["created_at"])
        last_signal = max(signals, key=lambda x: x["created_at"])

        print("\n⏰ Временной диапазон:")
        print(f"  Первый сигнал: {first_signal['created_at']}")
        print(f"  Последний сигнал: {last_signal['created_at']}")


def main():
    """Основная функция"""
    print("🔍 ПОКАЗ ПОСЛЕДНИХ СИГНАЛОВ")
    print("=" * 60)

    # Получение последних 20 сигналов
    signals = get_recent_signals(20)

    # Отображение сигналов
    display_signals(signals)

    # Статистика
    get_signals_statistics(signals)

    print("\n✅ Анализ завершен!")


if __name__ == "__main__":
    main()
