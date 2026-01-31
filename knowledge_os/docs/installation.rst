Установка
=========

Требования
----------

* Python 3.9+
* pip
* Git

Установка зависимостей
----------------------

.. code-block:: bash

   # Клонирование репозитория
   git clone https://github.com/your-repo/atra.git
   cd atra
   
   # Установка зависимостей
   pip install -r requirements.txt
   
   # Установка зависимостей для разработки
   pip install -r requirements-dev.txt

Настройка окружения
-------------------

Создайте файл `.env` в корневой директории проекта:

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

Проверка установки
------------------

Запустите тесты для проверки корректности установки:

.. code-block:: bash

   python run_tests.py

Или отдельные компоненты:

.. code-block:: bash

   # Unit тесты
   python -m pytest tests/unit/ -v
   
   # Integration тесты
   python -m pytest tests/integration/ -v
   
   # Performance тесты
   python -m pytest tests/performance/ -v
