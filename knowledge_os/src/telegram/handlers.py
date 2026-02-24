#!/usr/bin/env python3
# pylint: disable=too-many-lines,invalid-name,wrong-import-position,import-outside-toplevel,line-too-long
# pylint: disable=missing-function-docstring,wrong-import-order,ungrouped-imports
"""
Обработчики команд Telegram для торгового бота ATRA
"""

import asyncio
import datetime as dt
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from config import TELEGRAM_TOKEN, TELEGRAM_TOKEN_DEV, TOKEN
from src.database.db import Database
from src.shared.utils.datetime_utils import get_utc_now
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

# Импорты с fallback для обратной совместимости
try:
    from src.telegram.messaging import (
        build_accept_message,
        build_dca_accept_message,
        build_full_close_message,
        build_partial_close_message,
    )
except ImportError:
    try:
        from src.telegram.messaging import (
            build_accept_message,
            build_dca_accept_message,
            build_full_close_message,
            build_partial_close_message,
        )
    except ImportError:
        # Stub функции
        def build_accept_message(*args, **kwargs):
            return ""

        def build_dca_accept_message(*args, **kwargs):
            return ""

        def build_full_close_message(*args, **kwargs):
            return ""

        def build_partial_close_message(*args, **kwargs):
            return ""


try:
    from src.utils.ohlc_utils import get_ohlc_binance_sync
except ImportError:
    try:
        from ohlc_utils import get_ohlc_binance_sync
    except ImportError:

        def get_ohlc_binance_sync(*args, **kwargs):
            return None


try:
    from src.telegram.utils import (
        CHAT_IDS,
        calculate_user_leverage,
        safe_format_price,
    )

    # Проверяем наличие других функций
    try:
        from src.telegram.utils import atomic_update_user_aggregate, profile
    except ImportError:

        def atomic_update_user_aggregate(*args, **kwargs):
            pass

        def profile(func):
            return func
except ImportError:
    try:
        from telegram_utils import (
            CHAT_IDS,
            atomic_update_user_aggregate,
            calculate_user_leverage,
            profile,
            safe_format_price,
        )
    except ImportError:
        # Fallback значения
        CHAT_IDS = []

        def atomic_update_user_aggregate(*args, **kwargs):
            pass

        def calculate_user_leverage(*args, **kwargs):
            return 1.0

        def profile(func):
            return func

        def safe_format_price(price, symbol=None):
            return f"{price:.5f}"


# Импорты системы принятия сигналов
from src.database.acceptance import AcceptanceDatabase

SIGNAL_ACCEPTANCE_AVAILABLE = True

# Глобальная переменная для системы принятия сигналов
signal_acceptance_manager = None

ROOT_DIR = Path(__file__).resolve().parent
REPORTS_DIR = ROOT_DIR / "data" / "reports"


def set_signal_acceptance_manager(manager):
    """Устанавливает менеджер принятия сигналов"""
    global signal_acceptance_manager
    signal_acceptance_manager = manager
    logging.info("✅ signal_acceptance_manager установлен: %s", manager)


# from exchange_api import get_ohlc_binance_sync  # Function not found, removed


# Rate limiter для предотвращения Flood control (без global statement)
async def rate_limit_api_call():
    """Ограничивает частоту запросов к Telegram API для предотвращения Flood control"""
    if not hasattr(rate_limit_api_call, "last_call"):
        rate_limit_api_call.last_call = 0  # type: ignore
        rate_limit_api_call.min_interval = 0.1  # type: ignore # 100ms

    current_time = time.time()
    time_since_last_call = current_time - rate_limit_api_call.last_call  # type: ignore
    min_interval = rate_limit_api_call.min_interval  # type: ignore

    if time_since_last_call < min_interval:
        await asyncio.sleep(min_interval - time_since_last_call)

    rate_limit_api_call.last_call = time.time()  # type: ignore


try:
    from src.utils.shared_utils import (
        calculate_unified_tp_for_symbol,
        clamp_new_risk,
        get_dynamic_tp_levels,
    )
except ImportError:
    try:
        from shared_utils import (
            calculate_unified_tp_for_symbol,
            clamp_new_risk,
            get_dynamic_tp_levels,
        )
    except ImportError:
        # Stub функции
        def get_dynamic_tp_levels(*args, **kwargs):
            return {}

        def calculate_unified_tp_for_symbol(*args, **kwargs):
            return (0, 0, 0)

        def clamp_new_risk(*args, **kwargs):
            return 1.0


try:
    from tools.backtest.backtrader_adapter import run_backtest_replay_db
except ImportError:
    try:
        from backtrader_adapter import run_backtest_replay_db
    except ImportError:

        def run_backtest_replay_db(*args, **kwargs):
            return None


# Singleton Database instance с lazy initialization для telegram_handlers
_db_telegram = None


def get_db_telegram():
    """Получает или создает экземпляр Database для telegram_handlers (singleton с lazy init)"""
    if not hasattr(get_db_telegram, "instance"):
        get_db_telegram.instance = Database()  # type: ignore
    return get_db_telegram.instance  # type: ignore


# Для обратной совместимости
class LazyDB:
    """Lazy proxy для Database с безопасной обработкой None"""

    def __getattr__(self, name):
        try:
            db_instance = get_db_telegram()
            if db_instance is None:
                logging.warning("⚠️ db_instance is None при вызове %s", name)

                # Возвращаем stub функцию, которая ничего не делает
                def stub(*args, **kwargs):
                    logging.warning("⚠️ Вызов stub для %s (db не инициализирован)", name)
                    return None

                return stub
            return getattr(db_instance, name)
        except Exception as e:
            logging.error("❌ Ошибка при получении атрибута %s из db: %s", name, e)

            # Возвращаем stub функцию
            def stub(*args, **kwargs):
                logging.warning("⚠️ Вызов stub для %s (ошибка: %s)", name, e)
                return None

            return stub


db = LazyDB()

# =============================================================================
# STATELESS SESSION MANAGER
# =============================================================================


class SessionManager:
    """
    Менеджер сессий для управления состоянием пользователей (stateless).

    Управляет pending_trades через явное состояние, заменяя модульную переменную.

    Example:
        ```python
        session_manager = SessionManager()
        trade = session_manager.get_pending_trade(user_id)
        session_manager.set_pending_trade(user_id, trade_data)
        ```
    """

    def __init__(self):
        """Initialize empty pending trades dictionary"""
        self._pending_trades: Dict[int, Dict[str, Any]] = {}

    def get_pending_trade(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get pending trade for user.

        Args:
            user_id: User ID

        Returns:
            Pending trade data or None
        """
        return self._pending_trades.get(user_id)

    def set_pending_trade(self, user_id: int, trade_data: Dict[str, Any]) -> None:
        """
        Set pending trade for user.

        Args:
            user_id: User ID
            trade_data: Trade data dictionary
        """
        self._pending_trades[user_id] = trade_data

    def remove_pending_trade(self, user_id: int) -> None:
        """
        Remove pending trade for user.

        Args:
            user_id: User ID
        """
        self._pending_trades.pop(user_id, None)

    def has_pending_trade(self, user_id: int) -> bool:
        """
        Check if user has pending trade.

        Args:
            user_id: User ID

        Returns:
            True if user has pending trade
        """
        return user_id in self._pending_trades

    def clear_all(self) -> None:
        """Clear all pending trades"""
        self._pending_trades.clear()

    def get_all_user_ids(self) -> list:
        """Get all user IDs with pending trades"""
        return list(self._pending_trades.keys())


# Singleton instance for application-wide session management
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    Get singleton session manager instance.

    Returns:
        SessionManager instance
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def reset_session_manager() -> None:
    """Reset session manager (useful for testing)"""
    global _session_manager
    _session_manager = None


# =============================================================================
# BACKWARD COMPATIBILITY: Legacy pending_trades access
# =============================================================================


class _PendingTradesProxy:
    """Dict-like proxy for backward compatibility with pending_trades"""

    def __getitem__(self, key):
        """Get pending trade for user"""
        manager = get_session_manager()
        trade = manager.get_pending_trade(key)
        if trade is None:
            raise KeyError(key)
        return trade

    def __setitem__(self, key, value):
        """Set pending trade for user"""
        manager = get_session_manager()
        manager.set_pending_trade(key, value)

    def __delitem__(self, key):
        """Remove pending trade for user"""
        manager = get_session_manager()
        manager.remove_pending_trade(key)

    def __contains__(self, key):
        """Check if user has pending trade"""
        manager = get_session_manager()
        return manager.has_pending_trade(key)

    def get(self, key, default=None):
        """Get pending trade with default"""
        manager = get_session_manager()
        return manager.get_pending_trade(key) or default

    def clear(self):
        """Clear all pending trades"""
        manager = get_session_manager()
        manager.clear_all()

    def keys(self):
        """Get all user IDs"""
        manager = get_session_manager()
        return manager.get_all_user_ids()


# Legacy module-level variable (for backward compatibility)
# ⚠️ DEPRECATED: Use get_session_manager() for new code
pending_trades = _PendingTradesProxy()


# Функция для тестирования парсинга callback_data
def test_callback_parsing():
    """Тестовая функция для проверки парсинга callback_data"""
    test_cases = [
        "accept|BTCUSDT|2401011200|45000.0000|0.0010|long|2.0|5.0",  # DCA сигнал
        "accept|BTCUSDT|2401011200|45000.0000|long|2.0|5.0",  # Обычный сигнал
        "accept|ETHUSDT|2401011200|3000.0000|short|1.5|3.0",  # Short сигнал
    ]

    for i, data in enumerate(test_cases):
        print(f"\nТест {i + 1}: {data}")

        if "|" in data:
            parts = data.split("|")
            print(f"  Количество параметров: {len(parts)}")

            if len(parts) >= 7:
                symbol = parts[1]
                entry_price = float(parts[3])
                side = parts[5]
                risk_pct = float(parts[6])

                # Переменные для совместимости с реальным кодом
                _ = symbol  # symbol используется в тестах
                _ = entry_price  # entry_price используется в тестах
                _ = side  # side используется в тестах
                _ = risk_pct  # risk_pct используется в тестах

                if len(parts) >= 8:
                    qty = float(parts[4])
                    leverage = float(parts[7])
                    tp_price = entry_price * 1.02
                    is_dca = True
                    print(
                        f"  DCA сигнал: {symbol} {side} цена={entry_price} qty={qty} leverage={leverage}"
                    )

                    # Используем переменные для устранения предупреждений
                    _ = qty
                    _ = leverage
                    _ = tp_price
                    _ = is_dca
                else:
                    qty = 0
                    leverage = float(parts[6]) if len(parts) > 6 else 1.0
                    tp_price = entry_price * (1.02 if side == "long" else 0.98)
                    is_dca = False
                    print(
                        f"  Обычный сигнал: {symbol} {side} цена={entry_price} leverage={leverage}"
                    )

                    # Используем переменные для устранения предупреждений
                    _ = qty
                    _ = leverage
                    _ = tp_price
                    _ = is_dca
            else:
                print("  ❌ Неверный формат данных")


# Раскомментируйте для тестирования:
# test_callback_parsing()


# Функция для тестирования обработки кнопок
def test_button_logic():
    """Тестовая функция для проверки логики обработки кнопок"""
    # Реальные кнопки из кода
    real_buttons = [
        "accept|BTCUSDT|2401011200|45000.0000|0.0010|long|2.0|5.0",  # DCA сигнал
        "accept|BTCUSDT|2401011200|45000.0000|long|2.0|5.0",  # Обычный сигнал
        "setup_trade_mode_spot",
        "setup_trade_mode_futures",
        "setup_filter_mode_strict",
        "setup_filter_mode_soft",
    ]

    # Подготовленные, но неиспользуемые кнопки
    prepared_buttons = ["close_BTCUSDT", "dca_BTCUSDT_45000.0_46000.0_long_1", "confirm_close_all"]

    # Неизвестные кнопки
    unknown_buttons = ["unknown_button_data", "some_random_callback"]

    test_cases = real_buttons + prepared_buttons + unknown_buttons

    print("\n🧪 Тестирование логики обработки кнопок:")
    print("=" * 50)
    print("📊 Реальные кнопки (используются):")
    print("   ✅ accept|... - кнопки принятия сигналов (LONG/SHORT/DCA)")
    print("   ✅ setup_... - кнопки настройки бота")
    print("📋 Подготовленные кнопки (готовы, но не используются):")
    print("   🔒 close_... - закрытие позиций")
    print("   📈 dca_... - добавление к DCA")
    print("   ✔️ confirm_... - подтверждение действий")
    print()

    for i, data in enumerate(test_cases, 1):
        print(f"\nТест {i}: '{data}'")

        if data.startswith("accept_") or data.startswith("accept|"):
            print("  ✅ Маршрутизируется в: handle_accept_button")
        elif data.startswith("close_"):
            print("  🔒 Маршрутизируется в: handle_close_button")
        elif data.startswith("dca_"):
            print("  📈 Маршрутизируется в: handle_dca_button")
        elif data.startswith("confirm_"):
            print("  ✔️ Маршрутизируется в: handle_confirm_button")
        elif data.startswith("setup_"):
            print("  🔧 Маршрутизируется в: handle_setup_button")
        else:
            print("  ❌ Неизвестная кнопка!")

        # Проверяем формат accept сигналов
        if data.startswith("accept|") or data.startswith("accept_"):
            parts = data.split("|") if "|" in data else data.split("_")
            print(f"  📊 Количество параметров: {len(parts)}")
            if len(parts) >= 7:
                print("  ✅ Формат корректный")
            else:
                print("  ❌ Недостаточно параметров")


# Раскомментируйте для тестирования:
# test_button_logic()


async def get_market_cap_data(symbol):
    """
    Делегирует получение капы/объема в общий сервис из signal_live.
    """
    try:
        # Импортируем из общего места, чтобы не дублировать логику
        from signal_live import get_market_cap_data as _shared_mcap

        return await _shared_mcap(symbol)
    except (ImportError, RuntimeError, ValueError, TypeError) as e:
        logging.warning(
            "[Anomaly] Ошибка общего сервиса cap/volume для %s: %s", symbol, e, exc_info=True
        )
        return None


async def perf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /perf [days] — сводка эффективности по БД."""
    try:
        args = context.args if hasattr(context, "args") else []
        days = int(args[0]) if args and args[0].isdigit() else 7
        summary = db.get_performance_summary(days)
        text = (
            f"📊 <b>PERF (за {summary['since_days']} дн.)</b>\n\n"
            f"Всего событий: <code>{summary['total_events']}</code>\n"
            f"Уникальных позиций: <code>{summary['distinct_positions']}</code>\n"
            f"TP2: <code>{summary['tp2_count']}</code> | TP1(partial): <code>{summary['tp1_partial_count']}</code> | SL: <code>{summary['sl_count']}</code>\n"
            f"Σ PnL: <code>{summary['net_profit_sum']:.2f}</code> | Avg PnL: <code>{summary['net_profit_avg']:.2f}</code>\n\n"
            f"Последние события:\n"
        )
        for item in summary.get("recent", []) or []:
            np = item["net_profit"]
            np_str = f"{np:.2f}" if isinstance(np, (int, float)) else "—"
            text += f"• {item['symbol']}: {item['result']} | PnL={np_str} | {item['created_at']}\n"
        await update.message.reply_text(text, parse_mode="HTML")
    except (RuntimeError, ValueError, TypeError, KeyError) as e:
        logging.error("/perf error: %s", e)
        await update.message.reply_text("❌ Ошибка при формировании сводки")


async def portfolio(update: Update, _: ContextTypes.DEFAULT_TYPE):  # noqa: ARG001
    """Команда /portfolio — краткая сводка портфеля пользователя."""
    try:
        user_id = update.effective_user.id
        data = db.get_user_data(user_id) or {}
        positions = data.get("positions", []) or []
        trade_mode = data.get("trade_mode", "spot")
        leverage = int(data.get("leverage", 1)) if trade_mode == "futures" else 1
        deposit = float(data.get("deposit", 0) or 0)
        free_deposit = float(data.get("free_deposit", deposit) or deposit)
        balance = float(data.get("balance", deposit) or deposit)

        # Агрегируем открытые позиции по symbol (все DCA по монете = одна позиция)
        open_positions = []
        grouped = {}
        for p in positions or []:
            try:
                if p.get("status", "open") != "open":
                    continue
                qty = float(p.get("qty", 0) or 0)
            except (TypeError, ValueError):
                qty = 0.0
            if qty <= 0:
                continue
            sym = p.get("symbol")
            side = (p.get("side") or "long").upper()
            if not sym:
                continue
            key = sym
            if key not in grouped:
                grouped[key] = {
                    "symbol": sym,
                    "qty": 0.0,
                    "side_counts": {"LONG": 0.0, "SHORT": 0.0},
                }
            grouped[key]["qty"] += qty
            grouped[key]["side_counts"][side] = grouped[key]["side_counts"].get(side, 0.0) + qty
        # Формируем список позиций: одна на символ, сторона — доминирующая по qty
        open_positions = []
        for sym, agg in grouped.items():
            dom_side = (
                "LONG"
                if agg["side_counts"].get("LONG", 0.0) >= agg["side_counts"].get("SHORT", 0.0)
                else "SHORT"
            )
            open_positions.append({"symbol": sym, "side": dom_side, "qty": agg["qty"]})
        symbols = [f"{p['symbol']}:{p['side']}" for p in open_positions]
        notional_sum = 0.0
        risk_sum_pct = 0.0
        for p in open_positions:
            try:
                qty = float(p.get("qty", 0) or 0)
                # entry_price может быть у отдельных лотов; для суммарной маржи применим усреднённую из исходных позиций
                entry_price = 0.0
                try:
                    # вычислим среднюю цену по символу из исходных позиций
                    cost = 0.0
                    qty_sum = 0.0
                    for lp in positions or []:
                        if lp.get("status", "open") != "open" or lp.get("symbol") != p.get(
                            "symbol"
                        ):
                            continue
                        q = float(lp.get("qty", 0) or 0)
                        ep = float(lp.get("entry_price", 0) or 0)
                        cost += q * ep
                        qty_sum += q
                    entry_price = (cost / qty_sum) if qty_sum > 0 else 0.0
                except (TypeError, ValueError):
                    entry_price = 0.0
                notional = qty * entry_price
                notional_sum += notional
                risk_pct = float(p.get("risk_pct", 0) or 0)
                risk_sum_pct += risk_pct
            except (ValueError, TypeError):
                continue

        used_margin = notional_sum if trade_mode == "spot" else (notional_sum / max(1, leverage))
        mode_display = "FUTURES" if trade_mode == "futures" else "SPOT"

        # Формируем текст
        lines = [
            "📊 <b>ПОРТФЕЛЬ</b>",
            f"Режим: <code>{mode_display}</code> | Плечо: <code>x{leverage}</code>",
            f"Баланс: <code>{balance:.2f}</code> | Свободно: <code>{free_deposit:.2f}</code>",
            f"Использовано (нот.): <code>{notional_sum:.2f}</code> | Маржа: <code>{used_margin:.2f}</code>",
            f"Открыто позиций: <code>{len(open_positions)}</code>",
        ]
        if symbols:
            lines.append("Активы: " + ", ".join(symbols))
        # Риск портфеля (сумма risk_pct по позициям)
        lines.append(f"Суммарный риск (∑): <code>{risk_sum_pct:.2f}%</code>")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except (RuntimeError, ValueError, TypeError, KeyError) as e:
        logging.error("/portfolio error: %s", e)
        await update.message.reply_text("❌ Ошибка при формировании портфеля")


async def sentiment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /sentiment <SYMBOL> — рыночный сентимент по монете."""
    try:
        args = context.args if hasattr(context, "args") else []
        if not args:
            await update.message.reply_text("Укажите символ: /sentiment BTCUSDT")
            return
        symbol = args[0].upper()
        # get_market_sentiment временно недоступен - заглушка
        try:
            from signal_live import get_market_sentiment

            s = await get_market_sentiment(symbol)
        except (ImportError, AttributeError):
            await update.message.reply_text(f"⚠️ Сентимент для {symbol} временно недоступен")
            return
        score = s.get("score", 0.0)
        label = s.get("label", "Нейтрально")
        fgi = s.get("fgi")
        src = s.get("source", "unknown")
        fgi_part = f"FGI: <code>{fgi}</code>" if isinstance(fgi, int) else "FGI: —"
        text = (
            f"🧭 <b>СЕНТИМЕНТ {symbol}</b>\n\n"
            f"Оценка: <code>{score:+.2f}</code> — {label}\n"
            f"Источник: <code>{src}</code>\n"
            f"{fgi_part}"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as e:
        logging.error("/sentiment error: %s", e)
        await update.message.reply_text("❌ Ошибка при расчёте сентимента")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        logging.info("🔔 [COMMAND] /start вызван пользователем %s", update.effective_user.id)
        user_id = update.effective_user.id
        user_data = context.user_data
        # Гарантируем наличие записи пользователя в БД при первом контакте
        try:
            # Проверяем, что db инициализирован
            if db is None or not hasattr(db, "get_user_data"):
                logging.warning(
                    "⚠️ db не инициализирован в start, используем только context.user_data"
                )
                latest = None
            else:
                latest = db.get_user_data(user_id)
            if not latest:
                defaults = {
                    "deposit": 0.0,
                    "balance": 0.0,
                    "free_deposit": 0.0,
                    "risk_pct": 2.0,
                    "trade_mode": "spot",
                    "filter_mode": "soft",
                    "leverage": 1,
                    "setup_completed": False,
                }
                try:
                    try:
                        from src.utils.user_utils import save_user_data_for_signals
                    except ImportError:
                        try:
                            from user_utils import save_user_data_for_signals
                        except ImportError:

                            def save_user_data_for_signals(*args, **kwargs):
                                pass

                    save_user_data_for_signals({str(user_id): defaults})
                except (RuntimeError, ValueError, TypeError):
                    pass
                user_data.update(defaults)
        except (RuntimeError, ValueError, TypeError):
            pass

        # Если настройка уже была завершена ранее — показываем текущие настройки с возможностью изменить
        if user_data.get("setup_completed") and all(
            k in user_data for k in ("deposit", "trade_mode", "filter_mode")
        ):
            trade_mode_display = "SPOT" if user_data.get("trade_mode") == "spot" else "FUTURES"
            filter_display = "Строгий" if user_data.get("filter_mode") == "strict" else "Мягкий"

            # Добавляем кнопку для повторной настройки
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔄 Изменить настройки", callback_data="restart_setup")]]
            )

            text = (
                f"✅ <b>Ваши текущие настройки:</b>\n\n"
                f"💰 Депозит: <code>{user_data.get('deposit', 0)}</code> USDT\n"
                f"📈 Режим торговли: <code>{trade_mode_display}</code>\n"
                f"🎯 Режим фильтров: <code>{filter_display}</code>\n\n"
                f"💡 Используйте кнопку ниже для изменения настроек\n"
                f"Или команды: /set_trade_mode, /set_filter_mode, /set_balance\n"
            )
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
            return

        # Если настройка ещё не завершена — запускаем пошаговый мастер
        if "setup_step" not in user_data:
            user_data["setup_step"] = "deposit"

        # Проверяем, нужно ли пройти настройку
        if "deposit" not in user_data or user_data.get("setup_step") == "deposit":
            # Шаг 1: Запрашиваем депозит
            await update.message.reply_text(
                "🚀 <b>ДОБРО ПОЖАЛОВАТЬ В ТОРГОВЫЙ БОТ!</b>\n\n"
                "Для начала работы нужно настроить основные параметры.\n\n"
                "💰 <b>Шаг 1: Установите начальный депозит</b>\n"
                "Введите сумму в USDT (например: 1000):",
                parse_mode="HTML",
            )
            user_data["setup_step"] = "deposit"
            # Сохраняем данные пользователя
            try:
                if db and hasattr(db, "save_user_data"):
                    db.save_user_data(user_id, user_data)
            except Exception as e:
                logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)
            return

        if "trade_mode" not in user_data or user_data.get("setup_step") == "trade_mode":
            # Шаг 2: Запрашиваем режим торговли

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("💵 SPOT", callback_data="setup_trade_mode_spot"),
                        InlineKeyboardButton(
                            "⚡ FUTURES", callback_data="setup_trade_mode_futures"
                        ),
                    ]
                ]
            )

            await update.message.reply_text(
                "💰 <b>Шаг 2: Выберите режим торговли</b>\n\n"
                "💵 <b>SPOT</b> — торговля без плеча (только LONG сигналы)\n"
                "⚡ <b>FUTURES</b> — торговля с плечом (LONG + SHORT сигналы)\n\n"
                "⚠️ <i>Рекомендуется FUTURES для полного использования стратегий</i>\n\n"
                "Выберите режим:",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            user_data["setup_step"] = "trade_mode"
            # Сохраняем данные пользователя
            try:
                if db and hasattr(db, "save_user_data"):
                    db.save_user_data(user_id, user_data)
            except Exception as e:
                logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)
            return

        if "filter_mode" not in user_data or user_data.get("setup_step") == "filter_mode":
            # Шаг 3: Запрашиваем режим фильтров

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔴 Строгий", callback_data="setup_filter_mode_strict"
                        ),
                        InlineKeyboardButton("🟢 Мягкий", callback_data="setup_filter_mode_soft"),
                    ]
                ]
            )

            await update.message.reply_text(
                "🎯 <b>Шаг 3: Выберите режим фильтров</b>\n\n"
                "🔴 <b>Строгий</b> — меньше сигналов, но качественные\n"
                "🟢 <b>Мягкий</b> — больше сигналов, более активная торговля\n\n"
                "Выберите режим:",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            user_data["setup_step"] = "filter_mode"
            # Сохраняем данные пользователя
            try:
                if db and hasattr(db, "save_user_data"):
                    db.save_user_data(user_id, user_data)
            except Exception as e:
                logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)
            return

        # Все настройки завершены
        deposit = user_data.get("deposit", 0)
        trade_mode = user_data.get("trade_mode", "spot")
        filter_mode = user_data.get("filter_mode", "strict")

        # Устанавливаем значения по умолчанию
        if "risk_pct" not in user_data:
            user_data["risk_pct"] = 2.0
        if "leverage" not in user_data:
            user_data["leverage"] = 1
        if "news_filter_mode" not in user_data:
            user_data["news_filter_mode"] = "conservative"

        # Удаляем флаг настройки и фиксируем завершение навсегда
        if "setup_step" in user_data:
            del user_data["setup_step"]
        user_data["setup_completed"] = True

        # Сохраняем данные пользователя
        try:
            if db and hasattr(db, "save_user_data"):
                db.save_user_data(user_id, user_data)
        except Exception as e:
            logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)

        # Приветственное сообщение
        trade_mode_display = "SPOT" if trade_mode == "spot" else "FUTURES"
        filter_display = "Строгий" if filter_mode == "strict" else "Мягкий"

        welcome_text = (
            "✅ <b>НАСТРОЙКА ЗАВЕРШЕНА!</b>\n\n"
            f"💰 Депозит: <code>{deposit}</code> USDT\n"
            f"📈 Режим: <code>{trade_mode_display}</code>\n"
            f"🎯 Фильтры: <code>{filter_display}</code>\n\n"
            "🚀 <b>Бот готов к работе!</b>\n\n"
            "📋 Основные команды:\n"
            "• /balance — ваш баланс\n"
            "• /positions — открытые позиции\n"
            "• /help — все команды\n\n"
            "⚠️ Риск и плечо рассчитываются автоматически\n"
            "📡 Сигналы будут приходить автоматически\n"
        )

        await update.message.reply_text(welcome_text, parse_mode="HTML")

    except TelegramError as e:
        logging.error("Telegram API ошибка в start: %s", e)
        await update.message.reply_text("❌ Ошибка при запуске бота")
    except (OSError, KeyError, ValueError, AttributeError, TypeError) as e:
        logging.error("Ошибка данных в start: %s", e, exc_info=True)
        try:
            await update.message.reply_text("❌ Ошибка при запуске бота")
        except (TelegramError, BadRequest, RuntimeError):
            # Игнорируем ошибки отправки сообщений об ошибках
            pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    logging.info(
        "📩 Получено сообщение от пользователя %s: %s",
        update.effective_user.id,
        update.message.text if update.message else "None",
    )
    try:
        user_id = update.effective_user.id
        message_text = update.message.text
        user_data = context.user_data
        pending_feedback = user_data.get("pending_feedback")

        if pending_feedback and not message_text.startswith("/"):
            comment = (message_text or "").strip()
            if not comment:
                await update.message.reply_text(
                    "✏️ Введите текст комментария или нажмите кнопку снова."
                )
                return

            if not SIGNAL_ACCEPTANCE_AVAILABLE:
                logging.error("❌ AcceptanceDatabase недоступна для сохранения комментария")
                await update.message.reply_text(
                    "❌ Не удалось сохранить комментарий (БД недоступна)."
                )
                return

            adb = AcceptanceDatabase()
            await adb.record_feedback(
                signal_key=pending_feedback.get("signal_key"),
                symbol=pending_feedback.get("symbol", "N/A"),
                direction=pending_feedback.get("direction"),
                user_id=int(user_id),
                chat_id=pending_feedback.get("chat_id"),
                message_id=pending_feedback.get("message_id"),
                feedback_type="comment",
                comment=comment[:600],
                metadata={"source": "comment", "received_at": get_utc_now().isoformat()},
            )
            user_data.pop("pending_feedback", None)
            await update.message.reply_text("✅ Комментарий сохранён. Спасибо!", parse_mode="HTML")
            return

        # Если пользователя нет в БД, создаём запись с дефолтами (для активации команд)
        try:
            # Проверяем, что db инициализирован
            if db is None or not hasattr(db, "get_user_data"):
                logging.warning(
                    "⚠️ db не инициализирован в handle_message, используем только context.user_data"
                )
                latest = None
            else:
                latest = db.get_user_data(user_id)
            if not latest:
                defaults = {
                    "deposit": 0.0,
                    "balance": 0.0,
                    "free_deposit": 0.0,
                    "risk_pct": 2.0,
                    "trade_mode": "spot",
                    "filter_mode": "soft",
                    "leverage": 1,
                    "setup_completed": False,
                }
                try:
                    from src.utils.user_utils import save_user_data_for_signals
                except ImportError:
                    try:
                        from user_utils import save_user_data_for_signals
                    except ImportError:

                        def save_user_data_for_signals(*args, **kwargs):
                            pass

                save_user_data_for_signals({str(user_id): defaults})
                user_data.update(defaults)
        except (RuntimeError, ValueError, TypeError):
            pass

        # Проверяем, является ли сообщение командой
        if message_text.startswith("/"):
            return

        # Обрабатываем ввод депозита во время настройки
        if user_data.get("setup_step") == "deposit":
            try:
                deposit = float(message_text)
                if deposit <= 0:
                    await update.message.reply_text(
                        "❌ Депозит должен быть больше 0. Попробуйте снова:"
                    )
                    return

                # Сохраняем депозит
                user_data["deposit"] = deposit
                user_data["balance"] = deposit
                user_data["free_deposit"] = deposit
                user_data["setup_step"] = "trade_mode"

                # Сохраняем данные пользователя
                try:
                    if db and hasattr(db, "save_user_data"):
                        db.save_user_data(user_id, user_data)
                except Exception as e:
                    logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)

                # Переходим к выбору режима торговли
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("💵 SPOT", callback_data="setup_trade_mode_spot"),
                            InlineKeyboardButton(
                                "⚡ FUTURES", callback_data="setup_trade_mode_futures"
                            ),
                        ]
                    ]
                )

                await update.message.reply_text(
                    f"✅ <b>Депозит установлен: {deposit} USDT</b>\n\n"
                    "💰 <b>Шаг 2: Выберите режим торговли</b>\n\n"
                    "💵 <b>SPOT</b> — торговля без плеча (только LONG сигналы)\n"
                    "⚡ <b>FUTURES</b> — торговля с плечом (LONG + SHORT сигналы)\n\n"
                    "⚠️ <i>Рекомендуется FUTURES для полного использования стратегий</i>\n\n"
                    "Выберите режим:",
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                return

            except ValueError:
                await update.message.reply_text(
                    "❌ Введите корректную сумму (например: 1000). Попробуйте снова:"
                )
                return

        # Обрабатываем обычные сообщения
        if message_text.lower().startswith("connect_bitget"):
            await update.message.reply_text(
                "💡 Пожалуйста, используйте команду со слэшем: <code>/connect_bitget</code>",
                parse_mode="HTML",
            )
            return

        if message_text.lower() in ["привет", "hello", "hi"]:
            await update.message.reply_text("👋 Привет! Используйте /help для справки по командам.")
        elif message_text.lower() in ["статус", "status"]:
            await update.message.reply_text("🔧 Используйте /status для проверки статуса системы.")
        elif message_text.lower() in ["баланс", "balance"]:
            await update.message.reply_text("💰 Используйте /balance для просмотра баланса.")
        else:
            await update.message.reply_text(
                "💡 Используйте /help для справки по доступным командам."
            )

    except TelegramError as e:
        logging.error("Telegram API ошибка в handle_message: %s", e)
        await update.message.reply_text("❌ Ошибка при обработке сообщения")
    except (OSError, KeyError, ValueError, AttributeError) as e:
        logging.error("Ошибка данных в handle_message: %s", e, exc_info=True)
        try:
            await update.message.reply_text("❌ Ошибка при обработке сообщения")
        except (TelegramError, BadRequest, RuntimeError):
            # Игнорируем ошибки отправки сообщений об ошибках
            pass


async def notify_user(user_id, text, **kwargs):
    """Отправляет уведомление пользователю с таймаутом и ретраем (упрощённо).

    Спец-параметры:
    - _timeout: таймаут первой попытки
    - _return_message: если True — вернуть словарь {chat_id, message_id} при успехе
    - _send_to_both_bots: если True — отправляет в оба бота (DEV и PROD)
    """
    # 🆕 Проверяем, нужно ли отправлять в оба бота
    send_to_both = kwargs.pop("_send_to_both_bots", False)

    # Всегда используем HTML parse_mode, если не указан явно другой
    # HTML формат скрывает теги, но значения в <code> копируются при нажатии
    if "parse_mode" not in kwargs:
        kwargs["parse_mode"] = "HTML"

    timeout_seconds = kwargs.pop("_timeout", 5)
    return_message = bool(kwargs.pop("_return_message", False))
    log_ctx = f"notify_user(uid={user_id})"
    logging.info("%s: start", log_ctx)

    # Проверяем размер сообщения
    message_size = len(str(text).encode("utf-8"))
    if message_size > 2000:  # Лимит 2000 байт для безопасности
        logging.warning("%s: Message too large (%d bytes), truncating", log_ctx, message_size)
        text = str(text)[:1500] + "... [сообщение сокращено]"

    # 🆕 Если нужно отправить в оба бота - проверяем доступность и отправляем в работающие
    if send_to_both and (TELEGRAM_TOKEN or TELEGRAM_TOKEN_DEV):
        logging.info("%s: Проверка доступности ботов (PROD и DEV)", log_ctx)
        results = {}

        # 🆕 Проверяем доступность PROD бота
        prod_bot_available = False
        if TELEGRAM_TOKEN:
            try:
                bot_prod_check = Bot(token=TELEGRAM_TOKEN)
                await asyncio.wait_for(bot_prod_check.get_me(), timeout=2.0)
                prod_bot_available = True
                logging.debug("%s: PROD бот доступен", log_ctx)
            except Exception as e:
                logging.info("%s: PROD бот недоступен (%s) - пропускаем", log_ctx, str(e)[:50])
                results["prod"] = False

        # 🆕 Проверяем доступность DEV бота
        dev_bot_available = False
        if TELEGRAM_TOKEN_DEV:
            try:
                bot_dev_check = Bot(token=TELEGRAM_TOKEN_DEV)
                await asyncio.wait_for(bot_dev_check.get_me(), timeout=2.0)
                dev_bot_available = True
                logging.debug("%s: DEV бот доступен", log_ctx)
            except Exception as e:
                logging.info("%s: DEV бот недоступен (%s) - пропускаем", log_ctx, str(e)[:50])
                results["dev"] = False

        # 🆕 Отправляем только в работающие боты
        if prod_bot_available:
            try:
                bot_prod = Bot(token=TELEGRAM_TOKEN)
                msg_prod = await asyncio.wait_for(
                    bot_prod.send_message(chat_id=user_id, text=text, **kwargs),
                    timeout=timeout_seconds,
                )
                results["prod"] = {
                    "chat_id": int(user_id),
                    "message_id": int(getattr(msg_prod, "message_id", 0)),
                }
                logging.info("%s: PROD бот: успешно отправлено", log_ctx)
            except Exception as e:
                logging.error("%s: PROD бот: ошибка при отправке: %s", log_ctx, e)
                results["prod"] = False

        if dev_bot_available:
            # Небольшая задержка между отправками
            await asyncio.sleep(0.5)
            try:
                bot_dev = Bot(token=TELEGRAM_TOKEN_DEV)
                msg_dev = await asyncio.wait_for(
                    bot_dev.send_message(chat_id=user_id, text=text, **kwargs),
                    timeout=timeout_seconds,
                )
                results["dev"] = {
                    "chat_id": int(user_id),
                    "message_id": int(getattr(msg_dev, "message_id", 0)),
                }
                logging.info("%s: DEV бот: успешно отправлено", log_ctx)
            except Exception as e:
                logging.error("%s: DEV бот: ошибка при отправке: %s", log_ctx, e)
                results["dev"] = False

        # 🆕 Возвращаем результат первого успешного бота (приоритет PROD, затем DEV)
        if return_message:
            if results.get("prod"):
                return results["prod"]
            elif results.get("dev"):
                return results["dev"]
            else:
                return {"chat_id": int(user_id), "message_id": 0}
        # Успех определяется наличием хотя бы одного успешного бота
        return bool(results.get("prod", False) or results.get("dev", False))

    # ИСПРАВЛЕНО: Увеличиваем задержку для предотвращения Flood Control
    await asyncio.sleep(5.0)  # 5 секунд задержки между сообщениями

    try:
        bot = Bot(token=TOKEN)
        # Основная попытка с таймаутом
        msg = await asyncio.wait_for(
            bot.send_message(chat_id=user_id, text=text, **kwargs),
            timeout=timeout_seconds,
        )
        logging.info("%s: success (first try)", log_ctx)
        return (
            {"chat_id": int(user_id), "message_id": int(getattr(msg, "message_id", 0))}
            if return_message
            else True
        )
    except asyncio.TimeoutError:
        logging.warning("%s: timeout after %ss, retrying simplified", log_ctx, timeout_seconds)
    except TelegramError as e:
        logging.error("%s: Telegram API error on first try: %s", log_ctx, e)
        # ИСПРАВЛЕНО: Улучшенная обработка Flood Control
        if "Flood control" in str(e):
            logging.error("%s: Flood control detected - extracting retry time", log_ctx)

            # Извлекаем время ожидания из ошибки
            try:
                import re

                retry_match = re.search(r"retry after (\d+)", str(e).lower())
                if retry_match:
                    retry_seconds = int(retry_match.group(1))
                    logging.info("%s: Flood control: waiting %d seconds", log_ctx, retry_seconds)
                    await asyncio.sleep(min(retry_seconds, 600))  # Максимум 10 минут
                else:
                    # Стандартная задержка при flood control
                    await asyncio.sleep(60)
            except (ValueError, AttributeError):
                await asyncio.sleep(60)

            return False
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logging.error("%s: Data error on first try: %s", log_ctx, e)

    # Ретрай: сохраняем клавиатуру и HTML, чтобы таймер мог обновлять кнопку
    try:
        bot = Bot(token=TOKEN)
        # Разрешаем только безопасные параметры во второй попытке
        fallback_kwargs = {}
        if "reply_markup" in kwargs:
            fallback_kwargs["reply_markup"] = kwargs.get("reply_markup")
        if "parse_mode" in kwargs:
            fallback_kwargs["parse_mode"] = kwargs.get("parse_mode")
        msg = await asyncio.wait_for(
            bot.send_message(chat_id=user_id, text=str(text), **fallback_kwargs),
            timeout=3,
        )
        logging.info("%s: success (fallback)", log_ctx)
        return (
            {"chat_id": int(user_id), "message_id": int(getattr(msg, "message_id", 0))}
            if return_message
            else True
        )
    except (
        asyncio.TimeoutError,
        TelegramError,
        KeyError,
        ValueError,
        AttributeError,
        TypeError,
    ) as e:
        logging.error("%s: fallback failed: %s", log_ctx, e)
        return False
    finally:
        logging.info("%s: finish", log_ctx)


async def remove_reply_markup(chat_id: int, message_id: int) -> bool:
    """Удаляет клавиатуру у сообщения (делает кнопку недоступной)."""
    try:
        # Rate limiting для предотвращения Flood control
        await rate_limit_api_call()
        bot = Bot(token=TOKEN)
        await asyncio.wait_for(
            bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=None
            ),
            timeout=5,
        )
        return True
    except (asyncio.TimeoutError, TelegramError, KeyError, ValueError, AttributeError, TypeError):
        return False


async def start_accept_button_ttl(
    chat_id: int, message_id: int, expiry_iso: str, callback_data: str
) -> None:
    """Запускает TTL кнопку с фиксированным временем окончания.

    Показывает время окончания в формате "ПРИНЯТЬ ДО 12:43".
    По истечении времени автоматически удаляет кнопку.
    """
    # Некорректные входные данные — ничего не делаем
    if not chat_id or not message_id or message_id <= 0 or not expiry_iso or not callback_data:
        return

    try:
        expiry_dt = dt.datetime.fromisoformat(str(expiry_iso))
    except (ValueError, TypeError):
        # Если не удалось распарсить время истечения — не запускаем таймер
        return

    # Форматируем время окончания в формате ЧЧ:ММ
    expiry_time_str = expiry_dt.strftime("%H:%M")
    initial_label = f"ПРИНЯТЬ ДО {expiry_time_str}"

    # Создаем начальную кнопку с фиксированным временем
    try:
        await rate_limit_api_call()
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(initial_label, callback_data=callback_data)]]
        )
        bot = Bot(token=TOKEN)
        await asyncio.wait_for(
            bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=markup
            ),
            timeout=5,
        )
    except (asyncio.TimeoutError, RuntimeError, OSError, ValueError) as e:
        logging.warning("Ошибка создания TTL кнопки: %s", e)
        return

    # Ждем до истечения времени
    while True:
        # Синхронизируем осведомлённость о таймзоне
        if expiry_dt.tzinfo is not None and expiry_dt.tzinfo.utcoffset(expiry_dt) is not None:
            # Используем UTC время с timezone для сравнения
            now = get_utc_now().replace(tzinfo=expiry_dt.tzinfo)
        else:
            now = get_utc_now()

        remain = (expiry_dt - now).total_seconds()
        if remain <= 0:
            # Срок истёк — убираем клавиатуру
            await remove_reply_markup(chat_id, message_id)
            return

        # Проверяем каждые 60 секунд, чтобы не перегружать API
        await asyncio.sleep(60)


async def start_accept_button_countdown(
    chat_id: int, message_id: int, expiry_iso: str, callback_data: str, _step_seconds: int = 5
) -> None:
    """Запускает обратный отсчёт на кнопке "Принять" до истечения TTL.

    Периодически обновляет текст кнопки вида "Принять (ММ:СС)".
    По истечении времени удаляет клавиатуру.
    """
    # Некорректные входные данные — ничего не делаем
    if not chat_id or not message_id or message_id <= 0 or not expiry_iso or not callback_data:
        return
    try:
        expiry_dt = dt.datetime.fromisoformat(str(expiry_iso))
    except (ValueError, TypeError):
        # Если не удалось распарсить время истечения — не запускаем таймер
        return

    def _fmt(seconds: int) -> str:
        seconds = max(0, int(seconds))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}"
        else:
            return f"{m:02d}:{s:02d}"

    last_label = None
    while True:
        # Синхронизируем осведомлённость о таймзоне: если expiry_dt aware — берём now в той же tz
        if expiry_dt.tzinfo is not None and expiry_dt.tzinfo.utcoffset(expiry_dt) is not None:
            # Используем UTC время с timezone для сравнения
            now = get_utc_now().replace(tzinfo=expiry_dt.tzinfo)
        else:
            now = get_utc_now()
        remain = (expiry_dt - now).total_seconds()
        if remain <= 0:
            # Срок истёк — убираем клавиатуру
            await remove_reply_markup(chat_id, message_id)
            return

        # Формируем новую клавиатуру с обновлённой меткой (тот же формат, что при отправке)
        label = f"Принять ({_fmt(remain)})"
        if label != last_label:
            try:
                # Rate limiting для предотвращения Flood control
                await rate_limit_api_call()
                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(label, callback_data=callback_data)]]
                )
                bot = Bot(token=TOKEN)
                await asyncio.wait_for(
                    bot.edit_message_reply_markup(
                        chat_id=chat_id, message_id=message_id, reply_markup=markup
                    ),
                    timeout=5,
                )
                last_label = label
            except (
                asyncio.TimeoutError,
                TelegramError,
                KeyError,
                ValueError,
                AttributeError,
                TypeError,
            ):
                # Продолжаем попытки до истечения TTL, не выходим
                pass

        # Спим до следующего обновления, но не дольше оставшегося времени
        # Оптимизированный таймер для предотвращения Flood control: реже обновляем кнопки
        if remain > 300:  # > 5 минут
            sleep_for = 30  # Каждые 30 секунд
        elif remain > 60:  # 1-5 минут
            sleep_for = 15  # Каждые 15 секунд
        else:  # < 1 минуты
            sleep_for = 10  # Каждые 10 секунд (не каждую секунду!)
        try:
            await asyncio.sleep(sleep_for)
        except asyncio.CancelledError:
            return


async def notify_all(text, **kwargs):
    """Отправляет уведомление всем пользователям"""
    try:
        bot = Bot(token=TOKEN)
        success_count = 0
        for chat_id in CHAT_IDS:
            try:
                await bot.send_message(chat_id=chat_id, text=text, **kwargs)
                success_count += 1
                await asyncio.sleep(0.1)  # Небольшая задержка между сообщениями
            except TelegramError as e:
                logging.error("Telegram API ошибка отправки уведомления в чат %s: %s", chat_id, e)
        return success_count > 0  # Возвращаем True если хотя бы одно сообщение отправлено
    except TelegramError as e:
        logging.error("Telegram API ошибка в notify_all: %s", e)
        return False  # Возвращаем False при ошибке
    except (KeyError, ValueError, AttributeError) as e:
        logging.error("Ошибка данных в notify_all: %s", e)
        return False  # Возвращаем False при ошибке


from src.telegram.utils import rate_limit_api_call, safe_delete_message, safe_edit_message_text


@profile
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    # 🔍 ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ДЛЯ ДИАГНОСТИКИ
    logging.info(
        "🔘 [BUTTON] Функция button вызвана, update.type=%s",
        update.update_id if hasattr(update, "update_id") else "unknown",
    )
    # Дополнительное логирование для диагностики (можно отключить в production)
    logging.debug(
        "🔘 [BUTTON] Функция button вызвана, update_id=%s",
        update.update_id if hasattr(update, "update_id") else "unknown",
    )

    try:
        query = update.callback_query
        if not query:
            logging.error("❌ [BUTTON] Callback query отсутствует в update")
            # Уже логируется выше через logging.error
            return

        logging.info(
            "🔘 [BUTTON] Получен callback query: %s от пользователя %s",
            query.data,
            query.from_user.id,
        )
        # Уже логируется выше через logging.info
        try:
            await query.answer()
            logging.debug("✅ [BUTTON] query.answer() выполнен успешно")
        except BadRequest as e:
            err = str(e)
            if "Query is too old" in err or "query id is invalid" in err:
                logging.warning("⚠️ button: устаревший callback_query")
                # Пытаемся показать alert; при неудаче отправляем новое сообщение
                try:
                    await query.answer(
                        "Эта кнопка устарела. Откройте новое сообщение и попробуйте снова.",
                        show_alert=True,
                    )
                except TelegramError:
                    try:
                        msg = getattr(query, "message", None)
                        if msg is not None:
                            await msg.reply_text(
                                "⚠️ Кнопка устарела. Пожалуйста, дождитесь нового сигнала и нажмите 'Принять' в актуальном сообщении.",
                                parse_mode="HTML",
                            )
                    except TelegramError:
                        pass
                return
            raise

        user_data = context.user_data

        # Парсим данные кнопки
        data = query.data
        logging.info("🔍 button: получен callback_data: '%s'", data)

        if not data:
            logging.warning("⚠️ button: пустые данные callback")
            return

        # Обрабатываем разные типы кнопок
        if data.startswith("accept_") and "_" in data and "|" not in data:
            # Новый формат системы принятия сигналов: accept_SYMBOL_TIMESTAMP
            logging.info("🎯 button: обрабатываем кнопку принятия сигнала: %s", data)
            await handle_signal_acceptance_button(query, user_data, data)
        elif data.startswith("accept|"):
            # Старый формат: accept|SYMBOL|TIMESTAMP|...
            logging.info("✅ button: обрабатываем accept кнопку (старый формат): %s", data)
            # Уже логируется выше через logging.info
            await handle_accept_button(query, user_data, data)
            logging.debug("✅ [BUTTON] handle_accept_button завершен")
        elif data.startswith("feedback|"):
            logging.info("🧠 button: обрабатываем HITL feedback: %s", data)
            await handle_feedback_button(query, user_data, data)
        elif data.startswith("close_") and "_" in data and "|" not in data:
            # Новый формат системы принятия сигналов: close_SYMBOL_TIMESTAMP
            logging.info("🔒 button: обрабатываем кнопку закрытия позиции: %s", data)
            await handle_position_close_button(query, user_data, data)
        elif data.startswith("close|"):
            # Старый формат: close|SYMBOL|TIMESTAMP|...
            logging.info("🔒 button: обрабатываем close кнопку (старый формат): %s", data)
            await handle_close_button(query, user_data, data)
        elif data.startswith("dca_"):
            logging.info("📈 button: обрабатываем dca кнопку: %s", data)
            await handle_dca_button(query, user_data, data)
        elif data.startswith("confirm_"):
            logging.info("✔️ button: обрабатываем confirm кнопку: %s", data)
            await handle_confirm_button(query, user_data, data)
        elif data.startswith("history_page_"):
            logging.info("📜 button: переключение страницы истории: %s", data)
            try:
                page = int(data.split("_")[-1])
                from src.telegram.bot_trading import trade_history_cmd

                # Имитируем вызов команды с аргументом страницы
                context.args = [str(page)]
                # Используем вспомогательный метод для редактирования
                await trade_history_cmd(update, context)
            except Exception as e:
                logging.error("Ошибка при переключении истории: %s", e)
        elif data == "restart_setup":
            logging.info("🔄 button: перезапуск настройки: %s", data)
            # Сбрасываем setup_completed и начинаем заново
            user_data["setup_completed"] = False
            user_data["setup_step"] = "deposit"
            db.save_user_data(query.from_user.id, user_data)

            await query.message.edit_text(
                "🔄 <b>Перенастройка бота</b>\n\n"
                "💰 <b>Шаг 1: Установите новый депозит</b>\n"
                "Введите сумму в USDT (например: 1000):",
                parse_mode="HTML",
            )
        elif data.startswith("setup_"):
            logging.info("🔧 button: обрабатываем setup кнопку: %s", data)
            await handle_setup_button(query, user_data, data)
        elif data == "open_positions":
            logging.info("📊 button: обрабатываем open_positions кнопку: %s", data)
            await handle_open_positions_button(query, user_data, data)
        else:
            logging.error("❌ button: неизвестная кнопка: '%s' (длина: %s)", data, len(data))
            await safe_edit_message_text(query, f"❌ Неизвестная кнопка: {data}")

    except TelegramError as e:
        logging.error("Telegram API ошибка в button: %s", e)
        try:
            await safe_edit_message_text(query, "❌ Ошибка при обработке кнопки")
        except (KeyError, ValueError, AttributeError):
            pass
    except (KeyError, ValueError, AttributeError) as e:
        logging.error("Ошибка данных в button: %s", e)
        try:
            await safe_edit_message_text(query, "❌ Ошибка при обработке кнопки")
        except (KeyError, ValueError, AttributeError):
            pass


# ========================
# РЕЖИМЫ ТОРГОВЛИ (/mode)
# ========================
async def mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        adb = AcceptanceDatabase()
        mode = await adb.get_user_mode(user_id)

        # Проверяем наличие ключей для auto
        keys_status = "❌ Не подключены"
        if mode == "auto":
            keys = await adb.get_active_exchange_keys(user_id, "bitget")
            keys_status = "✅ Подключены" if keys else "❌ Не подключены (переключитесь на manual)"

        mode_emoji = "🤖" if mode == "auto" else "👤"
        await update.message.reply_text(
            f"{mode_emoji} <b>Режим торговли:</b> {mode.upper()}\n\n"
            f"🔐 <b>Ключи Bitget:</b> {keys_status}\n\n"
            f"📋 <b>Доступные режимы:</b>\n"
            f"• manual — ручное принятие сигналов\n"
            f"• auto — автоматическое исполнение\n\n"
            f"⚙️ Изменить: /mode_set manual|auto",
            parse_mode="HTML",
        )
    except Exception as e:
        logging.error("/mode error: %s", e)
        await update.message.reply_text("❌ Ошибка получения режима")


async def mode_set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        logging.info(
            "🔧 mode_set_cmd: user_id=%s, args=%s", user_id, context.args if context.args else []
        )

        if not context.args:
            await update.message.reply_text(
                "⚙️ <b>Установка режима торговли</b>\n\n"
                "Использование:\n"
                "<code>/mode_set manual</code> — ручной режим\n"
                "<code>/mode_set auto</code> — автоматический режим\n\n"
                "📋 <b>Manual:</b> сигналы требуют принятия (/accept)\n"
                "🤖 <b>Auto:</b> сигналы исполняются автоматически",
                parse_mode="HTML",
            )
            return

        new_mode = (context.args[0] or "manual").lower()
        if new_mode not in ("manual", "auto"):
            await update.message.reply_text("❌ Некорректный режим. Доступно: manual | auto")
            return

        adb = AcceptanceDatabase()

        # Проверка ключей для auto режима
        if new_mode == "auto":
            keys = await adb.get_active_exchange_keys(user_id, "bitget")
            if not keys:
                await update.message.reply_text(
                    "⚠️ <b>Ключи Bitget не подключены</b>\n\n"
                    "Для auto режима требуются ключи биржи.\n"
                    "Подключите их командой:\n"
                    "<code>/connect_bitget &lt;api_key&gt; &lt;secret&gt; &lt;passphrase&gt;</code>",
                    parse_mode="HTML",
                )
                return

        ok = await adb.set_user_mode(user_id, new_mode)
        if ok:
            mode_emoji = "🤖" if new_mode == "auto" else "👤"
            await update.message.reply_text(
                f"✅ <b>Режим обновлен:</b> {mode_emoji} {new_mode.upper()}\n\n"
                f"{'🤖 Сигналы будут исполняться автоматически' if new_mode == 'auto' else '👤 Сигналы требуют принятия кнопкой'}",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("❌ Не удалось обновить режим")
    except Exception as e:
        logging.error("/mode_set error: %s", e)
        await update.message.reply_text("❌ Ошибка установки режима")


async def backtest_all_cmd(update, context):
    """/backtest_all [interval] [days]

    Пример: /backtest_all 1h 90 — прогон по нескольким топ-символам за 90 дней
    """
    try:
        from backtrader_adapter import run_backtest_replay_batch

        from config import COINS
    except ImportError:
        await update.message.reply_text("❌ Невозможно загрузить зависимости")
        return

    try:
        interval = str(context.args[0]).lower() if len(context.args) >= 1 else "1h"
        days = int(context.args[1]) if len(context.args) >= 2 else 90
    except (ValueError, TypeError):
        await update.message.reply_text("Использование: /backtest_all [interval] [days]")
        return

    # Берем первые 10 монет для оперативного запуска
    symbols = [s for s in COINS[:10] if isinstance(s, str)]
    await update.message.reply_text(
        "🧪 Запускаю бэктест по нескольким символам... Это может занять время."
    )

    # Выполняем в пуле, чтобы не блокировать loop
    result = await asyncio.to_thread(run_backtest_replay_batch, symbols, interval, days)
    if not result.get("ok"):
        await update.message.reply_text("❌ Бэктест не дал результатов")
        return

    totals = result["totals"]
    lines = [
        "📊 <b>Backtest Summary (batch)</b>",
        f"Интервал: <code>{result['interval']}</code>",
        f"Период: <code>{result['since_days']}d</code>",
        f"Символов: <b>{totals['symbols']}</b>",
        f"Сигналов: <b>{totals['signals']}</b>",
        f"TP1 / TP2 / SL: <b>{totals['tp1']}</b> / <b>{totals['tp2']}</b> / <b>{totals['sl']}</b>",
        f"Суммарный PnL: <b>{totals['pnl']:.8f}</b>",
        "\nТоп-5 по PnL:",
    ]

    # Сортируем top-5
    items = sorted(result.get("items", []), key=lambda x: float(x.get("pnl", 0.0)), reverse=True)[
        :5
    ]
    for it in items:
        lines.append(
            f"• <code>{it['symbol']}</code>: pnl=<b>{float(it.get('pnl', 0.0)):.8f}</b>, "
            f"sig={int(it.get('signals', 0))}, tp1={int(it.get('tp1', 0))}, tp2={int(it.get('tp2', 0))}, sl={int(it.get('sl', 0))}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# =============================
# КЛЮЧИ БИРЖИ (/connect_bitget)
# =============================
async def connect_bitget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logging.info("🚀 Команда /connect_bitget вызвана пользователем %s", user_id)
    try:
        logging.info(
            "🔧 connect_bitget_cmd: user_id=%s, args_count=%s",
            user_id,
            len(context.args) if context.args else 0,
        )
        if context.args:
            logging.info(
                "🔧 connect_bitget_cmd: args_list=%s",
                [f"arg_{i}: {len(a)} chars" for i, a in enumerate(context.args)],
            )

        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "🔐 <b>Подключение Bitget</b>\n\n"
                "Использование:\n"
                "<code>/connect_bitget &lt;api_key&gt; &lt;secret&gt; &lt;passphrase&gt;</code>\n\n"
                "⚠️ <b>ВАЖНО:</b>\n"
                "• Создайте API ключ с правами: Read + Trade\n"
                "• БЕЗ прав Transfer и Withdraw!\n"
                "• Ключи будут зашифрованы при сохранении",
                parse_mode="HTML",
            )
            return

        api_key, secret, passphrase = context.args[0], context.args[1], context.args[2]
        logging.info("🔧 connect_bitget_cmd: получены ключи, сохраняю...")

        adb = AcceptanceDatabase()
        ok = await adb.save_exchange_keys(user_id, "bitget", api_key, secret, passphrase)

        logging.info("🔧 connect_bitget_cmd: save result=%s", ok)

        if ok:
            await update.message.reply_text(
                "✅ <b>Bitget ключи сохранены</b>\n\n"
                "🔐 Ключи зашифрованы и активированы\n"
                "📊 Теперь можете использовать /mode_set auto",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("❌ Не удалось сохранить ключи Bitget")
    except Exception as e:
        import traceback

        error_type = type(e).__name__
        error_msg_full = f"{error_type}: {str(e)}"
        logging.error("/connect_bitget error: %s", error_msg_full, exc_info=True)
        try:
            # Отправляем детальную ошибку пользователю для отладки
            error_msg = f"❌ Ошибка команды [{error_type}]: {str(e)}\n\n"
            if len(context.args) < 3 if context.args else True:
                error_msg += "⚠️ Похоже, вы передали меньше 3-х параметров. Нужно: /connect_bitget API SECRET PASS"
            await update.message.reply_text(error_msg)
        except (TelegramError, BadRequest, RuntimeError):
            # Игнорируем ошибки отправки сообщений об ошибках
            pass


async def disconnect_bitget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        logging.info("🔧 disconnect_bitget_cmd: user_id=%s", user_id)

        adb = AcceptanceDatabase()
        ok = await adb.deactivate_exchange_keys(user_id, "bitget")

        logging.info("🔧 disconnect_bitget_cmd: deactivate result=%s", ok)

        if ok:
            await update.message.reply_text(
                "✅ <b>Bitget ключи деактивированы</b>\n\n"
                "🔐 Ключи остаются в БД (зашифрованы)\n"
                "📊 Автоматически переключено на manual режим",
                parse_mode="HTML",
            )
            # Автоматически переключаем на manual при отключении ключей
            await adb.set_user_mode(user_id, "manual")
        else:
            await update.message.reply_text("⚠️ Ключи уже отключены или не найдены")
    except Exception as e:
        logging.error("/disconnect_bitget error: %s", e, exc_info=True)
        try:
            await update.message.reply_text("❌ Ошибка команды")
        except Exception:
            pass


async def handle_feedback_button(query, user_data, data):
    """Обрабатывает HITL-фидбек по сигналу."""
    try:
        parts = data.split("|")
        if len(parts) < 5:
            logging.warning("⚠️ handle_feedback_button: некорректные данные '%s'", data)
            await query.answer("Некорректные данные кнопки", show_alert=True)
            return

        _, symbol, token, direction_raw, action_raw = parts[:5]
        feedback_type = (action_raw or "").strip().lower()
        direction = (direction_raw or "").upper() or None
        signal_key = f"{symbol}|{token}"
        user_id = query.from_user.id if query.from_user else None

        if not user_id:
            logging.error("❌ handle_feedback_button: отсутствует user_id")
            await query.answer("Ошибка обработки", show_alert=True)
            return

        message = getattr(query, "message", None)
        chat = getattr(message, "chat", None) if message else None
        chat_id = getattr(message, "chat_id", None)
        if chat_id is None and chat is not None:
            chat_id = getattr(chat, "id", None)
        message_id = getattr(message, "message_id", None)

        if feedback_type == "comment":
            user_data["pending_feedback"] = {
                "signal_key": signal_key,
                "symbol": symbol,
                "direction": direction,
                "chat_id": chat_id,
                "message_id": message_id,
                "created_at": time.time(),
            }
            await query.answer("Напишите комментарий следующим сообщением.", show_alert=True)
            if message:
                await message.reply_text(
                    "📝 Напишите комментарий к сигналу (например: «SL слишком узкий»).",
                    parse_mode="HTML",
                )
            return

        if feedback_type not in {"confirm", "reject"}:
            logging.warning("⚠️ handle_feedback_button: неизвестный тип '%s'", feedback_type)
            await query.answer("Неизвестный тип обратной связи", show_alert=True)
            return

        if not SIGNAL_ACCEPTANCE_AVAILABLE:
            logging.error("❌ AcceptanceDatabase недоступна для HITL фидбека")
            await query.answer("База данных недоступна", show_alert=True)
            return

        adb = AcceptanceDatabase()
        await adb.record_feedback(
            signal_key=signal_key,
            symbol=symbol,
            direction=direction,
            user_id=int(user_id),
            chat_id=int(chat_id) if chat_id is not None else None,
            message_id=int(message_id) if message_id is not None else None,
            feedback_type=feedback_type,
            comment=None,
            metadata={"source": "button"},
        )

        if feedback_type == "confirm":
            await query.answer("✅ Сигнал подтверждён", show_alert=False)
        else:
            await query.answer("🚩 Сигнал помечен как ошибочный", show_alert=True)
            if message:
                await message.reply_text(
                    "🚨 Зафиксировано: сигнал помечен как ошибочный. Команда проверит детали.",
                    parse_mode="HTML",
                )

    except TelegramError as e:
        logging.error("Telegram API ошибка в handle_feedback_button: %s", e)
        await query.answer("Ошибка Telegram", show_alert=True)
    except Exception as e:  # noqa: BLE001
        logging.error("❌ handle_feedback_button ошибка: %s", e, exc_info=True)
        await query.answer("Ошибка обработки", show_alert=True)


async def handle_accept_button(query, user_data, data):
    """Обработчик кнопки принятия сигнала"""
    try:
        logging.info("🚀 handle_accept_button: начало обработки сигнала: %s", data)
        # Базовая инициализация плеча для всех путей выполнения
        position_leverage = 1

        # Получаем ID пользователя
        user_id = query.from_user.id
        logging.info("👤 handle_accept_button: пользователь %s", user_id)

        # Синхронизируем user_data с БД, чтобы учесть закрытия по TP2/SL, выполненные в фоновом процессе
        try:
            latest = db.get_user_data(user_id)
            if not latest:
                defaults = {
                    "deposit": 0.0,
                    "balance": 0.0,
                    "free_deposit": 0.0,
                    "risk_pct": 2.0,
                    "trade_mode": "spot",
                    "filter_mode": "soft",
                    "leverage": 1,
                    "setup_completed": False,
                }
                try:
                    try:
                        from src.utils.user_utils import save_user_data_for_signals
                    except ImportError:
                        try:
                            from user_utils import save_user_data_for_signals
                        except ImportError:

                            def save_user_data_for_signals(*args, **kwargs):
                                pass

                    save_user_data_for_signals({str(user_id): defaults})
                except (RuntimeError, ValueError, TypeError):
                    pass
                user_data.update(defaults)
        except (RuntimeError, ValueError, TypeError):
            pass

        # Получаем данные пользователя
        deposit = user_data.get("deposit")

        # Проверяем, что пользователь прошел настройку
        if not deposit:
            logging.warning(
                "⚠️ handle_accept_button: пользователь %s не прошел настройку (нет deposit)", user_id
            )
            await query.edit_message_text(
                "❌ <b>Необходимо завершить настройку бота</b>\n\n"
                "Используйте команду /start для настройки депозита и параметров торговли.",
                parse_mode="HTML",
            )
            return

        # Проверяем, что настройка завершена
        if not user_data.get("setup_completed", False):
            logging.warning(
                "⚠️ handle_accept_button: пользователь %s не завершил настройку (setup_completed=False)",
                user_id,
            )
            await query.edit_message_text(
                "❌ <b>Необходимо завершить настройку бота</b>\n\n"
                "Используйте команду /start для завершения настройки.",
                parse_mode="HTML",
            )
            return

        # leverage будет установлен из callback_data

        # Инициализируем переменные по умолчанию
        symbol = ""
        entry_price = 0.0
        qty = 0.0
        side = ""
        risk_pct = 0.0
        tp_price = 0.0  # для обратной совместимости
        tp1_price = 0.0
        tp2_price = 0.0
        risk_amount = 0.0  # Добавляем инициализацию
        # Безопасная инициализация плеча по умолчанию (на случай, если рыночные данные недоступны)
        position_leverage = 1
        try:
            _tm = (user_data.get("trade_mode", "spot") or "spot").lower()
            position_leverage = int(user_data.get("leverage", 1)) if _tm == "futures" else 1
        except (TypeError, ValueError, AttributeError, KeyError):
            position_leverage = 1

        # Парсер с валидацией «срезов» callback_data
        logging.info("📊 handle_accept_button: парсинг данных сигнала")

        def _parse_accept_payload(raw: str):
            if "|" not in raw or not (raw.startswith("accept|") or raw.startswith("accept_")):
                return False, {}, "format"
            parts = raw.split("|")
            # Поддерживаем форматы: 5..8 полей
            if len(parts) < 5:
                return False, {}, "len"
            try:
                # Базовые поля всегда: accept|symbol|ts|price|...
                symbol_val = parts[1]
                ts_val = parts[2] if len(parts) >= 3 else ""
                price_val = float(parts[3])
                payload = {
                    "symbol": symbol_val,
                    "entry_price": price_val,
                    "ts": ts_val,
                }
            except (ValueError, TypeError):
                return False, {}, "price"

            # Дальше гибко: возможные варианты
            # 5 полей: accept|sym|ts|price|side
            # 6 полей: accept|sym|ts|price|side|risk
            # 7 полей: accept|sym|ts|price|qty|side|risk (DCA без lev)
            # 8 полей: accept|sym|ts|price|qty|side|risk|lev (полный DCA)
            try:
                side_val = None
                risk_val = None
                qty_val = 0.0
                lev_val = None

                if len(parts) == 5:
                    # accept|sym|ts|price|side
                    side_val = str(parts[4]).lower()
                    risk_val = 2.0  # фолбэк на риск по умолчанию
                elif len(parts) == 6:
                    # accept|sym|ts|price|side|risk
                    side_val = str(parts[4]).lower()
                    risk_val = float(parts[5])
                elif len(parts) == 7:
                    # Два возможных варианта:
                    # 1) accept|sym|ts|price|qty|side|risk   -> DCA без lev
                    # 2) accept|sym|ts|price|side|risk|lev   -> обычный без qty, но с lev
                    if str(parts[4]).lower() in ("long", "short"):
                        # Вариант 2: side|risk|lev
                        side_val = str(parts[4]).lower()
                        risk_val = float(parts[5])
                        try:
                            lev_val = float(parts[6])
                        except (ValueError, TypeError):
                            lev_val = None
                        qty_val = 0.0
                    else:
                        # Вариант 1: qty|side|risk
                        qty_val = float(parts[4])
                        side_val = str(parts[5]).lower()
                        risk_val = float(parts[6])
                else:  # len >= 8
                    # accept|sym|ts|price|qty|side|risk|lev -> полный DCA
                    qty_val = float(parts[4])
                    side_val = str(parts[5]).lower()
                    risk_val = float(parts[6])
                    lev_val = float(parts[7])

                payload["qty"] = float(qty_val or 0.0)
                payload["side"] = side_val or "long"
                payload["risk_pct"] = float(risk_val if risk_val is not None else 2.0)
                payload["lev"] = lev_val
                # 🔧 ИСПРАВЛЕНО: DCA определяется по наличию qty > 0 И правильной структуре
                # Обычный сигнал: accept|sym|ts|price|qty|side|risk|lev (8 частей, но qty может быть 0)
                # DCA сигнал: accept|sym|ts|price|qty|side|risk|lev (8 частей, qty > 0 И это усреднение)
                # КРИТЕРИЙ: DCA только если qty > 0 И это не первый сигнал по символу
                # Для простоты: если qty > 0 и есть открытая позиция по символу - это DCA
                # Иначе: обычный сигнал (qty передается для информации, но рассчитывается заново)
                payload["is_dca"] = False  # По умолчанию обычный сигнал
            except (ValueError, TypeError, IndexError):
                return False, {}, "fields"

            # Валидация полей
            if payload["side"] not in ("long", "short"):
                return False, {}, "side"
            if payload["risk_pct"] < -0.01 or payload["risk_pct"] > 100.0:
                return False, {}, "risk"
            if payload["lev"] is not None and (
                float(payload["lev"]) <= 0.0 or float(payload["lev"]) > 125.0
            ):
                return False, {}, "lev"
            if payload["is_dca"] and payload["qty"] < 0:
                return False, {}, "qty"
            sym = payload["symbol"]
            if not sym or len(sym) > 20:
                return False, {}, "symbol"
            return True, payload, ""

        ok, pl, reason = _parse_accept_payload(data)
        if not ok:
            logging.error("❌ handle_accept_button: некорректные данные (%s): %s", reason, data)
            await query.edit_message_text("❌ Неверный формат данных сигнала")
            return

        symbol = pl["symbol"]
        entry_price = float(pl["entry_price"])
        side = pl["side"]
        risk_pct = float(pl["risk_pct"])
        received_lev = pl["lev"]

        logging.info(
            "📈 handle_accept_button: %s %s цена=%s риск=%s",
            symbol,
            side,
            entry_price,
            str(risk_pct) + "%",
        )

        # 🔧 ИСПРАВЛЕНО: Определяем DCA по наличию открытой позиции по символу
        # Проверяем, есть ли уже открытая позиция по этому символу
        try:
            existing_positions = user_data.get("positions", []) or []
            has_open_position = any(
                p.get("symbol") == symbol and p.get("status", "open") == "open"
                for p in existing_positions
            )
            # DCA только если есть открытая позиция И qty > 0
            is_dca_signal = bool(has_open_position and pl.get("qty", 0) > 0)
            logging.info(
                "🔍 handle_accept_button: has_open_position=%s, qty=%s, is_dca_signal=%s",
                has_open_position,
                pl.get("qty", 0),
                is_dca_signal,
            )
        except (TypeError, ValueError, KeyError):
            is_dca_signal = False
            logging.warning(
                "⚠️ handle_accept_button: ошибка определения DCA, используем обычный сигнал"
            )

        if is_dca_signal:
            qty = float(pl["qty"])
            # TP для DCA: по умолчанию 1% и 2% в сторону профита
            if side == "long":
                tp1_price = entry_price * 1.01
                tp2_price = entry_price * 1.02
            else:
                tp1_price = entry_price * 0.99
                tp2_price = entry_price * 0.98
            tp_price = tp2_price
            risk_amount = qty * entry_price
            logging.info(
                "🔄 handle_accept_button: DCA сигнал qty=%s leverage_in_cb=%s", qty, received_lev
            )
            # Фолбэк qty от риска, если qty некорректно
            try:
                if not qty or float(qty) <= 0:
                    base_deposit = float(deposit or 0.0)
                    base_risk_pct = float(risk_pct or user_data.get("risk_pct", 2))
                    calc_risk = base_deposit * (base_risk_pct / 100.0)
                    qty = calc_risk / max(1e-9, float(entry_price))
                    risk_amount = calc_risk
            except (TypeError, ValueError):
                pass
        else:
            # Обычный сигнал: qty рассчитаем позже; плечо — из received_lev
            qty = 0
            # Рассчитываем TP для обычных сигналов: 1% и 2% по умолчанию
            if side == "long":
                tp1_price = entry_price * 1.01
                tp2_price = entry_price * 1.02
            else:
                tp1_price = entry_price * 0.99
                tp2_price = entry_price * 0.98
            tp_price = tp2_price
            is_dca_signal = False
            logging.info(
                "🆕 handle_accept_button: обычный сигнал leverage_in_cb=%s tp=%s",
                received_lev,
                tp_price,
            )

            # Проверка на дубликаты только для обычных (не DCA) сигналов
            try:
                entry_time = pl.get("ts", "")
                signal_key = f"{symbol}_{entry_time}"
                if "accepted_signals" in user_data:
                    if any(
                        s.get("signal_key") == signal_key for s in user_data["accepted_signals"]
                    ):
                        logging.warning(
                            "⚠️ handle_accept_button: обычный сигнал %s уже был принят ранее",
                            signal_key,
                        )
                        await query.edit_message_text(
                            "✅ <b>Сигнал уже принят</b>\n\n"
                            f"Символ: {symbol}\n"
                            f"Цена: {entry_price}\n\n"
                            f"💡 Используйте кнопку DCA для усреднения позиции",
                            parse_mode="HTML",
                        )
                        return
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError):
                pass

        # --- Проверка истечения срока действия сигнала (TTL) ---
        try:
            short_ts = pl.get("ts", "")
            signal_key = f"{symbol}|{short_ts}|{str(side).lower()}"
            info = db.get_active_signal_info(signal_key)
            if info and info.get("expiry_time"):
                try:
                    now_dt = get_utc_now()
                    exp_dt = dt.datetime.fromisoformat(str(info["expiry_time"]))
                    if now_dt > exp_dt:
                        # Помечаем expired в active_signals и закрываем запись в signals_log
                        try:
                            db.mark_signal_expired(signal_key)
                        except (RuntimeError, ValueError, TypeError):
                            pass
                        try:
                            entry_time_iso = info.get("entry_time")
                            if entry_time_iso:
                                db.update_signal_close_db(
                                    symbol, entry_time_iso, now_dt.isoformat(), "expired", 0.0
                                )
                        except (RuntimeError, ValueError, TypeError):
                            pass
                        await query.edit_message_text(
                            "❌ <b>Время принятия сигнала истекло</b>\n\nПодождите следующий сигнал по этому символу.",
                            parse_mode="HTML",
                        )
                        return
                except (ValueError, TypeError, KeyError):
                    # Если не смогли распарсить — не блокируем, продолжаем
                    pass
        except (RuntimeError, ValueError, TypeError, KeyError):
            pass

        # Проверяем данные пользователя (дублирующая проверка, на случай если deposit был удален)
        if not deposit:
            await query.edit_message_text("❌ Установите баланс командой /set_balance")
            return

        # Инициализируем base_risk_pct ДО использования (исправление UnboundLocalError)
        base_risk_pct = user_data.get("risk_pct", 2)

        if is_dca_signal:
            # Для DCA сигналов параметры уже рассчитаны
            logging.debug(
                "[DEBUG DCA] %s: Используем переданные параметры - цена: %s, количество: %s, риск: %s%%",
                symbol,
                entry_price,
                qty,
                risk_pct,
            )
        else:
            # Для обычных сигналов рассчитываем параметры
            risk_pct = base_risk_pct

        # Фиксируем принятие сигнала в user_data (accepted_signals)
        try:
            if "accepted_signals" not in user_data:
                user_data["accepted_signals"] = []
            entry_time = pl.get("ts", "")
            signal_key = f"{symbol}_{entry_time}"
            if not any(s.get("signal_key") == signal_key for s in user_data["accepted_signals"]):
                user_data["accepted_signals"].append(
                    {
                        "signal_key": signal_key,
                        "symbol": symbol,
                        "entry_time": entry_time,
                        "side": side,
                    }
                )
            # Сохраняем в БД обновлённые данные пользователя
            try:
                try:
                    from src.utils.user_utils import save_user_data_for_signals
                except ImportError:
                    try:
                        from user_utils import save_user_data_for_signals
                    except ImportError:

                        def save_user_data_for_signals(*args, **kwargs):
                            pass

                save_user_data_for_signals({str(user_id): user_data})
            except (RuntimeError, ValueError, TypeError):
                pass
        except (RuntimeError, ValueError, TypeError, KeyError):
            pass

        # --- ПОРТФЕЛЬНЫЕ ОГРАНИЧЕНИЯ ПЕРЕД СОЗДАНИЕМ ПОЗИЦИИ ---
        try:
            # ✅ ВАЖНО: Проверяем позиции из БД, а не только из user_data!
            # Это предотвращает дубликаты при перезапуске бота
            try:
                # Получаем активные позиции из БД
                # pylint: disable=redefined-outer-name
                try:
                    from src.database.acceptance import AcceptanceDatabase
                except ImportError:
                    try:
                        from acceptance_database import AcceptanceDatabase
                    except ImportError:

                        class AcceptanceDatabase:
                            async def get_active_positions_by_user(self, *args, **kwargs):
                                return []

                adb = AcceptanceDatabase()
                db_positions = await adb.get_active_positions_by_user(str(user_id))

                # Преобразуем в формат user_data для обратной совместимости
                positions_all = []
                for pos in db_positions:
                    positions_all.append(
                        {
                            "symbol": pos["symbol"],
                            "side": pos["direction"].lower(),
                            "entry_price": pos["entry_price"],
                            "qty": 0,  # Количество нужно получать из signals_log
                            "status": pos["status"],
                        }
                    )

                # Добавляем позиции из user_data если их нет в БД (для обратной совместимости)
                user_positions = user_data.get("positions", []) or user_data.get(
                    "open_positions", []
                )
                existing_symbols = {p["symbol"] for p in positions_all}
                for up in user_positions:
                    if up.get("symbol") not in existing_symbols:
                        positions_all.append(up)
            except Exception as e:
                logging.warning("⚠️ Ошибка получения позиций из БД, используем user_data: %s", e)
                # Fallback на user_data
                positions_all = user_data.get("positions", []) or user_data.get(
                    "open_positions", []
                )
            open_positions = [
                p
                for p in positions_all
                if p.get("status", "open") == "open" and float(p.get("qty", 0)) > 0
            ]

            # 0) Лимит по числу позиций (динамика от риска/депозита с системными крышами)
            try:
                from config import (
                    MAX_CONCURRENT_SYMBOLS,
                    PORTFOLIO_MAX_POSITIONS_HARD,
                    PORTFOLIO_MAX_RISK_PCT,
                    PORTFOLIO_MIN_POSITIONS,
                )
            except ImportError:
                PORTFOLIO_MAX_RISK_PCT = 8.0
                PORTFOLIO_MIN_POSITIONS = 2
                PORTFOLIO_MAX_POSITIONS_HARD = 10
                MAX_CONCURRENT_SYMBOLS = 6
            user_risk_pct = float(user_data.get("risk_pct", 2.0))
            dyn_limit = int(max(1, float(PORTFOLIO_MAX_RISK_PCT) // max(0.1, user_risk_pct)))
            # Учет депозита и минимального нотионала на позицию
            try:
                import importlib

                _cfg = importlib.import_module("config")
                min_notional_per_pos = float(getattr(_cfg, "MIN_NOTIONAL_PER_POSITION_USDT", 200))
            except (ImportError, ValueError, TypeError):
                min_notional_per_pos = 200.0
            try:
                deposit_val = float(user_data.get("deposit") or user_data.get("balance") or 0.0)
                if min_notional_per_pos > 0:
                    dyn_by_notional = int(max(1, deposit_val // min_notional_per_pos))
                    dyn_limit = max(dyn_limit, dyn_by_notional)
            except (TypeError, ValueError):
                pass
            user_max_override = int(user_data.get("portfolio_max_positions", 0) or 0)
            if user_max_override > 0:
                dyn_limit = min(dyn_limit, user_max_override)
            dyn_limit = max(
                int(PORTFOLIO_MIN_POSITIONS),
                min(int(PORTFOLIO_MAX_POSITIONS_HARD), int(MAX_CONCURRENT_SYMBOLS), dyn_limit),
            )
            # DCA не считается отдельной позицией: лимитируем по кол-ву уникальных символов с открытыми лотами
            unique_open_symbols = {p.get("symbol") for p in open_positions if p.get("symbol")}
            # Блокируем только если символ новый и превысим лимит; DCA по существующему символу — разрешаем
            if len(unique_open_symbols) >= dyn_limit and (symbol not in unique_open_symbols):
                await query.edit_message_text(
                    f"❌ Достигнут лимит уникальных символов: {dyn_limit}. Закройте позицию, чтобы открыть новую."
                )
                return

            # 1) Лимит позиций по одному символу
            max_per_symbol = int(user_data.get("max_positions_per_symbol", 1))
            same_symbol_open = [p for p in open_positions if p.get("symbol") == symbol]
            # Для обычных входов применяем лимит; для DCA — не блокируем добавление к существующей позиции
            if not is_dca_signal and len(same_symbol_open) >= max_per_symbol:
                await query.edit_message_text(
                    "❌ Уже есть открытая позиция по этому символу. Закройте текущую перед открытием новой."
                )
                return

            # 2) Проверка загрузки депозита (грубая)
            # Текущий нотионал
            current_notional = 0.0
            for p in open_positions:
                try:
                    current_notional += float(p.get("entry_price", 0)) * float(p.get("qty", 0))
                except (TypeError, ValueError):
                    pass

            # Планируемый нотионал по входящему сигналу
            if is_dca_signal and qty and qty > 0:
                proposed_notional = float(qty) * float(entry_price)
            else:
                # Для обычного сигнала используем риск от депозита
                proposed_notional = float(deposit) * (float(risk_pct) / 100.0)
                # Если qty уже рассчитан выше, можно уточнить как qty*entry_price
                try:
                    if qty and qty > 0:
                        proposed_notional = float(qty) * float(entry_price)
                except (TypeError, ValueError):
                    pass

            usage_limit_pct = float(user_data.get("max_margin_usage_pct", 80.0))
            usage_pct = (current_notional + proposed_notional) / max(1.0, float(deposit)) * 100.0
            if usage_pct > usage_limit_pct:
                await query.edit_message_text(
                    f"❌ Загрузка депозита {usage_pct:.1f}% превышает лимит {usage_limit_pct:.0f}%. Уменьшите риск/объём."
                )
                return

            # 3) Проверка свободного депозита (чтобы не уходить в отрицательные свободные средства)
            free_deposit = float(user_data.get("free_deposit", deposit))
            if proposed_notional > free_deposit:
                await query.edit_message_text(
                    f"❌ Недостаточно свободного депозита: нужно {proposed_notional:.2f}, доступно {free_deposit:.2f}."
                )
                return
        except (TypeError, ValueError, KeyError) as e:
            logging.warning("⚠️ Ошибка проверки портфельных ограничений: %s", e)

        # --- ИНТЕГРАЦИЯ АНОМАЛИЙ ---
        # Для DCA сигналов пропускаем расчет аномалий, так как параметры уже оптимизированы
        if not is_dca_signal:
            try:
                # Импортируем функции расчета аномалий
                from signal_live import (
                    calculate_anomaly_based_risk,
                    calculate_anomaly_based_volume,
                    calculate_anomaly_indicator_volume,
                )

                # Получаем данные о рынке для расчета аномалий
                try:
                    market_data = await get_market_cap_data(symbol)
                    if market_data:
                        volume_24h = market_data.get("volume_24h", 0)
                        market_cap = market_data.get("market_cap", 0)

                        if volume_24h > 0 and market_cap > 0:
                            # Рассчитываем аномалии
                            circles_count, _, _ = calculate_anomaly_indicator_volume(
                                volume_24h, market_cap, side
                            )

                            # Корректируем риск на основе аномалий
                            adjusted_risk_pct, _ = calculate_anomaly_based_risk(
                                base_risk_pct, circles_count
                            )
                            logging.debug(
                                "[DEBUG] %s: Аномалии - %d кружков, риск скорректирован с %s%% на %.1f%%",
                                symbol,
                                circles_count,
                                base_risk_pct,
                                adjusted_risk_pct,
                            )

                            # Корректируем объем на основе аномалий
                            base_volume = deposit * (adjusted_risk_pct / 100)
                            adjusted_volume, volume_multiplier, _ = calculate_anomaly_based_volume(
                                base_volume, circles_count, deposit
                            )

                            # Рассчитываем итоговое количество с учетом аномалий и фиксируем риск
                            qty = adjusted_volume / entry_price
                            risk_pct = adjusted_risk_pct
                            risk_amount = adjusted_volume

                            logging.debug(
                                "[DEBUG] %s: Объем скорректирован с %.2f на %.2f (%.2fx)",
                                symbol,
                                base_volume,
                                adjusted_volume,
                                volume_multiplier,
                            )
                        else:
                            logging.debug(
                                "[DEBUG] %s: Недостаточно данных для расчета аномалий", symbol
                            )
                            # Используем базовый расчет
                            risk_pct = base_risk_pct
                            risk_amount = deposit * (risk_pct / 100)
                            qty = risk_amount / entry_price
                    else:
                        logging.debug("[DEBUG] %s: Не удалось получить данные о рынке", symbol)
                        # Используем базовый расчет
                        risk_pct = base_risk_pct
                        risk_amount = deposit * (risk_pct / 100)
                        qty = risk_amount / entry_price
                except (ImportError, AttributeError) as e:
                    logging.debug(
                        "[DEBUG] %s: Ошибка расчета аномалий: %s", symbol, e, exc_info=True
                    )
                    # Используем базовый расчет
                    risk_pct = base_risk_pct
                    risk_amount = deposit * (risk_pct / 100)
                    qty = risk_amount / entry_price

            except ImportError:
                logging.debug("[DEBUG] %s: Функции аномалий недоступны", symbol)
                # Используем базовый расчет
                risk_pct = base_risk_pct
                risk_amount = deposit * (risk_pct / 100)
                qty = risk_amount / entry_price

        # Для обычных сигналов устанавливаем переменные по умолчанию
        if not is_dca_signal:
            risk_pct = base_risk_pct

        # --- Обновляем цену входа на актуальную и считаем динамические TP/плечо ---
        try:
            ohlc = get_ohlc_binance_sync(symbol, interval="1m", limit=50)
            if ohlc and len(ohlc) > 0:
                entry_price = float(ohlc[-1]["close"])  # актуальная цена
                # Плечо: если пришло в callback — уважаем; иначе считаем рыночное с базой 5 и капами
                try:
                    trade_mode = (user_data.get("trade_mode", "spot") or "spot").lower()
                    if trade_mode == "futures":
                        # Жёсткие капы
                        try:
                            deposit_val = float(user_data.get("deposit", 0) or 0)
                            from shared_utils import risk_profile_for_user

                            max_hard = int(
                                risk_profile_for_user(deposit_val, trade_mode).get(
                                    "max_leverage_hard", 20
                                )
                            )
                        except (ValueError, TypeError, KeyError, ImportError):
                            max_hard = 20
                        try:
                            user_lev_cap = int(user_data.get("leverage", 20) or 20)
                        except (TypeError, ValueError):
                            user_lev_cap = 20

                        if received_lev is not None:
                            position_leverage = int(
                                min(20, max_hard, user_lev_cap, max(1, int(round(received_lev))))
                            )
                        else:
                            from signal_live import get_dynamic_leverage

                            df = pd.DataFrame(ohlc)
                            dyn_raw = int(
                                max(1, get_dynamic_leverage(df, len(df) - 1, base_leverage=5))
                            )
                            position_leverage = int(min(20, max_hard, user_lev_cap, dyn_raw))
                    else:
                        position_leverage = 1
                except (ValueError, TypeError, RuntimeError, ImportError, KeyError):
                    # Фолбэк: сохраняем пришедшее значение или базу режима
                    if received_lev is not None:
                        try:
                            position_leverage = int(max(1, round(received_lev)))
                        except (TypeError, ValueError):
                            position_leverage = int(user_data.get("leverage", 1))
                    else:
                        position_leverage = (
                            1
                            if user_data.get("trade_mode", "spot") == "spot"
                            else int(user_data.get("leverage", 1))
                        )
                # Динамический риск (база)
                try:
                    from signal_live import get_dynamic_risk_pct

                    df_dyn = pd.DataFrame(ohlc)
                    dynamic_risk_pct = float(get_dynamic_risk_pct(df_dyn, len(df_dyn) - 1))
                except (ValueError, TypeError, ImportError, AttributeError):
                    dynamic_risk_pct = user_data.get("risk_pct", base_risk_pct)
                # Динамические TP на основе волатильности/BB и унификации
                df = pd.DataFrame(ohlc)
                trade_mode = user_data.get("trade_mode", "spot")
                tp1_pct, tp2_pct = get_dynamic_tp_levels(
                    df, len(df) - 1, side, trade_mode=trade_mode, adjust_for_fees=True
                )
                # Унифицируем с учётом открытых позиций пользователя (если есть df, индекс)
                try:
                    u_tp1_pct, u_tp2_pct = calculate_unified_tp_for_symbol(
                        user_data, symbol, entry_price, df, len(df) - 1
                    )
                    # Берём более мягкие из двух подходов
                    tp1_pct = min(tp1_pct, u_tp1_pct)
                    tp2_pct = min(tp2_pct, u_tp2_pct)
                except (ValueError, TypeError, KeyError):
                    pass
                if side == "long":
                    tp1_price = entry_price * (1 + tp1_pct / 100)
                    tp2_price = entry_price * (1 + tp2_pct / 100)
                else:
                    tp1_price = entry_price * (1 - tp1_pct / 100)
                    tp2_price = entry_price * (1 - tp2_pct / 100)

                # Сдвигаем TP2 внутрь на несколько тиков: динамически от ATR с фолбэком на константу
                try:
                    from exchange_api import get_symbol_info

                    from config import TP2_INWARD_TICKS

                    info = await get_symbol_info(symbol)
                    tick = float(info.get("price_tick", 0) or 0)

                    inward_ticks = 0
                    # Пробуем посчитать ATR (локальный импорт, чтобы не тащить зависимость глобально)
                    try:
                        # ATR (Average True Range)
                        from ta.volatility import AverageTrueRange

                        atr_ind = AverageTrueRange(
                            high=df["high"], low=df["low"], close=df["close"], window=14
                        )
                        atr_val = float(atr_ind.average_true_range().iloc[-1])
                    except (
                        ImportError,
                        AttributeError,
                        KeyError,
                        ValueError,
                        TypeError,
                        IndexError,
                    ):
                        # Ручной ATR как среднее True Range за 14
                        try:
                            prev_close = df["close"].shift(1)
                            tr = (df["high"] - df["low"]).to_frame("hl")
                            tr["hc"] = (df["high"] - prev_close).abs()
                            tr["lc"] = (df["low"] - prev_close).abs()
                            true_range = tr.max(axis=1)
                            atr_val = float(true_range.rolling(14).mean().iloc[-1])
                        except (KeyError, ValueError, TypeError, AttributeError, IndexError):
                            atr_val = 0.0

                    if tick > 0 and atr_val > 0:
                        atr_ticks = atr_val / tick
                        # Берём долю ATR в тиках, аккуратно ограничиваем диапазон
                        dyn_ticks = int(max(8, min(20, round(0.2 * atr_ticks))))
                        inward_ticks = max(0, dyn_ticks)

                    # Фолбэк на статическую настройку, если динамика не получилась
                    if inward_ticks <= 0:
                        inward_ticks = max(0, int(TP2_INWARD_TICKS))

                    inward = inward_ticks * tick
                    if inward and tick:
                        if side == "long":
                            tp2_price = max(0.0, tp2_price - inward)
                        else:
                            tp2_price = tp2_price + inward
                except (ImportError, ValueError, TypeError, KeyError):
                    pass
                # Гарантируем корректный порядок целей: для LONG tp2 >= tp1, для SHORT tp2 <= tp1
                try:
                    if (
                        side == "long"
                        and tp2_price < tp1_price
                        or side != "long"
                        and tp2_price > tp1_price
                    ):
                        tp1_price, tp2_price = tp2_price, tp1_price
                except (TypeError, ValueError):
                    pass
                tp_price = tp2_price
                # Корректируем риск аномалиями (если доступны данные о рынке)
                try:
                    from signal_live import (
                        calculate_anomaly_based_risk,
                        calculate_anomaly_indicator_volume,
                    )

                    market_data = await get_market_cap_data(symbol)
                except (ImportError, AttributeError):
                    # Функции недоступны, используем базовый риск
                    market_data = None

                if market_data:
                    try:
                        volume_24h = market_data.get("volume_24h", 0)
                        market_cap = market_data.get("market_cap", 0)
                        if volume_24h > 0 and market_cap > 0:
                            from signal_live import (
                                calculate_anomaly_based_risk,
                                calculate_anomaly_indicator_volume,
                            )

                            circles_count, _, _ = calculate_anomaly_indicator_volume(
                                volume_24h, market_cap, side
                            )
                            adjusted_risk_pct, _ = calculate_anomaly_based_risk(
                                dynamic_risk_pct, circles_count
                            )
                            risk_pct = adjusted_risk_pct
                        else:
                            risk_pct = dynamic_risk_pct
                    except (ValueError, TypeError, ImportError, AttributeError):
                        risk_pct = dynamic_risk_pct
                else:
                    risk_pct = dynamic_risk_pct
                # Пересчитываем qty/риск под динамический risk_pct (с учётом тренда BTC/ETH)
                # Применяем капы по профилю риска
                trade_mode = user_data.get("trade_mode", "spot")
                # Мультипликатор риска по фильтру soft/strict используется только при генерации (signal_live),
                # здесь применяем базу пользователя
                base_new_risk_usd = deposit * (risk_pct / 100)
                allowed_risk = clamp_new_risk(
                    deposit, user_data, symbol, base_new_risk_usd, trade_mode
                )
                risk_amount = allowed_risk
                qty = risk_amount / max(1e-9, entry_price)
        except (RuntimeError, ValueError, TypeError):
            pass

        # Определяем итоговые значения для позиции
        if "risk_pct" not in locals():
            risk_pct = base_risk_pct
            risk_amount = deposit * (risk_pct / 100)

        # Гарантируем ненулевое количество (qty) перед созданием позиции
        try:
            if not qty or float(qty) <= 0:
                fallback_risk = float(risk_amount or (deposit * (risk_pct / 100)))
                qty = fallback_risk / max(1e-9, float(entry_price))
        except (TypeError, ValueError):
            qty = 0.0

        # Создаем позицию
        is_dca_position = bool(is_dca_signal)
        # Определяем порядковый номер усреднения на момент создания лота
        try:
            existing_symbol_open = [
                p
                for p in (user_data.get("positions", []) or [])
                if p.get("symbol") == symbol and p.get("status", "open") == "open"
            ]
            current_dca_index = sum(1 for p in existing_symbol_open if p.get("is_dca")) + (
                1 if is_dca_position else 0
            )
        except (TypeError, ValueError, KeyError):
            current_dca_index = 1 if is_dca_position else 0

        position = {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "tp_price": tp_price,  # для обратной совместимости
            "tp1": tp1_price,
            "tp2": tp2_price,
            "qty": qty,
            "leverage": position_leverage,
            "risk_pct": risk_pct,
            "risk_amount": float(risk_amount or 0.0),
            "entry_time": get_utc_now().isoformat(),
            "pnl": 0,
            "pnl_pct": 0,
            "status": "open",
            "stage": "open",
            "is_dca": is_dca_position,
            "n_dca": current_dca_index,
        }

        logging.debug(
            "[DEBUG] Создание позиции: %s %s цена=%s qty=%s leverage=%s",
            symbol,
            side,
            entry_price,
            qty,
            position_leverage,
        )
        logging.info("💾 handle_accept_button: позиция создана успешно")

        # Добавляем позицию в список
        if "positions" not in user_data:
            user_data["positions"] = []
        user_data["positions"].append(position)

        # Для совместимости: дублируем в open_positions (некоторые блоки читают оттуда)
        if "open_positions" not in user_data or user_data["open_positions"] is None:
            user_data["open_positions"] = []
        user_data["open_positions"].append(dict(position))

        # Обновляем баланс (если risk_amount не был рассчитан выше, считаем от risk_pct)
        if not risk_amount:
            risk_amount = deposit * (risk_pct / 100)
        user_data["balance"] = deposit - risk_amount
        # Обновляем свободный депозит
        try:
            user_data["free_deposit"] = max(
                0.0,
                float(user_data.get("free_deposit", deposit)) - float((qty or 0) * entry_price),
            )
        except (TypeError, ValueError, KeyError):
            pass

        # Сохраняем данные (бэкап на пользователя) и атомарно обновляем агрегат
        db.save_user_data(user_id, user_data)
        atomic_update_user_aggregate(user_id, user_data)
        logging.info("✅ handle_accept_button: данные пользователя сохранены")

        # Вычисляем notional_usd для использования в логировании и сообщениях
        notional_usd = (qty or 0) * entry_price
        # Надёжный fallback, чтобы сумма входа всегда была показана
        try:
            if notional_usd is None or notional_usd <= 0:
                notional_usd = float(risk_amount or 0.0)
            if notional_usd <= 0:
                # последний резерв — от процента риска
                notional_usd = float(deposit) * (float(risk_pct) / 100.0)
        except (TypeError, ValueError):
            pass
        position["notional"] = float(notional_usd or 0.0)

        # 💾 СОХРАНЕНИЕ TP/SL В signals_log ДЛЯ СИСТЕМЫ МОНИТОРИНГА
        try:
            # Рассчитываем Stop Loss используя ИИ-функцию из signal_live
            sl_price = 0.0
            try:
                # Импортируем функцию динамического расчёта SL
                from src.signals.risk import get_dynamic_sl_level

                # Получаем динамический процент SL на основе ATR с AI-оптимизацией
                sl_pct = get_dynamic_sl_level(
                    df, len(df) - 1, side, base_sl_pct=2.0, symbol=symbol, use_ai_optimization=True
                )

                # Рассчитываем цену SL
                if side == "long":
                    sl_price = entry_price * (1 - sl_pct / 100)  # Для LONG: вниз
                else:
                    sl_price = entry_price * (1 + sl_pct / 100)  # Для SHORT: вверх

                logging.info("🤖 ИИ-расчет SL: %.2f%% для %s, цена=%.8f", sl_pct, symbol, sl_price)
            except (
                ImportError,
                NameError,
                TypeError,
                ValueError,
                KeyError,
                AttributeError,
            ) as sl_err:
                # Фолбэк: стандартный процент ±2%
                logging.warning("⚠️ Ошибка ИИ-расчета SL (%s), используем фолбэк 2%%", sl_err)
                if side == "long":
                    sl_price = entry_price * 0.98  # -2%
                else:
                    sl_price = entry_price * 1.02  # +2%

            # Сохраняем данные сигнала в signals_log для системы мониторинга
            db.insert_signal_log(
                symbol=symbol,
                entry=entry_price,
                stop=sl_price,
                tp1=tp1_price,
                tp2=tp2_price,
                entry_time=get_utc_now().isoformat(),
                leverage_used=position_leverage,
                risk_pct_used=risk_pct,
                entry_amount_usd=notional_usd,
                trade_mode=trade_mode,
                user_id=user_id,
            )
            logging.info(
                "💾 TP/SL сохранены в signals_log: TP1=%.8f, TP2=%.8f, SL=%.8f",
                tp1_price,
                tp2_price,
                sl_price,
            )
        except Exception as save_err:
            logging.error("❌ Ошибка сохранения TP/SL в signals_log: %s", save_err)

        # 🤖 ИИ ОТСЛЕЖИВАНИЕ: Записываем паттерн для обучения
        try:
            # Пробуем разные варианты импорта
            ai_integration = None
            try:
                from ai_integration import ai_integration
            except ImportError:
                try:
                    from src.ai.integration import ai_integration
                except ImportError:
                    try:
                        from src.ai.integration import AIIntegration

                        ai_integration = AIIntegration()
                    except ImportError:
                        pass

            if ai_integration and hasattr(ai_integration, "record_signal_pattern"):
                await ai_integration.record_signal_pattern(
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    tp1_price=tp1_price,
                    tp2_price=tp2_price,
                    risk_pct=risk_pct,
                    leverage=position_leverage,
                    user_id=user_id,
                    is_dca=is_dca_position,
                )
                logging.info("🤖 ИИ: Паттерн сигнала записан для обучения")
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logging.debug(
                "🤖 ИИ: Модуль ai_integration недоступен или ошибка записи паттерна: %s", e
            )

        # Формат без "жесткого" округления для цен
        def _format_price_raw(value: float) -> str:
            try:
                s = f"{float(value):.10f}"  # до 10 знаков после запятой
                s = s.rstrip("0").rstrip(".")
                return s if s else "0"
            except (TypeError, ValueError):
                return str(value)

        # Формируем сообщение подтверждения
        # notional_usd уже вычислен выше (перед сохранением в signals_log)
        # Проценты относительно цены входа
        # Ранее использовались tp1_pct_view/tp2_pct_view для отображения процентов.
        # Сейчас проценты не используются в подтверждении — вычисления удалены для чистоты.

        if is_dca_signal:
            # Рассчитываем новый средний вход с учётом уже открытых лотов по символу
            try:
                existing_positions = [
                    p
                    for p in (user_data.get("positions", []) or [])
                    if p.get("symbol") == symbol and p.get("status", "open") == "open"
                ]
                total_cost = 0.0
                total_qty = 0.0
                for p in existing_positions:
                    ep = float(p.get("entry_price") or 0.0)
                    q = float(p.get("qty") or 0.0)
                    total_cost += ep * q
                    total_qty += q
                # Добавляем текущую DCA-покупку
                total_cost += float(entry_price) * float(qty)
                total_qty += float(qty)
                avg_price_new = (
                    (total_cost / max(1e-9, total_qty)) if total_qty > 0 else float(entry_price)
                )
            except (TypeError, ValueError):
                avg_price_new = float(entry_price)

            # Порядковый номер усреднения
            try:
                dca_index = 1 + sum(1 for p in existing_positions)
            except (TypeError, ValueError):
                dca_index = 1

            # Пересчёты TP1/TP2 и левередж-проценты больше не используются — удалены для чистоты

            dca_text = build_dca_accept_message(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                qty=qty,
                leverage=position_leverage,
                risk_amount=risk_amount,
                tp1_price=tp1_price,
                tp2_price=tp2_price,
                avg_price_new=avg_price_new,
                dca_index=dca_index,
                price_formatter=lambda v: safe_format_price(v, symbol),
            )
            await query.edit_message_text(dca_text, parse_mode="HTML")
        else:
            # Чистые проценты и левередж-проценты больше не используются — упрощено
            # Удаляем неиспользуемые tp1_pct_view/tp2_pct_view переменные из прежней логики

            confirm_text = build_accept_message(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                tp1_price=tp1_price,
                tp2_price=tp2_price,
                qty=qty,
                leverage=position_leverage,
                risk_amount=risk_amount,
                notional_usd=notional_usd,
                price_formatter=lambda v: safe_format_price(v, symbol),
            )

            await query.edit_message_text(confirm_text, parse_mode="HTML")
        logging.info("🎉 handle_accept_button: сигнал успешно принят!")

        # 🤖 АВТОМАТИЧЕСКОЕ ОТКРЫТИЕ ПОЗИЦИИ НА БИРЖЕ
        try:
            # Проверяем, включен ли автоматический режим
            auto_mode = (
                user_data.get("auto_mode", False)
                or user_data.get("signal_acceptance_mode", "manual") == "auto"
            )

            if auto_mode:
                logging.info("🤖 [AUTO] Автоматическое открытие позиции для %s %s", symbol, side)

                # Импортируем AutoExecutionService
                try:
                    from src.database.acceptance import AcceptanceDatabase
                    from src.execution.auto_execution import AutoExecutionService
                except ImportError:
                    try:
                        from acceptance_database import AcceptanceDatabase

                        from src.execution.auto_execution import AutoExecutionService
                    except ImportError:
                        logging.warning(
                            "⚠️ [AUTO] AutoExecutionService недоступен, пропускаем автоматическое открытие"
                        )
                        auto_mode = False

                if auto_mode:
                    try:
                        acceptance_db = AcceptanceDatabase()
                        auto_exec = AutoExecutionService(acceptance_db)

                        # Получаем message_id и chat_id для сохранения в БД
                        message_id = query.message.message_id if query.message else None
                        chat_id = query.message.chat.id if query.message else None

                        # Формируем signal_key
                        entry_time = pl.get("ts", "")
                        signal_key = f"{symbol}_{entry_time}" if entry_time else None

                        # Направление для биржи (BUY/SELL)
                        direction = "BUY" if side.lower() == "long" else "SELL"

                        # Рассчитываем quantity_usdt (сумма входа)
                        quantity_usdt = float(
                            notional_usd or risk_amount or (deposit * (risk_pct / 100))
                        )

                        # Получаем текущую экспозицию пользователя
                        current_exposure = 0.0
                        try:
                            open_positions = user_data.get("open_positions", []) or user_data.get(
                                "positions", []
                            )
                            for pos in open_positions:
                                if pos.get("status") == "open":
                                    pos_notional = float(
                                        pos.get("notional", 0)
                                        or (
                                            float(pos.get("qty", 0))
                                            * float(pos.get("entry_price", 0))
                                        )
                                    )
                                    current_exposure += pos_notional
                        except (TypeError, ValueError, KeyError):
                            pass

                        # Вызываем автоматическое открытие позиции
                        execution_success = await auto_exec.execute_and_open(
                            symbol=symbol,
                            direction=direction,
                            entry_price=entry_price,
                            user_id=user_id,
                            message_id=message_id,
                            chat_id=chat_id,
                            signal_key=signal_key,
                            quantity_usdt=quantity_usdt,
                            user_balance=float(deposit),
                            current_exposure=current_exposure,
                            leverage=position_leverage,
                            sl_price=sl_price if "sl_price" in locals() else None,
                            tp1_price=tp1_price,
                            tp2_price=tp2_price,
                            trade_mode=trade_mode,
                        )

                        if execution_success:
                            logging.info(
                                "✅ [AUTO] Позиция %s %s успешно открыта на бирже",
                                symbol,
                                direction,
                            )
                            # Обновляем сообщение пользователю
                            try:
                                await query.message.reply_text(
                                    f"🤖 <b>Позиция открыта на бирже!</b>\n\n"
                                    f"Символ: <code>{symbol}</code>\n"
                                    f"Направление: <code>{direction}</code>\n"
                                    f"Цена входа: <code>{safe_format_price(entry_price, symbol)}</code>\n"
                                    f"Размер: <code>{quantity_usdt:.2f} USDT</code>",
                                    parse_mode="HTML",
                                )
                            except (TelegramError, BadRequest, RuntimeError):
                                # Игнорируем ошибки отправки уведомлений
                                pass
                        else:
                            logging.warning(
                                "⚠️ [AUTO] Не удалось открыть позицию %s %s на бирже",
                                symbol,
                                direction,
                            )
                            # Уведомляем пользователя об ошибке
                            try:
                                await query.message.reply_text(
                                    "⚠️ <b>Не удалось открыть позицию на бирже</b>\n\n"
                                    "Проверьте:\n"
                                    "• Наличие API ключей биржи\n"
                                    "• Достаточный баланс\n"
                                    "• Настройки биржи\n\n"
                                    "Позиция сохранена локально, но не открыта на бирже.",
                                    parse_mode="HTML",
                                )
                            except (TelegramError, BadRequest, RuntimeError):
                                # Игнорируем ошибки отправки уведомлений
                                pass
                    except Exception as auto_exc:
                        logging.error(
                            "❌ [AUTO] Ошибка автоматического открытия позиции: %s",
                            auto_exc,
                            exc_info=True,
                        )
                        # Не блокируем основной поток, просто логируем ошибку
            else:
                logging.info(
                    "👤 [MANUAL] Режим ручной торговли, позиция не открывается автоматически на бирже"
                )
        except Exception as auto_check_exc:
            logging.warning("⚠️ [AUTO] Ошибка проверки автоматического режима: %s", auto_check_exc)

    except TelegramError as e:
        logging.error("❌ Telegram API ошибка в handle_accept_button: %s", e)
        await query.edit_message_text("❌ Ошибка при принятии сигнала")
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logging.error("💥 Ошибка данных в handle_accept_button: %s", e)
        logging.error(
            "📊 handle_accept_button: данные для отладки: user_id=%s, data='%s'", user_id, data
        )
        await query.edit_message_text("❌ Ошибка при принятии сигнала")


async def handle_close_button(query, user_data, data):
    """Обработчик кнопки закрытия позиции"""
    try:
        # Получаем ID пользователя
        user_id = query.from_user.id

        # Парсим данные позиции (поддержка форматов: close_SYMBOL и close|SYMBOL|PCT)
        close_pct = 100.0
        symbol = None
        if "|" in data:
            try:
                _, symbol, pct_str = data.split("|", 2)
                close_pct = float(pct_str)
            except (ValueError, TypeError):
                await query.edit_message_text("❌ Неверный формат данных позиции")
                return
        else:
            parts = data.split("_")
            if len(parts) < 2:
                await query.edit_message_text("❌ Неверный формат данных позиции")
                return
            symbol = parts[1]

        # Собираем все открытые лоты по символу (FIFO)
        positions = user_data.get("positions", []) or []
        lots = [
            p for p in positions if p.get("symbol") == symbol and p.get("status", "open") == "open"
        ]

        # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ДЛЯ ДИАГНОСТИКИ РУЧНОГО ЗАКРЫТИЯ
        logging.debug(
            "[DEBUG] РУЧНОЕ ЗАКРЫТИЕ: Пользователь %d закрывает позицию %s на %s%%",
            user_id,
            symbol,
            close_pct,
        )
        logging.debug("[DEBUG] РУЧНОЕ ЗАКРЫТИЕ: Всего позиций пользователя: %d", len(positions))
        logging.debug("[DEBUG] РУЧНОЕ ЗАКРЫТИЕ: Открытых позиций по %s: %d", symbol, len(lots))
        for i, lot in enumerate(lots):
            logging.debug(
                "[DEBUG] РУЧНОЕ ЗАКРЫТИЕ: Лот %d: %s %s status=%s qty=%s",
                i,
                lot.get("symbol"),
                lot.get("side"),
                lot.get("status"),
                lot.get("qty"),
            )

        if not lots:
            await query.edit_message_text(f"📭 Нет открытых позиций по {symbol}")
            return

        # Актуальная цена
        try:
            ohlc = get_ohlc_binance_sync(symbol, interval="1m", limit=1)
            current_price = (
                float(ohlc[-1]["close"]) if ohlc else float(lots[0].get("entry_price", 0))
            )
        except (TypeError, ValueError):
            current_price = float(lots[0].get("entry_price", 0))

        # Общий объём и объём к закрытию
        total_qty = sum(float(p.get("qty", 0)) for p in lots)
        close_pct = max(0.0, min(100.0, float(close_pct)))
        qty_to_close = total_qty * (close_pct / 100.0)
        partial_close = close_pct < 100.0

        # Сторона сделки (предполагаем единая для символа)
        side = (lots[0].get("side") or "long").lower()

        # Настройки комиссий
        try:
            from config import FUTURES_TAKER_FEE_PCT, SPOT_TAKER_FEE_PCT

            trade_mode = user_data.get("trade_mode", "spot")
            taker_fee_pct = FUTURES_TAKER_FEE_PCT if trade_mode == "futures" else SPOT_TAKER_FEE_PCT
        except (ImportError, AttributeError):
            taker_fee_pct = 0.0

        # FIFO: сортируем по времени входа, если доступно
        def _lot_dt(p):
            try:
                return (
                    dt.datetime.fromisoformat(p.get("entry_time"))
                    if p.get("entry_time")
                    else dt.datetime.min
                )
            except (ValueError, TypeError, AttributeError):
                return dt.datetime.min

        lots.sort(key=_lot_dt)

        remaining = qty_to_close
        total_pnl = 0.0
        total_fee = 0.0
        total_closed_qty = 0.0
        cost_basis_closed = 0.0  # для % PnL на закрытую часть

        # Закрываем лоты по очереди
        for lot in lots:
            if remaining <= 0:
                break
            lot_qty = float(lot.get("qty", 0))
            if lot_qty <= 0:
                continue
            take_qty = min(lot_qty, remaining)
            entry_price = float(lot.get("entry_price", 0))

            pnl_lot = (
                (current_price - entry_price) * take_qty
                if side == "long"
                else (entry_price - current_price) * take_qty
            )
            fee_lot = (take_qty * current_price) * (taker_fee_pct / 100.0)

            # Обновляем лот
            lot["qty"] = max(0.0, lot_qty - take_qty)
            try:
                lot["notional"] = float(lot["qty"]) * entry_price
            except (TypeError, ValueError):
                pass

            # Если закрываем всё (close 100%) — помечаем лот закрытым
            if not partial_close and abs(lot.get("qty", 0.0)) < 1e-12:
                lot["status"] = "closed"
                lot["close_time"] = get_utc_now().isoformat()

            # История по лоту
            hist = {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "close_price": current_price,
                "closed_qty": take_qty,
                "pnl": pnl_lot - fee_lot,
                "fee": fee_lot,
                "pnl_pct": ((pnl_lot) / max(1e-9, entry_price * take_qty)) * 100.0,
                "result": "PARTIAL_CLOSE" if partial_close else "CLOSE_FIFO",
                "close_time": get_utc_now().isoformat(),
            }
            if "trade_history" not in user_data:
                user_data["trade_history"] = []
            user_data["trade_history"].append(hist)

            # Сводные итоги
            total_pnl += pnl_lot
            total_fee += fee_lot
            total_closed_qty += take_qty
            cost_basis_closed += entry_price * take_qty
            remaining -= take_qty

        # Обновляем баланс и свободный депозит
        user_data["balance"] = (
            float(user_data.get("balance", 0)) + float(total_pnl) - float(total_fee)
        )
        try:
            user_data["free_deposit"] = float(user_data.get("free_deposit", 0)) + float(
                cost_basis_closed
            )
        except (TypeError, ValueError):
            pass

        # Чистим нулевые остатки и закрываем их явно
        for p in positions:
            try:
                if float(p.get("qty", 0)) <= 0 and p.get("status", "open") == "open":
                    p["status"] = "closed"
                    p["close_time"] = get_utc_now().isoformat()
            except (TypeError, ValueError):
                pass

        # Пересобираем open_positions как производную от positions (только qty>0 и status=='open')
        user_data["open_positions"] = [
            p for p in positions if p.get("status", "open") == "open" and float(p.get("qty", 0)) > 0
        ]

        # Также очищаем основной массив positions от позиций с нулевым количеством
        user_data["positions"] = [
            p for p in positions if p.get("status", "open") == "open" and float(p.get("qty", 0)) > 0
        ]

        # ЛОГИРОВАНИЕ ПОСЛЕ ЗАКРЫТИЯ ПОЗИЦИИ
        logging.debug(
            "[DEBUG] РУЧНОЕ ЗАКРЫТИЕ: После закрытия - открытых позиций по %s: %d",
            symbol,
            len([p for p in user_data["open_positions"] if p.get("symbol") == symbol]),
        )
        logging.debug(
            "[DEBUG] РУЧНОЕ ЗАКРЫТИЕ: Всего открытых позиций пользователя: %d",
            len(user_data["open_positions"]),
        )
        for pos in user_data["open_positions"]:
            if pos.get("symbol") == symbol:
                logging.debug(
                    "[DEBUG] РУЧНОЕ ЗАКРЫТИЕ: Остаток позиции: %s %s status=%s qty=%s",
                    pos.get("symbol"),
                    pos.get("side"),
                    pos.get("status"),
                    pos.get("qty"),
                )

        # 🔄 ОБНОВЛЕНИЕ ПАТТЕРНОВ ИИ при закрытии позиции
        try:
            # Пробуем разные варианты импорта
            try:
                from ai_integration import AIIntegration
            except ImportError:
                try:
                    from src.ai.integration import AIIntegration
                except ImportError:
                    raise ImportError("ai_integration module not found")
            ai_integration = AIIntegration()

            # Обновляем паттерны для каждого закрытого лота
            for lot in lots:
                if lot.get("status") == "closed" or float(lot.get("qty", 0)) <= 0:
                    entry_price = float(lot.get("entry_price", 0))
                    side = lot.get("side", "long").upper()

                    # Находим соответствующий history entry для получения точного PnL
                    for hist in user_data.get("trade_history", []):
                        if (
                            hist.get("symbol") == symbol
                            and hist.get("side") == side
                            and abs(float(hist.get("entry_price", 0)) - entry_price) < 0.01
                        ):
                            profit_pct = float(hist.get("pnl_pct", 0))
                            exit_price = float(hist.get("close_price", current_price))

                            await ai_integration.update_pattern_from_closed_trade(
                                symbol=symbol,
                                side=side,
                                entry_price=entry_price,
                                exit_price=exit_price,
                                exit_reason="manual_close",
                                user_id=user_id,
                                profit_pct=profit_pct,
                            )
                            break
        except Exception as e:
            logger.warning("⚠️ Ошибка обновления паттернов при закрытии: %s", e)

        # Сохраняем данные
        db.save_user_data(user_id, user_data)
        atomic_update_user_aggregate(user_id, user_data)

        # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ДАННЫХ ПОСЛЕ РУЧНОГО ЗАКРЫТИЯ
        # Перезагружаем данные пользователей для корректной генерации новых сигналов
        try:
            try:
                from src.utils.user_utils import load_user_data_for_signals
            except ImportError:
                try:
                    from src.utils.user_utils import load_user_data_for_signals
                except ImportError:

                    def load_user_data_for_signals(*args, **kwargs):
                        return {}

            updated_user_data = load_user_data_for_signals()
            if updated_user_data:
                logging.debug(
                    "[DEBUG] РУЧНОЕ ЗАКРЫТИЕ: Данные пользователей обновлены после ручного закрытия позиции %s",
                    symbol,
                )
                logging.info(
                    "🔄 РУЧНОЕ ЗАКРЫТИЕ: Данные пользователей обновлены после ручного закрытия позиции %s",
                    symbol,
                )
        except (RuntimeError, OSError, ValueError, TypeError) as e:
            logging.warning(
                "[WARNING] РУЧНОЕ ЗАКРЫТИЕ: Ошибка обновления данных пользователей: %s",
                e,
                exc_info=True,
            )
            logging.warning("⚠️ РУЧНОЕ ЗАКРЫТИЕ: Ошибка обновления данных пользователей: %s", e)

        # 🤖 ИИ ОТСЛЕЖИВАНИЕ: Записываем результат закрытия позиции
        try:
            # Пробуем разные варианты импорта
            try:
                from ai_integration import AIIntegration
            except ImportError:
                try:
                    from src.ai.integration import AIIntegration
                except ImportError:
                    raise ImportError("ai_integration module not found")
            ai_integration = AIIntegration()

            # Обновляем паттерны для каждого закрытого лота (уже добавлено выше)
            # Дополнительно обновляем через record_position_result если доступно
            if hasattr(ai_integration, "record_position_result"):
                # Рассчитываем среднюю цену входа для закрытых позиций
                avg_entry_price = (
                    cost_basis_closed / max(1e-9, total_closed_qty) if total_closed_qty > 0 else 0
                )
                # Рассчитываем profit_pct для ИИ
                profit_pct = (
                    (total_pnl / max(1e-9, cost_basis_closed)) * 100.0
                    if cost_basis_closed > 0
                    else 0.0
                )

                await ai_integration.record_position_result(
                    user_id=user_id,
                    symbol=symbol,
                    side=side,
                    _entry_price=avg_entry_price,
                    _exit_price=current_price,
                    profit_pct=profit_pct,
                    is_dca=False,  # Обычное закрытие позиции
                )
                logging.info("🤖 ИИ: Результат закрытия позиции записан для обучения")
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logging.error("🤖 ИИ: Ошибка записи результата закрытия: %s", e)

        # 📊 ШАГ 3: Записываем сделку в TradeTracker при ручном закрытии
        try:
            from datetime import datetime

            from trade_tracker import get_trade_tracker

            # Получаем данные из первого закрытого лота
            if lots:
                first_lot = lots[0]
                entry_time_str = first_lot.get("entry_time")

                # Парсим entry_time
                try:
                    if entry_time_str:
                        if isinstance(entry_time_str, str):
                            entry_time = datetime.fromisoformat(
                                entry_time_str.replace("Z", "+00:00")
                            )
                        else:
                            entry_time = get_utc_now()
                    else:
                        entry_time = get_utc_now()
                except (ValueError, AttributeError):
                    entry_time = get_utc_now()

                # Получаем дополнительные данные из active_positions или signals_log
                tp1_price = None
                tp2_price = None
                sl_price = None
                leverage = float(first_lot.get("leverage", 1.0))
                risk_pct = None
                trade_mode = user_data.get("trade_mode", "futures")

                try:
                    # Получаем TP/SL данные из accepted_signals через signal_key
                    import sqlite3

                    with sqlite3.connect("trading.db") as conn:
                        cursor = conn.cursor()

                        # Сначала получаем signal_key из signals_log или active_positions
                        if entry_time_str:
                            cursor.execute(
                                """
                                SELECT signal_key FROM signals_log
                                WHERE user_id = ? AND symbol = ? AND entry_time = ?
                                LIMIT 1
                            """,
                                (str(user_id), symbol, entry_time_str),
                            )

                            signal_key_row = cursor.fetchone()
                            signal_key_for_query = signal_key_row[0] if signal_key_row else None

                            if signal_key_for_query:
                                # Получаем TP/SL из accepted_signals
                                cursor.execute(
                                    """
                                    SELECT tp1_price, tp2_price, sl_price
                                    FROM accepted_signals
                                    WHERE signal_key = ?
                                    LIMIT 1
                                """,
                                    (signal_key_for_query,),
                                )

                                signal_row = cursor.fetchone()
                                if signal_row:
                                    tp1_price, tp2_price, sl_price = signal_row

                        # Получаем leverage и risk_percent из signals_log
                        if entry_time_str:
                            cursor.execute(
                                """
                                SELECT leverage_used, risk_pct_used
                                FROM signals_log
                                WHERE user_id = ? AND symbol = ? AND entry_time = ?
                                LIMIT 1
                            """,
                                (str(user_id), symbol, entry_time_str),
                            )

                            leverage_row = cursor.fetchone()
                            if leverage_row:
                                leverage_from_db, risk_pct_from_db = leverage_row
                                if leverage_from_db:
                                    leverage = float(leverage_from_db)
                                if risk_pct_from_db:
                                    risk_pct = float(risk_pct_from_db)
                except Exception as e:
                    logging.debug("Не удалось получить TP/SL из БД: %s", e)

                # Определяем exit_reason
                exit_reason = "MANUAL"
                if close_pct == 100.0:
                    exit_reason = "MANUAL"  # Полное ручное закрытие
                else:
                    exit_reason = "MANUAL"  # Частичное ручное закрытие

                # Записываем сделку
                tracker = get_trade_tracker()
                position_size_usdt = cost_basis_closed

                # Рассчитываем среднюю цену входа для записи
                calculated_avg_entry = (
                    cost_basis_closed / max(1e-9, total_closed_qty)
                    if total_closed_qty > 0
                    else float(first_lot.get("entry_price", 0))
                )

                await tracker.record_trade(
                    symbol=symbol,
                    direction=side.upper(),
                    entry_price=calculated_avg_entry,
                    exit_price=float(current_price),
                    entry_time=entry_time,
                    exit_time=get_utc_now(),
                    quantity=float(total_closed_qty),
                    position_size_usdt=float(position_size_usdt),
                    leverage=leverage,
                    risk_percent=risk_pct,
                    fees_usd=float(total_fee),
                    exit_reason=exit_reason,
                    tp1_price=float(tp1_price) if tp1_price else None,
                    tp2_price=float(tp2_price) if tp2_price else None,
                    sl_price=float(sl_price) if sl_price else None,
                    signal_key=f"{symbol}_{entry_time.isoformat()}_manual" if entry_time else None,
                    user_id=str(user_id),
                    trade_mode=str(trade_mode),
                )
                logging.info(
                    "✅ Сделка ручного закрытия записана в TradeTracker для %s (%s%%)",
                    symbol,
                    close_pct,
                )
        except Exception as e:
            logging.error(
                "⚠️ Ошибка записи сделки ручного закрытия в TradeTracker: %s", e, exc_info=True
            )

        # Итоговые сообщения (без $ по просьбе пользователя)
        closed_pct_view = close_pct
        pnl_pct_total = (
            (total_pnl / max(1e-9, cost_basis_closed)) * 100.0 if cost_basis_closed > 0 else 0.0
        )
        remain_total_qty = sum(
            float(p.get("qty", 0)) for p in user_data["open_positions"] if p.get("symbol") == symbol
        )

        if partial_close:
            close_text = build_partial_close_message(
                symbol=symbol,
                side=side,
                total_closed_qty=total_closed_qty,
                closed_pct_view=closed_pct_view,
                pnl_after_fee=(total_pnl - total_fee),
                pnl_pct_total=pnl_pct_total,
                total_fee=total_fee,
                remain_total_qty=remain_total_qty,
                new_balance=user_data["balance"],
            )
        else:
            close_text = build_full_close_message(
                symbol=symbol,
                side=side,
                total_closed_qty=total_closed_qty,
                pnl_after_fee=(total_pnl - total_fee),
                pnl_pct_total=pnl_pct_total,
                total_fee=total_fee,
            )

        await query.edit_message_text(close_text, parse_mode="HTML")

    except TelegramError as e:
        logging.error("Telegram API ошибка в handle_close_button: %s", e)
        await query.edit_message_text("❌ Ошибка при закрытии позиции")
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logging.error("Ошибка данных в handle_close_button: %s", e)
        await query.edit_message_text("❌ Ошибка при закрытии позиции")


async def handle_dca_button(query, user_data, data):
    """Обработчик кнопки DCA"""
    try:
        # Получаем ID пользователя
        user_id = query.from_user.id

        # Парсим данные DCA
        parts = data.split("_")
        if len(parts) < 5:
            await query.edit_message_text("❌ Неверный формат данных DCA")
            return

        symbol = parts[1]
        entry_price = float(parts[2])
        tp_price = float(parts[3])
        side = parts[4]
        dca_count = int(parts[5]) if len(parts) > 5 else 1

        # Проверяем данные пользователя
        if not user_data.get("deposit"):
            await query.edit_message_text("❌ Установите баланс командой /set_balance")
            return

        # Рассчитываем параметры DCA
        deposit = user_data["deposit"]
        risk_pct = user_data.get("risk_pct", 2)
        user_leverage = int(user_data.get("leverage", 1) or 1)

        # Получаем существующие позиции по символу
        positions = user_data.get("positions", [])
        symbol_positions = [
            pos for pos in positions if pos.get("symbol") == symbol and pos.get("status") == "open"
        ]

        if not symbol_positions:
            await query.edit_message_text(f"❌ Нет открытых позиций по {symbol}")
            return

        # Рассчитываем среднюю цену и количество
        total_qty = sum(pos.get("qty", 0) for pos in symbol_positions)
        avg_price = (
            sum(pos.get("entry_price", 0) * pos.get("qty", 0) for pos in symbol_positions)
            / total_qty
        )

        # Рассчитываем следующее количество для DCA
        remaining_risk = deposit * (risk_pct / 100) * (1 - dca_count * 0.1)
        next_qty = remaining_risk / entry_price

        # Фолбэк на qty
        try:
            if not next_qty or float(next_qty) <= 0:
                next_qty = (deposit * (risk_pct / 100.0)) / max(1e-9, entry_price)
        except (TypeError, ValueError):
            pass

        # Создаем новую позицию DCA
        dca_position = {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "tp_price": tp_price,
            "qty": next_qty,
            "leverage": user_leverage,
            "entry_time": get_utc_now().isoformat(),
            "pnl": 0,
            "pnl_pct": 0,
            "status": "open",
            "stage": "open",
            "dca_count": dca_count,
        }

        # Добавляем позицию
        user_data["positions"].append(dca_position)

        # --- ЖЁСТКАЯ СИНХРОНИЗАЦИЯ TP ПОСЛЕ DCA ---
        try:
            # Пересчитываем объединённую среднюю и динамические TP для символа
            df = get_ohlc_binance_sync(symbol, interval="1h", limit=250)
            df = pd.DataFrame(df)
            current_index = len(df) - 1
            side_norm = (side or "long").lower()

            # Базовые динамические TP
            trade_mode = user_data.get("trade_mode", "spot")
            tp1_pct, tp2_pct = get_dynamic_tp_levels(
                df, current_index, side_norm, trade_mode=trade_mode, adjust_for_fees=True
            )

            # Унификация TP по всем открытым позициям символа
            u_tp1_pct, u_tp2_pct = calculate_unified_tp_for_symbol(
                user_data, symbol, entry_price, df, current_index
            )
            tp1_pct = min(tp1_pct, u_tp1_pct)
            tp2_pct = min(tp2_pct, u_tp2_pct)

            # Конвертируем в цены от обновлённой средней
            # Пересчитываем среднюю заново с учётом только что добавленной DCA позиции
            positions = user_data.get("positions", []) or []
            symbol_positions = [
                p
                for p in positions
                if p.get("symbol") == symbol and p.get("status", "open") == "open"
            ]
            total_qty_new = sum(float(p.get("qty", 0)) for p in symbol_positions)
            avg_price_new = sum(
                float(p.get("entry_price", 0)) * float(p.get("qty", 0)) for p in symbol_positions
            ) / max(1e-9, total_qty_new)

            if side_norm == "long":
                tp1_price_new = avg_price_new * (1 + tp1_pct / 100.0)
                tp2_price_new = avg_price_new * (1 + tp2_pct / 100.0)
            else:
                tp1_price_new = avg_price_new * (1 - tp1_pct / 100.0)
                tp2_price_new = avg_price_new * (1 - tp2_pct / 100.0)

            # Обновляем TP во всех открытых позициях символа
            for p in symbol_positions:
                old_tp1 = p.get("tp1")
                old_tp2 = p.get("tp2")
                p["tp1"] = tp1_price_new
                p["tp2"] = tp2_price_new
                # КРИТИЧЕСКИ ВАЖНО: сбрасываем флаги и stage для отслеживания новых TP
                p["tp1_notified"] = False  # Сбрасываем флаг уведомления TP1
                p["stage"] = "open"  # Сбрасываем stage на 'open' для отслеживания новых TP
                logging.info(
                    "[DCA] %s: Обновлены TP после усреднения: "
                    "TP1: %.6f → %.6f, "
                    "TP2: %.6f → %.6f, "
                    "Средняя цена: %.6f",
                    symbol,
                    old_tp1,
                    tp1_price_new,
                    old_tp2,
                    tp2_price_new,
                    avg_price_new,
                )
        except (KeyError, ValueError, TypeError, ZeroDivisionError):
            pass

        # Обновляем баланс
        try:
            user_data["balance"] = float(user_data.get("balance", deposit)) - float(remaining_risk)
        except (TypeError, ValueError):
            pass

        # Сохраняем данные
        db.save_user_data(user_id, user_data)

        # Формируем сообщение
        notional_usd = float(next_qty) * float(entry_price)
        # Используем правильную среднюю цену после DCA
        try:
            # Пересчитываем среднюю цену с учетом всех позиций включая новую DCA
            positions = user_data.get("positions", []) or []
            symbol_positions = [
                p
                for p in positions
                if p.get("symbol") == symbol and p.get("status", "open") == "open"
            ]
            total_qty_new = sum(float(p.get("qty", 0)) for p in symbol_positions)
            avg_price_new = sum(
                float(p.get("entry_price", 0)) * float(p.get("qty", 0)) for p in symbol_positions
            ) / max(1e-9, total_qty_new)
        except (ValueError, TypeError, ZeroDivisionError):
            avg_price_new = avg_price  # Fallback на старую среднюю цену

        # Получаем новые TP уровни для отображения
        try:
            tp1_price_new = None
            tp2_price_new = None
            for p in symbol_positions:
                if p.get("tp1") and p.get("tp2"):
                    tp1_price_new = p.get("tp1")
                    tp2_price_new = p.get("tp2")
                    break
        except (ValueError, TypeError, KeyError):
            tp1_price_new = None
            tp2_price_new = None

        dca_text = (
            "📈 <b>DCA позиция добавлена!</b>\n\n"
            f"🔸 Символ: <code>{symbol}</code>\n"
            f"🔸 DCA #<code>{dca_count}</code>\n"
            f"🔸 Цена входа: <code>${safe_format_price(entry_price, symbol)}</code>\n"
            f"🔸 Количество: <code>{next_qty:.6f}</code>\n"
            f"🔸 Сумма входа: <code>${notional_usd:.2f}</code>\n"
            f"🔸 Средняя цена: <code>${safe_format_price(avg_price_new, symbol)}</code>\n"
        )

        # Добавляем информацию о TP если они рассчитаны
        if tp1_price_new and tp2_price_new:
            tp1_pct = (
                ((tp1_price_new - avg_price_new) / avg_price_new * 100) if avg_price_new > 0 else 0
            )
            tp2_pct = (
                ((tp2_price_new - avg_price_new) / avg_price_new * 100) if avg_price_new > 0 else 0
            )
            dca_text += (
                f"🔸 TP1: <code>${safe_format_price(tp1_price_new, symbol)}</code> (+{tp1_pct:.2f}%)\n"
                f"🔸 TP2: <code>${safe_format_price(tp2_price_new, symbol)}</code> (+{tp2_pct:.2f}%)\n\n"
            )

        dca_text += (
            f"⚠️ <b>Внимание:</b> на <b>TP1</b> фиксируем <b>50%</b> позиции, остаток держим до <b>TP2</b>\n\n"
            f"⏰ Время: <code>{get_utc_now().strftime('%H:%M:%S')}</code>"
        )

        await query.edit_message_text(dca_text, parse_mode="HTML")

    except TelegramError as e:
        logging.error("Telegram API ошибка в handle_dca_button: %s", e)
        await query.edit_message_text("❌ Ошибка при добавлении DCA позиции")
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logging.error("Ошибка данных в handle_dca_button: %s", e)
        await query.edit_message_text("❌ Ошибка при добавлении DCA позиции")


async def handle_open_positions_button(query, user_data, data):
    """Обработчик кнопки 'ОТКРЫТЫЕ ПОЗИЦИИ'"""
    try:
        # Получаем открытые позиции
        positions = user_data.get("positions", []) or user_data.get("open_positions", [])
        open_positions = [pos for pos in positions if pos.get("status") == "open"]

        if not open_positions:
            await query.edit_message_text("📭 У вас нет открытых позиций")
            return

        # Формируем сообщение с позициями и кнопками
        message = "📊 <b>ОТКРЫТЫЕ ПОЗИЦИИ</b>\n\n"

        keyboard = []
        for i, pos in enumerate(open_positions):
            symbol = pos.get("symbol", "N/A")
            side = pos.get("side", "N/A")
            qty = pos.get("qty", 0)
            entry_price = pos.get("entry_price", 0)

            message += f"<b>{i + 1}.</b> {symbol} ({side})\n"
            message += f"   📦 Количество: {qty:.6f}\n"
            message += f"   💰 Цена входа: {entry_price:.6f}\n\n"

            # Добавляем кнопки для каждой позиции
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🔒 Закрыть 50% {symbol}", callback_data=f"close|{symbol}|50"
                    ),
                    InlineKeyboardButton(
                        f"🔒 Закрыть 100% {symbol}", callback_data=f"close|{symbol}|100"
                    ),
                ]
            )

        # Добавляем кнопку "Закрыть все"
        keyboard.append(
            [InlineKeyboardButton("🔒 ЗАКРЫТЬ ВСЕ ПОЗИЦИИ", callback_data="confirm_close_all")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logging.error("❌ Ошибка в handle_open_positions_button: %s", e)
        await query.edit_message_text("❌ Ошибка при получении позиций")


async def handle_confirm_button(query, user_data, data):
    """Обработчик кнопки подтверждения"""
    try:
        # Парсим данные подтверждения
        parts = data.split("_")
        if len(parts) < 2:
            await query.edit_message_text("❌ Неверный формат данных подтверждения")
            return

        action = parts[1]

        if action == "close_all":
            await handle_confirm_close_all(query, user_data)
        else:
            await query.edit_message_text("❌ Неизвестное действие")

    except TelegramError as e:
        logging.error("Telegram API ошибка в handle_confirm_button: %s", e)
        await query.edit_message_text("❌ Ошибка при подтверждении")
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logging.error("Ошибка данных в handle_confirm_button: %s", e)
        await query.edit_message_text("❌ Ошибка при подтверждении")


async def handle_confirm_close_all(query, user_data):
    """Обработчик подтверждения закрытия всех позиций"""
    try:
        # Получаем ID пользователя
        user_id = query.from_user.id

        positions = user_data.get("positions", [])
        open_positions = [pos for pos in positions if pos.get("status") == "open"]

        if not open_positions:
            await query.edit_message_text("📭 Нет открытых позиций для закрытия")
            return

        # Закрываем все позиции
        total_pnl = 0
        closed_count = 0

        for pos in open_positions:
            pos["status"] = "closed"
            pos["close_time"] = get_utc_now().isoformat()

            # Упрощенный расчет PnL
            entry_price = pos["entry_price"]
            current_price = entry_price  # В реальности нужно получить текущую цену
            qty = pos["qty"]
            side = pos["side"]

            if side == "long":
                pnl = (current_price - entry_price) * qty
            else:
                pnl = (entry_price - current_price) * qty

            pos["pnl"] = pnl
            pos["pnl_pct"] = (pnl / (entry_price * qty)) * 100
            total_pnl += pnl
            closed_count += 1

        # Обновляем баланс
        user_data["balance"] += total_pnl

        # Перемещаем в историю
        if "trade_history" not in user_data:
            user_data["trade_history"] = []
        user_data["trade_history"].extend(open_positions)

        # Очищаем открытые позиции
        user_data["positions"] = []

        # Сохраняем данные
        db.save_user_data(user_id, user_data)
        atomic_update_user_aggregate(user_id, user_data)

        # Формируем сообщение
        close_all_text = f"""
🔒 *Все позиции закрыты*

📊 Закрыто позиций: {closed_count}
💰 Общий PnL: ${total_pnl:.2f}
💳 Новый баланс: ${user_data["balance"]:.2f}

⏰ Время: {get_utc_now().strftime("%H:%M:%S")}
"""

        await query.edit_message_text(close_all_text, parse_mode="HTML")

    except TelegramError as e:
        logging.error("Telegram API ошибка в handle_confirm_close_all: %s", e)
        await query.edit_message_text("❌ Ошибка при закрытии всех позиций")
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logging.error("Ошибка данных в handle_confirm_close_all: %s", e)
        await query.edit_message_text("❌ Ошибка при закрытии всех позиций")


async def handle_setup_button(query, user_data, data):
    """Обработчик кнопок настройки"""
    try:
        user_id = query.from_user.id
        logging.info("🔧 handle_setup_button: user_id=%s, data=%s", user_id, data)

        # Парсим данные кнопки
        parts = data.split("_")
        logging.info("🔧 parts: %s", parts)

        if len(parts) < 4:
            logging.error("❌ Неверный формат данных настройки: %s", data)
            await query.edit_message_text("❌ Неверный формат данных настройки")
            return

        action = (
            parts[1] + "_" + parts[2] + "_" + parts[3]
        )  # setup_trade_mode_spot -> trade_mode_spot
        logging.info("🔧 action: %s", action)

        if action == "trade_mode_spot":
            logging.info("🔧 Обрабатываем trade_mode_spot")
            user_data["trade_mode"] = "spot"

            # Рассчитываем плечо для SPOT торговли
            deposit = user_data.get("deposit", 0)
            filter_mode = user_data.get("filter_mode", "soft")
            user_data["leverage"] = calculate_user_leverage(deposit, "spot", filter_mode)

            # Добавляем недостающие параметры
            if "total_risk_amount" not in user_data:
                user_data["total_risk_amount"] = 0
            if "free_deposit" not in user_data:
                user_data["free_deposit"] = user_data.get("deposit", 0)
            if "total_profit" not in user_data:
                user_data["total_profit"] = 0
            if "open_positions" not in user_data:
                user_data["open_positions"] = []
            if "accepted_signals" not in user_data:
                user_data["accepted_signals"] = []
            if "trade_history" not in user_data:
                user_data["trade_history"] = []

            # Сохраняем данные пользователя
            try:
                if db and hasattr(db, "save_user_data"):
                    db.save_user_data(user_id, user_data)
            except Exception as e:
                logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)

            # Переходим к следующему шагу - выбор режима фильтров
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔴 Строгий", callback_data="setup_filter_mode_strict"
                        ),
                        InlineKeyboardButton("🟢 Мягкий", callback_data="setup_filter_mode_soft"),
                    ]
                ]
            )

            await query.message.reply_text(
                "✅ <b>Режим торговли: SPOT</b>\n\n"
                "🎯 <b>Шаг 3: Выберите режим фильтров</b>\n\n"
                "🔴 <b>Строгий</b> — меньше сигналов, но качественные\n"
                "🟢 <b>Мягкий</b> — больше сигналов, более активная торговля\n\n"
                "Выберите режим:",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            await query.edit_message_reply_markup(reply_markup=None)
            return

        elif action == "trade_mode_futures":
            logging.info("🔧 Обрабатываем trade_mode_futures")
            user_data["trade_mode"] = "futures"

            # Рассчитываем плечо для FUTURES торговли
            deposit = user_data.get("deposit", 0)
            filter_mode = user_data.get("filter_mode", "soft")
            user_data["leverage"] = calculate_user_leverage(deposit, "futures", filter_mode)

            # Добавляем недостающие параметры
            if "total_risk_amount" not in user_data:
                user_data["total_risk_amount"] = 0
            if "free_deposit" not in user_data:
                user_data["free_deposit"] = user_data.get("deposit", 0)
            if "total_profit" not in user_data:
                user_data["total_profit"] = 0
            if "open_positions" not in user_data:
                user_data["open_positions"] = []
            if "accepted_signals" not in user_data:
                user_data["accepted_signals"] = []
            if "trade_history" not in user_data:
                user_data["trade_history"] = []

            # Сохраняем данные пользователя
            try:
                if db and hasattr(db, "save_user_data"):
                    db.save_user_data(user_id, user_data)
            except Exception as e:
                logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)

            # Переходим к следующему шагу - выбор режима фильтров
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔴 Строгий", callback_data="setup_filter_mode_strict"
                        ),
                        InlineKeyboardButton("🟢 Мягкий", callback_data="setup_filter_mode_soft"),
                    ]
                ]
            )

            await query.message.reply_text(
                "✅ <b>Режим торговли: FUTURES</b>\n\n"
                "⚠️ <b>Плечо рассчитывается автоматически!</b>\n"
                "Система учитывает волатильность и рыночные условия\n\n"
                "🎯 <b>Шаг 3: Выберите режим фильтров</b>\n\n"
                "🔴 <b>Строгий</b> — меньше сигналов, но качественные\n"
                "🟢 <b>Мягкий</b> — больше сигналов, более активная торговля\n\n"
                "Выберите режим:",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            await query.edit_message_reply_markup(reply_markup=None)
            return

        elif action == "filter_mode_strict":
            logging.info("🔧 Обрабатываем filter_mode_strict")
            user_data["filter_mode"] = "strict"
            user_data["news_filter_mode"] = "conservative"

            # Пересчитываем плечо с новым режимом фильтров
            deposit = user_data.get("deposit", 0)
            trade_mode = user_data.get("trade_mode", "spot")
            user_data["leverage"] = calculate_user_leverage(deposit, trade_mode, "strict")

            # Добавляем недостающие параметры
            if "total_risk_amount" not in user_data:
                user_data["total_risk_amount"] = 0
            if "free_deposit" not in user_data:
                user_data["free_deposit"] = user_data.get("deposit", 0)
            if "total_profit" not in user_data:
                user_data["total_profit"] = 0
            if "open_positions" not in user_data:
                user_data["open_positions"] = []
            if "accepted_signals" not in user_data:
                user_data["accepted_signals"] = []
            if "trade_history" not in user_data:
                user_data["trade_history"] = []

            # Удаляем setup_step и фиксируем завершение настройки
            if "setup_step" in user_data:
                del user_data["setup_step"]
            user_data["setup_completed"] = True
            # Сохраняем данные пользователя (идемпотентно)
            try:
                if db and hasattr(db, "save_user_data"):
                    db.save_user_data(user_id, user_data)
            except Exception as e:
                logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)

            # Завершаем настройку
            deposit = user_data.get("deposit", 0)
            trade_mode = user_data.get("trade_mode", "spot")
            leverage = user_data.get("leverage", 1)

            await query.message.reply_text(
                f"✅ <b>НАСТРОЙКА ЗАВЕРШЕНА!</b>\n\n"
                f"💰 Депозит: <code>{deposit}</code> USDT\n"
                f"📈 Режим: <code>{trade_mode.upper()}</code>\n"
                f"🎯 Фильтры: <code>Строгий</code>\n"
                f"⚡ Плечо: <code>{leverage}x</code>\n\n"
                f"🚀 <b>Бот готов к работе!</b>\n\n"
                f"📋 Основные команды:\n"
                f"• /balance — ваш баланс\n"
                f"• /positions — открытые позиции\n"
                f"• /help — все команды\n\n"
                f"⚠️ Риск и плечо рассчитываются автоматически\n"
                f"📡 Сигналы будут приходить автоматически",
                parse_mode="HTML",
            )
            await query.edit_message_reply_markup(reply_markup=None)
            return

        elif action == "filter_mode_soft":
            logging.info("🔧 Обрабатываем filter_mode_soft")
            user_data["filter_mode"] = "soft"
            user_data["news_filter_mode"] = "aggressive"

            # Пересчитываем плечо с новым режимом фильтров
            deposit = user_data.get("deposit", 0)
            trade_mode = user_data.get("trade_mode", "spot")
            user_data["leverage"] = calculate_user_leverage(deposit, trade_mode, "soft")

            # Добавляем недостающие параметры
            if "total_risk_amount" not in user_data:
                user_data["total_risk_amount"] = 0
            if "free_deposit" not in user_data:
                user_data["free_deposit"] = user_data.get("deposit", 0)
            if "total_profit" not in user_data:
                user_data["total_profit"] = 0
            if "open_positions" not in user_data:
                user_data["open_positions"] = []
            if "accepted_signals" not in user_data:
                user_data["accepted_signals"] = []
            if "trade_history" not in user_data:
                user_data["trade_history"] = []

            # Удаляем setup_step и фиксируем завершение настройки
            if "setup_step" in user_data:
                del user_data["setup_step"]
            user_data["setup_completed"] = True
            # Сохраняем данные пользователя (идемпотентно)
            try:
                if db and hasattr(db, "save_user_data"):
                    db.save_user_data(user_id, user_data)
            except Exception as e:
                logging.warning("⚠️ Не удалось сохранить user_data в БД: %s", e)

            # Завершаем настройку
            deposit = user_data.get("deposit", 0)
            trade_mode = user_data.get("trade_mode", "spot")
            leverage = user_data.get("leverage", 1)

            await query.message.reply_text(
                f"✅ <b>НАСТРОЙКА ЗАВЕРШЕНА!</b>\n\n"
                f"💰 Депозит: <code>{deposit}</code> USDT\n"
                f"📈 Режим: <code>{trade_mode.upper()}</code>\n"
                f"🎯 Фильтры: <code>Мягкий</code>\n"
                f"⚡ Плечо: <code>{leverage}x</code>\n\n"
                f"🚀 <b>Бот готов к работе!</b>\n\n"
                f"📋 Основные команды:\n"
                f"• /balance — ваш баланс\n"
                f"• /positions — открытые позиции\n"
                f"• /help — все команды\n\n"
                f"⚠️ Риск и плечо рассчитываются автоматически\n"
                f"📡 Сигналы будут приходить автоматически",
                parse_mode="HTML",
            )
            await query.edit_message_reply_markup(reply_markup=None)
            return

        else:
            logging.error("❌ Неизвестная кнопка настройки: %s", action)
            await query.edit_message_text(f"❌ Неизвестная кнопка настройки: {action}")

    except TelegramError as e:
        logging.error("Telegram API ошибка в handle_setup_button: %s", e)
        await query.edit_message_text("❌ Ошибка при настройке")
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logging.error("Ошибка данных в handle_setup_button: %s", e, exc_info=True)
        try:
            await query.edit_message_text("❌ Ошибка при настройке")
        except (TelegramError, BadRequest, RuntimeError, AttributeError):
            # Игнорируем ошибки отправки сообщений об ошибках
            pass


async def error_handler(_update, context):
    """Обработчик ошибок"""
    try:
        error = getattr(context, "error", None)
        error_type = type(error).__name__ if error else "None"
        error_msg = str(error) if error else "No error message"
        logging.error("Ошибка в боте: %s (%s): %s", error_type, error_msg, error)

        # Логируем полный traceback для диагностики
        import sys
        import traceback

        if error:
            exc_type, exc_value, exc_traceback = type(error), error, error.__traceback__
            if exc_traceback is None:
                exc_traceback = sys.exc_info()[2]
            full_traceback = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            logging.error("Полный traceback ошибки:\n%s", full_traceback)

        # Если update доступен, пытаемся уведомить пользователя
        # ВАЖНО: проверяем все возможные варианты получения сообщения
        message_to_reply = None
        if _update:
            # Пробуем разные способы получить сообщение
            if hasattr(_update, "message") and _update.message:
                message_to_reply = _update.message
            elif hasattr(_update, "effective_message") and _update.effective_message:
                message_to_reply = _update.effective_message
            elif (
                hasattr(_update, "callback_query")
                and _update.callback_query
                and hasattr(_update.callback_query, "message")
            ):
                message_to_reply = _update.callback_query.message

        if message_to_reply:
            try:
                reply_method = getattr(message_to_reply, "reply_text", None)
                if reply_method and callable(reply_method):
                    await reply_method(
                        "❌ Произошла ошибка при обработке команды. Попробуйте позже."
                    )
            except Exception as notify_err:
                logging.error(
                    "Ошибка уведомления пользователя в error_handler: %s (тип: %s)",
                    notify_err,
                    type(notify_err).__name__,
                )
                # Пробуем альтернативный способ - через callback_query.answer
                try:
                    if _update and hasattr(_update, "callback_query") and _update.callback_query:
                        await _update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
                except Exception:
                    pass
    except Exception as e:
        logging.error(
            "Критическая ошибка в error_handler: %s (тип: %s)", e, type(e).__name__, exc_info=True
        )


async def backtest_cmd(update, context):
    """/backtest <symbol> [interval] [days] [mode]

    mode: replay (по умолчанию) | strategy
    """
    try:
        args = context.args or []
        symbol = (args[0] if len(args) > 0 else "BTCUSDT").upper()
        interval = args[1] if len(args) > 1 else "1h"
        days = int(args[2]) if len(args) > 2 else 30
        # режим фиксируем как replay
    except (ValueError, TypeError, AttributeError):
        await update.message.reply_text(
            "Использование: /backtest <symbol> [interval] [days] [replay|strategy]"
        )
        return

    await update.message.reply_text("⏳ Запускаю бэктест, подождите...")
    # Стратегия только наша (replay_db)

    # replay (наша стратегия по БД)
    result = await asyncio.to_thread(run_backtest_replay_db, symbol, interval, days)
    if not result.get("ok"):
        await update.message.reply_text(f"❌ {result.get('error', 'Ошибка')}")
        return

    signals = max(1, int(result.get("signals", 0)))
    tp1 = int(result.get("tp1", 0))
    tp2 = int(result.get("tp2", 0))
    sl = int(result.get("sl", 0))
    pnl = float(result.get("pnl", 0.0))
    mae_avg = float(result.get("mae_avg_pct", 0.0))
    mfe_avg = float(result.get("mfe_avg_pct", 0.0))
    avg_dur_sec = float(result.get("avg_duration_sec", 0.0))
    avg_dur_min = avg_dur_sec / 60.0 if avg_dur_sec else 0.0
    tp1_rate = 100.0 * tp1 / signals if signals else 0.0
    tp2_rate = 100.0 * tp2 / signals if signals else 0.0
    sl_rate = 100.0 * sl / signals if signals else 0.0
    avg_pnl = pnl / signals if signals else 0.0

    text = (
        "📈 <b>Backtest Summary</b>\n\n"
        f"Символ: <code>{result['symbol']}</code>\n"
        f"Интервал: <code>{result['interval']}</code>\n"
        f"Свечей: <code>{result.get('bars', '?')}</code>\n"
        f"Период: <code>{result.get('start', '?')}</code> → <code>{result.get('end', '?')}</code>\n"
        f"Режим: <code>replay_db</code>\n"
        f"Сигналов: <code>{signals}</code>\n"
        f"TP1/TP2/SL: <code>{tp1}</code>/<code>{tp2}</code>/<code>{sl}</code>\n"
        f"Доли: <code>{tp1_rate:.1f}%</code>/<code>{tp2_rate:.1f}%</code>/<code>{sl_rate:.1f}%</code>\n"
        f"PNL (ед.): <code>{pnl:.4f}</code> | Ср.: <code>{avg_pnl:.4f}</code>\n"
        f"MFE avg: <code>{mfe_avg:.2f}%</code> | MAE avg: <code>{mae_avg:.2f}%</code>\n"
        f"Avg duration: <code>{avg_dur_min:.1f} мин</code>\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# Обработчики системы принятия сигналов
async def handle_signal_acceptance_button(query, user_data, data):
    """Обработчик кнопки принятия сигнала из системы принятия сигналов"""
    try:
        if not SIGNAL_ACCEPTANCE_AVAILABLE:
            await query.answer("❌ Система принятия сигналов недоступна")
            return

        # Парсим данные кнопки: accept_SYMBOL_TIMESTAMP
        parts = data.split("_")
        logging.info("🔍 Парсинг кнопки: data='%s', parts=%s", data, parts)

        if len(parts) < 3:
            logging.error("❌ Неверный формат кнопки: %s, parts=%s", data, parts)
            await query.answer("❌ Неверный формат кнопки")
            return

        symbol = parts[1]
        signal_timestamp = None
        try:
            signal_timestamp = float(parts[2])
            logging.info("🔍 Парсинг timestamp: %s -> %s", parts[2], signal_timestamp)
        except ValueError as e:
            logging.error("❌ Ошибка парсинга timestamp: %s, error: %s", parts[2], e)
            await query.answer("❌ Неверный формат timestamp")
            return

        user_id = str(query.from_user.id)
        logging.info(
            "🎯 Парсинг успешен: symbol=%s, timestamp=%s, user_id=%s",
            symbol,
            signal_timestamp,
            user_id,
        )

        # Получаем глобальные переменные системы принятия сигналов
        try:
            global signal_acceptance_manager
            if not signal_acceptance_manager:
                # Пытаемся получить из signal_live
                try:
                    from signal_live import signal_acceptance_manager as sam

                    signal_acceptance_manager = sam
                except (ImportError, AttributeError):
                    pass

            logging.info("🔍 signal_acceptance_manager: %s", signal_acceptance_manager)

            if not signal_acceptance_manager:
                logging.error("❌ signal_acceptance_manager не инициализирован")
                await query.answer("❌ Система принятия сигналов не инициализирована")
                return

            # Проверяем статус сигнала перед попыткой принять
            try:
                import sqlite3

                with sqlite3.connect("trading.db") as conn:
                    cursor = conn.cursor()
                    signal_key = f"{symbol}_{signal_timestamp}"
                    cursor.execute(
                        """
                        SELECT status, accepted_by FROM accepted_signals
                        WHERE signal_key = ?
                    """,
                        (signal_key,),
                    )
                    result = cursor.fetchone()

                    if not result:
                        await query.answer("❌ Сигнал не найден")
                        return

                    status, accepted_by = result

                    if status == "accepted":
                        if accepted_by == user_id:
                            await query.answer("✅ Сигнал уже принят вами")
                        else:
                            await query.answer("❌ Сигнал уже принят другим пользователем")
                        return
                    elif status != "pending":
                        await query.answer(f"❌ Сигнал в статусе: {status}")
                        return
            except Exception as e:
                logging.error("❌ Ошибка проверки статуса сигнала: %s", e)
                await query.answer("❌ Ошибка проверки статуса")
                return

            # Принимаем сигнал
            logging.info(
                "🎯 Вызываем accept_signal для %s, %s, %s", symbol, signal_timestamp, user_id
            )
            success = await signal_acceptance_manager.accept_signal(
                symbol, signal_timestamp, user_id
            )

            if success:
                await query.answer("✅ Сигнал принят!")
                logging.info("✅ Сигнал %s принят пользователем %s", symbol, user_id)
            else:
                await query.answer("❌ Ошибка принятия сигнала")
                logging.warning(
                    "❌ Не удалось принять сигнал %s для пользователя %s", symbol, user_id
                )

        except Exception as e:
            logging.error("❌ Ошибка обработки кнопки принятия сигнала: %s", e)
            await query.answer("❌ Произошла ошибка")

    except Exception as e:
        logging.error("❌ Критическая ошибка в handle_signal_acceptance_button: %s", e)
        await query.answer("❌ Произошла ошибка")


async def handle_position_close_button(query, user_data, data):
    """Обработчик кнопки закрытия позиции из системы принятия сигналов"""
    try:
        if not SIGNAL_ACCEPTANCE_AVAILABLE:
            await query.answer("❌ Система принятия сигналов недоступна")
            return

        # Парсим данные кнопки: close_SYMBOL_TIMESTAMP
        parts = data.split("_")
        if len(parts) < 3:
            await query.answer("❌ Неверный формат кнопки")
            return

        symbol = parts[1]
        signal_timestamp = float(parts[2])
        user_id = str(query.from_user.id)

        # Получаем глобальные переменные системы принятия сигналов
        try:
            try:
                from signal_live import signal_acceptance_manager as sam
            except (ImportError, AttributeError):
                sam = None

            if not sam:
                await query.answer("❌ Система принятия сигналов не инициализирована")
                return

            # Закрываем позицию
            if sam and hasattr(sam, "close_position"):
                close_method = getattr(sam, "close_position", None)
                if close_method and callable(close_method):
                    success = await close_method(symbol, signal_timestamp, user_id)
                else:
                    logging.error("❌ close_position не является callable: %s", type(close_method))
                    await query.answer("❌ Ошибка: метод close_position недоступен")
                    return
            else:
                logging.error("❌ sam или close_position недоступны")
                await query.answer("❌ Система закрытия позиций недоступна")
                return

            if success:
                await query.answer("📊 Позиция закрыта!")
                logging.info("📊 Позиция %s закрыта пользователем %s", symbol, user_id)
            else:
                await query.answer("❌ Ошибка закрытия позиции")
                logging.warning(
                    "❌ Не удалось закрыть позицию %s для пользователя %s", symbol, user_id
                )

        except Exception as e:
            logging.error("❌ Ошибка обработки кнопки закрытия позиции: %s", e)
            await query.answer("❌ Произошла ошибка")

    except Exception as e:
        logging.error("❌ Критическая ошибка в handle_position_close_button: %s", e)
        await query.answer("❌ Произошла ошибка")
