#!/usr/bin/env python3
"""
[ATRA CORP] Анализ торгового дня — Orderbook & Trade Anomaly Detection
Задача: выявить аномалии, скрытые мотивы маркет-мейкеров и китов из parquet-снэпшотов стакана.
Запуск: python3 analyze_orderbook.py --file /path/to/2026-03-09.parquet
"""

import duckdb
import json
import sys
import argparse
import os
from datetime import datetime

def get_file_path():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="/Users/zhuchyok/Downloads/2026-03-09.parquet")
    args, _ = parser.parse_known_args()
    return args.file

def inspect_schema(con, file):
    """Шаг 1: Изучить схему и структуру данных."""
    print("\n" + "="*60)
    print("ШАГ 1: СХЕМА И СТРУКТУРА ДАННЫХ")
    print("="*60)

    schema = con.execute(f"DESCRIBE SELECT * FROM '{file}' LIMIT 1").fetchall()
    print("Колонки:")
    for col in schema:
        print(f"  {col[0]:20s} {col[1]}")

    count = con.execute(f"SELECT COUNT(*) FROM '{file}'").fetchone()[0]
    print(f"\nВсего записей: {count:,}")

    tr = con.execute(f"SELECT MIN(time), MAX(time) FROM '{file}'").fetchone()
    print(f"Диапазон: {tr[0]} → {tr[1]}")

    tickers = con.execute(f"""
        SELECT ticker, COUNT(*) as cnt,
               ROUND(AVG(price),4) as avg_price,
               ROUND(MIN(price),4) as min_price,
               ROUND(MAX(price),4) as max_price
        FROM '{file}'
        GROUP BY ticker ORDER BY cnt DESC LIMIT 10
    """).fetchall()
    print("\nТикеры:")
    for t in tickers:
        print(f"  {str(t[0]):15s} cnt={t[1]:>8,}  avg={t[2]}  min={t[3]}  max={t[4]}")

    # Пробуем распарсить payload
    sample_payload = con.execute(f"SELECT payload FROM '{file}' LIMIT 1").fetchone()
    if sample_payload:
        try:
            p = json.loads(sample_payload[0])
            print(f"\nПример payload (ключи): {list(p.keys()) if isinstance(p, dict) else type(p)}")
        except Exception:
            print(f"\nPayload (raw): {str(sample_payload[0])[:200]}")

    return count

def detect_price_anomalies(con, file):
    """Шаг 2: Аномалии цены — резкие скачки, flash crashes."""
    print("\n" + "="*60)
    print("ШАГ 2: АНОМАЛИИ ЦЕНЫ (Flash Crash / Spike)")
    print("="*60)

    result = con.execute(f"""
        WITH price_diff AS (
            SELECT
                time, ticker, price,
                LAG(price) OVER (PARTITION BY ticker ORDER BY time) AS prev_price,
                (price - LAG(price) OVER (PARTITION BY ticker ORDER BY time))
                    / NULLIF(LAG(price) OVER (PARTITION BY ticker ORDER BY time), 0) * 100 AS pct_change
            FROM '{file}'
        )
        SELECT time, ticker,
               ROUND(price, 6) as price,
               ROUND(prev_price, 6) as prev_price,
               ROUND(pct_change, 4) as pct_change_pct
        FROM price_diff
        WHERE ABS(pct_change) > 0.5
        ORDER BY ABS(pct_change) DESC
        LIMIT 20
    """).fetchall()

    if result:
        print(f"Найдено резких движений (>0.5%): {len(result)}")
        for r in result:
            print(f"  {r[0]}  {r[1]:12s}  {r[2]} → {r[3]}  Δ={r[4]}%")
    else:
        print("Резких аномалий цены не обнаружено.")
    return result

def detect_volume_anomalies(con, file):
    """Шаг 3: Аномалии объёма — подозрительные всплески."""
    print("\n" + "="*60)
    print("ШАГ 3: АНОМАЛИИ ОБЪЁМА (Whale Activity)")
    print("="*60)

    # Пробуем найти поле объёма в payload
    sample = con.execute(f"SELECT payload FROM '{file}' LIMIT 5").fetchall()
    volume_field = None
    for s in sample:
        try:
            p = json.loads(s[0])
            if isinstance(p, dict):
                for key in ['volume', 'vol', 'size', 'qty', 'quantity', 'amount']:
                    if key in p:
                        volume_field = key
                        break
        except Exception:
            pass
        if volume_field:
            break

    if volume_field:
        print(f"Поле объёма в payload: '{volume_field}'")
        result = con.execute(f"""
            WITH vol_data AS (
                SELECT time, ticker, price,
                    TRY_CAST(json_extract_string(payload, '$.{volume_field}') AS DOUBLE) AS volume
                FROM '{file}'
            ),
            vol_stats AS (
                SELECT ticker,
                    AVG(volume) as avg_vol,
                    STDDEV(volume) as std_vol
                FROM vol_data GROUP BY ticker
            )
            SELECT v.time, v.ticker, ROUND(v.price,4) as price,
                   ROUND(v.volume,2) as volume,
                   ROUND((v.volume - s.avg_vol) / NULLIF(s.std_vol,0), 2) as z_score
            FROM vol_data v JOIN vol_stats s ON v.ticker = s.ticker
            WHERE (v.volume - s.avg_vol) / NULLIF(s.std_vol,0) > 3
            ORDER BY z_score DESC LIMIT 20
        """).fetchall()
        if result:
            print(f"Аномальные всплески объёма (z>3): {len(result)}")
            for r in result:
                print(f"  {r[0]}  {r[1]:12s}  price={r[2]}  vol={r[3]}  z={r[4]}")
    else:
        print("Поле объёма в payload не найдено — анализирую по плотности снэпшотов.")
        result = con.execute(f"""
            SELECT
                time_bucket,
                ticker,
                cnt,
                ROUND(avg_price, 6) as avg_price
            FROM (
                SELECT
                    STRFTIME(time, '%H:%M') as time_bucket,
                    ticker,
                    COUNT(*) as cnt,
                    AVG(price) as avg_price
                FROM '{file}'
                GROUP BY time_bucket, ticker
            ) t
            ORDER BY cnt DESC LIMIT 20
        """).fetchall()
        print("Топ периодов по плотности снэпшотов:")
        for r in result:
            print(f"  {r[0]}  {r[1]:12s}  cnt={r[2]:>6,}  avg_price={r[3]}")
    return result

def detect_spread_manipulation(con, file):
    """Шаг 4: Манипуляции со спредом — поиск аномальных bid/ask."""
    print("\n" + "="*60)
    print("ШАГ 4: МАНИПУЛЯЦИИ СПРЕДОМ (Market Maker Behaviour)")
    print("="*60)

    sample = con.execute(f"SELECT payload FROM '{file}' LIMIT 3").fetchall()
    has_bid_ask = False
    for s in sample:
        try:
            p = json.loads(s[0])
            if isinstance(p, dict) and ('bids' in p or 'asks' in p or 'bid' in p or 'ask' in p):
                has_bid_ask = True
                print(f"Структура стакана найдена. Ключи: {list(p.keys())}")
                # Показываем первый уровень стакана
                for side in ['bids', 'asks']:
                    if side in p and p[side]:
                        print(f"  {side}[0]: {p[side][0] if isinstance(p[side], list) else p[side]}")
                break
        except Exception:
            pass

    if not has_bid_ask:
        print("Структура bids/asks в payload не обнаружена. Анализирую spread через price.")
        result = con.execute(f"""
            WITH price_range AS (
                SELECT
                    STRFTIME(time, '%H') as hour,
                    ticker,
                    MAX(price) - MIN(price) as hour_range,
                    MIN(price) as low,
                    MAX(price) as high,
                    COUNT(*) as snapshots
                FROM '{file}'
                GROUP BY hour, ticker
            )
            SELECT hour, ticker,
                   ROUND(hour_range, 6) as range,
                   ROUND(low, 6) as low,
                   ROUND(high, 6) as high,
                   snapshots
            FROM price_range
            ORDER BY hour_range DESC LIMIT 15
        """).fetchall()
        print("Наибольший ценовой диапазон по часам:")
        for r in result:
            print(f"  {r[0]}:xx  {r[1]:12s}  range={r[2]}  [{r[3]} → {r[4]}]  snaps={r[5]}")
        return result

def detect_market_microstructure(con, file):
    """Шаг 5: Общее поведение рынка — тренды, ликвидность."""
    print("\n" + "="*60)
    print("ШАГ 5: МИКРОСТРУКТУРА РЫНКА")
    print("="*60)

    result = con.execute(f"""
        WITH hourly AS (
            SELECT
                STRFTIME(time, '%H:%M') as minute,
                ticker,
                FIRST(price ORDER BY time) as open_price,
                LAST(price ORDER BY time) as close_price,
                MAX(price) as high,
                MIN(price) as low,
                COUNT(*) as ticks
            FROM '{file}'
            GROUP BY minute, ticker
        )
        SELECT
            ticker,
            COUNT(minute) as active_minutes,
            ROUND(AVG(ticks), 1) as avg_ticks_per_min,
            ROUND(SUM(close_price - open_price) / NULLIF(FIRST(open_price ORDER BY minute), 0) * 100, 4) as total_return_pct,
            ROUND(AVG((high - low) / NULLIF(low, 0) * 100), 4) as avg_intrabar_volatility_pct
        FROM hourly
        GROUP BY ticker
        ORDER BY avg_intrabar_volatility_pct DESC
    """).fetchall()

    print("Микроструктура по тикерам:")
    for r in result:
        print(f"  {str(r[0]):15s}  active_min={r[1]:>5}  ticks/min={r[2]:>6}  return={r[3]:>8}%  volatility={r[4]:>6}%")
    return result

def run_analysis(file_path):
    print(f"\n🚀 ATRA CORP — Анализ торгового дня 2026-03-09")
    print(f"📂 Файл: {file_path}")
    print(f"🕐 Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not os.path.exists(file_path):
        print(f"\n❌ Файл не найден: {file_path}")
        print("Убедитесь что файл скопирован на эту машину и путь верный.")
        return False

    con = duckdb.connect()

    try:
        count = inspect_schema(con, file_path)
        detect_price_anomalies(con, file_path)
        detect_volume_anomalies(con, file_path)
        detect_spread_manipulation(con, file_path)
        detect_market_microstructure(con, file_path)

        print("\n" + "="*60)
        print("✅ АНАЛИЗ ЗАВЕРШЁН")
        print("="*60)
        return True
    except Exception as e:
        print(f"\n❌ Ошибка анализа: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        con.close()

if __name__ == "__main__":
    file_path = get_file_path()
    run_analysis(file_path)
