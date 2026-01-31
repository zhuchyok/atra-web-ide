import pandas as pd
from typing import Optional, Tuple, Dict
import ta

# Reuse existing async OHLC fetcher
try:
    from src.utils.ohlc_utils import get_ohlc_binance_sync_async
except ImportError:
    try:
        from ohlc_utils import get_ohlc_binance_sync_async
    except ImportError:
        async def get_ohlc_binance_sync_async(*args, **kwargs): return None


async def _fetch_tf_last_row(symbol: str, interval: str, min_len: int = 40) -> Optional[pd.Series]:
    """Fetches last row of OHLC for given timeframe and computes minimal indicators.

    Returns:
        pd.Series with at least: close, ema7, ema25, rsi; or None if not enough data
    """
    ohlc = await get_ohlc_binance_sync_async(symbol, interval=interval, limit=max(min_len, 60))
    if not ohlc or len(ohlc) < min_len:
        return None
    df = pd.DataFrame(ohlc)
    df["open_time"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("open_time")
    
    # Использование централизованного модуля индикаторов
    from src.signals.indicators import add_technical_indicators
    df = add_technical_indicators(df)
    
    return df.iloc[-1]


def _mtf_ok_for_side(row: Optional[pd.Series], side_dir: str) -> bool:
    """Evaluates simple MTF rule for given side using last-row indicators.

    If row is None, returns True (do not block when data is missing).
    LONG: ema7 > ema25 and rsi < 60
    SHORT: ema7 < ema25 and rsi > 40
    """
    if row is None:
        return True
    try:
        ema7 = float(row["ema7"]) if row.get("ema7") is not None else None
        ema25 = float(row["ema25"]) if row.get("ema25") is not None else None
        rsi = float(row["rsi"]) if row.get("rsi") is not None else None
    except Exception:
        return True
    if ema7 is None or ema25 is None or rsi is None:
        return True
    if str(side_dir).upper() == "LONG":
        return (ema7 > ema25) and (rsi < 60)
    else:
        return (ema7 < ema25) and (rsi > 40)


def build_mtf_accumulation_line(symbol: str, *args, **kwargs) -> str:
    """
    Строит линию накопления MTF (Multi-Timeframe) на основе анализа нескольких таймфреймов
    """
    try:
        # Простая реализация MTF анализа
        # В реальной системе здесь был бы более сложный анализ
        
        # Получаем данные для разных таймфреймов
        import asyncio
        
        async def _get_mtf_data():
            try:
                # Получаем данные для 1h и 4h таймфреймов
                ohlc_1h = await get_ohlc_binance_sync_async(symbol, "1h", limit=50)
                ohlc_4h = await get_ohlc_binance_sync_async(symbol, "4h", limit=50)
                
                if not ohlc_1h or not ohlc_4h:
                    return "📊 MTF: Данные недоступны"
                
                # Простой анализ тренда
                df_1h = pd.DataFrame(ohlc_1h)
                df_4h = pd.DataFrame(ohlc_4h)
                
                # Рассчитываем индикаторы через централизованный модуль
                from src.signals.indicators import add_technical_indicators
                df_1h = add_technical_indicators(df_1h)
                df_4h = add_technical_indicators(df_4h)
                
                # Анализ тренда
                trend_1h = "BULLISH" if df_1h["ema7"].iloc[-1] > df_1h["ema25"].iloc[-1] else "BEARISH"
                trend_4h = "BULLISH" if df_4h["ema7"].iloc[-1] > df_4h["ema25"].iloc[-1] else "BEARISH"
                
                # Определяем общий тренд
                if trend_1h == "BULLISH" and trend_4h == "BULLISH":
                    return "📈 MTF: Сильный бычий тренд"
                elif trend_1h == "BEARISH" and trend_4h == "BEARISH":
                    return "📉 MTF: Сильный медвежий тренд"
                elif trend_1h == "BULLISH" and trend_4h == "BEARISH":
                    return "🔄 MTF: Коррекция вверх"
                elif trend_1h == "BEARISH" and trend_4h == "BULLISH":
                    return "🔄 MTF: Коррекция вниз"
                else:
                    return "📊 MTF: Нейтральный тренд"
                    
            except Exception as e:
                return f"📊 MTF: Ошибка расчета ({str(e)[:50]})"
        
        # Запускаем асинхронную функцию
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если loop уже запущен, создаем задачу
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _get_mtf_data())
                    return future.result()
            else:
                return loop.run_until_complete(_get_mtf_data())
        except Exception:
            return "📊 MTF: Данные недоступны"
            
    except Exception as e:
        return f"📊 MTF: Ошибка ({str(e)[:50]})"
