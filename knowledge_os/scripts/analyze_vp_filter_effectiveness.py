"""
Анализ эффективности Volume Profile фильтра
Проверяет, почему фильтр не влияет на результаты
"""
import os
import sys
import pandas as pd
from pathlib import Path

# Настройка окружения
os.environ['USE_VP_FILTER'] = 'True'
os.environ['DISABLE_EXTRA_FILTERS'] = 'true'
os.environ['volume_profile_threshold'] = '0.6'

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest_5coins_intelligent import load_yearly_data
from src.signals.core import soft_entry_signal
from src.signals.filters_volume_vwap import check_volume_profile_filter

# Счетчики
total_signals = 0
signals_passed_vp = 0
signals_rejected_vp = 0
rejection_reasons = {}

def analyze_symbol(symbol: str, period_days: int = 7):
    """Анализирует один символ"""
    global total_signals, signals_passed_vp, signals_rejected_vp
    
    print(f"\n{'='*80}")
    print(f"📊 АНАЛИЗ: {symbol}")
    print(f"{'='*80}")
    
    df = load_yearly_data(symbol, limit_days=period_days)
    if df is None or len(df) < 100:
        print(f"❌ Недостаточно данных")
        return
    
    from src.signals.indicators import add_technical_indicators
    df = add_technical_indicators(df)
    
    start_idx = 100
    vp_rejections = []
    
    for i in range(start_idx, len(df)):
        # Проверяем, есть ли базовый сигнал
        signal, price = soft_entry_signal(df, i)
        
        if signal:
            total_signals += 1
            side = signal.lower()
            
            # Проверяем Volume Profile фильтр
            vp_ok, vp_reason = check_volume_profile_filter(df, i, side, strict_mode=False)
            
            if vp_ok:
                signals_passed_vp += 1
            else:
                signals_rejected_vp += 1
                vp_rejections.append({
                    'candle': i,
                    'price': df['close'].iloc[i],
                    'side': side,
                    'reason': vp_reason
                })
                if vp_reason:
                    reason_key = vp_reason.split(':')[0] if ':' in vp_reason else vp_reason
                    rejection_reasons[reason_key] = rejection_reasons.get(reason_key, 0) + 1
    
    print(f"   📈 Всего сигналов: {total_signals}")
    print(f"   ✅ Прошли VP фильтр: {signals_passed_vp}")
    print(f"   ❌ Отклонены VP фильтром: {signals_rejected_vp}")
    print(f"   📊 Процент отклонений: {signals_rejected_vp / total_signals * 100:.1f}%" if total_signals > 0 else "   📊 Процент отклонений: 0%")
    
    if vp_rejections:
        print(f"\n   🔍 Примеры отклонений:")
        for r in vp_rejections[:5]:
            print(f"      Свеча {r['candle']}: {r['side']} @ {r['price']:.2f} - {r['reason']}")

if __name__ == "__main__":
    print("="*80)
    print("🔍 АНАЛИЗ ЭФФЕКТИВНОСТИ VOLUME PROFILE ФИЛЬТРА")
    print("="*80)
    print(f"📅 Период: 7 дней")
    print(f"🎯 Параметр: volume_profile_threshold = 0.6")
    print("="*80)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
    
    for symbol in symbols:
        analyze_symbol(symbol, period_days=7)
    
    print(f"\n{'='*80}")
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*80}")
    print(f"📈 Всего сигналов: {total_signals}")
    print(f"✅ Прошли VP фильтр: {signals_passed_vp} ({signals_passed_vp / total_signals * 100:.1f}%)" if total_signals > 0 else "✅ Прошли VP фильтр: 0")
    print(f"❌ Отклонены VP фильтром: {signals_rejected_vp} ({signals_rejected_vp / total_signals * 100:.1f}%)" if total_signals > 0 else "❌ Отклонены VP фильтром: 0")
    
    if rejection_reasons:
        print(f"\n📋 Причины отклонений:")
        for reason, count in sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"   {reason}: {count}")
    
    print(f"\n{'='*80}")
    if signals_rejected_vp == 0:
        print("⚠️ ВЫВОД: Фильтр НЕ ОТКЛОНЯЕТ сигналы!")
        print("   Возможные причины:")
        print("   1. Все сигналы проходят фильтр (слишком мягкие условия)")
        print("   2. Фильтр не вызывается (проблема в коде)")
        print("   3. Фильтр возвращает True по умолчанию (ошибка в логике)")
    else:
        print(f"✅ Фильтр работает: отклонено {signals_rejected_vp} сигналов")
    print(f"{'='*80}")

