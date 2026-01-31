Конфигурация
============

Настройка торгового бота ATRA.

Основные настройки
------------------

Файл `config.py` содержит основные настройки системы:

.. code-block:: python

   # Торговые настройки
   DEFAULT_RISK_PCT = 2.0          # Процент риска по умолчанию
   DEFAULT_LEVERAGE = 1.0          # Плечо по умолчанию
   TRADING_MODE = 'spot'           # Режим торговли (spot/futures)
   
   # Фильтры
   ENABLE_BB_FILTER = True         # Фильтр Bollinger Bands
   ENABLE_EMA_FILTER = True        # Фильтр EMA
   ENABLE_RSI_FILTER = True        # Фильтр RSI
   ENABLE_VOLUME_FILTER = True     # Объемный фильтр
   ENABLE_AI_FILTER = True         # AI фильтр
   
   # Telegram
   TELEGRAM_BOT_TOKEN = 'your_token'
   TELEGRAM_CHAT_ID = 'your_chat_id'
   
   # База данных
   DATABASE_URL = 'sqlite:///atra.db'

Переменные окружения
--------------------

Создайте файл `.env` для настройки переменных окружения:

.. code-block:: env

   # Telegram Bot
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   
   # Database
   DATABASE_URL=sqlite:///atra.db
   
   # API Keys
   BINANCE_API_KEY=your_binance_api_key
   BINANCE_SECRET_KEY=your_binance_secret_key
   
   # Trading Settings
   DEFAULT_RISK_PCT=2.0
   DEFAULT_LEVERAGE=1.0
   TRADING_MODE=spot
   
   # Logging
   LOG_LEVEL=INFO
   LOG_FILE=logs/system.log

Торговые настройки
------------------

### Риск-менеджмент

.. code-block:: python

   # Процент риска
   RISK_PCT_MIN = 0.1              # Минимальный риск
   RISK_PCT_MAX = 10.0             # Максимальный риск
   RISK_PCT_DEFAULT = 2.0          # Риск по умолчанию
   
   # Плечо
   LEVERAGE_MIN = 1.0              # Минимальное плечо
   LEVERAGE_MAX = 20.0             # Максимальное плечо
   LEVERAGE_DEFAULT = 1.0          # Плечо по умолчанию

### Фильтры

.. code-block:: python

   # Bollinger Bands
   BB_WINDOW = 20                  # Период BB
   BB_STD = 2.0                    # Стандартное отклонение
   
   # EMA
   EMA_SHORT = 7                   # Короткая EMA
   EMA_LONG = 25                   # Длинная EMA
   
   # RSI
   RSI_PERIOD = 14                 # Период RSI
   RSI_OVERSOLD = 30               # Уровень перепроданности
   RSI_OVERBOUGHT = 70             # Уровень перекупленности

AI/ML настройки
---------------

### Параметры обучения

.. code-block:: python

   # Обучение
   AI_LEARNING_ENABLED = True      # Включить обучение
   AI_LEARNING_INTERVAL = 3600     # Интервал обучения (сек)
   AI_PATTERN_MIN_COUNT = 100      # Минимальное количество паттернов
   
   # Оптимизация
   AI_OPTIMIZATION_ENABLED = True  # Включить оптимизацию
   AI_OPTIMIZATION_INTERVAL = 21600 # Интервал оптимизации (сек)
   
   # Предсказания
   AI_PREDICTION_ENABLED = True    # Включить предсказания
   AI_CONFIDENCE_THRESHOLD = 0.7   # Порог уверенности

### Модели

.. code-block:: python

   # Модели
   AI_MODEL_TYPE = 'ensemble'      # Тип модели
   AI_MODEL_PATH = 'models/'       # Путь к моделям
   AI_MODEL_UPDATE_INTERVAL = 86400 # Интервал обновления модели

Мониторинг
----------

### Логирование

.. code-block:: python

   # Уровни логирования
   LOG_LEVEL = 'INFO'              # Уровень логирования
   LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   
   # Файлы логов
   LOG_FILE_SYSTEM = 'logs/system.log'
   LOG_FILE_ERRORS = 'logs/errors.log'
   LOG_FILE_TRADES = 'logs/trades.log'
   
   # Ротация логов
   LOG_MAX_SIZE = 50 * 1024 * 1024  # 50MB
   LOG_BACKUP_COUNT = 5

### Метрики

.. code-block:: python

   # Метрики
   METRICS_ENABLED = True          # Включить метрики
   METRICS_INTERVAL = 60           # Интервал сбора метрик (сек)
   METRICS_RETENTION = 86400 * 7   # Время хранения метрик (сек)
   
   # Алерты
   ALERTS_ENABLED = True           # Включить алерты
   ALERT_EMAIL = 'admin@example.com'
   ALERT_TELEGRAM = True

Производительность
------------------

### Кэширование

.. code-block:: python

   # Кэш данных
   CACHE_ENABLED = True            # Включить кэш
   CACHE_TTL = 300                # Время жизни кэша (сек)
   CACHE_MAX_SIZE = 1000          # Максимальный размер кэша
   
   # Кэш API
   API_CACHE_ENABLED = True       # Кэш API запросов
   API_CACHE_TTL = 60             # Время жизни API кэша (сек)

### Параллелизм

.. code-block:: python

   # Параллельная обработка
   PARALLEL_PROCESSING = True      # Включить параллельную обработку
   MAX_WORKERS = 4                # Максимальное количество воркеров
   
   # Асинхронная обработка
   ASYNC_PROCESSING = True        # Включить асинхронную обработку
   ASYNC_MAX_CONCURRENT = 10      # Максимальное количество одновременных задач

Безопасность
------------

### Шифрование

.. code-block:: python

   # Шифрование данных
   ENCRYPTION_ENABLED = True       # Включить шифрование
   ENCRYPTION_KEY = 'your_encryption_key'
   
   # Шифрование API ключей
   API_KEY_ENCRYPTION = True       # Шифровать API ключи

### Аудит

.. code-block:: python

   # Аудит операций
   AUDIT_ENABLED = True           # Включить аудит
   AUDIT_LOG_FILE = 'logs/audit.log'
   AUDIT_RETENTION = 86400 * 30   # Время хранения аудита (сек)

Проверка конфигурации
---------------------

Запустите проверку конфигурации:

.. code-block:: bash

   python check_config.py

Или используйте встроенную проверку:

.. code-block:: python

   from config import validate_config
   
   # Проверка конфигурации
   is_valid, errors = validate_config()
   
   if not is_valid:
       print("Ошибки конфигурации:")
       for error in errors:
           print(f"  - {error}")
   else:
       print("Конфигурация корректна")
