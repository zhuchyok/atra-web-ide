import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class StuckPositionMonitor:
    """
    Мониторит 'зависшие' позиции и принимает решения по их восстановлению.
    """

    def __init__(self, db_path: Optional[str] = None):
        from src.database.acceptance import AcceptanceDatabase

        self.adb = AcceptanceDatabase(db_path=db_path)
        self.db_path = self.adb.db_path
        # Внутренний кэш для защиты от спама в рамках одной сессии (на всякий случай)
        self._local_history = {}

    async def run_monitor(self, user_id: int):
        """Основной цикл мониторинга"""
        while True:
            try:
                positions = await self.get_active_positions(user_id)
                for pos in positions:
                    await self.process_position(user_id, pos)
                await asyncio.sleep(300)  # Проверка каждые 5 минут
            except Exception as e:
                logger.error("❌ [ARS] Ошибка монитора: %s", e)
                await asyncio.sleep(60)

    async def get_active_positions(self, user_id: int) -> List[Dict]:
        """Получает открытые позиции из БД"""
        query = "SELECT * FROM active_positions WHERE user_id = ? AND status = 'open'"
        rows = await self.adb.execute_with_retry(query, (user_id,), is_write=False)

        positions = []
        if rows:
            for row in rows:
                positions.append(
                    {
                        "id": row[0],
                        "symbol": row[1],
                        "direction": row[2],
                        "entry_price": row[3],
                        "entry_time": row[4],
                        "current_price": row[5],
                        "pnl_percent": row[6],
                        "status": row[7],
                        "accepted_by": row[8],
                        "user_id": row[9],
                        "message_id": row[10],
                        "chat_id": row[11],
                        "signal_key": row[12],
                        "ars_last_action": row[14],
                        "ars_last_time": row[15],
                    }
                )
        return positions

    async def process_position(self, user_id: int, pos: Dict):
        """Анализирует конкретную позицию"""
        symbol = pos["symbol"]
        pnl_pct = pos.get("pnl_percent", 0)

        # Если PnL ниже -3% и позиция открыта более 4 часов
        entry_time_str = pos.get("entry_time")
        if not entry_time_str:
            return

        try:
            entry_time = (
                datetime.fromisoformat(entry_time_str)
                if "T" in entry_time_str
                else datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
            )
        except Exception:
            return

        hours_open = (get_utc_now() - entry_time).total_seconds() / 3600

        if pnl_pct < -3.0 or hours_open > 12:
            await self.make_decision(user_id, pos, pnl_pct, hours_open)

    async def make_decision(self, user_id: int, pos: Dict, pnl_pct: float, hours_open: float):
        """Принимает решение по 'зависшей' позиции"""
        symbol = pos["symbol"]

        # ЛОГИКА ПРИНЯТИЯ РЕШЕНИЯ
        decision = "DYNAMIC_TRAILING"
        reason = "Боковик. Ждем локального слива для выхода."

        if pnl_pct < -10.0:
            decision = "FORCE_CLOSE"
            reason = "Критический убыток. Принудительное закрытие для сохранения депо."
        elif hours_open > 48:
            decision = "REDUCE_POSITION"
            reason = "Позиция открыта слишком долго. Сокращение объема."

        # 🛑 АНТИ-СПАМ ПРОВЕРКА (КРИТИЧНО)
        last_action = pos.get("ars_last_action")
        last_time_str = pos.get("ars_last_time")

        if last_action == decision and last_time_str:
            try:
                last_time = (
                    datetime.fromisoformat(last_time_str)
                    if "T" in last_time_str
                    else datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
                )
                # НЕ ШЛЕМ ЧАЩЕ ЧЕМ РАЗ В 4 ЧАСА ОДНО И ТО ЖЕ
                if (get_utc_now() - last_time) < timedelta(hours=4):
                    logger.info(
                        "🔕 [ARS] Уведомление по %s (%s) подавлено (анти-спам 4ч)", symbol, decision
                    )
                    return
            except Exception as e:
                logger.warning("⚠️ [ARS] Ошибка парсинга времени в анти-спаме: %s", e)

        # 💾 ЗАПИСЫВАЕМ В БД ПЕРЕД ОТПРАВКОЙ
        query = "UPDATE active_positions SET ars_last_action = ?, ars_last_time = ? WHERE id = ?"
        params = (decision, get_utc_now().strftime("%Y-%m-%d %H:%M:%S"), pos["id"])
        success = await self.adb.execute_with_retry(query, params, is_write=True)

        if success:
            logger.info("💾 [ARS] Состояние сохранено в БД для %s: %s", symbol, decision)
        else:
            logger.error("❌ [ARS] Ошибка сохранения состояния в БД")
            return  # Если не смогли записать, лучше не слать, иначе будет спам

        # 📨 ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ
        logger.info("🎯 [ARS] Исполнение решения по %s: %s", symbol, decision)
        await self.notify_user(user_id, symbol, decision, reason, pnl_pct)

    async def notify_user(
        self, user_id: int, symbol: str, decision: str, reason: str, pnl_pct: float
    ):
        """Отправляет уведомление в Telegram (через импорт бота внутри)"""
        try:
            from src.telegram.bot_core import bot_app

            message = (
                f"🛡️ *AUTONOMOUS RECOVERY SYSTEM*\n\n"
                f"Монета: `{symbol}`\n"
                f"Текущий PnL: `{pnl_pct:.2f}%`\n"
                f"Статус: *ЗАВИСЛА*\n\n"
                f"🎯 РЕШЕНИЕ: *{decision}*\n"
                f"💡 ОБОСНОВАНИЕ: _{reason}_\n\n"
                f"Система приступает к исполнению решения..."
            )

            await bot_app.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
        except Exception as e:
            logger.error("❌ [ARS] Ошибка отправки уведомления: %s", e)

    async def execute_recovery_action(self, user_id: int, pos: Dict, decision: str):
        """Здесь будет логика реального исполнения ордеров (Bitget API)"""
        # Пока только логируем
        logger.info("⚙️ [ARS] Выполнение экшена %s для %s", decision, pos["symbol"])
        pass


async def start_stuck_monitor():
    """Запускает мониторинг зависших позиций для всех пользователей"""
    from src.database.acceptance import AcceptanceDatabase

    adb = AcceptanceDatabase()

    monitor = StuckPositionMonitor(db_path=adb.db_path)

    # Получаем список пользователей из БД
    try:
        query = "SELECT DISTINCT user_id FROM active_positions WHERE status = 'open'"
        rows = await adb.execute_with_retry(query, (), is_write=False)
        user_ids = [row[0] for row in rows] if rows else []

        logger.info("🛡️ [ARS] Запуск мониторинга для %d пользователей", len(user_ids))

        # Запускаем мониторинг для каждого пользователя
        for user_id in user_ids:
            if user_id:
                asyncio.create_task(monitor.run_monitor(user_id))

    except Exception as e:
        logger.error("❌ [ARS] Ошибка запуска мониторинга: %s", e)

    # Периодически проверяем новых пользователей
    while True:
        try:
            await asyncio.sleep(300)  # Проверка каждые 5 минут
            query = "SELECT DISTINCT user_id FROM active_positions WHERE status = 'open'"
            rows = await adb.execute_with_retry(query, (), is_write=False)
            user_ids = [row[0] for row in rows] if rows else []

            # Запускаем мониторинг для новых пользователей
            for user_id in user_ids:
                if user_id and user_id not in monitor._local_history:
                    asyncio.create_task(monitor.run_monitor(user_id))
                    monitor._local_history[user_id] = True

        except Exception as e:
            logger.error("❌ [ARS] Ошибка в цикле мониторинга: %s", e)
            await asyncio.sleep(60)
