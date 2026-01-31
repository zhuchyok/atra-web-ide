# 🧪 Руководство по тестированию Enhanced режима

**Дата:** 2026-01-25  
**Версия:** 1.0

---

## 📋 Обзор

Это руководство описывает процесс тестирования всех 13 компонентов супер-корпорации ATRA.

---

## 🚀 Быстрый старт

### 1. Comprehensive Test Suite

Запуск всех тестов компонентов:

```bash
python scripts/test_enhanced_comprehensive.py
```

**Что тестируется:**
- ✅ ReAct Framework
- ✅ Extended Thinking
- ✅ Tree of Thoughts
- ✅ Swarm Intelligence
- ✅ Consensus Agent
- ✅ Collective Memory
- ✅ ReCAP Framework
- ✅ Автоматический выбор метода

**Результаты:**
- Сохраняются в `docs/mac-studio/test_results/enhanced_test_*.json`
- Выводятся в консоль

### 2. Benchmark Tests

Сравнение Enhanced vs Standard режимов:

```bash
python scripts/run_enhanced_benchmarks.py
```

**Что измеряется:**
- ⏱️ Время выполнения
- ✅ Success rate
- 📊 Улучшение качества
- 🎯 Выбор метода

**Результаты:**
- Сохраняются в `docs/mac-studio/test_results/benchmark_*.json`
- Сравнительная статистика

---

## 📊 Интерпретация результатов

### Comprehensive Test Suite

**Успешный тест:**
```json
{
  "status": "passed",
  "method": "extended_thinking",
  "time": 2.45,
  "confidence": 0.95,
  "thinking_steps": 5
}
```

**Проваленный тест:**
```json
{
  "status": "failed",
  "error": "Connection timeout"
}
```

**Пропущенный тест:**
```json
{
  "status": "skipped",
  "reason": "Component not available"
}
```

### Benchmark Tests

**Метрики:**
- `avg_time` - среднее время выполнения
- `success_rate` - процент успешных выполнений
- `time_improvement` - улучшение времени в %
- `success_improvement` - улучшение success rate в %

**Ожидаемые результаты:**
- Enhanced режим должен быть медленнее на 10-30% (из-за дополнительной обработки)
- Success rate должен быть выше на 20-40%
- Качество ответов должно быть выше

---

## 🔧 Настройка тестов

### Переменные окружения

```bash
# Использовать локальные модели
export OLLAMA_BASE_URL=http://localhost:11434

# Использовать удаленный сервер
export OLLAMA_BASE_URL=http://185.177.216.15:11434

# Включить детальное логирование
export LOG_LEVEL=DEBUG
```

### Кастомизация тестов

Редактируйте `scripts/test_enhanced_comprehensive.py`:
- Добавьте новые тесты в `run_all_tests()`
- Измените тестовые задачи
- Настройте таймауты

---

## 📈 Метрики качества

### Ключевые метрики:

1. **Accuracy** - точность ответов
2. **Latency** - время выполнения
3. **Success Rate** - процент успешных выполнений
4. **Method Selection** - правильность выбора метода
5. **Resource Usage** - использование ресурсов

### Целевые значения:

- ✅ Success Rate: >90%
- ✅ Latency: <5s для большинства задач
- ✅ Method Selection: >85% правильных выборов
- ✅ Accuracy: +20-40% vs Standard режим

---

## 🐛 Отладка

### Проблемы с подключением:

```bash
# Проверить доступность Ollama
curl http://localhost:11434/api/tags

# Проверить Victoria Enhanced
curl http://localhost:8010/health
```

### Проблемы с компонентами:

```python
# Проверить доступность компонентов
from app.victoria_enhanced import VictoriaEnhanced
enhanced = VictoriaEnhanced()
print(f"ReAct: {enhanced.react_agent is not None}")
print(f"Extended Thinking: {enhanced.extended_thinking is not None}")
```

---

## 📝 Отчеты

### Автоматические отчеты:

Тесты автоматически создают JSON отчеты в:
- `docs/mac-studio/test_results/enhanced_test_*.json`
- `docs/mac-studio/test_results/benchmark_*.json`

### Анализ результатов:

```bash
# Просмотр последних результатов
ls -lt docs/mac-studio/test_results/ | head -5

# Анализ JSON
python -m json.tool docs/mac-studio/test_results/enhanced_test_*.json
```

---

## 🔄 Непрерывное тестирование

### CI/CD интеграция:

```yaml
# .github/workflows/test-enhanced.yml
name: Test Enhanced
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: python scripts/test_enhanced_comprehensive.py
```

---

## 📚 Дополнительные ресурсы

- `docs/mac-studio/SUPER_CORPORATION_STATUS.md` - статус компонентов
- `docs/mac-studio/VICTORIA_ENHANCED_INTEGRATION.md` - интеграция
- `docs/mac-studio/NEXT_STEPS_ROADMAP.md` - roadmap развития

---

**Обновлено:** 2026-01-25
