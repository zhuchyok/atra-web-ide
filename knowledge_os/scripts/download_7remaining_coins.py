#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка исторических данных для 7 оставшихся монет
Альтернативный метод с прямыми запросами к Binance API
"""

import sys
import os
import time
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import urllib.request
import urllib.error

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REMAINING_7 = [
    "EOSUSDT", "FTMUSDT", "KEEPUSDT", "KLAYUSDT", "MKRUSDT",
    "RNDRUSDT", "XMRUSDT"
]

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "backtest_data_yearly"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def download_binance_data(symbol: str, days: int = 365) -> pd.DataFrame:
    """Загружает данные с Binance с повторными попытками"""
    all_data = []
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    current_end = end_time
    batch_count = 0
    max_batches = 15
    
    print(f"    Загрузка {symbol}...", end=" ")
    
    while current_end > start_time and batch_count < max_batches:
        current_start = current_end - timedelta(days=40)
        if current_start < start_time:
            current_start = start_time
        
        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': '1h',
            'startTime': int(current_start.timestamp() * 1000),
            'endTime': int(current_end.timestamp() * 1000),
            'limit': 1000
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{query_string}"
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                req = urllib.request.Request(full_url)
                req.add_header('User-Agent', 'Mozilla/5.0 (compatible; ATRA/1.0)')
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        
                        if data:
                            all_data.extend(data)
                            current_end = current_start
                            batch_count += 1
                            time.sleep(0.5)  # Задержка между батчами
                            break
                        else:
                            break
                    else:
                        if attempt < max_attempts - 1:
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            return pd.DataFrame()
                            
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    # Символ может быть недоступен
                    return pd.DataFrame()
                elif attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return pd.DataFrame()
                    
            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return pd.DataFrame()
        else:
            # Все попытки провалились
            break
    
    if not all_data:
        return pd.DataFrame()
    
    # Удаляем дубликаты
    seen = set()
    unique_data = []
    for item in all_data:
        ts = item[0]
        if ts not in seen:
            seen.add(ts)
            unique_data.append(item)
    
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
    
    # Создаем open_time из timestamp
    df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
    df = df.sort_values('open_time').reset_index(drop=True)
    
    return df


def main():
    print("=" * 80)
    print("📥 ЗАГРУЗКА ДАННЫХ ДЛЯ 7 ОСТАВШИХСЯ МОНЕТ")
    print("=" * 80)
    print()
    
    successful = 0
    failed = []
    
    for idx, symbol in enumerate(REMAINING_7, 1):
        output_file = OUTPUT_DIR / f"{symbol}.csv"
        
        if output_file.exists():
            # Проверяем, есть ли данные
            try:
                df_check = pd.read_csv(output_file)
                if len(df_check) > 100:
                    print(f"[{idx}/7] ⏭️  {symbol} - уже загружено ({len(df_check)} свечей)")
                    successful += 1
                    continue
            except:
                pass
        
        print(f"[{idx}/7] 📥 {symbol}...", end=" ")
        
        df = download_binance_data(symbol, days=365)
        
        if not df.empty and len(df) > 100:
            df.to_csv(output_file, index=False)
            days_actual = (df['open_time'].max() - df['open_time'].min()).days if len(df) > 1 else 0
            print(f"✅ {len(df)} свечей, {days_actual} дней")
            successful += 1
        else:
            print(f"❌ Нет данных или ошибка")
            failed.append(symbol)
        
        if idx < len(REMAINING_7):
            time.sleep(1)
    
    print()
    print("=" * 80)
    print("✅ ЗАГРУЗКА ЗАВЕРШЕНА")
    print("=" * 80)
    print(f"\n✅ Успешно загружено: {successful}/{len(REMAINING_7)} монет")
    
    if failed:
        print(f"❌ Не загружено: {len(failed)} монет")
        print(f"   {', '.join(failed)}")
    
    print(f"\n💾 Данные сохранены в: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

