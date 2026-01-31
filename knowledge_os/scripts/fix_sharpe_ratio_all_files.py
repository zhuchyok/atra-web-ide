#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 ИСПРАВЛЕНИЕ ФОРМУЛЫ SHARPE RATIO ВО ВСЕХ ФАЙЛАХ

Правильная формула Sharpe Ratio:
Sharpe = (R_p - R_f) / σ_p
где:
- R_p - доходность портфеля (total_return)
- R_f - безрисковая ставка (0 для крипто)
- σ_p - стандартное отклонение доходности

КРИТИЧНО: Если total_return < 0, то Sharpe должен быть <= 0!
"""

import re
from pathlib import Path
from typing import List, Tuple

# Правильная формула Sharpe Ratio для BacktestStats класса
CORRECT_SHARPE_CODE = '''        # Sharpe Ratio (исправленный расчет)
        # ⚠️ ВАЖНО: Sharpe должен отражать общую доходность портфеля
        # Формула: Sharpe = (R_p - R_f) / σ_p, где R_p = total_return, R_f = 0
        if len(self.trades) > 1:
            returns = [t.get('profit_pct', 0) for t in self.trades]
            std_return = np.std(returns)
            
            if std_return > 0:
                # Используем общую доходность портфеля (total_return в %)
                # Нормализуем по волатильности сделок
                # Предполагаем месячные данные (30 дней), умножаем на 12 для годовой доходности
                annualized_return_pct = total_return * 12  # Годовая доходность
                annualized_volatility_pct = std_return * np.sqrt(365)  # Годовая волатильность
                sharpe_ratio = annualized_return_pct / annualized_volatility_pct if annualized_volatility_pct > 0 else 0.0
            else:
                sharpe_ratio = 0.0
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: Sharpe должен иметь тот же знак, что и общая доходность
            # Если общая доходность отрицательна, Sharpe не может быть положительным!
            if total_return < 0:
                sharpe_ratio = min(0.0, sharpe_ratio)  # Принудительно делаем отрицательным или 0
        else:
            sharpe_ratio = 0.0'''

def find_sharpe_blocks(content: str) -> List[Tuple[int, int, str]]:
    """Находит все блоки расчета Sharpe Ratio"""
    blocks = []
    
    # Паттерн для поиска блока расчета Sharpe
    pattern = r'(#\s*Sharpe Ratio.*?\n|#\s*Коэффициент Шарпа.*?\n).*?(sharpe.*?=.*?\n)'
    
    for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
        start, end = match.span()
        blocks.append((start, end, match.group(0)))
    
    return blocks

def fix_backtest_stats_sharpe(content: str) -> Tuple[str, bool]:
    """Исправляет формулу Sharpe Ratio в классе BacktestStats"""
    modified = False
    
    # Ищем блок с расчетом Sharpe в get_metrics
    # Ищем: returns = [t.get('profit_pct' или returns = [t['profit_pct']
    if 'returns = [t.get(\'profit_pct\'' in content or 'returns = [t[\'profit_pct\']' in content:
        # Проверяем, есть ли уже проверка на total_return < 0
        if 'КРИТИЧЕСКАЯ ПРОВЕРКА' not in content and 'if total_return < 0' not in content:
            # Находим блок расчета Sharpe
            pattern = r'(#\s*Sharpe Ratio.*?\n)(.*?)(sharpe.*?=.*?\n)'
            
            def replace_sharpe(match):
                nonlocal modified
                modified = True
                return CORRECT_SHARPE_CODE
            
            # Пробуем заменить
            new_content = re.sub(
                r'(#\s*Sharpe Ratio.*?)(if len\(self\.trades\) > 1:.*?)(sharpe.*?=.*?\n)(.*?)(else:.*?sharpe.*?=.*?\n)',
                CORRECT_SHARPE_CODE,
                content,
                flags=re.DOTALL
            )
            
            if new_content != content:
                content = new_content
                modified = True
    
    return content, modified

def fix_file(file_path: Path) -> bool:
    """Исправляет формулу Sharpe Ratio в файле"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Проверяем, есть ли BacktestStats класс
        if 'class BacktestStats' in content or 'def get_metrics' in content:
            content, modified = fix_backtest_stats_sharpe(content)
            
            if modified:
                file_path.write_text(content, encoding='utf-8')
                return True
        
        return False
    except Exception as e:
        print(f"  ❌ Ошибка в {file_path.name}: {e}")
        return False

def main():
    """Главная функция"""
    print("="*80)
    print("🔧 ИСПРАВЛЕНИЕ ФОРМУЛЫ SHARPE RATIO ВО ВСЕХ ФАЙЛАХ")
    print("="*80)
    print()
    
    # Основной файл, который нужно исправить
    main_files = [
        Path('scripts/backtest_5coins_intelligent.py'),
        Path('scripts/backtest_5coins_monthly.py'),
        Path('scripts/backtest_bnbusdt_weekly.py'),
    ]
    
    fixed_count = 0
    
    for file_path in main_files:
        if file_path.exists():
            print(f"📁 Проверяю: {file_path.name}")
            if fix_file(file_path):
                print(f"  ✅ Исправлено!")
                fixed_count += 1
            else:
                print(f"  ⏭️  Уже исправлен или не требует изменений")
        else:
            print(f"  ⚠️  Файл не найден: {file_path}")
    
    print()
    print("="*80)
    print(f"✅ Исправлено файлов: {fixed_count}")
    print("="*80)

if __name__ == '__main__':
    main()

