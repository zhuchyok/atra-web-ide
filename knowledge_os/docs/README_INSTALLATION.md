# 🚀 УСТАНОВКА ТОРГОВОЙ СИСТЕМЫ ATRA

## 📋 ТРЕБОВАНИЯ

- **Python 3.8 или выше**
- **pip** (менеджер пакетов Python)
- **Git** (для клонирования репозитория)

## 🎯 СПОСОБЫ УСТАНОВКИ

### 1. 🏆 РЕКОМЕНДУЕМЫЙ СПОСОБ: Виртуальное окружение

#### Быстрая установка (macOS/Linux):

```bash
# Сделать скрипт исполняемым (если еще не сделано)
chmod +x setup_venv.sh

# Запустить автоматическую установку
./setup_venv.sh
```

#### Пошаговая установка:

```bash
# 1. Создать виртуальное окружение
python3 -m venv venv

# 2. Активировать виртуальное окружение
source venv/bin/activate  # macOS/Linux
# или
venv\Scripts\activate     # Windows

# 3. Обновить pip
pip install --upgrade pip

# 4. Установить зависимости
pip install -r requirements.txt
```

### 2. 🔧 ИНТЕРАКТИВНАЯ УСТАНОВКА

Запустите интерактивный скрипт установки:

```bash
python3 install_dependencies.py
```

Выберите один из вариантов:

- **1** - Создать виртуальное окружение (РЕКОМЕНДУЕТСЯ)
- **2** - Установить в глобальное окружение
- **3** - Проверить текущую установку

### 3. 🌍 ГЛОБАЛЬНАЯ УСТАНОВКА

```bash
# Установить все зависимости глобально
pip install -r requirements.txt
```

## 📦 ЗАВИСИМОСТИ

### Критически важные:

- **pandas** - обработка данных
- **numpy** - численные вычисления
- **requests** - HTTP запросы
- **aiohttp** - асинхронные HTTP запросы
- **ta** - технический анализ
- **ccxt** - криптовалютные API
- **python-telegram-bot** - Telegram бот

### Дополнительные:

- **scikit-learn** - машинное обучение
- **matplotlib** - визуализация
- **redis** - кэширование
- **cryptography** - безопасность

## 🚀 ЗАПУСК СИСТЕМЫ

### В виртуальном окружении:

```bash
# 1. Активировать виртуальное окружение
source venv/bin/activate  # macOS/Linux
# или
venv\Scripts\activate     # Windows

# 2. Запустить систему
python main.py
```

### В глобальном окружении:

```bash
python3 main.py
```

## 🔧 НАСТРОЙКА

### 1. Конфигурация Telegram бота

Отредактируйте файл `config.py`:

```python
TOKEN = "ваш_токен_бота"
```

### 2. Настройка пользователей

Отредактируйте файл `user_data.json`:

```json
{
  "user_id": {
    "trade_mode": "spot",
    "filter_mode": "strict",
    "deposit": 1000,
    "leverage": 1
  }
}
```

## 🛠️ УСТРАНЕНИЕ ПРОБЛЕМ

### Ошибка "pip не найден":

```bash
python3 -m ensurepip --upgrade
```

### Ошибка "Permission denied":

```bash
# Использовать sudo (Linux/macOS)
sudo pip install -r requirements.txt

# Или установить в пользовательскую директорию
pip install --user -r requirements.txt
```

### Ошибка "Python не найден":

```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# Windows
# Скачать с python.org
```

### Проблемы с виртуальным окружением:

```bash
# Удалить и пересоздать
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📁 СТРУКТУРА ПРОЕКТА

```
atra/
├── main.py                    # Главный файл системы
├── signal_live.py            # Генерация торговых сигналов
├── telegram_bot.py           # Telegram бот
├── config.py                 # Конфигурация
├── requirements.txt          # Зависимости
├── install_dependencies.py   # Скрипт установки
├── setup_venv.sh            # Быстрая установка venv
├── user_data.json           # Данные пользователей
└── README_INSTALLATION.md   # Этот файл
```

## 🔍 ПРОВЕРКА УСТАНОВКИ

### Проверить установку зависимостей:

```bash
python3 install_dependencies.py
# Выберите опцию 3 - "Проверить текущую установку"
```

### Проверить работу системы:

```bash
# Запустить систему
python main.py

# Проверить логи
tail -f system_improved.log
```

## 📞 ПОДДЕРЖКА

### Логи системы:

- `system_improved.log` - основные логи
- `telegram_bot.log` - логи Telegram бота

### Полезные команды:

```bash
# Просмотр логов в реальном времени
tail -f system_improved.log

# Проверка статуса системы
ps aux | grep python

# Очистка кэша
python3 cache_restore_system.py cleanup
```

## 🎉 ГОТОВО!

После успешной установки система ATRA готова к работе!

### Следующие шаги:

1. ✅ Настроить конфигурацию в `config.py`
2. ✅ Добавить пользователей в `user_data.json`
3. ✅ Запустить систему: `python main.py`
4. ✅ Отправить команду `/start` боту в Telegram

---

**Удачной торговли! 📈**
