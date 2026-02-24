# 📦 Production модели на Mac Studio M4 Max

**Дата обновления:** 2025-01-21  
**Статус:** ⚠️ **ОЖИДАЮТСЯ** (настройка конфигурации)

---

## 🎯 PRODUCTION МОДЕЛИ (ОСНОВНОЙ СТЕК)

### 1. **Reasoning (Сложные задачи)**

#### Приоритет 1: Production модель

- ⚠️ `deepseek-r1-distill-llama-70b` (55GB)
  - **Статус:** Ожидается установка
  - **Назначение:** Самый мощный для reasoning задач
  - **Форматы:** `deepseek-r1-distill-llama-70b:instruct-q6_k`, `deepseek-r1-distill-llama-70b:q6_k`

#### Приоритет 2: Альтернативы

- ⚠️ `llama3.3:70b` (35GB)
- ⚠️ `llama3.3-70b-instruct` (35GB)

#### Fallback (работает сейчас)

- ✅ `deepseek-r1:7b` (4.7GB) - **УСТАНОВЛЕН**

---

### 2. **Coding (Разработка)**

#### Приоритет 1: Production модель

- ⚠️ `qwen2.5-coder-32b` (35GB)
  - **Статус:** Ожидается установка
  - **Назначение:** Самый мощный для кодирования
  - **Форматы:** `qwen2.5-coder-32b-instruct`, `qwen2.5-coder-32b-instruct:q8_0`

#### Fallback (работают сейчас)

- ✅ `qwen2.5-coder:7b` (4.7GB) - **УСТАНОВЛЕН**
- ✅ `qwen2.5-coder:3b` (1.9GB) - **УСТАНОВЛЕН**

---

### 3. **Fast (Быстрые задачи)**

#### Приоритет 1: Production модели

- ⚠️ `phi3.5-mini-4k` (2GB)
  - **Статус:** Ожидается установка
  - **Форматы:** `phi3.5-mini-4k-instruct`, `phi3.5-mini-4k-instruct:q4_k_m`

- ⚠️ `phi3-mini-4k-instruct` (2GB)
  - **Статус:** Ожидается установка

#### Fallback (работает сейчас)

- ✅ `phi4:latest` (9.1GB) - **УСТАНОВЛЕН**

---

### 4. **Tiny (Очень быстрые)**

#### Приоритет 1: Production модели

- ⚠️ `tinyllama:1.1b-chat-v1.0-q4_0` (0.7GB)
  - **Статус:** Ожидается установка
  - **Форматы:** `tinyllama:1.1b-chat`

- ⚠️ `qwen2.5-3b-instruct` (2GB)
  - **Статус:** Ожидается установка
  - **Форматы:** `qwen2.5-3b-instruct:q4_k_m`

#### Fallback (работает сейчас)

- ✅ `qwen2.5-coder:3b` (1.9GB) - **УСТАНОВЛЕН**

---

### 5. **Large (Очень сложные задачи)**

#### Приоритет 1: Production модель

- ⚠️ `command-r-plus` (65GB)
  - **Статус:** Ожидается установка
  - **Назначение:** Очень мощная модель для сложных задач
  - **Форматы:** `command-r-plus:q4_k_m`

#### Альтернативы

- ⚠️ `llama3.3:70b` (35GB)
- ⚠️ `qwen2.5-coder-32b` (35GB)

---

## 📋 УСТАНОВКА PRODUCTION МОДЕЛЕЙ

### Через Ollama:

```bash
# Основной стек
ollama pull deepseek-r1-distill-llama-70b:instruct-q6_k   # 55GB
ollama pull qwen2.5-coder-32b-instruct:q8_0                # 35GB
ollama pull phi3.5-mini-4k-instruct:q4_k_m                 # 2GB

# Мелкие модели
ollama pull tinyllama:1.1b-chat-v1.0-q4_0                  # 0.7GB
ollama pull qwen2.5-3b-instruct:q4_k_m                     # 2GB
ollama pull phi3-mini-4k-instruct:q4_k_m                   # 2GB

# Дополнительные
ollama pull llama3.3-70b-instruct:q6_k                     # 35GB
ollama pull command-r-plus:q4_k_m                          # 65GB
```

---

## 🔧 КОНФИГУРАЦИЯ

### MODEL_PRIORITIES настроен с поддержкой:

1. **Автоматический поиск** - система пробует разные варианты имен
2. **Fallback** - если production модель недоступна, использует установленную
3. **Приоритеты** - самые мощные модели имеют приоритет

### Пример работы:

```
🔍 Выбор модели для категории 'reasoning'...
   Проверка: deepseek-r1-distill-llama-70b (55GB)
   ⏭️  Модель недоступна
   Проверка: llama3.3:70b (35GB)
   ⏭️  Модель недоступна
   Проверка: deepseek-r1:7b (4.7GB)
✅ Выбрана модель: deepseek-r1:7b (приоритет 3)
```

---

## ✅ ТЕКУЩИЙ СТАТУС

### Установлены и работают:

- ✅ `deepseek-r1:7b` (4.7GB) - Reasoning fallback
- ✅ `qwen2.5-coder:7b` (4.7GB) - Coding fallback
- ✅ `qwen2.5-coder:3b` (1.9GB) - Tiny fallback
- ✅ `phi4:latest` (9.1GB) - Fast fallback

### Ожидаются (production):

- ⚠️ `deepseek-r1-distill-llama-70b` (55GB) - Reasoning
- ⚠️ `qwen2.5-coder-32b` (35GB) - Coding
- ⚠️ `phi3.5-mini-4k` (2GB) - Fast
- ⚠️ `tinyllama:1.1b-chat` (0.7GB) - Tiny
- ⚠️ `qwen2.5-3b-instruct` (2GB) - Tiny
- ⚠️ `phi3-mini-4k-instruct` (2GB) - Fast
- ⚠️ `llama3.3:70b` (35GB) - Large
- ⚠️ `command-r-plus` (65GB) - Large

---

## 🚀 ПОСЛЕ УСТАНОВКИ

После установки production моделей:

1. ✅ Система автоматически начнет использовать их
2. ✅ Fallback на текущие модели останется доступным
3. ✅ Приоритеты настроены правильно
4. ✅ Все модели будут проверяться автоматически

---

_Конфигурация обновлена командой экспертов ATRA - 2025-01-21_
