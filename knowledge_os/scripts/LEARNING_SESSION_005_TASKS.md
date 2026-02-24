# 🎯 LEARNING SESSION #5: Критичные задачи для выполнения

**Дата:** November 23, 2025  
**Команда:** Все 13 сотрудников  
**Статус:** 🚀 **ЗАДАЧИ ГОТОВЫ К ВЫПОЛНЕНИЮ**

---

## 🔥 КРИТИЧНЫЕ ЗАДАЧИ (Приоритет 1)

### **1. ДМИТРИЙ: Model Ensembling (Stacking)** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** +10-15% метрик

#### **Задача:**

Реализовать model ensembling с stacking для улучшения предсказаний.

#### **Реализация:**

```python
# Создать новый файл: ml/ensemble_stacking.py
class StackingEnsemble:
    """Stacking ensemble для улучшения предсказаний"""
    def __init__(self, base_models, meta_model):
        self.base_models = base_models
        self.meta_model = meta_model

    def fit(self, X_train, y_train):
        # Обучаем base models
        # Создаем meta-features
        # Обучаем meta-model
        pass

    def predict(self, X):
        # Предсказания base models
        # Meta-features
        # Предсказание meta-model
        pass
```

**Файл:** `ml/ensemble_stacking.py` (новый)

---

### **2. МАКСИМ: CVaR и MAE метрики** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** Улучшение risk management

#### **Задача:**

Реализовать Conditional Value at Risk (CVaR) и Maximum Adverse Excursion (MAE).

#### **Реализация:**

```python
# Создать новый файл: risk/advanced_metrics.py
def calculate_cvar(returns: np.ndarray, confidence: float = 0.95) -> float:
    """Conditional Value at Risk (CVaR)"""
    var = np.percentile(returns, (1 - confidence) * 100)
    cvar = returns[returns <= var].mean()
    return cvar

def calculate_mae(equity_curve: np.ndarray) -> float:
    """Maximum Adverse Excursion (MAE)"""
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - running_max) / running_max
    mae = np.min(drawdown)
    return mae
```

**Файл:** `risk/advanced_metrics.py` (новый)

---

### **3. ИГОРЬ: Event-Driven Components** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** Улучшение scalability

#### **Задача:**

Реализовать event-driven компоненты для улучшения архитектуры.

#### **Реализация:**

```python
# Создать новый файл: event_bus.py
class EventBus:
    """Event bus для event-driven архитектуры"""
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type: str, handler: Callable):
        """Подписка на событие"""
        pass

    def publish(self, event_type: str, data: Any):
        """Публикация события"""
        pass
```

**Файл:** `event_bus.py` (новый)

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
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

def setup_tracing(service_name: str = "atra"):
    """Настройка distributed tracing"""
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)

    # Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",
        agent_port=6831,
    )

    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

    return tracer
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
    risk_pct=st.floats(min_value=0.1, max_value=10.0),
    entry_price=st.floats(min_value=1, max_value=100000),
    stop_loss_price=st.floats(min_value=1, max_value=100000)
)
def test_position_sizing_properties(balance, risk_pct, entry_price, stop_loss_price):
    """Property-based тест для position sizing"""
    sizer = PositionSizer()
    result = sizer.calculate_position_size(
        balance, entry_price, stop_loss_price, risk_pct
    )

    # Properties:
    assert result['position_size'] >= 0
    assert result['risk_amount'] <= balance * risk_pct / 100
    assert result['margin_used'] <= balance
```

**Файл:** `tests/unit/test_risk_manager.py`

---

## ⚡ ВАЖНЫЕ ЗАДАЧИ (Приоритет 2)

### **6. ЕЛЕНА: OpenTelemetry Integration** 🟡

**Задача:** Интегрировать OpenTelemetry в систему

### **7. ОЛЕГ: Self-Healing Tests** 🟡

**Задача:** Внедрить self-healing механизм для тестов

### **8. ПАВЕЛ: Memory Optimization** 🟡

**Задача:** Оптимизировать memory usage

### **9. МАРИЯ: Interactive Documentation** 🟡

**Задача:** Создать interactive API documentation

### **10. АЛЕКСЕЙ: Advanced Profiling** 🟡

**Задача:** Провести advanced profiling и оптимизацию

### **11. РОМАН: Alternative Data** 🟡

**Задача:** Исследовать использование alternative data

### **12. ДАРЬЯ: Penetration Testing** 🟡

**Задача:** Провести penetration testing системы

### **13. ВИКТОР: Team Optimization** 🟡

**Задача:** Оптимизировать процессы команды

---

## 📊 ПЛАН ВЫПОЛНЕНИЯ

### **День 1-2: Критичные задачи**

- ✅ Дмитрий: Model ensembling
- ✅ Максим: CVaR и MAE метрики
- ✅ Игорь: Event-driven components

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
