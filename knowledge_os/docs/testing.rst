Тестирование
============

Руководство по тестированию торгового бота ATRA.

Типы тестов
-----------

Система включает несколько уровней тестирования:

* **Unit тесты** - тестирование отдельных функций и классов
* **Integration тесты** - тестирование взаимодействия компонентов
* **Performance тесты** - тестирование производительности
* **End-to-End тесты** - тестирование полного потока

Запуск тестов
-------------

### Все тесты

.. code-block:: bash

   python run_tests.py

### Отдельные типы тестов

.. code-block:: bash

   # Unit тесты
   python -m pytest tests/unit/ -v
   
   # Integration тесты
   python -m pytest tests/integration/ -v
   
   # Performance тесты
   python -m pytest tests/performance/ -v

### С покрытием кода

.. code-block:: bash

   python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

Unit тесты
----------

Тестирование отдельных компонентов системы.

### Тесты валидации

.. code-block:: python

   # tests/unit/test_validation.py
   def test_validate_signal_data_valid():
       """Тест валидации корректных данных сигнала"""
       signal_data = {
           'symbol': 'BTCUSDT',
           'side': 'long',
           'price': 50000.0,
           'user_id': '123456789'
       }
       
       result = validate_signal_data(signal_data)
       assert result is True

### Тесты генерации сигналов

.. code-block:: python

   # tests/unit/test_core.py
   def test_strict_entry_signal():
       """Тест строгого сигнала"""
       df = create_test_dataframe()
       side, price = strict_entry_signal(df, len(df) - 1)
       
       assert side is None or side in ['LONG', 'SHORT']
       assert price is None or isinstance(price, (int, float))

Integration тесты
-----------------

Тестирование взаимодействия компонентов.

### Тест полного потока

.. code-block:: python

   # tests/integration/test_signal_flow.py
   async def test_complete_signal_generation_flow():
       """Тест полного потока генерации сигнала"""
       df = prepare_dataframe()
       user_data = get_user_data()
       
       # Генерируем сигнал
       side, price = strict_entry_signal(df, len(df) - 1)
       
       if side and price:
           # Валидируем сигнал
           signal_data = create_signal_data(side, price)
           is_valid = validate_signal_data(signal_data)
           assert is_valid is True

Performance тесты
-----------------

Тестирование производительности под нагрузкой.

### Тест нагрузки

.. code-block:: python

   # tests/performance/test_load.py
   def test_signal_generation_under_load():
       """Тест генерации сигналов под нагрузкой"""
       df = prepare_dataframe()
       
       # Параметры нагрузки
       num_iterations = 1000
       max_execution_time = 10.0  # секунд
       
       start_time = time.time()
       
       # Генерируем множество сигналов
       for i in range(num_iterations):
           side, price = strict_entry_signal(df, len(df) - 1)
       
       end_time = time.time()
       execution_time = end_time - start_time
       
       assert execution_time < max_execution_time

### Тест памяти

.. code-block:: python

   def test_memory_usage_under_load():
       """Тест использования памяти под нагрузкой"""
       import psutil
       import os
       
       process = psutil.Process(os.getpid())
       initial_memory = process.memory_info().rss / 1024 / 1024  # MB
       
       # Генерируем множество сигналов
       for iteration in range(100):
           df = create_test_dataframe()
           for i in range(50, len(df)):
               side, price = strict_entry_signal(df, i)
           
           # Проверяем память
           if iteration % 10 == 0:
               current_memory = process.memory_info().rss / 1024 / 1024
               memory_increase = current_memory - initial_memory
               assert memory_increase < 100  # MB

Написание тестов
----------------

### Структура теста

.. code-block:: python

   def test_function_name():
       """Описание теста"""
       # Arrange - подготовка данных
       input_data = create_test_data()
       
       # Act - выполнение действия
       result = function_under_test(input_data)
       
       # Assert - проверка результата
       assert result is not None
       assert result > 0

### Фикстуры

.. code-block:: python

   @pytest.fixture
   def sample_ohlc_data():
       """Создает тестовые OHLC данные"""
       dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
       
       df = pd.DataFrame({
           'timestamp': dates,
           'open': np.random.uniform(40000, 60000, 100),
           'high': np.random.uniform(40000, 60000, 100),
           'low': np.random.uniform(40000, 60000, 100),
           'close': np.random.uniform(40000, 60000, 100),
           'volume': np.random.uniform(1000, 10000, 100)
       })
       
       return df

### Моки

.. code-block:: python

   @patch('src.signals.generation.notify_user')
   def test_signal_notification(mock_notify):
       """Тест уведомления о сигнале"""
       mock_notify.return_value = True
       
       # Тестируем отправку сигнала
       result = send_signal(signal_data)
       
       assert result is True
       mock_notify.assert_called_once()

Непрерывная интеграция
----------------------

### GitHub Actions

Создайте файл `.github/workflows/tests.yml`:

.. code-block:: yaml

   name: Tests
   
   on: [push, pull_request]
   
   jobs:
     test:
       runs-on: ubuntu-latest
       
       steps:
       - uses: actions/checkout@v2
       
       - name: Set up Python
         uses: actions/setup-python@v2
         with:
           python-version: 3.9
       
       - name: Install dependencies
         run: |
           pip install -r requirements.txt
           pip install -r requirements-dev.txt
       
       - name: Run tests
         run: python run_tests.py

### Локальная проверка

.. code-block:: bash

   # Установка pre-commit hooks
   pip install pre-commit
   pre-commit install
   
   # Запуск проверок
   pre-commit run --all-files

Отчеты о тестах
---------------

### HTML отчет

.. code-block:: bash

   python -m pytest tests/ --cov=src --cov-report=html
   
   # Откройте htmlcov/index.html в браузере

### JSON отчет

.. code-block:: bash

   python -m pytest tests/ --cov=src --cov-report=json

### Терминальный отчет

.. code-block:: bash

   python -m pytest tests/ --cov=src --cov-report=term-missing

Лучшие практики
-------------

### 1. Именование тестов

.. code-block:: python

   def test_function_name_should_return_expected_result():
       """Тест должен описывать ожидаемое поведение"""
       pass

### 2. Изоляция тестов

.. code-block:: python

   def test_isolated():
       """Каждый тест должен быть независимым"""
       # Не полагайтесь на состояние других тестов
       pass

### 3. Обработка исключений

.. code-block:: python

   def test_exception_handling():
       """Тестируйте обработку исключений"""
       with pytest.raises(ValueError):
           function_that_raises_value_error()

### 4. Параметризация тестов

.. code-block:: python

   @pytest.mark.parametrize("input,expected", [
       (1, 2),
       (2, 4),
       (3, 6),
   ])
   def test_multiply_by_two(input, expected):
       assert multiply_by_two(input) == expected
