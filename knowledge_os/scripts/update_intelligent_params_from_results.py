#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматического обновления параметров в intelligent_filter_system.py
из результатов оптимизации с исправленной формулой Sharpe Ratio
"""

import json
import re
from pathlib import Path

# Загружаем результаты
files = sorted(Path('backtests').glob('optimize_intelligent_params_20251130_*.json'), reverse=True)
if not files:
    print("❌ Файл результатов не найден!")
    exit(1)

with open(files[0]) as f:
    data = json.load(f)

print(f"✅ Загружены результаты из {files[0].name}")
print(f"📊 Всего монет: {len(data)}")

# Читаем файл intelligent_filter_system.py
target_file = Path('src/ai/intelligent_filter_system.py')
content = target_file.read_text(encoding='utf-8')

# Обновляем параметры для каждой монеты
updates_count = 0

for symbol, info in data.items():
    if not info.get('best_params'):
        continue
    
    params = info['best_params']
    result = info.get('best_result', {})
    
    vol_ratio = params['volume_ratio']
    quality_score = params['quality_score']
    total_return = result.get('total_return', 0)
    sharpe = result.get('sharpe_ratio', 0)
    
    # Ищем блок для этой монеты
    pattern = rf"('{symbol}':\s*{{[^}}]*?'volume_ratio':\s*)[0-9.]+"
    
    def replace_volume(match):
        return f"{match.group(1)}{vol_ratio}"
    
    # Заменяем volume_ratio
    new_content = re.sub(pattern, replace_volume, content, flags=re.DOTALL)
    
    if new_content != content:
        content = new_content
        updates_count += 1
    
    # Заменяем quality_score
    pattern2 = rf"('{symbol}':\s*{{[^}}]*?'quality_score':\s*)[0-9.]+"
    
    def replace_quality(match):
        return f"{match.group(1)}{quality_score}"
    
    new_content = re.sub(pattern2, replace_quality, content, flags=re.DOTALL)
    
    if new_content != content:
        content = new_content
    
    # Обновляем комментарий с результатами
    pattern3 = rf"('{symbol}':\s*{{[^}}]*?# Результаты[^\n]*)"
    new_comment = f"# Результаты (пересчет 30.11.2025): return={total_return:+.2f}%, Sharpe={sharpe:+.2f}"
    
    def replace_comment(match):
        return new_comment
    
    new_content = re.sub(pattern3, replace_comment, content, flags=re.DOTALL)

# Сохраняем
if updates_count > 0:
    target_file.write_text(content, encoding='utf-8')
    print(f"✅ Обновлено параметров для {updates_count} монет")
else:
    print("⚠️ Не найдено монет для обновления")

