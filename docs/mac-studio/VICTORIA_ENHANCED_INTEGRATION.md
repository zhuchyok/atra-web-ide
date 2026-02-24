# 🚀 Victoria Enhanced - Интеграция новых компонентов

**Дата:** 2026-01-25  
**Статус:** ✅ Готово к использованию

---

## 🎯 Обзор

Victoria Enhanced - это обертка над Victoria, которая автоматически использует все новые компоненты супер-корпорации для максимальной эффективности.

---

## ✅ Интегрированные компоненты

### Автоматический выбор метода:

| Категория задачи | Используемый метод              | Компоненты                               |
| ---------------- | ------------------------------- | ---------------------------------------- |
| **Reasoning**    | Extended Thinking + ReCAP       | ExtendedThinkingEngine, ReCAPFramework   |
| **Planning**     | Tree of Thoughts + Hierarchical | TreeOfThoughts, HierarchicalOrchestrator |
| **Complex**      | Swarm + Consensus               | SwarmIntelligence, ConsensusAgent        |
| **Execution**    | ReAct Framework                 | ReActAgent                               |
| **General**      | Extended Thinking               | ExtendedThinkingEngine                   |

---

## 🚀 Использование

### Через Victoria Enhanced напрямую:

```python
from knowledge_os.app.victoria_enhanced import VictoriaEnhanced

victoria = VictoriaEnhanced(
    model_name="deepseek-r1-distill-llama:70b",
    use_react=True,
    use_extended_thinking=True,
    use_swarm=True,
    use_consensus=True,
    use_collective_memory=True
)

# Автоматический выбор метода
result = await victoria.solve("Реши сложную задачу...")

# Или явно указать метод
result = await victoria.solve("Задача...", method="swarm")
```

### Через Victoria Server (HTTP API):

```bash
# Включить enhanced режим
export USE_VICTORIA_ENHANCED=true

# Запустить Victoria
python src/agents/bridge/victoria_server.py

# Использовать через API
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "Реши сложную задачу..."}'
```

### Тестирование:

```bash
# Запустить тесты
python scripts/test_victoria_enhanced.py
```

---

## 📊 Примеры работы

### Reasoning задача:

```python
result = await victoria.solve("Реши задачу: 2+2*2")
# Использует: Extended Thinking
# Результат: Пошаговое рассуждение с высокой уверенностью
```

### Planning задача:

```python
result = await victoria.solve("Спланируй оптимизацию БД")
# Использует: Tree of Thoughts
# Результат: Структурированный план с multi-branch exploration
```

### Complex задача:

```python
result = await victoria.solve("Как улучшить мультиагентную систему?")
# Использует: Swarm Intelligence (16 агентов)
# Результат: Коллективный интеллект, consensus
```

### Execution задача:

```python
result = await victoria.solve("Выполни анализ кода")
# Использует: ReAct Framework
# Результат: Think → Act → Observe → Reflect цикл
```

---

## 🔧 Конфигурация

### Переменные окружения:

```bash
# Использовать Victoria Enhanced в сервере
USE_VICTORIA_ENHANCED=true

# Модель по умолчанию
VICTORIA_MODEL=deepseek-r1-distill-llama:70b

# Включить/выключить компоненты
VICTORIA_USE_REACT=true
VICTORIA_USE_EXTENDED_THINKING=true
VICTORIA_USE_SWARM=true
VICTORIA_USE_CONSENSUS=true
VICTORIA_USE_COLLECTIVE_MEMORY=true
```

---

## 📈 Ожидаемые улучшения

| Метрика              | Улучшение           |
| -------------------- | ------------------- |
| **Reasoning задачи** | +40-60% качества    |
| **Planning задачи**  | +50-70% качества    |
| **Complex задачи**   | +50-70% через Swarm |
| **Execution задачи** | +30-40% через ReAct |
| **Общее качество**   | +50-80%             |

---

## ✅ Статус компонентов

Проверка доступности:

```python
status = await victoria.get_status()
# Показывает какие компоненты доступны
```

---

**Версия:** 1.0  
**Обновлено:** 2026-01-25
