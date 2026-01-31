#!/usr/bin/env python3
"""
Утилиты для работы с ИИ-оптимизированными параметрами сигналов
"""

import json
import logging
import os
from typing import Dict, Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Путь к файлу с ИИ-оптимизированными параметрами
AI_OPTIMIZED_PARAMETERS_FILE = "ai_learning_data/ai_optimized_parameters.json"


def load_ai_optimized_parameters() -> Dict[str, Any]:
    """Загружает ИИ-оптимизированные параметры из файла."""
    try:
        with open(AI_OPTIMIZED_PARAMETERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            metrics = data.get("metrics", {})
            logger.info("🤖 Загружены ИИ-оптимизированные параметры:")
            logger.info("  • Win Rate: %.1f%%", metrics.get("win_rate", 0.0) * 100)
            logger.info("  • Profit Factor: %.2f", metrics.get("profit_factor", 0.0))
            logger.info("  • Сделок: %d", metrics.get("trades_count", 0))
            return data
    except FileNotFoundError:
        logger.warning("Файл ИИ-оптимизированных параметров не найден. "
                      "Используем параметры по умолчанию.")
        return {
            "parameters": {
                "soft_score_threshold": 15.0,  # Снижено с 25.0 (-40%)
                "strict_score_threshold": 25.0,  # Снижено с 35.0 (-29%)
                "min_volume_usd": 10,  # Минимальный порог для тестирования
                "min_volatility_pct": 0.001,  # Снижено с 0.005 (-80%)
                "max_volatility_pct": 0.25,  # Увеличено с 0.15 (+67%)
                "min_rsi": 30,
                "max_rsi": 70,
                "min_adx": 20,
                "max_adx": 50,
                "ema_fast_period": 20,
                "ema_slow_period": 50,
                "bb_window": 20,
                "bb_std_dev": 2,
                "ai_confidence_threshold": 0.7,
                "risk_per_trade_pct": 0.5,
                "max_leverage": 5,
                "take_profit_multiplier": 1.5,
                "stop_loss_multiplier": 0.75,
            },
            "metrics": {
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "trades_count": 0
            }
        }
    except Exception as e:
        logger.error("Ошибка загрузки ИИ-оптимизированных параметров: %s", e)
        return {}


def get_ai_optimized_parameters(symbol: Optional[str] = None) -> Dict[str, Any]:
    """
    Динамически загружает ИИ-оптимизированные параметры.
    Если указан символ, пытается загрузить специфичные для символа параметры.
    """
    ai_params = load_ai_optimized_parameters()

    if symbol:
        try:
            # Попытка загрузить параметры, специфичные для символа
            symbol_specific_file = f"ai_learning_data/symbol_params/{symbol}.json"
            if os.path.exists(symbol_specific_file):
                with open(symbol_specific_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                symbol_params = data.get("parameters", ai_params.get("parameters", {}))
                logger.debug("✅ Загружены индивидуальные параметры для %s из файла", symbol)
                return {"parameters": symbol_params, "metrics": ai_params.get("metrics", {})}
            else:
                logger.debug("ℹ️ Индивидуальные параметры для %s не найдены, используем общие.", symbol)
        except Exception as e:
            logger.warning("Ошибка загрузки индивидуальных параметров для %s: %s. "
                          "Используем общие.", symbol, e)
    return ai_params


def calculate_ai_signal_score(df: pd.DataFrame, ai_params: Dict[str, Any], symbol: Optional[str] = None) -> float:
    """
    Рассчитывает ИИ-скор сигнала на основе технических индикаторов и ИИ-оптимизированных параметров.
    """
    if df.empty or len(df) < max(ai_params.get("ema_slow_period", 50), ai_params.get("bb_window", 20)) + 1:
        logger.debug("Недостаточно данных для расчета скора для %s", symbol)
        return 0.0

    # ДИАГНОСТИКА: Логируем колонки DataFrame
    logger.debug("🔍 DataFrame для %s содержит колонки: %s", symbol, list(df.columns))

    # Получаем индивидуальные параметры для символа
    current_ai_params = get_ai_optimized_parameters(symbol).get("parameters", {})

    score = 0
    bonus = 0

    # 1. RSI
    if 'rsi' in df.columns and df['rsi'].iloc[-1] > current_ai_params.get("min_rsi", 30):
        score += 15
        if df['rsi'].iloc[-1] < 50:  # Дополнительный бонус за недокупленность
            bonus += 5

    # 2. Volume Ratio (пример)
    if ('volume_ratio' in df.columns and
        df['volume_ratio'].iloc[-1] > current_ai_params.get("soft_volume_ratio", 1.2)):  # Объем выше среднего
        score += 10
        bonus += 3

    # 3. Volatility (ATR%)
    if ('volatility' in df.columns and
        current_ai_params.get("min_volatility_pct", 0.01) < df['volatility'].iloc[-1] <
        current_ai_params.get("max_volatility_pct", 0.10)):
        score += 20
        bonus += 7

    # 4. Trend Strength (ADX)
    if ('trend_strength' in df.columns and
        df['trend_strength'].iloc[-1] > current_ai_params.get("min_adx", 20)):
        score += 15
        bonus += 5

    # 5. Bollinger Bands (пример: цена у нижней границы для лонга)
    if ('bb_lower' in df.columns and
        df['close'].iloc[-1] < df['bb_lower'].iloc[-1]):
        score += 10
        bonus += 4

    # 6. EMA Crossover (пример: бычий кроссовер)
    if ('ema_fast' in df.columns and 'ema_slow' in df.columns and
        df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1]):
        score += 10
        bonus += 3

    # Применяем бонус
    score += bonus

    # ДИАГНОСТИКА: Логируем итоговый score
    logger.debug("📊 Score для %s: %.1f (бонус: %d)", symbol, score, bonus)

    return min(score, 100.0)  # Максимум 100


# Загружаем параметры при старте
ai_optimized_params_global = load_ai_optimized_parameters()
