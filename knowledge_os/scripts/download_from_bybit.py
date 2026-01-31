#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка исторических данных с Bybit для монет, недоступных на Binance
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

BYBIT_COINS = [
    "EOSUSDT", "FTMUSDT", "KLAYUSDT", "MKRUSDT", "RNDRUSDT"
]

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "backtest_data_yearly"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def download_from_bybit(symbol: str, days: int = 365) -> pd.DataFrame:
    """Загружает данные с Bybit API"""
    all_data = []
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    # Bybit использует timestamp в секундах
    current_end_ts = int(end_time.timestamp())
    start_ts = int(start_time.timestamp())
    
    batch = 0
    max_batches = 200  # Увеличиваем лимит батчей для загрузки года
    
    print(f"    Загрузка {symbol} с Bybit...", end=" ")
    
    while current_end_ts > start_ts and batch < max_batches:
        # Bybit лимит: 200 свечей на запрос
        # Для 1h свечей: 200 свечей = ~8.3 дня
        # Загружаем с перекрытием для надежности
        current_start_ts = current_end_ts - (7 * 24 * 3600)  # 7 дней назад (меньше для перекрытия)
        if current_start_ts < start_ts:
            current_start_ts = start_ts
        
        # Bybit API v5: category=spot, interval=60 (1 час), limit=200
        url = f"https://api.bybit.com/v5/market/kline"
        params = {
            'category': 'spot',
            'symbol': symbol,
            'interval': '60',  # 1 час в минутах
            'start': current_start_ts * 1000,  # в миллисекундах
            'end': current_end_ts * 1000,
            'limit': 200
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
                        
                        if data.get('retCode') == 0:
                            result = data.get('result', {})
                            klines = result.get('list', [])
                            
                            if klines:
                                # Bybit возвращает данные в формате:
                                # [startTime, open, high, low, close, volume, turnover]
                                for kline in reversed(klines):  # Bybit возвращает в обратном порядке
                                    all_data.append([
                                        int(kline[0]),  # timestamp
                                        float(kline[1]),  # open
                                        float(kline[2]),  # high
                                        float(kline[3]),  # low
                                        float(kline[4]),  # close
                                        float(kline[5]),  # volume
                                    ])
                                
                                current_end_ts = current_start_ts
                                batch += 1
                                time.sleep(0.5)
                                break
                            else:
                                # Нет данных для этого периода
                                break
                        else:
                            if attempt < max_attempts - 1:
                                time.sleep(2 ** attempt)
                                continue
                            else:
                                return pd.DataFrame()
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
        'timestamp', 'open', 'high', 'low', 'close', 'volume'
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
    print("📥 ЗАГРУЗКА ДАННЫХ С BYBIT (5 монет)")
    print("=" * 80)
    print()
    
    successful = 0
    failed = []
    
    for idx, symbol in enumerate(BYBIT_COINS, 1):
        output_file = OUTPUT_DIR / f"{symbol}.csv"
        
        # Проверяем существующие данные - если меньше 8000 свечей (приблизительно год), перезагружаем
        if output_file.exists():
            try:
                df_check = pd.read_csv(output_file)
                days_check = (pd.to_datetime(df_check['open_time']).max() - pd.to_datetime(df_check['open_time']).min()).days if len(df_check) > 1 else 0
                if len(df_check) > 8000 and days_check > 300:  # Больше 300 дней = год
                    print(f"[{idx}/{len(BYBIT_COINS)}] ⏭️  {symbol} - уже загружено ({len(df_check)} свечей, {days_check} дней)")
                    successful += 1
                    continue
                else:
                    print(f"[{idx}/{len(BYBIT_COINS)}] 🔄 {symbol} - мало данных ({len(df_check)} свечей, {days_check} дней), перезагружаем...")
            except:
                pass
        
        print(f"[{idx}/{len(BYBIT_COINS)}] 📥 {symbol}...", end=" ")
        
        df = download_from_bybit(symbol, days=365)
        
        if not df.empty and len(df) > 100:
            df.to_csv(output_file, index=False)
            days_actual = (df['open_time'].max() - df['open_time'].min()).days if len(df) > 1 else 0
            print(f"✅ {len(df)} свечей, {days_actual} дней")
            successful += 1
        else:
            print(f"❌ Нет данных")
            failed.append(symbol)
        
        if idx < len(BYBIT_COINS):
            time.sleep(1)
    
    print()
    print("=" * 80)
    print("✅ ЗАГРУЗКА ЗАВЕРШЕНА")
    print("=" * 80)
    print(f"\n✅ Успешно загружено: {successful}/{len(BYBIT_COINS)} монет")
    
    if failed:
        print(f"❌ Не загружено: {len(failed)} монет")
        print(f"   {', '.join(failed)}")
    
    print(f"\n💾 Данные сохранены в: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

