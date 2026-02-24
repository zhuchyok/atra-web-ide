# 🎯 LEARNING SESSION #6: Финальные задачи (+20%)

**Дата:** November 23, 2025  
**Команда:** Все 13 сотрудников  
**Статус:** 🚀 **ФИНАЛЬНЫЕ ЗАДАЧИ ГОТОВЫ**

---

## 🔥 КРИТИЧНЫЕ ЗАДАЧИ (Приоритет 1)

### **1. ДМИТРИЙ: SHAP для интерпретации моделей** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** Интерпретация моделей

#### **Задача:**

Добавить SHAP для интерпретации ML моделей.

#### **Реализация:**

```python
# Создать новый файл: ml/shap_explainer.py
import shap
from lightgbm_predictor import LightGBMPredictor

class SHAPExplainer:
    """SHAP explainer для интерпретации моделей"""
    def __init__(self, predictor: LightGBMPredictor):
        self.predictor = predictor
        self.explainer = None

    def fit(self, X_train):
        """Обучает SHAP explainer"""
        if self.predictor.classifier:
            self.explainer = shap.TreeExplainer(self.predictor.classifier)

    def explain(self, X):
        """Объясняет предсказания"""
        shap_values = self.explainer.shap_values(X)
        return shap_values
```

**Файл:** `ml/shap_explainer.py` (новый)

---

### **2. МАКСИМ: Monte Carlo Simulation** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** Stress testing

#### **Задача:**

Реализовать Monte Carlo simulation для stress testing.

#### **Реализация:**

```python
# Создать новый файл: risk/monte_carlo.py
def monte_carlo_simulation(
    returns: np.ndarray,
    n_simulations: int = 10000,
    days: int = 30
) -> Dict:
    """Monte Carlo simulation для stress testing"""
    # Реализация
    pass
```

**Файл:** `risk/monte_carlo.py` (новый)

---

### **3. ИГОРЬ: Cython Optimization** 🔴

**Критичность:** ВЫСОКАЯ  
**Ожидаемый эффект:** Ускорение на 30-40%

#### **Задача:**

Оптимизировать критичные функции с Cython.

#### **Реализация:**

```python
# Создать новый файл: optimizations/cython_utils.pyx
# Cython код для ускорения
```

**Файл:** `optimizations/cython_utils.pyx` (новый)

---

### **4. СЕРГЕЙ: Auto-scaling Configuration** 🔴

**Критичность:** СРЕДНЯЯ  
**Ожидаемый эффект:** Улучшение reliability

#### **Задача:**

Настроить auto-scaling для системы.

---

### **5. АННА: Self-Healing Tests** 🔴

**Критичность:** СРЕДНЯЯ  
**Ожидаемый эффект:** Улучшение качества тестов

#### **Задача:**

Внедрить self-healing механизм для тестов.

---

## ✅ СТАТУС

**Финальные задачи готовы к выполнению!** 🚀

_Задачи созданы: Виктор (Team Lead)_
