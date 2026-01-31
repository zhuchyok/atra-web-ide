#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Анализ реальных сигналов на проде
"""

import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print('=' * 80)
print('ANALIZ SIGNALOV ZA 3 DNYA')
print('=' * 80)

three_days_ago = datetime.now() - timedelta(hours=72)

# 1. Obshchaya statistika
cursor.execute('''
    SELECT COUNT(*) as total
    FROM signals_log
    WHERE created_at >= ?
''', (three_days_ago,))
total = cursor.fetchone()[0]

print(f'\n1. SIGNALY ZA 3 DNYA: {total}')

# 2. Filtry-blokirovshchiki
cursor.execute('''
    SELECT filter_type, 
           COUNT(*) as checks,
           SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as blocked
    FROM filter_checks 
    WHERE created_at >= ?
    GROUP BY filter_type
    ORDER BY blocked DESC
    LIMIT 5
''', (three_days_ago,))
filters = cursor.fetchall()

print('\n2. TOP-5 BLOKIRUYUSHCHIKH FILTROV:')
for f in filters:
    block_pct = (f[2] / f[1] * 100) if f[1] > 0 else 0
    print(f'   {f[0]:20s}: {f[2]:4d} blokirovok ({block_pct:5.1f}%)')

# 3. Quality score
cursor.execute('''
    SELECT 
        AVG(quality_score) as avg_q,
        MIN(quality_score) as min_q,
        MAX(quality_score) as max_q,
        COUNT(*) as total
    FROM signals_log
    WHERE created_at >= ? AND quality_score IS NOT NULL
''', (three_days_ago,))
q = cursor.fetchone()

print(f'\n3. QUALITY SCORE:')
if q and q[3] > 0:
    print(f'   Sredniy: {q[0]:.3f}')
    print(f'   Min: {q[1]:.3f}')
    print(f'   Max: {q[2]:.3f}')
else:
    print(f'   Net dannykh')

# 4. Poslednie 5 signalov
cursor.execute('''
    SELECT created_at, symbol
    FROM signals_log
    ORDER BY created_at DESC
    LIMIT 5
''')
recent = cursor.fetchall()

print('\n4. POSLEDNIE 5 SIGNALOV:')
if recent:
    for r in recent:
        print(f'   {r[0]} | {r[1]:10s}')
else:
    print(f'   Net signalov')

# 5. RSI Warning prichiny
print('\n5. RSI WARNING - PRICHINY BLOKIROVKI:')
cursor.execute('''
    SELECT reason, COUNT(*) as count
    FROM filter_checks
    WHERE created_at >= ? AND filter_type = 'rsi_warning' AND passed = 0
    GROUP BY reason
    ORDER BY count DESC
    LIMIT 3
''', (three_days_ago,))
rsi = cursor.fetchall()
for r in rsi:
    print(f'   {r[0][:70]}: {r[1]} raz')

# 6. Chastota signalov
print(f'\n6. CHASTOTA:')
print(f'   Signalov v chas: {total / 72:.1f}')
print(f'   Signalov v den: {total / 3:.1f}')

print('\n' + '=' * 80)

conn.close()

