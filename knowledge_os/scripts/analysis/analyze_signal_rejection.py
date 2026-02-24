#!/usr/bin/env python3
"""
Детальный анализ блокировок сигналов из логов
"""

import glob
import os
import re
from collections import defaultdict
from datetime import datetime


def analyze_signal_blocks():
    """Анализ блокировок сигналов из последнего лог файла"""

    # Находим последний лог файл
    log_files = glob.glob("bot_restart_*.log")
    if not log_files:
        print("❌ Лог файлы не найдены")
        return

    latest_log = max(log_files, key=lambda x: os.path.getmtime(x))
    print(f"📊 Анализ лог файла: {latest_log}")
    print(f"   Размер: {os.path.getsize(latest_log) / 1024 / 1024:.2f} MB")
    print("")

    # Счетчики блокировок
    block_reasons = defaultdict(int)
    stage_blocks = defaultdict(int)
    symbol_blocks = defaultdict(lambda: {"total": 0, "blocks": 0, "reasons": defaultdict(int)})

    # Паттерны блокировок
    patterns = {
        "Direction Check": re.compile(
            r"Direction.*confidence|Direction Check|не.*подтвержд|2/4|3/4", re.I
        ),
        "Quality Score": re.compile(
            r"Quality.*Score|quality.*score|качество.*сигнала|0\.\d+.*quality", re.I
        ),
        "RSI Warning": re.compile(
            r"RSI.*Warning|RSI.*блок|RSI.*65|RSI.*35|RSI.*>.*65|RSI.*<.*35", re.I
        ),
        "MTF Confirmation": re.compile(
            r"MTF.*Confirmation|MTF.*блок|мультитаймфрейм|H4.*тренд", re.I
        ),
        "BTC Alignment": re.compile(
            r"BTC.*alignment|BTC.*тренд|BTC.*блок|BTC.*не.*подтвержд", re.I
        ),
        "Anomaly Filter": re.compile(r"аномали|anomaly|кружков|риск.*не.*приемлем", re.I),
        "False Breakout": re.compile(r"False.*Breakout|ложный.*пробой|breakout.*rejected", re.I),
        "Volume Filter": re.compile(r"Volume.*filter|объем.*фильтр|volume.*low", re.I),
        "Liquidity": re.compile(r"ликвидность|liquidity|depth.*low", re.I),
    }

    try:
        with open(latest_log, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        print(f"   Всего строк: {len(lines):,}")
        print(f"   Анализируем последние {min(50000, len(lines)):,} строк")
        print("")

        # Анализируем последние 50000 строк
        recent_lines = lines[-50000:] if len(lines) > 50000 else lines

        # Поиск блокировок
        block_count = 0
        for i, line in enumerate(recent_lines):
            line_lower = line.lower()

            # Ищем блокировки
            is_block = False
            reason = None

            if any(
                keyword in line_lower
                for keyword in [
                    "блок",
                    "отклонен",
                    "отклонён",
                    "rejected",
                    "blocked",
                    "не пройден",
                    "🚫",
                ]
            ):
                is_block = True
                block_count += 1

                # Определяем причину
                for reason_name, pattern in patterns.items():
                    if pattern.search(line):
                        reason = reason_name
                        block_reasons[reason_name] += 1
                        stage_blocks[reason_name] += 1
                        break

                # Извлекаем символ
                symbol_match = re.search(r"\[([A-Z]{2,10}USDT)\]|([A-Z]{2,10}USDT)", line)
                if symbol_match:
                    symbol = symbol_match.group(1) or symbol_match.group(2)
                    symbol_blocks[symbol]["total"] += 1
                    symbol_blocks[symbol]["blocks"] += 1
                    if reason:
                        symbol_blocks[symbol]["reasons"][reason] += 1

        # Поиск PIPELINE STATISTICS
        pipeline_stats = []
        for i, line in enumerate(recent_lines):
            if "PIPELINE STATISTICS" in line:
                # Собираем следующие 15 строк
                stats_block = []
                for j in range(i, min(i + 15, len(recent_lines))):
                    stats_block.append(recent_lines[j].strip())
                pipeline_stats.append("\n".join(stats_block))

        # Выводим отчет
        print("=" * 80)
        print("📊 АНАЛИЗ БЛОКИРОВОК СИГНАЛОВ")
        print("=" * 80)
        print("")

        print(f"🔍 Всего блокировок найдено: {block_count}")
        print("")

        if block_reasons:
            print("🔴 ПРИЧИНЫ БЛОКИРОВОК (по частоте):")
            print("-" * 80)
            total_blocks = sum(block_reasons.values())
            for reason, count in sorted(block_reasons.items(), key=lambda x: x[1], reverse=True):
                pct = (count / total_blocks * 100) if total_blocks > 0 else 0
                bar = "█" * int(pct / 2)
                print(f"  {reason:25s} {count:5d} ({pct:5.1f}%) {bar}")
            print("")
        else:
            print("⚠️  Блокировки не найдены в последних строках лога")
            print("")

        if symbol_blocks:
            print("🎯 СТАТИСТИКА ПО СИМВОЛАМ (топ-15):")
            print("-" * 80)
            sorted_symbols = sorted(
                symbol_blocks.items(), key=lambda x: x[1]["blocks"], reverse=True
            )[:15]
            for symbol, stats in sorted_symbols:
                block_rate = (stats["blocks"] / stats["total"] * 100) if stats["total"] > 0 else 0
                reasons_str = ", ".join(
                    [
                        f"{r}({c})"
                        for r, c in sorted(
                            stats["reasons"].items(), key=lambda x: x[1], reverse=True
                        )[:3]
                    ]
                )
                print(
                    f"  • {symbol:12s} {stats['total']:3d} попыток, {stats['blocks']:3d} блокировок ({block_rate:5.1f}%) - {reasons_str}"
                )
            print("")

        if pipeline_stats:
            print("📈 ПОСЛЕДНИЕ PIPELINE STATISTICS:")
            print("-" * 80)
            # Берем последнюю статистику
            last_stats = pipeline_stats[-1] if pipeline_stats else ""
            for line in last_stats.split("\n"):
                if line.strip():
                    print(f"  {line}")
            print("")
        else:
            print("⚠️  PIPELINE STATISTICS не найдены в логе")
            print("")

        # Поиск последних блокировок с деталями
        print("🔍 ПОСЛЕДНИЕ БЛОКИРОВКИ (топ-30):")
        print("-" * 80)
        recent_blocks = []
        for line in recent_lines[-2000:]:
            if any(
                keyword in line.lower()
                for keyword in ["блок", "отклонен", "rejected", "🚫", "не пройден"]
            ):
                time_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                time_str = time_match.group(1) if time_match else "N/A"
                symbol_match = re.search(r"\[([A-Z]{2,10}USDT)\]|([A-Z]{2,10}USDT)", line)
                symbol = (
                    symbol_match.group(1) or symbol_match.group(2) if symbol_match else "UNKNOWN"
                )

                # Определяем причину
                reason = "Unknown"
                for reason_name, pattern in patterns.items():
                    if pattern.search(line):
                        reason = reason_name
                        break

                recent_blocks.append((time_str, symbol, reason, line.strip()[:120]))

        for time_str, symbol, reason, msg in recent_blocks[-30:]:
            print(f"  [{time_str}] {symbol:12s} [{reason:20s}] {msg}")

        print("")
        print("=" * 80)

        # Рекомендации
        print("💡 РЕКОМЕНДАЦИИ:")
        print("-" * 80)
        if block_reasons:
            top_reason = max(block_reasons.items(), key=lambda x: x[1])
            print(f"  • Основная причина блокировок: {top_reason[0]} ({top_reason[1]} раз)")
            print(f"  • Рекомендуется проверить настройки фильтра: {top_reason[0]}")

        if not pipeline_stats:
            print("  • Статистика pipeline не выводится - проверьте настройки логирования")

        print("")
        print("=" * 80)

    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    analyze_signal_blocks()
