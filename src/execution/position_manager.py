"""
ImprovedPositionManager - Улучшенный менеджер позиций с отслеживанием PnL
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.core.exceptions import DatabaseError, FinancialError, ValidationError
from src.data.price_api import get_current_price_robust
from src.database.acceptance import AcceptanceDatabase
from src.execution.audit_log import get_audit_log
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


@dataclass
class PositionData:
    """Данные позиции"""

    symbol: str
    direction: str  # LONG/SHORT
    entry_price: Decimal
    entry_time: datetime
    current_price: Decimal = Decimal("0.0")
    pnl_percent: Decimal = Decimal("0.0")
    pnl_usd: Decimal = Decimal("0.0")
    status: str = "open"  # open, closed, expired
    user_id: Optional[str] = None
    message_id: Optional[int] = None
    chat_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    signal_key: Optional[str] = None


class ImprovedPositionManager:
    """Улучшенный менеджер позиций с интеграцией в БД и Аудит."""

    def __init__(
        self, acceptance_db: Optional[AcceptanceDatabase] = None, telegram_updater: Any = None
    ):
        self.acceptance_db = acceptance_db or AcceptanceDatabase()
        self.audit_log = get_audit_log()
        self.telegram_updater = telegram_updater
        self.active_positions: Dict[str, PositionData] = {}
        self.position_timeout_hours = 24  # Время жизни позиции
        self.update_interval = 60  # Интервал обновления (1 минута)

        logger.info("✅ ImprovedPositionManager инициализирован")

    async def create_position(self, signal_data: Any, user_id: str) -> Optional[PositionData]:
        """Создает новую позицию из принятого сигнала и сохраняет в БД"""
        try:
            position_key = f"{signal_data.symbol}_{int(signal_data.signal_time.timestamp())}"

            # Создаем позицию
            entry_price = Decimal(str(signal_data.entry_price))
            now = get_utc_now()
            position = PositionData(
                symbol=signal_data.symbol,
                direction=signal_data.direction,
                entry_price=entry_price,
                entry_time=now,
                current_price=entry_price,
                user_id=user_id,
                message_id=getattr(signal_data, "message_id", None),
                chat_id=getattr(signal_data, "chat_id", None),
                expires_at=now + timedelta(hours=self.position_timeout_hours),
                signal_key=getattr(signal_data, "signal_key", position_key),
            )

            # Рассчитываем уровни SL/TP
            await self._calculate_sl_tp(position)

            # Сохраняем позицию локально и в БД
            self.active_positions[position_key] = position
            await self._save_position_to_db(position)

            # Логируем в аудит
            await self.audit_log.log_order(
                user_id=int(user_id),
                symbol=position.symbol,
                side=position.direction,
                order_type="MARKET",
                amount=0,  # Зависит от реализации sizing
                price=float(position.entry_price),
                order_id=position.signal_key,
                status="OPENED",
                exchange="bitget",
            )

            logger.info("✅ Позиция создана: %s %s", position.symbol, position.direction)
            return position

        except (ValidationError, FinancialError) as e:
            logger.error("❌ Ошибка валидации или финансовых расчетов при создании позиции: %s", e)
            return None
        except DatabaseError as e:
            logger.error("❌ Ошибка базы данных при создании позиции: %s", e)
            return None
        except Exception as e:
            logger.error("❌ Непредвиденная ошибка создания позиции: %s", e, exc_info=True)
            return None

    async def _calculate_sl_tp(self, position: PositionData):
        """Рассчитывает уровни стоп-лосс и тейк-профит с улучшенным соотношением риск/прибыль"""
        try:
            # УЛУЧШЕННЫЕ ПАРАМЕТРЫ для прибыльности:
            # - Уже стоп-лосс: 1.5% вместо 2% (меньше средний убыток)
            # - Лучшее соотношение риск/прибыль: 1.5% риск на 4.5% прибыль = 1:3
            # - Это должно улучшить средний убыток vs средняя прибыль

            # УЛУЧШЕННЫЕ ПАРАМЕТРЫ для прибыльности:
            # - Уже стоп-лосс: 1.5% вместо 2% (меньше средний убыток)
            # - Лучшее соотношение риск/прибыль: 1.5% риск на 4.5% прибыль = 1:3
            # - TP1 на 3% (соотношение 1:2), TP2 на 4.5% (соотношение 1:3)
            if position.direction.upper() in ["LONG", "BUY"]:
                position.stop_loss = position.entry_price * Decimal("0.985")  # -1.5% (было -2%)
                # Используем TP1 как основной take_profit для лучшего соотношения
                position.take_profit = position.entry_price * Decimal(
                    "1.03"
                )  # +3% (соотношение 1:2)
                # TP2 можно установить отдельно, если нужно
                if not hasattr(position, "take_profit_2"):
                    position.take_profit_2 = position.entry_price * Decimal(
                        "1.045"
                    )  # +4.5% (соотношение 1:3)
            else:
                position.stop_loss = position.entry_price * Decimal("1.015")  # +1.5% (было +2%)
                position.take_profit = position.entry_price * Decimal(
                    "0.97"
                )  # -3% (соотношение 1:2)
                if not hasattr(position, "take_profit_2"):
                    position.take_profit_2 = position.entry_price * Decimal(
                        "0.955"
                    )  # -4.5% (соотношение 1:3)

            logger.debug(
                "SL/TP рассчитаны для %s: SL=%.4f (%.2f%%), TP=%.4f (%.2f%%)",
                position.symbol,
                float(position.stop_loss),
                float((position.stop_loss - position.entry_price) / position.entry_price * 100),
                float(position.take_profit),
                float((position.take_profit - position.entry_price) / position.entry_price * 100),
            )

        except Exception as e:
            logger.error("❌ Ошибка расчета SL/TP: %s", e)
            raise FinancialError(f"Failed to calculate SL/TP for {position.symbol}: {e}") from e

    async def update_position_prices(self, symbol: str, current_price: Decimal) -> bool:
        """Обновляет текущие цены для позиций по символу"""
        try:
            updated_count = 0

            for _, position in self.active_positions.items():
                if position.symbol == symbol and position.status == "open":
                    # Обновляем цену
                    position.current_price = current_price

                    # Рассчитываем PnL
                    await self._calculate_pnl(position)

                    # Проверяем условия закрытия
                    await self._check_exit_conditions(position)

                    updated_count += 1

            if updated_count > 0:
                logger.debug("✅ Обновлено %s позиций для %s", updated_count, symbol)
                return True

            return False

        except Exception as e:
            logger.error("❌ Ошибка обновления цен позиций: %s", e)
            return False

    async def _calculate_pnl(self, position: PositionData):
        """Рассчитывает PnL позиции"""
        try:
            if position.direction.upper() in ["LONG", "BUY"]:
                position.pnl_percent = (
                    (position.current_price - position.entry_price) / position.entry_price
                ) * Decimal("100")
            else:
                position.pnl_percent = (
                    (position.entry_price - position.current_price) / position.entry_price
                ) * Decimal("100")

            position.pnl_usd = (position.pnl_percent / Decimal("100")) * Decimal(
                "100"
            )  # На базе 100 USDT

            logger.debug(
                "PnL %s: %.2f%% (%.2f USDT)",
                position.symbol,
                float(position.pnl_percent),
                float(position.pnl_usd),
            )

        except Exception as e:
            logger.error("❌ Ошибка расчета PnL: %s", e)
            raise FinancialError(f"Failed to calculate PnL for {position.symbol}: {e}") from e

    async def _check_exit_conditions(self, position: PositionData):
        """Проверяет условия для выхода из позиции (SL, TP, Trailing Stop)"""
        try:
            # 1. Проверка Take Profit
            if position.direction.upper() in ["LONG", "BUY"]:
                if position.take_profit and position.current_price >= position.take_profit:
                    await self.close_position(position, reason="Take Profit")
                    return
            else:
                if position.take_profit and position.current_price <= position.take_profit:
                    await self.close_position(position, reason="Take Profit")
                    return

            # 2. Проверка Stop Loss
            if position.direction.upper() in ["LONG", "BUY"]:
                if position.stop_loss and position.current_price <= position.stop_loss:
                    await self.close_position(position, reason="Stop Loss")
                    return
            else:
                if position.stop_loss and position.current_price >= position.stop_loss:
                    await self.close_position(position, reason="Stop Loss")
                    return

            # 3. Проверка истечения времени (Time-based exit)
            if position.expires_at and get_utc_now() > position.expires_at:
                await self.close_position(position, reason="Timeout")
                return

            # 4. ⚡ УЛУЧШЕННЫЙ Trailing Stop для защиты прибыли
            # Активируем раньше (0.5% вместо 1%) для лучшей защиты прибыли
            if position.pnl_percent >= Decimal("0.5"):  # Было 1.0%
                if position.direction.upper() in ["LONG", "BUY"]:
                    # Безубыток + небольшой буфер для комиссий
                    breakeven_sl = position.entry_price * Decimal(
                        "1.002"
                    )  # +0.2% (учитываем комиссии)

                    # Если прибыль > 1%, подтягиваем стоп ближе к цене
                    if position.pnl_percent >= Decimal("1.0"):
                        # Trailing stop на 0.8% ниже текущей цены
                        trailing_sl = position.current_price * Decimal("0.992")  # -0.8%
                        new_sl = max(breakeven_sl, trailing_sl)
                    else:
                        new_sl = breakeven_sl

                    if not position.stop_loss or new_sl > position.stop_loss:
                        position.stop_loss = new_sl
                        logger.info(
                            "🚀 %s Trailing SL: %.2f%% прибыль → SL=%.4f (%.2f%%)",
                            position.symbol,
                            float(position.pnl_percent),
                            float(new_sl),
                            float((new_sl - position.entry_price) / position.entry_price * 100),
                        )
                else:  # SHORT
                    # Безубыток - небольшой буфер для комиссий
                    breakeven_sl = position.entry_price * Decimal("0.998")  # -0.2%

                    # Если прибыль > 1%, подтягиваем стоп ближе к цене
                    if position.pnl_percent >= Decimal("1.0"):
                        # Trailing stop на 0.8% выше текущей цены
                        trailing_sl = position.current_price * Decimal("1.008")  # +0.8%
                        new_sl = min(breakeven_sl, trailing_sl)
                    else:
                        new_sl = breakeven_sl

                    if not position.stop_loss or new_sl < position.stop_loss:
                        position.stop_loss = new_sl
                        logger.info(
                            "🚀 %s Trailing SL: %.2f%% прибыль → SL=%.4f (%.2f%%)",
                            position.symbol,
                            float(position.pnl_percent),
                            float(new_sl),
                            float((position.entry_price - new_sl) / position.entry_price * 100),
                        )

        except Exception as e:
            logger.error("❌ Ошибка проверки условий выхода: %s", e)

    async def close_position(self, position: PositionData, reason: str = "Manual") -> bool:
        """Закрывает позицию и логирует в БД и Аудит"""
        try:
            position.status = "closed"

            # Находим ключ
            position_key = None
            for key, pos in self.active_positions.items():
                if pos == position:
                    position_key = key
                    break

            if position_key:
                del self.active_positions[position_key]

            # Обновляем в БД
            try:
                await self.acceptance_db.close_active_position_by_symbol(
                    user_id=int(position.user_id) if position.user_id else 0, symbol=position.symbol
                )
            except Exception as e:
                logger.error("⚠️ Не удалось закрыть позицию в БД: %s", e)
                # Продолжаем закрытие локально

            # Сохраняем сделку в trades таблицу
            try:
                import sqlite3

                from src.execution.trade_tracker import get_trade_tracker
                from src.shared.utils.datetime_utils import get_utc_now

                tracker = get_trade_tracker()
                if tracker:
                    # Определяем exit_reason на основе reason
                    exit_reason = "MANUAL"
                    if reason == "Timeout":
                        exit_reason = "TIMEOUT"
                    elif reason == "Stop Loss":
                        exit_reason = "SL"
                    elif reason == "Take Profit":
                        exit_reason = "TP2"

                    # Получаем quantity и position_size_usdt из БД
                    quantity = 1.0
                    position_size_usdt = float(position.entry_price)

                    try:
                        with sqlite3.connect("trading.db") as conn:
                            conn.row_factory = sqlite3.Row
                            cursor = conn.cursor()

                            # Пытаемся получить данные из signals_log
                            entry_time_str = position.entry_time.isoformat()
                            cursor.execute(
                                """
                                SELECT qty_added, entry, position_size_usdt
                                FROM signals_log
                                WHERE user_id = ? AND symbol = ? AND entry_time = ?
                                ORDER BY created_at DESC LIMIT 1
                            """,
                                (
                                    str(position.user_id) if position.user_id else None,
                                    position.symbol,
                                    entry_time_str,
                                ),
                            )

                            row = cursor.fetchone()
                            if row:
                                qty_added = row[0]
                                entry_price_db = row[1]
                                position_size_db = row[2]

                                if qty_added and qty_added > 0:
                                    quantity = float(qty_added)
                                if entry_price_db:
                                    entry_price_used = float(entry_price_db)
                                else:
                                    entry_price_used = float(position.entry_price)

                                if position_size_db and position_size_db > 0:
                                    position_size_usdt = float(position_size_db)
                                else:
                                    position_size_usdt = entry_price_used * quantity
                            else:
                                # Если не нашли в signals_log, используем entry_price * 1.0
                                quantity = 1.0
                                position_size_usdt = float(position.entry_price)
                    except Exception as db_e:
                        logger.warning(
                            "⚠️ Не удалось получить quantity из БД: %s, используем значения по умолчанию",
                            db_e,
                        )
                        quantity = 1.0
                        position_size_usdt = float(position.entry_price)

                    await tracker.record_trade(
                        symbol=position.symbol,
                        direction=position.direction,
                        entry_price=float(position.entry_price),
                        exit_price=float(position.current_price),
                        entry_time=position.entry_time,
                        exit_time=get_utc_now(),
                        quantity=quantity,
                        position_size_usdt=position_size_usdt,
                        exit_reason=exit_reason,
                        user_id=str(position.user_id) if position.user_id else None,
                        signal_key=position.signal_key,
                    )
                    logger.info(
                        "✅ Сделка сохранена в trades: %s (%s, qty=%.2f, size=%.2f)",
                        position.symbol,
                        exit_reason,
                        quantity,
                        position_size_usdt,
                    )
            except Exception as e:
                logger.error("⚠️ Ошибка сохранения сделки в trades: %s", e)

            # Логируем в аудит
            await self.audit_log.log_order(
                user_id=int(position.user_id) if position.user_id else 0,
                symbol=position.symbol,
                side="CLOSE",
                order_type="MARKET",
                amount=0,
                price=float(position.current_price),
                order_id=position.signal_key,
                status="CLOSED",
                error_msg=f"Reason: {reason}",
            )

            # Уведомление
            await self._send_close_notification(position, reason)

            logger.info("✅ Позиция закрыта: %s (%s)", position.symbol, reason)
            return True

        except Exception as e:
            logger.error("❌ Ошибка закрытия позиции: %s", e)
            return False

    async def _send_close_notification(self, position: PositionData, reason: str):
        """Отправляет уведомление о закрытии позиции"""
        try:
            if not position.user_id or not position.chat_id:
                return

            # Формируем сообщение
            pnl_emoji = "📈" if position.pnl_percent >= 0 else "📉"
            message = f"""{pnl_emoji} **ПОЗИЦИЯ ЗАКРЫТА**

📊 **Символ:** {position.symbol}
📈 **Направление:** {position.direction}
💰 **Цена входа:** {float(position.entry_price):.4f}
💵 **Цена закрытия:** {float(position.current_price):.4f}
📊 **PnL:** {float(position.pnl_percent):+.2f}% ({float(position.pnl_usd):+.2f} USDT)
🔚 **Причина:** {reason}
⏰ **Время:** {get_utc_now().strftime("%d.%m.%Y %H:%M")}"""

            await self.telegram_updater.send_notification(position.chat_id, message, "success")

        except Exception as e:
            logger.error("❌ Ошибка отправки уведомления о закрытии: %s", e)

    async def get_active_positions(self) -> List[PositionData]:
        """Получает все активные позиции"""
        try:
            return [pos for pos in self.active_positions.values() if pos.status == "open"]
        except Exception as e:
            logger.error("❌ Ошибка получения активных позиций: %s", e)
            return []

    async def get_user_positions(self, user_id: str) -> List[PositionData]:
        """Получает позиции пользователя"""
        try:
            return [
                pos
                for pos in self.active_positions.values()
                if pos.user_id == user_id and pos.status == "open"
            ]
        except Exception as e:
            logger.error("❌ Ошибка получения позиций пользователя: %s", e)
            return []

    async def _save_position_to_db(self, position: PositionData):
        """Сохраняет позицию в AcceptanceDatabase"""
        try:
            await self.acceptance_db.create_active_position(
                symbol=position.symbol,
                direction=position.direction,
                entry_price=float(position.entry_price),
                user_id=int(position.user_id) if position.user_id else 0,
                chat_id=int(position.chat_id) if position.chat_id else 0,
                message_id=int(position.message_id) if position.message_id else 0,
                signal_key=position.signal_key or position.symbol,
            )
        except Exception as e:
            logger.error("❌ Ошибка сохранения позиции в БД: %s", e)

    async def _update_position_in_db(self, position: PositionData):
        """Обновляет позицию в БД (заглушка для обратной совместимости)"""

    async def start_price_monitoring(self):
        """🚀 ЭКСПЕРТНАЯ ОПТИМИЗАЦИЯ (Игорь): Параллельный мониторинг цен позиций"""
        try:
            while True:
                # Обновляем цены для всех активных позиций
                symbols = list(
                    set(
                        pos.symbol for pos in self.active_positions.values() if pos.status == "open"
                    )
                )

                if not symbols:
                    await asyncio.sleep(self.update_interval)
                    continue

                # ⚡ Используем gather для параллельного получения цен
                tasks = [self._get_current_price(symbol) for symbol in symbols]
                prices = await asyncio.gather(*tasks, return_exceptions=True)

                for symbol, price in zip(symbols, prices):
                    if isinstance(price, Decimal) and price > 0:
                        await self.update_position_prices(symbol, price)
                    elif isinstance(price, Exception):
                        logger.error("❌ Error fetching price for %s: %s", symbol, price)

                # Ждем следующий цикл
                await asyncio.sleep(self.update_interval)

        except Exception as e:
            logger.error("❌ Ошибка мониторинга цен: %s", e)

    async def _get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Получает текущую цену символа через робастный API (🚀 ТОЧНОСТЬ DECIMAL)"""
        price = await get_current_price_robust(symbol)
        if price is not None:
            return Decimal(str(price))
        return None

    async def get_position_statistics(self) -> Dict[str, Any]:
        """Получает статистику позиций с использованием Decimal"""
        try:
            active_positions = await self.get_active_positions()

            total_positions = len(active_positions)
            if total_positions == 0:
                return {
                    "total_positions": 0,
                    "profitable_positions": 0,
                    "losing_positions": 0,
                    "total_pnl_percent": Decimal("0"),
                    "avg_pnl_percent": Decimal("0"),
                    "win_rate": 0,
                }

            profitable_positions = len([p for p in active_positions if p.pnl_percent > 0])
            losing_positions = len([p for p in active_positions if p.pnl_percent < 0])

            total_pnl = sum(p.pnl_percent for p in active_positions)
            avg_pnl = total_pnl / Decimal(str(total_positions))

            return {
                "total_positions": total_positions,
                "profitable_positions": profitable_positions,
                "losing_positions": losing_positions,
                "total_pnl_percent": total_pnl,
                "avg_pnl_percent": avg_pnl,
                "win_rate": (profitable_positions / total_positions * 100),
            }

        except Exception as e:
            logger.error("❌ Ошибка получения статистики позиций: %s", e)
            return {}
