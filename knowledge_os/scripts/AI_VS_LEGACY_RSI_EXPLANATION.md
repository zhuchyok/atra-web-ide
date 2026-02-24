# 🤖 AI VS LEGACY RSI: КАК ЭТО РАБОТАЕТ

**Дата:** 2025-11-20  
**Вопрос:** У нас не ИИ эти параметры регулировало?

---

## ✅ ОТВЕТ: ДА, ЧАСТИЧНО

### Система использует A/B тестирование:

**50% символов → Группа A (Smart RSI Filter с AI)** 🤖  
**50% символов → Группа B (Legacy, фиксированные пороги)** 📊

---

## 🔍 КАК ЭТО РАБОТАЕТ

### 1. Определение группы (строка 1807):

```python
def get_rsi_experiment_group(symbol: str, timestamp: Optional[datetime]) -> str:
    """Детерминированно распределяет символы по группам A/B"""
    unique_key = f"{symbol}:{timestamp.strftime('%Y%m%d')}"
    group_hash = _deterministic_hash(unique_key) % 100
    return "A" if group_hash < 50 else "B"  # 50/50 распределение
```

**Результат:**

- BTCUSDT → группа A (Smart RSI)
- ETHUSDT → группа B (Legacy)
- SOLUSDT → группа A (Smart RSI)
- и т.д. (детерминированно по хешу)

---

### 2. Группа A: Smart RSI Filter (AI) 🤖

**Файл:** `signal_live.py` строка 1832

**Логика:**

```python
if group == "A":  # Smart режим
    result = SMART_RSI_FILTER.evaluate(
        rsi=float(rsi_value),
        direction=signal_type,
        trend_strength=trend_strength,      # 🤖 AI учитывает
        volume_ratio=volume_ratio,          # 🤖 AI учитывает
        ai_confidence=ai_confidence,        # 🤖 AI учитывает
        btc_alignment=btc_alignment,        # 🤖 AI учитывает
    )
    return result['decision'] != 'reject'
```

**Что учитывает AI:**

- ✅ RSI значение
- ✅ Сила тренда (trend_strength)
- ✅ Объем (volume_ratio)
- ✅ AI уверенность (ai_confidence)
- ✅ BTC alignment (согласованность с BTC)

**Примеры решений:**

- RSI 68 + сильный тренд + высокий объем → **разрешить LONG** ✅
- RSI 68 + слабый тренд + низкий объем → **блокировать LONG** ❌
- RSI 32 + AI уверенность 0.15 → **блокировать SHORT** ❌

---

### 3. Группа B: Legacy (фиксированные пороги) 📊

**Файл:** `signal_live.py` строка 5792

**Логика:**

```python
if group != "A":  # Legacy режим
    if signal_type == "BUY" and rsi_value > 70:  # 📊 Фиксированный порог
        return False  # Блокируем
    if signal_type == "SELL" and rsi_value < 30:  # 📊 Фиксированный порог
        return False  # Блокируем
    return True
```

**Что учитывает Legacy:**

- ✅ RSI значение
- ❌ Сила тренда (не учитывается)
- ❌ Объем (не учитывается)
- ❌ AI уверенность (не учитывается)
- ❌ BTC alignment (не учитывается)

**Примеры решений:**

- RSI 68 → **разрешить LONG** ✅
- RSI 72 → **блокировать LONG** ❌
- RSI 32 → **блокировать SHORT** ❌
- RSI 28 → **блокировать SHORT** ❌

---

## 🚨 ЧТО ПОШЛО НЕ ТАК

### Проблема была в Legacy группе (B):

**Было (слишком строго):**

```python
if signal_type == "BUY" and rsi_value > 65:  # ❌ 48.2% блокировок!
    return False
if signal_type == "SELL" and rsi_value < 35:  # ❌ Слишком строго
    return False
```

**Исправлено:**

```python
if signal_type == "BUY" and rsi_value > 70:  # ✅ Стандартный порог
    return False
if signal_type == "SELL" and rsi_value < 30:  # ✅ Стандартный порог
    return False
```

---

## 📊 СТАТИСТИКА

### Сегодня (до исправления):

- **Группа A (Smart RSI):** ~50% символов
  - AI регулирует динамически
  - Блокировок: умеренно
- **Группа B (Legacy):** ~50% символов
  - Фиксированные пороги 65/35
  - **Блокировок: 48.2%!** ❌

### Сегодня (после исправления):

- **Группа A (Smart RSI):** ~50% символов
  - AI регулирует динамически
  - Блокировок: умеренно
- **Группа B (Legacy):** ~50% символов
  - Фиксированные пороги 70/30 ✅
  - **Блокировок: ~10-15%** (ожидается)

---

## 💡 ВЫВОД

### Да, у нас есть AI регулировка RSI! 🤖

**Но:**

1. **50% символов** используют Smart RSI Filter (AI) 🤖
   - Динамическая оценка
   - Учитывает контекст (тренд, объем, AI уверенность)
2. **50% символов** используют Legacy (фиксированные пороги) 📊
   - Простые пороги 70/30
   - Не учитывает контекст
   - **Это группа, которая блокировала 48.2%!**

### Исправление:

- Для Legacy группы (B): вернули пороги с 65/35 на 70/30
- Для Smart RSI группы (A): не требуется изменений (AI работает правильно)

### Рекомендация:

Можно рассмотреть **перевод всех символов на группу A (Smart RSI)**:

```python
# В функции get_rsi_experiment_group:
return "A"  # Все символы используют Smart RSI
```

Это даст:

- ✅ AI регулировка для всех символов
- ✅ Меньше ложных блокировок
- ✅ Лучшая адаптация к рынку

Но сейчас исправление Legacy порогов должно помочь 50% символов.

---

_Анализ на основе кода signal_live.py_
