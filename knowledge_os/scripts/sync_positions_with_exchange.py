#!/usr/bin/env python3
import asyncio
import logging
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync_positions")


async def sync_user(user_id: int) -> Dict[str, Any]:
    from acceptance_database import AcceptanceDatabase
    from exchange_adapter import ExchangeAdapter

    adb = AcceptanceDatabase()

    keys = await adb.get_active_exchange_keys(user_id, "bitget")
    if not keys:
        return {"user_id": user_id, "skipped": True, "reason": "no_keys"}

    adapter = ExchangeAdapter("bitget", keys=keys, sandbox=False, trade_mode="futures")
    if not adapter.client:
        return {"user_id": user_id, "skipped": True, "reason": "no_client"}

    # Биржевые позиции
    exch_positions = await adapter.fetch_positions() or []
    exch_map = {}
    for p in exch_positions:
        try:
            sym = (p.get("symbol") or "").replace("/", "").replace(":USDT", "")
            side = (p.get("side") or "").lower()
            size = float(p.get("contracts") or p.get("size") or 0.0)
            if size > 0 and sym:
                exch_map[(sym, side)] = size
        except Exception:
            continue

    # Позиции из БД
    db_positions = await adb.get_active_positions_by_user(str(user_id))
    closed = 0
    upserted = 0

    # Закрываем те, которых нет на бирже
    for pos in db_positions:
        sym_db = (pos.get("symbol") or "").replace("/", "").replace(":USDT", "")
        dir_db = (pos.get("direction") or "").upper()
        side = "long" if dir_db == "BUY" else "short"
        if (sym_db, side) not in exch_map:
            ok = await adb.close_active_position_by_symbol(user_id, pos.get("symbol") or sym_db)
            if ok:
                closed += 1

    # Добавляем позиции с биржи, которых нет в БД
    db_map = {}
    for pos in db_positions:
        sym_db = (pos.get("symbol") or "").replace("/", "").replace(":USDT", "")
        dir_db = (pos.get("direction") or "").upper()
        side = "long" if dir_db == "BUY" else "short"
        db_map[(sym_db, side)] = True

    for p in exch_positions:
        try:
            sym = (p.get("symbol") or "").replace("/", "").replace(":USDT", "")
            side = (p.get("side") or "").lower()
            size = float(p.get("contracts") or p.get("size") or 0.0)
            entry_price = float(p.get("entryPrice") or p.get("openPriceAvg") or 0.0)

            if size > 0 and sym and entry_price > 0:
                if (sym, side) not in db_map:
                    # 🛡️ ПРОВЕРКА: Определяем источник позиции
                    direction = "BUY" if side == "long" else "SELL"

                    # Проверяем наличие сигнала в accepted_signals
                    has_signal = False
                    try:
                        signal_data = await adb.get_signal_data(user_id, sym)
                        if signal_data:
                            has_signal = True
                    except Exception:
                        pass

                    # 🆕 БЛОКИРУЕМ: Если сигнала нет - это ручная позиция, НЕ добавляем в БД
                    if not has_signal:
                        logger.warning(
                            "🚫 [SYNC_BLOCK] %s %s: Позиция найдена на бирже БЕЗ сигнала в системе. "
                            "Позиция НЕ будет добавлена в БД (открыта вручную или через другой процесс).",
                            sym,
                            direction,
                        )
                        continue  # 🆕 БЛОКИРУЕМ: не добавляем ручные позиции

                    # Добавляем позицию в БД только если есть соответствующий сигнал
                    ok = await adb.create_active_position(
                        symbol=sym,
                        direction=direction,
                        entry_price=entry_price,
                        user_id=user_id,
                        message_id=None,
                        chat_id=None,
                        signal_key=None,
                    )
                    if ok:
                        upserted += 1
                        logger.info(
                            "✅ Синхронизирована позиция: %s %s @ %.8f", sym, direction, entry_price
                        )
        except Exception as e:
            logger.debug("Ошибка добавления позиции %s: %s", p.get("symbol"), e)

    return {"user_id": user_id, "skipped": False, "closed": closed, "upserted": upserted}


async def main_async() -> None:
    from acceptance_database import AcceptanceDatabase

    adb = AcceptanceDatabase()
    # Берём всех пользователей с auto-режимом
    auto_users = await adb.get_users_by_mode("auto")
    if not auto_users:
        logger.info("Нет пользователей в auto-режиме, синхронизация пропущена")
        return

    results: List[Dict[str, Any]] = []
    for uid in auto_users:
        try:
            res = await sync_user(uid)
            results.append(res)
            logger.info("user %s sync: %s", uid, res)
        except Exception as e:
            logger.error("Ошибка синхронизации user %s: %s", uid, e)

    logger.info("✅ Sync finished: %s", results)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
