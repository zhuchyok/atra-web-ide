#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система пересмотра per-symbol параметров
Оставляет индивидуальные настройки только для проблемных тикеров
Решает проблему переоптимизации per-symbol параметров
"""

import os
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)

class PerSymbolOptimizationReview:
    """Система пересмотра per-symbol параметров"""
    
    def __init__(self):
        self.data_dir = "ai_learning_data"
        self.symbol_params_dir = os.path.join(self.data_dir, "symbol_specific_params")
        self.problematic_symbols = set()
        self.healthy_symbols = set()
        
        # Критерии для определения проблемных символов
        self.problematic_criteria = {
            "min_trades": 20,           # Минимум сделок для анализа
            "min_winrate": 0.35,        # Минимальный винрейт (35%)
            "max_loss_pct": -15.0,      # Максимальные потери за период
            "max_drawdown_pct": -25.0,  # Максимальная просадка
            "min_profit_factor": 0.8,   # Минимальный profit factor
            "analysis_period_days": 30   # Период анализа в днях
        }
        
        # Критерии для здоровых символов
        self.healthy_criteria = {
            "min_trades": 15,           # Минимум сделок
            "min_winrate": 0.50,        # Хороший винрейт (50%+)
            "min_profit_factor": 1.2,   # Хороший profit factor
            "max_drawdown_pct": -10.0,  # Небольшая просадка
            "analysis_period_days": 30
        }
    
    def analyze_symbol_performance(self, symbol: str) -> Dict[str, Any]:
        """
        Анализирует производительность символа за последние 30 дней
        
        Returns:
            Dict с метриками производительности
        """
        try:
            # Здесь должна быть интеграция с базой данных
            # Пока используем заглушку для демонстрации логики
            
            # В реальной системе это будет:
            # from database import Database
            # db = Database()
            # performance = db.get_symbol_performance(symbol, since_days=30)
            
            # Заглушка для демонстрации
            performance = {
                "total_trades": 25,
                "winrate": 0.40,
                "profit_factor": 0.85,
                "max_drawdown": -18.5,
                "net_profit": -125.0,
                "avg_trade_duration": 4.2,
                "volatility": 0.15
            }
            
            return performance
            
        except Exception as e:
            logger.error("Ошибка анализа производительности для %s: %s", symbol, e)
            return {}
    
    def classify_symbol(self, symbol: str) -> str:
        """
        Классифицирует символ как проблемный, здоровый или нейтральный
        
        Returns:
            str: "PROBLEMATIC", "HEALTHY", "NEUTRAL"
        """
        try:
            performance = self.analyze_symbol_performance(symbol)
            
            if not performance:
                return "NEUTRAL"
            
            # Проверяем критерии проблемных символов
            is_problematic = (
                performance.get("total_trades", 0) >= self.problematic_criteria["min_trades"] and
                performance.get("winrate", 0) < self.problematic_criteria["min_winrate"] and
                performance.get("profit_factor", 0) < self.problematic_criteria["min_profit_factor"] and
                performance.get("max_drawdown", 0) < self.problematic_criteria["max_drawdown_pct"]
            )
            
            # Проверяем критерии здоровых символов
            is_healthy = (
                performance.get("total_trades", 0) >= self.healthy_criteria["min_trades"] and
                performance.get("winrate", 0) >= self.healthy_criteria["min_winrate"] and
                performance.get("profit_factor", 0) >= self.healthy_criteria["min_profit_factor"] and
                performance.get("max_drawdown", 0) >= self.healthy_criteria["max_drawdown_pct"]
            )
            
            if is_problematic:
                self.problematic_symbols.add(symbol)
                return "PROBLEMATIC"
            elif is_healthy:
                self.healthy_symbols.add(symbol)
                return "HEALTHY"
            else:
                return "NEUTRAL"
                
        except Exception as e:
            logger.error("Ошибка классификации символа %s: %s", symbol, e)
            return "NEUTRAL"
    
    def get_symbols_to_optimize(self) -> List[str]:
        """
        Возвращает список символов, которые нуждаются в индивидуальной оптимизации
        
        Returns:
            List[str]: Список проблемных символов
        """
        try:
            # Получаем все символы с индивидуальными параметрами
            symbols_with_params = []
            if os.path.exists(self.symbol_params_dir):
                for filename in os.listdir(self.symbol_params_dir):
                    if filename.endswith("_params.json"):
                        symbol = filename.replace("_params.json", "")
                        symbols_with_params.append(symbol)
            
            # Анализируем каждый символ
            symbols_to_optimize = []
            symbols_to_remove = []
            
            for symbol in symbols_with_params:
                classification = self.classify_symbol(symbol)
                
                if classification == "PROBLEMATIC":
                    symbols_to_optimize.append(symbol)
                    logger.info("🔴 Символ %s классифицирован как ПРОБЛЕМНЫЙ - требует оптимизации", symbol)
                elif classification == "HEALTHY":
                    symbols_to_remove.append(symbol)
                    logger.info("🟢 Символ %s классифицирован как ЗДОРОВЫЙ - удаляем индивидуальные параметры", symbol)
                else:
                    logger.info("🟡 Символ %s классифицирован как НЕЙТРАЛЬНЫЙ - оставляем как есть", symbol)
            
            return symbols_to_optimize, symbols_to_remove
            
        except Exception as e:
            logger.error("Ошибка получения символов для оптимизации: %s", e)
            return [], []
    
    def remove_healthy_symbol_params(self, symbols_to_remove: List[str]) -> int:
        """
        Удаляет индивидуальные параметры для здоровых символов
        
        Args:
            symbols_to_remove: Список символов для удаления параметров
            
        Returns:
            int: Количество удаленных файлов
        """
        removed_count = 0
        
        try:
            for symbol in symbols_to_remove:
                file_path = os.path.join(self.symbol_params_dir, f"{symbol}_params.json")
                
                if os.path.exists(file_path):
                    # Создаем резервную копию
                    backup_path = file_path + ".backup"
                    os.rename(file_path, backup_path)
                    
                    # Удаляем файл
                    os.remove(backup_path)
                    removed_count += 1
                    
                    logger.info("🗑️ Удалены индивидуальные параметры для %s", symbol)
                    
                    # Обновляем кэш
                    if symbol in self.healthy_symbols:
                        self.healthy_symbols.remove(symbol)
            
            return removed_count
            
        except Exception as e:
            logger.error("Ошибка удаления параметров здоровых символов: %s", e)
            return removed_count
    
    def optimize_problematic_symbols(self, symbols_to_optimize: List[str]) -> Dict[str, Any]:
        """
        Оптимизирует параметры для проблемных символов
        
        Args:
            symbols_to_optimize: Список проблемных символов
            
        Returns:
            Dict с результатами оптимизации
        """
        optimization_results = {
            "optimized_symbols": [],
            "failed_symbols": [],
            "total_optimized": 0
        }
        
        try:
            for symbol in symbols_to_optimize:
                try:
                    # Получаем текущие параметры
                    current_params = self._load_symbol_params(symbol)
                    
                    # Анализируем производительность
                    performance = self.analyze_symbol_performance(symbol)
                    
                    # Генерируем оптимизированные параметры
                    optimized_params = self._generate_optimized_params(symbol, performance, current_params)
                    
                    # Сохраняем новые параметры
                    self._save_symbol_params(symbol, optimized_params)
                    
                    optimization_results["optimized_symbols"].append(symbol)
                    optimization_results["total_optimized"] += 1
                    
                    logger.info("✅ Оптимизированы параметры для %s", symbol)
                    
                except Exception as e:
                    logger.error("Ошибка оптимизации %s: %s", symbol, e)
                    optimization_results["failed_symbols"].append(symbol)
            
            return optimization_results
            
        except Exception as e:
            logger.error("Ошибка оптимизации проблемных символов: %s", e)
            return optimization_results
    
    def _load_symbol_params(self, symbol: str) -> Dict[str, Any]:
        """Загружает текущие параметры символа"""
        try:
            file_path = os.path.join(self.symbol_params_dir, f"{symbol}_params.json")
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {}
                
        except Exception as e:
            logger.error("Ошибка загрузки параметров для %s: %s", symbol, e)
            return {}
    
    def _generate_optimized_params(self, symbol: str, performance: Dict[str, Any], 
                                 current_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерирует оптимизированные параметры для проблемного символа
        
        Args:
            symbol: Символ для оптимизации
            performance: Метрики производительности
            current_params: Текущие параметры
            
        Returns:
            Dict с оптимизированными параметрами
        """
        try:
            # Базовые параметры (общие для всех символов)
            base_params = {
                "rsi_overbought": 75,
                "rsi_oversold": 25,
                "adx_threshold": 15,
                "volume_threshold": 1.0,
                "bb_squeeze_threshold": 0.8,
                "min_distance": 0.15
            }
            
            # Адаптируем параметры на основе производительности
            optimized_params = base_params.copy()
            
            # Если низкий винрейт - ужесточаем фильтры
            if performance.get("winrate", 0) < 0.40:
                optimized_params.update({
                    "rsi_overbought": 70,  # Более строгий RSI
                    "adx_threshold": 18,   # Более строгий ADX
                    "volume_threshold": 1.2,  # Более строгий объем
                    "min_distance": 0.20   # Больше расстояние
                })
            
            # Если высокие потери - снижаем риск
            if performance.get("max_drawdown", 0) < -20:
                optimized_params.update({
                    "risk_multiplier": 0.7,  # Снижаем риск на 30%
                    "max_position_size": 0.5  # Ограничиваем размер позиции
                })
            
            # Если низкий profit factor - улучшаем TP/SL
            if performance.get("profit_factor", 0) < 1.0:
                optimized_params.update({
                    "tp1_multiplier": 1.2,  # Увеличиваем TP1
                    "tp2_multiplier": 1.5,  # Увеличиваем TP2
                    "sl_multiplier": 0.8    # Уменьшаем SL
                })
            
            # Добавляем метаданные
            optimized_params.update({
                "optimization_date": datetime.now().isoformat(),
                "symbol": symbol,
                "performance_metrics": performance,
                "optimization_reason": "problematic_symbol"
            })
            
            return optimized_params
            
        except Exception as e:
            logger.error("Ошибка генерации оптимизированных параметров для %s: %s", symbol, e)
            return current_params
    
    def _save_symbol_params(self, symbol: str, params: Dict[str, Any]) -> bool:
        """Сохраняет параметры символа"""
        try:
            os.makedirs(self.symbol_params_dir, exist_ok=True)
            
            file_path = os.path.join(self.symbol_params_dir, f"{symbol}_params.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(params, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            logger.error("Ошибка сохранения параметров для %s: %s", symbol, e)
            return False
    
    def run_optimization_review(self) -> Dict[str, Any]:
        """
        Запускает полный пересмотр per-symbol параметров
        
        Returns:
            Dict с результатами пересмотра
        """
        try:
            logger.info("🔄 Начинаем пересмотр per-symbol параметров...")
            
            # Получаем символы для оптимизации и удаления
            symbols_to_optimize, symbols_to_remove = self.get_symbols_to_optimize()
            
            # Удаляем параметры здоровых символов
            removed_count = self.remove_healthy_symbol_params(symbols_to_remove)
            
            # Оптимизируем проблемные символы
            optimization_results = self.optimize_problematic_symbols(symbols_to_optimize)
            
            # Формируем отчет
            review_results = {
                "timestamp": datetime.now().isoformat(),
                "symbols_analyzed": len(symbols_to_optimize) + len(symbols_to_remove),
                "problematic_symbols": len(symbols_to_optimize),
                "healthy_symbols_removed": removed_count,
                "optimization_results": optimization_results,
                "summary": {
                    "total_symbols": len(symbols_to_optimize) + len(symbols_to_remove),
                    "optimized": optimization_results["total_optimized"],
                    "removed": removed_count,
                    "failed": len(optimization_results["failed_symbols"])
                }
            }
            
            logger.info("✅ Пересмотр per-symbol параметров завершен:")
            logger.info("  📊 Проанализировано символов: %d", review_results["symbols_analyzed"])
            logger.info("  🔴 Проблемных символов: %d", review_results["problematic_symbols"])
            logger.info("  🟢 Удалено здоровых символов: %d", review_results["healthy_symbols_removed"])
            logger.info("  ✅ Оптимизировано: %d", review_results["summary"]["optimized"])
            logger.info("  ❌ Ошибок: %d", review_results["summary"]["failed"])
            
            return review_results
            
        except Exception as e:
            logger.error("Ошибка в пересмотре per-symbol параметров: %s", e)
            return {"error": str(e)}


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================================

# Создаем глобальный экземпляр системы пересмотра
per_symbol_review = PerSymbolOptimizationReview()

# Функция для запуска пересмотра
def run_per_symbol_optimization_review() -> Dict[str, Any]:
    """
    Запускает пересмотр per-symbol параметров
    
    Returns:
        Dict с результатами пересмотра
    """
    try:
        return per_symbol_review.run_optimization_review()
    except Exception as e:
        logger.error("Ошибка запуска пересмотра per-symbol параметров: %s", e)
        return {"error": str(e)}
