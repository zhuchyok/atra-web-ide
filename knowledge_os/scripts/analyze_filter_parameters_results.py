#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
АНАЛИЗ РЕЗУЛЬТАТОВ БЭКТЕСТОВ ПАРАМЕТРОВ ФИЛЬТРОВ
Анализирует результаты бэктестов и определяет оптимальные значения параметров
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import pandas as pd

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ
# ============================================================================

RESULTS_DIR = Path("backtest_results/filter_parameters")
OUTPUT_REPORT = Path("docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md")

# ============================================================================
# КЛАСС ДЛЯ АНАЛИЗА РЕЗУЛЬТАТОВ
# ============================================================================

class FilterParametersAnalyzer:
    """Класс для анализа результатов бэктестов параметров"""
    
    def __init__(self, results_dir: Path = RESULTS_DIR):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def load_results(self, param_name: str) -> Optional[Dict[str, Any]]:
        """Загружает результаты бэктеста для параметра"""
        filename = self.results_dir / f"{param_name}_results.json"
        
        if not filename.exists():
            logger.warning("⚠️ Файл результатов не найден: %s", filename)
            return None
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error("❌ Ошибка загрузки результатов: %s", e)
            return None
    
    def analyze_parameter(self, param_name: str) -> Optional[Dict[str, Any]]:
        """Анализирует результаты для одного параметра"""
        results = self.load_results(param_name)
        if not results:
            return None
        
        logger.info("📊 Анализ параметра: %s", param_name)
        
        # Преобразуем результаты в DataFrame для удобства анализа
        data = []
        for param_value, metrics in results.items():
            data.append({
                'param_value': param_value,
                'win_rate': metrics.get('win_rate', 0),
                'profit_factor': metrics.get('profit_factor', 0),
                'total_return': metrics.get('total_return', 0),
                'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'total_trades': metrics.get('total_trades', 0),
                'signals_generated': metrics.get('signals_generated', 0),
                'signals_executed': metrics.get('signals_executed', 0),
                'avg_profit_per_trade': metrics.get('avg_profit_per_trade', 0)
            })
        
        df = pd.DataFrame(data)
        
        if df.empty:
            logger.warning("⚠️ Нет данных для анализа")
            return None
        
        # Определяем оптимальное значение на основе комплексного score
        best_value = None
        best_score = -float('inf')
        best_metrics = None
        
        for _, row in df.iterrows():
            # Вычисляем комплексный score
            score = 0.0
            
            # Profit Factor (вес 30%)
            pf = row['profit_factor']
            if pf != float('inf') and pf > 0:
                score += min(pf, 3.0) * 0.3  # Ограничиваем максимальный вклад
            
            # Win Rate (вес 25%)
            wr = row['win_rate']
            if wr > 50:
                score += (wr / 100) * 0.25
            else:
                score -= (50 - wr) / 100 * 0.25
            
            # Total Return (вес 20%)
            tr = row['total_return']
            if tr > 0:
                score += min(tr / 100, 0.5) * 0.2  # Ограничиваем максимальный вклад
            else:
                score += tr / 100 * 0.2
            
            # Sharpe Ratio (вес 15%)
            sr = row['sharpe_ratio']
            if sr > 0:
                score += min(sr, 2.0) * 0.15  # Ограничиваем максимальный вклад
            
            # Max Drawdown (вес 10%, меньше = лучше)
            dd = row['max_drawdown_pct']
            if dd < 20:
                score += (20 - dd) / 20 * 0.1
            else:
                score -= (dd - 20) / 20 * 0.1
            
            if score > best_score:
                best_score = score
                best_value = row['param_value']
                best_metrics = row.to_dict()
        
        return {
            'param_name': param_name,
            'optimal_value': best_value,
            'score': best_score,
            'metrics': best_metrics,
            'all_results': results,
            'dataframe': df
        }
    
    def generate_report(self, analyses: List[Dict[str, Any]]) -> str:
        """Генерирует Markdown отчет с результатами"""
        report = []
        
        report.append("# Результаты оптимизации параметров фильтров")
        report.append("")
        report.append(f"**Дата анализа:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        report.append("## Методология")
        report.append("")
        report.append("Бэктесты проводились на следующих условиях:")
        report.append("- **Период:** 3 месяца (90 дней)")
        report.append("- **Символы:** Топ-20 монет из intelligent_filter_system")
        report.append("- **Таймфрейм:** 1h")
        report.append("- **Начальный баланс:** 10,000 USDT")
        report.append("- **Комиссия:** 0.1% (0.001)")
        report.append("- **Проскальзывание:** 0.05% (0.0005)")
        report.append("- **Параллелизация:** Rust с 15 потоками")
        report.append("")
        report.append("### Критерии выбора оптимального значения")
        report.append("")
        report.append("Комплексный score рассчитывается на основе:")
        report.append("1. **Profit Factor** (вес 30%) - отношение прибыли к убыткам")
        report.append("2. **Win Rate** (вес 25%) - процент прибыльных сделок")
        report.append("3. **Total Return** (вес 20%) - общая доходность")
        report.append("4. **Sharpe Ratio** (вес 15%) - риск-скорректированная доходность")
        report.append("5. **Max Drawdown** (вес 10%) - максимальная просадка (меньше = лучше)")
        report.append("")
        report.append("---")
        report.append("")
        
        for analysis in analyses:
            if not analysis:
                continue
            
            param_name = analysis['param_name']
            optimal_value = analysis['optimal_value']
            score = analysis['score']
            metrics = analysis['metrics']
            df = analysis['dataframe']
            
            report.append(f"## {param_name}")
            report.append("")
            report.append(f"**Оптимальное значение:** `{optimal_value}`")
            report.append(f"**Комплексный score:** `{score:.3f}`")
            report.append("")
            
            # Таблица сравнения всех значений
            report.append("### Сравнение всех значений")
            report.append("")
            report.append("| Значение | Win Rate (%) | Profit Factor | Total Return (%) | Max Drawdown (%) | Sharpe Ratio | Total Trades |")
            report.append("|----------|--------------|---------------|------------------|------------------|--------------|--------------|")
            
            for _, row in df.sort_values('param_value').iterrows():
                is_optimal = row['param_value'] == optimal_value
                marker = " **⭐**" if is_optimal else ""
                report.append(
                    f"| {row['param_value']}{marker} | "
                    f"{row['win_rate']:.2f} | "
                    f"{row['profit_factor']:.2f} | "
                    f"{row['total_return']:.2f} | "
                    f"{row['max_drawdown_pct']:.2f} | "
                    f"{row['sharpe_ratio']:.2f} | "
                    f"{row['total_trades']} |"
                )
            
            report.append("")
            
            # Детальные метрики оптимального значения
            if metrics:
                report.append("### Детальные метрики оптимального значения")
                report.append("")
                report.append(f"- **Win Rate:** {metrics['win_rate']:.2f}%")
                report.append(f"- **Profit Factor:** {metrics['profit_factor']:.2f}")
                report.append(f"- **Total Return:** {metrics['total_return']:.2f}%")
                report.append(f"- **Max Drawdown:** {metrics['max_drawdown_pct']:.2f}%")
                report.append(f"- **Sharpe Ratio:** {metrics['sharpe_ratio']:.2f}")
                report.append(f"- **Total Trades:** {metrics['total_trades']}")
                report.append(f"- **Signals Generated:** {metrics['signals_generated']}")
                report.append(f"- **Signals Executed:** {metrics['signals_executed']}")
                report.append(f"- **Avg Profit per Trade:** {metrics['avg_profit_per_trade']:.2f} USDT")
                report.append("")
            
            report.append("---")
            report.append("")
        
        # Сводная таблица оптимальных значений
        report.append("## Сводная таблица оптимальных значений")
        report.append("")
        report.append("| Параметр | Оптимальное значение | Score | Win Rate (%) | Profit Factor | Total Return (%) |")
        report.append("|----------|---------------------|-------|--------------|---------------|------------------|")
        
        for analysis in analyses:
            if not analysis:
                continue
            
            param_name = analysis['param_name']
            optimal_value = analysis['optimal_value']
            score = analysis['score']
            metrics = analysis['metrics']
            
            if metrics:
                report.append(
                    f"| {param_name} | {optimal_value} | {score:.3f} | "
                    f"{metrics['win_rate']:.2f} | {metrics['profit_factor']:.2f} | "
                    f"{metrics['total_return']:.2f} |"
                )
        
        report.append("")
        report.append("---")
        report.append("")
        report.append("## Рекомендации")
        report.append("")
        report.append("На основе результатов бэктестов рекомендуется:")
        report.append("")
        
        for analysis in analyses:
            if not analysis:
                continue
            
            param_name = analysis['param_name']
            optimal_value = analysis['optimal_value']
            metrics = analysis['metrics']
            
            if metrics:
                report.append(f"### {param_name}")
                report.append("")
                report.append(f"- **Рекомендуемое значение:** `{optimal_value}`")
                report.append(f"- **Обоснование:** Win Rate {metrics['win_rate']:.2f}%, ")
                report.append(f"  Profit Factor {metrics['profit_factor']:.2f}, ")
                report.append(f"  Total Return {metrics['total_return']:.2f}%, ")
                report.append(f"  Max Drawdown {metrics['max_drawdown_pct']:.2f}%")
                report.append("")
        
        report.append("---")
        report.append("")
        report.append("*Отчет сгенерирован автоматически на основе результатов бэктестов*")
        
        return "\n".join(report)
    
    def save_report(self, report: str, output_file: Path = OUTPUT_REPORT):
        """Сохраняет отчет в файл"""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info("💾 Отчет сохранен в %s", output_file)

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Анализ результатов бэктестов параметров')
    parser.add_argument('--results-dir', type=str, default=str(RESULTS_DIR), help='Директория с результатами')
    parser.add_argument('--output', type=str, default=str(OUTPUT_REPORT), help='Файл для сохранения отчета')
    parser.add_argument('--param', type=str, help='Анализировать только один параметр')
    
    args = parser.parse_args()
    
    logger.info("📊 АНАЛИЗ РЕЗУЛЬТАТОВ БЭКТЕСТОВ ПАРАМЕТРОВ")
    logger.info("=" * 80)
    
    analyzer = FilterParametersAnalyzer(results_dir=Path(args.results_dir))
    
    # Определяем какие параметры анализировать
    params_to_analyze = []
    
    if args.param:
        params_to_analyze = [args.param]
    else:
        # Анализируем все параметры
        params_to_analyze = [
            'min_confidence_for_short',
            'min_quality_threshold_long',
            'min_quality_for_short',
            'market_adjustment',
            'min_h4_confidence'
        ]
    
    analyses = []
    
    for param_name in params_to_analyze:
        analysis = analyzer.analyze_parameter(param_name)
        if analysis:
            analyses.append(analysis)
            logger.info(
                "✅ %s: Оптимальное значение = %s (score=%.3f)",
                param_name,
                analysis['optimal_value'],
                analysis['score']
            )
        else:
            logger.warning("⚠️ Не удалось проанализировать %s", param_name)
    
    if not analyses:
        logger.error("❌ Нет данных для анализа")
        return
    
    # Генерируем отчет
    report = analyzer.generate_report(analyses)
    analyzer.save_report(report, output_file=Path(args.output))
    
    logger.info("=" * 80)
    logger.info("✅ АНАЛИЗ ЗАВЕРШЕН")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()

