#!/usr/bin/env python3
"""
Проверка старых монет (топ 1-100) на необходимость переоптимизации
"""

import re
from pathlib import Path
from typing import Any, Dict, List


def extract_coin_info(content: str, symbol: str) -> Dict[str, Any]:
    """Извлекает информацию о монете из кода"""
    pattern = rf"'{symbol}':\s*\{{([^}}]+)\}}"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return None

    block = match.group(1)

    # Извлекаем параметры
    params = {}
    param_patterns = {
        "volume_ratio": r"'volume_ratio':\s*([0-9.]+)",
        "quality_score": r"'quality_score':\s*([0-9.]+)",
        "rsi_oversold": r"'rsi_oversold':\s*([0-9]+)",
        "rsi_overbought": r"'rsi_overbought':\s*([0-9]+)",
        "trend_strength": r"'trend_strength':\s*([0-9.]+)",
        "momentum_threshold": r"'momentum_threshold':\s*([-0-9.]+)",
    }

    for key, pattern in param_patterns.items():
        m = re.search(pattern, block)
        if m:
            params[key] = float(m.group(1))

    # Извлекаем комментарии с результатами
    comment_pattern = r"# Результаты.*?return=([+-]?[0-9.]+)%.*?Sharpe=([+-]?[0-9.]+)"
    comment_match = re.search(comment_pattern, block)

    result_info = {}
    if comment_match:
        result_info["return_pct"] = float(comment_match.group(1))
        result_info["sharpe"] = float(comment_match.group(2))
        result_info["has_backtest_results"] = True
    else:
        result_info["has_backtest_results"] = False

    return {"symbol": symbol, "params": params, "result_info": result_info}


def check_coin_needs_reoptimization(coin_info: Dict[str, Any]) -> bool:
    """Проверяет, нуждается ли монета в переоптимизации"""
    if not coin_info:
        return True  # Если монета не найдена, нужно проверить

    result_info = coin_info.get("result_info", {})

    # Если нет результатов бэктеста - нужно переоптимизировать
    if not result_info.get("has_backtest_results", False):
        return True

    sharpe = result_info.get("sharpe", 0)
    return_pct = result_info.get("return_pct", 0)

    # Критерии для переоптимизации
    if sharpe < 0:  # Отрицательный Sharpe
        return True

    if return_pct < 20:  # Низкая доходность (<20%)
        return True

    if sharpe < 0.1 and return_pct < 50:  # Низкий Sharpe и низкая доходность
        return True

    return False


def main():
    target_file = Path("src/ai/intelligent_filter_system.py")
    content = target_file.read_text(encoding="utf-8")

    # Список монет для проверки
    # Топ 1-50
    top_50_coins = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "TRXUSDT",
        "DOTUSDT",
        "MATICUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "UNIUSDT",
        "LTCUSDT",
        "ATOMUSDT",
        "ETCUSDT",
        "XLMUSDT",
        "BCHUSDT",
        "ALGOUSDT",
        "VETUSDT",
        "ICPUSDT",
        "FILUSDT",
        "THETAUSDT",
        "EOSUSDT",
        "AAVEUSDT",
        "CAKEUSDT",
        "AXSUSDT",
        "MKRUSDT",
        "SANDUSDT",
        "NEARUSDT",
        "GRTUSDT",
        "CHZUSDT",
        "MANAUSDT",
        "ENJUSDT",
        "HBARUSDT",
        "XTZUSDT",
        "FLOWUSDT",
        "ZILUSDT",
        "IOTAUSDT",
        "SUSHIUSDT",
        "APTUSDT",
        "OPUSDT",
        "ARBUSDT",
        "INJUSDT",
        "STXUSDT",
        "TIAUSDT",
        "SEIUSDT",
        "SUIUSDT",
        "RUNEUSDT",
        "FETUSDT",
    ]

    # Топ 51-100 (уже добавленные ранее)
    top_51_100_coins = [
        "AAVEUSDT",
        "MKRUSDT",
        "ONTUSDT",
        "ZILUSDT",
        "RUNEUSDT",
        "WOOUSDT",
        "IDUSDT",
        "ARKMUSDT",
        "FETUSDT",
        "AIUSDT",
        "PHBUSDT",
        "XAIUSDT",
        "NMRUSDT",
        "ARDRUSDT",
        "ARKUSDT",
        "API3USDT",
        "BANDUSDT",
        "CTSIUSDT",
        "DATAUSDT",
        "DCRUSDT",
        "DGBUSDT",
        "PORTALUSDT",
        "PENDLEUSDT",
        "PIXELUSDT",
        "LUNAUSDT",
        "USTCUSDT",
        "CAKEUSDT",
        "JTOUSDT",
        "PYTHUSDT",
        "WIFUSDT",
        "BONKUSDT",
        "FLOKIUSDT",
        "BOMEUSDT",
        "SHIBUSDT",
        "JUPUSDT",
        "WLDUSDT",
        "1INCHUSDT",
        "ENSUSDT",
        "LDOUSDT",
        "CRVUSDT",
        "TWTUSDT",
        "LUNCUSDT",
    ]

    print("=" * 80)
    print("🔍 ПРОВЕРКА СТАРЫХ МОНЕТ НА ПЕРЕОПТИМИЗАЦИЮ")
    print("=" * 80)
    print()

    all_coins = list(set(top_50_coins + top_51_100_coins))

    needs_reopt = []
    ok_coins = []
    not_found = []

    for symbol in sorted(all_coins):
        coin_info = extract_coin_info(content, symbol)
        if not coin_info:
            not_found.append(symbol)
            continue

        if check_coin_needs_reoptimization(coin_info):
            needs_reopt.append((symbol, coin_info))
        else:
            ok_coins.append((symbol, coin_info))

    print(f"📊 Всего проверено монет: {len(all_coins)}")
    print(f"✅ В порядке: {len(ok_coins)}")
    print(f"⚠️  Требуют переоптимизации: {len(needs_reopt)}")
    print(f"❌ Не найдены: {len(not_found)}")
    print()

    if needs_reopt:
        print("⚠️  МОНЕТЫ, ТРЕБУЮЩИЕ ПЕРЕОПТИМИЗАЦИИ:")
        print("=" * 80)
        for symbol, info in needs_reopt:
            result = info.get("result_info", {})
            sharpe = result.get("sharpe", "N/A")
            return_pct = result.get("return_pct", "N/A")
            has_results = result.get("has_backtest_results", False)

            reason = []
            if not has_results:
                reason.append("нет результатов")
            elif sharpe != "N/A" and sharpe < 0:
                reason.append(f"Sharpe={sharpe:.3f} < 0")
            elif return_pct != "N/A" and return_pct < 20:
                reason.append(f"Return={return_pct:.1f}% < 20%")

            print(f"  {symbol:12s} | {', '.join(reason) if reason else 'требует проверки'}")
        print("=" * 80)
        print()

    if not_found:
        print(f"❌ Монеты не найдены в файле ({len(not_found)}):")
        print(f"   {', '.join(not_found[:10])}")
        if len(not_found) > 10:
            print(f"   ... и еще {len(not_found) - 10}")
        print()


if __name__ == "__main__":
    main()
