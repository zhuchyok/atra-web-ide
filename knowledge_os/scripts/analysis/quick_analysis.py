#!/usr/bin/env python3
import glob
import os
import re

log_files = glob.glob("bot_restart_*.log")
if log_files:
    latest = max(log_files, key=lambda x: os.path.getmtime(x))
    print(f"📊 Анализ: {latest}")

    with open(latest, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    recent = lines[-50000:]
    print(f"   Анализируем последние {len(recent):,} строк")
    print()

    # Поиск блокировок
    blocks = []
    for line in recent:
        if any(k in line.lower() for k in ["🚫", "блок", "отклонен", "rejected"]):
            blocks.append(line)

    print(f"🔴 Всего блокировок: {len(blocks)}")
    print()

    # Статистика по причинам
    reasons = {
        "direction": 0,
        "quality": 0,
        "rsi": 0,
        "mtf": 0,
        "btc": 0,
        "volume": 0,
        "anomaly": 0,
        "breakout": 0,
    }

    for block in blocks:
        bl = block.lower()
        if "direction" in bl or "confidence" in bl:
            reasons["direction"] += 1
        if "quality" in bl:
            reasons["quality"] += 1
        if "rsi" in bl:
            reasons["rsi"] += 1
        if "mtf" in bl:
            reasons["mtf"] += 1
        if "btc" in bl:
            reasons["btc"] += 1
        if "volume" in bl:
            reasons["volume"] += 1
        if "аномали" in bl:
            reasons["anomaly"] += 1
        if "breakout" in bl:
            reasons["breakout"] += 1

    print("📊 Причины блокировок:")
    for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            pct = (count / len(blocks) * 100) if blocks else 0
            print(f"  {reason:12s} {count:5d} ({pct:5.1f}%)")
    print()

    # Последние блокировки
    if blocks:
        print("🔍 Последние 20 блокировок:")
        for block in blocks[-20:]:
            time_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", block)
            time_str = time_match.group(1) if time_match else "N/A"
            symbol_match = re.search(r"\[([A-Z]{2,10}USDT)\]", block)
            symbol = symbol_match.group(1) if symbol_match else "UNKNOWN"
            print(f"  [{time_str}] {symbol:12s} {block.strip()[:100]}")
    print()

    # Pipeline Statistics
    pipeline_lines = [i for i, line in enumerate(recent) if "PIPELINE STATISTICS" in line]
    if pipeline_lines:
        idx = pipeline_lines[-1]
        print("📈 Последняя статистика pipeline:")
        for i in range(idx, min(idx + 15, len(recent))):
            print(f"  {recent[i].strip()}")
    else:
        print("⚠️  PIPELINE STATISTICS не найдены")

    print()
    print("=" * 70)
