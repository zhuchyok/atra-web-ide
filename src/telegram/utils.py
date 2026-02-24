import ast
import inspect
import json
import logging
import os
import time
import types
from datetime import datetime
from functools import wraps

import pandas as pd

from config import TELEGRAM_CHAT_IDS
from src.execution.exchange_api import get_symbol_precision
from src.shared.utils.datetime_utils import get_utc_now
from telegram.error import BadRequest, TelegramError


async def safe_edit_message_text(query, text: str, **kwargs):
    """Безопасное редактирование текста сообщения:
    - пропускает, если текст/markup не меняются
    - подавляет 'Message is not modified'
    - корректно обрабатывает устаревшие callback-запросы
    """
    try:
        msg = getattr(query, "message", None)
        if msg is None:
            return

        # Если есть parse_mode в kwargs, проверяем его
        parse_mode = kwargs.get("parse_mode", "HTML")

        current_text = getattr(msg, "text", None) or getattr(msg, "caption", None) or ""
        new_text = text or ""

        # Проверяем, меняется ли текст и разметка
        same_text = current_text == new_text
        current_markup = getattr(msg, "reply_markup", None)
        new_markup = kwargs.get("reply_markup")

        # Сравнение markup может быть сложным, используем базовое сравнение
        same_markup = (current_markup == new_markup) or (
            new_markup is None and current_markup is None
        )

        if same_text and same_markup:
            return

        await query.edit_message_text(text, **kwargs)

    except BadRequest as e:
        err = str(e)
        if "Message is not modified" in err:
            return
        if "Query is too old" in err or "query id is invalid" in err:
            try:
                await query.answer(
                    "Эта кнопка устарела. Откройте новое сообщение.",
                    show_alert=True,
                )
            except TelegramError:
                pass
            return
        raise
    except TelegramError:
        return


async def safe_delete_message(bot, chat_id, message_id):
    """Безопасное удаление сообщения"""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except (BadRequest, TelegramError):
        pass


async def rate_limit_api_call(delay=0.05):
    """Rate limiting для предотвращения Flood control"""
    import asyncio

    await asyncio.sleep(delay)


# --- ФУНКЦИЯ БЕЗОПАСНОГО ФОРМАТИРОВАНИЯ ЦЕН ---
def safe_format_price(price, symbol=None):
    """
    Безопасное форматирование цены с динамической точностью как на бирже.
    🚀 ЭКСПЕРТНАЯ ОПТИМИЗАЦИЯ (Татьяна): Сохраняем полную точность согласно правилам проекта.
    """
    if price is None or pd.isna(price):
        return "N/A"

    try:
        if symbol is None:
            return f"{price:.5f}"  # Fallback

        # Используем get_full_price_format для правильного форматирования
        from src.utils.exchange_utils import get_full_price_format

        fmt = get_full_price_format(symbol)
        formatted = fmt.format(float(price))

        # 🔧 ВАЖНО: Мы НЕ убираем нули в конце, чтобы соответствовать нативной точности биржи
        return formatted

    except (ValueError, TypeError, ImportError):
        try:
            precision = get_symbol_precision(symbol)
            return f"{price:.{precision}f}"
        except (ValueError, TypeError):
            return f"{price:.5f}"


def profile(func):
    """Декоратор профилирования времени выполнения.

    Корректно работает как с синхронными, так и с асинхронными функциями.
    """
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - t0
                logging.info("%s выполнена за %.3f сек", func.__name__, elapsed)

        return async_wrapper
    else:

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - t0
                logging.info("%s выполнена за %.3f сек", func.__name__, elapsed)

        return sync_wrapper


def calculate_base_leverage(deposit):
    """Рассчитывает базовое плечо на основе депозита"""
    if deposit <= 100:
        return 1
    elif deposit <= 500:
        return 2
    elif deposit <= 1000:
        return 3
    elif deposit <= 5000:
        return 5
    else:
        return 10


def calculate_risk_based_leverage(deposit, risk_tolerance="moderate"):
    """Рассчитывает плечо на основе депозита и толерантности к риску"""
    base_leverage = calculate_base_leverage(deposit)

    if risk_tolerance == "conservative":
        return max(1, min(base_leverage // 2, 10))
    elif risk_tolerance == "aggressive":
        return min(base_leverage * 2, 10)
    else:  # moderate
        return min(base_leverage, 10)


def calculate_user_leverage(deposit, trade_mode, filter_mode):
    """Рассчитывает плечо для пользователя с учетом режима торговли и фильтров"""
    base_leverage = calculate_base_leverage(deposit)

    # Корректировка по режиму торговли
    if trade_mode == "spot":
        return 1
    elif trade_mode == "futures":
        leverage = base_leverage
    else:
        leverage = base_leverage

    # Корректировка по режиму фильтров
    if filter_mode == "strict":
        leverage = max(1, leverage // 2)
    elif filter_mode == "soft":
        leverage = min(leverage * 1.5, 10)
    # Жёсткий верхний предел 10x
    leverage = max(1, min(int(leverage), 10))
    return leverage


def save_user_data_to_file(user_id, user_data):
    """Сохраняет данные пользователя: сперва в БД (источник истины), затем JSON-бэкап."""
    try:
        # Преобразуем MappingProxy в обычный dict
        if isinstance(user_data, types.MappingProxyType):
            user_data = dict(user_data)

        # Сохраняем в БД
        try:
            from db import Database

            db = Database()
            # Проекция open_positions из positions (для консистентности UI)
            if isinstance(user_data, dict):
                positions = user_data.get("positions", []) or []
                user_data["open_positions"] = [
                    p for p in positions if p.get("status", "open") == "open"
                ]
            db.save_user_data(user_id, user_data)
        except (ImportError, RuntimeError, OSError, ValueError, TypeError) as _e:
            logging.warning("Не удалось сохранить в БД user_id=%s: %s", user_id, _e)

        # Создаем директорию если не существует
        os.makedirs("user_data_backups", exist_ok=True)

        # Сохраняем с временной меткой
        timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_data_backups/user_{user_id}_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2, default=str)

        logging.info("Данные пользователя %s сохранены в %s", user_id, filename)
        return filename
    except (OSError, TypeError, ValueError) as e:
        logging.error("Ошибка сохранения данных пользователя %s: %s", user_id, e)
        return None


def atomic_update_user_aggregate(
    user_id: int, user_data: dict, aggregate_path: str = "user_data.json"
) -> bool:
    """Атомарно обновляет данные пользователя: сперва сохраняет в БД, затем делает JSON-бэкап."""
    try:
        import tempfile

        # Сохранение в БД как источник истины
        try:
            from db import Database

            db = Database()
            # Проекция open_positions из positions (не храним отдельно)
            if isinstance(user_data, dict):
                positions = user_data.get("positions", []) or []
                user_data["open_positions"] = [
                    p for p in positions if p.get("status", "open") == "open"
                ]
            db.save_user_data(user_id, user_data)
        except (ImportError, RuntimeError, OSError, ValueError, TypeError) as _e:
            logging.warning("DB недоступна при atomic_update_user_aggregate: %s", _e)
        # Читаем текущее содержимое
        current = {}
        if os.path.exists(aggregate_path):
            try:
                with open(aggregate_path, encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        loaded = json.loads(content)
                        if isinstance(loaded, dict):
                            current = loaded
            except json.JSONDecodeError:
                current = {}
        # Проекция open_positions из positions (не храним отдельно)
        try:
            if isinstance(user_data, dict):
                positions = user_data.get("positions", []) or []
                user_data["open_positions"] = [
                    p for p in positions if p.get("status", "open") == "open"
                ]
        except (TypeError, ValueError, KeyError):
            pass
        # Апдейт
        current[str(user_id)] = user_data
        # Пишем во временный и заменяем
        dir_name = os.path.dirname(aggregate_path) or "."
        fd, tmp_path = tempfile.mkstemp(prefix="user_data_", suffix=".tmp", dir=dir_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tf:
                json.dump(current, tf, indent=2, ensure_ascii=False)
            os.replace(tmp_path, aggregate_path)
        except (OSError, PermissionError, FileNotFoundError):
            try:
                os.remove(tmp_path)
            except (OSError, PermissionError, FileNotFoundError):
                pass
            raise
        return True
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        logging.error("Ошибка атомарного обновления aggregate: %s", e)
        return False


def convert_mappingproxy(obj):
    """Рекурсивно преобразует MappingProxy в обычные dict"""
    if isinstance(obj, types.MappingProxyType):
        return dict(obj)
    elif isinstance(obj, dict):
        return {k: convert_mappingproxy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_mappingproxy(item) for item in obj]
    else:
        return obj


def save_user_data(context_or_app):
    """Сохраняет данные всех пользователей"""
    try:
        user_data = getattr(context_or_app, "user_data", {})
        if not user_data:
            logging.warning("Нет данных пользователей для сохранения")
            return

        # Создаем резервную копию
        backup_dir = "user_data_backups"
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/all_users_{timestamp}.json"

        # Преобразуем данные
        converted_data = convert_mappingproxy(user_data)

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(converted_data, f, ensure_ascii=False, indent=2, default=str)

        logging.info("Данные всех пользователей сохранены в %s", backup_file)

        # Очищаем старые резервные копии (оставляем последние 10)
        cleanup_old_backups(backup_dir, 10)

    except (OSError, TypeError, ValueError, json.JSONDecodeError) as e:
        logging.error("Ошибка сохранения данных пользователей: %s", e)


def load_user_data(context_or_app):
    """Универсальный доступ к user_data"""
    try:
        # Пытаемся получить user_data из разных источников
        if hasattr(context_or_app, "user_data"):
            return context_or_app.user_data
        elif hasattr(context_or_app, "bot_data"):
            return context_or_app.bot_data.get("user_data", {})
        else:
            # Если ничего не найдено, возвращаем пустой словарь
            return {}
    except (AttributeError, KeyError, TypeError) as e:
        logging.error("Ошибка загрузки user_data: %s", e)
        return {}


def make_signal_key(symbol, buy_exchange, sell_exchange):
    """Создает уникальный ключ для сигнала"""
    return f"{symbol}_{buy_exchange}_{sell_exchange}"


# Исправленный парсинг chat_id
if TELEGRAM_CHAT_IDS:
    if TELEGRAM_CHAT_IDS.strip().startswith("["):
        CHAT_IDS = [int(cid) for cid in ast.literal_eval(TELEGRAM_CHAT_IDS)]
    else:
        CHAT_IDS = [int(cid) for cid in TELEGRAM_CHAT_IDS.split(",") if cid.strip()]
else:
    CHAT_IDS = []

# Глобальные переменные
FUTURES_FEE = 0.1
USER_DATA_FILE = "user_data.json"


def cleanup_old_backups(backup_dir, keep_count=10):
    """Очищает старые резервные копии, оставляя только последние keep_count"""
    try:
        files = [f for f in os.listdir(backup_dir) if f.endswith(".json")]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)

        for old_file in files[keep_count:]:
            file_path = os.path.join(backup_dir, old_file)
            os.remove(file_path)
            logging.info("Удален старый файл резервной копии: %s", file_path)
    except (OSError, PermissionError, FileNotFoundError) as e:
        logging.error("Ошибка очистки старых резервных копий: %s", e)


def dca_calculate_next_qty_and_tp(
    entry_prices, qtys, price, dca_count, deposit, risk_pct, side="long", commission_rate=0.001
):
    """Рассчитывает следующее количество и take profit для DCA с учетом комиссии"""
    try:
        # Рассчитываем среднюю цену входа (исправлено: используем entry_prices вместо price)
        total_qty = sum(qtys)
        if total_qty == 0:
            return 0, 0, 0

        # Правильный расчет средней цены
        total_cost = sum(entry_price * qty for entry_price, qty in zip(entry_prices, qtys))
        avg_price = total_cost / total_qty

        # Рассчитываем следующее количество
        remaining_risk = deposit * (risk_pct / 100) * (1 - dca_count * 0.1)
        next_qty = remaining_risk / price

        # Рассчитываем новую среднюю цену после DCA с учетом комиссии
        new_total_qty = total_qty + next_qty
        new_total_cost = total_cost + (next_qty * price)
        new_avg_price = new_total_cost / new_total_qty

        # Рассчитываем take profit с учетом комиссии
        # Комиссия учитывается дважды: при входе и при выходе
        total_commission = commission_rate * 2  # 0.1% при входе + 0.1% при выходе

        if side == "long":
            # Для лонга: TP должен покрыть комиссию + желаемую прибыль
            tp_price = new_avg_price * (1 + 0.02 + total_commission)  # 2% прибыли + комиссия
        else:
            # Для шорта: TP должен покрыть комиссию + желаемую прибыль
            tp_price = new_avg_price * (1 - 0.02 - total_commission)  # 2% прибыли + комиссия

        return next_qty, tp_price, new_avg_price
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logging.error("Ошибка расчета DCA: %s", e)
        return 0, 0, 0, 0


def calculate_liquidation_price(avg_price, leverage, side="long"):
    """Упрощённая формула для cross margin (без учёта комиссий и funding)"""
    try:
        if side == "long":
            return avg_price * (1 - 1 / leverage)
        else:
            return avg_price * (1 + 1 / leverage)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logging.error("Ошибка расчета цены ликвидации: %s", e)
        return 0


def recalculate_balance_and_risks(user_data, user_id=None):
    """Пересчитывает баланс и риски для пользователя"""
    try:
        if not user_data:
            return

        # Пересчитываем баланс
        if "positions" in user_data:
            total_pnl = 0
            for position in user_data["positions"]:
                if "pnl" in position:
                    total_pnl += position["pnl"]

            user_data["balance"] = user_data.get("deposit", 0) + total_pnl

        # Пересчитываем риски
        if "deposit" in user_data and "risk_pct" in user_data:
            user_data["risk_amount"] = user_data["deposit"] * (user_data["risk_pct"] / 100)

        # Пересчитываем плечо
        if all(key in user_data for key in ["deposit", "trade_mode", "filter_mode"]):
            user_data["leverage"] = calculate_user_leverage(
                user_data["deposit"], user_data["trade_mode"], user_data["filter_mode"]
            )

        logging.info("Пересчитаны баланс и риски для пользователя %s", user_id)

    except (KeyError, TypeError, ValueError, ZeroDivisionError) as e:
        logging.error("Ошибка пересчета баланса и рисков: %s", e)
