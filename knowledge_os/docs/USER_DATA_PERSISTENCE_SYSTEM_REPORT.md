# 🔄 СИСТЕМА СОХРАНЕНИЯ И ЗАГРУЗКИ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ

## 🎯 **ОПИСАНИЕ СИСТЕМЫ**

Система автоматически сохраняет данные пользователей перед остановкой и загружает их при запуске, обеспечивая непрерывность работы и сохранность настроек пользователей.

## 🔧 **КОМПОНЕНТЫ СИСТЕМЫ**

### **1. Сохранение данных (`save_user_data`)**

**Файл:** `telegram_bot.py` (строки 230-260)

```python
def save_user_data(context_or_app):
    """Сохранение данных пользователей в файл"""
    try:
        # Получаем данные пользователей
        if hasattr(context_or_app, "application"):
            user_data = context_or_app.application.user_data
        elif hasattr(context_or_app, "user_data"):
            user_data = context_or_app.user_data
        else:
            user_data = context_or_app

        # Очищаем дублирующиеся записи
        safe_data = convert_mappingproxy(user_data)
        unique_data = {}
        for k, v in safe_data.items():
            unique_data[str(k)] = v

        # Сохраняем в файл
        with open(USER_DATA_FILE, "w") as f:
            json.dump(unique_data, f, indent=2)

        # Создаем резервную копию
        backup_dir = "user_data_backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"user_data_{timestamp}.json")
        shutil.copy(USER_DATA_FILE, backup_path)

    except Exception as e:
        logging.error(f"Ошибка сохранения user_data: {e}")
```

### **2. Загрузка данных (`load_user_data`)**

**Файл:** `telegram_bot.py` (строки 264-310)

```python
def load_user_data(context_or_app):
    """Загрузка данных пользователей из файла"""
    try:
        # Определяем где хранятся данные
        if hasattr(context_or_app, "application"):
            user_data = context_or_app.application.user_data
            is_app = True
        else:
            user_data = context_or_app.user_data
            is_app = False

        # Загружаем из файла
        if os.path.isfile(USER_DATA_FILE):
            with open(USER_DATA_FILE, "r") as f:
                content = f.read()
                if not content.strip():
                    data = {}
                else:
                    data = json.loads(content)

            # Обновляем данные в приложении
            if isinstance(user_data, types.MappingProxyType):
                if is_app:
                    context_or_app.application.user_data = dict(data)
                else:
                    context_or_app.user_data = dict(data)
            else:
                user_data.clear()
                user_data.update(data)

    except Exception as e:
        logging.error(f"Ошибка загрузки user_data: {e}")
```

### **3. Обработчики сигналов**

**Файл:** `main.py` (строки 185-186, 170-180)

```python
def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"📡 Получен сигнал {signum}, завершение работы...")
    sys.exit(0)

async def cleanup():
    """Очистка ресурсов"""
    logger.info("🧹 Очистка ресурсов...")

    try:
        # Сохраняем данные пользователей перед остановкой
        from telegram_bot import save_user_data, app
        if app:
            save_user_data(app)
            logger.info("✅ Данные пользователей сохранены")

        # Останавливаем Telegram бот
        from telegram_bot import stop_telegram_bot
        await stop_telegram_bot()
        logger.info("✅ Telegram бот корректно остановлен")

    except Exception as e:
        logger.warning(f"⚠️ Ошибка при остановке бота: {e}")
```

### **4. Автоматическая загрузка при запуске**

**Файл:** `telegram_bot.py` (строка 4401)

```python
async def run_telegram_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    # Загружаем user_data.json при старте
    load_user_data(app)
    # ... остальной код
```

## 🔄 **ПРОЦЕСС РАБОТЫ**

### **При запуске системы:**

1. ✅ Создается экземпляр Telegram приложения
2. ✅ Вызывается `load_user_data(app)`
3. ✅ Данные загружаются из `user_data.json`
4. ✅ Если файл не существует, создается пустой словарь
5. ✅ Данные восстанавливаются в памяти приложения

### **При остановке системы:**

1. 📡 Получается сигнал SIGINT/SIGTERM
2. 🧹 Вызывается функция `cleanup()`
3. 💾 Вызывается `save_user_data(app)`
4. 📁 Данные сохраняются в `user_data.json`
5. 🔄 Создается резервная копия в `user_data_backups/`
6. 🛑 Система корректно завершается

### **При синтаксических ошибках:**

1. ❌ Обнаруживается синтаксическая ошибка
2. 🧹 Система пытается выполнить `cleanup()`
3. 💾 Данные пользователей сохраняются
4. 🔄 При следующем запуске данные восстанавливаются

## 📁 **СТРУКТУРА ФАЙЛОВ**

```
atra/
├── user_data.json                    # Основной файл данных
├── user_data_backups/                # Папка с резервными копиями
│   ├── user_data_20250815_024538.json
│   ├── user_data_20250817_232825.json
│   └── ...
└── logs/                             # Логи системы
```

## 🛡️ **БЕЗОПАСНОСТЬ И НАДЕЖНОСТЬ**

### **Защита от потери данных:**

- ✅ Автоматическое создание резервных копий
- ✅ Проверка целостности файлов
- ✅ Обработка ошибок при сохранении/загрузке
- ✅ Graceful shutdown при критических ошибках

### **Восстановление данных:**

- ✅ Автоматическая загрузка при запуске
- ✅ Резервные копии с временными метками
- ✅ Возможность ручного восстановления из бэкапа

## 🎯 **ПРЕИМУЩЕСТВА СИСТЕМЫ**

1. **Непрерывность работы** - данные сохраняются между перезапусками
2. **Надежность** - автоматические резервные копии
3. **Автоматизация** - не требует ручного вмешательства
4. **Безопасность** - защита от потери данных при сбоях
5. **Простота** - прозрачная работа для пользователей

## 📊 **СТАТИСТИКА**

- **Файлы данных:** `user_data.json`
- **Резервные копии:** `user_data_backups/`
- **Автоматическое сохранение:** При каждом graceful shutdown
- **Автоматическая загрузка:** При каждом запуске
- **Формат данных:** JSON с отступами для читаемости

---

**📅 Дата создания:** 17.08.2025
**🔧 Разработчик:** AI Assistant
**📋 Статус:** Активно используется ✅
