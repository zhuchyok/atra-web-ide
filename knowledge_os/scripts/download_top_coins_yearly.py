#!/usr/bin/env python3

"""
Загрузка годовых данных для топ монет с использованием фильтрации
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.shared.utils.datetime_utils import get_utc_now

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent.parent))

from pair_filtering import get_filtered_top_usdt_pairs_fast

from data.historical_data_loader import HistoricalDataLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "backtest_data_yearly"
DAYS = 365  # 1 год
TOP_N = 500  # Получаем топ-500 по объему
FINAL_LIMIT = 30  # Финальный лимит после фильтрации


async def main():
    print("=" * 80)
    print("📥 ЗАГРУЗКА ГОДОВЫХ ДАННЫХ ДЛЯ ТОП МОНЕТ")
    print("=" * 80)
    print(f"\n📊 Топ монет для анализа: {TOP_N}")
    print(f"📊 Финальный лимит: {FINAL_LIMIT}")
    print(f"📅 Период: {DAYS} дней (~ {DAYS / 30:.1f} месяцев)")
    print(f"💾 Папка: {OUTPUT_DIR}\n")

    # Получаем отфильтрованные монеты
    print("🔍 Получение и фильтрация топ монет...")
    symbols = await get_filtered_top_usdt_pairs_fast(top_n=TOP_N, final_limit=FINAL_LIMIT)

    if not symbols:
        print("❌ Не удалось получить список монет")
        return

    print(f"✅ Получено {len(symbols)} монет после фильтрации")
    print(f"   Топ-15: {', '.join(symbols[:15])}")
    print(f"   Всего: {', '.join(symbols)}\n")

    # Загружаем данные
    async with HistoricalDataLoader(exchange="binance") as loader:
        print("🔄 Загрузка данных...\n")

        end_time = get_utc_now()
        start_time = end_time - timedelta(days=DAYS)

        all_data = {}

        # Загружаем по одному символу
        for i, symbol in enumerate(symbols, 1):
            try:
                print(f"  [{i}/{len(symbols)}] Загрузка {symbol}...", end=" ")
                df = await loader.fetch_ohlcv(
                    symbol=symbol, interval="1h", start_time=start_time, end_time=end_time
                )

                if df is not None and not df.empty:
                    all_data[symbol] = df
                    days_actual = (df.index[-1] - df.index[0]).days
                    print(f"✅ {len(df)} свечей ({days_actual} дней)")
                else:
                    print("⚠️ Нет данных")

            except Exception as e:
                print(f"❌ Ошибка: {e}")

        # Сохраняем в CSV
        if all_data:
            print(f"\n💾 Сохранение данных в {OUTPUT_DIR}...")
            loader.save_to_csv(all_data, OUTPUT_DIR)

            print("\n" + "=" * 80)
            print("✅ ЗАГРУЗКА ЗАВЕРШЕНА")
            print("=" * 80)

            # Статистика
            print(f"\n📊 Загружено символов: {len(all_data)}")
            print("\n" + "-" * 60)
            print(f"{'Символ':<15} {'Свечей':>10} {'Дней':>10} {'Полнота':>10}")
            print("-" * 60)

            for symbol, df in sorted(all_data.items()):
                days_actual = (df.index[-1] - df.index[0]).days
                completeness = (days_actual / DAYS) * 100
                print(f"{symbol:<15} {len(df):>10} {days_actual:>10} {completeness:>9.1f}%")

            # Фильтруем монеты с недостаточными данными
            full_data_symbols = [
                s for s, df in all_data.items() if (df.index[-1] - df.index[0]).days >= 300
            ]
            print("\n" + "-" * 60)
            print(f"✅ Монет с полными данными (>300 дней): {len(full_data_symbols)}")
            print(f"   {', '.join(full_data_symbols)}")

            print(f"\n💾 Все данные сохранены в: {OUTPUT_DIR}")
        else:
            print("\n❌ Нет данных для сохранения")


if __name__ == "__main__":
    asyncio.run(main())
