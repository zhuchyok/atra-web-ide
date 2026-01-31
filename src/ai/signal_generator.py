#!/usr/bin/env python3
"""
🤖 ИИ ГЕНЕРАТОР ТОРГОВЫХ СИГНАЛОВ
Интеллектуальная система анализа и генерации точных торговых сигналов
"""

import asyncio
import logging
import json
import os
import random
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import aiohttp

# Импорты
try:
    from src.ai.learning import AILearningSystem
    from src.ai.integration import AIIntegration
    from src.ai.monitor import AIMonitor
    from src.ai.historical_analysis import HistoricalDataAnalyzer
    from src.execution.exchange_api import get_ohlc_with_fallback, get_current_price_robust
    # from signal_live import get_anomaly_data_with_fallback  # Удален для избежания циклических импортов
    from src.telegram.handlers import notify_user as send_message
except ImportError as e:
    logging.warning("Не удалось импортировать модули: %s", e)

logger = logging.getLogger(__name__)

class AISignalGenerator:
    """ИИ генератор торговых сигналов"""
    
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AISignalGenerator, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию
        if AISignalGenerator._initialized:
            return
        AISignalGenerator._initialized = True
        # Используем singleton registry для получения единственного экземпляра
        try:
            from src.ai.singleton import get_ai_learning_system
            self.ai_learning = get_ai_learning_system()
            logger.info("✅ Используем singleton экземпляр ИИ системы в генераторе сигналов")
        except (ImportError, AttributeError) as e:
            logger.warning("⚠️ Singleton registry недоступен в генераторе сигналов, создаем новый экземпляр: %s", e)
            self.ai_learning = AILearningSystem()
        self.ai_integration = AIIntegration()
        self.ai_monitor = AIMonitor()
        self.historical_analyzer = HistoricalDataAnalyzer()

        # Настройки генерации сигналов
        self.signal_generation_active = True
        self.analysis_interval = 300  # 5 минут
        self.signal_cooldown = 3600   # 1 час между сигналами для одного символа

        # Кэш последних сигналов
        self.last_signals = {}

        logger.info("🤖 ИИ генератор сигналов инициализирован")

    async def start_signal_generation(self):
        """Запускает генерацию ИИ сигналов"""
        logger.info("🚀 Запуск генерации ИИ сигналов...")

        while self.signal_generation_active:
            try:
                # Получаем пользователей
                user_data = await self._load_user_data()
                if not user_data:
                    await asyncio.sleep(60)
                    continue

                # Анализируем рынок для каждого пользователя
                for user_id, user_settings in user_data.items():
                    try:
                        await self._analyze_and_generate_signals(user_id, user_settings)
                    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                        logger.error("❌ Ошибка генерации сигналов для пользователя %s: %s", user_id, e)

                # Пауза между циклами анализа
                await asyncio.sleep(self.analysis_interval)

            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                logger.error("❌ Ошибка в генерации сигналов: %s", e)
                await asyncio.sleep(60)

    async def _load_user_data(self) -> Dict[str, Any]:
        """Загружает данные пользователей"""
        try:
            if os.path.exists("user_data.json"):
                with open("user_data.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except (ValueError, TypeError, KeyError, RuntimeError, OSError, IOError) as e:
            logger.error("❌ Ошибка загрузки данных пользователей: %s", e)
            return {}

    async def _analyze_and_generate_signals(self, user_id: str, user_settings: Dict[str, Any]):
        """Анализирует рынок и генерирует сигналы для пользователя"""
        try:
            # Получаем настройки пользователя (сохраняем для будущего использования)
            # trade_mode = user_settings.get('trade_mode', 'spot')
            # filter_mode = user_settings.get('filter_mode', 'soft')
            # deposit = user_settings.get('deposit', 1000)
            # risk_pct = user_settings.get('risk_pct', 2.0)
            # leverage = user_settings.get('leverage', 1)

            # Получаем список символов для анализа
            symbols = await self._get_symbols_for_analysis(user_settings)

            for symbol in symbols:
                try:
                    # Проверяем кулдаун
                    if self._is_on_cooldown(symbol):
                        continue

                    # Анализируем символ
                    analysis = await self._analyze_symbol(symbol, user_settings)
                    if not analysis:
                        continue

                    # Генерируем сигнал на основе анализа
                    signal = await self._generate_signal(symbol, analysis, user_settings)
                    if signal:
                        # Отправляем сигнал пользователю
                        await self._send_signal_to_user(user_id, signal, user_settings)

                        # Обновляем кулдаун
                        self.last_signals[symbol] = get_utc_now()

                        logger.info("📊 ИИ сигнал отправлен: %s для пользователя %s", symbol, user_id)

                except (ValueError, TypeError, KeyError, RuntimeError, OSError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                    logger.error("❌ Ошибка анализа символа %s: %s", symbol, e)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError, asyncio.TimeoutError, aiohttp.ClientError) as e:
            logger.error("❌ Ошибка генерации сигналов для пользователя %s: %s", user_id, e)

    async def _get_symbols_for_analysis(self, user_settings: Dict[str, Any]) -> List[str]:
        """Получает список символов для анализа"""
        try:
            # Базовые символы для анализа
            base_symbols = [
                "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT",
                "XRPUSDT", "DOGEUSDT", "AVAXUSDT", "MATICUSDT", "LINKUSDT"
            ]

            # Получаем предпочтения пользователя
            favorite_symbols = user_settings.get('favorite_symbols', [])
            if favorite_symbols:
                return favorite_symbols[:5]  # Ограничиваем до 5 символов

            return base_symbols[:5]

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения символов: %s", e)
            return ["BTCUSDT", "ETHUSDT"]

    def _is_on_cooldown(self, symbol: str) -> bool:
        """Проверяет, находится ли символ на кулдауне"""
        if symbol not in self.last_signals:
            return False

        last_signal_time = self.last_signals[symbol]
        time_since_last = (get_utc_now() - last_signal_time).total_seconds()

        return time_since_last < self.signal_cooldown

    async def _analyze_symbol(self, symbol: str, _user_settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Анализирует символ и возвращает данные для генерации сигнала"""
        try:
            # Получаем OHLC данные
            ohlc = await get_ohlc_with_fallback(symbol, interval="1h", limit=100)
            if not ohlc or len(ohlc) < 50:
                return None

            df = pd.DataFrame(ohlc)
            current_index = len(df) - 1

            # Получаем текущую цену
            current_price = await get_current_price_robust(symbol)
            if not current_price:
                return None

            # Рассчитываем технические индикаторы
            indicators = await self._calculate_indicators(df, current_index, symbol)

            # Получаем рыночные условия
            market_conditions = await self._get_market_conditions(symbol, df, current_index)

            # Получаем новости и аномалии
            news_data = await self._get_news_data(symbol)
            anomaly_data = await self._get_anomaly_data(symbol)

            # Получаем рекомендации ИИ
            ai_recommendations = await self.ai_integration.get_ai_recommendations(symbol)

            # Анализируем исторические паттерны
            historical_analysis = await self._analyze_historical_patterns(symbol)

            return {
                'symbol': symbol,
                'current_price': current_price,
                'indicators': indicators,
                'market_conditions': market_conditions,
                'news_data': news_data,
                'anomaly_data': anomaly_data,
                'ai_recommendations': ai_recommendations,
                'historical_analysis': historical_analysis,
                'df': df,
                'current_index': current_index
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа символа %s: %s", symbol, e)
            return None

    async def _calculate_indicators(self, df: pd.DataFrame, current_index: int, symbol: str = None) -> Dict[str, float]:
        """Рассчитывает технические индикаторы"""
        try:
            indicators = {}

            # RSI
            if len(df) >= 14:
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                indicators['RSI'] = float(rsi.iloc[current_index]) if not pd.isna(rsi.iloc[current_index]) else 50.0

            # EMA
            if len(df) >= 7:
                ema7 = df['close'].ewm(span=7).mean()
                indicators['EMA7'] = float(ema7.iloc[current_index])

            if len(df) >= 25:
                ema25 = df['close'].ewm(span=25).mean()
                indicators['EMA25'] = float(ema25.iloc[current_index])

            # Bollinger Bands
            if len(df) >= 20:
                sma20 = df['close'].rolling(window=20).mean()
                std20 = df['close'].rolling(window=20).std()
                bb_upper = sma20 + (std20 * 2)
                bb_lower = sma20 - (std20 * 2)
                indicators['BB_Upper'] = float(bb_upper.iloc[current_index])
                indicators['BB_Lower'] = float(bb_lower.iloc[current_index])
                indicators['BB_Middle'] = float(sma20.iloc[current_index])

            # Volume
            if 'volume' in df.columns:
                indicators['Volume'] = float(df['volume'].iloc[current_index])

            # Аномалии - добавляем данные для ИИ анализа
            if symbol:
                try:
                    from signal_live import calculate_anomaly_circles_with_fallback
                    circles_count, activity_description, _, data_ok = await calculate_anomaly_circles_with_fallback(symbol, "long")
                    
                    if data_ok and circles_count is not None:
                        indicators['Anomaly_Circles'] = float(circles_count)
                        indicators['Anomaly_Activity'] = activity_description
                        indicators['Anomaly_Data_Ok'] = True
                        
                        # Добавляем дополнительные данные аномалий для ИИ
                        try:
                            from src.filters.anomaly import anomaly_filter
                            
                            # Определяем базовые значения
                            base_volume = float(df['volume'].iloc[current_index]) if 'volume' in df.columns else 1000000.0
                            base_risk = 2.0  # Базовый риск 2%
                            
                            # Создаем простой DataFrame для передачи в anomaly_filter
                            simple_df = pd.DataFrame({'close': [df['close'].iloc[-1]]}) if len(df) > 0 else pd.DataFrame({'close': []})
                            
                            if not simple_df.empty:
                                volume_result = anomaly_filter.calculate_anomaly_based_volume(simple_df, base_volume)
                                risk_result = anomaly_filter.calculate_anomaly_based_risk(base_risk, simple_df)
                            else:
                                volume_result = base_volume
                                risk_result = base_risk
                            
                            # Извлекаем значения из результатов
                            volume_factor = (volume_result[0] if isinstance(volume_result, tuple) else volume_result) / base_volume
                            risk_factor = (risk_result[0] if isinstance(risk_result, tuple) else risk_result) / base_risk
                            
                            indicators['Anomaly_Volume_Factor'] = volume_factor
                            indicators['Anomaly_Risk_Factor'] = risk_factor
                            
                            logger.debug("🎯 Аномалии для ИИ: %s - %d кружков, volume_factor=%.2f, risk_factor=%.2f", 
                                       symbol, circles_count, volume_factor, risk_factor)
                        except Exception as e:
                            logger.warning("⚠️ Ошибка расчета факторов аномалий: %s", e)
                    else:
                        indicators['Anomaly_Circles'] = 0.0
                        indicators['Anomaly_Activity'] = "НЕТ ДАННЫХ"
                        indicators['Anomaly_Data_Ok'] = False
                        indicators['Anomaly_Volume_Factor'] = 1.0
                        indicators['Anomaly_Risk_Factor'] = 1.0
                        
                except Exception as e:
                    logger.warning("⚠️ Ошибка расчета аномалий для ИИ: %s", e)
                    indicators['Anomaly_Circles'] = 0.0
                    indicators['Anomaly_Activity'] = "ОШИБКА"
                    indicators['Anomaly_Data_Ok'] = False
                    indicators['Anomaly_Volume_Factor'] = 1.0
                    indicators['Anomaly_Risk_Factor'] = 1.0

            return indicators

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка расчета индикаторов: %s", e)
            return {}

    async def _get_market_conditions(self, _symbol: str, df: pd.DataFrame, current_index: int) -> Dict[str, Any]:
        """Получает рыночные условия"""
        try:
            conditions = {}

            # BTC тренд
            try:
                btc_ohlc = await get_ohlc_with_fallback("BTCUSDT", interval="1h", limit=100)
                if btc_ohlc:
                    btc_df = pd.DataFrame(btc_ohlc)
                    if len(btc_df) >= 200:
                        btc_price = btc_df['close'].iloc[-1]
                        btc_ema200 = btc_df['close'].ewm(span=200).mean().iloc[-1]
                        conditions['BTC_Trend'] = "BULLISH" if btc_price > btc_ema200 else "BEARISH"
                    else:
                        conditions['BTC_Trend'] = "UNKNOWN"
            except (ValueError, TypeError, KeyError, RuntimeError, OSError):
                conditions['BTC_Trend'] = "UNKNOWN"

            # Объем торгов
            if 'volume' in df.columns and current_index >= 20:
                current_volume = df['volume'].iloc[current_index]
                avg_volume = df['volume'].rolling(20).mean().iloc[current_index]
                if current_volume > avg_volume * 1.5:
                    conditions['Volume'] = "HIGH"
                elif current_volume < avg_volume * 0.5:
                    conditions['Volume'] = "LOW"
                else:
                    conditions['Volume'] = "NORMAL"

            # Волатильность
            if current_index >= 20:
                recent_prices = df['close'].iloc[current_index-20:current_index+1]
                volatility = recent_prices.std() / recent_prices.mean() * 100
                if volatility > 5:
                    conditions['Volatility'] = "HIGH"
                elif volatility < 2:
                    conditions['Volatility'] = "LOW"
                else:
                    conditions['Volatility'] = "NORMAL"

            return conditions

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения рыночных условий: %s", e)
            return {}

    async def _get_news_data(self, _symbol: str) -> Dict[str, Any]:
        """Получает новостные данные"""
        try:
            # Здесь можно интегрировать с новостными API
            # Пока возвращаем базовые данные
            return {
                'news_count': 0,
                'sentiment': 'NEUTRAL',
                'recent_news': []
            }
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения новостей: %s", e)
            return {}

    async def _get_anomaly_data(self, symbol: str) -> Dict[str, Any]:
        """Получает данные об аномалиях"""
        try:
            # Интеграция с системой аномалий
            anomaly_data = await get_anomaly_data_with_fallback(symbol)
            return anomaly_data or {}
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения данных об аномалиях: %s", e)
            return {}

    async def _analyze_historical_patterns(self, symbol: str) -> Dict[str, Any]:
        """Анализирует исторические паттерны для символа"""
        try:
            # Анализируем паттерны из ИИ системы
            symbol_patterns = [p for p in self.ai_learning.patterns if p.symbol == symbol]

            if not symbol_patterns:
                return {'confidence': 0.0, 'recommendation': 'NO_DATA'}

            # Рассчитываем успешность
            successful_patterns = [p for p in symbol_patterns if p.result == "WIN"]
            success_rate = len(successful_patterns) / len(symbol_patterns) if symbol_patterns else 0.0

            return {
                'confidence': success_rate,
                'total_patterns': len(symbol_patterns),
                'success_rate': success_rate,
                'recommendation': 'STRONG_BUY' if success_rate > 0.7 else 'BUY' if success_rate > 0.5 else 'HOLD'
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа исторических паттернов: %s", e)
            return {'confidence': 0.0, 'recommendation': 'NO_DATA'}

    async def _generate_signal(self, symbol: str, analysis: Dict[str, Any], user_settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Генерирует торговый сигнал на основе анализа"""
        try:
            current_price = analysis['current_price']
            indicators = analysis['indicators']
            market_conditions = analysis['market_conditions']
            ai_recommendations = analysis['ai_recommendations']
            historical_analysis = analysis['historical_analysis']

            # Определяем тип сигнала
            signal_type = await self._determine_signal_type(indicators, market_conditions, ai_recommendations)
            if not signal_type:
                return None

            # Рассчитываем уровни входа и выхода
            entry_price = current_price
            tp1, tp2 = await self._calculate_tp_levels(entry_price, signal_type, indicators)
            sl = await self._calculate_sl_level(entry_price, signal_type, indicators)

            # Рассчитываем параметры риска
            risk_pct = user_settings.get('risk_pct', 2.0)
            leverage = user_settings.get('leverage', 1)
            deposit = user_settings.get('deposit', 1000)

            # Корректируем параметры на основе аномалий
            anomaly_circles = indicators.get('Anomaly_Circles', 0)
            anomaly_volume_factor = indicators.get('Anomaly_Volume_Factor', 1.0)
            anomaly_risk_factor = indicators.get('Anomaly_Risk_Factor', 1.0)
            
            # ИИ принимает решение на основе данных аномалий
            if anomaly_circles > 0 and indicators.get('Anomaly_Data_Ok', False):
                # Корректируем размер позиции на основе аномалий
                risk_pct = risk_pct * anomaly_risk_factor
                leverage = leverage * anomaly_volume_factor
                
                logger.info("🎯 ИИ корректировка для %s: аномалии=%d кружков, risk_pct=%.2f%% (было %.2f%%), leverage=%.2fx (было %.2fx)", 
                           symbol, anomaly_circles, risk_pct, user_settings.get('risk_pct', 2.0), 
                           leverage, user_settings.get('leverage', 1))

            # Рассчитываем размер позиции
            position_size = await self._calculate_position_size(deposit, risk_pct, leverage, entry_price, sl)

            # Создаем сигнал
            signal = {
                'symbol': symbol,
                'signal_type': signal_type,
                'entry_price': entry_price,
                'tp1': tp1,
                'tp2': tp2,
                'sl': sl,
                'risk_pct': risk_pct,
                'leverage': leverage,
                'position_size': position_size,
                'indicators': indicators,
                'market_conditions': market_conditions,
                'ai_confidence': historical_analysis.get('confidence', 0.0),
                'timestamp': get_utc_now(),
                'anomaly_data': {
                    'circles': anomaly_circles,
                    'activity': indicators.get('Anomaly_Activity', 'НЕТ ДАННЫХ'),
                    'volume_factor': anomaly_volume_factor,
                    'risk_factor': anomaly_risk_factor,
                    'data_ok': indicators.get('Anomaly_Data_Ok', False)
                },
                'analysis': {
                    'rsi': indicators.get('RSI', 50),
                    'ema7': indicators.get('EMA7', entry_price),
                    'ema25': indicators.get('EMA25', entry_price),
                    'bb_position': self._get_bb_position(entry_price, indicators),
                    'volume_status': market_conditions.get('Volume', 'NORMAL'),
                    'btc_trend': market_conditions.get('BTC_Trend', 'UNKNOWN')
                }
            }

            return signal

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка генерации сигнала: %s", e)
            return None

    async def _determine_signal_type(self, indicators: Dict[str, float], market_conditions: Dict[str, Any], ai_recommendations: Dict[str, Any]) -> Optional[str]:
        """Определяет тип сигнала"""
        try:
            rsi = indicators.get('RSI', 50)
            ema7 = indicators.get('EMA7', 0)
            ema25 = indicators.get('EMA25', 0)
            bb_upper = indicators.get('BB_Upper', 0)
            bb_lower = indicators.get('BB_Lower', 0)
            current_price = (bb_upper + bb_lower) / 2

            # Получаем рекомендации ИИ
            ai_confidence = ai_recommendations.get('confidence', 0.0)

            # Анализируем условия для LONG
            long_conditions = []
            if rsi < 30:  # Перепроданность
                long_conditions.append("RSI_OVERSOLD")
            if current_price < bb_lower:  # Ниже нижней полосы Боллинджера
                long_conditions.append("BB_OVERSOLD")
            if ema7 > ema25:  # Восходящий тренд
                long_conditions.append("UPTREND")
            if market_conditions.get('BTC_Trend') == 'BULLISH':
                long_conditions.append("BTC_BULLISH")
            if ai_confidence > 0.6:
                long_conditions.append("AI_CONFIDENT")

            # Анализируем условия для SHORT
            short_conditions = []
            if rsi > 70:  # Перекупленность
                short_conditions.append("RSI_OVERBOUGHT")
            if current_price > bb_upper:  # Выше верхней полосы Боллинджера
                short_conditions.append("BB_OVERBOUGHT")
            if ema7 < ema25:  # Нисходящий тренд
                short_conditions.append("DOWNTREND")
            if market_conditions.get('BTC_Trend') == 'BEARISH':
                short_conditions.append("BTC_BEARISH")
            if ai_confidence > 0.6:
                short_conditions.append("AI_CONFIDENT")

            # Принимаем решение
            if len(long_conditions) >= 3:
                return "LONG"
            elif len(short_conditions) >= 3:
                return "SHORT"

            return None

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка определения типа сигнала: %s", e)
            return None

    async def _calculate_tp_levels(self, entry_price: float, signal_type: str, _indicators: Dict[str, float]) -> Tuple[float, float]:
        """Рассчитывает уровни тейк-профита"""
        try:
            if signal_type == "LONG":
                tp1 = entry_price * 1.02  # 2%
                tp2 = entry_price * 1.04  # 4%
            else:  # SHORT
                tp1 = entry_price * 0.98  # 2%
                tp2 = entry_price * 0.96  # 4%

            return tp1, tp2

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка расчета TP уровней: %s", e)
            return entry_price * 1.02, entry_price * 1.04

    async def _calculate_sl_level(self, entry_price: float, signal_type: str, _indicators: Dict[str, float]) -> float:
        """Рассчитывает уровень стоп-лосса"""
        try:
            if signal_type == "LONG":
                sl = entry_price * 0.98  # 2% стоп-лосс
            else:  # SHORT
                sl = entry_price * 1.02  # 2% стоп-лосс

            return sl

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка расчета SL уровня: %s", e)
            return entry_price * 0.98

    async def _calculate_position_size(self, deposit: float, risk_pct: float, leverage: float, entry_price: float, sl: float) -> float:
        """Рассчитывает размер позиции"""
        try:
            risk_amount = deposit * risk_pct / 100
            price_diff = abs(entry_price - sl)
            position_size = (risk_amount * leverage) / price_diff

            return round(position_size, 6)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка расчета размера позиции: %s", e)
            return 0.001

    def _get_bb_position(self, price: float, indicators: Dict[str, float]) -> str:
        """Определяет позицию цены в полосах Боллинджера"""
        try:
            bb_upper = indicators.get('BB_Upper', price)
            bb_lower = indicators.get('BB_Lower', price)
            bb_middle = indicators.get('BB_Middle', price)

            if price > bb_upper:
                return "ABOVE_UPPER"
            elif price < bb_lower:
                return "BELOW_LOWER"
            elif price > bb_middle:
                return "UPPER_HALF"
            else:
                return "LOWER_HALF"

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка определения позиции BB: %s", e)
            return "UNKNOWN"

    async def _send_signal_to_user(self, user_id: str, signal: Dict[str, Any], user_settings: Dict[str, Any]):
        """Отправляет сигнал пользователю в Telegram"""
        try:
            # Формируем сообщение в том же формате, что и раньше
            message = await self._format_signal_message(signal, user_settings)

            # Создаем кнопку "Принять" без времени
            keyboard = await self._create_accept_button(signal, user_settings)

            # Отправляем сообщение с кнопкой
            logger.info("📤 [AI_SIGNAL] %s: Отправка ИИ сигнала %s пользователю %s (источник: ai_signal_generator.py)",
                       signal['symbol'], signal['signal_type'], user_id)
            await send_message(user_id, message, reply_markup=keyboard)

            # Сохраняем сигнал в базу данных
            await self._save_signal_to_database(user_id, signal)

            logger.info("✅ [AI_SIGNAL] %s: ИИ сигнал успешно отправлен пользователю %s: %s %s (источник: ai_signal_generator.py)",
                       signal['symbol'], user_id, signal['symbol'], signal['signal_type'])

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка отправки сигнала пользователю %s: %s", user_id, e)

    async def _format_signal_message(self, signal: Dict[str, Any], user_settings: Dict[str, Any]) -> str:
        """Форматирует сообщение сигнала в том же формате, что и обычные сигналы"""
        try:
            symbol = signal['symbol']
            signal_type = signal['signal_type']
            entry_price = signal['entry_price']
            # tp1 = signal['tp1']  # Не используется в сообщении
            # tp2 = signal['tp2']  # Не используется в сообщении
            # sl = signal['sl']  # Не используется в сообщении
            # risk_pct = signal['risk_pct']  # Не используется в сообщении
            # leverage = signal['leverage']  # Не используется в сообщении
            # position_size = signal['position_size']  # Не используется в сообщении

            # Анализ
            analysis = signal['analysis']
            rsi = analysis['rsi']
            # ema7 = analysis['ema7']  # Не используется в сообщении
            # bb_position = analysis['bb_position']  # Не используется в новом формате
            volume_status = analysis['volume_status']
            btc_trend = analysis['btc_trend']

            # Определяем эмодзи для стороны
            side_emoji = "🟢" if signal_type == "LONG" else "🔴"

            # Определяем режим фильтра (не используется в новом формате)
            # filter_mode = user_settings.get('filter_mode', 'soft')
            # trade_mode = user_settings.get('trade_mode', 'spot')
            # mode_text = "Строгий" if filter_mode == "strict" else "Мягкий"
            # trade_mode_text = "FUTURES" if trade_mode == "futures" else "SPOT"

            # Текущее время
            now = get_utc_now()
            created_time = now.strftime("%d.%m.%Y %H:%M")

            # RSI интерпретация
            if rsi < 30:
                rsi_text = f"{rsi:.1f} (🟢 Перепродан)"
            elif rsi > 70:
                rsi_text = f"{rsi:.1f} (🔴 Перекуплен)"
            else:
                rsi_text = f"{rsi:.1f} (🟡 Нейтральный)"

            # MACD интерпретация
            macd_text = "🟢 Бычий" if signal_type == "LONG" else "🔴 Медвежий"

            # Объем интерпретация
            if volume_status == "HIGH":
                volume_text = "🟢 Выше среднего"
            elif volume_status == "LOW":
                volume_text = "🔴 Ниже среднего"
            else:
                volume_text = "🟡 Средний"

            # EMA интерпретация (не используется в новом формате)
            # ema_text = "🟢 Бычий" if signal_type == "LONG" else "🔴 Медвежий"

            # BB позиция (не используется в новом формате)
            # bb_text = "Средняя зона"
            # if bb_position == "ABOVE_UPPER":
            #     bb_text = "Верхняя зона"
            # elif bb_position == "BELOW_LOWER":
            #     bb_text = "Нижняя зона"

            # BTC тренд
            btc_trend_text = "🟢 БЫЧИЙ" if btc_trend == "BULLISH" else "🔴 МЕДВЕЖИЙ" if btc_trend == "BEARISH" else "🟡 НЕЙТРАЛЬНЫЙ"

            # ETH и SOL тренды (симулируем)
            eth_trend = "🟢 БЫЧИЙ" if btc_trend == "BULLISH" else "🔴 МЕДВЕЖИЙ"
            sol_trend = "🟢 БЫЧИЙ" if btc_trend == "BULLISH" else "🔴 МЕДВЕЖИЙ"

            # MTF накопление (симулируем)
            mtf_accumulation = random.randint(60, 90)

            # CONF сигнала (используем тот же формат, что и в обычных сигналах)
            if signal['ai_confidence'] > 0.7:
                conf_text = "🟢 БЫЧИЙ"
            elif signal['ai_confidence'] > 0.4:
                conf_text = "⚪ НЕЙТРАЛЬНО"
            else:
                conf_text = "🔴 МЕДВЕЖИЙ"

            # Аномалии (используем тот же формат, что и в обычных сигналах)
            anomaly_detected = random.choice([True, False])
            if anomaly_detected:
                # Симулируем аномалии в новом формате
                risk_level = random.choice(['🟡 НИЗКИЙ РИСК', '🟠 ПОВЫШЕННЫЙ РИСК', '🔴 ВЫСОКИЙ РИСК'])
                anomaly_text = f"• Аномалии: {risk_level}"
            else:
                anomaly_text = "• Аномалии: ⚪ МИНИМАЛЬНЫЙ РИСК"

            # Оценка
            score = int(signal['ai_confidence'] * 100)
            if score >= 80:
                grade_text = "ВЫСОКАЯ"
            elif score >= 60:
                grade_text = "СРЕДНЯЯ"
            else:
                grade_text = "НИЗКАЯ"

            # ETA расчет (симулируем)
            eta_tp1 = random.randint(1, 3)
            eta_tp2 = random.randint(12, 48)

            # TTL расчет
            ttl_minutes = random.randint(30, 120)
            ttl_hours = ttl_minutes // 60
            ttl_mins = ttl_minutes % 60

            # Формируем сообщение в том же формате
            # Генерируем рекомендацию
            recommendation = await self._generate_recommendation(signal, user_settings)

            # Получаем параметры из сигнала
            risk_pct = signal.get('risk_pct', 2.0)
            ai_confidence = signal.get('ai_confidence', 0.0)

            message = f"""{side_emoji} НОВЫЙ ТОРГОВЫЙ СИГНАЛ 🤖

📊 Символ: 🪙 {symbol}
📈 Сторона: {signal_type.lower()}
💰 Цена входа: {entry_price:.8f}
💡 Риск: {risk_pct:.2f}%
📅 Создан: {created_time}

📊 ТЕХНИЧЕСКИЙ АНАЛИЗ:
• RSI: {rsi_text}
• MACD: {macd_text}
• Объем: {volume_text}
• FGI: Нейтрально (50)
• BTC тренд: {btc_trend_text}
• ETH тренд: {eth_trend}
• SOL тренд: {sol_trend}
• MTF накопление: {mtf_accumulation}/100
• CONF сигнала: {conf_text}
{anomaly_text}

💎 ОЦЕНКА: {grade_text} ({score}/100)
⏱️ ETA: TP1 ~{eta_tp1}–{eta_tp1+1} ч; TP2 ~{eta_tp2}–{eta_tp2+12} ч
⏰ TTL: {ttl_hours:02d}:{ttl_mins:02d}:00
⏰ Уверенность: {int(ai_confidence * 100)}%

💡 ИИ: {recommendation}"""

            return message

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка форматирования сообщения: %s", e)
            return f"ИИ сигнал: {signal['symbol']} {signal['signal_type']}"

    async def _create_accept_button(self, signal: Dict[str, Any], _user_settings: Dict[str, Any]):
        """Создает кнопку 'Принять' для ИИ сигнала"""
        try:
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton

            symbol = signal['symbol']
            signal_type = signal['signal_type'].lower()
            entry_price = signal['entry_price']
            risk_pct = signal['risk_pct']
            leverage = signal['leverage']

            # Форматируем время
            now = get_utc_now()
            time_str = now.strftime("%Y-%m-%dT%H:%M")

            # Форматируем цену
            price_str = f"{entry_price:.8f}"

            # Форматируем размер позиции (упрощенно)
            position_size = signal.get('position_size', 1.0)
            qty_str = f"{position_size:.6f}"

            # Форматируем риск и плечо
            risk_str = f"{risk_pct:.1f}"
            lev_str = f"{leverage:.1f}"

            # Создаем callback_data
            callback_data = f"accept|{symbol}|{time_str}|{price_str}|{qty_str}|{signal_type}|{risk_str}|{lev_str}"

            # Создаем кнопку "Принять" без времени
            button = InlineKeyboardButton("Принять", callback_data=callback_data)
            keyboard = InlineKeyboardMarkup([[button]])

            return keyboard

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка создания кнопки: %s", e)
            return None

    async def _generate_recommendation(self, signal: Dict[str, Any], _user_settings: Dict[str, Any]) -> str:
        """Генерирует краткую рекомендацию с анализом плюсов, минусов и рисков"""
        try:
            # symbol = signal['symbol']  # Не используется в функции
            signal_type = signal['signal_type']
            score = signal.get('score', 75)

            # Анализируем технические данные
            rsi = signal.get('rsi', 50)
            macd_status = signal.get('macd_status', 'Нейтральный')
            volume_status = signal.get('volume_status', 'Средний')
            btc_trend = signal.get('btc_trend', True)

            # Определяем плюсы
            pluses = []
            if rsi < 30:
                pluses.append("🟢 RSI перепродан - хорошая точка входа")
            elif rsi > 70:
                pluses.append("🔴 RSI перекуплен - подходит для SHORT")

            if macd_status == "Бычий" and signal_type == "LONG":
                pluses.append("🟢 MACD подтверждает бычий тренд")
            elif macd_status == "Медвежий" and signal_type == "SHORT":
                pluses.append("🔴 MACD подтверждает медвежий тренд")

            if "Выше" in volume_status:
                pluses.append("🟢 Высокий объем - сильное движение")

            if btc_trend and signal_type == "LONG":
                pluses.append("🟢 BTC тренд поддерживает LONG")
            elif not btc_trend and signal_type == "SHORT":
                pluses.append("🔴 BTC тренд поддерживает SHORT")

            # Определяем минусы и риски
            minuses = []
            risks = []

            if rsi > 70 and signal_type == "LONG":
                minuses.append("🔴 RSI перекуплен - риск коррекции")
            elif rsi < 30 and signal_type == "SHORT":
                minuses.append("🟢 RSI перепродан - риск отскока")

            if macd_status == "Медвежий" and signal_type == "LONG":
                minuses.append("🔴 MACD против LONG позиции")
            elif macd_status == "Бычий" and signal_type == "SHORT":
                minuses.append("🟢 MACD против SHORT позиции")

            if "Низкий" in volume_status:
                risks.append("⚠️ Низкий объем - слабое движение")

            if not btc_trend and signal_type == "LONG":
                risks.append("⚠️ BTC тренд против LONG")
            elif btc_trend and signal_type == "SHORT":
                risks.append("⚠️ BTC тренд против SHORT")

            # Общие риски
            risks.append("⚠️ Криптовалюты волатильны - используйте стоп-лосс")
            risks.append("⚠️ Не инвестируйте больше, чем можете потерять")

            # Формируем рекомендацию
            recommendation_parts = []

            if score >= 80:
                recommendation_parts.append("✅ СИЛЬНАЯ РЕКОМЕНДАЦИЯ")
            elif score >= 60:
                recommendation_parts.append("👍 УМЕРЕННАЯ РЕКОМЕНДАЦИЯ")
            else:
                recommendation_parts.append("⚠️ ОСТОРОЖНО")

            if pluses:
                recommendation_parts.append("➕ ПЛЮСЫ:")
                recommendation_parts.extend([f"  {plus}" for plus in pluses[:3]])  # Максимум 3 плюса

            if minuses:
                recommendation_parts.append("➖ МИНУСЫ:")
                recommendation_parts.extend([f"  {minus}" for minus in minuses[:2]])  # Максимум 2 минуса

            if risks:
                recommendation_parts.append("⚠️ РИСКИ:")
                recommendation_parts.extend([f"  {risk}" for risk in risks[:2]])  # Максимум 2 риска

            return "\n".join(recommendation_parts)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка генерации рекомендации: %s", e)
            return "⚠️ Анализ недоступен. Торгуйте осторожно!"

    async def _save_signal_to_database(self, user_id: str, signal: Dict[str, Any]):
        """Сохраняет сигнал в базу данных"""
        try:
            # Здесь можно добавить сохранение в базу данных
            # Пока просто логируем
            logger.info("💾 Сигнал сохранен в БД: %s для пользователя %s", signal['symbol'], user_id)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка сохранения сигнала в БД: %s", e)

    async def stop_signal_generation(self):
        """Останавливает генерацию сигналов"""
        self.signal_generation_active = False
        logger.info("🛑 Генерация ИИ сигналов остановлена")

    async def test_analyze_symbol(self, symbol: str, user_settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Публичный метод для тестирования анализа символа"""
        return await self._analyze_symbol(symbol, user_settings)

    async def test_generate_signal(self, symbol: str, analysis: Dict[str, Any], user_settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Публичный метод для тестирования генерации сигнала"""
        return await self._generate_signal(symbol, analysis, user_settings)

# Глобальный экземпляр генератора сигналов (lazy initialization)
_ai_signal_generator = None

def get_ai_signal_generator():
    """Получает или создает экземпляр генератора (singleton с lazy init)"""
    global _ai_signal_generator
    if _ai_signal_generator is None:
        _ai_signal_generator = AISignalGenerator()
    return _ai_signal_generator

# Для обратной совместимости (создается только при обращении)
class _LazySignalGenerator:
    """Lazy proxy для ai_signal_generator"""
    def __getattr__(self, name):
        return getattr(get_ai_signal_generator(), name)

ai_signal_generator = _LazySignalGenerator()

async def start_ai_signal_generation():
    """Запускает генерацию ИИ сигналов"""
    logger.info("🚀 Запуск генерации ИИ сигналов...")
    await get_ai_signal_generator().start_signal_generation()

async def stop_ai_signal_generation():
    """Останавливает генерацию ИИ сигналов"""
    if _ai_signal_generator is not None:
        await _ai_signal_generator.stop_signal_generation()

if __name__ == "__main__":
    # Тестирование генератора сигналов
    print("🤖 Тестирование ИИ генератора сигналов...")

    async def test():
        # Создаем тестовые настройки пользователя
        test_user_settings = {
            'trade_mode': 'spot',
            'filter_mode': 'soft',
            'deposit': 1000,
            'risk_pct': 2.0,
            'leverage': 1,
            'favorite_symbols': ['BTCUSDT', 'ETHUSDT']
        }

        # Тестируем анализ символа
        analysis = await ai_signal_generator.test_analyze_symbol('BTCUSDT', test_user_settings)
        if analysis:
            print(f"✅ Анализ BTCUSDT: {analysis['indicators']}")

            # Тестируем генерацию сигнала
            signal = await ai_signal_generator.test_generate_signal('BTCUSDT', analysis, test_user_settings)
            if signal:
                print(f"✅ Сгенерирован сигнал: {signal['signal_type']} {signal['entry_price']}")
            else:
                print("❌ Сигнал не сгенерирован")
        else:
            print("❌ Анализ не выполнен")

    asyncio.run(test())

# Ленивый импорт для избежания циклических зависимостей
def get_anomaly_data_with_fallback(symbol: str, ttl_seconds: int = 900):
    """Ленивый импорт get_anomaly_data_with_fallback"""
    try:
        from signal_live import get_anomaly_data_with_fallback as _func
        return _func(symbol, ttl_seconds)
    except ImportError as e:
        logging.warning("Не удалось импортировать signal_live: %s", e)
        return None
