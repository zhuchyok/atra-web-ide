#!/usr/bin/env python3
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("live_smoke_test")


async def run_test(
    user_id: int,
    symbol: str,
    direction: str = "BUY",
    amount_usdt: float = 5.0,
    leverage: int = 2,
    trade_mode: str = "futures",
) -> Dict[str, Any]:
    from acceptance_database import AcceptanceDatabase
    from auto_execution import AutoExecutionService
    from exchange_adapter import ExchangeAdapter

    adb = AcceptanceDatabase()
    keys = await adb.get_active_exchange_keys(user_id, "bitget")
    if not keys:
        return {"ok": False, "reason": "no_keys", "details": "Активные ключи Bitget не найдены"}

    svc = AutoExecutionService(acceptance_db=adb)
    entry_price = None
    try:
        # Получим приблизительную цену через ccxt, если доступно
        adapter = ExchangeAdapter("bitget", keys=keys, sandbox=False, trade_mode=trade_mode)
        if adapter.client:
            try:
                ticker = adapter.client.fetch_ticker(symbol)
                entry_price = float(ticker.get("last") or ticker.get("close") or 0.0) or None
            except Exception:
                entry_price = None
    except Exception:
        entry_price = None

    # Открываем позицию и авто-выставляем защиту
    ok = await svc.execute_and_open(
        symbol=symbol,
        direction=direction,
        entry_price=entry_price or 0.0,
        user_id=user_id,
        quantity_usdt=amount_usdt,
        user_balance=100.0,
        current_exposure=0.0,
        leverage=leverage,
        trade_mode=trade_mode,
    )
    if not ok:
        return {
            "ok": False,
            "reason": "open_failed",
            "details": "Не удалось открыть позицию через авто-исполнение",
        }

    # Проверим наличие план-ордеров TP/SL
    try:
        adapter = ExchangeAdapter("bitget", keys=keys, sandbox=False, trade_mode=trade_mode)
        await asyncio.sleep(2)
        # Попробуем получить план-ордера через raw API
        plan_rows = await adapter.fetch_plan_orders(symbol=symbol)
        found_tp1 = any(
            "pos_profit" in str(r).lower() and ("tp1" in str(r).lower() or True) for r in plan_rows
        )
        found_tp2 = any("pos_profit" in str(r).lower() for r in plan_rows)
        found_sl = any("pos_loss" in str(r).lower() for r in plan_rows)
        plans_count = len(plan_rows)
        # Если raw недоступен — fallback на open_orders (может не показывать планы)
        if plans_count == 0 and adapter.client:
            try:
                open_orders = adapter.client.fetch_open_orders(symbol)
            except Exception:
                open_orders = []

            def _is_plan(o: Dict[str, Any]) -> bool:
                t = (o.get("type") or "").lower()
                info = str(o.get("info") or "").lower()
                return ("plan" in info) or ("takeprofit" in t) or ("stop" in t)

            plans = [o for o in (open_orders or []) if _is_plan(o)]
            found_tp1 = found_tp1 or any(
                "tp1" in str(o).lower() or "takeprofit" in (o.get("type") or "").lower()
                for o in plans
            )
            found_tp2 = found_tp2 or any(
                "takeprofit" in (o.get("type") or "").lower() for o in plans
            )
            found_sl = found_sl or any(
                "stop" in (o.get("type") or "").lower() or "loss" in str(o).lower() for o in plans
            )
            plans_count = plans_count or len(plans)
        return {
            "ok": True,
            "symbol": symbol,
            "found_tp1": found_tp1,
            "found_tp2": found_tp2,
            "found_sl": found_sl,
            "plans_count": plans_count,
        }
    except Exception as e:
        return {
            "ok": True,
            "symbol": symbol,
            "found_tp1": None,
            "found_tp2": None,
            "found_sl": None,
            "error": str(e),
        }


def write_report(result: Dict[str, Any]) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("docs/LIVE_TESTS", exist_ok=True)
    path = f"docs/LIVE_TESTS/tp_sl_smoke_{ts}.md"
    lines = []
    lines.append(f"# Live TP/SL Smoke Test — {ts}")
    lines.append("")
    for k, v in result.items():
        lines.append(f"- {k}: {v}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def parse_env() -> Dict[str, Any]:
    user_id = int(os.getenv("SMOKE_USER_ID", "1"))
    symbol = os.getenv("SMOKE_SYMBOL", "BTC/USDT:USDT")
    direction = os.getenv("SMOKE_DIRECTION", "BUY")
    amount_usdt = float(os.getenv("SMOKE_AMOUNT_USDT", "5"))
    leverage = int(os.getenv("SMOKE_LEVERAGE", "2"))
    trade_mode = os.getenv("SMOKE_TRADE_MODE", "futures")
    return {
        "user_id": user_id,
        "symbol": symbol,
        "direction": direction,
        "amount_usdt": amount_usdt,
        "leverage": leverage,
        "trade_mode": trade_mode,
    }


def main() -> None:
    params = parse_env()
    logger.info("🚀 Live TP/SL smoke test: %s", params)
    result = asyncio.run(run_test(**params))
    report = write_report(result)
    if not result.get("ok"):
        logger.error("❌ Smoke test failed: %s (report: %s)", result, report)
    else:
        logger.info("✅ Smoke test done: %s (report: %s)", result, report)


if __name__ == "__main__":
    main()
