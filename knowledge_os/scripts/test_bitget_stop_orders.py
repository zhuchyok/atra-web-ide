#!/usr/bin/env python3
"""
Тестовый прогон Bitget-фьючерсов:
- открывает минимальную SHORT позицию
- выставляет плановый Stop Loss через ExchangeAdapter
- проверяет, что план-ордер создан
- очищает всё (отменяет SL и закрывает позицию)

⚠️ Требуются реальные API-ключи Bitget в переменных окружения:
    BITGET_API_KEY, BITGET_SECRET, BITGET_PASSWORD

Использовать осмотрительно: скрипт работает с реальным аккаунтом.
"""

import asyncio
import logging
import os
import pathlib
import sys
from dataclasses import dataclass
from typing import Dict, Optional

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.execution.exchange_adapter import ExchangeAdapter

try:
    import ccxt as ccxt_sync  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError("ccxt не установлен, выполните `pip install ccxt`.") from exc


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bitget_stoploss_test")


@dataclass
class TestConfig:
    """Параметры тестового запуска."""

    symbol: str = "DASHUSDT"
    leverage: int = 2
    entry_notional: float = 15.0  # USDT
    stop_offset_pct: float = 2.5  # отступ для SL (над входом для SHORT)


def _read_env_keys() -> Dict[str, str]:
    """Читает ключи Bitget из env."""
    env_map = {
        "api_key": os.environ.get("BITGET_API_KEY"),
        "secret": os.environ.get("BITGET_SECRET"),
        "passphrase": os.environ.get("BITGET_PASSWORD"),
    }
    missing = [name for name, value in env_map.items() if not value]

    if missing:
        env_path = pathlib.Path(".env")
        if env_path.exists():
            logger.info("🔐 Загружаю ключи из .env (переменные окружения не найдены).")
            with env_path.open("r", encoding="utf-8") as env_file:
                for line in env_file:
                    striped = line.strip()
                    if not striped or striped.startswith("#") or "=" not in striped:
                        continue
                    key, raw_value = striped.split("=", 1)
                    key = key.strip()
                    value = raw_value.strip().strip('"').strip("'")
                    if key == "BITGET_API_KEY" and not env_map["api_key"]:
                        env_map["api_key"] = value
                    elif key == "BITGET_SECRET" and not env_map["secret"]:
                        env_map["secret"] = value
                    elif key == "BITGET_PASSWORD" and not env_map["passphrase"]:
                        env_map["passphrase"] = value
            missing = [name for name, value in env_map.items() if not value]

    if missing:
        hint = ", ".join(missing)
        raise RuntimeError(f"Не заданы переменные окружения или значения в .env для Bitget: {hint}")
    return env_map  # type: ignore[return-value]


def _calc_amount(client: ccxt_sync.Exchange, symbol: str, price: float, notional: float) -> float:
    """Рассчитывает и нормализует объём по лимитам биржи."""
    raw_amount = max(notional / price, 0.0001)
    try:
        amount_precision = float(client.amount_to_precision(symbol, raw_amount))
    except Exception:  # pragma: no cover
        amount_precision = float(f"{raw_amount:.6f}")
    market = client.market(symbol)
    min_amount = float(market.get("limits", {}).get("amount", {}).get("min") or 0)
    if min_amount and amount_precision < min_amount:
        amount_precision = min_amount
    return amount_precision


def _format_price(client: ccxt_sync.Exchange, symbol: str, price: float) -> float:
    """Приводит цену к требуемой точности."""
    try:
        return float(client.price_to_precision(symbol, price))
    except Exception:  # pragma: no cover
        return float(f"{price:.6f}")


async def _close_position(
    adapter: ExchangeAdapter,
    symbol: str,
    amount: float,
) -> None:
    """Закрывает позицию маркет-ордером reduce only."""
    await adapter.create_market_order(
        symbol=symbol,
        side="buy",
        amount=amount,
        reduce_only=True,
    )


async def run_test(config: TestConfig) -> None:
    """Основной сценарий проверки Stop Loss."""
    keys = _read_env_keys()
    adapter = ExchangeAdapter("bitget", keys=keys, sandbox=False, trade_mode="futures")
    if adapter.client is None:
        raise RuntimeError("Не удалось инициализировать ExchangeAdapter (ccxt клиент None).")

    client: ccxt_sync.Exchange = adapter.client
    client.load_markets()

    ticker = client.fetch_ticker(config.symbol)
    last_price = float(ticker.get("last") or ticker.get("close"))
    if last_price <= 0:
        raise RuntimeError(f"Не удалось получить цену для {config.symbol}")
    logger.info("📈 Последняя цена %s: %.8f", config.symbol, last_price)

    amount = _calc_amount(client, config.symbol, last_price, config.entry_notional)
    logger.info("🧮 Объём позиции: %.6f %s", amount, config.symbol.replace("USDT", ""))

    await adapter.set_leverage(config.symbol, config.leverage)

    logger.info("🚀 Открываю тестовый SHORT через маркет.")
    entry = await adapter.create_market_order(config.symbol, "sell", amount)
    if not entry or not entry.get("id"):
        raise RuntimeError("Не удалось открыть позицию, маркет-ордер не создан.")

    stop_price = _format_price(
        client,
        config.symbol,
        last_price * (1 + config.stop_offset_pct / 100),
    )
    logger.info("🛡️ Выставляю Stop Loss %.6f (offset %.2f%%)", stop_price, config.stop_offset_pct)
    plan_order: Optional[Dict[str, str]] = await adapter.place_stop_loss_order(
        symbol=config.symbol,
        direction="SHORT",
        position_amount=amount,
        stop_price=stop_price,
        reduce_only=True,
    )

    if not plan_order or not plan_order.get("id"):
        raise RuntimeError("Плановый стоп не создан — требуется разбор логов.")

    plan_id = str(plan_order["id"])
    margin_coin = client.market(config.symbol).get("settle", "USDT")
    logger.info("✅ Плановый стоп установлен, id=%s", plan_id)

    logger.info("⏳ Ожидаю 3 секунды и проверяю наличие ордера.")
    await asyncio.sleep(3)

    try:
        open_plans = client.fetch_open_orders(
            config.symbol,
            params={
                "trigger": True,
                "planType": "pos_loss",
                "productType": "USDT-FUTURES",
                "marginCoin": margin_coin,
            },
        )
        logger.info("📋 Текущие плановые ордера: %s", open_plans)
    except Exception as exc:  # pragma: no cover - сеть/ответ Bitget
        logger.warning("⚠️ Не удалось получить список плановых ордеров: %s", exc)

    logger.info("🧹 Чищу тест: отмена SL и закрытие позиции.")
    client.cancel_order(
        plan_id,
        config.symbol,
        params={
            "trigger": True,
            "planType": "pos_loss",
            "productType": "USDT-FUTURES",
            "marginMode": "isolated",
            "marginCoin": margin_coin,
        },
    )
    await asyncio.sleep(1)
    await _close_position(adapter, config.symbol, amount)

    logger.info("🏁 Тест завершён. Проверьте баланс и журналы для подтверждения.")


if __name__ == "__main__":
    asyncio.run(run_test(TestConfig()))
