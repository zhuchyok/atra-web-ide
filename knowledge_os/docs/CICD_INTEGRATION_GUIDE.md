# 🔄 Руководство по интеграции в CI/CD Pipeline

## 🎯 Цель

Интеграция Self-Validating Code принципов в CI/CD pipeline для автоматической проверки качества кода, обнаружения антипаттернов и мониторинга метрик.

---

## 📋 Компоненты для интеграции

### 1. Anti-Pattern Detection

**Файл:** `src/core/anti_pattern_detector.py`

**Использование:**
```python
from src.core.anti_pattern_detector import get_anti_pattern_detector

detector = get_anti_pattern_detector()
patterns = detector.detect_in_code(code, "file.py")

# Проверка критичных ошибок
critical_patterns = [p for p in patterns if p.severity == "error"]
if critical_patterns:
    print(f"Обнаружено {len(critical_patterns)} критичных антипаттернов")
    exit(1)
```

**CI/CD скрипт:**
```bash
#!/bin/bash
# scripts/ci/check_anti_patterns.sh

python3 -c "
from src.core.anti_pattern_detector import get_anti_pattern_detector
import os
import sys

detector = get_anti_pattern_detector()
errors = 0

for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r') as f:
                code = f.read()
            patterns = detector.detect_in_code(code, filepath)
            critical = [p for p in patterns if p.severity == 'error']
            if critical:
                print(f'❌ {filepath}: {len(critical)} критичных антипаттернов')
                for p in critical:
                    print(f'  - {p.message} (строка {p.line_number})')
                errors += len(critical)

if errors > 0:
    sys.exit(1)
else:
    print('✅ Антипаттерны не обнаружены')
"
```

---

### 2. Performance Profiling

**Файл:** `src/core/profiling.py`

**Использование:**
```python
from src.core.profiling import get_profiler

profiler = get_profiler()
stats = profiler.get_latency_stats("function_name")

# Проверка узких мест
bottlenecks = profiler.detect_bottlenecks(threshold_ms=100.0)
if bottlenecks:
    print(f"Обнаружено {len(bottlenecks)} узких мест")
```

**CI/CD скрипт:**
```bash
#!/bin/bash
# scripts/ci/check_performance.sh

python3 -c "
from src.core.profiling import get_profiler
import sys

profiler = get_profiler()
# Запускаем тесты с профилированием
# ... (запуск тестов)

stats = profiler.get_latency_stats()
bottlenecks = profiler.detect_bottlenecks(threshold_ms=100.0)

if bottlenecks:
    print('⚠️ Обнаружены узкие места:')
    for b in bottlenecks:
        print(f'  - {b.function_name}: {b.duration_ms:.2f}ms')
    # Не прерываем CI, только предупреждаем
else:
    print('✅ Узких мест не обнаружено')
"
```

---

### 3. Self-Validation

**Файл:** `src/core/self_validation.py`

**Использование:**
```python
from src.core.self_validation import get_validation_manager
from src.core.invariants import register_all_invariants

register_all_invariants()
manager = get_validation_manager()

# Валидация объектов в тестах
results = manager.validate_object(signal, "TradeSignal")
errors = [r for r in results if not r.passed and r.level.value == "error"]
if errors:
    print(f"Обнаружено {len(errors)} нарушений инвариантов")
```

**CI/CD скрипт:**
```bash
#!/bin/bash
# scripts/ci/check_invariants.sh

python3 -c "
from src.core.self_validation import get_validation_manager
from src.core.invariants import register_all_invariants
import sys

register_all_invariants()
manager = get_validation_manager()

# Запускаем тесты, которые создают объекты
# ... (запуск тестов)

# Проверяем результаты валидации
# (интеграция в тесты)
"
```

---

### 4. Contract-Based Programming

**Файл:** `src/core/contracts.py`

**Использование:**
Контракты автоматически проверяются при вызове функций. В CI/CD можно добавить тесты, которые проверяют нарушение контрактов:

```python
import pytest
from src.core.contracts import ContractViolationError

def test_precondition_violation():
    from src.signals.risk import get_dynamic_tp_levels
    
    with pytest.raises(ContractViolationError):
        get_dynamic_tp_levels(None, -1, "invalid")
```

---

## 🔧 Интеграция в GitHub Actions

**Файл:** `.github/workflows/quality_checks.yml`

```yaml
name: Quality Checks

on:
  pull_request:
    branches: [ main, develop ]
  push:
    branches: [ main, develop ]

jobs:
  anti-patterns:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Check anti-patterns
        run: bash scripts/ci/check_anti_patterns.sh

  self-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests with validation
        run: pytest tests/ -v

  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Check performance
        run: bash scripts/ci/check_performance.sh
```

---

## 🔧 Интеграция в GitLab CI

**Файл:** `.gitlab-ci.yml`

```yaml
stages:
  - quality
  - test

anti-patterns:
  stage: quality
  script:
    - pip install -r requirements.txt
    - bash scripts/ci/check_anti_patterns.sh
  only:
    - merge_requests
    - main
    - develop

self-validation:
  stage: test
  script:
    - pip install -r requirements.txt
    - pytest tests/ -v
  only:
    - merge_requests
    - main
    - develop

performance:
  stage: quality
  script:
    - pip install -r requirements.txt
    - bash scripts/ci/check_performance.sh
  only:
    - merge_requests
    - main
    - develop
```

---

## 📊 Метрики для мониторинга

### Prometheus метрики

**Файл:** `src/core/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

# Метрики антипаттернов
anti_pattern_counter = Counter(
    'code_anti_patterns_total',
    'Total number of anti-patterns detected',
    ['severity', 'type']
)

# Метрики производительности
function_latency = Histogram(
    'function_latency_seconds',
    'Function execution latency',
    ['function_name']
)

# Метрики валидации
invariant_violations = Counter(
    'invariant_violations_total',
    'Total number of invariant violations',
    ['class_name', 'invariant_name']
)
```

### Grafana дашборды

**Пример конфигурации:**
- **Панель 1:** Количество антипаттернов по типам
- **Панель 2:** Latency критичных функций (P50, P95, P99)
- **Панель 3:** Количество нарушений инвариантов по классам
- **Панель 4:** Узкие места производительности

---

## 🚨 Алерты

### Настройка алертов в Prometheus

```yaml
groups:
  - name: code_quality
    rules:
      - alert: HighAntiPatternCount
        expr: rate(code_anti_patterns_total{severity="error"}[5m]) > 10
        annotations:
          summary: "Высокое количество критичных антипаттернов"
      
      - alert: SlowFunction
        expr: function_latency_seconds{quantile="0.95"} > 1.0
        annotations:
          summary: "Функция {{ $labels.function_name }} медленная"
      
      - alert: InvariantViolations
        expr: rate(invariant_violations_total[5m]) > 5
        annotations:
          summary: "Высокое количество нарушений инвариантов"
```

---

## ✅ Чек-лист интеграции

- [ ] Создать скрипты CI/CD для проверки антипаттернов
- [ ] Добавить проверки в GitHub Actions / GitLab CI
- [ ] Настроить Prometheus метрики
- [ ] Создать Grafana дашборды
- [ ] Настроить алерты
- [ ] Добавить проверки контрактов в тесты
- [ ] Интегрировать профилирование в тесты производительности
- [ ] Документировать процесс

---

## 📚 Дополнительные ресурсы

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

---

**Автор:** Команда ATRA  
**Дата:** 2025-01-XX  
**Версия:** 1.0

