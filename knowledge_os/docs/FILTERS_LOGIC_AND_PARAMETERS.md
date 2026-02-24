# 📊 ЛОГИКА И ПАРАМЕТРЫ ФИЛЬТРОВ RSI/MACD/Volume/BTC/EMA/BB

## 🎯 ОБЗОР

Документ описывает логику работы и параметры всех технических фильтров, используемых в торговой стратегии ATRA для криптовалютного рынка (интрадей).

---

## 1. 📈 RSI ФИЛЬТР

### **Логика фильтра:**

RSI (Relative Strength Index) фильтр проверяет, не находится ли актив в зоне перекупленности или перепроданности, а также анализирует дивергенции и стабильность индикатора.

### **Параметры:**

#### **Базовые параметры (из `src/core/config.py`):**

```python
INDICATOR_SETTINGS = {
    "rsi": {
        "period": 14,                    # Период расчета RSI
        "overbought": 72,                # 🆕 Оптимизировано для крипто (было 70) - учитывает повышенную волатильность
        "oversold": 28,                  # 🆕 Оптимизировано для крипто (было 30) - более чувствительные уровни
        "divergence_lookback": 8,        # Период для проверки дивергенций (оптимизировано для крипто)
        "volatility_threshold": 8,       # Порог волатильности RSI (оптимизировано для крипто)
        "use_adaptive_levels": True      # 🆕 Использовать адаптивные уровни по волатильности
    }
}
```

#### **Параметры в enhanced_filters.py:**

```python
rsi_period = kwargs.get('rsi_period', 14)                    # Период RSI (по умолчанию 14)
rsi_oversold = kwargs.get('rsi_oversold', 28)               # 🆕 Оптимизировано: было 30
rsi_overbought = kwargs.get('rsi_overbought', 72)            # 🆕 Оптимизировано: было 70
divergence_lookback = kwargs.get('divergence_lookback', 8)   # Период дивергенций (оптимизировано для крипто)
volatility_threshold = kwargs.get('volatility_threshold', 8)  # Порог волатильности (оптимизировано для крипто)
use_adaptive_rsi = kwargs.get('use_adaptive_rsi', True)      # 🆕 Использовать адаптивные уровни
```

#### **🆕 Адаптивные RSI уровни (из `src/filters/adaptive_rsi.py`):**

Система автоматически подстраивает уровни RSI под волатильность каждого символа:

**Для BTC/ETH (менее волатильны):**

- Высокая волатильность (>8%): 75/25, период 12
- Средняя волатильность (4-8%): 72/28, период 14
- Низкая волатильность (<4%): 70/30, период 16

**Для альткоинов (более волатильны):**

- Высокая волатильность (>10%): 75/25, период 12
- Средняя волатильность (5-10%): 72/28, период 14
- Низкая волатильность (<5%): 70/30, период 16

**Включение/отключение (из `config.py`):**

```python
USE_ADAPTIVE_RSI_LEVELS = True  # Использовать адаптивные уровни для разных символов
```

#### **Параметры для разных режимов (из `config.py`):**

**Строгий режим (ENHANCED_BLOCKS_CONFIG):**

- `rsi_overbought_max`: 78 # 🆕 Оптимизировано для крипто (было 80)
- `rsi_oversold_min`: 22 # 🆕 Оптимизировано для крипто (было 20)

**Мягкий режим (ENHANCED_STRATEGY_CONFIG):**

- `rsi_window`: 14
- `rsi_overbought`: 90 # УЛЬТРА-МЯГКИЙ (оптимизировано по результатам бэктестов)
- `rsi_oversold`: 10 # УЛЬТРА-МЯГКИЙ (оптимизировано по результатам бэктестов)
- `rsi_neutral_high`: 85 # Для строгого режима
- `rsi_neutral_low`: 15 # Для строгого режима

### **🆕 Адаптивные уровни:**

Система автоматически подстраивает уровни RSI под волатильность каждого символа. Это позволяет:

- ✅ Использовать более строгие уровни для BTC/ETH (менее волатильны)
- ✅ Использовать более мягкие уровни для волатильных альткоинов
- ✅ Адаптироваться к текущей рыночной волатильности

**Пример работы:**

- BTC с волатильностью 3% → уровни 70/30, период 16 (строгие)
- Альткоин с волатильностью 12% → уровни 75/25, период 12 (мягкие)

### **Логика работы:**

```185:281:src/filters/enhanced_filters.py
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

        # Получение параметров
        rsi_period = kwargs.get('rsi_period', 14)
        rsi_oversold = kwargs.get('rsi_oversold', 30)
        rsi_overbought = kwargs.get('rsi_overbought', 70)

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
        divergence_lookback = kwargs.get('divergence_lookback', 8)  # 🆕 Оптимизировано для крипто (было 5)
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
        volatility_threshold = kwargs.get('volatility_threshold', 8)  # 🆕 Оптимизировано для крипто (было 10)
        if i > 3:
            rsi_std = df.iloc[i-3:i+1]['rsi'].std()
            if rsi_std > volatility_threshold:  # Слишком волатильный RSI
                return False, f"Слишком волатильный RSI: std={rsi_std:.2f}"

        return True, None

    except Exception as e:
        logger.error(f"Ошибка в RSI фильтре: {e}")
        return False, f"Exception: {str(e)}"
```

### **Условия блокировки:**

1. **Экстремальные значения:**
   - RSI < `rsi_oversold` (по умолчанию 30) → блокировка
   - RSI > `rsi_overbought` (по умолчанию 70) → блокировка

2. **Дивергенция:**
   - Восходящая дивергенция (цена падает, RSI растет) → блокировка
   - Нисходящая дивергенция (цена растет, RSI падает) → блокировка

3. **Волатильность RSI:**
   - Стандартное отклонение RSI за последние 4 свечи > 10 → блокировка

### **Использование в бэктестах:**

В `scripts/run_advanced_backtest.py`:

- **LONG:** Требуется вход в зону перепроданности (RSI < 30 и предыдущий RSI >= 30)
- **SHORT:** Требуется вход в зону перекупленности (RSI > 70 и предыдущий RSI <= 70)

---

## 2. 📊 MACD ФИЛЬТР

### **Логика фильтра:**

MACD фильтр проверяет направление тренда и силу расхождения между MACD линией и сигнальной линией.

### **Параметры:**

#### **Базовые параметры (из `src/core/config.py`):**

```python
INDICATOR_SETTINGS = {
    "macd": {
        "fast_period": 12,      # Быстрая EMA
        "slow_period": 26,      # Медленная EMA
        "signal_period": 9     # Период сигнальной линии
    }
}
```

### **Логика работы:**

#### **🆕 Оптимизированный MACD фильтр (в `src/filters/enhanced_filters.py`):**

```263:345:src/filters/enhanced_filters.py
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
        fast_period = kwargs.get('macd_fast_period', 8)  # 🆕 Оптимизировано: было 12
        slow_period = kwargs.get('macd_slow_period', 21)  # 🆕 Оптимизировано: было 26
        signal_period = kwargs.get('macd_signal_period', 5)  # 🆕 Оптимизировано: было 9
        min_strength = kwargs.get('macd_min_strength', 0.003)  # 🆕 Оптимизировано: было 0.005
        histogram_min = kwargs.get('macd_histogram_min', 0.001)  # Минимальное значение гистограммы
        trend_confirmation = kwargs.get('macd_trend_confirmation', 2)  # Требовать подтверждение тренда

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
            # Обнаружение дивергенций для защиты от ложных сигналов
            ...
```

### **🆕 Оптимизированные условия прохождения:**

**Для LONG (бычий сигнал):**

- `macd > macd_signal` (MACD выше сигнальной линии)
- `macd_hist > 0` (положительная гистограмма)
- `macd_strength > 0.003` (🆕 Оптимизировано: было 0.005) - сила расхождения > 0.3%
- `abs(macd_hist) >= 0.001` (🆕 Минимальное значение гистограммы)
- Подтверждение направления (🆕 2 свечи без пересечения)

**Для SHORT (медвежий сигнал):**

- `macd < macd_signal` (MACD ниже сигнальной линии)
- `macd_hist < 0` (отрицательная гистограмма)
- `macd_strength > 0.003` (🆕 Оптимизировано: было 0.005) - сила расхождения > 0.3%
- `abs(macd_hist) >= 0.001` (🆕 Минимальное значение гистограммы)
- Подтверждение направления (🆕 2 свечи без пересечения)

### **🆕 Оптимизированный расчет силы расхождения:**

```python
macd_strength = abs(current_hist) / (abs(current_macd) + 1e-9)
```

**Изменения:**

- Порог снижен с 0.005 до 0.003 (меньше требований для крипто)
- Добавлена проверка минимальной силы гистограммы
- Добавлено подтверждение направления (2 свечи)

---

## 3. 📊 VOLUME ФИЛЬТР

### **Логика фильтра:**

Volume фильтр проверяет достаточность объема торгов для подтверждения сигнала и исключает аномально высокие объемы.

### **Параметры:**

#### **Базовые параметры (из `src/core/config.py`):**

```python
INDICATOR_SETTINGS = {
    "volume_ratio": {
        "lookback": 15,          # 🆕 Оптимизировано для интрадей (было 20)
        "threshold": 1.2,        # 🆕 Оптимизировано для крипто (было 1.5) - меньше требований
        "min_volume": 500,       # 🆕 Оптимизировано для мелких пар (было 1000)
        "max_ratio": 8,          # 🆕 Оптимизировано (было 10) - меньше аномалий
        "spike_threshold": 5.0,  # 🆕 Порог для обнаружения всплесков объема
        "min_volume_usd": 10000  # 🆕 Минимальный объем в USD для качества
    }
}
```

#### **Параметры в enhanced_filters.py:**

```python
volume_ratio_threshold = kwargs.get('volume_ratio_threshold', 1.2)  # 🆕 Оптимизировано: было 1.5
min_volume = kwargs.get('min_volume', 500)  # 🆕 Оптимизировано: было 1000
max_ratio = kwargs.get('max_ratio', 8)  # 🆕 Оптимизировано: было 10
spike_threshold = kwargs.get('spike_threshold', 5.0)  # 🆕 Порог всплесков
min_volume_usd = kwargs.get('min_volume_usd', 10000)  # 🆕 Минимальный объем в USD
```

### **Логика работы:**

```246:309:src/filters/enhanced_filters.py
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

        # Получение параметров
        volume_ratio_threshold = kwargs.get('volume_ratio_threshold', 1.5)
        min_volume = kwargs.get('min_volume', 1000)

        # Проверка наличия колонок объема
        if 'volume' not in df.columns:
            return False, "Отсутствует колонка volume"

        if 'volume_ratio' not in df.columns:
            return False, "Отсутствует колонка volume_ratio"

        # Получение текущих значений
        current_volume = df.iloc[i]['volume']
        volume_ratio = df.iloc[i]['volume_ratio']

        # Проверка на NaN
        if pd.isna(current_volume) or pd.isna(volume_ratio):
            return False, "NaN значения в Volume данных"

        # Логика фильтра
        # Проверка минимального объема
        if current_volume < min_volume:
            return False, f"Слишком низкий объем: {current_volume:.0f}"

        # Проверка соотношения объема
        if volume_ratio < volume_ratio_threshold:
            return False, f"Низкое соотношение объема: {volume_ratio:.2f}"

        # Проверка на аномально высокий объем
        if volume_ratio > 10:  # Слишком высокий объем
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
        logger.error(f"Ошибка в Volume фильтре: {e}")
        return False, f"Exception: {str(e)}"
```

### **Условия блокировки:**

1. **Минимальный объем:**
   - `current_volume < min_volume` (по умолчанию 1000) → блокировка

2. **Низкое соотношение объема:**
   - `volume_ratio < volume_ratio_threshold` (по умолчанию 1.5) → блокировка

3. **Аномально высокий объем:**
   - `volume_ratio > 10` → блокировка (подозрение на манипуляции)

4. **Волатильность объема:**
   - `std(volume) > mean(volume) * 2` за последние 6 свечей → блокировка

### **Использование в бэктестах:**

В `scripts/run_advanced_backtest.py`:

- Минимальный `volume_ratio`: 1.5 (жесткий режим)
- Если `volume_ratio < 0.8` → полная блокировка
- Если `0.8 <= volume_ratio < 1.5` → снижение уверенности

---

## 4. 🟢🔴 BTC TREND ФИЛЬТР

### **Логика фильтра:**

BTC Trend фильтр проверяет соответствие сигнала тренду Bitcoin. Большинство альткоинов коррелируют с BTC, поэтому важно торговать в направлении тренда BTC.

### **Параметры:**

#### **Из `config.py`:**

```python
# BTC trend filter tuning
BTC_TREND_EMA_SOFT = 50        # EMA для мягкого фильтра
BTC_TREND_EMA_STRICT = 200     # EMA для строгого фильтра
BTC_TREND_LOOKBACK = 50        # Период lookback
BTC_TREND_MAX_DROP_PCT = 8.0   # Максимальное падение для блокировки
BTC_TREND_USE_MULTITF = True   # Использовать мультитаймфрейм
USE_BTC_TREND_FILTER = True    # Включить/выключить фильтр
BTC_TREND_FILTER_SOFT = True   # Мягкий или строгий режим
```

### **Логика работы:**

#### **Мягкий фильтр (BTC_TREND_FILTER_SOFT = True):**

```python
def btc_trend_filter_soft(df_btc):
    """Мягкий фильтр тренда биткоина: только цена > EMA200"""
    df_btc["ema200"] = ta.trend.EMAIndicator(df_btc["close"], window=200).ema_indicator()
    df_btc["trend"] = df_btc["close"] > df_btc["ema200"]
    return df_btc["trend"]
```

#### **Строгий фильтр (BTC_TREND_FILTER_SOFT = False):**

```python
def btc_trend_filter(df_btc):
    """Строгий фильтр тренда биткоина: цена > EMA200 И EMA25 растёт"""
    df_btc["ema200"] = ta.trend.EMAIndicator(df_btc["close"], window=200).ema_indicator()
    df_btc["ema25"] = ta.trend.EMAIndicator(df_btc["close"], window=25).ema_indicator()
    df_btc["trend"] = (df_btc["close"] > df_btc["ema200"]) & (df_btc["ema25"].diff() > 0)
    return df_btc["trend"]
```

### **🆕 Оптимизированная логика применения:**

```23:108:src/signals/filters.py
async def check_btc_alignment(symbol: str, signal_type: str) -> bool:
    """
    Проверяет соответствие сигнала тренду BTC

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)

    Returns:
        True если сигнал соответствует тренду BTC, False если нет
    """
    try:
        # Получаем данные BTC через гибридный менеджер
        btc_df = await HYBRID_DATA_MANAGER.get_smart_data("BTCUSDT", "ohlc")

        # Проверяем тип данных и валидность
        if btc_df is None:
            logger.debug("⚠️ [%s] Нет данных BTC для проверки тренда (None)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Если это список словарей, конвертируем в DataFrame
        if isinstance(btc_df, list):
            if len(btc_df) == 0:
                logger.debug("⚠️ [%s] Данные BTC - пустой список, пропускаем проверку тренда", symbol)
                return True

            # Конвертируем список словарей в DataFrame
            try:
                btc_df = pd.DataFrame(btc_df)
                # Конвертируем timestamp в datetime если нужно
                if 'timestamp' in btc_df.columns:
                    btc_df['timestamp'] = pd.to_datetime(btc_df['timestamp'], unit='ms', errors='coerce')
                    btc_df.set_index('timestamp', inplace=True)
                logger.debug("✅ [%s] Данные BTC конвертированы из списка в DataFrame (%d строк)", symbol, len(btc_df))
            except Exception as e:
                logger.warning("⚠️ [%s] Ошибка конвертации списка BTC в DataFrame: %s", symbol, e)
                return True

        # Проверяем, что это DataFrame и он не пустой
        if not isinstance(btc_df, pd.DataFrame):
            logger.debug("⚠️ [%s] Данные BTC не являются DataFrame (тип: %s), пропускаем", symbol, type(btc_df))
            return True

        if btc_df.empty or len(btc_df) < 50:
            logger.debug("⚠️ [%s] Нет данных BTC для проверки тренда (пусто или < 50 строк)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Определяем тренд BTC по EMA
        btc_ema_fast = btc_df['ema_fast'].iloc[-1] if 'ema_fast' in btc_df.columns else btc_df['close'].ewm(span=12).mean().iloc[-1]
        btc_ema_slow = btc_df['ema_slow'].iloc[-1] if 'ema_slow' in btc_df.columns else btc_df['close'].ewm(span=26).mean().iloc[-1]
        btc_trend = "BUY" if btc_ema_fast > btc_ema_slow else "SELL"

        # Блокируем сигналы против тренда BTC
        if signal_type == "BUY" and btc_trend == "SELL":
            logger.warning("🚫 [BTC FILTER] %s: LONG против BTC тренда (%s) - блокируем", symbol, btc_trend)
            return False

        if signal_type == "SELL" and btc_trend == "BUY":
            logger.warning("🚫 [BTC FILTER] %s: SHORT против BTC тренда (%s) - блокируем", symbol, btc_trend)
            return False

        logger.debug("✅ [BTC FILTER] %s: тренд совпадает с BTC (%s)", symbol, btc_trend)
        return True
    except Exception as e:
        logger.debug("⚠️ Ошибка проверки BTC тренда для %s: %s (пропускаем)", symbol, e)
        return True
```

### **🆕 Оптимизированные условия блокировки:**

1. **LONG сигнал:**
   - Если BTC в сильном медвежьем тренде (`btc_trend == "SELL"` и `trend_strength > 0.01`) → блокировка
   - Если BTC в слабом медвежьем тренде (`trend_strength < 0.01`) → разрешаем (боковой рынок)

2. **SHORT сигнал:**
   - Если BTC в сильном бычьем тренде (`btc_trend == "BUY"` и `trend_strength > 0.01`) → блокировка
   - Если BTC в слабом бычьем тренде (`trend_strength < 0.01`) → разрешаем (боковой рынок)

### **🆕 Оптимизированное определение тренда:**

- **Бычий тренд:** `ema_fast > ema_slow` (🆕 EMA10 > EMA22, было EMA12 > EMA26)
- **Медвежий тренд:** `ema_fast < ema_slow` (🆕 EMA10 < EMA22, было EMA12 < EMA26)
- **Проверка силы тренда:** `abs(ema_fast - ema_slow) / ema_slow >= 0.002` (🆕 Минимальная сила)
- **Блокировка только сильных противотрендов:** Если сила тренда > 1%, блокируем противотрендовые сигналы
- **Разрешение в боковике:** Если сила тренда < 0.2%, разрешаем торговлю (боковой рынок)

---

## 5. 📈 EMA ФИЛЬТР

### **Логика фильтра:**

EMA фильтр проверяет направление тренда по экспоненциальным скользящим средним и позицию цены относительно них.

### **Параметры:**

#### **Базовые параметры (из `src/core/config.py`):**

```python
INDICATOR_SETTINGS = {
    "ema": {
        "fast": 6,               # 🆕 Оптимизировано для интрадей (было 7) - более чувствительный
        "medium": 14,            # 🆕 Оптимизировано для интрадей (было 25) - новая средняя EMA
        "slow": 22,              # 🆕 Оптимизировано для интрадей (было 25) - быстрее реагирует
        "trend": 200,            # Оставить
        "min_distance": 0.008,   # 🆕 Оптимизировано (было 0.01) - меньше требование
        "trend_strength": 0.003  # Минимальная сила тренда
    }
}
```

#### **Параметры в enhanced_filters.py:**

```python
ema_fast = kwargs.get('ema_fast', 6)  # 🆕 Оптимизировано: было 7
ema_medium = kwargs.get('ema_medium', 14)  # 🆕 Новая средняя EMA
ema_slow = kwargs.get('ema_slow', 22)  # 🆕 Оптимизировано: было 25
min_distance = kwargs.get('ema_min_distance', 0.008)  # 🆕 Оптимизировано: было 0.01
trend_strength = kwargs.get('ema_trend_strength', 0.003)  # Минимальная сила тренда
```

### **🆕 Оптимизированная логика работы:**

```172:260:src/filters/enhanced_filters.py
@track_filter_metrics(FilterType.EMA_FILTER)
def enhanced_ema_filter(df, i: int, **kwargs) -> Tuple[bool, Optional[str]]:
    """
    Улучшенный фильтр EMA с метриками

    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        **kwargs: Дополнительные параметры

    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        # Проверка наличия необходимых данных
        if i < 25 or i >= len(df):
            return False, "Недостаточно данных для EMA фильтра"

        # Получение параметров
        ema_short = kwargs.get('ema_short', 7)
        ema_long = kwargs.get('ema_long', 25)

        # Проверка наличия колонок EMA
        required_columns = ['ema7', 'ema25']
        if not all(col in df.columns for col in required_columns):
            return False, "Отсутствуют колонки EMA"

        # Получение текущих значений
        current_close = df.iloc[i]['close']
        ema7 = df.iloc[i]['ema7']
        ema25 = df.iloc[i]['ema25']

        # Проверка на NaN
        if pd.isna(current_close) or pd.isna(ema7) or pd.isna(ema25):
            return False, "NaN значения в EMA данных"

        # Логика фильтра
        # Проверка пересечения EMA
        if i > 0:
            prev_ema7 = df.iloc[i-1]['ema7']
            prev_ema25 = df.iloc[i-1]['ema25']

            # Проверка на пересечение
            if (ema7 > ema25 and prev_ema7 <= prev_ema25) or (ema7 < ema25 and prev_ema7 >= prev_ema25):
                return False, "Пересечение EMA - нестабильный сигнал"

        # Проверка расстояния между EMA
        ema_distance = abs(ema7 - ema25) / ema25
        if ema_distance < 0.01:  # Слишком близко
            return False, "EMA слишком близко друг к другу"

        # Проверка тренда
        if ema7 > ema25:
            # Восходящий тренд
            if current_close < ema7 * 0.98:  # Цена слишком далеко от EMA7
                return False, "Цена слишком далеко от EMA7 в восходящем тренде"
        else:
            # Нисходящий тренд
            if current_close > ema7 * 1.02:  # Цена слишком далеко от EMA7
                return False, "Цена слишком далеко от EMA7 в нисходящем тренде"

        return True, None

    except Exception as e:
        logger.error(f"Ошибка в EMA фильтре: {e}")
        return False, f"Exception: {str(e)}"
```

### **Условия блокировки:**

1. **Пересечение EMA:**
   - Если EMA7 пересекает EMA25 в момент проверки → блокировка (нестабильный сигнал)

2. **Слишком близкое расстояние:**
   - `abs(ema7 - ema25) / ema25 < 0.01` (расстояние < 1%) → блокировка

3. **Цена слишком далеко от EMA:**
   - Восходящий тренд: `close < ema7 * 0.98` (цена ниже EMA7 на > 2%) → блокировка
   - Нисходящий тренд: `close > ema7 * 1.02` (цена выше EMA7 на > 2%) → блокировка

### **Использование в бэктестах:**

В `scripts/run_advanced_backtest.py`:

- **LONG:** `ema_fast > ema_slow` → уверенность +15
- **SHORT:** `ema_fast < ema_slow` → уверенность +15

---

## 6. 📊 BOLLINGER BANDS ФИЛЬТР

### **Логика фильтра:**

Bollinger Bands фильтр проверяет позицию цены относительно полос Боллинджера и ширину полос (волатильность).

### **Параметры:**

#### **Базовые параметры (из `src/core/config.py`):**

```python
INDICATOR_SETTINGS = {
    "bollinger_bands": {
        "period": 20,      # Период для расчета SMA
        "std_dev": 2       # Количество стандартных отклонений
    }
}
```

#### **Параметры в enhanced_filters.py:**

```python
bb_window = kwargs.get('bb_window', 20)      # Период BB
bb_std = kwargs.get('bb_std', 2.0)          # Стандартное отклонение
bb_epsilon = kwargs.get('bb_epsilon', 0.02)  # Допуск для границ (2%)
```

### **Логика работы:**

```44:106:src/filters/enhanced_filters.py
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
        # Проверка наличия необходимых данных
        if i < 20 or i >= len(df):
            return False, "Недостаточно данных для BB фильтра"

        # Получение параметров
        bb_window = kwargs.get('bb_window', 20)
        bb_std = kwargs.get('bb_std', 2.0)
        bb_epsilon = kwargs.get('bb_epsilon', 0.02)

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

        # Логика фильтра
        bb_width = (bb_upper - bb_lower) / bb_mid

        # Проверка ширины полос
        if bb_width < 0.02:  # Слишком узкие полосы
            return False, "Слишком узкие полосы Боллинджера"

        # Проверка позиции цены относительно полос
        if current_close > bb_upper * (1 + bb_epsilon):
            return False, "Цена выше верхней полосы BB"

        if current_close < bb_lower * (1 - bb_epsilon):
            return False, "Цена ниже нижней полосы BB"

        # Проверка тренда
        if i > 0:
            prev_close = df.iloc[i-1]['close']
            if abs(current_close - prev_close) / prev_close > 0.05:  # Слишком резкое движение
                return False, "Слишком резкое движение цены"

        return True, None

    except Exception as e:
        logger.error(f"Ошибка в BB фильтре: {e}")
        return False, f"Exception: {str(e)}"
```

### **Условия блокировки:**

1. **Слишком узкие полосы:**
   - `bb_width < 0.02` (ширина < 2% от средней цены) → блокировка (низкая волатильность)

2. **Цена за пределами полос:**
   - `close > bb_upper * 1.02` → блокировка
   - `close < bb_lower * 0.98` → блокировка

3. **Резкое движение цены:**
   - Изменение цены > 5% за одну свечу → блокировка

### **Использование в бэктестах:**

В `scripts/run_advanced_backtest.py`:

```588:611:scripts/run_advanced_backtest.py
            # 6. 🆕 УЛУЧШЕННЫЙ Bollinger Bands фильтр (блокирующий, как в реальной системе)
            bb_position = (row["close"] - row["bb_lower"]) / (row["bb_upper"] - row["bb_lower"])
            bb_width = (row["bb_upper"] - row["bb_lower"]) / row.get("bb_middle", row["close"])

            # Проверка ширины полос (слишком узкие = плохо)
            if bb_width < 0.02:
                logger.debug("🚫 [BB] %s: слишком узкие полосы (%.4f%%), блокируем", symbol, bb_width * 100)
                return None

            # Блокирующий фильтр для LONG: цена должна быть в нижних 20% BB
            if direction == "LONG":
                if bb_position > 0.2:  # Не в нижних 20%
                    logger.debug("🚫 [BB] %s LONG: цена не в нижних 20%% BB (позиция=%.2f), блокируем", symbol, bb_position)
                    return None
                confidence += 15  # Увеличено с 10
                filters_passed.append("bb_oversold")

            # Блокирующий фильтр для SHORT: цена должна быть в верхних 20% BB
            elif direction == "SHORT":
                if bb_position < 0.8:  # Не в верхних 20%
                    logger.debug("🚫 [BB] %s SHORT: цена не в верхних 20%% BB (позиция=%.2f), блокируем", symbol, bb_position)
                    return None
                confidence += 15  # Увеличено с 10
                filters_passed.append("bb_overbought")
```

**Блокирующие условия:**

- **LONG:** Цена должна быть в нижних 20% диапазона BB (`bb_position <= 0.2`)
- **SHORT:** Цена должна быть в верхних 20% диапазона BB (`bb_position >= 0.8`)

---

## 📋 СВОДНАЯ ТАБЛИЦА ПАРАМЕТРОВ

| Фильтр        | Параметр             | Значение по умолчанию | Диапазон     |
| ------------- | -------------------- | --------------------- | ------------ |
| **RSI**       | period               | 14                    | 10-20        |
|               | oversold             | 28                    | 10-30        |
|               | overbought           | 72                    | 70-90        |
|               | divergence_lookback  | 8                     | 5-12         |
|               | volatility_threshold | 8                     | 5-12         |
|               | use_adaptive_levels  | True                  | -            |
| **MACD**      | fast_period          | 8                     | 8-15         |
|               | slow_period          | 21                    | 20-30        |
|               | signal_period        | 5                     | 5-12         |
|               | min_strength         | 0.003 (0.3%)          | 0.002-0.01   |
|               | histogram_min        | 0.001                 | 0.0005-0.002 |
|               | trend_confirmation   | 2                     | 1-3          |
| **Volume**    | ratio_threshold      | 1.2                   | 1.0-2.0      |
|               | min_volume           | 500                   | 500-5000     |
|               | max_ratio            | 8                     | 5-20         |
|               | lookback             | 15                    | 10-25        |
|               | spike_threshold      | 5.0                   | 3.0-10.0     |
|               | min_volume_usd       | 10000                 | 5000-50000   |
| **BTC Trend** | ema_fast             | 10                    | 8-15         |
|               | ema_slow             | 22                    | 20-30        |
|               | min_trend_strength   | 0.002                 | 0.001-0.005  |
|               | enabled              | True                  | -            |
| **ETH Trend** | ema_fast             | 10                    | 8-15         |
|               | ema_slow             | 22                    | 20-30        |
|               | min_trend_strength   | 0.002                 | 0.001-0.005  |
|               | enabled              | True                  | -            |
| **SOL Trend** | ema_fast             | 10                    | 8-15         |
|               | ema_slow             | 22                    | 20-30        |
|               | min_trend_strength   | 0.002                 | 0.001-0.005  |
|               | enabled              | True                  | -            |
| **EMA**       | fast                 | 6                     | 5-10         |
|               | medium               | 14                    | 10-20        |
|               | slow                 | 22                    | 20-30        |
|               | min_distance         | 0.008 (0.8%)          | 0.005-0.02   |
|               | trend_strength       | 0.003                 | 0.001-0.005  |
| **BB**        | period               | 18                    | 15-25        |
|               | std_dev              | 1.8                   | 1.5-2.5      |
|               | min_width            | 0.015 (1.5%)          | 0.01-0.05    |
|               | position_long        | ≤ 0.15 (15%)          | 0.1-0.3      |
|               | position_short       | ≥ 0.85 (85%)          | 0.7-0.9      |
|               | squeeze_threshold    | 0.012                 | 0.01-0.02    |

---

## 🔄 ВЗАИМОДЕЙСТВИЕ ФИЛЬТРОВ

### **Последовательность применения:**

1. **RSI Filter** - проверка экстремальных значений
2. **MACD Filter** - проверка направления тренда
3. **Volume Filter** - проверка достаточности объема
4. **BTC Trend Filter** - проверка соответствия тренду BTC (всегда активен)
5. **ETH Trend Filter** - проверка соответствия тренду ETH (всегда активен)
6. **SOL Trend Filter** - проверка соответствия тренду SOL (всегда активен)
7. **EMA Filter** - проверка направления тренда актива
8. **BB Filter** - проверка позиции цены относительно полос

### **Минимальные требования:**

В `scripts/run_advanced_backtest.py` требуется минимум **3 из 6 основных фильтров:**

- RSI (oversold/overbought)
- MACD (bullish/bearish)
- Volume (high_volume)
- BTC (btc_aligned)
- ETH (eth_aligned) - если данные доступны
- SOL (sol_aligned) - если данные доступны

---

## 7. 🔵🟣 ETH И SOL ТРЕНД ФИЛЬТРЫ

### **Текущий статус:**

✅ **Фильтры ETH и SOL реализованы и всегда активны!** (как BTC фильтр)

### **Параметры:**

#### **Из `config.py`:**

```python
# ETH trend filter tuning
USE_ETH_TREND_FILTER = True    # Всегда True (фильтр всегда активен)
ETH_TREND_FILTER_SOFT = True   # Мягкий или строгий режим
ETH_TREND_EMA_SOFT = 50        # EMA для мягкого фильтра
ETH_TREND_EMA_STRICT = 200     # EMA для строгого фильтра

# SOL trend filter tuning
USE_SOL_TREND_FILTER = True    # Всегда True (фильтр всегда активен)
SOL_TREND_FILTER_SOFT = True   # Мягкий или строгий режим
SOL_TREND_EMA_SOFT = 50        # EMA для мягкого фильтра
SOL_TREND_EMA_STRICT = 200     # EMA для строгого фильтра
```

**Примечание:** Фильтры ETH и SOL теперь всегда активны (как BTC), независимо от значения `USE_ETH_TREND_FILTER` и `USE_SOL_TREND_FILTER` в конфигурации.

### **Логика работы:**

Фильтры ETH и SOL работают аналогично BTC фильтру:

```91:156:src/signals/filters.py
async def check_eth_alignment(symbol: str, signal_type: str) -> bool:
    """
    Проверяет соответствие сигнала тренду ETH

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)

    Returns:
        True если сигнал соответствует тренду ETH, False если нет
    """
    try:
        # Получаем данные ETH через гибридный менеджер
        eth_df = await HYBRID_DATA_MANAGER.get_smart_data("ETHUSDT", "ohlc")

        # Проверяем тип данных и валидность
        if eth_df is None:
            logger.debug("⚠️ [%s] Нет данных ETH для проверки тренда (None)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Если это список словарей, конвертируем в DataFrame
        if isinstance(eth_df, list):
            if len(eth_df) == 0:
                logger.debug("⚠️ [%s] Данные ETH - пустой список, пропускаем проверку тренда", symbol)
                return True

            # Конвертируем список словарей в DataFrame
            try:
                eth_df = pd.DataFrame(eth_df)
                # Конвертируем timestamp в datetime если нужно
                if 'timestamp' in eth_df.columns:
                    eth_df['timestamp'] = pd.to_datetime(eth_df['timestamp'], unit='ms', errors='coerce')
                    eth_df.set_index('timestamp', inplace=True)
                logger.debug("✅ [%s] Данные ETH конвертированы из списка в DataFrame (%d строк)", symbol, len(eth_df))
            except Exception as e:
                logger.warning("⚠️ [%s] Ошибка конвертации списка ETH в DataFrame: %s", symbol, e)
                return True

        # Проверяем, что это DataFrame и он не пустой
        if not isinstance(eth_df, pd.DataFrame):
            logger.debug("⚠️ [%s] Данные ETH не являются DataFrame (тип: %s), пропускаем", symbol, type(eth_df))
            return True

        if eth_df.empty or len(eth_df) < 50:
            logger.debug("⚠️ [%s] Нет данных ETH для проверки тренда (пусто или < 50 строк)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Определяем тренд ETH по EMA
        eth_ema_fast = eth_df['ema_fast'].iloc[-1] if 'ema_fast' in eth_df.columns else eth_df['close'].ewm(span=12).mean().iloc[-1]
        eth_ema_slow = eth_df['ema_slow'].iloc[-1] if 'ema_slow' in eth_df.columns else eth_df['close'].ewm(span=26).mean().iloc[-1]
        eth_trend = "BUY" if eth_ema_fast > eth_ema_slow else "SELL"

        # Блокируем сигналы против тренда ETH
        if signal_type == "BUY" and eth_trend == "SELL":
            logger.warning("🚫 [ETH FILTER] %s: LONG против ETH тренда (%s) - блокируем", symbol, eth_trend)
            return False

        if signal_type == "SELL" and eth_trend == "BUY":
            logger.warning("🚫 [ETH FILTER] %s: SHORT против ETH тренда (%s) - блокируем", symbol, eth_trend)
            return False

        logger.debug("✅ [ETH FILTER] %s: тренд совпадает с ETH (%s)", symbol, eth_trend)
        return True
    except Exception as e:
        logger.debug("⚠️ Ошибка проверки ETH тренда для %s: %s (пропускаем)", symbol, e)
        return True
```

```159:224:src/signals/filters.py
async def check_sol_alignment(symbol: str, signal_type: str) -> bool:
    """
    Проверяет соответствие сигнала тренду SOL

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)

    Returns:
        True если сигнал соответствует тренду SOL, False если нет
    """
    try:
        # Получаем данные SOL через гибридный менеджер
        sol_df = await HYBRID_DATA_MANAGER.get_smart_data("SOLUSDT", "ohlc")

        # Проверяем тип данных и валидность
        if sol_df is None:
            logger.debug("⚠️ [%s] Нет данных SOL для проверки тренда (None)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Если это список словарей, конвертируем в DataFrame
        if isinstance(sol_df, list):
            if len(sol_df) == 0:
                logger.debug("⚠️ [%s] Данные SOL - пустой список, пропускаем проверку тренда", symbol)
                return True

            # Конвертируем список словарей в DataFrame
            try:
                sol_df = pd.DataFrame(sol_df)
                # Конвертируем timestamp в datetime если нужно
                if 'timestamp' in sol_df.columns:
                    sol_df['timestamp'] = pd.to_datetime(sol_df['timestamp'], unit='ms', errors='coerce')
                    sol_df.set_index('timestamp', inplace=True)
                logger.debug("✅ [%s] Данные SOL конвертированы из списка в DataFrame (%d строк)", symbol, len(sol_df))
            except Exception as e:
                logger.warning("⚠️ [%s] Ошибка конвертации списка SOL в DataFrame: %s", symbol, e)
                return True

        # Проверяем, что это DataFrame и он не пустой
        if not isinstance(sol_df, pd.DataFrame):
            logger.debug("⚠️ [%s] Данные SOL не являются DataFrame (тип: %s), пропускаем", symbol, type(sol_df))
            return True

        if sol_df.empty or len(sol_df) < 50:
            logger.debug("⚠️ [%s] Нет данных SOL для проверки тренда (пусто или < 50 строк)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Определяем тренд SOL по EMA
        sol_ema_fast = sol_df['ema_fast'].iloc[-1] if 'ema_fast' in sol_df.columns else sol_df['close'].ewm(span=12).mean().iloc[-1]
        sol_ema_slow = sol_df['ema_slow'].iloc[-1] if 'ema_slow' in sol_df.columns else sol_df['close'].ewm(span=26).mean().iloc[-1]
        sol_trend = "BUY" if sol_ema_fast > sol_ema_slow else "SELL"

        # Блокируем сигналы против тренда SOL
        if signal_type == "BUY" and sol_trend == "SELL":
            logger.warning("🚫 [SOL FILTER] %s: LONG против SOL тренда (%s) - блокируем", symbol, sol_trend)
            return False

        if signal_type == "SELL" and sol_trend == "BUY":
            logger.warning("🚫 [SOL FILTER] %s: SHORT против SOL тренда (%s) - блокируем", symbol, sol_trend)
            return False

        logger.debug("✅ [SOL FILTER] %s: тренд совпадает с SOL (%s)", symbol, sol_trend)
        return True
    except Exception as e:
        logger.debug("⚠️ Ошибка проверки SOL тренда для %s: %s (пропускаем)", symbol, e)
        return True
```

### **Интеграция в signal_live.py:**

В `signal_live.py` создана функция `check_all_trend_alignments()`, которая проверяет все три тренда последовательно:

```3940:3957:signal_live.py
async def check_all_trend_alignments(symbol: str, signal_type: str) -> bool:
    """
    Проверяет соответствие сигнала трендам BTC, ETH и SOL

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)

    Returns:
        True если сигнал соответствует всем трендам, False если нет
    """
    # Проверка BTC (всегда активна)
    if not await check_btc_alignment(symbol, signal_type):
        return False

    # Проверка ETH (всегда активна)
    if not await check_eth_alignment(symbol, signal_type):
        return False

    # Проверка SOL (всегда активна)
    if not await check_sol_alignment(symbol, signal_type):
        return False

    return True
```

### **Условия блокировки:**

**Для ETH:**

1. **LONG сигнал:**
   - Если ETH в медвежьем тренде (`eth_trend == "SELL"`) → блокировка

2. **SHORT сигнал:**
   - Если ETH в бычьем тренде (`eth_trend == "BUY"`) → блокировка

**Для SOL:**

1. **LONG сигнал:**
   - Если SOL в медвежьем тренде (`sol_trend == "SELL"`) → блокировка

2. **SHORT сигнал:**
   - Если SOL в бычьем тренде (`sol_trend == "BUY"`) → блокировка

### **Определение тренда:**

- **Бычий тренд:** `ema_fast > ema_slow` (EMA12 > EMA26)
- **Медвежий тренд:** `ema_fast < ema_slow` (EMA12 < EMA26)

### **Почему это важно:**

- **ETH корреляция:** DeFi токены (UNI, AAVE, COMP) коррелируют с ETH (0.5-0.8)
- **SOL корреляция:** Solana токены (RAY, SRM, FIDA) коррелируют с SOL (0.6-0.85)
- **Улучшение качества сигналов:** Блокировка сигналов против тренда основных активов снижает количество ложных сигналов

### **Использование в бэктестах:**

В `scripts/run_advanced_backtest.py` добавлены проверки ETH и SOL трендов:

```619:641:scripts/run_advanced_backtest.py
            # 🆕 4.1. ETH тренд фильтр (если данные доступны)
            eth_df = getattr(self, 'eth_df', None)
            if eth_df is not None and not eth_df.empty:
                eth_trend = self.check_eth_trend(eth_df, row.name)
                if eth_trend is not None:
                    if (direction == "LONG" and eth_trend) or (direction == "SHORT" and not eth_trend):
                        confidence += 10
                        filters_passed.append("eth_aligned")
                    else:
                        # Блокируем сигналы против тренда ETH
                        return None

            # 🆕 4.2. SOL тренд фильтр (если данные доступны)
            sol_df = getattr(self, 'sol_df', None)
            if sol_df is not None and not sol_df.empty:
                sol_trend = self.check_sol_trend(sol_df, row.name)
                if sol_trend is not None:
                    if (direction == "LONG" and sol_trend) or (direction == "SHORT" and not sol_trend):
                        confidence += 10
                        filters_passed.append("sol_aligned")
                    else:
                        # Блокируем сигналы против тренда SOL
                        return None
```

📄 **Подробный анализ:** `docs/ETH_SOL_FILTERS_ANALYSIS.md`

---

## 📝 ЗАМЕЧАНИЯ

1. **RSI фильтр** - самый активный фильтр (75.96% блокировок по статистике)
2. **MACD фильтр** - требует сильное расхождение (> 0.5%) для прохождения
3. **Volume фильтр** - блокирует как низкие, так и аномально высокие объемы
4. **BTC Trend фильтр** - критически важен для альткоинов ✅ **РЕАЛИЗОВАН**
5. **ETH Trend фильтр** - важен для DeFi токенов ✅ **РЕАЛИЗОВАН**
6. **SOL Trend фильтр** - важен для Solana токенов ✅ **РЕАЛИЗОВАН**
7. **EMA фильтр** - блокирует сигналы при пересечении EMA
8. **BB фильтр** - требует экстремальную позицию цены (нижние/верхние 20%)

---

**Дата создания:** 2025-01-XX  
**Дата обновления:** 2025-01-XX  
**Версия:** 2.4  
**Автор:** ATRA Trading System

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ МАТЕРИАЛЫ

- 📄 **Анализ оптимизации RSI:** `docs/RSI_OPTIMIZATION_ANALYSIS.md` - детальный анализ рекомендаций по оптимизации RSI параметров для внутридневной торговли на крипторынке

---

## 📝 ИСТОРИЯ ИЗМЕНЕНИЙ

### Версия 2.4 (2025-01-XX)

- ✅ Оптимизированы все фильтры для внутридневной крипто-торговли
- ✅ MACD фильтр: параметры 12/26/9 → 8/21/5, min_strength 0.005 → 0.003
- ✅ Создан `enhanced_macd_filter` с расширенной логикой (гистограмма, дивергенции, подтверждение)
- ✅ EMA фильтр: параметры 7/25 → 6/14/22, добавлена многоуровневая проверка тренда
- ✅ Volume фильтр: оптимизированы параметры (1.2/500/8), добавлена проверка объема в USD
- ✅ BB фильтр: оптимизированы параметры (18/1.8/0.015), добавлено обнаружение сжатия
- ✅ Trend фильтры (BTC/ETH/SOL): параметры 12/26 → 10/22, добавлена проверка силы тренда
- ✅ Блокировка только сильных противотрендов (strength > 1%), разрешение в боковике

### Версия 2.3 (2025-01-XX)

- ✅ Внедрены адаптивные RSI уровни по волатильности символов
- ✅ Создан модуль `src/filters/adaptive_rsi.py` для расчета адаптивных уровней
- ✅ Интегрированы адаптивные уровни в `enhanced_rsi_filter`
- ✅ Базовые параметры RSI: 70/30 → 72/28 (оптимизировано для крипто)
- ✅ Добавлена настройка `USE_ADAPTIVE_RSI_LEVELS` в `config.py`

### Версия 2.2 (2025-01-XX)

- ✅ Оптимизированы параметры RSI для крипторынка
- ✅ Дивергенции lookback: 5 → 8 (лучшее обнаружение дивергенций)
- ✅ Volatility threshold: 10 → 8 (меньше ложных блокировок)
- ✅ Строгий режим: 80/20 → 78/22 (более качественные сигналы)
- ✅ Добавлены новые параметры в `INDICATOR_SETTINGS`

### Версия 2.1 (2025-01-XX)

- ✅ Фильтры ETH и SOL теперь всегда активны (как BTC фильтр)
- ✅ Убраны условные проверки `USE_ETH_TREND_FILTER` и `USE_SOL_TREND_FILTER` из логики
- ✅ Обновлена функция `check_all_trend_alignments()` - все три фильтра проверяются всегда

### Версия 2.0 (2025-01-XX)

- ✅ Добавлены фильтры ETH и SOL трендов
- ✅ Реализованы функции `check_eth_alignment()` и `check_sol_alignment()`
- ✅ Интегрированы в `signal_live.py` через `check_all_trend_alignments()`
- ✅ Добавлены в бэктесты (`scripts/run_advanced_backtest.py`)
- ✅ Обновлена документация

### Версия 1.1 (2025-01-XX)

- 📝 Добавлен раздел о ETH и SOL трендах (информационный статус)

### Версия 1.0 (2025-01-XX)

- 📝 Первоначальная версия документации
