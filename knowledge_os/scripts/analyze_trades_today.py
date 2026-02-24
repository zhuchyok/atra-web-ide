#!/usr/bin/env python3
"""
Анализ сделок за сегодня
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "trading.db"


def analyze_trades_today() -> Dict[str, Any]:
    """Анализирует сделки за сегодня"""

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # Проверяем наличие таблицы trades
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='trades'
        """)
        if not cursor.fetchone():
            print("⚠️ Таблица trades не найдена в базе данных")
            return {"error": "Таблица trades не найдена"}

        # Получаем сделки за сегодня
        cursor = conn.execute("""
            SELECT
                symbol,
                direction,
                entry_price,
                exit_price,
                net_pnl_usd,
                pnl_percent,
                entry_time,
                exit_time,
                exit_reason,
                user_id
            FROM trades
            WHERE date(entry_time) = date('now')
            ORDER BY entry_time DESC
        """)

        trades = [dict(row) for row in cursor.fetchall()]

        # Если нет сделок за сегодня, проверяем вчера
        if not trades:
            cursor = conn.execute("""
                SELECT
                    symbol,
                    direction,
                    entry_price,
                    exit_price,
                    net_pnl_usd,
                    pnl_percent,
                    entry_time,
                    exit_time,
                    exit_reason,
                    user_id
                FROM trades
                WHERE date(entry_time) = date('now', '-1 day')
                ORDER BY entry_time DESC
            """)
            trades = [dict(row) for row in cursor.fetchall()]
            if trades:
                print(f"📅 Сделок за сегодня нет. Анализирую вчерашние сделки ({yesterday})")

        # Если все еще нет, берем последние 20 сделок
        if not trades:
            cursor = conn.execute("""
                SELECT
                    symbol,
                    direction,
                    entry_price,
                    exit_price,
                    net_pnl_usd,
                    pnl_percent,
                    entry_time,
                    exit_time,
                    exit_reason,
                    user_id
                FROM trades
                WHERE exit_time IS NOT NULL
                ORDER BY entry_time DESC
                LIMIT 20
            """)
            trades = [dict(row) for row in cursor.fetchall()]
            if trades:
                latest_date = (
                    datetime.fromisoformat(trades[0]["entry_time"]).date()
                    if trades[0].get("entry_time")
                    else today
                )
                print(
                    f"📅 Сделок за сегодня нет. Анализирую последние сделки (последняя: {latest_date})"
                )

        if not trades:
            print("❌ Сделок не найдено в базе данных")
            conn.close()
            return {"error": "Сделки не найдены"}

        # Анализ
        total_trades = len(trades)
        winners = [t for t in trades if t.get("net_pnl_usd", 0) > 0]
        losers = [t for t in trades if t.get("net_pnl_usd", 0) <= 0]

        total_pnl = sum(t.get("net_pnl_usd", 0) for t in trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0

        # По символам
        symbol_stats = {}
        for trade in trades:
            symbol = trade.get("symbol", "UNKNOWN")
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {"count": 0, "winners": 0, "total_pnl": 0.0, "avg_pnl": 0.0}
            symbol_stats[symbol]["count"] += 1
            pnl = trade.get("net_pnl_usd", 0)
            symbol_stats[symbol]["total_pnl"] += pnl
            if pnl > 0:
                symbol_stats[symbol]["winners"] += 1

        for symbol in symbol_stats:
            stats = symbol_stats[symbol]
            stats["avg_pnl"] = stats["total_pnl"] / stats["count"]
            stats["win_rate"] = (
                (stats["winners"] / stats["count"] * 100) if stats["count"] > 0 else 0
            )

        # По направлениям
        direction_stats = {
            "LONG": {"count": 0, "winners": 0, "total_pnl": 0.0},
            "SHORT": {"count": 0, "winners": 0, "total_pnl": 0.0},
        }

        for trade in trades:
            direction = trade.get("direction", "").upper()
            if direction in direction_stats:
                direction_stats[direction]["count"] += 1
                pnl = trade.get("net_pnl_usd", 0)
                direction_stats[direction]["total_pnl"] += pnl
                if pnl > 0:
                    direction_stats[direction]["winners"] += 1

        # По причинам закрытия
        exit_reason_stats = {}
        for trade in trades:
            reason = trade.get("exit_reason", "unknown")
            if reason not in exit_reason_stats:
                exit_reason_stats[reason] = {"count": 0, "total_pnl": 0.0}
            exit_reason_stats[reason]["count"] += 1
            exit_reason_stats[reason]["total_pnl"] += trade.get("net_pnl_usd", 0)

        # Лучшие и худшие сделки
        best_trade = max(trades, key=lambda t: t.get("net_pnl_usd", 0), default=None)
        worst_trade = min(trades, key=lambda t: t.get("net_pnl_usd", 0), default=None)

        conn.close()

        result = {
            "date": today.isoformat(),
            "total_trades": total_trades,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(avg_pnl, 2),
            "symbol_stats": symbol_stats,
            "direction_stats": direction_stats,
            "exit_reason_stats": exit_reason_stats,
            "best_trade": dict(best_trade) if best_trade else None,
            "worst_trade": dict(worst_trade) if worst_trade else None,
            "trades": trades[:20],  # Последние 20 сделок
        }

        return result

    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        import traceback

        traceback.print_exc()
        return {"error": str(e)}


def print_analysis(result: Dict[str, Any]):
    """Выводит анализ в консоль"""

    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print("\n" + "=" * 80)
    print(f"📊 АНАЛИЗ СДЕЛОК ЗА {result['date']}")
    print("=" * 80)

    print("\n📈 ОБЩАЯ СТАТИСТИКА:")
    print(f"  Всего сделок: {result['total_trades']}")
    print(f"  ✅ Прибыльных: {result['winners']} ({result['win_rate']:.1f}%)")
    print(f"  ❌ Убыточных: {result['losers']}")
    print(f"  💰 Общий PnL: {result['total_pnl']:.2f} USDT")
    print(f"  📊 Средний PnL: {result['avg_pnl']:.2f} USDT")

    if result.get("best_trade"):
        best = result["best_trade"]
        print("\n🏆 ЛУЧШАЯ СДЕЛКА:")
        print(f"  Символ: {best.get('symbol')}")
        print(f"  Направление: {best.get('direction')}")
        print(f"  PnL: {best.get('net_pnl_usd', 0):.2f} USDT ({best.get('pnl_percent', 0):.2f}%)")
        print(f"  Вход: {best.get('entry_price')} | Выход: {best.get('exit_price')}")
        print(f"  Причина закрытия: {best.get('exit_reason', 'unknown')}")

    if result.get("worst_trade"):
        worst = result["worst_trade"]
        print("\n📉 ХУДШАЯ СДЕЛКА:")
        print(f"  Символ: {worst.get('symbol')}")
        print(f"  Направление: {worst.get('direction')}")
        print(f"  PnL: {worst.get('net_pnl_usd', 0):.2f} USDT ({worst.get('pnl_percent', 0):.2f}%)")
        print(f"  Вход: {worst.get('entry_price')} | Выход: {worst.get('exit_price')}")
        print(f"  Причина закрытия: {worst.get('exit_reason', 'unknown')}")

    if result.get("symbol_stats"):
        print("\n📊 ПО СИМВОЛАМ:")
        sorted_symbols = sorted(
            result["symbol_stats"].items(), key=lambda x: x[1]["total_pnl"], reverse=True
        )
        for symbol, stats in sorted_symbols[:10]:
            print(f"  {symbol}:")
            print(
                f"    Сделок: {stats['count']} | Прибыльных: {stats['winners']} ({stats['win_rate']:.1f}%)"
            )
            print(f"    PnL: {stats['total_pnl']:.2f} USDT | Средний: {stats['avg_pnl']:.2f} USDT")

    if result.get("direction_stats"):
        print("\n📊 ПО НАПРАВЛЕНИЯМ:")
        for direction, stats in result["direction_stats"].items():
            if stats["count"] > 0:
                win_rate = (stats["winners"] / stats["count"] * 100) if stats["count"] > 0 else 0
                print(f"  {direction}:")
                print(
                    f"    Сделок: {stats['count']} | Прибыльных: {stats['winners']} ({win_rate:.1f}%)"
                )
                print(f"    PnL: {stats['total_pnl']:.2f} USDT")

    if result.get("exit_reason_stats"):
        print("\n📊 ПО ПРИЧИНАМ ЗАКРЫТИЯ:")
        sorted_reasons = sorted(
            result["exit_reason_stats"].items(), key=lambda x: x[1]["count"], reverse=True
        )
        for reason, stats in sorted_reasons:
            print(f"  {reason}:")
            print(f"    Количество: {stats['count']} | PnL: {stats['total_pnl']:.2f} USDT")

    if result.get("trades"):
        print(
            f"\n📋 ПОСЛЕДНИЕ СДЕЛКИ (показано {len(result['trades'])} из {result['total_trades']}):"
        )
        for i, trade in enumerate(result["trades"][:10], 1):
            pnl = trade.get("net_pnl_usd", 0)
            pnl_sign = "✅" if pnl > 0 else "❌" if pnl < 0 else "➖"
            print(
                f"  {i}. {pnl_sign} {trade.get('symbol')} {trade.get('direction')} | "
                f"PnL: {pnl:.2f} USDT ({trade.get('pnl_percent', 0):.2f}%) | "
                f"Выход: {trade.get('exit_reason', 'unknown')}"
            )

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    result = analyze_trades_today()
    print_analysis(result)
