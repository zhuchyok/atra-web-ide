#!/usr/bin/env python3
"""
Скрипт для проверки реальных TP1 ордеров на Bitget
Проверяет, правильно ли выставляются частичные TP1 ордера
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging

from config import BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE
from src.execution.exchange_adapter import ExchangeAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_tp1_orders():
    """Проверяет активные TP1 ордера на Bitget"""
    try:
        adapter = ExchangeAdapter(
            exchange_name="bitget",
            api_key=BITGET_API_KEY,
            api_secret=BITGET_API_SECRET,
            passphrase=BITGET_PASSPHRASE,
            trade_mode="futures",
        )

        # Получаем активные план-ордера
        plan_orders = await adapter.fetch_plan_orders()

        print("🔍 ПРОВЕРКА TP1 ОРДЕРОВ НА BITGET")
        print("=" * 70)

        if not plan_orders:
            print("❌ Нет активных план-ордеров")
            return

        print(f"\n✅ Найдено {len(plan_orders)} активных план-ордеров:\n")

        tp1_orders = []
        tp2_orders = []
        sl_orders = []

        for order in plan_orders:
            order_type = order.get("planType") or order.get("plan_type", "")
            client_oid = order.get("clientOid") or order.get("client_oid", "")
            size = order.get("size") or order.get("size", 0)
            trigger_price = order.get("triggerPrice") or order.get("trigger_price", 0)
            pos_side = order.get("holdSide") or order.get("pos_side", "")

            if "tp1" in client_oid.lower():
                tp1_orders.append(
                    {
                        "client_oid": client_oid,
                        "size": size,
                        "trigger_price": trigger_price,
                        "pos_side": pos_side,
                        "order": order,
                    }
                )
            elif "tp2" in client_oid.lower():
                tp2_orders.append(
                    {
                        "client_oid": client_oid,
                        "size": size,
                        "trigger_price": trigger_price,
                        "pos_side": pos_side,
                        "order": order,
                    }
                )
            elif "sl" in client_oid.lower():
                sl_orders.append(
                    {
                        "client_oid": client_oid,
                        "size": size,
                        "trigger_price": trigger_price,
                        "pos_side": pos_side,
                        "order": order,
                    }
                )

        print("📊 Статистика:")
        print(f"   TP1 ордеров: {len(tp1_orders)}")
        print(f"   TP2 ордеров: {len(tp2_orders)}")
        print(f"   SL ордеров: {len(sl_orders)}")

        # Получаем реальные позиции на бирже
        positions = await adapter.fetch_positions()

        print(f"\n📈 Реальные позиции на бирже: {len(positions) if positions else 0}")

        if positions:
            for pos in positions:
                symbol = pos.get("symbol") or pos.get("info", {}).get("symbol", "")
                size = float(
                    pos.get("contracts") or pos.get("size") or pos.get("info", {}).get("size", 0)
                )
                pos_side = pos.get("side") or pos.get("info", {}).get("holdSide", "")

                if abs(size) > 0:
                    print(f"\n   {symbol} {pos_side}:")
                    print(f"      Размер позиции: {abs(size)}")

                    # Ищем соответствующие TP1 ордера
                    matching_tp1 = [o for o in tp1_orders if symbol in o.get("client_oid", "")]
                    if matching_tp1:
                        for tp1 in matching_tp1:
                            tp1_size = float(tp1.get("size", 0))
                            percentage = (tp1_size / abs(size) * 100) if abs(size) > 0 else 0
                            print(f"      TP1: size={tp1_size}, процент={percentage:.1f}%")
                            if percentage > 60:
                                print(
                                    f"      ⚠️ ВНИМАНИЕ: TP1 закрывает {percentage:.1f}% позиции (должно быть ~50%)"
                                )
                            elif percentage < 40:
                                print(
                                    f"      ⚠️ ВНИМАНИЕ: TP1 закрывает только {percentage:.1f}% позиции (должно быть ~50%)"
                                )
                    else:
                        print("      ❌ TP1 ордер не найден!")

        # Детальный вывод TP1 ордеров
        if tp1_orders:
            print("\n📋 Детали TP1 ордеров:")
            for tp1 in tp1_orders:
                print(f"\n   Client OID: {tp1['client_oid']}")
                print(f"   Size: {tp1['size']}")
                print(f"   Trigger Price: {tp1['trigger_price']}")
                print(f"   Pos Side: {tp1['pos_side']}")
                print(f"   Полный ордер: {tp1['order']}")

    except Exception as e:
        logger.error(f"❌ Ошибка проверки TP1 ордеров: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(check_tp1_orders())
