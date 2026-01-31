"""
Улучшенные фильтры с интеграцией метрик
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
import numpy as np
from src.metrics.decorators import track_filter_metrics, metrics_context
from src.metrics.filter_metrics import FilterType

logger = logging.getLogger(__name__)

# Импорт адаптивных RSI уровней
try:
    from src.filters.adaptive_rsi import get_adaptive_rsi_levels, should_use_adaptive_rsi
    ADAPTIVE_RSI_AVAILABLE = True
except ImportError:
    ADAPTIVE_RSI_AVAILABLE = False
    logger.warning("⚠️ Адаптивные RSI уровни недоступны")

# Импорт логирования фильтров
try:
    from src.utils.filter_logger import log_filter_check_async
    FILTER_LOGGER_AVAILABLE = True
except ImportError:
    FILTER_LOGGER_AVAILABLE = False
    logger.debug("Логирование фильтров недоступно")


class EnhancedFilterBase:
    """Базовый класс для улучшенных фильтров с метриками"""

    def __init__(self, filter_type: FilterType):
        self.filter_type = filter_type
        self.logger = logging.getLogger(f"filter.{filter_type.value}")

    def apply_filter(self, data: Dict[str, Any], **kwargs) -> Tuple[bool, Optional[str]]:
        """
        Применение фильтра с автоматическим сбором метрик

        Returns:
            Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
        """
        with metrics_context(f"{self.filter_type.value}_filter", self.filter_type) as ctx:
            try:
                result, rejection_reason = self._filter_logic(data, **kwargs)
                ctx.set_result(result, rejection_reason)
                return result, rejection_reason

            except Exception as e:
                self.logger.error("Ошибка в фильтре %s: %s", self.filter_type.value, e)
                ctx.set_result(False, f"Exception: {str(e)}")
                return False, f"Exception: {str(e)}"

    def _filter_logic(self, data: Dict[str, Any], **kwargs) -> Tuple[bool, Optional[str]]:
        """Логика фильтра - должна быть переопределена в наследниках"""
        raise NotImplementedError("Метод _filter_logic должен быть переопределен")


@track_filter_metrics(FilterType.BB_FILTER)
def enhanced_bb_filter(df, i: int, **kwargs) -> Tuple[bool, Optional[str]]:
    """
    Улучшенный фильтр Bollinger Bands с метриками

    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        **kwargs: Дополнительные параметры

    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        # Получение параметров (оптимизированы для интрадей)
        bb_window = kwargs.get('bb_window', 18)  # 🆕 Оптимизировано: было 20
        # bb_std и bb_epsilon используются в расчетах BB, но не напрямую в этой функции
        min_width = kwargs.get('bb_min_width', 0.015)  # 🆕 Оптимизировано: было 0.02
        position_long = kwargs.get('bb_position_long', 0.15)  # 🆕 Оптимизировано: было 0.2
        position_short = kwargs.get('bb_position_short', 0.85)  # 🆕 Оптимизировано: было 0.8
        squeeze_threshold = kwargs.get('bb_squeeze_threshold', 0.012)  # 🆕 Порог сжатия

        # Проверка наличия необходимых данных
        if i < bb_window or i >= len(df):
            return False, f"Недостаточно данных для BB фильтра (нужно {bb_window})"

        # Проверка наличия колонок BB
        required_columns = ['bb_upper', 'bb_lower', 'bb_mid']
        if not all(col in df.columns for col in required_columns):
            return False, "Отсутствуют колонки Bollinger Bands"

        # Получение текущих значений
        current_close = df.iloc[i]['close']
        bb_upper = df.iloc[i]['bb_upper']
        bb_lower = df.iloc[i]['bb_lower']
        bb_mid = df.iloc[i]['bb_mid']

        # Проверка на NaN
        if pd.isna(current_close) or pd.isna(bb_upper) or pd.isna(bb_lower) or pd.isna(bb_mid):
            return False, "NaN значения в BB данных"

        # 🆕 Проверка ширины полос (оптимизированная)
        bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0
        if bb_width < min_width:
            return False, f"Слишком узкие полосы: {bb_width:.3%}"

        # 🆕 Проверка на сжатие (расширенная)
        if bb_width < squeeze_threshold:
            # Анализируем волатильность перед сжатием
            if i > 5:
                prev_widths = []
                for j in range(1, 6):
                    if i - j >= 0:
                        prev_upper = df.iloc[i-j]['bb_upper']
                        prev_lower = df.iloc[i-j]['bb_lower']
                        prev_mid = df.iloc[i-j]['bb_mid']
                        if prev_mid > 0:
                            prev_width = (prev_upper - prev_lower) / prev_mid
                            prev_widths.append(prev_width)

                # Если полосы резко сузились - возможен пробой
                if prev_widths and max(prev_widths) > bb_width * 1.5:
                    return False, "Резкое сжатие полос - возможен пробой"

        # 🆕 Расчет позиции цены (оптимизированная формула)
        bb_position = (current_close - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

        # 🆕 Строгие условия для позиции
        if bb_position < position_long:  # В нижних 15%
            # Дополнительная проверка для лонгов
            if i > 0:
                prev_upper = df.iloc[i-1]['bb_upper']
                prev_lower = df.iloc[i-1]['bb_lower']
                prev_close = df.iloc[i-1]['close']
                if (prev_upper - prev_lower) > 0:
                    prev_position = (prev_close - prev_lower) / (prev_upper - prev_lower)
                    if prev_position < position_long:
                        return False, "Цена слишком долго в нижней зоне"
        elif bb_position > position_short:  # В верхних 15%
            # Дополнительная проверка для шортов
            if i > 0:
                prev_upper = df.iloc[i-1]['bb_upper']
                prev_lower = df.iloc[i-1]['bb_lower']
                prev_close = df.iloc[i-1]['close']
                if (prev_upper - prev_lower) > 0:
                    prev_position = (prev_close - prev_lower) / (prev_upper - prev_lower)
                    if prev_position > position_short:
                        return False, "Цена слишком долго в верхней зоне"
        else:
            return False, f"Цена в средней зоне BB: {bb_position:.2f}"

        # 🆕 Проверка на ложный пробой
        if i > 2:
            recent_positions = []
            for j in range(3):
                if i - j >= 0:
                    prev_upper = df.iloc[i-j]['bb_upper']
                    prev_lower = df.iloc[i-j]['bb_lower']
                    prev_close = df.iloc[i-j]['close']
                    if (prev_upper - prev_lower) > 0:
                        pos = (prev_close - prev_lower) / (prev_upper - prev_lower)
                        recent_positions.append(pos)

            # Если цена "прыгает" через границы - возможен ложный сигнал
            if len(recent_positions) >= 2:
                position_changes = sum(1 for j in range(1, len(recent_positions)) if
                                     (recent_positions[j] < position_long and recent_positions[j-1] > position_short) or
                                     (recent_positions[j] > position_short and recent_positions[j-1] < position_long))

                if position_changes > 0:
                    return False, "Подозрительные скачки через полосы BB"

        return True, None

    except Exception as e:
        logger.error("Ошибка в BB фильтре: %s", e)
        return False, f"Exception: {str(e)}"


@track_filter_metrics(FilterType.EMA_FILTER)
def enhanced_ema_filter(df, i: int, **kwargs) -> Tuple[bool, Optional[str]]:
    """
    ОПТИМИЗИРОВАННЫЙ EMA фильтр для интрадей крипто

    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        **kwargs: Дополнительные параметры

    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        # Оптимизированные параметры
        ema_fast = kwargs.get('ema_fast', 6)  # 🆕 Оптимизировано: было 7
        ema_medium = kwargs.get('ema_medium', 14)  # 🆕 Новая средняя EMA
        ema_slow = kwargs.get('ema_slow', 22)  # 🆕 Оптимизировано: было 25
        min_distance = kwargs.get('ema_min_distance', 0.008)  # 🆕 Оптимизировано: было 0.01
        trend_strength = kwargs.get('ema_trend_strength', 0.003)  # Минимальная сила тренда

        if i < ema_slow:
            return False, f"Недостаточно данных для EMA (нужно {ema_slow})"

        # Получаем значения EMA (динамически)
        ema_fast_col = f'ema{ema_fast}'
        ema_medium_col = f'ema{ema_medium}'
        ema_slow_col = f'ema{ema_slow}'

        # Проверка наличия колонок EMA
        required_columns = [ema_fast_col, ema_medium_col, ema_slow_col]
        if not all(col in df.columns for col in required_columns):
            return False, f"Отсутствуют колонки EMA: {required_columns}"

        ema_fast_val = df.iloc[i][ema_fast_col]
        ema_medium_val = df.iloc[i][ema_medium_col]
        ema_slow_val = df.iloc[i][ema_slow_col]
        current_close = df.iloc[i]['close']

        # Проверка на NaN
        if pd.isna(current_close) or pd.isna(ema_fast_val) or pd.isna(ema_medium_val) or pd.isna(ema_slow_val):
            return False, "NaN значения в EMA данных"

        # 🆕 ОПТИМИЗИРОВАННЫЕ ПРОВЕРКИ:

        # 1. Многоуровневая проверка тренда
        fast_above_medium = ema_fast_val > ema_medium_val
        medium_above_slow = ema_medium_val > ema_slow_val

        # Все EMA должны быть выстроены в тренд
        if fast_above_medium != medium_above_slow:
            return False, "EMA не синхронизированы - нет четкого тренда"

        # 2. Проверка расстояния между EMA (оптимизированная)
        ema_distance = abs(ema_fast_val - ema_medium_val) / ema_medium_val if ema_medium_val > 0 else 0
        if ema_distance < min_distance:
            return False, f"EMA слишком близко: {ema_distance:.3%}"

        # 3. Проверка силы тренда
        trend_strength_actual = abs(ema_fast_val - ema_slow_val) / ema_slow_val if ema_slow_val > 0 else 0
        if trend_strength_actual < trend_strength:
            return False, f"Слабый тренд: {trend_strength_actual:.3%}"

        # 4. Проверка положения цены относительно EMA
        if fast_above_medium:  # Восходящий тренд
            if current_close < ema_fast_val * 0.985:  # 🆕 Оптимизировано: было 0.98
                return False, "Цена слишком далеко от быстрой EMA в восходящем тренде"
        else:  # Нисходящий тренд
            if current_close > ema_fast_val * 1.015:  # 🆕 Оптимизировано: было 1.02
                return False, "Цена слишком далеко от быстрой EMA в нисходящем тренде"

        # 5. Проверка на разворот (расширенная)
        if i > 2:
            trend_direction_changes = 0
            for j in range(1, 3):
                if i - j >= 0:
                    prev_fast = df.iloc[i-j][ema_fast_col]
                    prev_medium = df.iloc[i-j][ema_medium_col]
                    if (prev_fast > prev_medium) != fast_above_medium:
                        trend_direction_changes += 1

            if trend_direction_changes >= 2:
                return False, "Частые смены направления тренда"

        return True, None

    except Exception as e:
        logger.error("Ошибка в оптимизированном EMA фильтре: %s", e)
        return False, f"Exception: {str(e)}"


@track_filter_metrics(FilterType.MACD_FILTER)
def enhanced_macd_filter(df, i: int, **kwargs) -> Tuple[bool, Optional[str]]:
    """
    ОПТИМИЗИРОВАННЫЙ MACD фильтр для интрадей крипто

    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        **kwargs: Дополнительные параметры

    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        # Оптимизированные параметры
        # fast_period и signal_period используются в расчетах MACD, но не напрямую в этой функции
        slow_period = kwargs.get('macd_slow_period', 21)  # 🆕 Оптимизировано: было 26
        min_strength = kwargs.get('macd_min_strength', 0.003)  # 🆕 Оптимизировано: было 0.005
        histogram_min = kwargs.get('macd_histogram_min', 0.001)  # Минимальное значение гистограммы
        trend_confirmation = kwargs.get('macd_trend_confirmation', 2)  # Требовать подтверждение тренда

        if i < slow_period or i >= len(df):
            return False, f"Недостаточно данных для MACD (нужно {slow_period})"

        # Проверка наличия колонок MACD
        required_columns = ['macd', 'macd_signal', 'macd_hist']
        if not all(col in df.columns for col in required_columns):
            return False, "Отсутствуют колонки MACD"

        current_macd = df.iloc[i]['macd']
        current_signal = df.iloc[i]['macd_signal']
        current_hist = df.iloc[i]['macd_hist']

        # Проверка на NaN
        if pd.isna(current_macd) or pd.isna(current_signal) or pd.isna(current_hist):
            return False, "NaN значения в MACD данных"

        # 🆕 ОПТИМИЗИРОВАННЫЕ ПРОВЕРКИ:

        # 1. Проверка минимальной силы гистограммы
        if abs(current_hist) < histogram_min:
            return False, f"Слабая гистограмма MACD: {current_hist:.4f}"

        # 2. Оптимизированный расчет силы расхождения
        macd_strength = abs(current_hist) / (abs(current_macd) + 1e-9)
        if macd_strength < min_strength:
            return False, f"Слабое расхождение MACD: {macd_strength:.4f}"

        # 3. Проверка направления с подтверждением
        if i >= trend_confirmation:
            # Требуем подтверждение направления (2 свечи)
            prev_macd = df.iloc[i-1]['macd']
            prev_signal = df.iloc[i-1]['macd_signal']

            if (current_macd > current_signal and prev_macd <= prev_signal) or \
               (current_macd < current_signal and prev_macd >= prev_signal):
                return False, "MACD только что пересек сигнал - нестабильно"

        # 4. Проверка на дивергенцию (расширенная)
        if i > 7:
            # Простая проверка на дивергенцию
            lookback = 7
            recent_macd = df.iloc[i-lookback:i+1]['macd'].values
            recent_close = df.iloc[i-lookback:i+1]['close'].values

            # Проверка на дивергенцию
            price_trend = recent_close[-1] > recent_close[0]  # True если цена растет
            macd_trend = recent_macd[-1] > recent_macd[0]  # True если MACD растет

            if price_trend != macd_trend:
                # Дополнительная проверка силы дивергенции
                price_change = abs(recent_close[-1] - recent_close[0]) / recent_close[0] if recent_close[0] > 0 else 0
                macd_change = abs(recent_macd[-1] - recent_macd[0])

                if price_change > 0.03 and macd_change > 0.001:  # Значительные движения
                    return False, "Обнаружена дивергенция MACD"

        return True, None

    except Exception as e:
        logger.error("Ошибка в оптимизированном MACD фильтре: %s", e)
        return False, f"Exception: {str(e)}"


@track_filter_metrics(FilterType.RSI_FILTER)
def enhanced_rsi_filter(df, i: int, **kwargs) -> Tuple[bool, Optional[str]]:
    """
    Улучшенный фильтр RSI с метриками

    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        **kwargs: Дополнительные параметры

    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        # Проверка наличия необходимых данных
        if i < 14 or i >= len(df):
            return False, "Недостаточно данных для RSI фильтра"

        # Получение параметров (базовые значения - оптимизированы для крипто)
        base_rsi_period = kwargs.get('rsi_period', 14)
        base_rsi_oversold = kwargs.get('rsi_oversold', 28)  # 🆕 Оптимизировано: было 30
        base_rsi_overbought = kwargs.get('rsi_overbought', 72)  # 🆕 Оптимизировано: было 70

        # 🆕 Используем адаптивные уровни если доступны и включены
        use_adaptive = kwargs.get('use_adaptive_rsi', True) and ADAPTIVE_RSI_AVAILABLE
        symbol = kwargs.get('symbol', 'UNKNOWN')

        if use_adaptive and should_use_adaptive_rsi(symbol):
            try:
                adaptive_levels = get_adaptive_rsi_levels(
                    symbol, df, i,
                    base_overbought=base_rsi_overbought,
                    base_oversold=base_rsi_oversold,
                    base_period=base_rsi_period
                )
                rsi_oversold = adaptive_levels.get('oversold', base_rsi_oversold)
                rsi_overbought = adaptive_levels.get('overbought', base_rsi_overbought)
                volatility_pct = adaptive_levels.get('volatility', 0) * 100
                group = adaptive_levels.get('group', 'default')
                logger.debug("📊 [ADAPTIVE RSI] %s: волатильность=%.2f%%, "
                           "группа=%s, уровни=%.0f/%.0f",
                           symbol, volatility_pct, group, rsi_oversold, rsi_overbought)
            except Exception as e:
                logger.debug("⚠️ [ADAPTIVE RSI] Ошибка для %s: %s, используем базовые уровни", symbol, e)
                rsi_oversold = base_rsi_oversold
                rsi_overbought = base_rsi_overbought
        else:
            rsi_oversold = base_rsi_oversold
            rsi_overbought = base_rsi_overbought

        # Проверка наличия колонки RSI
        if 'rsi' not in df.columns:
            return False, "Отсутствует колонка RSI"

        # Получение текущего значения RSI
        current_rsi = df.iloc[i]['rsi']

        # Проверка на NaN
        if pd.isna(current_rsi):
            return False, "NaN значение в RSI"

        # Логика фильтра
        # Проверка экстремальных значений
        if current_rsi < rsi_oversold:
            return False, f"RSI в зоне перепроданности: {current_rsi:.2f}"

        if current_rsi > rsi_overbought:
            return False, f"RSI в зоне перекупленности: {current_rsi:.2f}"

        # Проверка на дивергенцию
        divergence_lookback = kwargs.get('divergence_lookback', 8)  # Оптимизировано для крипто (было 5)
        if i > divergence_lookback:
            # Простая проверка на дивергенцию
            recent_rsi = df.iloc[i-divergence_lookback:i+1]['rsi'].values
            recent_close = df.iloc[i-divergence_lookback:i+1]['close'].values

            # Проверка на восходящую дивергенцию
            if (recent_close[-1] < recent_close[0] and recent_rsi[-1] > recent_rsi[0]):
                return False, "Восходящая дивергенция RSI"

            # Проверка на нисходящую дивергенцию
            if (recent_close[-1] > recent_close[0] and recent_rsi[-1] < recent_rsi[0]):
                return False, "Нисходящая дивергенция RSI"

        # Проверка на стабильность RSI
        volatility_threshold = kwargs.get('volatility_threshold', 8)  # Оптимизировано для крипто (было 10)
        if i > 3:
            rsi_std = df.iloc[i-3:i+1]['rsi'].std()
            if rsi_std > volatility_threshold:  # Слишком волатильный RSI
                return False, f"Слишком волатильный RSI: std={rsi_std:.2f}"

        return True, None

    except Exception as e:
        logger.error("Ошибка в RSI фильтре: %s", e)
        return False, f"Exception: {str(e)}"


@track_filter_metrics(FilterType.VOLUME_FILTER)
def enhanced_volume_filter(df, i: int, **kwargs) -> Tuple[bool, Optional[str]]:
    """
    Улучшенный фильтр объема с метриками

    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        **kwargs: Дополнительные параметры

    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        # Проверка наличия необходимых данных
        if i < 20 or i >= len(df):
            return False, "Недостаточно данных для Volume фильтра"

        # Получение параметров (оптимизированы для крипто)
        volume_ratio_threshold = kwargs.get('volume_ratio_threshold', 1.2)  # 🆕 Оптимизировано: было 1.5
        min_volume = kwargs.get('min_volume', 500)  # 🆕 Оптимизировано: было 1000
        max_ratio = kwargs.get('max_ratio', 8)  # 🆕 Оптимизировано: было 10
        spike_threshold = kwargs.get('spike_threshold', 5.0)  # 🆕 Порог всплесков
        min_volume_usd = kwargs.get('min_volume_usd', 10000)  # 🆕 Минимальный объем в USD

        # Проверка наличия колонок объема
        if 'volume' not in df.columns:
            return False, "Отсутствует колонка volume"

        if 'volume_ratio' not in df.columns:
            return False, "Отсутствует колонка volume_ratio"

        # Получение текущих значений
        current_volume = df.iloc[i]['volume']
        current_close = df.iloc[i]['close']
        volume_ratio = df.iloc[i]['volume_ratio']

        # Проверка на NaN
        if pd.isna(current_volume) or pd.isna(volume_ratio) or pd.isna(current_close):
            return False, "NaN значения в Volume данных"

        # 🆕 Проверка минимального объема в USD
        volume_usd = current_volume * current_close
        if volume_usd < min_volume_usd:
            return False, f"Слишком низкий объем в USD: {volume_usd:.0f}"

        # Логика фильтра
        # Проверка минимального объема
        if current_volume < min_volume:
            return False, f"Слишком низкий объем: {current_volume:.0f}"

        # Проверка соотношения объема
        if volume_ratio < volume_ratio_threshold:
            return False, f"Низкое соотношение объема: {volume_ratio:.2f}"

        # 🆕 Проверка на аномальные всплески объема (оптимизированная)
        if volume_ratio > spike_threshold:
            # Анализируем природу всплеска
            if i > 0:
                price_change = abs(current_close - df.iloc[i-1]['close']) / df.iloc[i-1]['close']
                if price_change > 0.08:  # Движение > 8%
                    return False, (
                        f"Подозрительный всплеск объема: ratio={volume_ratio:.2f}, "
                        f"price_change={price_change:.2%}"
                    )

        # Проверка на аномально высокий объем (обновлено)
        if volume_ratio > max_ratio:  # 🆕 Оптимизировано: было 10
            return False, f"Аномально высокий объем: {volume_ratio:.2f}"

        # Проверка на стабильность объема
        if i > 5:
            recent_volumes = df.iloc[i-5:i+1]['volume'].values
            volume_std = np.std(recent_volumes)
            volume_mean = np.mean(recent_volumes)

            if volume_std > volume_mean * 2:  # Слишком волатильный объем
                return False, f"Слишком волатильный объем: std={volume_std:.0f}"

        return True, None

    except Exception as e:
        logger.error("Ошибка в Volume фильтре: %s", e)
        return False, f"Exception: {str(e)}"


@track_filter_metrics(FilterType.AI_FILTER)
def enhanced_ai_filter(df, i: int, **kwargs) -> Tuple[bool, Optional[str]]:
    """
    Улучшенный AI фильтр с метриками

    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        **kwargs: Дополнительные параметры

    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        # Проверка наличия необходимых данных
        if i < 50 or i >= len(df):
            return False, "Недостаточно данных для AI фильтра"

        # Получение параметров
        ai_confidence_threshold = kwargs.get('ai_confidence_threshold', 0.7)
        # ai_pattern_min_count используется для валидации паттернов, но не напрямую в этой функции

        # Проверка наличия AI данных
        ai_columns = ['ai_confidence', 'ai_pattern_match', 'ai_sentiment']
        if not all(col in df.columns for col in ai_columns):
            return False, "Отсутствуют AI колонки"

        # Получение текущих значений
        ai_confidence = df.iloc[i]['ai_confidence']
        ai_pattern_match = df.iloc[i]['ai_pattern_match']
        ai_sentiment = df.iloc[i]['ai_sentiment']

        # Проверка на NaN
        if pd.isna(ai_confidence) or pd.isna(ai_pattern_match) or pd.isna(ai_sentiment):
            return False, "NaN значения в AI данных"

        # Логика фильтра
        # Проверка уверенности AI
        if ai_confidence < ai_confidence_threshold:
            return False, f"Низкая уверенность AI: {ai_confidence:.2f}"

        # Проверка соответствия паттерну
        if ai_pattern_match < 0.5:
            return False, f"Слабое соответствие паттерну: {ai_pattern_match:.2f}"

        # Проверка настроения
        if abs(ai_sentiment) < 0.3:  # Нейтральное настроение
            return False, f"Нейтральное настроение: {ai_sentiment:.2f}"

        # Проверка на противоречие с другими индикаторами
        if i > 0:
            prev_confidence = df.iloc[i-1]['ai_confidence']
            if abs(ai_confidence - prev_confidence) > 0.5:  # Резкое изменение уверенности
                return False, "Резкое изменение уверенности AI"

        return True, None

    except Exception as e:
        logger.error("Ошибка в AI фильтре: %s", e)
        return False, f"Exception: {str(e)}"


class FilterPipeline:
    """Пайплайн фильтров с метриками"""

    def __init__(self):
        self.filters = {
            FilterType.BB_FILTER: enhanced_bb_filter,
            FilterType.EMA_FILTER: enhanced_ema_filter,
            FilterType.RSI_FILTER: enhanced_rsi_filter,
            FilterType.VOLUME_FILTER: enhanced_volume_filter,
            FilterType.AI_FILTER: enhanced_ai_filter,
        }
        self.logger = logging.getLogger("filter_pipeline")

    def apply_filters(self, df, i: int, enabled_filters: Dict[FilterType, bool], **kwargs) -> Tuple[bool, List[str]]:
        """
        Применение всех фильтров

        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            enabled_filters: Словарь включенных фильтров
            **kwargs: Дополнительные параметры

        Returns:
            Tuple[bool, List[str]]: (прошел_все_фильтры, список_причин_отклонения)
        """
        rejection_reasons = []

        for filter_type, is_enabled in enabled_filters.items():
            if not is_enabled:
                continue

            if filter_type not in self.filters:
                self.logger.warning("Фильтр %s не найден", filter_type.value)
                continue

            try:
                filter_func = self.filters[filter_type]
                passed, reason = filter_func(df, i, **kwargs)

                # Логируем результат фильтра в БД
                if FILTER_LOGGER_AVAILABLE:
                    try:
                        symbol = kwargs.get('symbol', 'UNKNOWN')
                        log_filter_check_async(
                            symbol=symbol,
                            filter_type=filter_type.value,
                            passed=passed,
                            reason=reason if not passed else None
                        )
                    except Exception as log_err:
                        self.logger.debug("Ошибка логирования фильтра %s: %s", filter_type.value, log_err)

                if not passed:
                    rejection_reasons.append(f"{filter_type.value}: {reason}")
                    self.logger.debug("Сигнал отклонен фильтром %s: %s", filter_type.value, reason)
                else:
                    self.logger.debug("Сигнал прошел фильтр %s", filter_type.value)

            except Exception as e:
                error_msg = f"Ошибка в фильтре {filter_type.value}: {e}"
                rejection_reasons.append(error_msg)
                self.logger.error(error_msg)

                # Логируем ошибку фильтра
                if FILTER_LOGGER_AVAILABLE:
                    try:
                        symbol = kwargs.get('symbol', 'UNKNOWN')
                        log_filter_check_async(
                            symbol=symbol,
                            filter_type=filter_type.value,
                            passed=False,
                            reason=error_msg
                        )
                    except Exception:
                        pass

        # Сигнал проходит, если нет причин отклонения
        passed = len(rejection_reasons) == 0

        if passed:
            self.logger.info("Сигнал прошел все фильтры")
        else:
            reasons_str = ', '.join(rejection_reasons)
            self.logger.info("Сигнал отклонен: %s", reasons_str)

        return passed, rejection_reasons
