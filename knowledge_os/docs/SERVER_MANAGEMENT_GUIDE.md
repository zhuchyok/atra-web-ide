# 🚀 РУКОВОДСТВО ПО УПРАВЛЕНИЮ СЕРВЕРОМ ATRA

## 📋 **ОБЗОР**

Система управления сервером позволяет **выбирать и запускать только нужные компоненты**, отключая лишние мониторы и конфликтующие процессы.

## 🎯 **ОСНОВНЫЕ ПРИНЦИПЫ**

### ✅ **ВКЛЮЧЕНО ПО УМОЛЧАНИЮ:**

- **core** - Основная система (main.py)
- **telegram_bot** - Telegram бот
- **ai_system** - ИИ система
- **price_monitor** - Мониторинг цен
- **optimization** - Система оптимизации
- **signals** - Генерация сигналов

### ❌ **ОТКЛЮЧЕНО ПО УМОЛЧАНИЮ:**

- **monitoring** - Мониторинг системы (конфликтует)
- **auto_restart** - Автоперезапуск (конфликтует)
- **rest_api** - REST API (не обязательно)
- **web_dashboard** - Web дашборд (не обязательно)

## 🛠️ **ИСПОЛЬЗОВАНИЕ**

### **1. Быстрые команды:**

```bash
# Запустить сервер
./atra_server.sh start

# Остановить сервер
./atra_server.sh stop

# Перезапустить сервер
./atra_server.sh restart

# Показать статус
./atra_server.sh status
```

### **2. Управление компонентами:**

```bash
# Включить мониторинг (если нужен)
./atra_server.sh enable monitoring

# Отключить автоперезапуск (рекомендуется)
./atra_server.sh disable auto_restart

# Включить REST API
./atra_server.sh enable rest_api

# Отключить Web дашборд
./atra_server.sh disable web_dashboard
```

### **3. Продвинутое управление:**

```bash
# Прямое использование менеджера
python3 server_manager.py start
python3 server_manager.py stop
python3 server_manager.py status
python3 server_manager.py enable monitoring
python3 server_manager.py disable auto_restart
```

## 📊 **КОМПОНЕНТЫ СИСТЕМЫ**

### **🔧 ОСНОВНЫЕ (обязательные):**

- **core** - Основная система (main.py)
- **telegram_bot** - Telegram бот

### **🤖 ИИ И АНАЛИЗ:**

- **ai_system** - ИИ система обучения
- **optimization** - Автоматическая оптимизация
- **signals** - Генерация торговых сигналов

### **📈 МОНИТОРИНГ:**

- **price_monitor** - Мониторинг цен и TP/SL
- **monitoring** - Мониторинг системы (опционально)

### **🌐 ВЕБ-ИНТЕРФЕЙС:**

- **rest_api** - REST API для внешних систем
- **web_dashboard** - Web дашборд

### **🔄 АВТОМАТИЗАЦИЯ:**

- **auto_restart** - Автоперезапуск при сбоях

## ⚠️ **ВАЖНЫЕ ПРАВИЛА**

### **❌ НЕ ЗАПУСКАЙТЕ ОДНОВРЕМЕННО:**

- `monitoring` + `auto_restart` (конфликт)
- `main.py` + `system_monitor.py` (конфликт)
- `start_with_monitor.py` + `auto_restart_bot.py` (конфликт)

### **✅ РЕКОМЕНДУЕМАЯ КОНФИГУРАЦИЯ:**

```bash
# Для стабильной работы
./atra_server.sh start

# Для разработки (с мониторингом)
./atra_server.sh enable monitoring
./atra_server.sh restart
```

## 🔧 **НАСТРОЙКА ДЛЯ СЕРВЕРА**

### **1. Минимальная конфигурация (рекомендуется):**

```bash
./atra_server.sh disable monitoring
./atra_server.sh disable auto_restart
./atra_server.sh disable rest_api
./atra_server.sh disable web_dashboard
./atra_server.sh start
```

### **2. Полная конфигурация (для продвинутых пользователей):**

```bash
./atra_server.sh enable monitoring
./atra_server.sh enable rest_api
./atra_server.sh enable web_dashboard
./atra_server.sh start
```

### **3. Только автоперезапуск (для нестабильных серверов):**

```bash
./atra_server.sh disable monitoring
./atra_server.sh enable auto_restart
./atra_server.sh start
```

## 📁 **ФАЙЛЫ СИСТЕМЫ**

- **`server_manager.py`** - Основной менеджер
- **`atra_server.sh`** - Скрипт управления
- **`server_config.json`** - Конфигурация
- **`SERVER_MANAGEMENT_GUIDE.md`** - Это руководство

## 🚨 **РЕШЕНИЕ ПРОБЛЕМ**

### **Проблема: Система постоянно перезапускается**

```bash
# Отключить конфликтующие мониторы
./atra_server.sh disable monitoring
./atra_server.sh disable auto_restart
./atra_server.sh restart
```

### **Проблема: Нужен автоперезапуск**

```bash
# Включить только автоперезапуск
./atra_server.sh disable monitoring
./atra_server.sh enable auto_restart
./atra_server.sh restart
```

### **Проблема: Нужен мониторинг**

```bash
# Включить только мониторинг
./atra_server.sh disable auto_restart
./atra_server.sh enable monitoring
./atra_server.sh restart
```

## 🎯 **РЕКОМЕНДАЦИИ ПО ИСПОЛЬЗОВАНИЮ**

### **Для продакшена:**

- Используйте только `core` + `telegram_bot` + `ai_system`
- Отключите все мониторы для стабильности

### **Для разработки:**

- Включите `monitoring` для отслеживания
- Отключите `auto_restart` для ручного управления

### **Для нестабильных серверов:**

- Включите `auto_restart` для автоматического восстановления
- Отключите `monitoring` для избежания конфликтов

## 📞 **ПОДДЕРЖКА**

При возникновении проблем:

1. Проверьте статус: `./atra_server.sh status`
2. Остановите все: `./atra_server.sh stop`
3. Запустите заново: `./atra_server.sh start`
4. Проверьте логи в папке `logs/`
