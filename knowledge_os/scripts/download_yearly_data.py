#!/usr/bin/env python3

"""
Загрузка исторических данных за год с Binance
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent.parent))

from data.historical_data_loader import HistoricalDataLoader

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "backtest_data_yearly"
DAYS = 365  # 1 год
TOP_SYMBOLS_LIMIT = 20  # Топ-20 монет по объему


async def main():
    print("=" * 80)
    print("📥 ЗАГРУЗКА ГОДОВЫХ ДАННЫХ С BINANCE (TOP-20)")
    print("=" * 80)
    print(f"\n📊 Топ монет: {TOP_SYMBOLS_LIMIT}")
    print(f"📅 Период: {DAYS} дней (~ {DAYS / 30:.1f} месяцев)")
    print(f"💾 Папка: {OUTPUT_DIR}\n")

    async with HistoricalDataLoader(exchange="binance") as loader:
        # Получаем топ символы автоматически
        print("🔍 Получение топ символов с Binance...")
        symbols = await loader.get_top_symbols(limit=TOP_SYMBOLS_LIMIT)
        print(f"✅ Получено {len(symbols)} символов")
        print(f"   {', '.join(symbols[:15])}...")

        print("\n🔄 Загрузка данных...\n")

        # Загружаем данные для всех символов
        data = await loader.load_multiple_symbols(symbols=symbols, interval="1h", days=DAYS)

        # Сохраняем в CSV
        loader.save_to_csv(data, OUTPUT_DIR)

        print("\n" + "=" * 80)
        print("✅ ЗАГРУЗКА ЗАВЕРШЕНА")
        print("=" * 80)

        # Статистика
        for symbol, df in data.items():
            if not df.empty:
                days_actual = (df.index[-1] - df.index[0]).days
                print(f"{symbol:12} | {len(df):6} свечей | {days_actual:3} дней")

        print(f"\n💾 Данные сохранены в: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
