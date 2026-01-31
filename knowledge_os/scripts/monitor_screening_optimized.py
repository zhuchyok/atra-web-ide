#!/usr/bin/env python3
"""
Мониторинг прогресса повторного скрининга с оптимизированными параметрами
"""

import json
import time
from pathlib import Path
from datetime import datetime

from src.shared.utils.datetime_utils import get_utc_now

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = Path("/tmp/screening_optimized.log")
REPORT_DIR = PROJECT_ROOT / "data" / "reports"

def monitor_progress():
    """Мониторит прогресс скрининга"""
    print("🔍 Мониторинг повторного скрининга с оптимизированными параметрами...")
    print("="*80)
    
    last_size = 0
    last_lines = []
    
    while True:
        if LOG_FILE.exists():
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Показываем новые строки
            if len(lines) > last_size:
                new_lines = lines[last_size:]
                for line in new_lines:
                    line = line.strip()
                    if line:
                        print(f"[{get_utc_now().strftime('%H:%M:%S')}] {line}")
                last_size = len(lines)
                last_lines = lines[-10:]  # Последние 10 строк
        
        # Проверяем наличие результатов
        json_files = sorted(REPORT_DIR.glob("correlation_groups_screening_*.json"), reverse=True)
        if json_files:
            latest_file = json_files[0]
            file_time = datetime.fromtimestamp(latest_file.stat().st_mtime)
            if (get_utc_now() - file_time).total_seconds() < 60:  # Файл обновлялся в последнюю минуту
                try:
                    with open(latest_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    if "top5_by_group" in data:
                        print("\n" + "="*80)
                        print("✅ СКРИНИНГ ЗАВЕРШЕН!")
                        print("="*80)
                        
                        # Показываем результаты
                        for group, results in data["top5_by_group"].items():
                            if results:
                                print(f"\n📊 {group}: {len(results)} монет")
                                for r in results[:5]:
                                    print(
                                        f"  {r['symbol']:12s} | "
                                        f"WR: {r['win_rate']:5.2f}% | "
                                        f"PF: {r['profit_factor']:5.2f} | "
                                        f"PnL: {r['total_pnl']:8.2f} USDT"
                                    )
                        
                        return
                except Exception as e:
                    pass
        
        time.sleep(5)

if __name__ == "__main__":
    try:
        monitor_progress()
    except KeyboardInterrupt:
        print("\n\n⏹️ Мониторинг остановлен")

