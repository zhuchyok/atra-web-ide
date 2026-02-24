# 🛡️ САМОВОССТАНАВЛИВАЮЩАЯСЯ СИСТЕМА С ДУБЛИРОВАНИЕМ КАНАЛОВ

**Дата:** 2026-01-25  
**Статус:** 🚧 **В РАЗРАБОТКЕ**

---

## 🎯 ЦЕЛЬ

Создать полностью самовосстанавливающуюся и самопроверяющуюся систему с дублированием критических каналов для обеспечения максимальной надежности корпорации ATRA.

---

## 🏗️ АРХИТЕКТУРА

### **1. ResilientChannelManager** ✅

**Назначение:** Менеджер дублированных каналов с автоматическим переключением

**Возможности:**

- ✅ Регистрация множественных каналов для одного сервиса
- ✅ Health checks всех каналов
- ✅ Автоматическое переключение при сбоях
- ✅ Автоматическое восстановление упавших каналов
- ✅ Метрики и статистика

**Пример использования:**

```python
from resilient_channel_manager import get_resilient_manager

manager = get_resilient_manager()

# Регистрация каналов для Ollama
manager.register_channel(
    service_name="ollama",
    name="Ollama Primary",
    url="http://host.docker.internal:11434",
    priority=1
)
manager.register_channel(
    service_name="ollama",
    name="Ollama Backup",
    url="http://185.177.216.15:11434",
    priority=2
)

# Получение лучшего канала
channel = await manager.get_best_channel("ollama")

# Выполнение с автоматическим fallback
result = await manager.execute_with_fallback(
    "ollama",
    lambda channel, prompt: call_ollama(channel.url, prompt),
    "test prompt"
)
```

### **2. SelfCheckSystem** ✅

**Назначение:** Система самопроверки всех компонентов

**Проверяет:**

- ✅ Victoria Agent
- ✅ Veronica Agent
- ✅ Knowledge OS Database
- ✅ Ollama/MLX
- ✅ Redis
- ✅ Elasticsearch
- ✅ Автономные системы (Nightly Learner, Debate Processor, Smart Worker)

**Возможности:**

- ✅ Автоматическая проверка всех компонентов
- ✅ Диагностика проблем
- ✅ Автоматическое исправление (перезапуск сервисов)
- ✅ Отчетность и алерты

**Пример использования:**

```python
from self_check_system import get_self_check_system

system = get_self_check_system()

# Запуск мониторинга
await system.start_monitoring()

# Ручная проверка
report = await system.run_full_check()
```

---

## 🔄 ПРИНЦИПЫ РАБОТЫ

### **Дублирование каналов:**

1. **Приоритеты:** Каждый канал имеет приоритет (1 = высший)
2. **Health checks:** Постоянный мониторинг состояния всех каналов
3. **Автоматическое переключение:** При сбое активного канала автоматически переключается на резервный
4. **Автоматическое восстановление:** Попытки восстановить упавшие каналы

### **Самопроверка:**

1. **Периодические проверки:** Каждые 60 секунд (настраивается)
2. **Диагностика:** Детальный анализ проблем
3. **Автоматическое исправление:** Перезапуск упавших сервисов
4. **Алерты:** Уведомления о критических проблемах

---

## 📊 ИНТЕГРАЦИЯ

### **Victoria Agent:**

```python
# В victoria_server.py
from resilient_channel_manager import get_resilient_manager

manager = get_resilient_manager()

# Регистрация каналов при инициализации
manager.register_channel("ollama", "Ollama Local", "http://host.docker.internal:11434", priority=1)
manager.register_channel("ollama", "Ollama Server", "http://185.177.216.15:11434", priority=2)

# Использование в step()
async def step(self, prompt: str):
    channel = await manager.get_best_channel("ollama")
    if channel:
        result = await call_ollama(channel.url, prompt)
        return result
```

### **LocalAIRouter:**

```python
# В local_router.py
from resilient_channel_manager import get_resilient_manager

manager = get_resilient_manager()

# Использование вместо прямых вызовов
async def run_local_llm(self, prompt: str, ...):
    result = await manager.execute_with_fallback(
        "ollama",
        lambda channel, p: self._call_ollama(channel.url, p),
        prompt
    )
    return result
```

---

## 🚀 ПЛАН ВНЕДРЕНИЯ

### **Этап 1: Базовые компоненты** ✅

- [x] ResilientChannelManager
- [x] SelfCheckSystem

### **Этап 2: Интеграция** 🚧

- [ ] Интеграция в Victoria Agent
- [ ] Интеграция в LocalAIRouter
- [ ] Интеграция в Veronica Agent

### **Этап 3: Автономный мониторинг** 🚧

- [ ] Запуск SelfCheckSystem как автономного процесса
- [ ] Интеграция с ELK для логирования
- [ ] Интеграция с Telegram для алертов

### **Этап 4: Расширение** 📋

- [ ] Дублирование для Database
- [ ] Дублирование для Redis
- [ ] Дублирование для Elasticsearch
- [ ] Метрики в Prometheus

---

## 📈 МЕТРИКИ

**ResilientChannelManager отслеживает:**

- Количество переключений между каналами
- Количество успешных/неуспешных запросов
- Время ответа каждого канала
- Количество автоматических восстановлений

**SelfCheckSystem отслеживает:**

- Статус каждого компонента
- Количество автоматических исправлений
- История проверок
- Время восстановления

---

## 🎯 РЕЗУЛЬТАТ

**Система обеспечивает:**

- ✅ **Высокую доступность:** Автоматическое переключение на резервные каналы
- ✅ **Самовосстановление:** Автоматическое исправление проблем
- ✅ **Самопроверку:** Постоянный мониторинг всех компонентов
- ✅ **Надежность:** Дублирование критических каналов
- ✅ **Прозрачность:** Детальная статистика и метрики

---

_Документ создан 2026-01-25_
