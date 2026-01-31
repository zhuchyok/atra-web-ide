"""
🤖 АДАПТИВНЫЙ РЕГУЛЯТОР ФИЛЬТРОВ (КАЧЕСТВО-ОРИЕНТИРОВАННЫЙ)
Автоматически регулирует пороги RSI, Volume, Quality для МАКСИМИЗАЦИИ КАЧЕСТВА:
- Ужесточает фильтры при низком Win Rate / Profit Factor
- Ослабляет фильтры только при высоком качестве (>75% WR, PF>2.0)
- Адаптируется к рыночным условиям (волатильность, объем)
- Использует AI-оптимизацию для поиска оптимальных порогов

ВАЖНО: Фокус на КАЧЕСТВЕ, а не на количестве сигналов!
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
import pandas as pd

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from src.ai.filter_optimizer import AIFilterOptimizer
    AI_FILTER_OPTIMIZER_AVAILABLE = True
except ImportError:
    AI_FILTER_OPTIMIZER_AVAILABLE = False
    AIFilterOptimizer = None
    logger.warning("⚠️ AIFilterOptimizer недоступен")

try:
    from config import load_ai_optimized_parameters
    AI_PARAMS_AVAILABLE = True
except ImportError:
    AI_PARAMS_AVAILABLE = False
    load_ai_optimized_parameters = None


class AdaptiveFilterRegulator:
    """
    Адаптивный регулятор порогов фильтров
    
    Автоматически регулирует:
    - RSI пороги (70/30 → адаптивные)
    - Volume ratio пороги (1.2 → адаптивные)
    - Quality score пороги (0.68 → адаптивные)
    """
    
    def __init__(self):
        self.ai_optimizer = None
        if AI_FILTER_OPTIMIZER_AVAILABLE and AIFilterOptimizer:
            try:
                self.ai_optimizer = AIFilterOptimizer()
                logger.info("✅ AI Filter Optimizer загружен для адаптивной регуляции")
            except Exception as e:
                logger.warning("⚠️ Не удалось инициализировать AI Filter Optimizer: %s", e)
        
        # 🕵️ Новое: Детектор рыночного режима
        try:
            from src.ai.regime_detection import MarketRegimeDetector
            self.regime_detector = MarketRegimeDetector()
            logger.info("✅ Market Regime Detector интегрирован в регулятор")
        except ImportError:
            self.regime_detector = None
            logger.warning("⚠️ Market Regime Detector недоступен")

        # Базовые пороги (будут адаптироваться)
        self.base_rsi_long_threshold = 70.0
        self.base_rsi_short_threshold = 30.0
        self.base_volume_ratio = 1.2
        self.base_quality_score = 0.68
        
        # Диапазоны для адаптации
        self.rsi_long_range = (65.0, 75.0)  # Может быть от 65 до 75
        self.rsi_short_range = (25.0, 35.0)  # Может быть от 25 до 35
        self.volume_ratio_range = (0.8, 1.5)  # Может быть от 0.8 до 1.5
        self.quality_score_range = (0.60, 0.75)  # Может быть от 0.60 до 0.75
        
        # Текущие адаптированные значения
        self.current_rsi_long = self.base_rsi_long_threshold
        self.current_rsi_short = self.base_rsi_short_threshold
        self.current_volume_ratio = self.base_volume_ratio
        self.current_quality_score = self.base_quality_score
        
        logger.info("🤖 AdaptiveFilterRegulator инициализирован")
    
    async def get_adaptive_rsi_thresholds(
        self,
        df: Optional[pd.DataFrame] = None,
        market_volatility: Optional[float] = None,
        volume_ratio: Optional[float] = None,
        win_rate: Optional[float] = None,
        profit_factor: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Получает адаптивные пороги RSI для МАКСИМИЗАЦИИ КАЧЕСТВА
        """
        try:
            # Начинаем с базовых значений
            rsi_long = self.base_rsi_long_threshold
            rsi_short = self.base_rsi_short_threshold
            
            # 🕵️ Адаптация по рыночному режиму (HMM/Statistical)
            if df is not None and self.regime_detector:
                # 🚀 ИСПРАВЛЕНО: Правильный асинхронный вызов
                res = self.regime_detector.detect_regime(df)
                if asyncio.iscoroutine(res):
                    regime_data = await res
                else:
                    regime_data = res
                
                regime = regime_data.get('regime', 'NORMAL')
                
                if regime == "HIGH_VOL_RANGE":
                    # На высокой волатильности сужаем границы для исключения шума
                    rsi_long -= 2.0
                    rsi_short += 2.0
                    logger.info("🕵️ [REGIME] High Volatility detected -> RSI tightened")
                elif regime == "BULL_TREND":
                    # На бычьем тренде можно чуть ослабить для LONG
                    rsi_long += 2.0
                    logger.info("🕵️ [REGIME] Bull Trend detected -> RSI LONG relaxed")
                elif regime == "BEAR_TREND":
                    # На медвежьем тренде можно чуть ослабить для SHORT
                    rsi_short -= 2.0
                    logger.info("🕵️ [REGIME] Bear Trend detected -> RSI SHORT relaxed")
            
            # 1. ПРИОРИТЕТ: Адаптация по качеству (Win Rate, Profit Factor)
            if win_rate is not None:
                if win_rate < 0.60:  # Низкий Win Rate → УЖЕСТОЧАЕМ
                    rsi_long -= 3.0  # 70 → 67 (более строгий)
                    rsi_short += 3.0  # 30 → 33 (более строгий)
                    logger.info("🔒 [ADAPTIVE RSI] Низкий WR (%.1f%%) → УЖЕСТОЧАЕМ: LONG=%.1f, SHORT=%.1f",
                               win_rate * 100, rsi_long, rsi_short)
                elif win_rate > 0.75 and profit_factor and profit_factor > 2.0:
                    # Высокий WR + PF → Можно немного ослабить (но осторожно!)
                    rsi_long += 1.0  # 70 → 71 (чуть мягче)
                    rsi_short -= 1.0  # 30 → 29 (чуть мягче)
                    logger.info("✅ [ADAPTIVE RSI] Высокий WR (%.1f%%) + PF (%.2f) → Слегка ослабляем: LONG=%.1f, SHORT=%.1f",
                               win_rate * 100, profit_factor, rsi_long, rsi_short)
            
            # 2. Адаптация по волатильности (качество важнее)
            if market_volatility is not None:
                if market_volatility > 4.0:  # Высокая волатильность → УЖЕСТОЧАЕМ
                    rsi_long -= 2.0  # 70 → 68 (избегаем шумных сигналов)
                    rsi_short += 2.0  # 30 → 32
                    logger.debug("📈 [ADAPTIVE RSI] Высокая волатильность → УЖЕСТОЧАЕМ: LONG=%.1f, SHORT=%.1f",
                                rsi_long, rsi_short)
                elif market_volatility < 1.0:  # Низкая волатильность → Стандартные пороги
                    # Не ослабляем, оставляем базовые значения
                    logger.debug("📉 [ADAPTIVE RSI] Низкая волатильность → Стандартные пороги: LONG=%.1f, SHORT=%.1f",
                                rsi_long, rsi_short)
            
            # 3. Адаптация по объему (качество важнее)
            if volume_ratio is not None:
                if volume_ratio < 0.5:  # Очень низкий объем → УЖЕСТОЧАЕМ (избегаем неликвидных сигналов)
                    rsi_long -= 1.0
                    rsi_short += 1.0
                    logger.debug("📊 [ADAPTIVE RSI] Очень низкий объем → УЖЕСТОЧАЕМ: LONG=%.1f, SHORT=%.1f",
                                rsi_long, rsi_short)
                elif volume_ratio > 2.5:  # Очень высокий объем → Можно немного ужесточить
                    rsi_long -= 0.5
                    rsi_short += 0.5
                    logger.debug("📊 [ADAPTIVE RSI] Высокий объем → Слегка ужесточаем: LONG=%.1f, SHORT=%.1f",
                                rsi_long, rsi_short)
            
            # 4. Используем AI-оптимизированные параметры если доступны
            if self.ai_optimizer:
                try:
                    optimized_params = self.ai_optimizer.load_optimized_params()
                    if optimized_params:
                        # AI может предложить свои пороги на основе исторических результатов
                        logger.debug("🤖 [ADAPTIVE RSI] AI параметры доступны")
                except Exception as e:
                    logger.debug("⚠️ Ошибка загрузки AI параметров: %s", e)
            
            # Ограничиваем диапазон
            rsi_long = max(self.rsi_long_range[0], min(self.rsi_long_range[1], rsi_long))
            rsi_short = max(self.rsi_short_range[0], min(self.rsi_short_range[1], rsi_short))
            
            # Обновляем текущие значения
            self.current_rsi_long = rsi_long
            self.current_rsi_short = rsi_short
            
            return rsi_long, rsi_short
            
        except Exception as e:
            logger.error("❌ Ошибка расчета адаптивных RSI порогов: %s", e)
            return self.base_rsi_long_threshold, self.base_rsi_short_threshold
    
    def get_adaptive_volume_ratio(
        self,
        df: Optional[pd.DataFrame] = None,
        market_volatility: Optional[float] = None,
        win_rate: Optional[float] = None,
        profit_factor: Optional[float] = None,
        filter_mode: str = "soft",  # 🆕 Добавлен режим фильтрации
    ) -> float:
        """
        Получает адаптивный порог volume ratio для МАКСИМИЗАЦИИ КАЧЕСТВА
        
        Логика:
        - Низкий Win Rate (<60%) → УЖЕСТОЧАЕМ (требуем больше объема)
        - Высокий Win Rate (>75%) + PF>2.0 → Можно немного ослабить
        - Высокая волатильность → УЖЕСТОЧАЕМ (избегаем шумных сигналов)
        
        Args:
            df: DataFrame с данными (опционально)
            market_volatility: Текущая волатильность (опционально)
            win_rate: Текущий Win Rate (опционально)
            profit_factor: Текущий Profit Factor (опционально)
            filter_mode: Режим фильтрации ("soft" или "strict") 🆕
        
        Returns:
            float: Адаптивный порог volume ratio
        """
        try:
            # 🆕 Диапазоны и базовые значения для разных режимов
            if filter_mode == "soft":
                volume_ratio_range = (0.05, 0.5)  # 🚀 СУПЕР-МЯГКО
                base_volume_ratio = 0.10  # 🚀 СНИЖЕНО до 0.10
            else:
                volume_ratio_range = (0.3, 1.0)  # 🚀 СНИЖЕНО
                base_volume_ratio = 0.4  # 🚀 СНИЖЕНО до 0.4
            
            volume_ratio = base_volume_ratio
            
            # 1. ПРИОРИТЕТ: Адаптация по качеству (Win Rate, Profit Factor)
            if win_rate is not None:
                if win_rate < 0.60:  # Низкий Win Rate → УЖЕСТОЧАЕМ
                    if filter_mode == "soft":
                        volume_ratio = base_volume_ratio * 1.3  # 0.3 → 0.39 (требуем больше объема)
                    else:
                        volume_ratio = 1.4  # Было 1.2 → стало 1.4
                    logger.info("🔒 [ADAPTIVE VOLUME] Низкий WR (%.1f%%) → УЖЕСТОЧАЕМ: ratio=%.2f (mode=%s)",
                               win_rate * 100, volume_ratio, filter_mode)
                elif win_rate > 0.75 and profit_factor and profit_factor > 2.0:
                    # Высокий WR + PF → Можно немного ослабить (но осторожно!)
                    if filter_mode == "soft":
                        volume_ratio = base_volume_ratio * 0.9  # 0.3 → 0.27 (немного ослабляем)
                    else:
                        volume_ratio = 1.1  # Было 1.2 → стало 1.1
                    logger.info("✅ [ADAPTIVE VOLUME] Высокий WR (%.1f%%) + PF (%.2f) → Слегка ослабляем: ratio=%.2f (mode=%s)",
                               win_rate * 100, profit_factor, volume_ratio, filter_mode)
            
            # 2. Адаптация по волатильности
            if market_volatility is not None:
                if market_volatility > 4.0:  # Высокая волатильность → УЖЕСТОЧАЕМ
                    if filter_mode == "soft":
                        volume_ratio = max(volume_ratio, base_volume_ratio * 1.2)  # 0.3 → 0.36
                    else:
                        volume_ratio = max(volume_ratio, 1.4)  # Требуем больше объема
                    logger.debug("📈 [ADAPTIVE VOLUME] Высокая волатильность → УЖЕСТОЧАЕМ: ratio=%.2f (mode=%s)", 
                               volume_ratio, filter_mode)
                elif market_volatility < 1.0:  # Низкая волатильность → Стандартные пороги
                    # Не ослабляем, оставляем базовые значения
                    logger.debug("📉 [ADAPTIVE VOLUME] Низкая волатильность → Стандартные пороги: ratio=%.2f (mode=%s)", 
                               volume_ratio, filter_mode)
            
            # 3. Используем AI-оптимизированные параметры
            if self.ai_optimizer:
                try:
                    optimized_params = self.ai_optimizer.load_optimized_params()
                    if optimized_params:
                        # AI оптимизирует на основе исторических результатов
                        ai_volume_ratio = optimized_params.get("soft_volume_ratio")
                        if ai_volume_ratio:
                            # Используем AI значение, но не ниже текущего (если качество низкое)
                            if win_rate and win_rate < 0.60:
                                volume_ratio = max(volume_ratio, ai_volume_ratio)  # Не ослабляем при низком WR
                            else:
                                volume_ratio = ai_volume_ratio
                            logger.debug("🤖 [ADAPTIVE VOLUME] Используем AI-оптимизированный: %.2f", volume_ratio)
                except Exception as e:
                    logger.debug("⚠️ Ошибка загрузки AI volume параметров: %s", e)
            
            # Ограничиваем диапазон (используем диапазон для текущего режима)
            volume_ratio = max(volume_ratio_range[0], min(volume_ratio_range[1], volume_ratio))
            
            # Обновляем текущее значение
            self.current_volume_ratio = volume_ratio
            
            return volume_ratio
            
        except Exception as e:
            logger.error("❌ Ошибка расчета адаптивного volume ratio: %s", e)
            # Возвращаем базовое значение для текущего режима
            return 0.10 if filter_mode == "soft" else 0.40
    
    def get_adaptive_quality_score(
        self,
        df: Optional[pd.DataFrame] = None,
        market_volatility: Optional[float] = None,
        volume_ratio: Optional[float] = None,
        win_rate: Optional[float] = None,
        profit_factor: Optional[float] = None,
        filter_mode: str = "soft",
    ) -> float:
        """
        Получает адаптивный порог quality score для МАКСИМИЗАЦИИ КАЧЕСТВА
        
        Логика:
        - Низкий Win Rate (<60%) → УЖЕСТОЧАЕМ (требуем выше quality)
        - Высокий Win Rate (>75%) + PF>2.0 → Можно немного ослабить
        - Высокая волатильность → УЖЕСТОЧАЕМ (избегаем шумных сигналов)
        
        Args:
            df: DataFrame с данными (опционально)
            market_volatility: Текущая волатильность (опционально)
            volume_ratio: Текущий volume ratio (опционально)
            win_rate: Текущий Win Rate (опционально)
            profit_factor: Текущий Profit Factor (опционально)
            filter_mode: Режим фильтрации ("soft" или "strict")
        
        Returns:
            float: Адаптивный порог quality score
        """
        try:
            # Базовый порог зависит от режима
            base_quality = 0.65 if filter_mode == "soft" else 0.68
            quality_score = base_quality
            
            # 1. ПРИОРИТЕТ: Адаптация по качеству (Win Rate, Profit Factor)
            if win_rate is not None:
                if win_rate < 0.60:  # Низкий Win Rate → УЖЕСТОЧАЕМ
                    quality_score += 0.05  # 0.68 → 0.73 (требуем выше quality)
                    logger.info("🔒 [ADAPTIVE QUALITY] Низкий WR (%.1f%%) → УЖЕСТОЧАЕМ: score=%.3f",
                               win_rate * 100, quality_score)
                elif win_rate > 0.75 and profit_factor and profit_factor > 2.0:
                    # Высокий WR + PF → Можно немного ослабить (но осторожно!)
                    quality_score -= 0.02  # 0.68 → 0.66
                    logger.info("✅ [ADAPTIVE QUALITY] Высокий WR (%.1f%%) + PF (%.2f) → Слегка ослабляем: score=%.3f",
                               win_rate * 100, profit_factor, quality_score)
            
            # 2. Адаптация по волатильности
            if market_volatility is not None:
                if market_volatility > 4.0:  # Высокая волатильность → УЖЕСТОЧАЕМ
                    quality_score += 0.03  # 0.68 → 0.71 (избегаем шумных сигналов)
                    logger.debug("📈 [ADAPTIVE QUALITY] Высокая волатильность → УЖЕСТОЧАЕМ: score=%.3f", quality_score)
                elif market_volatility < 1.0:  # Низкая волатильность → Стандартные пороги
                    # Не ослабляем, оставляем базовые значения
                    logger.debug("📉 [ADAPTIVE QUALITY] Низкая волатильность → Стандартные пороги: score=%.3f", quality_score)
            
            # 3. Адаптация по объему (качество важнее)
            if volume_ratio is not None:
                if volume_ratio < 0.5:  # Очень низкий объем → УЖЕСТОЧАЕМ
                    quality_score += 0.02
                    logger.debug("📊 [ADAPTIVE QUALITY] Очень низкий объем → УЖЕСТОЧАЕМ: score=%.3f", quality_score)
            
            # 4. Используем AI-оптимизированные параметры
            if AI_PARAMS_AVAILABLE and load_ai_optimized_parameters:
                try:
                    ai_params = load_ai_optimized_parameters()
                    if ai_params and isinstance(ai_params, dict):
                        quality_params = ai_params.get("quality_thresholds", {})
                        if quality_params:
                            adaptive_quality = quality_params.get("long", {}).get(filter_mode)
                            if adaptive_quality:
                                # Используем AI значение, но не ниже текущего (если качество низкое)
                                if win_rate and win_rate < 0.60:
                                    quality_score = max(quality_score, adaptive_quality)  # Не ослабляем при низком WR
                                else:
                                    quality_score = adaptive_quality
                                logger.debug("🤖 [ADAPTIVE QUALITY] Используем AI-оптимизированный: %.3f", quality_score)
                except Exception as e:
                    logger.debug("⚠️ Ошибка загрузки AI quality параметров: %s", e)
            
            # Ограничиваем диапазон
            quality_score = max(self.quality_score_range[0], min(self.quality_score_range[1], quality_score))
            
            # Обновляем текущее значение
            self.current_quality_score = quality_score
            
            return quality_score
            
        except Exception as e:
            logger.error("❌ Ошибка расчета адаптивного quality score: %s", e)
            return base_quality
    
    async def get_all_adaptive_thresholds(
        self,
        df: Optional[pd.DataFrame] = None,
        market_volatility: Optional[float] = None,
        volume_ratio: Optional[float] = None,
        win_rate: Optional[float] = None,
        profit_factor: Optional[float] = None,
        filter_mode: str = "soft",
    ) -> Dict[str, Any]:
        """
        Получает все адаптивные пороги одновременно для МАКСИМИЗАЦИИ КАЧЕСТВА
        
        Args:
            df: DataFrame с данными (опционально)
            market_volatility: Текущая волатильность (опционально)
            volume_ratio: Текущий volume ratio (опционально)
            win_rate: Текущий Win Rate (опционально)
            profit_factor: Текущий Profit Factor (опционально)
            filter_mode: Режим фильтрации ("soft" или "strict")
        
        Returns:
            Dict с адаптивными порогами:
            {
                'rsi_long': float,
                'rsi_short': float,
                'volume_ratio': float,
                'quality_score': float,
            }
        """
        rsi_long, rsi_short = await self.get_adaptive_rsi_thresholds(
            df=df,
            market_volatility=market_volatility,
            volume_ratio=volume_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
        )
        
        adaptive_volume = self.get_adaptive_volume_ratio(
            df=df,
            market_volatility=market_volatility,
            win_rate=win_rate,
            profit_factor=profit_factor,
            filter_mode=filter_mode,  # 🆕 Передаем режим
        )
        
        adaptive_quality = self.get_adaptive_quality_score(
            df=df,
            market_volatility=market_volatility,
            volume_ratio=volume_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            filter_mode=filter_mode,
        )
        
        return {
            'rsi_long': rsi_long,
            'rsi_short': rsi_short,
            'volume_ratio': adaptive_volume,
            'quality_score': adaptive_quality,
        }
    
    def _load_external_improvements(self):
        """Загружает подтвержденные улучшения от Research Lab"""
        try:
            import os
            import json
            import glob
            from datetime import datetime
            
            improvement_dir = "config/improvements"
            if not os.path.exists(improvement_dir):
                return
                
            # Ищем файлы за сегодня
            today = get_utc_now().strftime('%Y%m%d')
            files = glob.glob(f"{improvement_dir}/applied_{today}.json")
            
            for file_path in files:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            hypo = entry.get("hypothesis", {})
                            idea = hypo.get("idea", "")
                            
                            # Парсим идею и применяем к базовым порогам
                            if "RSI для LONG на 15%" in idea:
                                self.base_rsi_long_threshold *= 0.85
                                logger.info("🧪 [RESEARCH] Применено смягчение RSI для LONG (Research Lab)")
                            elif "Quality Score для LONG до 0.85" in idea:
                                self.base_quality_score = 0.85
                                logger.info("🧪 [RESEARCH] Применено увеличение Quality Score (Research Lab)")
                                
                        except Exception as parse_err:
                            logger.error("❌ Ошибка парсинга строки улучшения: %s", parse_err)
                            
        except Exception as e:
            logger.error("❌ Ошибка загрузки внешних улучшений: %s", e)

    async def update_from_ai_optimization(self, metrics: Optional[Dict[str, Any]] = None):
        """
        Обновляет пороги на основе AI-оптимизации и внешних улучшений (Research Lab)
        
        Args:
            metrics: Метрики производительности (опционально, если None - загрузит из БД)
        """
        # 1. Загружаем внешние улучшения от Research Lab
        self._load_external_improvements()

        if not self.ai_optimizer:
            logger.warning("⚠️ AI Optimizer недоступен для обновления порогов")
            return
        
        try:
            # Запускаем оптимизацию
            optimized_params = await self.ai_optimizer.optimize_parameters()
            
            # Обновляем базовые значения на основе оптимизации
            # (AI оптимизирует volume_ratio, но не RSI напрямую, пока)
            if optimized_params and 'soft_volume_ratio' in optimized_params:
                self.base_volume_ratio = optimized_params['soft_volume_ratio']
                logger.info("🤖 [ADAPTIVE] Обновлен base_volume_ratio: %.2f", self.base_volume_ratio)
            
            logger.info("✅ [ADAPTIVE] Пороги обновлены на основе AI-оптимизации")
            
        except Exception as e:
            logger.error("❌ Ошибка обновления порогов из AI: %s", e)


# Глобальный экземпляр регулятора
_adaptive_regulator: Optional[AdaptiveFilterRegulator] = None


def get_adaptive_regulator() -> AdaptiveFilterRegulator:
    """Получает глобальный экземпляр адаптивного регулятора"""
    global _adaptive_regulator
    if _adaptive_regulator is None:
        _adaptive_regulator = AdaptiveFilterRegulator()
    return _adaptive_regulator

