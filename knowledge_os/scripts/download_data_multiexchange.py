#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка исторических данных для монет с нескольких бирж
Пробует: Binance -> Bybit -> KuCoin -> CoinGecko
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

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Монеты для загрузки (можно переопределить через переменную окружения)
import os
if os.environ.get('COINS_LIST'):
    import json
    COINS_TO_DOWNLOAD = json.loads(os.environ.get('COINS_LIST'))
else:
    # По умолчанию - новые 100 монет (топ 160-259)
    COINS_TO_DOWNLOAD = [
        "USDCUSDT", "FDUSDUSDT", "GIGGLEUSDT", "MOVEUSDT", "GUNUSDT",
        "SOMIUSDT", "JUVUSDT", "AXLUSDT", "HUMAUSDT", "EURUSDT",
        "USD1USDT", "BIOUSDT", "BARDUSDT", "TRUMPUSDT", "XUSDUSDT",
        "HYPERUSDT", "ORDIUSDT", "ATUSDT", "BFUSDUSDT", "TURBOUSDT",
        "POLUSDT", "0GUSDT", "KDAUSDT", "VIRTUALUSDT", "EIGENUSDT",
        "ZROUSDT", "SANTOSUSDT", "BERAUSDT", "ONDOUSDT", "USUALUSDT",
        "WBTCUSDT", "IOUSDT", "ETHFIUSDT", "LAYERUSDT", "GLMRUSDT",
        "ARUSDT", "SAHARAUSDT", "SYRUPUSDT", "KITEUSDT", "RESOLVUSDT",
        "ACTUSDT", "FISUSDT", "VOXELUSDT", "ZKUSDT", "NEIROUSDT",
        "BANANAS31USDT", "SKYUSDT", "SUSDT", "METUSDT", "SAPIENUSDT",
        "ALTUSDT", "PLUMEUSDT", "FFUSDT", "SCRUSDT", "INITUSDT",
        "BARUSDT", "BUSDUSDT", "PNUTUSDT", "MORPHOUSDT", "MEUSDT",
        "LINEAUSDT", "NOTUSDT", "COCOSUSDT", "QNTUSDT", "POLYUSDT",
        "EPICUSDT", "VANAUSDT", "WUSDT", "KMNOUSDT", "PARTIUSDT",
        "XVGUSDT", "HEMIUSDT", "GALUSDT", "TRBUSDT", "MAVUSDT",
        "RAYUSDT", "MAGICUSDT", "FORMUSDT", "GLMUSDT", "AVNTUSDT",
        "AIXBTUSDT", "AUSDT", "SHELLUSDT", "OMNIUSDT", "LSKUSDT",
        "TOMOUSDT", "JSTUSDT", "ONGUSDT", "SAGAUSDT", "ENSOUSDT",
        "SUPERUSDT", "KAITOUSDT", "TVKUSDT", "OGUSDT", "MINAUSDT",
        "SSVUSDT", "1000CHEEMSUSDT", "2ZUSDT", "1000SATSUSDT", "ACHUSDT"
    ]

DATA_DIR = Path("data/backtest_data_yearly")
DATA_DIR.mkdir(parents=True, exist_ok=True)

def download_from_binance(symbol: str) -> pd.DataFrame:
    """Загрузка данных с Binance"""
    try:
        print(f"   🔄 Пробуем Binance...")
        # Убираем 1000 из начала для Binance
        binance_symbol = symbol.replace("1000SHIB", "SHIB").replace("USDT", "USDT")
        
        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': binance_symbol,
            'interval': '1h',
            'limit': 1000
        }
        
        # Нужно получить данные за год (365 дней * 24 часа = 8760 свечей)
        # Binance дает максимум 1000 свечей за запрос
        all_data = []
        end_time = int(datetime.now().timestamp() * 1000)
        
        for _ in range(9):  # 9 запросов по 1000 = 9000 свечей (больше года)
            params['endTime'] = end_time
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            
            req = urllib.request.Request(full_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                if not data:
                    break
                
                all_data.extend(data)
                end_time = data[0][0] - 1  # Время первой свечи минус 1 мс
                
                if len(data) < 1000:
                    break
                
                time.sleep(0.2)  # Rate limiting
        
        if not all_data:
            return None
        
        # Конвертируем в DataFrame
        df = pd.DataFrame(all_data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
        df = df.astype({
            'open': float, 'high': float, 'low': float, 'close': float, 'volume': float
        })
        
        if len(df) >= 720:  # Минимум месяц данных
            print(f"   ✅ Binance: {len(df)} свечей")
            return df
        else:
            print(f"   ⚠️ Binance: недостаточно данных ({len(df)} свечей)")
            return None
            
    except Exception as e:
        print(f"   ❌ Binance: {str(e)[:50]}")
        return None

def download_from_bybit(symbol: str) -> pd.DataFrame:
    """Загрузка данных с Bybit"""
    try:
        print(f"   🔄 Пробуем Bybit...")
        # Bybit использует формат без USDT
        bybit_symbol = symbol.replace("USDT", "USDT")
        
        url = "https://api.bybit.com/v5/market/kline"
        
        all_data = []
        end_time = int(datetime.now().timestamp() * 1000)
        
        for _ in range(9):  # 9 запросов
            params = {
                'category': 'spot',
                'symbol': bybit_symbol,
                'interval': '60',  # 1 час
                'limit': '200',
                'end': str(end_time)
            }
            
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                
                if result.get('retCode') != 0 or not result.get('result', {}).get('list'):
                    break
                
                data = result['result']['list']
                all_data.extend(data)
                
                if len(data) < 200:
                    break
                
                end_time = int(data[-1][0]) - 1
                time.sleep(0.2)
        
        if not all_data:
            return None
        
        # Конвертируем в DataFrame
        df = pd.DataFrame(all_data, columns=[
            'startTime', 'open', 'high', 'low', 'close', 'volume',
            'turnover', 'ignore'
        ])
        
        df['open_time'] = pd.to_datetime(df['startTime'], unit='ms')
        df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
        df = df.astype({
            'open': float, 'high': float, 'low': float, 'close': float, 'volume': float
        })
        df = df.sort_values('open_time')
        
        if len(df) >= 720:
            print(f"   ✅ Bybit: {len(df)} свечей")
            return df
        else:
            print(f"   ⚠️ Bybit: недостаточно данных ({len(df)} свечей)")
            return None
            
    except Exception as e:
        print(f"   ❌ Bybit: {str(e)[:50]}")
        return None

def download_from_kucoin(symbol: str) -> pd.DataFrame:
    """Загрузка данных с KuCoin"""
    try:
        print(f"   🔄 Пробуем KuCoin...")
        # KuCoin использует формат без USDT
        kucoin_symbol = symbol.replace("USDT", "-USDT")
        
        url = "https://api.kucoin.com/api/v1/market/candles"
        
        all_data = []
        end_time = int(datetime.now().timestamp())
        
        for _ in range(9):
            params = {
                'symbol': kucoin_symbol,
                'type': '1hour',
                'endAt': str(end_time)
            }
            
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                
                if result.get('code') != '200000' or not result.get('data'):
                    break
                
                data = result['data']
                all_data.extend(data)
                
                if len(data) < 200:
                    break
                
                end_time = int(data[-1][0]) - 1
                time.sleep(0.2)
        
        if not all_data:
            return None
        
        # Конвертируем в DataFrame
        df = pd.DataFrame(all_data, columns=[
            'time', 'open', 'close', 'high', 'low', 'volume', 'amount'
        ])
        
        df['open_time'] = pd.to_datetime(df['time'], unit='s')
        df = df[['open_time', 'open', 'high', 'low', 'close', 'volume']]
        df = df.astype({
            'open': float, 'high': float, 'low': float, 'close': float, 'volume': float
        })
        df = df.sort_values('open_time')
        
        if len(df) >= 720:
            print(f"   ✅ KuCoin: {len(df)} свечей")
            return df
        else:
            print(f"   ⚠️ KuCoin: недостаточно данных ({len(df)} свечей)")
            return None
            
    except Exception as e:
        print(f"   ❌ KuCoin: {str(e)[:50]}")
        return None

def download_from_coingecko(symbol: str) -> pd.DataFrame:
    """Загрузка данных с CoinGecko"""
    try:
        print(f"   🔄 Пробуем CoinGecko...")
        # CoinGecko требует ID монеты, не символ
        # Это сложнее, пропускаем пока
        print(f"   ⚠️ CoinGecko: требует mapping символов на ID, пропускаем")
        return None
    except Exception as e:
        print(f"   ❌ CoinGecko: {str(e)[:50]}")
        return None

def download_coin_data(symbol: str) -> bool:
    """Загружает данные для монеты с разных бирж"""
    print(f"\n📥 Загрузка данных для {symbol}...")
    
    csv_path = DATA_DIR / f"{symbol}.csv"
    
    # Пробуем разные биржи
    df = None
    exchange = None
    
    # 1. Binance
    df = download_from_binance(symbol)
    if df is not None:
        exchange = "Binance"
    
    # 2. Bybit
    if df is None:
        df = download_from_bybit(symbol)
        if df is not None:
            exchange = "Bybit"
    
    # 3. KuCoin
    if df is None:
        df = download_from_kucoin(symbol)
        if df is not None:
            exchange = "KuCoin"
    
    # 4. CoinGecko (пропускаем, сложно)
    # if df is None:
    #     df = download_from_coingecko(symbol)
    #     if df is not None:
    #         exchange = "CoinGecko"
    
    if df is not None and len(df) >= 720:
        df.to_csv(csv_path, index=False)
        print(f"   ✅ Сохранено {len(df)} свечей с {exchange} в {csv_path}")
        return True
    else:
        print(f"   ❌ Не удалось загрузить данные для {symbol}")
        return False

def main():
    print("="*80)
    print("📥 ЗАГРУЗКА ДАННЫХ С НЕСКОЛЬКИХ БИРЖ")
    print("="*80)
    print(f"📋 Монет для загрузки: {len(COINS_TO_DOWNLOAD)}")
    print(f"🔍 Биржи: Binance -> Bybit -> KuCoin")
    print()
    
    downloaded = []
    failed = []
    
    for i, symbol in enumerate(COINS_TO_DOWNLOAD, 1):
        print(f"\n[{i}/{len(COINS_TO_DOWNLOAD)}] {symbol}")
        if download_coin_data(symbol):
            downloaded.append(symbol)
        else:
            failed.append(symbol)
        time.sleep(1)  # Пауза между запросами
    
    print()
    print("="*80)
    print("📊 ИТОГИ ЗАГРУЗКИ")
    print("="*80)
    print(f"✅ Загружено: {len(downloaded)}/{len(COINS_TO_DOWNLOAD)}")
    if downloaded:
        print(f"   {', '.join(downloaded)}")
    print()
    if failed:
        print(f"❌ Не загружено: {len(failed)}/{len(COINS_TO_DOWNLOAD)}")
        print(f"   {', '.join(failed)}")
    print("="*80)

if __name__ == "__main__":
    main()

