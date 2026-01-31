#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка исторических данных для новых 50 монет (топ 51-100)
Простой скрипт с использованием requests
"""

import sys
import os
import time
import urllib.request
import urllib.parse
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from src.shared.utils.datetime_utils import get_utc_now

# Новые 50 монет (топ 51-100)
NEW_COINS = [
    # Топ 51-60: DeFi и L2
    "AAVEUSDT", "MKRUSDT", "COMPUSDT", "SNXUSDT", "YFIUSDT",
    "LRCUSDT", "STXUSDT", "DYDXUSDT", "GMXUSDT", "RDNTUSDT",
    # Топ 61-70: NFT и Metaverse
    "SANDUSDT", "MANAUSDT", "AXSUSDT", "ENJUSDT", "GALAUSDT",
    "IMXUSDT", "APEUSDT", "RENDERUSDT", "RNDRUSDT", "FLOWUSDT",
    # Топ 71-80: Layer 1 альтернативы
    "XLMUSDT", "ALGOUSDT", "VETUSDT", "THETAUSDT", "EOSUSDT",
    "XTZUSDT", "EGLDUSDT", "KLAYUSDT", "ROSEUSDT", "IOTXUSDT",
    # Топ 81-90: Privacy и старые монеты
    "COTIUSDT", "ONEUSDT", "IOTAUSDT", "QTUMUSDT", "XMRUSDT",
    "DASHUSDT", "ZRXUSDT", "BATUSDT", "NEOUSDT", "ONTUSDT",
    # Топ 91-100: Новые популярные
    "ZILUSDT", "CHZUSDT", "FTMUSDT", "HOTUSDT", "CELRUSDT",
    "DENTUSDT", "CELOUSDT", "KEEPUSDT", "C98USDT", "MASKUSDT"
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
        
        # Бинance лимит: 1000 свечей на запрос
        # За час: 1000 свечей = ~41 день
        # Для 365 дней нужно ~9 запросов
        
        current_end = end_time
        batch_count = 0
        max_batches = 15  # Максимум батчей
        
        while current_end > start_time and batch_count < max_batches:
            current_start = current_end - timedelta(days=41)  # ~41 день на батч
            
            url = "https://api.binance.com/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': INTERVAL,
                'startTime': int(current_start.timestamp() * 1000),
                'endTime': int(current_end.timestamp() * 1000),
                'limit': 1000
            }
            
            # Формируем URL с параметрами
            query_string = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_string}"
            
            req = urllib.request.Request(full_url)
            req.add_header('User-Agent', 'Mozilla/5.0')
            
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode())
                    
                    if data:
                        all_data.extend(data)
                        current_end = current_start
                        batch_count += 1
                        time.sleep(0.1)  # Задержка между запросами
                    else:
                        break
            except urllib.error.HTTPError as e:
                print(f"  ⚠️ Ошибка HTTP {e.code} для {symbol}: {e.reason}")
                break
            except Exception as e:
                print(f"  ⚠️ Ошибка запроса для {symbol}: {e}")
                break
        
        if not all_data:
            return pd.DataFrame()
        
        # Удаляем дубликаты по timestamp
        seen = set()
        unique_data = []
        for item in all_data:
            ts = item[0]
            if ts not in seen:
                seen.add(ts)
                unique_data.append(item)
        
        # Сортируем по времени
        unique_data.sort(key=lambda x: x[0])
        
        # Создаем DataFrame
        df = pd.DataFrame(unique_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Конвертируем типы
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.rename(columns={'timestamp': 'open_time'})
        df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
        df = df.sort_values('open_time').reset_index(drop=True)
        
        return df
        
    except Exception as e:
        print(f"  ❌ Ошибка для {symbol}: {e}")
        return pd.DataFrame()


def main():
    print("=" * 80)
    print("📥 ЗАГРУЗКА ГОДОВЫХ ДАННЫХ ДЛЯ НОВЫХ 50 МОНЕТ (топ 51-100)")
    print("=" * 80)
    print(f"\n📊 Монет для загрузки: {len(NEW_COINS)}")
    print(f"📅 Период: {DAYS} дней (~ {DAYS/30:.1f} месяцев)")
    print(f"💾 Папка: {OUTPUT_DIR}\n")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    failed = []
    
    for idx, symbol in enumerate(NEW_COINS, 1):
        print(f"[{idx}/{len(NEW_COINS)}] Загрузка {symbol}...", end=" ")
        
        df = fetch_binance_data(symbol, days=DAYS)
        
        if not df.empty:
            # Сохраняем в CSV
            csv_path = OUTPUT_DIR / f"{symbol}.csv"
            df.to_csv(csv_path)
            
            days_actual = (df.index[-1] - df.index[0]).days if len(df) > 1 else 0
            print(f"✅ {len(df)} свечей, {days_actual} дней")
            successful += 1
        else:
            print(f"❌ Нет данных")
            failed.append(symbol)
        
        # Небольшая задержка между монетами
        if idx < len(NEW_COINS):
            time.sleep(0.2)
    
    print("\n" + "=" * 80)
    print("✅ ЗАГРУЗКА ЗАВЕРШЕНА")
    print("=" * 80)
    print(f"\n✅ Успешно загружено: {successful}/{len(NEW_COINS)} монет")
    
    if failed:
        print(f"❌ Не загружено: {len(failed)} монет")
        print(f"   {', '.join(failed)}")
    
    print(f"\n💾 Данные сохранены в: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
