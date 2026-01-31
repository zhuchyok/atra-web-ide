#!/usr/bin/env python3
"""
🔗 ИНТЕГРАЦИЯ ИИ С ТОРГОВОЙ СИСТЕМОЙ
Автоматическое обучение и оптимизация на основе реальных данных
"""

import asyncio
import logging
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Any, Optional

import pandas as pd

# Импорты из основной системы
try:
    from src.ai.learning import AILearningSystem, TradingPattern
except ImportError as e:
    logging.warning("Не удалось импортировать ai_learning_system: %s", e)
    AILearningSystem = None
    TradingPattern = None

# Ленивые импорты для избежания циклических зависимостей
def get_anomaly_data_with_fallback(symbol: str, ttl_seconds: int = 900):
    """Ленивый импорт get_anomaly_data_with_fallback"""
    try:
        from src.signals.core import get_anomaly_data_with_fallback as _func
        return _func(symbol, ttl_seconds)
    except ImportError as e:
        logging.warning("Не удалось импортировать anomaly filter: %s", e)
        return None

def get_symbol_info(symbol: str):
    """Ленивый импорт get_symbol_info"""
    try:
        from src.utils.cache_manager import get_symbol_info as _func
        return _func(symbol)
    except ImportError as e:
        logging.warning("Не удалось импортировать cache_manager: %s", e)
        return None

def get_ohlc_binance_sync_async(symbol: str, interval: str, limit: int = 100, _no_cache: bool = False):
    """Ленивый импорт get_ohlc_binance_sync_async"""
    try:
        from src.utils.ohlc_utils import get_ohlc_binance_sync_async as _func
        # Исправлено: используем именованный аргумент для _no_cache, чтобы избежать E1121
        return _func(symbol, interval, limit=limit, _no_cache=_no_cache)
    except ImportError as e:
        logging.warning("Не удалось импортировать ohlc_utils: %s", e)
        return None

# SourcesHub импортируем отдельно
try:
    from src.data.sources_hub import sources_hub  # Новый централизованный хаб источников
    logging.info("✅ SourcesHub успешно импортирован")
except ImportError as e:
    logging.warning("Не удалось импортировать sources_hub: %s", e)
    sources_hub = None

# Импорт динамических функций из правильных модулей
try:
    from src.signals.risk import get_dynamic_risk_pct, get_dynamic_leverage
    from src.utils.shared_utils import get_dynamic_tp_levels
    logging.info("✅ Динамические функции успешно импортированы")
except ImportError:
    logging.warning("Динамические функции недоступны, используем заглушки")
    def get_dynamic_risk_pct(*_args, **_kwargs):
        """Заглушка для процента риска"""
        return 2.0

    def get_dynamic_leverage(*_args, **_kwargs):
        """Заглушка для плеча"""
        return 1

    def get_dynamic_tp_levels(*_args, **_kwargs):
        """Заглушка для уровней тейк-профита"""
        return [1.5, 3.0]

logger = logging.getLogger(__name__)

class AIIntegration:
    """Интеграция ИИ с торговой системой"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIIntegration, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию
        if AIIntegration._initialized:
            return
        AIIntegration._initialized = True

        # Инициализация атрибутов (исправление W0201)
        self.ai_learning = None
        self.learning_active = True
        self.optimized_parameters = {}
        self._continuous_learning_ready = False
        self.user_patterns = {}

        # Используем singleton registry для получения единственного экземпляра
        try:
            from src.ai.singleton import get_ai_learning_system
            self.ai_learning = get_ai_learning_system()
            logger.info("✅ Используем singleton экземпляр ИИ системы")
        except (ImportError, AttributeError, Exception) as e:
            logger.warning("⚠️ Singleton registry недоступен, создаем новый экземпляр: %s", e)
            if AILearningSystem is None:
                logger.error("❌ AILearningSystem недоступен, ИИ система отключена")
                self.ai_learning = None
            else:
                try:
                    self.ai_learning = AILearningSystem()
                    logger.info("🤖 Создан новый экземпляр ИИ системы (fallback)")
                except Exception as init_error:
                    logger.error("❌ Ошибка создания AILearningSystem: %s", init_error)
                    self.ai_learning = None

        self.learning_active = True
        self.optimized_parameters = self._load_optimized_parameters()
        logger.info("🤖 ИИ интеграция инициализирована")

        # Запускаем непрерывное обучение в фоне
        self._start_continuous_learning()

    async def capture_signal_data(self, symbol: str, signal_type: str,
                                entry_price: float, user_data: Dict) -> Optional[TradingPattern]:
        """Захватывает данные сигнала для обучения"""
        try:
            # Получаем текущие данные
            ohlc = await get_ohlc_binance_sync_async(symbol, interval="1h", limit=100)
            if not ohlc:
                return None

            df = pd.DataFrame(ohlc)
            current_index = len(df) - 1

            # Получаем индикаторы
            indicators = await self._get_indicators(df, current_index)

            # Получаем рыночные условия
            market_conditions = await self._get_market_conditions(symbol, df, current_index)

            # Рассчитываем динамические параметры
            risk_pct = get_dynamic_risk_pct(df, current_index)
            leverage = get_dynamic_leverage(df, current_index, user_data.get('leverage', 1))
            tp1_pct, tp2_pct = get_dynamic_tp_levels(df, current_index, signal_type)

            # Рассчитываем TP уровни
            tp1 = entry_price * (1 + tp1_pct/100) if signal_type == "LONG" else entry_price * (1 - tp1_pct/100)
            tp2 = entry_price * (1 + tp2_pct/100) if signal_type == "LONG" else entry_price * (1 - tp2_pct/100)

            # Создаем паттерн
            pattern = TradingPattern(
                symbol=symbol,
                timestamp=get_utc_now(),
                signal_type=signal_type,
                entry_price=entry_price,
                tp1=tp1,
                tp2=tp2,
                risk_pct=risk_pct,
                leverage=leverage,
                indicators=indicators,
                market_conditions=market_conditions
            )

            logger.info("📊 Захвачен паттерн: %s %s", symbol, signal_type)
            return pattern

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка захвата данных сигнала: %s", e)
            return None

    async def _get_indicators(self, df: pd.DataFrame, current_index: int) -> Dict[str, float]:
        """Получает технические индикаторы"""
        try:
            indicators = {}

            # RSI
            if 'rsi' in df.columns and current_index < len(df):
                indicators['RSI'] = float(df['rsi'].iloc[current_index])

            # EMA
            if 'ema7' in df.columns and current_index < len(df):
                indicators['EMA7'] = float(df['ema7'].iloc[current_index])
            if 'ema25' in df.columns and current_index < len(df):
                indicators['EMA25'] = float(df['ema25'].iloc[current_index])

            # Bollinger Bands
            if 'bb_upper' in df.columns and current_index < len(df):
                indicators['BB_Upper'] = float(df['bb_upper'].iloc[current_index])
            if 'bb_lower' in df.columns and current_index < len(df):
                indicators['BB_Lower'] = float(df['bb_lower'].iloc[current_index])

            # Volume
            if 'volume' in df.columns and current_index < len(df):
                indicators['Volume'] = float(df['volume'].iloc[current_index])

            return indicators

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения индикаторов: %s", e)
            return {}

    async def _get_market_conditions(self, symbol: str, df: pd.DataFrame = None,
                                   current_index: int = None) -> Dict[str, Any]:
        """Получает рыночные условия через SourcesHub"""
        try:
            conditions = {}

            # BTC тренд
            try:
                btc_ohlc = await get_ohlc_binance_sync_async("BTCUSDT", interval="1h", limit=100)
                if btc_ohlc:
                    btc_df = pd.DataFrame(btc_ohlc)
                    if len(btc_df) > 0:
                        btc_price = btc_df['close'].iloc[-1]
                        btc_ema200 = btc_df['close'].rolling(200).mean().iloc[-1]
                        conditions['BTC_Trend'] = "BULLISH" if btc_price > btc_ema200 else "BEARISH"
            except (ValueError, TypeError, KeyError, RuntimeError, OSError):
                conditions['BTC_Trend'] = "UNKNOWN"

            # Market Cap через SourcesHub
            if sources_hub:
                try:
                    mcap_data = await sources_hub.get_market_cap_data(symbol)
                    if mcap_data:
                        conditions['Market_Cap'] = mcap_data.get('market_cap', 0)
                        conditions['Market_Cap_Sources'] = mcap_data.get('sources_used', 0)
                except (ValueError, TypeError, KeyError, RuntimeError, OSError):
                    conditions['Market_Cap'] = 0

                # Volume через SourcesHub
                try:
                    volume_24h = await sources_hub.get_volume_data(symbol)
                    if volume_24h:
                        conditions['Volume_24h'] = volume_24h
                        # Классификация объема
                        if volume_24h > 100_000_000:  # > 100M
                            conditions['Volume_Class'] = "MEGA"
                        elif volume_24h > 50_000_000:  # > 50M
                            conditions['Volume_Class'] = "HIGH"
                        elif volume_24h > 10_000_000:  # > 10M
                            conditions['Volume_Class'] = "MEDIUM"
                        else:
                            conditions['Volume_Class'] = "LOW"
                except (ValueError, TypeError, KeyError, RuntimeError, OSError):
                    conditions['Volume_24h'] = 0
                    conditions['Volume_Class'] = "UNKNOWN"

                # Price через SourcesHub
                try:
                    current_price = await sources_hub.get_price_data(symbol)
                    if current_price:
                        conditions['Current_Price'] = current_price
                except (ValueError, TypeError, KeyError, RuntimeError, OSError):
                    conditions['Current_Price'] = 0
            else:
                conditions['Market_Cap'] = 0
                conditions['Volume_24h'] = 0
                conditions['Volume_Class'] = "UNKNOWN"
                conditions['Current_Price'] = 0

            # Объем торгов (локальный) - только если df передан и есть индекс
            if df is not None and hasattr(df, 'columns') and len(df) > 0:
                if current_index is None:
                    current_index = len(df) - 1
                if 'volume' in df.columns and current_index < len(df) and current_index >= 0:
                    try:
                        current_volume = df['volume'].iloc[current_index]
                        if len(df) >= 20:
                            avg_volume = df['volume'].rolling(20).mean().iloc[current_index]
                        else:
                            avg_volume = df['volume'].mean()

                        if not pd.isna(current_volume) and not pd.isna(avg_volume) and avg_volume > 0:
                            if current_volume > avg_volume * 1.5:
                                conditions['Volume'] = "HIGH"
                            elif current_volume < avg_volume * 0.5:
                                conditions['Volume'] = "LOW"
                            else:
                                conditions['Volume'] = "NORMAL"
                        else:
                            conditions['Volume'] = "NORMAL"
                    except (IndexError, KeyError):
                        conditions['Volume'] = "NORMAL"

                # Волатильность
                if 'close' in df.columns and current_index >= 20:
                    try:
                        recent_prices = df['close'].iloc[current_index-20:current_index+1]
                        if len(recent_prices) > 0:
                            volatility = recent_prices.std() / recent_prices.mean() * 100
                            if not pd.isna(volatility):
                                if volatility > 5:
                                    conditions['Volatility'] = "HIGH"
                                elif volatility < 2:
                                    conditions['Volatility'] = "LOW"
                                else:
                                    conditions['Volatility'] = "NORMAL"
                            else:
                                conditions['Volatility'] = "NORMAL"
                        else:
                            conditions['Volatility'] = "NORMAL"
                    except (IndexError, KeyError):
                        conditions['Volatility'] = "NORMAL"

            return conditions

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения рыночных условий: %s", e)
            return {}

    async def update_signal_result(self, symbol: str, signal_type: str,
                                 entry_price: float, exit_price: float,
                                 result: str) -> bool:
        """Обновляет результат сигнала для обучения"""
        try:
            # Ищем соответствующий паттерн
            for pattern in self.ai_learning.patterns:
                if (pattern.symbol == symbol and
                    pattern.signal_type == signal_type and
                    abs(pattern.entry_price - entry_price) < 0.01 and
                    pattern.result is None):

                    # Рассчитываем прибыль
                    if signal_type == "LONG":
                        profit_pct = (exit_price - entry_price) / entry_price * 100
                    else:
                        profit_pct = (entry_price - exit_price) / entry_price * 100

                    # Обновляем паттерн
                    pattern.result = result
                    pattern.profit_pct = profit_pct

                    # Обновляем метрики
                    self.ai_learning.update_metrics()

                    logger.info("📊 Обновлен результат: %s %s = %s (%.2f%%)", symbol, signal_type, result, profit_pct)
                    return True

            logger.warning("⚠️ Паттерн не найден: %s %s", symbol, signal_type)
            return False

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка обновления результата: %s", e)
            return False

    async def analyze_news_items(self, news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Анализирует новости с помощью ИИ (расширенная версия)"""
        try:
            if not news_items:
                return []

            enhanced_news = []
            for item in news_items:
                enhanced_item = item.copy()

                # Анализ заголовка
                title = item.get('title', '').lower()

                # Определяем тональность
                positive_keywords = ['pump', 'surge', 'rally', 'bullish', 'breakthrough', 'adoption', 'partnership']
                negative_keywords = ['dump', 'crash', 'bearish', 'regulation', 'ban', 'hack', 'scam']

                positive_score = sum(1 for keyword in positive_keywords if keyword in title)
                negative_score = sum(1 for keyword in negative_keywords if keyword in title)

                if positive_score > negative_score:
                    enhanced_item['sentiment'] = 'POSITIVE'
                    enhanced_item['sentiment_score'] = positive_score
                elif negative_score > positive_score:
                    enhanced_item['sentiment'] = 'NEGATIVE'
                    enhanced_item['sentiment_score'] = negative_score
                else:
                    enhanced_item['sentiment'] = 'NEUTRAL'
                    enhanced_item['sentiment_score'] = 0

                # Определяем важность
                importance_keywords = ['bitcoin', 'ethereum', 'sec', 'fed', 'regulation', 'adoption', 'institutional']
                importance_score = sum(1 for keyword in importance_keywords if keyword in title)

                if importance_score >= 2:
                    enhanced_item['importance'] = 'HIGH'
                elif importance_score == 1:
                    enhanced_item['importance'] = 'MEDIUM'
                else:
                    enhanced_item['importance'] = 'LOW'

                enhanced_news.append(enhanced_item)

            return enhanced_news

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа новостей: %s", e)
            return news_items

    def _calculate_news_sentiment(self, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Рассчитывает общую тональность новостей"""
        try:
            if not news_items:
                return {"sentiment": "NEUTRAL", "score": 0}

            positive_count = sum(1 for item in news_items if item.get('sentiment') == 'POSITIVE')
            negative_count = sum(1 for item in news_items if item.get('sentiment') == 'NEGATIVE')
            neutral_count = sum(1 for item in news_items if item.get('sentiment') == 'NEUTRAL')

            total = len(news_items)

            if positive_count > negative_count:
                sentiment = "POSITIVE"
                score = positive_count / total
            elif negative_count > positive_count:
                sentiment = "NEGATIVE"
                score = negative_count / total
            else:
                sentiment = "NEUTRAL"
                score = 0.5

            return {
                "sentiment": sentiment,
                "score": score,
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count,
                "total": total
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка расчета тональности: %s", e)
            return {"sentiment": "NEUTRAL", "score": 0}

    def _load_optimized_parameters(self) -> Dict[str, Any]:
        """Загружает оптимизированные параметры из файла"""
        try:
            import os
            import json

            params_file = os.path.join("ai_learning_data", "optimized_parameters.json")
            if os.path.exists(params_file):
                with open(params_file, 'r', encoding='utf-8') as f:
                    params = json.load(f)
                logger.info("✅ Загружено %d оптимизированных параметров", len(params))
                return params
            else:
                logger.info("📝 Файл оптимизированных параметров не найден, используем значения по умолчанию")
                return {}

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка загрузки оптимизированных параметров: %s", e)
            return {}

    def _start_continuous_learning(self):
        """Запускает непрерывное обучение в фоне"""
        # Отложенный запуск - будет вызван после инициализации asyncio
        self._continuous_learning_ready = True
        logger.info("🔄 Непрерывное обучение подготовлено к запуску")

    async def start_continuous_learning_async(self):
        """Асинхронный запуск непрерывного обучения"""
        if not getattr(self, '_continuous_learning_ready', False):
            return

        try:
            # asyncio уже импортирован

            async def background_learning():
                while True:
                    try:
                        await self.ai_learning.continuous_learning()
                        # Пауза между циклами обучения
                        await asyncio.sleep(300)  # 5 минут
                    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                        logger.error("❌ Ошибка в непрерывном обучении: %s", e)
                        await asyncio.sleep(60)  # 1 минута при ошибке

            # Запускаем в фоне
            asyncio.create_task(background_learning())
            logger.info("🔄 Непрерывное обучение запущено в фоне")
            self._continuous_learning_ready = False  # Предотвращаем повторный запуск

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка запуска непрерывного обучения: %s", e)

    def get_optimized_parameter(self, parameter_name: str, default_value: Any = None) -> Any:
        """Получает оптимизированный параметр"""
        try:
            # Обновляем параметры если нужно
            self.optimized_parameters = self._load_optimized_parameters()

            value = self.optimized_parameters.get(parameter_name, default_value)
            if value is not None:
                logger.debug("🎯 Используем оптимизированный параметр %s: %s", parameter_name, value)
            return value

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения параметра %s: %s", parameter_name, e)
            return default_value

    def get_ai_optimized_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию с оптимизированными параметрами"""
        try:
            config = {
                # Параметры риска
                "risk_pct": self.get_optimized_parameter("risk_pct", 2.0),
                "leverage": self.get_optimized_parameter("leverage", 1.0),

                # Тейк-профиты
                "tp1": self.get_optimized_parameter("tp1", 1.5),
                "tp2": self.get_optimized_parameter("tp2", 3.0),

                # Индикаторы
                "rsi_oversold": self.get_optimized_parameter("rsi_oversold", 30),
                "rsi_overbought": self.get_optimized_parameter("rsi_overbought", 70),
                "ema_fast": self.get_optimized_parameter("ema_fast", 21),
                "ema_slow": self.get_optimized_parameter("ema_slow", 50),

                # Stop-Loss
                "stop_loss_pct": self.get_optimized_parameter("stop_loss_pct", 2.0),

                # Предпочтительные символы
                "preferred_symbols": self.get_optimized_parameter("preferred_symbols", []),

                # Время торговли
                "trading_hours": self.get_optimized_parameter("trading_hours", [9, 15, 21]),

                # Рыночные условия
                "optimal_btc_trend": self.get_optimized_parameter("optimal_btc_trend", "BULLISH"),
                "optimal_volume_class": self.get_optimized_parameter("optimal_volume_class", "HIGH"),
            }

            logger.info("🤖 Сформирована ИИ конфигурация с %d параметрами", len(config))
            return config

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка формирования ИИ конфигурации: %s", e)
            return {}

    async def get_ai_recommendations(self, symbol: str) -> Dict[str, Any]:
        """Получает рекомендации ИИ для символа"""
        try:
            recommendations = {
                "symbol": symbol,
                "timestamp": get_utc_now().isoformat(),
                "recommendations": [],
                "confidence": 0.0
            }

            # Получаем расширенные данные через SourcesHub
            if sources_hub:
                try:
                    # Market Cap
                    mcap_data = await sources_hub.get_market_cap_data(symbol)
                    if mcap_data:
                        recommendations["market_cap"] = mcap_data.get('market_cap', 0)
                        recommendations["market_cap_sources"] = mcap_data.get('sources_used', 0)

                    # Volume
                    volume_24h = await sources_hub.get_volume_data(symbol)
                    if volume_24h:
                        recommendations["volume_24h"] = volume_24h

                    # Price
                    current_price = await sources_hub.get_price_data(symbol)
                    if current_price:
                        recommendations["current_price"] = current_price

                    # News
                    news_items = await sources_hub.get_news_data(symbol)
                    if news_items:
                        enhanced_news = await self.analyze_news_items(news_items)
                        recommendations["news_count"] = len(enhanced_news)
                        recommendations["news_sentiment"] = self._calculate_news_sentiment(enhanced_news)

                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                    logger.warning("⚠️ Не удалось получить данные через SourcesHub: %s", e)
            else:
                logger.warning("⚠️ SourcesHub недоступен")

            # Анализируем исторические данные символа
            symbol_patterns = [p for p in self.ai_learning.patterns if p.symbol == symbol]

            if len(symbol_patterns) >= 5:
                # Есть достаточно исторических данных
                # Считаем WIN rate только от закрытых позиций (WIN + LOSS)
                successful_patterns = [p for p in symbol_patterns if p.result == "WIN"]
                failed_patterns = [p for p in symbol_patterns if p.result == "LOSS"]
                closed_patterns = len(successful_patterns) + len(failed_patterns)

                if closed_patterns >= 5:
                    # Есть достаточно закрытых позиций для расчета
                    success_rate = len(successful_patterns) / closed_patterns

                    if success_rate > 0.7:
                        msg = f"✅ Высокая успешность: {success_rate:.1%} ({len(successful_patterns)}/{closed_patterns})"
                        recommendations["recommendations"].append(msg + ". Рекомендуется торговать")
                        recommendations["confidence"] = success_rate
                    elif success_rate < 0.3:
                        msg = f"⚠️ Низкая успешность: {success_rate:.1%} ({len(successful_patterns)}/{closed_patterns})"
                        recommendations["recommendations"].append(msg + ". Рекомендуется избегать")
                        # При низком WIN rate - низкая уверенность (не инвертируем!)
                        recommendations["confidence"] = max(0.3, success_rate)
                    else:
                        recommendations["recommendations"].append(
                            f"📊 Средняя успешность: {success_rate:.1%} ({len(successful_patterns)}/{closed_patterns})"
                        )
                        recommendations["confidence"] = success_rate
                else:
                    # Недостаточно закрытых позиций - используем технический анализ
                    technical_confidence = await self._calculate_technical_confidence(symbol)
                    recommendations["confidence"] = technical_confidence
                    msg = f"📊 Мало данных ({closed_patterns} закрытых), используем тех. анализ: {technical_confidence:.1%}"
                    recommendations["recommendations"].append(msg)
            else:
                # Недостаточно исторических данных - используем технический анализ
                technical_confidence = await self._calculate_technical_confidence(symbol)
                recommendations["confidence"] = technical_confidence

                if technical_confidence > 0.7:
                    recommendations["recommendations"].append(
                        f"📈 Высокая техническая уверенность: {technical_confidence:.1%}"
                    )
                elif technical_confidence < 0.3:
                    recommendations["recommendations"].append(
                        f"📉 Низкая техническая уверенность: {technical_confidence:.1%}"
                    )
                else:
                    recommendations["recommendations"].append(
                        f"📊 Средняя техническая уверенность: {technical_confidence:.1%}"
                    )

            # Анализ лучших условий
            successful_patterns = [p for p in symbol_patterns if p.result == "WIN"]
            if successful_patterns:
                best_conditions = {}
                for pattern in successful_patterns:
                    for condition, value in pattern.market_conditions.items():
                        if condition not in best_conditions:
                            best_conditions[condition] = []
                        best_conditions[condition].append(value)

                for condition, values in best_conditions.items():
                    most_common = max(set(values), key=values.count)
                    recommendations["recommendations"].append(
                        f"🎯 Лучшие условия для {condition}: {most_common}"
                    )

            logger.info("🤖 Рекомендации для %s: %d советов", symbol, len(recommendations['recommendations']))
            return recommendations

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения рекомендаций: %s", e)
            return {"error": str(e)}


    async def auto_optimize_user_settings(self, user_id: str, user_data: Dict) -> Dict[str, Any]:
        """Автоматически оптимизирует настройки пользователя"""
        try:
            optimization = {
                "user_id": user_id,
                "timestamp": get_utc_now().isoformat(),
                "optimizations": {},
                "recommendations": []
            }

            # Анализируем паттерны пользователя
            user_patterns = [p for p in self.ai_learning.patterns
                           if p.symbol in user_data.get('favorite_symbols', [])]

            if not user_patterns:
                optimization["recommendations"].append(
                    "📊 Недостаточно данных для оптимизации"
                )
                return optimization

            # Анализ лучших символов
            symbol_success = {}
            for pattern in user_patterns:
                if pattern.result == "WIN":
                    if pattern.symbol not in symbol_success:
                        symbol_success[pattern.symbol] = 0
                    symbol_success[pattern.symbol] += 1

            if symbol_success:
                best_symbols = sorted(symbol_success.items(), key=lambda x: x[1], reverse=True)[:3]
                optimization["optimizations"]["best_symbols"] = [s[0] for s in best_symbols]
                optimization["recommendations"].append(
                    f"✅ Рекомендуемые символы: {', '.join([s[0] for s in best_symbols])}"
                )

            # Анализ риска
            avg_risk = sum(p.risk_pct for p in user_patterns) / len(user_patterns)
            if avg_risk > 3.0:
                optimization["recommendations"].append(
                    f"⚠️ Высокий средний риск: {avg_risk:.1f}%. Рекомендуется снизить"
                )
            elif avg_risk < 1.0:
                optimization["recommendations"].append(
                    f"📈 Низкий средний риск: {avg_risk:.1f}%. Можно увеличить"
                )

                logger.info("🔧 Оптимизация для пользователя %s: %d рекомендаций",
                            user_id, len(optimization['recommendations']))
            return optimization

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка оптимизации настроек: %s", e)
            return {"error": str(e)}

    async def generate_learning_report(self) -> str:
        """Генерирует отчет об обучении"""
        try:
            report = self.ai_learning.generate_learning_report()

            # Добавляем интеграционные данные
            report += f"""
🔗 ИНТЕГРАЦИЯ С СИСТЕМОЙ:
• Статус обучения: {'🟢 Активно' if self.learning_active else '🔴 Отключено'}
• Всего паттернов: {len(self.ai_learning.patterns)}
• Последнее обновление: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S')}

💡 РЕКОМЕНДАЦИИ СИСТЕМЫ:
"""

            # Получаем общие рекомендации
            recommendations = self.ai_learning.get_learning_recommendations()
            for rec in recommendations:
                report += f"• {rec}\n"

            return report

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка генерации отчета: %s", e)
            return f"❌ Ошибка генерации отчета: {e}"

    async def record_signal_pattern(self, symbol: str, side: str, entry_price: float,
                                   tp1_price: float, tp2_price: float, risk_pct: float,
                                   leverage: float, user_id: int, is_dca: bool = False):
        """Записывает паттерн принятого сигнала для обучения ИИ"""
        try:
            # Проверяем, есть ли уже паттерн с PENDING статусом
            pattern_id = None
            if hasattr(self, 'user_patterns'):
                for pid, data in self.user_patterns.items():
                    if (data['user_id'] == user_id and
                        data['symbol'] == symbol and
                        data['side'].upper() == side.upper() and
                        data.get('status') == 'PENDING'):
                        pattern_id = pid
                        break

            if pattern_id:
                # Обновляем существующий паттерн - меняем статус на ACCEPTED
                pattern_data = self.user_patterns[pattern_id]
                pattern_data['status'] = 'ACCEPTED'
                pattern_data['accepted_at'] = get_utc_now()
                logger.info("🤖 ИИ: Паттерн обновлен на ACCEPTED для %s %s пользователя %s", symbol, side, user_id)
                return

            # Создаем новый паттерн (если не найден существующий)
            # Получаем текущие рыночные условия
            market_conditions = await self._get_market_conditions(symbol, None, None)

            # Получаем индикаторы (если доступны)
            indicators = await self._get_indicators(symbol)

            # Создаем паттерн
            pattern = TradingPattern(
                symbol=symbol,
                timestamp=get_utc_now(),
                signal_type=side.upper(),
                entry_price=entry_price,
                tp1=tp1_price,
                tp2=tp2_price,
                risk_pct=risk_pct,
                leverage=leverage,
                indicators=indicators,
                market_conditions=market_conditions,
                result=None,  # Будет заполнено при закрытии позиции
                profit_pct=None
            )

            # Добавляем паттерн в систему обучения
            self.ai_learning.add_pattern(pattern)

            # Сохраняем связь с пользователем для отслеживания результатов
            now = get_utc_now()
            pattern_id = f"{user_id}_{symbol}_{now.strftime('%Y%m%d_%H%M%S')}"
            self.user_patterns[pattern_id] = {
                'pattern': pattern,
                'user_id': user_id,
                'symbol': symbol,
                'entry_price': entry_price,
                'side': side,
                'is_dca': is_dca,
                'status': 'ACCEPTED',
                'created_at': now,
                'accepted_at': now
            }

            logger.info("🤖 ИИ: Паттерн записан для %s %s пользователем %s", symbol, side, user_id)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка записи паттерна ИИ: %s", e)

    async def update_pattern_from_closed_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        exit_reason: str,
        user_id: int,
        profit_pct: float,
    ):
        """🔄 ОБНОВЛЯЕТ паттерн результатом закрытой сделки для обучения ИИ

        Вызывается при закрытии позиции для обновления паттерна результатом (WIN/LOSS).
        Это критически важно для обучения системы на реальных результатах.
        """
        try:
            # Ищем паттерн с PENDING/ACCEPTED статусом для этой сделки
            pattern_id = None
            if hasattr(self, 'user_patterns'):
                for pid, data in self.user_patterns.items():
                    if (data['user_id'] == user_id and
                        data['symbol'] == symbol and
                        data['side'].upper() == side.upper() and
                        data.get('status') in ['PENDING', 'ACCEPTED']):
                        pattern_id = pid
                        break

            if pattern_id:
                # Обновляем существующий паттерн результатом
                pattern_data = self.user_patterns[pattern_id]
                pattern = pattern_data.get('pattern')

                if pattern:
                    # Обновляем результат
                    pattern.result = "WIN" if profit_pct > 0 else "LOSS"
                    pattern.profit_pct = profit_pct

                    # Обновляем статус
                    pattern_data['status'] = 'CLOSED'
                    pattern_data['exit_price'] = exit_price
                    pattern_data['exit_reason'] = exit_reason
                    pattern_data['profit_pct'] = profit_pct
                    pattern_data['closed_at'] = get_utc_now()

                    # Добавляем обновлённый паттерн в систему обучения
                    # (старый паттерн будет заменён при следующей очистке)
                    self.ai_learning.add_pattern(pattern)

                    logger.info(
                        "✅ ИИ: Паттерн обновлён результатом для %s %s: %s (%.2f%%)",
                        symbol, side, pattern.result, profit_pct
                    )
                else:
                    logger.warning("⚠️ ИИ: Паттерн не найден для обновления: %s", pattern_id)
            else:
                # Если паттерн не найден, создаём новый из закрытой сделки
                # Это важно для импорта исторических данных
                market_conditions = await self._get_market_conditions(symbol, None, None)
                indicators = await self._get_indicators(symbol)

                pattern = TradingPattern(
                    symbol=symbol,
                    timestamp=get_utc_now(),
                    signal_type=side.upper(),
                    entry_price=entry_price,
                    tp1=exit_price,  # Используем exit_price как приближение
                    tp2=exit_price,
                    risk_pct=2.0,  # Дефолтное значение
                    leverage=1.0,  # Дефолтное значение
                    indicators=indicators,
                    market_conditions=market_conditions,
                    result="WIN" if profit_pct > 0 else "LOSS",
                    profit_pct=profit_pct
                )

                self.ai_learning.add_pattern(pattern)
                logger.info(
                    "📥 ИИ: Создан паттерн из закрытой сделки %s %s: %s (%.2f%%)",
                    symbol, side, pattern.result, profit_pct
                )

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка обновления паттерна из закрытой сделки: %s", e)

    async def record_signal_pattern_on_send(self, symbol: str, side: str, entry_price: float,
                                           tp1_price: float, tp2_price: float, risk_pct: float,
                                           leverage: float, user_id: int, df: Any = None):
        """Записывает паттерн отправленного сигнала (PENDING) для обучения ИИ

        Вызывается при отправке сигнала, чтобы сохранить паттерн даже если пользователь не примет сигнал.
        Это решает проблему "замкнутого круга" - система будет учиться на всех сигналах.
        """
        try:
            # Получаем текущие рыночные условия
            # Если передан df, используем последний индекс
            if df is not None and hasattr(df, '__len__') and len(df) > 0:
                current_index = len(df) - 1
                # Создаем DataFrame если передан список
                if not hasattr(df, 'columns'):
                    df = pd.DataFrame(df)
                market_conditions = await self._get_market_conditions(symbol, df, current_index)
            else:
                # Fallback: пустой DataFrame
                market_conditions = await self._get_market_conditions(symbol, pd.DataFrame(), None)

            # Получаем индикаторы (если доступны)
            indicators = await self._get_indicators(symbol, df)

            # Создаем паттерн со статусом PENDING
            now = get_utc_now()
            pattern = TradingPattern(
                symbol=symbol,
                timestamp=now,
                signal_type=side.upper(),
                entry_price=entry_price,
                tp1=tp1_price,
                tp2=tp2_price,
                risk_pct=risk_pct,
                leverage=leverage,
                indicators=indicators,
                market_conditions=market_conditions,
                result=None,  # Будет заполнено при закрытии позиции или отклонении
                profit_pct=None
            )

            # Добавляем паттерн в систему обучения
            self.ai_learning.add_pattern(pattern)

            # Сохраняем связь с пользователем для отслеживания результатов
            pattern_id = f"{user_id}_{symbol}_{now.strftime('%Y%m%d_%H%M%S')}"
            self.user_patterns[pattern_id] = {
                'pattern': pattern,
                'user_id': user_id,
                'symbol': symbol,
                'entry_price': entry_price,
                'side': side,
                'status': 'PENDING',  # Статус PENDING - сигнал отправлен, но не принят
                'created_at': now
            }

            logger.info("🤖 ИИ: Паттерн сохранен (PENDING) для %s %s пользователя %s", symbol, side, user_id)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка записи паттерна при отправке: %s", e)

    async def record_position_result(self, user_id: int, symbol: str, side: str,
                                   _entry_price: float, _exit_price: float,
                                   profit_pct: float, is_dca: bool = False):
        """Записывает результат закрытой позиции для обучения ИИ"""
        try:
            # Ищем соответствующий паттерн
            pattern_id = None
            if hasattr(self, 'user_patterns'):
                for pid, data in self.user_patterns.items():
                    if (data['user_id'] == user_id and
                        data['symbol'] == symbol and
                        data['side'] == side.lower() and
                        data['is_dca'] == is_dca):
                        pattern_id = pid
                        break

            if pattern_id:
                # Обновляем результат паттерна
                pattern_data = self.user_patterns[pattern_id]
                pattern = pattern_data['pattern']

                # Определяем результат
                if profit_pct > 0:
                    pattern.result = "WIN"
                elif profit_pct < 0:
                    pattern.result = "LOSS"
                else:
                    pattern.result = "NEUTRAL"

                pattern.profit_pct = profit_pct

                # Обновляем метрики
                self.ai_learning.update_metrics()

                # Удаляем из активных паттернов
                del self.user_patterns[pattern_id]

                logger.info("🤖 ИИ: Результат записан для %s %s: %s (%.2f%%)", symbol, side, pattern.result, profit_pct)

                # Запускаем переобучение если накопилось достаточно данных
                if len(self.ai_learning.patterns) % 10 == 0:
                    await self.ai_learning.continuous_learning()

            else:
                logger.warning("🤖 ИИ: Паттерн не найден для %s %s пользователя %s", symbol, side, user_id)

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка записи результата ИИ: %s", e)

    async def _get_indicators(self, symbol: str, df: Any = None) -> Dict[str, float]:
        """Получает текущие значения индикаторов

        Args:
            symbol: Торговый символ
            df: DataFrame с данными OHLC (опционально, для более точных значений)
        """
        try:
            # Если передан df, извлекаем индикаторы из него
            if df is not None and hasattr(df, 'iloc') and len(df) > 0:
                try:
                    indicators = {}
                    # RSI
                    if 'rsi' in df.columns:
                        rsi_val = df['rsi'].iloc[-1]
                        indicators['rsi'] = float(rsi_val) if not pd.isna(rsi_val) else 50.0
                    else:
                        indicators['rsi'] = 50.0

                    # EMA
                    if 'ema_fast' in df.columns:
                        ema_fast_val = df['ema_fast'].iloc[-1]
                        indicators['ema_fast'] = float(ema_fast_val) if not pd.isna(ema_fast_val) else 0.0
                    else:
                        indicators['ema_fast'] = 0.0

                    if 'ema_slow' in df.columns:
                        ema_slow_val = df['ema_slow'].iloc[-1]
                        indicators['ema_slow'] = float(ema_slow_val) if not pd.isna(ema_slow_val) else 0.0
                    else:
                        indicators['ema_slow'] = 0.0

                    # Bollinger Bands
                    if 'bb_upper' in df.columns:
                        bb_upper_val = df['bb_upper'].iloc[-1]
                        indicators['bollinger_upper'] = float(bb_upper_val) if not pd.isna(bb_upper_val) else 0.0
                    else:
                        indicators['bollinger_upper'] = 0.0

                    if 'bb_lower' in df.columns:
                        bb_lower_val = df['bb_lower'].iloc[-1]
                        indicators['bollinger_lower'] = float(bb_lower_val) if not pd.isna(bb_lower_val) else 0.0
                    else:
                        indicators['bollinger_lower'] = 0.0

                    # Volume
                    if 'volume' in df.columns:
                        volume_val = df['volume'].iloc[-1]
                        indicators['volume'] = float(volume_val) if not pd.isna(volume_val) else 0.0
                    else:
                        indicators['volume'] = 0.0

                    return indicators
                except Exception as e:
                    logger.debug("Ошибка извлечения индикаторов из df: %s, используем базовые значения", e)

            # Fallback: базовые значения
            return {
                'rsi': 50.0,
                'ema_fast': 0.0,
                'ema_slow': 0.0,
                'bollinger_upper': 0.0,
                'bollinger_lower': 0.0,
                'volume': 0.0
            }
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка получения индикаторов: %s", e)
            return {}

    async def _calculate_technical_confidence(self, symbol: str) -> float:
        """Рассчитывает техническую уверенность на основе индикаторов"""
        try:
            # Получаем OHLC данные для анализа
            ohlc = await get_ohlc_binance_sync_async(symbol, interval="1h", limit=100)
            if not ohlc or len(ohlc) < 50:
                return 0.5  # Нейтральная уверенность при недостатке данных

            df = pd.DataFrame(ohlc)
            if len(df) < 50:
                return 0.5

            # Рассчитываем индикаторы (используем библиотеку ta)
            use_ta_lib = False
            try:
                # Проверяем, что библиотека ta работает
                test_data = df['close'].iloc[-20:]  # Берем последние 20 значений для теста
                if len(test_data) >= 14:  # Минимум для RSI
                    from ta.momentum import RSIIndicator  # pylint: disable=import-outside-toplevel
                    test_rsi = RSIIndicator(test_data, window=14).rsi()
                    if not test_rsi.isna().iloc[-1]:
                        use_ta_lib = True
                        logger.debug("✅ Библиотека ta доступна и работает корректно")
                    else:
                        logger.warning("⚠️ ta импортирована, но расчеты дают NaN, используем простые расчеты")
                else:
                    logger.warning("⚠️ Недостаточно данных для ta, используем простые расчеты")
            except ImportError:
                logger.warning("⚠️ Библиотека ta недоступна, используем простые расчеты")
            except Exception as e:
                logger.warning("⚠️ Ошибка при работе с ta: %s, используем простые расчеты", e)

            if use_ta_lib:
                # RSI
                from ta.momentum import RSIIndicator  # pylint: disable=import-outside-toplevel
                close_floats = df['close'].astype(float)
                rsi = RSIIndicator(close_floats, window=14).rsi()
                current_rsi = float(rsi.iloc[-1]) if not rsi.isna().iloc[-1] else 50.0

                # EMA
                from ta.trend import EMAIndicator  # pylint: disable=import-outside-toplevel
                ema_7 = EMAIndicator(close_floats, window=7).ema_indicator()
                ema_25 = EMAIndicator(close_floats, window=25).ema_indicator()
                current_ema_7 = float(ema_7.iloc[-1]) if not ema_7.isna().iloc[-1] else float(close_floats.iloc[-1])
                current_ema_25 = float(ema_25.iloc[-1]) if not ema_25.isna().iloc[-1] else float(close_floats.iloc[-1])

                # Bollinger Bands
                from ta.volatility import BollingerBands  # pylint: disable=import-outside-toplevel
                bb = BollingerBands(close_floats, window=20, window_dev=2)
                bb_upper = bb.bollinger_hband()
                bb_lower = bb.bollinger_lband()
                current_price = float(close_floats.iloc[-1])
                bb_upper_val = float(bb_upper.iloc[-1]) if not bb_upper.isna().iloc[-1] else current_price * 1.02
                bb_lower_val = float(bb_lower.iloc[-1]) if not bb_lower.isna().iloc[-1] else current_price * 0.98

                # MACD
                from ta.trend import MACD  # pylint: disable=import-outside-toplevel
                macd = MACD(close_floats)
                current_macd = float(macd.macd().iloc[-1]) if not macd.macd().isna().iloc[-1] else 0.0
                current_macd_signal = float(macd.macd_signal().iloc[-1]) if not macd.macd_signal().isna().iloc[-1] else 0.0
            else:
                # Простые расчеты без TA-Lib
                import numpy as np  # pylint: disable=import-outside-toplevel
                close_floats = df['close'].astype(float)
                current_price = float(close_floats.iloc[-1])

                # Простой RSI
                delta = close_floats.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                current_rsi = 100 - (100 / (1 + float(rs.iloc[-1]))) if not np.isnan(rs.iloc[-1]) else 50.0

                # Простые EMA
                current_ema_7 = float(close_floats.ewm(span=7).mean().iloc[-1])
                current_ema_25 = float(close_floats.ewm(span=25).mean().iloc[-1])

                # Простые Bollinger Bands
                sma_20 = float(close_floats.rolling(window=20).mean().iloc[-1])
                std_20 = float(close_floats.rolling(window=20).std().iloc[-1])
                bb_upper_val = sma_20 + (2 * std_20)
                bb_lower_val = sma_20 - (2 * std_20)

                # Простой MACD
                ema_12 = close_floats.ewm(span=12).mean()
                ema_26 = close_floats.ewm(span=26).mean()
                macd_line = ema_12 - ema_26
                macd_signal_line = macd_line.ewm(span=9).mean()
                current_macd = float(macd_line.iloc[-1])
                current_macd_signal = float(macd_signal_line.iloc[-1])

            # Рассчитываем факторы уверенности
            confidence_factors = []

            # 1. RSI фактор (оптимально между 30-70)
            if 30 <= current_rsi <= 70:
                rsi_factor = 1.0
            elif current_rsi < 30 or current_rsi > 70:
                rsi_factor = 0.7  # Снижаем уверенность при экстремальных значениях
            else:
                rsi_factor = 0.5
            confidence_factors.append(rsi_factor)

            # 2. EMA фактор (тренд)
            ema_diff = (current_ema_7 - current_ema_25) / current_ema_25
            if abs(ema_diff) > 0.02:  # Сильный тренд
                ema_factor = 0.8
            elif abs(ema_diff) > 0.01:  # Средний тренд
                ema_factor = 0.7
            else:  # Слабый тренд
                ema_factor = 0.6
            confidence_factors.append(ema_factor)

            # 3. Bollinger Bands фактор
            bb_position = (current_price - bb_lower_val) / (bb_upper_val - bb_lower_val)
            if 0.2 <= bb_position <= 0.8:  # В пределах полос
                bb_factor = 0.8
            elif bb_position < 0.2 or bb_position > 0.8:  # У границ
                bb_factor = 0.6
            else:
                bb_factor = 0.5
            confidence_factors.append(bb_factor)

            # 4. MACD фактор
            if current_macd > current_macd_signal:
                macd_factor = 0.8  # Бычий сигнал
            elif current_macd < current_macd_signal:
                macd_factor = 0.6  # Медвежий сигнал
            else:
                macd_factor = 0.7  # Нейтральный
            confidence_factors.append(macd_factor)

            # 5. Волатильность фактор
            import numpy as np  # pylint: disable=import-outside-toplevel
            returns = df['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(24)  # Дневная волатильность
            if 0.01 <= volatility <= 0.05:  # Нормальная волатильность
                vol_factor = 0.8
            elif volatility > 0.05:  # Высокая волатильность
                vol_factor = 0.6
            else:  # Низкая волатильность
                vol_factor = 0.7
            confidence_factors.append(vol_factor)

            # Рассчитываем общую уверенность как среднее взвешенное
            weights = [0.2, 0.25, 0.2, 0.2, 0.15]  # Веса для каждого фактора
            technical_confidence = sum(f * w for f, w in zip(confidence_factors, weights))

            # Нормализуем в диапазон 0.1-0.9 (не даем 0 или 1)
            technical_confidence = max(0.1, min(0.9, technical_confidence))

            logger.debug("📊 Техническая уверенность для %s: %.2f", symbol, technical_confidence)
            logger.debug("   RSI: %.1f (фактор: %.2f)", current_rsi, rsi_factor)
            logger.debug("   EMA разность: %.3f (фактор: %.2f)", ema_diff, ema_factor)
            logger.debug("   BB позиция: %.2f (фактор: %.2f)", bb_position, bb_factor)
            logger.debug("   MACD: %.4f (фактор: %.2f)", current_macd, macd_factor)
            logger.debug("   Волатильность: %.3f (фактор: %.2f)", volatility, vol_factor)

            return technical_confidence

        except Exception as e:
            logger.error("❌ Ошибка расчета технической уверенности: %s", e)
            return 0.5  # Нейтральная уверенность при ошибке

# Глобальный экземпляр интеграции
ai_integration = AIIntegration()

async def start_ai_learning_integration():
    """Запускает интеграцию обучения ИИ"""
    logger.info("🚀 Запуск интеграции обучения ИИ...")

    # Запускаем асинхронное непрерывное обучение
    await ai_integration.start_continuous_learning_async()

    # Запускаем одноразовое обучение при старте
    await ai_integration.ai_learning.continuous_learning()

if __name__ == "__main__":
    # Тестирование интеграции
    logging.info("🤖 Тестирование интеграции ИИ...")

    # Генерируем отчет
    async def test():
        """Тестовая функция для генерации отчета"""
        report = await ai_integration.generate_learning_report()
        logging.info("Отчет ИИ: %s", report)

    asyncio.run(test())
