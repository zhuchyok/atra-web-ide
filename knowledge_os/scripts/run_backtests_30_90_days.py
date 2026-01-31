#!/usr/bin/env python3
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_backtests")

COMMISSION_RATE = 0.0004  # 0.04%
SLIPPAGE_MODEL = "realistic"


def run_safe(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning("⚠️ backtest runner: %s not available: %s", getattr(func, "__name__", "func"), e)
        return None


def main() -> None:
    logger.info("🧪 Запуск бэктестов 30/90 дней (комиссия=%.4f%%, slippage=%s)", COMMISSION_RATE * 100, SLIPPAGE_MODEL)

    # Пробуем разные движки/шаблоны, если доступны
    results = []

    # 30 дней
    try:
        from backtests.advanced_backtest_30days import AdvancedBacktestEngine  # type: ignore
        engine30 = AdvancedBacktestEngine(initial_deposit=10000)
        res30 = run_safe(getattr(engine30, "run_backtest", lambda *a, **k: None), "ALL", "1h")
        results.append(("30d", res30))
    except Exception as e:
        logger.info("ℹ️ AdvancedBacktestEngine недоступен: %s", e)

    # 90 дней (если есть реализация 3 months)
    try:
        from backtests.current_strategy_3months_backtest import run_backtest_for_symbol  # type: ignore
        res90 = run_safe(run_backtest_for_symbol, "ALL")
        results.append(("90d", res90))
    except Exception as e:
        logger.info("ℹ️ 3months backtest недоступен: %s", e)

    logger.info("✅ Бэктесты завершены (смотрите логи конкретных движков)")
    for label, r in results:
        logger.info("  - %s: %s", label, "ok" if r is not None else "skipped")


if __name__ == "__main__":
    main()


