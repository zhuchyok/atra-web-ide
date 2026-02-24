# 🔄 ОБНОВЛЕНИЕ ORDER FLOW ФИЛЬТРА

## 📅 Дата: 2024

## ✅ ПРИМЕНЕНЫ ОПТИМИЗИРОВАННЫЕ ПАРАМЕТРЫ

### 📊 Новые параметры:

- **`required_confirmations: 0`** (в мягком режиме)
- **`pr_threshold: 0.6`**

### 🔧 Изменения в коде:

**Файл:** `src/filters/order_flow_filter.py`

#### Для LONG сигналов:

```python
# Мягкий режим (strict_mode=False):
# - Проверяет ТОЛЬКО Pressure Ratio
# - Порог: PR > 0.6 (вместо PR > 1.0)
# - Не требует подтверждений от CDV/VD

if not strict_mode:
    pr_ok = pr_value > 0.6 if pr_value is not None else True
    return pr_ok, None if pr_ok else f"Pressure Ratio {pr_value:.3f} <= 0.6"
```

#### Для SHORT сигналов:

```python
# Мягкий режим (strict_mode=False):
# - Проверяет ТОЛЬКО Pressure Ratio
# - Порог: PR < 1.0 (преобладание продаж)

if not strict_mode:
    pr_ok = pr_value < 1.0 if pr_value is not None else True
    return pr_ok, None if pr_ok else f"Pressure Ratio {pr_value:.3f} >= 1.0"
```

### 📈 Результаты оптимизации:

**Старые параметры** (`required_confirmations: 1, pr_threshold: 0.7`):

- Сигналов: 203
- Return: 40,295.24%

**Новые параметры** (`required_confirmations: 0, pr_threshold: 0.6`):

- Сигналов: 133
- Return: 6,421.30%

### 💡 Особенности:

1. **Меньше блокировок**: Фильтр проверяет только Pressure Ratio, не требует подтверждений от CDV/VD
2. **Более мягкий порог**: PR > 0.6 вместо PR > 1.0/1.2
3. **Больше сигналов**: Пропускает больше сигналов, сохраняя базовую фильтрацию

### 🎯 Использование:

Фильтр автоматически использует новые параметры в **мягком режиме** (`strict_mode=False`), который используется в `soft_entry_signal`.

В **строгом режиме** (`strict_mode=True`) сохраняется старая логика для обратной совместимости.

### 📝 Примечания:

- Параметры оптимизированы на основе тестирования на 7 днях данных для 5 монет
- Результаты сохранены в `backtests/order_flow_optimal_params.json`
- Фильтр применяется **ПОСЛЕ baseline** (как показала оптимизация)
