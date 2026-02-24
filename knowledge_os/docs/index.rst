ATRA Trading Bot Documentation
==============================

Добро пожаловать в документацию торгового бота ATRA!

ATRA - это продвинутая система автоматической генерации торговых сигналов с использованием AI/ML технологий, комплексной валидации данных и современной модульной архитектуры.

.. toctree::
   :maxdepth: 2
   :caption: Содержание:

   installation
   quickstart
   api/index
   architecture
   configuration
   testing
   deployment

Особенности
-----------

* 🤖 **AI/ML интеграция** - динамические параметры с автоматической оптимизацией
* 🔍 **Комплексная валидация** - многоуровневая проверка данных на всех этапах
* 🏗️ **Модульная архитектура** - легко расширяемая и поддерживаемая система
* 📊 **Продвинутый мониторинг** - real-time метрики и алерты
* 🧪 **Полное тестирование** - unit, integration и performance тесты
* 📚 **Автодокументация** - автоматически генерируемая документация API

Быстрый старт
-------------

.. code-block:: python

   from src.signals.core import strict_entry_signal
   from src.signals.validation import validate_signal_data

   # Генерация сигнала
   side, price = strict_entry_signal(df, i)

   # Валидация сигнала
   signal_data = {
       'symbol': 'BTCUSDT',
       'side': side.lower(),
       'price': price,
       'user_id': '123456789'
   }

   is_valid = validate_signal_data(signal_data)

Архитектура
-----------

Система построена на модульной архитектуре с четким разделением ответственности:

* **src/signals/** - Основная логика генерации сигналов
* **src/filters/** - Фильтры сигналов (новости, BTC тренд, киты)
* **src/data/** - Провайдеры данных и валидация
* **src/utils/** - Вспомогательные функции

API Reference
-------------

.. toctree::
   :maxdepth: 2

   api/signals
   api/validation
   api/risk
   api/filters

Индексы и таблицы
=================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
