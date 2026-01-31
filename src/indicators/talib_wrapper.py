#!/usr/bin/env python3
"""
Универсальный wrapper для talib с автоматическим fallback
Поддерживает все основные функции talib с fallback на pandas/ta
"""

import sys
import os
import site
import warnings
import numpy as np

# Подавляем предупреждения talib
warnings.filterwarnings("ignore", category=UserWarning, module="talib")

def get_talib():
    """Получает talib модуль с автоматическим fallback"""
    
    # Сначала пробуем стандартный импорт
    try:
        import talib
        print("✅ talib успешно загружен")
        return talib
    except ImportError:
        pass

    # Если не получилось, ищем talib в различных местах
    possible_paths = [
        # Стандартные пути Python
        "/usr/local/lib/python3.9/site-packages",
        "/usr/local/lib/python3.10/site-packages", 
        "/usr/local/lib/python3.11/site-packages",
        "/usr/local/lib/python3.12/site-packages",
        "/usr/lib/python3.9/site-packages",
        "/usr/lib/python3.10/site-packages",
        "/usr/lib/python3.11/site-packages",
        "/usr/lib/python3.12/site-packages",
        # Пользовательские пути
        os.path.expanduser("~/.local/lib/python3.9/site-packages"),
        os.path.expanduser("~/.local/lib/python3.10/site-packages"),
        os.path.expanduser("~/.local/lib/python3.11/site-packages"),
        os.path.expanduser("~/.local/lib/python3.12/site-packages"),
        # Виртуальные окружения
        os.path.join(os.getcwd(), "venv", "lib", "python3.9", "site-packages"),
        os.path.join(os.getcwd(), "venv", "lib", "python3.10", "site-packages"),
        os.path.join(os.getcwd(), "venv", "lib", "python3.11", "site-packages"),
        os.path.join(os.getcwd(), "venv", "lib", "python3.12", "site-packages"),
        # macOS пути
        "/opt/homebrew/lib/python3.9/site-packages",
        "/opt/homebrew/lib/python3.10/site-packages",
        "/opt/homebrew/lib/python3.11/site-packages",
        "/opt/homebrew/lib/python3.12/site-packages",
        "/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/site-packages",
        "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages",
        "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages",
        "/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/site-packages",
        # macOS Homebrew paths
        "/opt/homebrew/lib/python3.9/site-packages",
        "/opt/homebrew/lib/python3.10/site-packages",
        "/opt/homebrew/lib/python3.11/site-packages",
        "/opt/homebrew/lib/python3.12/site-packages",
        # macOS system paths
        "/usr/local/lib/python3.9/site-packages",
        "/usr/local/lib/python3.10/site-packages",
        "/usr/local/lib/python3.11/site-packages",
        "/usr/local/lib/python3.12/site-packages",
        # User library paths
        os.path.expanduser("~/Library/Python/3.9/lib/python/site-packages"),
        os.path.expanduser("~/Library/Python/3.10/lib/python/site-packages"),
        os.path.expanduser("~/Library/Python/3.11/lib/python/site-packages"),
        os.path.expanduser("~/Library/Python/3.12/lib/python/site-packages"),
        # Framework paths
        "/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/site-packages",
        "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages",
        "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages",
        "/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/site-packages",
        # CommandLineTools paths
        "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/site-packages",
        "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.10/lib/python3.10/site-packages",
        "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.11/lib/python3.11/site-packages",
        "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.12/lib/python3.12/site-packages",
        # System paths
        "/usr/lib/python3.9/site-packages",
        "/usr/lib/python3.10/site-packages",
        "/usr/lib/python3.11/site-packages",
        "/usr/lib/python3.12/site-packages",
    ]

    # Добавляем пути к sys.path
    for path in possible_paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)

    # Пробуем импортировать talib после добавления путей
    try:
        import talib
        print("✅ talib найден в дополнительных путях")
        return talib
    except ImportError:
        pass

    # Последняя попытка - ищем через site-packages
    try:
        for site_dir in site.getsitepackages():
            talib_path = os.path.join(site_dir, "talib")
            if os.path.exists(talib_path):
                sys.path.insert(0, site_dir)
                try:
                    import talib
                    print(f"✅ talib найден в {site_dir}")
                    return talib
                except ImportError:
                    continue
    except (OSError, ImportError, RuntimeError):
        pass

    # Если talib не найден, используем fallback
    print("⚠️ talib не найден, используется fallback режим")
    return None

# Глобальная переменная для talib
_talib = get_talib()

# Создаем fallback функции если talib недоступен
if _talib is None:
    print("🔧 Создание fallback функций для talib...")
    
    # Создаем заглушки для основных функций talib
    class TalibFallback:
        """Fallback класс для talib функций"""
        
        @staticmethod
        def SMA(data, timeperiod=30):
            """Простая скользящая средняя"""
            import pandas as pd
            return pd.Series(data).rolling(window=timeperiod).mean().values
        
        @staticmethod
        def EMA(data, timeperiod=30):
            """Экспоненциальная скользящая средняя"""
            import pandas as pd
            return pd.Series(data).ewm(span=timeperiod).mean().values
        
        @staticmethod
        def RSI(data, timeperiod=14):
            """RSI индикатор"""
            import pandas as pd
            delta = pd.Series(data).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=timeperiod).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=timeperiod).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.values
        
        @staticmethod
        def BBANDS(data, timeperiod=20, nbdevup=2, nbdevdn=2):
            """Полосы Боллинджера"""
            import pandas as pd
            series = pd.Series(data)
            middle = series.rolling(window=timeperiod).mean()
            std = series.rolling(window=timeperiod).std()
            upper = middle + (std * nbdevup)
            lower = middle - (std * nbdevdn)
            return upper.values, middle.values, lower.values
        
        @staticmethod
        def ATR(high, low, close, timeperiod=14):
            """Average True Range"""
            import pandas as pd
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)
            
            tr1 = high_series - low_series
            tr2 = abs(high_series - close_series.shift(1))
            tr3 = abs(low_series - close_series.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=timeperiod).mean()
            return atr.values
        
        @staticmethod
        def MACD(data, fastperiod=12, slowperiod=26, signalperiod=9):
            """MACD индикатор"""
            import pandas as pd
            series = pd.Series(data)
            ema_fast = series.ewm(span=fastperiod).mean()
            ema_slow = series.ewm(span=slowperiod).mean()
            macd = ema_fast - ema_slow
            signal = macd.ewm(span=signalperiod).mean()
            histogram = macd - signal
            return macd.values, signal.values, histogram.values
        
        @staticmethod
        def STOCH(high, low, close, fastk_period=5, slowk_period=3, slowd_period=3):
            """Stochastic индикатор"""
            import pandas as pd
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)
            
            lowest_low = low_series.rolling(window=fastk_period).min()
            highest_high = high_series.rolling(window=fastk_period).max()
            
            k_percent = 100 * (close_series - lowest_low) / (highest_high - lowest_low)
            k_percent = k_percent.rolling(window=slowk_period).mean()
            d_percent = k_percent.rolling(window=slowd_period).mean()
            
            return k_percent.values, d_percent.values
        
        @staticmethod
        def ADX(high, low, close, timeperiod=14):
            """ADX индикатор"""
            import pandas as pd
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)
            
            # True Range
            tr1 = high_series - low_series
            tr2 = abs(high_series - close_series.shift(1))
            tr3 = abs(low_series - close_series.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Directional Movement
            dm_plus = high_series.diff()
            dm_minus = -low_series.diff()
            
            dm_plus = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0)
            dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0)
            
            # Smoothed values
            atr_smooth = tr.rolling(window=timeperiod).mean()
            dm_plus_smooth = dm_plus.rolling(window=timeperiod).mean()
            dm_minus_smooth = dm_minus.rolling(window=timeperiod).mean()
            
            # DI+ and DI-
            di_plus = 100 * dm_plus_smooth / atr_smooth
            di_minus = 100 * dm_minus_smooth / atr_smooth
            
            # ADX
            dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
            adx = dx.rolling(window=timeperiod).mean()
            
            return adx.values, di_plus.values, di_minus.values
        
        @staticmethod
        def CCI(high, low, close, timeperiod=14):
            """Commodity Channel Index"""
            import pandas as pd
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)
            
            typical_price = (high_series + low_series + close_series) / 3
            sma_tp = typical_price.rolling(window=timeperiod).mean()
            mean_dev = typical_price.rolling(window=timeperiod).apply(
                lambda x: np.mean(np.abs(x - x.mean()))
            )
            cci = (typical_price - sma_tp) / (0.015 * mean_dev)
            
            return cci.values
        
        @staticmethod
        def WILLR(high, low, close, timeperiod=14):
            """Williams %R"""
            import pandas as pd
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)
            
            highest_high = high_series.rolling(window=timeperiod).max()
            lowest_low = low_series.rolling(window=timeperiod).min()
            
            willr = -100 * (highest_high - close_series) / (highest_high - lowest_low)
            
            return willr.values
        
        @staticmethod
        def MOM(data, timeperiod=10):
            """Momentum"""
            import pandas as pd
            return pd.Series(data).diff(timeperiod).values
        
        @staticmethod
        def ROC(data, timeperiod=10):
            """Rate of Change"""
            import pandas as pd
            series = pd.Series(data)
            return (series / series.shift(timeperiod) - 1) * 100
    
    # Заменяем talib на fallback
    _talib = TalibFallback()
    print("✅ Fallback режим активирован")

# Экспортируем talib или fallback
if _talib is not None:
    # Экспортируем все функции talib
    globals().update(_talib.__dict__)
