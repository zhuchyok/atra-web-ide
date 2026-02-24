# 🎯 LEARNING SESSION #4: Критичные задачи для выполнения

**Дата:** November 23, 2025  
**Команда:** Все 13 сотрудников  
**Статус:** 🚀 **ЗАДАЧИ ГОТОВЫ К ВЫПОЛНЕНИЮ**

---

## 🔥 КРИТИЧНЫЕ ЗАДАЧИ (Приоритет 1)

### **1. ДМИТРИЙ: Lag Features в ML Pipeline** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** +5-10% метрик

#### **Задача:**

Добавить lag features в ML pipeline для улучшения предсказаний.

#### **Реализация:**

```python
# В scripts/retrain_lightgbm.py добавить:
def add_lag_features(df: pd.DataFrame, lags: List[int] = [1, 2, 3, 5, 10]) -> pd.DataFrame:
    """Добавляет lag features для временных рядов"""
    for lag in lags:
        df[f'rsi_lag_{lag}'] = df['rsi'].shift(lag)
        df[f'macd_lag_{lag}'] = df['macd'].shift(lag)
        df[f'volume_lag_{lag}'] = df['volume'].shift(lag)
    return df
```

**Файл:** `scripts/retrain_lightgbm.py`

---

### **2. МАКСИМ: Walk-Forward Optimization** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** Предотвращение overfitting

#### **Задача:**

Реализовать walk-forward optimization для бэктестов.

#### **Реализация:**

```python
# Создать новый файл: backtests/walk_forward_optimization.py
def walk_forward_optimization(
    data: pd.DataFrame,
    train_period: int = 90,
    test_period: int = 30,
    step: int = 30
):
    """Walk-forward optimization для предотвращения overfitting"""
    # Реализация walk-forward
    pass
```

**Файл:** `backtests/walk_forward_optimization.py` (новый)

---

### **3. ИГОРЬ: Circuit Breaker для API** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** Защита от каскадных сбоев

#### **Задача:**

Реализовать circuit breaker pattern для API запросов.

#### **Реализация:**

```python
# Создать новый файл: circuit_breaker.py
class CircuitBreaker:
    """Circuit breaker для защиты от каскадных сбоев"""
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        # ... реализация
```

**Файл:** `circuit_breaker.py` (новый)

---

### **4. СЕРГЕЙ: Distributed Tracing** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** Полная observability

#### **Задача:**

Внедрить distributed tracing с OpenTelemetry.

#### **Реализация:**

```python
# Создать новый файл: observability/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

def setup_tracing():
    """Настройка distributed tracing"""
    trace.set_tracer_provider(TracerProvider())
    # ... настройка
```

**Файл:** `observability/tracing.py` (новый)

---

### **5. АННА: Property-Based Testing** 🔴

**Критичность:** СРЕДНЯЯ  
**Ожидаемый эффект:** Нахождение edge cases

#### **Задача:**

Внедрить property-based testing с Hypothesis.

#### **Реализация:**

```python
# В tests/unit/test_risk_manager.py добавить:
from hypothesis import given, strategies as st

@given(
    balance=st.floats(min_value=100, max_value=100000),
    risk_pct=st.floats(min_value=0.1, max_value=10.0)
)
def test_position_sizing_properties(balance, risk_pct):
    """Property-based тест для position sizing"""
    # Тестируем свойства функции
    pass
```

**Файл:** `tests/unit/test_risk_manager.py`

---

## ⚡ ВАЖНЫЕ ЗАДАЧИ (Приоритет 2)

### **6. ЕЛЕНА: OpenTelemetry Integration** 🟡

**Задача:** Интегрировать OpenTelemetry в систему

### **7. ОЛЕГ: Self-Healing Tests** 🟡

**Задача:** Внедрить self-healing механизм для тестов

### **8. ПАВЕЛ: Database Query Optimization** 🟡

**Задача:** Оптимизировать медленные SQL запросы

### **9. МАРИЯ: Interactive Documentation** 🟡

**Задача:** Создать interactive API documentation

### **10. АЛЕКСЕЙ: Memory Profiling** 🟡

**Задача:** Провести memory profiling и оптимизацию

### **11. РОМАН: Alternative Data Research** 🟡

**Задача:** Исследовать использование alternative data

### **12. ДАРЬЯ: Penetration Testing** 🟡

**Задача:** Провести penetration testing системы

### **13. ВИКТОР: Team Processes Optimization** 🟡

**Задача:** Оптимизировать процессы команды

---

## 📊 ПЛАН ВЫПОЛНЕНИЯ

### **День 1-2: Критичные задачи**

- ✅ Дмитрий: Lag features
- ✅ Максим: Walk-forward optimization
- ✅ Игорь: Circuit breaker

### **День 3-4: Важные задачи**

- ✅ Сергей: Distributed tracing
- ✅ Анна: Property-based testing
- ✅ Елена: OpenTelemetry

### **День 5-7: Остальные задачи**

- ✅ Олег, Павел, Мария, Алексей, Роман, Дарья, Виктор

---

## ✅ СТАТУС

**Задачи готовы к выполнению!** 🚀

_Задачи созданы: Виктор (Team Lead)_
