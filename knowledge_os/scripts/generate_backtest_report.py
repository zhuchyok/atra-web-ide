#!/usr/bin/env python3
"""Генератор подробного отчета по результатам бектеста."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.shared.utils.datetime_utils import get_utc_now

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class BacktestReportGenerator:
    """Генератор подробного отчета по бектесту."""

    def __init__(self, report_path: Path):
        with report_path.open("r", encoding="utf-8") as f:
            self.report = json.load(f)

        self.trades_df = pd.DataFrame(self.report["trades"])
        self.metrics = self.report["metrics"]
        self.backtest_info = self.report["backtest_info"]

    def generate_report(self) -> str:
        """Генерирует подробный отчет в Markdown."""
        lines = []

        # Заголовок
        lines.append("# 📊 Подробный отчет по бектесту")
        lines.append("")
        lines.append(f"**Дата генерации:** {get_utc_now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Информация о бектесте
        lines.append("## 📋 Информация о бектесте")
        lines.append("")
        lines.append(f"- **Период:** {self.backtest_info['start_date']} → {self.backtest_info['end_date']}")
        lines.append(f"- **Длительность:** {self.backtest_info['days']} дней")
        lines.append(f"- **Символы:** {', '.join(self.backtest_info['symbols'])}")
        lines.append(f"- **Начальный баланс:** ${self.backtest_info['initial_balance']:,.2f}")
        lines.append(f"- **Риск на сделку:** {self.backtest_info['risk_per_trade']}%")
        lines.append(f"- **Плечо:** {self.backtest_info['leverage']}x")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Основные метрики
        lines.append("## 📈 Основные метрики производительности")
        lines.append("")
        lines.append("| Метрика | Значение |")
        lines.append("|---------|----------|")
        lines.append(f"| **Всего сделок** | {self.metrics['total_trades']} |")
        lines.append(f"| **Прибыльных** | {self.metrics['winning_trades']} |")
        lines.append(f"| **Убыточных** | {self.metrics['losing_trades']} |")
        lines.append(f"| **Win Rate** | {self.metrics['win_rate']:.2f}% |")
        lines.append(f"| **Total PnL** | ${self.metrics['total_pnl']:,.2f} |")
        lines.append(f"| **Total Return** | {self.metrics['total_return']:.2f}% |")
        lines.append(f"| **Final Balance** | ${self.metrics['final_balance']:,.2f} |")
        lines.append(f"| **Sharpe Ratio** | {self.metrics['sharpe_ratio']:.2f} |")
        lines.append(f"| **Sortino Ratio** | {self.metrics['sortino_ratio']:.2f} |")
        lines.append(f"| **Profit Factor** | {self.metrics['profit_factor']:.2f} |")
        lines.append(f"| **Max Drawdown** | {self.metrics['max_drawdown']:.2f}% |")
        lines.append(f"| **Max Profit** | ${self.metrics['max_profit']:,.2f} |")
        lines.append(f"| **Max Loss** | ${self.metrics['max_loss']:,.2f} |")
        lines.append(f"| **Avg PnL** | ${self.metrics['avg_pnl']:,.2f} |")
        lines.append(f"| **Avg Win** | ${self.metrics['avg_win']:,.2f} |")
        lines.append(f"| **Avg Loss** | ${self.metrics['avg_loss']:,.2f} |")
        if 'max_consecutive_wins' in self.metrics:
            lines.append(f"| **Max Consecutive Wins** | {self.metrics['max_consecutive_wins']} |")
        if 'max_consecutive_losses' in self.metrics:
            lines.append(f"| **Max Consecutive Losses** | {self.metrics['max_consecutive_losses']} |")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Анализ по символам
        if not self.trades_df.empty:
            lines.append("## 💰 Анализ по символам")
            lines.append("")
            symbol_stats = self.trades_df.groupby("symbol").agg(
                {
                    "pnl": ["count", "sum", "mean"],
                    "pnl_percent": "mean",
                }
            ).round(2)

            lines.append("| Символ | Сделок | Total PnL | Avg PnL | Avg PnL % |")
            lines.append("|--------|--------|-----------|---------|-----------|")
            for symbol in symbol_stats.index:
                count = int(symbol_stats.loc[symbol, ("pnl", "count")])
                total = symbol_stats.loc[symbol, ("pnl", "sum")]
                avg = symbol_stats.loc[symbol, ("pnl", "mean")]
                avg_pct = symbol_stats.loc[symbol, ("pnl_percent", "mean")]
                lines.append(f"| {symbol} | {count} | ${total:,.2f} | ${avg:,.2f} | {avg_pct:.2f}% |")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Анализ по направлениям
        if not self.trades_df.empty:
            lines.append("## 📊 Анализ по направлениям")
            lines.append("")
            direction_stats = self.trades_df.groupby("direction").agg(
                {
                    "pnl": ["count", "sum", "mean"],
                    "pnl_percent": "mean",
                }
            ).round(2)

            lines.append("| Направление | Сделок | Total PnL | Avg PnL | Avg PnL % |")
            lines.append("|-------------|--------|-----------|---------|-----------|")
            for direction in direction_stats.index:
                count = int(direction_stats.loc[direction, ("pnl", "count")])
                total = direction_stats.loc[direction, ("pnl", "sum")]
                avg = direction_stats.loc[direction, ("pnl", "mean")]
                avg_pct = direction_stats.loc[direction, ("pnl_percent", "mean")]
                lines.append(f"| {direction} | {count} | ${total:,.2f} | ${avg:,.2f} | {avg_pct:.2f}% |")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Анализ по причинам закрытия
        if not self.trades_df.empty and "exit_reason" in self.trades_df.columns:
            lines.append("## 🎯 Анализ по причинам закрытия")
            lines.append("")
            exit_stats = self.trades_df.groupby("exit_reason").agg(
                {
                    "pnl": ["count", "sum", "mean"],
                }
            ).round(2)

            lines.append("| Причина | Сделок | Total PnL | Avg PnL |")
            lines.append("|---------|--------|-----------|---------|")
            for reason in exit_stats.index:
                count = int(exit_stats.loc[reason, ("pnl", "count")])
                total = exit_stats.loc[reason, ("pnl", "sum")]
                avg = exit_stats.loc[reason, ("pnl", "mean")]
                lines.append(f"| {reason} | {count} | ${total:,.2f} | ${avg:,.2f} |")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Анализ фильтров
        lines.append("## 🔍 Анализ работы фильтров")
        lines.append("")
        filter_stats = self.metrics.get("filter_stats", {})
        total_filtered = sum(filter_stats.values())
        if total_filtered > 0:
            lines.append("| Фильтр | Количество блокировок | % от общего |")
            lines.append("|--------|----------------------|-------------|")
            for filter_name, count in sorted(filter_stats.items(), key=lambda x: x[1], reverse=True):
                pct = (count / total_filtered * 100) if total_filtered > 0 else 0
                lines.append(f"| {filter_name} | {count} | {pct:.2f}% |")
        else:
            lines.append("Нет данных о фильтрах.")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Анализ убыточных сделок
        if not self.trades_df.empty:
            losing_trades = self.trades_df[self.trades_df["pnl"] < 0]
            if len(losing_trades) > 0:
                lines.append("## ❌ Анализ убыточных сделок")
                lines.append("")
                lines.append(f"**Всего убыточных сделок:** {len(losing_trades)}")
                lines.append("")

                # Топ-10 худших сделок
                worst_trades = losing_trades.nsmallest(10, "pnl")
                lines.append("### Топ-10 худших сделок:")
                lines.append("")
                lines.append("| Символ | Направление | Entry | Exit | PnL | PnL % | Причина |")
                lines.append("|--------|-------------|-------|------|-----|-------|---------|")
                for _, trade in worst_trades.iterrows():
                    lines.append(
                        f"| {trade['symbol']} | {trade['direction']} | "
                        f"${trade['entry_price']:.4f} | ${trade['exit_price']:.4f} | "
                        f"${trade['pnl']:.2f} | {trade['pnl_percent']:.2f}% | {trade.get('exit_reason', 'N/A')} |"
                    )

                lines.append("")
                lines.append("---")
                lines.append("")

        # Анализ прибыльных сделок
        if not self.trades_df.empty:
            winning_trades = self.trades_df[self.trades_df["pnl"] > 0]
            if len(winning_trades) > 0:
                lines.append("## ✅ Анализ прибыльных сделок")
                lines.append("")
                lines.append(f"**Всего прибыльных сделок:** {len(winning_trades)}")
                lines.append("")

                # Топ-10 лучших сделок
                best_trades = winning_trades.nlargest(10, "pnl")
                lines.append("### Топ-10 лучших сделок:")
                lines.append("")
                lines.append("| Символ | Направление | Entry | Exit | PnL | PnL % | Причина |")
                lines.append("|--------|-------------|-------|------|-----|-------|---------|")
                for _, trade in best_trades.iterrows():
                    lines.append(
                        f"| {trade['symbol']} | {trade['direction']} | "
                        f"${trade['entry_price']:.4f} | ${trade['exit_price']:.4f} | "
                        f"${trade['pnl']:.2f} | {trade['pnl_percent']:.2f}% | {trade.get('exit_reason', 'N/A')} |"
                    )

                lines.append("")
                lines.append("---")
                lines.append("")

        # Анализ рынка
        if not self.trades_df.empty:
            lines.append("## 📊 Анализ рыночных условий")
            lines.append("")

            # Анализ по RSI
            if "rsi" in self.trades_df.columns:
                rsi_analysis = self._analyze_rsi()
                if rsi_analysis:
                    lines.append("### RSI анализ:")
                    lines.append("")
                    lines.append(rsi_analysis)
                    lines.append("")

            # Анализ по объёму
            if "volume_ratio" in self.trades_df.columns:
                volume_analysis = self._analyze_volume()
                if volume_analysis:
                    lines.append("### Анализ объёма:")
                    lines.append("")
                    lines.append(volume_analysis)
                    lines.append("")

            # Анализ по BTC тренду
            if "btc_trend" in self.trades_df.columns:
                btc_analysis = self._analyze_btc_trend()
                if btc_analysis:
                    lines.append("### BTC тренд анализ:")
                    lines.append("")
                    lines.append(btc_analysis)
                    lines.append("")

            lines.append("---")
            lines.append("")

        # Анализ использования паттернов и индивидуальных параметров
        if not self.trades_df.empty:
            lines.append("## 🤖 Анализ использования паттернов и индивидуальных параметров")
            lines.append("")
            
            trades_with_params = self.trades_df[self.trades_df.get("symbol_params_used", False) == True]
            trades_with_patterns = self.trades_df[self.trades_df.get("patterns_analyzed", 0) > 0]
            
            if len(trades_with_params) > 0:
                win_rate_params = (trades_with_params["pnl"] > 0).sum() / len(trades_with_params) * 100
                avg_pnl_params = trades_with_params["pnl"].mean()
                lines.append(f"- **Сделок с индивидуальными параметрами:** {len(trades_with_params)} ({len(trades_with_params)/len(self.trades_df)*100:.1f}%)")
                lines.append(f"- **Win rate с индивидуальными параметрами:** {win_rate_params:.2f}%")
                lines.append(f"- **Средний PnL с индивидуальными параметрами:** ${avg_pnl_params:.2f}")
                lines.append("")
            
            if len(trades_with_patterns) > 0:
                win_rate_patterns = (trades_with_patterns["pnl"] > 0).sum() / len(trades_with_patterns) * 100
                avg_pnl_patterns = trades_with_patterns["pnl"].mean()
                avg_patterns_analyzed = trades_with_patterns["patterns_analyzed"].mean()
                lines.append(f"- **Сделок с анализом паттернов:** {len(trades_with_patterns)} ({len(trades_with_patterns)/len(self.trades_df)*100:.1f}%)")
                lines.append(f"- **Win rate с анализом паттернов:** {win_rate_patterns:.2f}%")
                lines.append(f"- **Средний PnL с анализом паттернов:** ${avg_pnl_patterns:.2f}")
                lines.append(f"- **Среднее количество проанализированных паттернов:** {avg_patterns_analyzed:.0f}")
                lines.append("")
            
            # Анализ по символам с паттернами
            if "patterns_analyzed" in self.trades_df.columns:
                symbol_patterns_analysis = self.trades_df.groupby("symbol").agg({
                    "patterns_analyzed": "mean",
                    "pnl": ["count", "sum", "mean"]
                }).round(2)
                
                lines.append("### Анализ паттернов по символам:")
                lines.append("")
                lines.append("| Символ | Среднее паттернов | Сделок | Total PnL | Avg PnL |")
                lines.append("|--------|-------------------|--------|-----------|---------|")
                for symbol in symbol_patterns_analysis.index:
                    avg_patterns = symbol_patterns_analysis.loc[symbol, ("patterns_analyzed", "mean")]
                    count = int(symbol_patterns_analysis.loc[symbol, ("pnl", "count")])
                    total = symbol_patterns_analysis.loc[symbol, ("pnl", "sum")]
                    avg = symbol_patterns_analysis.loc[symbol, ("pnl", "mean")]
                    lines.append(f"| {symbol} | {avg_patterns:.0f} | {count} | ${total:,.2f} | ${avg:,.2f} |")
                lines.append("")
            
            lines.append("---")
            lines.append("")

        # Зоны роста и недостатки
        lines.append("## 🚀 Зоны роста и недостатки")
        lines.append("")
        recommendations = self._generate_recommendations()
        lines.append(recommendations)
        lines.append("")

        return "\n".join(lines)

    def _analyze_rsi(self) -> str:
        """Анализирует влияние RSI на результаты."""
        if "rsi" not in self.trades_df.columns:
            return ""

        lines = []
        losing = self.trades_df[self.trades_df["pnl"] < 0]
        winning = self.trades_df[self.trades_df["pnl"] > 0]

        if len(losing) > 0:
            avg_rsi_losing = losing["rsi"].mean()
            lines.append(f"- **Средний RSI убыточных сделок:** {avg_rsi_losing:.2f}")

        if len(winning) > 0:
            avg_rsi_winning = winning["rsi"].mean()
            lines.append(f"- **Средний RSI прибыльных сделок:** {avg_rsi_winning:.2f}")

        # Анализ экстремальных значений
        extreme_oversold = self.trades_df[self.trades_df["rsi"] < 25]
        extreme_overbought = self.trades_df[self.trades_df["rsi"] > 75]

        if len(extreme_oversold) > 0:
            win_rate_oversold = (extreme_oversold["pnl"] > 0).sum() / len(extreme_oversold) * 100
            lines.append(f"- **Win rate при RSI < 25:** {win_rate_oversold:.2f}% ({len(extreme_oversold)} сделок)")

        if len(extreme_overbought) > 0:
            win_rate_overbought = (extreme_overbought["pnl"] > 0).sum() / len(extreme_overbought) * 100
            lines.append(f"- **Win rate при RSI > 75:** {win_rate_overbought:.2f}% ({len(extreme_overbought)} сделок)")

        return "\n".join(lines) if lines else ""

    def _analyze_volume(self) -> str:
        """Анализирует влияние объёма на результаты."""
        if "volume_ratio" not in self.trades_df.columns:
            return ""

        lines = []
        losing = self.trades_df[self.trades_df["pnl"] < 0]
        winning = self.trades_df[self.trades_df["pnl"] > 0]

        if len(losing) > 0:
            avg_volume_losing = losing["volume_ratio"].mean()
            lines.append(f"- **Средний volume ratio убыточных сделок:** {avg_volume_losing:.2f}")

        if len(winning) > 0:
            avg_volume_winning = winning["volume_ratio"].mean()
            lines.append(f"- **Средний volume ratio прибыльных сделок:** {avg_volume_winning:.2f}")

        # Анализ высокого объёма
        high_volume = self.trades_df[self.trades_df["volume_ratio"] > 1.5]
        if len(high_volume) > 0:
            win_rate_high = (high_volume["pnl"] > 0).sum() / len(high_volume) * 100
            lines.append(f"- **Win rate при volume ratio > 1.5:** {win_rate_high:.2f}% ({len(high_volume)} сделок)")

        return "\n".join(lines) if lines else ""

    def _analyze_btc_trend(self) -> str:
        """Анализирует влияние BTC тренда на результаты."""
        if "btc_trend" not in self.trades_df.columns:
            return ""

        lines = []
        btc_aligned = self.trades_df[self.trades_df["btc_trend"] == True]
        btc_opposite = self.trades_df[self.trades_df["btc_trend"] == False]

        if len(btc_aligned) > 0:
            win_rate_aligned = (btc_aligned["pnl"] > 0).sum() / len(btc_aligned) * 100
            avg_pnl_aligned = btc_aligned["pnl"].mean()
            lines.append(f"- **Win rate при совпадении с BTC трендом:** {win_rate_aligned:.2f}% ({len(btc_aligned)} сделок)")
            lines.append(f"- **Средний PnL при совпадении:** ${avg_pnl_aligned:.2f}")

        if len(btc_opposite) > 0:
            win_rate_opposite = (btc_opposite["pnl"] > 0).sum() / len(btc_opposite) * 100
            avg_pnl_opposite = btc_opposite["pnl"].mean()
            lines.append(f"- **Win rate при противоположном BTC тренде:** {win_rate_opposite:.2f}% ({len(btc_opposite)} сделок)")
            lines.append(f"- **Средний PnL при противоположном:** ${avg_pnl_opposite:.2f}")

        return "\n".join(lines) if lines else ""

    def _generate_recommendations(self) -> str:
        """Генерирует рекомендации по улучшению."""
        lines = []

        # Анализ использования паттернов
        patterns_total = self.metrics.get("patterns_total", 0)
        trades_with_patterns = self.metrics.get("trades_with_patterns_analysis", 0)
        trades_with_params = self.metrics.get("trades_with_symbol_params", 0)
        
        if patterns_total > 0:
            lines.append("### ✅ Использование паттернов и индивидуальных параметров")
            lines.append("")
            lines.append(f"- **Всего паттернов в системе:** {patterns_total:,}")
            lines.append(f"- **Сделок с анализом паттернов:** {trades_with_patterns} ({trades_with_patterns/self.metrics.get('total_trades', 1)*100:.1f}%)")
            lines.append(f"- **Сделок с индивидуальными параметрами:** {trades_with_params} ({trades_with_params/self.metrics.get('total_trades', 1)*100:.1f}%)")
            lines.append("")
            if trades_with_patterns < self.metrics.get("total_trades", 1) * 0.8:
                lines.append("⚠️ **Рекомендация:** Увеличить использование паттернов для оптимизации TP/SL")
                lines.append("")
        
        # Анализ win rate
        win_rate = self.metrics.get("win_rate", 0)
        if win_rate < 50:
            lines.append("### ⚠️ Низкий Win Rate")
            lines.append("")
            lines.append(f"- Текущий win rate: {win_rate:.2f}%")
            lines.append("- **Рекомендации:**")
            lines.append("  - Ужесточить фильтры входа (увеличить минимальную confidence)")
            lines.append("  - Улучшить проверку BTC тренда")
            lines.append("  - Добавить дополнительные фильтры (объём, волатильность)")
            lines.append("  - Использовать больше паттернов для оптимизации параметров")
            lines.append("")

        # Анализ Profit Factor
        profit_factor = self.metrics.get("profit_factor", 0)
        if profit_factor < 1.5:
            lines.append("### ⚠️ Низкий Profit Factor")
            lines.append("")
            lines.append(f"- Текущий profit factor: {profit_factor:.2f}")
            lines.append("- **Рекомендации:**")
            lines.append("  - Улучшить соотношение avg_win / avg_loss")
            lines.append("  - Оптимизировать TP/SL уровни")
            lines.append("  - Рассмотреть трейлинг стоп")
            lines.append("")

        # Анализ Drawdown
        max_dd = self.metrics.get("max_drawdown", 0)
        if max_dd > 20:
            lines.append("### ⚠️ Высокий Max Drawdown")
            lines.append("")
            lines.append(f"- Текущий max drawdown: {max_dd:.2f}%")
            lines.append("- **Рекомендации:**")
            lines.append("  - Уменьшить риск на сделку")
            lines.append("  - Добавить ограничение на максимальное количество открытых позиций")
            lines.append("  - Улучшить риск-менеджмент")
            lines.append("")

        # Анализ фильтров
        filter_stats = self.metrics.get("filter_stats", {})
        if filter_stats:
            most_blocking = max(filter_stats.items(), key=lambda x: x[1])
            lines.append("### 🔍 Анализ фильтров")
            lines.append("")
            lines.append(f"- Самый активный фильтр: {most_blocking[0]} ({most_blocking[1]} блокировок)")
            lines.append("- **Рекомендации:**")
            lines.append("  - Проанализировать эффективность фильтров")
            lines.append("  - Возможно, некоторые фильтры слишком строгие")
            lines.append("")

        if not lines:
            lines.append("### ✅ Система работает хорошо")
            lines.append("")
            lines.append("Все основные метрики в норме. Продолжайте мониторить результаты.")

        return "\n".join(lines)


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Генератор подробного отчета по бектесту")
    parser.add_argument("--input", default="data/backtest_report.json", help="Путь к JSON отчету")
    parser.add_argument("--output", default="data/backtest_report.md", help="Путь для сохранения Markdown отчета")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("❌ Файл отчета не найден: %s", input_path)
        return

    logger.info("📊 Генерация подробного отчета...")

    generator = BacktestReportGenerator(input_path)
    report = generator.generate_report()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(report)

    logger.info("✅ Отчет сохранён: %s", output_path)


if __name__ == "__main__":
    main()

