#!/usr/bin/env python3
"""
Мониторинг прогресса массового скрининга
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check_screening_progress():
    """Проверяет прогресс скрининга"""
    reports_dir = PROJECT_ROOT / "data" / "reports"

    # Ищем последние файлы результатов
    json_files = list(reports_dir.glob("correlation_groups_screening_*.json"))
    csv_files = list(reports_dir.glob("correlation_groups_top5_*.csv"))

    if json_files:
        latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
        print(f"📊 Последний JSON отчет: {latest_json.name}")
        print(f"   Время создания: {datetime.fromtimestamp(latest_json.stat().st_mtime)}")

        try:
            with open(latest_json, encoding="utf-8") as f:
                data = json.load(f)

            print("\n✅ Результаты скрининга:")
            print(f"   Всего символов: {data.get('screening_info', {}).get('total_symbols', 0)}")
            print(f"   Период: {data.get('screening_info', {}).get('period_days', 0)} дней")

            top5_by_group = data.get("top5_by_group", {})
            for group_name in ["BTC_HIGH", "ETH_HIGH", "SOL_HIGH"]:
                top5 = top5_by_group.get(group_name, [])
                print(f"\n   {group_name}: {len(top5)} монет")
                for idx, coin in enumerate(top5[:5], 1):
                    print(
                        f"      {idx}. {coin.get('symbol', 'N/A'):12s} | "
                        f"WR: {coin.get('win_rate', 0):5.2f}% | "
                        f"PF: {coin.get('profit_factor', 0):5.2f} | "
                        f"PnL: {coin.get('total_pnl_pct', 0):7.2f}%"
                    )
        except Exception as e:
            print(f"⚠️ Ошибка чтения JSON: {e}")

    if csv_files:
        latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
        print(f"\n📊 Последний CSV отчет: {latest_csv.name}")
        print(f"   Время создания: {datetime.fromtimestamp(latest_csv.stat().st_mtime)}")

    if not json_files and not csv_files:
        print("⏳ Скрининг еще не завершен или не начат")
        print("   Проверьте процесс: ps aux | grep mass_screening")


if __name__ == "__main__":
    check_screening_progress()
