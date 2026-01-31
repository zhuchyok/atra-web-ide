Быстрый старт
=============

Это руководство поможет вам быстро начать работу с торговым ботом ATRA.

Основные концепции
------------------

ATRA - это система автоматической генерации торговых сигналов, которая:

* Анализирует рыночные данные в реальном времени
* Применяет множественные фильтры для отбора качественных сигналов
* Использует AI/ML для оптимизации параметров
* Отправляет сигналы через Telegram

Простой пример
--------------

.. code-block:: python

   import pandas as pd
   from src.signals.core import strict_entry_signal
   from src.signals.validation import validate_signal_data
   
   # Загрузка данных
   df = pd.read_csv('market_data.csv')
   
   # Добавление индикаторов
   df = add_indicators(df)
   
   # Генерация сигнала
   side, price = strict_entry_signal(df, len(df) - 1)
   
   if side and price:
       # Валидация сигнала
       signal_data = {
           'symbol': 'BTCUSDT',
           'side': side.lower(),
           'price': price,
           'user_id': '123456789'
       }
       
       is_valid = validate_signal_data(signal_data)
       
       if is_valid:
           print(f"Сигнал: {side} {price}")

Запуск системы
--------------

1. **Инициализация базы данных:**

   .. code-block:: bash

      python database_initialization.py

2. **Запуск основного процесса:**

   .. code-block:: bash

      python main.py

3. **Мониторинг логов:**

   .. code-block:: bash

      tail -f logs/system.log

Конфигурация
------------

Основные настройки находятся в файле `config.py`:

.. code-block:: python

   # Торговые настройки
   DEFAULT_RISK_PCT = 2.0
   DEFAULT_LEVERAGE = 1.0
   TRADING_MODE = 'spot'
   
   # Фильтры
   ENABLE_BB_FILTER = True
   ENABLE_EMA_FILTER = True
   ENABLE_RSI_FILTER = True
   ENABLE_VOLUME_FILTER = True
   ENABLE_AI_FILTER = True

Telegram бот
------------

1. **Создайте бота через @BotFather**
2. **Получите токен и добавьте в .env**
3. **Запустите бота:**

   .. code-block:: bash

      python telegram_bot.py

4. **Основные команды:**
   - `/start` - Начать работу
   - `/balance` - Показать баланс
   - `/positions` - Показать позиции
   - `/history` - История сделок

Мониторинг
----------

Система предоставляет несколько способов мониторинга:

* **Логи** - детальная информация о работе системы
* **Метрики** - статистика производительности
* **Алерты** - уведомления о проблемах

.. code-block:: python

   from monitoring_system import MonitoringSystem
   
   # Инициализация мониторинга
   monitor = MonitoringSystem()
   
   # Получение метрик
   metrics = monitor.get_metrics()
   print(f"Активных сигналов: {metrics['active_signals']}")
   print(f"Успешных сделок: {metrics['successful_trades']}")

Следующие шаги
--------------

* Изучите :doc:`architecture` для понимания архитектуры
* Настройте :doc:`configuration` под ваши нужды
* Запустите :doc:`testing` для проверки системы
* Ознакомьтесь с :doc:`api/index` для работы с API
