import logging
from types import MappingProxyType

from src.database.db import Database

logger = logging.getLogger(__name__)

# Singleton Database instance с lazy initialization
_db = None


def get_db():
    """Получает или создает экземпляр Database (singleton с lazy init)"""
    global _db
    if _db is None:
        _db = Database()
    return _db


def load_user_data_for_signals():
    """
    Загружает данные пользователей строго из БД (без файловых фолбэков).
    Добавлена защита от блокировки базы данных при одновременном доступе.
    """
    max_retries = 3
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            db = get_db()
            user_ids = db.get_all_users()
            logger.info("✅ Загружено %d пользователей из базы данных", len(user_ids))
            if len(user_ids) == 0:
                logger.warning("⚠️ Нет данных пользователей для отправки сигналов")
            aggregated = {}

            # Защита от зависания при большом количестве пользователей
            max_users = 1000  # Максимум пользователей для обработки
            if len(user_ids) > max_users:
                print(
                    f"[WARNING] Слишком много пользователей ({len(user_ids)}), обрабатываем только первых {max_users}"
                )
                user_ids = user_ids[:max_users]

            for uid in user_ids:
                try:
                    # Добавляем небольшую задержку между запросами для избежания блокировки
                    if attempt > 0:
                        import time

                        time.sleep(0.1)

                    data = get_db().get_user_data(uid)
                    # Добавляем отладку для понимания проблемы
                    if data is None:
                        logger.warning(
                            "🚫 [USER LOAD] get_user_data(%s) вернул None - данные не найдены или не парсятся",
                            uid,
                        )
                    elif not isinstance(data, dict):
                        logger.warning(
                            "🚫 [USER LOAD] get_user_data(%s) вернул не dict: %s", uid, type(data)
                        )
                    elif not data:
                        logger.warning("🚫 [USER LOAD] get_user_data(%s) вернул пустой dict", uid)
                    if isinstance(data, dict) and data:
                        # Отладочная информация для режима торговли
                        trade_mode = data.get("trade_mode", "spot")
                        leverage = data.get("leverage", 1)
                        logger.debug(
                            "✅ [USER LOAD] Пользователь %s: trade_mode=%s, leverage=%s",
                            uid,
                            trade_mode,
                            leverage,
                        )

                        # ВАЖНО: Добавляем user_id в данные пользователя
                        data["user_id"] = str(uid)
                        aggregated[str(uid)] = data
                except Exception as user_error:
                    logger.warning(
                        "🚫 [USER LOAD] Ошибка загрузки данных пользователя %s: %s", uid, user_error
                    )
                    continue

            logger.info(
                "✅ [USER LOAD] Итого загружено %d пользователей с данными", len(aggregated)
            )
            return aggregated

        except Exception as e:
            logger.error(
                "❌ [USER LOAD] Попытка %d/%d загрузки данных пользователей: %s",
                attempt + 1,
                max_retries,
                e,
            )
            if attempt < max_retries - 1:
                logger.debug("🔄 [USER LOAD] Повторная попытка через %.1f секунд...", retry_delay)
                import time

                time.sleep(retry_delay)
                retry_delay *= 2  # Экспоненциальная задержка
            else:
                logger.error(
                    "❌ [USER LOAD] Все попытки загрузки данных пользователей исчерпаны, возвращаю пустой словарь"
                )
                return {}

    # Этот return никогда не должен выполниться, но на всякий случай
    return {}


def restore_user_data_to_context(context_or_app):
    """
    Восстанавливает данные пользователей из файлов бэкапа в context.user_data.
    Упрощённая надёжная версия: если user_data имеет тип mappingproxy, заменяем на обычный dict
    и далее используем обычные присваивания без проб и лишних логов.
    """
    try:
        # Загружаем данные из файлов/БД
        user_data_dict = load_user_data_for_signals()
        if not user_data_dict:
            print("⚠️ Нет данных для восстановления")
            return False

        # Получаем/создаём user_data
        store = None
        if hasattr(context_or_app, "user_data"):
            store = context_or_app.user_data
            if isinstance(store, MappingProxyType):
                new_store = dict(store)
                context_or_app.user_data = new_store
                store = context_or_app.user_data
        elif hasattr(context_or_app, "bot_data"):
            if "user_data" not in context_or_app.bot_data:
                context_or_app.bot_data["user_data"] = {}
            store = context_or_app.bot_data["user_data"]
        else:
            context_or_app.user_data = {}
            store = context_or_app.user_data

        if store is None:
            print("❌ Не удалось получить/создать user_data")
            return False

        restored = 0
        for user_id_str, content in user_data_dict.items():
            try:
                user_id = int(user_id_str)
                if isinstance(content, dict) and content:
                    store[user_id] = content
                    restored += 1
            except Exception:
                continue

        print(f"🎉 Успешно восстановлено {restored} пользователей")
        return restored > 0

    except Exception as e:
        print(f"❌ Ошибка восстановления данных в context: {e}")
        return False


def save_user_data_for_signals(user_data_dict):
    """
    Сохраняет данные пользователей строго в БД (без файловых бэкапов).
    """
    try:
        db = get_db()
        if isinstance(user_data_dict, dict):
            for user_id_str, data in user_data_dict.items():
                try:
                    get_db().save_user_data(user_id_str, data)
                except Exception as e:
                    print(f"⚠️ Ошибка записи в БД для {user_id_str}: {e}")
        return True
    except Exception as e:
        print(f"Ошибка сохранения данных пользователей в БД: {e}")
        return False
