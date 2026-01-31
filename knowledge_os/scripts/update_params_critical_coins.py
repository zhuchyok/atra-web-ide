#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновление параметров для критичных старых монет из результатов оптимизации
"""

import json
import re
from pathlib import Path
from datetime import datetime

# Загружаем результаты - ищем последний файл
import glob
result_files = sorted(glob.glob('backtests/optimize_critical_old_coins_*.json'), reverse=True)
if result_files:
    result_file = Path(result_files[0])
    print(f"📂 Используем файл: {result_file.name}")
else:
    print(f"❌ Файл результатов не найден!")
    exit(1)

with open(result_file, 'r') as f:
    data = json.load(f)

print(f"✅ Загружены результаты из {result_file.name}")
print(f"📊 Всего монет: {len(data)}")
print()

# Читаем файл intelligent_filter_system.py
target_file = Path('src/ai/intelligent_filter_system.py')
content = target_file.read_text(encoding='utf-8')

# Обновляем параметры для каждой монеты
updates_count = 0
updated_symbols = []

for symbol, info in data.items():
    if not info.get('best_params'):
        continue
    
    params = info['best_params']
    result = info.get('best_result', {})
    
    vol_ratio = params['volume_ratio']
    quality_score = params['quality_score']
    rsi_oversold = params.get('rsi_oversold', 40)
    rsi_overbought = params.get('rsi_overbought', 60)
    trend_strength = params.get('trend_strength', 0.15)
    momentum_threshold = params.get('momentum_threshold', -5.0)
    
    total_return = result.get('total_return', 0) * 100
    sharpe = result.get('sharpe_ratio', 0)
    win_rate = result.get('win_rate', 0)
    
    # Ищем блок для этой монеты
    pattern = rf"('{symbol}':\s*\{{[^}}]*?)(?:'volume_ratio':\s*)([0-9.]+)"
    
    def replace_params(match):
        prefix = match.group(1)
        # Заменяем все параметры
        replacement = (
            f"{prefix}'volume_ratio': {vol_ratio},\n"
            f"                   'rsi_oversold': {rsi_oversold},\n"
            f"                   'rsi_overbought': {rsi_overbought},\n"
            f"                   'trend_strength': {trend_strength},\n"
            f"                   'quality_score': {quality_score},\n"
            f"                   'momentum_threshold': {momentum_threshold}"
        )
        return replacement
    
    # Ищем и заменяем весь блок параметров
    new_content = re.sub(pattern, replace_params, content, flags=re.DOTALL)
    
    if new_content != content:
        content = new_content
        updates_count += 1
        updated_symbols.append(symbol)
        status = "✅ ИСПРАВЛЕНО" if sharpe > 0 else "⚠️"
        print(f"{status} {symbol}: VR={vol_ratio}, QS={quality_score}, Sharpe={sharpe:.3f}, Return={total_return:+.2f}%")
    
    # Обновляем комментарий с результатами (если есть)
    comment_pattern = rf"('{symbol}':\s*\{{[^}}]*?)# Результаты[^\n]*"
    new_comment = f"# Результаты (13.12.2025, переоптимизация): return={total_return:+.2f}%, Sharpe={sharpe:+.3f}, WinRate={win_rate:.1f}%"
    
    def replace_comment(match):
        return match.group(1) + new_comment
    
    new_content = re.sub(comment_pattern, replace_comment, content, flags=re.DOTALL)
    if new_content != content:
        content = new_content

# Сохраняем
if updates_count > 0:
    target_file.write_text(content, encoding='utf-8')
    print()
    print(f"✅ Обновлено параметров для {updates_count} монет")
    print(f"📋 Обновленные монеты: {', '.join(sorted(updated_symbols))}")
else:
    print("⚠️ Не найдено монет для обновления")

