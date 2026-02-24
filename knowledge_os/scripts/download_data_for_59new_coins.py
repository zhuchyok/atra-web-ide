#!/usr/bin/env python3
"""
Загрузка исторических данных для новых 59 монет (топ 101-159)
Простой скрипт с использованием urllib
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# Новые 59 монет (топ 101-159)
NEW_COINS = [
    # Топ 101-110: Мемкоины и популярные альткоины
    "WIFUSDT",
    "BONKUSDT",
    "FLOKIUSDT",
    "BOMEUSDT",
    "SHIBUSDT",
    "1000SHIBUSDT",
    "JUPUSDT",
    "WLDUSDT",
    "SEIUSDT",
    "TIAUSDT",
    # Топ 111-120: Layer 2 и DeFi протоколы
    "ARBUSDT",
    "OPUSDT",
    "MATICUSDT",
    "GRTUSDT",
    "BALUSDT",
    "CRVUSDT",
    "SUSHIUSDT",
    "1INCHUSDT",
    "ENSUSDT",
    "LDOUSDT",
    # Топ 121-130: Инфраструктурные и утилитарные токены
    "ATOMUSDT",
    "INJUSDT",
    "APTUSDT",
    "TWTUSDT",
    "HBARUSDT",
    "STXUSDT",
    "FILUSDT",
    "LUNCUSDT",
    "LUNAUSDT",
    "USTCUSDT",
    # Топ 131-140: Exchange токены и стейкинг
    "CAKEUSDT",
    "GTUSDT",
    "JTOUSDT",
    "PYTHUSDT",
    "RUNEUSDT",
    "KASUSDT",
    "WOOUSDT",
    "IDUSDT",
    "ARKMUSDT",
    "AGIXUSDT",
    # Топ 141-150: AI и новые протоколы
    "FETUSDT",
    "AIUSDT",
    "PHBUSDT",
    "XAIUSDT",
    "NMRUSDT",
    "OCEANUSDT",
    "VGXUSDT",
    "ARDRUSDT",
    "ARKUSDT",
    "API3USDT",
    # Топ 151-159: Разное
    "BANDUSDT",
    "BLZUSDT",
    "CTSIUSDT",
    "CTXCUSDT",
    "DATAUSDT",
    "DCRUSDT",
    "DOCKUSDT",
    "DGBUSDT",
    "ELFUSDT",
    "PORTALUSDT",
    "PENDLEUSDT",
    "PIXELUSDT",
]

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "backtest_data_yearly"
DAYS = 365  # 1 год
INTERVAL = "1h"  # 1-часовые свечи


def fetch_binance_data(symbol: str, days: int = 365) -> pd.DataFrame:
    """Загружает исторические данные с Binance"""
    try:
        # Для 1 года нужно загрузить несколько батчей (лимит 1000 свечей)
        all_data = []

        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        current_end = int(end_time.timestamp() * 1000)
        start_ms = int(start_time.timestamp() * 1000)
        batch = 0
        max_batches = 200  # Достаточно для года

        print(f"  📥 Загрузка {symbol} с Binance...")

        while current_end > start_ms and batch < max_batches:
            # Каждый батч - ~8 дней (200 свечей * 1 час)
            current_start = current_end - (8 * 24 * 3600 * 1000)
            if current_start < start_ms:
                current_start = start_ms

            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": INTERVAL,
                "startTime": current_start,
                "endTime": current_end,
                "limit": 1000,
            }

            query_string = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_string}"

            req = urllib.request.Request(full_url)
            req.add_header("User-Agent", "Mozilla/5.0")

            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    if response.status != 200:
                        print(f"  ⚠️ HTTP {response.status} для {symbol}")
                        break

                    data = json.loads(response.read().decode())

                    if not data:
                        break

                    all_data.extend(data)
                    current_end = current_start - 1
                    batch += 1

                    # Rate limiting
                    time.sleep(0.1)

            except Exception as e:
                print(f"  ⚠️ Ошибка запроса для {symbol}: {e}")
                break

        if not all_data:
            print(f"  ❌ Нет данных для {symbol}")
            return None

        # Конвертируем в DataFrame
        df = pd.DataFrame(
            all_data,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )

        # Конвертируем типы
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Оставляем нужные колонки
        df = df[["open_time", "open", "high", "low", "close", "volume"]]
        df.set_index("open_time", inplace=True)

        # Удаляем дубликаты и сортируем
        df = df[~df.index.duplicated(keep="first")]
        df.sort_index(inplace=True)

        return df

    except Exception as e:
        print(f"  ❌ Ошибка при загрузке {symbol}: {e}")
        return None


def main():
    """Основная функция"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("📥 ЗАГРУЗКА ДАННЫХ ДЛЯ НОВЫХ 59 МОНЕТ (топ 101-159)")
    print("=" * 80)
    print()

    downloaded = 0
    skipped = 0
    failed = 0

    for i, symbol in enumerate(NEW_COINS, 1):
        csv_path = OUTPUT_DIR / f"{symbol}.csv"

        # Пропускаем, если уже есть
        if csv_path.exists():
            df_existing = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            if len(df_existing) > 5000:  # Есть достаточное количество данных
                print(f"[{i}/{len(NEW_COINS)}] ⏭️  {symbol} - уже есть ({len(df_existing)} свечей)")
                skipped += 1
                continue

        print(f"[{i}/{len(NEW_COINS)}] 📥 {symbol}...")

        df = fetch_binance_data(symbol, days=DAYS)

        if df is not None and len(df) > 100:
            df.to_csv(csv_path)
            print(f"      ✅ Сохранено: {len(df)} свечей")
            downloaded += 1
        else:
            print("      ❌ Недостаточно данных или ошибка")
            failed += 1

        # Rate limiting между монетами
        time.sleep(0.5)
        print()

    print("=" * 80)
    print("📊 ИТОГИ:")
    print(f"   ✅ Загружено: {downloaded}")
    print(f"   ⏭️  Пропущено: {skipped}")
    print(f"   ❌ Ошибок: {failed}")
    print("=" * 80)


if __name__ == "__main__":
    main()
