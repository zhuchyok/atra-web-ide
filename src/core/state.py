# Глобальные переменные для управления режимами работы бота
ADAPTIVE_INTERVAL = 30  # стартовый интервал
MIN_INTERVAL = 10
MAX_INTERVAL = 120

SLEEP_MODE = False
SLEEP_START = 23  # по МСК
SLEEP_END = 7  # по МСК
MANUAL_INTERVAL = None
LAST_USER_ACTION = None  # 'confirm', 'decline', None
LAST_ACTION_TIME = 0

import time
import asyncio
import random
from collections import defaultdict, deque



# Продвинутая система контроля частоты отправки сообщений
class AdvancedNotificationLimiter:
    def __init__(self):
        # Основные лимиты Telegram API
        self.CHAT_RATE_LIMIT = 1.2  # секунд между сообщениями в одном чате (слегка повышено)
        self.GLOBAL_RATE_LIMIT = 30  # сообщений в секунду по всем чатам
        self.GLOBAL_WINDOW = 1.0  # окно для подсчета глобальных сообщений (секунды)

        # Настройки батчей
        self.BATCH_SIZE = 8  # размер батча для отправки (слегка уменьшено)
        self.BATCH_DELAY = 0.35  # задержка между батчами (слегка уменьшено)
        self.JITTER_RANGE = 0.25  # случайная задержка ±0.25 сек

        # Отслеживание сообщений
        self.chat_last_message = {}  # {chat_id: timestamp}
        self.chat_message_times = defaultdict(deque)  # {chat_id: deque of timestamps}
        self.global_message_times = deque()  # все сообщения по времени

        # Per-user backoff система
        self.user_backoff = {}  # {user_id: {retry_after: timestamp, attempts: count}}
        self.MAX_BACKOFF_ATTEMPTS = 3
        self.BACKOFF_MULTIPLIER = 2.0

        # Статистика
        self.stats = {
            'total_messages': 0,
            'rate_limited_messages': 0,
            'batches_sent': 0,
            'backoff_activations': 0,
            'last_reset': time.time()
        }

    def get_user_backoff_delay(self, user_id):
        """
        Возвращает задержку для пользователя на основе его backoff
        """
        if user_id not in self.user_backoff:
            return 0

        backoff_data = self.user_backoff[user_id]
        retry_after = backoff_data.get('retry_after', 0)
        attempts = backoff_data.get('attempts', 0)

        # Если время retry_after прошло, сбрасываем backoff
        if time.time() > retry_after:
            del self.user_backoff[user_id]
            return 0

        # Увеличиваем задержку с каждым попыткой
        delay = retry_after - time.time()
        if attempts > 0:
            delay *= (self.BACKOFF_MULTIPLIER ** (attempts - 1))

        return max(0, delay)

    def set_user_backoff(self, user_id, retry_after_seconds):
        """
        Устанавливает backoff для пользователя
        """
        current_time = time.time()
        if user_id not in self.user_backoff:
            self.user_backoff[user_id] = {
                'retry_after': current_time + retry_after_seconds,
                'attempts': 1
            }
        else:
            self.user_backoff[user_id]['attempts'] += 1
            self.user_backoff[user_id]['retry_after'] = current_time + retry_after_seconds

        self.stats['backoff_activations'] += 1
        print(f"[Backoff] Пользователь {user_id}: retry_after={retry_after_seconds}с, попыток={self.user_backoff[user_id]['attempts']}")

    def clear_user_backoff(self, user_id):
        """
        Очищает backoff для пользователя
        """
        if user_id in self.user_backoff:
            del self.user_backoff[user_id]

    async def wait_if_needed(self, chat_id=None):
        """
        Проверяет лимиты и ждет при необходимости
        """
        current_time = time.time()

        # Проверяем per-user backoff
        if chat_id is not None:
            backoff_delay = self.get_user_backoff_delay(chat_id)
            if backoff_delay > 0:
                print(f"[RateLimit] Backoff для пользователя {chat_id}, ожидание {backoff_delay:.2f} сек")
                self.stats['rate_limited_messages'] += 1
                await asyncio.sleep(backoff_delay)
                current_time = time.time()

        # Проверяем глобальный лимит (30 сообщений/сек)
        if len(self.global_message_times) > 0:
            # Удаляем старые сообщения из окна
            while (len(self.global_message_times) > 0 and
                   current_time - self.global_message_times[0] > self.GLOBAL_WINDOW):
                self.global_message_times.popleft()

            # Если превышен глобальный лимит, ждем
            if len(self.global_message_times) >= self.GLOBAL_RATE_LIMIT:
                wait_time = self.global_message_times[0] + self.GLOBAL_WINDOW - current_time
                if wait_time > 0:
                    print(f"[RateLimit] Глобальный лимит превышен, ожидание {wait_time:.2f} сек")
                    self.stats['rate_limited_messages'] += 1
                    await asyncio.sleep(wait_time)
                    current_time = time.time()

        # Проверяем лимит для конкретного чата (1 сообщение/сек)
        if chat_id is not None:
            if chat_id in self.chat_last_message:
                time_since_last = current_time - self.chat_last_message[chat_id]
                if time_since_last < self.CHAT_RATE_LIMIT:
                    wait_time = self.CHAT_RATE_LIMIT - time_since_last
                    print(f"[RateLimit] Лимит чата {chat_id} превышен, ожидание {wait_time:.2f} сек")
                    self.stats['rate_limited_messages'] += 1
                    await asyncio.sleep(wait_time)
                    current_time = time.time()

        # Обновляем статистику
        self.global_message_times.append(current_time)
        if chat_id is not None:
            self.chat_last_message[chat_id] = current_time
            self.chat_message_times[chat_id].append(current_time)

            # Очищаем старые записи для чата (оставляем только за последние 10 секунд)
            while (len(self.chat_message_times[chat_id]) > 0 and
                   current_time - self.chat_message_times[chat_id][0] > 10):
                self.chat_message_times[chat_id].popleft()

        self.stats['total_messages'] += 1

    def create_batches(self, user_ids, batch_size=None):
        """
        Разбивает список пользователей на батчи
        """
        if batch_size is None:
            batch_size = self.BATCH_SIZE

        batches = []
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i + batch_size]
            batches.append(batch)

        return batches

    async def send_batch_with_jitter(self, batch, send_func, **kwargs):
        """
        Отправляет батч с jitter задержкой и распределением нагрузки
        """
        # Добавляем случайную задержку (jitter)
        jitter = random.uniform(-self.JITTER_RANGE, self.JITTER_RANGE)
        delay = self.BATCH_DELAY + jitter

        if delay > 0:
            print(f"[Batch] Задержка между батчами: {delay:.2f} сек (jitter: {jitter:.2f})")
            await asyncio.sleep(delay)

        # Отправляем сообщения в батче с небольшой задержкой между пользователями
        results = []
        for i, user_id in enumerate(batch):
            try:
                # Небольшая задержка между пользователями в батче для распределения нагрузки
                if i > 0:
                    await asyncio.sleep(0.1)  # 100ms между пользователями

                result = await send_func(user_id, **kwargs)
                results.append((user_id, result))

                # Проверяем глобальные лимиты после каждого сообщения
                await self.wait_if_needed()

            except Exception as e:
                print(f"[Batch] Ошибка отправки пользователю {user_id}: {e}")
                results.append((user_id, None))

        self.stats['batches_sent'] += 1
        return results

    async def send_mass_notification(self, user_ids, send_func, **kwargs):
        """
        Отправляет массовое уведомление с разбивкой на батчи и распределением нагрузки
        """
        print(f"[MassNotification] Отправка {len(user_ids)} пользователям")

        # Разбиваем на батчи
        batches = self.create_batches(user_ids)
        print(f"[MassNotification] Создано {len(batches)} батчей по {self.BATCH_SIZE} пользователей")

        all_results = []

        for i, batch in enumerate(batches):
            print(f"[MassNotification] Отправка батча {i+1}/{len(batches)} ({len(batch)} пользователей)")

            # Отправляем батч
            batch_results = await self.send_batch_with_jitter(batch, send_func, **kwargs)
            all_results.extend(batch_results)

            # Проверяем глобальные лимиты между батчами
            if i < len(batches) - 1:
                await self.wait_if_needed()

                # Дополнительная задержка между батчами для лучшего распределения
                await asyncio.sleep(0.2)

        print(f"[MassNotification] ✅ Массовая отправка завершена")
        return all_results

    def get_stats(self):
        """
        Возвращает расширенную статистику использования лимитов
        """
        current_time = time.time()

        # Очищаем старые данные для актуальной статистики
        while (len(self.global_message_times) > 0 and
               current_time - self.global_message_times[0] > self.GLOBAL_WINDOW):
            self.global_message_times.popleft()

        return {
            'total_messages': self.stats['total_messages'],
            'rate_limited_messages': self.stats['rate_limited_messages'],
            'current_global_rate': len(self.global_message_times),
            'active_chats': len(self.chat_last_message),
            'batches_sent': self.stats['batches_sent'],
            'backoff_activations': self.stats['backoff_activations'],
            'users_in_backoff': len(self.user_backoff),
            'uptime_hours': (current_time - self.stats['last_reset']) / 3600
        }

    def reset_stats(self):
        """
        Сбрасывает статистику
        """
        self.stats = {
            'total_messages': 0,
            'rate_limited_messages': 0,
            'batches_sent': 0,
            'backoff_activations': 0,
            'last_reset': time.time()
        }

    def clear_all_backoffs(self):
        """
        Очищает все backoff'ы
        """
        self.user_backoff.clear()
        print("[Backoff] Все пользовательские backoff'ы очищены")


# Создаем глобальный экземпляр лимитера
NOTIFICATION_LIMITER = AdvancedNotificationLimiter()

signals_log_path = "signals_log.csv"
BALANCE_FILE = "balance.txt"
TRADING_HOURS_FILE = "trading_hours.txt"

import logging
import shutil
import os
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now

BACKUP_DIR = "backups"


def backup_file(filepath, backup_dir=BACKUP_DIR, max_backups: int = 10):
    """
    Создает бэкап файла с автоматической ротацией старых бэкапов.
    
    Args:
        filepath: Путь к файлу для бэкапа
        backup_dir: Директория для хранения бэкапов
        max_backups: Максимальное количество бэкапов для этого файла (по умолчанию 10)
    """
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.isfile(filepath):
        timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{os.path.basename(filepath)}_{timestamp}"
        backup_path = os.path.join(backup_dir, backup_filename)
        shutil.copy(filepath, backup_path)
        logging.info(f"Бэкап {filepath} -> {backup_path}")
        
        # Ротация: удаляем старые бэкапы, оставляем только последние max_backups
        try:
            # Находим все бэкапы этого файла
            base_name = os.path.basename(filepath)
            backup_pattern = os.path.join(backup_dir, f"{base_name}_*")
            import glob
            existing_backups = glob.glob(backup_pattern)
            
            # Сортируем по времени модификации (новые первыми)
            existing_backups.sort(key=os.path.getmtime, reverse=True)
            
            # Удаляем лишние бэкапы
            if len(existing_backups) > max_backups:
                for old_backup in existing_backups[max_backups:]:
                    try:
                        os.remove(old_backup)
                        logging.debug(f"Удален старый бэкап: {os.path.basename(old_backup)}")
                    except Exception as e:
                        logging.warning(f"Не удалось удалить старый бэкап {old_backup}: {e}")
        except Exception as e:
            logging.warning(f"Ошибка при ротации бэкапов: {e}")


def get_balance():
    try:
        with open(BALANCE_FILE, "r") as f:
            return float(f.read())
    except Exception as e:
        logging.error(e, exc_info=True)
        return 10000.0  # значение по умолчанию


def set_balance(value):
    try:
        with open(BALANCE_FILE, "w") as f:
            f.write(str(float(value)))
        backup_file(BALANCE_FILE)
    except Exception as e:
        logging.error(e, exc_info=True)


def set_trading_hours(start, end):
    try:
        with open(TRADING_HOURS_FILE, "w") as f:
            f.write(f"{int(start)} {int(end)}")
        backup_file(TRADING_HOURS_FILE)
    except Exception as e:
        logging.error(e, exc_info=True)


def get_trading_hours():
    try:
        with open(TRADING_HOURS_FILE, "r") as f:
            s, e = f.read().split()
            return int(s), int(e)
    except Exception as e:
        logging.error(e, exc_info=True)
        return 0, 24  # по умолчанию круглосуточно
