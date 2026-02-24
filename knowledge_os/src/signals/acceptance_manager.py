"""
SignalAcceptanceManager - Система управления принятием сигналов через интерактивные кнопки
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
except ImportError:
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


@dataclass
class SignalData:
    """Данные сигнала"""

    symbol: str
    direction: str  # LONG/SHORT
    entry_price: float
    signal_time: datetime
    message_id: Optional[int] = None
    chat_id: Optional[int] = None
    user_id: Optional[str] = None
    status: str = "pending"  # pending, accepted, in_progress, closed
    accepted_time: Optional[datetime] = None
    accepted_by: Optional[str] = None


class SignalAcceptanceManager:
    """Менеджер принятия сигналов с интерактивными кнопками"""

    def __init__(self, acceptance_db, telegram_updater, position_manager):
        self.acceptance_db = acceptance_db
        self.telegram_updater = telegram_updater
        self.position_manager = position_manager
        self.pending_signals: Dict[str, SignalData] = {}
        self.active_positions: Dict[str, SignalData] = {}

        logger.info("✅ SignalAcceptanceManager инициализирован")

    async def initialize(self):
        """Асинхронная инициализация - загружает существующие сигналы"""
        await self.load_existing_signals()

    def create_acceptance_keyboard(self, signal_data: SignalData) -> Dict[str, Any]:
        """Создает клавиатуру с кнопками для принятия сигнала"""
        try:
            if not InlineKeyboardButton or not InlineKeyboardMarkup:
                logger.error("❌ Telegram библиотека не найдена")
                return None

            # Основные кнопки
            buttons = []

            if signal_data.status == "pending":
                # Кнопка принятия сигнала
                accept_text = f"✅ Принять {signal_data.direction}"
                buttons.append(
                    [
                        InlineKeyboardButton(
                            accept_text,
                            callback_data=f"accept_{signal_data.symbol}_{signal_data.signal_time.timestamp()}",
                        )
                    ]
                )

            elif signal_data.status == "accepted":
                # Кнопка закрытия позиции
                close_text = f"🔴 Закрыть {signal_data.direction}"
                buttons.append(
                    [
                        InlineKeyboardButton(
                            close_text,
                            callback_data=f"close_{signal_data.symbol}_{signal_data.signal_time.timestamp()}",
                        )
                    ]
                )

            elif signal_data.status == "in_progress":
                # Информационная кнопка
                info_text = f"🔄 В работе {signal_data.direction}"
                buttons.append([InlineKeyboardButton(info_text, callback_data="info")])

            return InlineKeyboardMarkup(buttons)

        except Exception as e:
            logger.error("❌ Ошибка создания клавиатуры: %s", e)
            return None

    async def register_signal(self, signal_data: SignalData, message_id: int, chat_id: int) -> bool:
        """Регистрирует новый сигнал в системе"""
        try:
            # Сохраняем данные сигнала
            signal_data.message_id = message_id
            signal_data.chat_id = chat_id
            signal_data.status = "pending"

            # Сохраняем в базу данных
            await self.acceptance_db.save_signal(signal_data)

            # Добавляем в локальный кэш
            # Используем timestamp из signal_data для консистентности
            signal_timestamp = signal_data.signal_time.timestamp()
            signal_key = f"{signal_data.symbol}_{signal_timestamp}"
            self.pending_signals[signal_key] = signal_data

            logger.info(
                "✅ Сигнал зарегистрирован: %s %s", signal_data.symbol, signal_data.direction
            )
            return True

        except Exception as e:
            logger.error("❌ Ошибка регистрации сигнала: %s", e)
            return False

    async def accept_signal(self, symbol: str, signal_timestamp: float, user_id: str) -> bool:
        """Принимает сигнал пользователем - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            signal_key = f"{symbol}_{signal_timestamp}"
            logger.info("🔄 Попытка принятия сигнала %s пользователем %s", symbol, user_id)
            logger.info("🔍 Ищем сигнал: %s", signal_key)
            logger.info("🔍 Доступные сигналы: %s", list(self.pending_signals.keys()))

            # Получаем данные сигнала из базы
            signal_data_db = self.acceptance_db.get_signal_by_symbol(
                symbol, user_id, signal_timestamp
            )
            if not signal_data_db:
                logger.error("❌ Сигнал %s не найден в базе для пользователя %s", symbol, user_id)
                return False

            # Если не переданы message_id и chat_id, пытаемся получить из базы
            message_id = signal_data_db.get("message_id")
            chat_id = signal_data_db.get("chat_id")

            if not message_id or not chat_id:
                logger.error("❌ Не найдены message_id или chat_id для сигнала %s", symbol)
                return False

            # Обновляем статус в базе данных
            success = self.acceptance_db.update_signal_status(symbol, "accepted", user_id)

            if not success:
                logger.error("❌ Не удалось обновить статус в базе для %s", symbol)
                return False

            # 🆕 ПРОВЕРКА: Есть ли у пользователя ключи биржи для открытия позиции
            has_exchange_keys = False
            try:
                keys = await self.acceptance_db.get_active_exchange_keys(int(user_id), "bitget")
                # get_active_exchange_keys возвращает Dict или None
                has_exchange_keys = bool(keys and isinstance(keys, dict) and keys.get("api_key"))
                status_text = "есть" if has_exchange_keys else "нет"
                logger.info("🔍 [ACCEPT] Пользователь %s: ключи биржи = %s", user_id, status_text)
            except Exception as e:
                logger.debug("⚠️ Ошибка проверки ключей для %s: %s", user_id, e)
                has_exchange_keys = False

            # Обновляем signals_log: PENDING -> OPEN (для корреляции в manual-режиме)
            # Это делается ВСЕГДА, даже если ключей нет (для расчета рисков)
            try:
                await self.acceptance_db.update_signals_log_result(symbol, user_id, "OPEN")
                logger.info("✅ [ACCEPT] Сигнал %s учтен для расчета рисков (status=OPEN)", symbol)
            except Exception:
                logger.debug("signals_log update skip (non-fatal)")

            # 🆕 ОТКРЫВАЕМ ПОЗИЦИЮ ТОЛЬКО ЕСЛИ ЕСТЬ КЛЮЧИ БИРЖИ
            if has_exchange_keys:
                # ОТКРЫВАЕМ ПОЗИЦИЮ НА БИРЖЕ
                position_data = {
                    "symbol": symbol,
                    "direction": signal_data_db["direction"],
                    "entry_price": signal_data_db.get("entry_price"),
                    "user_id": user_id,
                    "message_id": message_id,
                    "chat_id": chat_id,
                }

                position_result = self.position_manager.open_position(position_data)

                if position_result:
                    logger.info(
                        "✅ [ACCEPT] Позиция открыта на бирже для %s (у пользователя есть ключи)",
                        symbol,
                    )

                    # 🔥 ГЛАВНОЕ ИСПРАВЛЕНИЕ: ОБНОВЛЯЕМ СООБЩЕНИЕ В TELEGRAM
                    update_success = await self.telegram_updater.update_acceptance_status(
                        chat_id=chat_id,
                        message_id=message_id,
                        symbol=symbol,
                        direction=signal_data_db["direction"],
                        accepted_by=user_id,
                    )

                    if update_success:
                        logger.info("✅ Сообщение Telegram обновлено для %s", symbol)
                    else:
                        logger.error("❌ Не удалось обновить сообщение Telegram для %s", symbol)

                    return True
                else:
                    logger.error("❌ Не удалось открыть позицию на бирже для %s", symbol)
                    return False
            else:
                # 🆕 КЛЮЧЕЙ НЕТ: Только учитываем для расчета рисков, позицию НЕ открываем
                logger.info(
                    "📊 [ACCEPT] Сигнал %s принят пользователем %s БЕЗ ключей биржи. "
                    "Учитывается для расчета рисков, позиция НЕ открывается на бирже.",
                    symbol,
                    user_id,
                )

                # Обновляем сообщение в Telegram (сигнал принят, но позиция не открыта)
                try:
                    update_success = await self.telegram_updater.update_acceptance_status(
                        chat_id=chat_id,
                        message_id=message_id,
                        symbol=symbol,
                        direction=signal_data_db["direction"],
                        accepted_by=user_id,
                    )
                    if update_success:
                        logger.info(
                            "✅ Сообщение Telegram обновлено для %s (без открытия позиции)", symbol
                        )
                except Exception as e:
                    logger.debug("⚠️ Ошибка обновления сообщения Telegram: %s", e)

                # Возвращаем True, так как сигнал успешно принят (учтен для рисков)
                return True

        except Exception as e:
            logger.error("❌ Критическая ошибка при принятии сигнала: %s", e)
            return False

    async def update_signal_message_id(
        self, symbol: str, signal_timestamp: float, message_id: int
    ) -> bool:
        """Обновляет message_id для сигнала"""
        try:
            signal_key = f"{symbol}_{signal_timestamp}"

            # Обновляем в локальном кэше
            if signal_key in self.pending_signals:
                self.pending_signals[signal_key].message_id = message_id

            # Обновляем в базе данных
            success = await self.acceptance_db.update_signal_message_id(
                symbol, signal_timestamp, message_id
            )

            if success:
                logger.info("✅ Message ID обновлен для %s: %s", symbol, message_id)
            else:
                logger.warning("⚠️ Не удалось обновить message_id для %s", symbol)

            return success

        except Exception as e:
            logger.error("❌ Ошибка обновления message_id: %s", e)
            return False

    async def close_position(self, symbol: str, signal_timestamp: float, user_id: str) -> bool:
        """Закрывает позицию"""
        try:
            signal_key = f"{symbol}_{signal_timestamp}"

            if signal_key not in self.active_positions:
                logger.warning("⚠️ Позиция %s не найдена", signal_key)
                return False

            signal_data = self.active_positions[signal_key]

            # Обновляем статус
            signal_data.status = "closed"

            # Сохраняем в базу данных
            await self.acceptance_db.update_signal_status(signal_key, "closed", user_id)

            # Удаляем из активных позиций
            del self.active_positions[signal_key]

            # Обновляем сообщение в Telegram
            await self.telegram_updater.update_signal_message(
                signal_data.chat_id,
                signal_data.message_id,
                signal_data,
                self.create_acceptance_keyboard(signal_data),
            )

            logger.info("✅ Позиция закрыта: %s пользователем %s", symbol, user_id)
            return True

        except Exception as e:
            logger.error("❌ Ошибка закрытия позиции: %s", e)
            return False

    async def get_user_signals(self, user_id: str) -> List[SignalData]:
        """Получает все сигналы пользователя"""
        try:
            return await self.acceptance_db.get_user_signals(user_id)
        except Exception as e:
            logger.error("❌ Ошибка получения сигналов пользователя: %s", e)
            return []

    async def get_active_positions(self) -> List[SignalData]:
        """Получает все активные позиции"""
        try:
            return list(self.active_positions.values())
        except Exception as e:
            logger.error("❌ Ошибка получения активных позиций: %s", e)
            return []

    async def cleanup_expired_signals(self, max_age_hours: int = 24):
        """Очищает устаревшие сигналы"""
        try:
            cutoff_time = get_utc_now() - timedelta(hours=max_age_hours)

            expired_signals = []
            for signal_key, signal_data in self.pending_signals.items():
                if signal_data.signal_time < cutoff_time:
                    expired_signals.append(signal_key)

            for signal_key in expired_signals:
                signal_data = self.pending_signals[signal_key]
                signal_data.status = "expired"
                await self.acceptance_db.update_signal_status(signal_key, "expired", None)
                del self.pending_signals[signal_key]

            if expired_signals:
                logger.info("🧹 Очищено %s устаревших сигналов", len(expired_signals))

        except Exception as e:
            logger.error("❌ Ошибка очистки устаревших сигналов: %s", e)

    async def get_statistics(self) -> Dict[str, Any]:
        """Получает статистику принятия сигналов"""
        try:
            stats = await self.acceptance_db.get_statistics()
            stats.update(
                {
                    "pending_signals": len(self.pending_signals),
                    "active_positions": len(self.active_positions),
                }
            )
            return stats
        except Exception as e:
            logger.error("❌ Ошибка получения статистики: %s", e)
            return {}

    async def load_existing_signals(self):
        """Загружает существующие сигналы из базы данных"""
        try:
            # Получаем все pending сигналы из базы данных
            with sqlite3.connect(self.acceptance_db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT symbol, direction, entry_price, signal_time, message_id,
                           chat_id, user_id, status, accepted_time, accepted_by, signal_key
                    FROM accepted_signals
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                """)

                rows = cursor.fetchall()
                logger.info("🔍 Найдено %s pending сигналов в БД", len(rows))

                for row in rows:
                    (
                        symbol,
                        direction,
                        entry_price,
                        signal_time_str,
                        message_id,
                        chat_id,
                        user_id,
                        status,
                        accepted_time_str,
                        accepted_by,
                        signal_key,
                    ) = row

                    # Создаем объект SignalData
                    signal_data = SignalData(
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        signal_time=datetime.fromisoformat(signal_time_str),
                        message_id=message_id,
                        chat_id=chat_id,
                        user_id=user_id,
                        status=status,
                        accepted_time=datetime.fromisoformat(accepted_time_str)
                        if accepted_time_str
                        else None,
                        accepted_by=accepted_by,
                    )

                    # Добавляем в pending_signals
                    self.pending_signals[signal_key] = signal_data

                logger.info("✅ Загружено %s pending сигналов из базы данных", len(rows))

        except Exception as e:
            logger.error("❌ Ошибка загрузки существующих сигналов: %s", e)
