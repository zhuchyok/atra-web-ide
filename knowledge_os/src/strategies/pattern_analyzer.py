#!/usr/bin/env python3
"""
Анализатор эффективности торговых паттернов
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from statistics import mean, stdev

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Результат торговой сделки"""
    symbol: str
    pattern_type: str
    signal_type: str  # LONG/SHORT
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: float = 0.0
    exit_time: Optional[float] = None
    pnl_pct: Optional[float] = None
    is_winner: Optional[bool] = None
    duration_hours: Optional[float] = None
    ai_score: float = 0.0
    volume_usd: float = 0.0
    volatility_pct: float = 0.0
    market_regime: str = "UNKNOWN"  # BULL_TREND/BEAR_TREND/HIGH_VOL_RANGE/LOW_VOL_RANGE/CRASH
    composite_score: float = 0.0  # Composite signal score
    composite_confidence: float = 0.0  # Composite signal confidence


@dataclass
class PatternStats:
    """Статистика по паттерну"""
    pattern_type: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    winrate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    avg_duration_hours: float = 0.0
    total_pnl_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_ai_score: float = 0.0
    market_regime_performance: Dict[str, float] = None
    last_updated: float = 0.0

    def __post_init__(self):
        if self.market_regime_performance is None:
            self.market_regime_performance = {}


class PatternEffectivenessAnalyzer:
    """Анализатор эффективности торговых паттернов с AI-метриками"""
    
    def __init__(self, data_file: str = "ai_learning_data/pattern_effectiveness.json"):
        self.data_file = data_file
        self.trade_results: List[TradeResult] = []
        self.pattern_stats: Dict[str, PatternStats] = {}
        self.load_historical_data()
        
    def add_trade_result(self, trade: TradeResult):
        """Добавляет результат сделки для анализа"""
        trade.entry_time = trade.entry_time or time.time()
        self.trade_results.append(trade)
        
        # Обновляем статистику паттерна
        self._update_pattern_stats(trade)
        
        logger.debug("📊 Добавлен результат сделки: %s %s (PnL: %.2f%%)", 
                    trade.symbol, trade.pattern_type, trade.pnl_pct or 0.0)
    
    def _update_pattern_stats(self, trade: TradeResult):
        """Обновляет статистику для паттерна"""
        pattern = trade.pattern_type
        
        if pattern not in self.pattern_stats:
            self.pattern_stats[pattern] = PatternStats(pattern_type=pattern)
        
        stats = self.pattern_stats[pattern]
        stats.total_trades += 1
        stats.last_updated = time.time()
        
        if trade.pnl_pct is not None:
            stats.total_pnl_pct += trade.pnl_pct
            
            if trade.is_winner:
                stats.winning_trades += 1
                if trade.pnl_pct > 0:
                    # Обновляем средний выигрыш
                    current_wins = [t.pnl_pct for t in self.trade_results 
                                  if t.pattern_type == pattern and t.is_winner and t.pnl_pct]
                    stats.avg_win_pct = mean(current_wins) if current_wins else 0.0
            else:
                stats.losing_trades += 1
                if trade.pnl_pct < 0:
                    # Обновляем средний проигрыш
                    current_losses = [abs(t.pnl_pct) for t in self.trade_results 
                                    if t.pattern_type == pattern and not t.is_winner and t.pnl_pct]
                    stats.avg_loss_pct = mean(current_losses) if current_losses else 0.0
        
        # Пересчитываем основные метрики
        self._recalculate_pattern_metrics(pattern)
    
    def _recalculate_pattern_metrics(self, pattern: str):
        """Пересчитывает метрики для паттерна"""
        stats = self.pattern_stats[pattern]
        pattern_trades = [t for t in self.trade_results if t.pattern_type == pattern]
        
        if not pattern_trades:
            return
        
        # Winrate
        completed_trades = [t for t in pattern_trades if t.pnl_pct is not None]
        if completed_trades:
            stats.winrate = stats.winning_trades / len(completed_trades)
        
        # Profit Factor
        total_wins = sum(t.pnl_pct for t in completed_trades if t.pnl_pct and t.pnl_pct > 0)
        total_losses = abs(sum(t.pnl_pct for t in completed_trades if t.pnl_pct and t.pnl_pct < 0))
        stats.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Средняя продолжительность
        duration_trades = [t for t in pattern_trades if t.duration_hours]
        if duration_trades:
            stats.avg_duration_hours = mean([t.duration_hours for t in duration_trades])
        
        # Средний AI-скор
        ai_score_trades = [t for t in pattern_trades if t.ai_score > 0]
        if ai_score_trades:
            stats.avg_ai_score = mean([t.ai_score for t in ai_score_trades])
        
        # Sharpe Ratio (упрощенный)
        pnl_values = [t.pnl_pct for t in completed_trades if t.pnl_pct is not None]
        if len(pnl_values) > 1:
            avg_return = mean(pnl_values)
            return_std = stdev(pnl_values)
            stats.sharpe_ratio = avg_return / return_std if return_std > 0 else 0.0
        
        # Производительность по режимам рынка
        for regime in ["TREND", "RANGE", "TRANSITION"]:
            regime_trades = [t for t in completed_trades if t.market_regime == regime]
            if regime_trades:
                regime_winrate = sum(1 for t in regime_trades if t.is_winner) / len(regime_trades)
                stats.market_regime_performance[regime] = regime_winrate
    
    def get_pattern_effectiveness(self, pattern: str, min_trades: int = 10) -> Optional[PatternStats]:
        """Получает статистику эффективности паттерна"""
        if pattern not in self.pattern_stats:
            return None
        
        stats = self.pattern_stats[pattern]
        if stats.total_trades < min_trades:
            logger.debug("📊 Недостаточно сделок для паттерна %s: %d < %d", 
                        pattern, stats.total_trades, min_trades)
            return None
        
        return stats
    
    def get_all_patterns_ranking(self, sort_by: str = "profit_factor") -> List[Tuple[str, PatternStats]]:
        """Получает рейтинг всех паттернов по эффективности"""
        valid_patterns = []
        
        for pattern, stats in self.pattern_stats.items():
            if stats.total_trades >= 5:  # Минимум для рейтинга
                valid_patterns.append((pattern, stats))
        
        # Сортируем по выбранной метрике
        if sort_by == "profit_factor":
            valid_patterns.sort(key=lambda x: x[1].profit_factor, reverse=True)
        elif sort_by == "winrate":
            valid_patterns.sort(key=lambda x: x[1].winrate, reverse=True)
        elif sort_by == "sharpe_ratio":
            valid_patterns.sort(key=lambda x: x[1].sharpe_ratio, reverse=True)
        elif sort_by == "total_pnl":
            valid_patterns.sort(key=lambda x: x[1].total_pnl_pct, reverse=True)
        
        return valid_patterns
    
    def get_optimization_insights(self) -> Dict[str, Any]:
        """Получает инсайты для оптимизации параметров"""
        insights = {
            "best_patterns": [],
            "worst_patterns": [],
            "regime_preferences": {},
            "ai_score_correlation": {},
            "volume_impact": {},
            "volatility_sweet_spots": {}
        }
        
        ranking = self.get_all_patterns_ranking("profit_factor")
        
        if len(ranking) >= 2:
            # Лучшие и худшие паттерны
            insights["best_patterns"] = ranking[:2]
            insights["worst_patterns"] = ranking[-2:]
        
        # Анализ корреляции AI-скора с успехом
        for pattern, _ in ranking:
            pattern_trades = [t for t in self.trade_results 
                            if t.pattern_type == pattern and t.ai_score > 0 and t.pnl_pct is not None]
            
            if len(pattern_trades) >= 10:
                # Группируем по AI-скору
                high_score_trades = [t for t in pattern_trades if t.ai_score >= 70]
                low_score_trades = [t for t in pattern_trades if t.ai_score < 50]
                
                if high_score_trades and low_score_trades:
                    high_score_winrate = sum(1 for t in high_score_trades if t.is_winner) / len(high_score_trades)
                    low_score_winrate = sum(1 for t in low_score_trades if t.is_winner) / len(low_score_trades)
                    
                    insights["ai_score_correlation"][pattern] = {
                        "high_score_winrate": high_score_winrate,
                        "low_score_winrate": low_score_winrate,
                        "correlation_strength": high_score_winrate - low_score_winrate
                    }
        
        return insights
    
    def save_data(self):
        """Сохраняет данные анализа"""
        try:
            import os
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            
            data = {
                "trade_results": [asdict(trade) for trade in self.trade_results[-1000:]],  # Последние 1000
                "pattern_stats": {k: asdict(v) for k, v in self.pattern_stats.items()},
                "last_updated": time.time()
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("💾 Данные анализа паттернов сохранены: %d сделок, %d паттернов", 
                       len(self.trade_results), len(self.pattern_stats))
        
        except Exception as e:
            logger.error("❌ Ошибка сохранения данных анализа: %s", e)
    
    def load_historical_data(self):
        """Загружает исторические данные анализа"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Восстанавливаем результаты сделок
            self.trade_results = []
            for trade_data in data.get("trade_results", []):
                trade = TradeResult(**trade_data)
                self.trade_results.append(trade)
            
            # Восстанавливаем статистику паттернов
            self.pattern_stats = {}
            for pattern, stats_data in data.get("pattern_stats", {}).items():
                stats = PatternStats(**stats_data)
                self.pattern_stats[pattern] = stats
            
            logger.info("📊 Загружены исторические данные: %d сделок, %d паттернов", 
                       len(self.trade_results), len(self.pattern_stats))
        
        except FileNotFoundError:
            logger.info("📊 Файл исторических данных не найден, начинаем с чистого листа")
        except Exception as e:
            logger.error("❌ Ошибка загрузки исторических данных: %s", e)
    
    def print_effectiveness_report(self):
        """Выводит отчет об эффективности паттернов"""
        logger.info("📊 ОТЧЕТ ОБ ЭФФЕКТИВНОСТИ ПАТТЕРНОВ:")
        
        ranking = self.get_all_patterns_ranking("profit_factor")
        
        if not ranking:
            logger.info("  📝 Недостаточно данных для анализа")
            return
        
        for i, (pattern, stats) in enumerate(ranking, 1):
            logger.info("  %d. %s:", i, pattern.replace('_', ' ').title())
            logger.info("     📈 Winrate: %.1f%% (%d/%d)", 
                       stats.winrate * 100, stats.winning_trades, stats.total_trades)
            logger.info("     💰 Profit Factor: %.2f", stats.profit_factor)
            logger.info("     📊 Sharpe Ratio: %.2f", stats.sharpe_ratio)
            logger.info("     🎯 Avg AI Score: %.1f", stats.avg_ai_score)
            logger.info("     ⏱️ Avg Duration: %.1f hours", stats.avg_duration_hours)
            
            if stats.market_regime_performance:
                logger.info("     🌍 Режимы рынка:")
                for regime, winrate in stats.market_regime_performance.items():
                    logger.info("       • %s: %.1f%%", regime, winrate * 100)
        
        # Инсайты для оптимизации
        insights = self.get_optimization_insights()
        if insights["ai_score_correlation"]:
            logger.info("  🧠 КОРРЕЛЯЦИЯ AI-СКОРА:")
            for pattern, corr_data in insights["ai_score_correlation"].items():
                logger.info("    • %s: высокий скор %.1f%% vs низкий %.1f%% (разница: +%.1f%%)", 
                           pattern, 
                           corr_data["high_score_winrate"] * 100,
                           corr_data["low_score_winrate"] * 100,
                           corr_data["correlation_strength"] * 100)
