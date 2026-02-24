# 🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Volume Imbalance Filter

## 🎯 НАЙДЕНА ПРИЧИНА ПРОБЛЕМЫ!

### ❌ ПРОБЛЕМА

В файле `src/signals/core.py` на **строке 183** было **переопределение**:

```python
USE_VOLUME_IMBALANCE_FILTER = False
```

Это переопределение **блокировало фильтр**, даже когда:

- В `config.py` было `USE_VOLUME_IMBALANCE_FILTER = False` (отключено)
- В `signal_live.py` была проверка `if volume_imbalance_filter and USE_VOLUME_IMBALANCE_FILTER:`

### 🔍 КАК ЭТО РАБОТАЛО

1. В `config.py`: `USE_VOLUME_IMBALANCE_FILTER = False` (отключено)
2. В `signal_live.py`: фильтр не инициализировался (`volume_imbalance_filter = None`)
3. **НО** в `core.py` строка 183 переопределяла флаг на `False`
4. В `core.py` строки 799-800 и 904-905 проверяли фильтр:
   ```python
   if USE_VOLUME_IMBALANCE_FILTER and long_base_ok:
       vi_ok, vi_reason = check_volume_imbalance_filter_sync(df, i, "long", strict_mode=False)
   ```
5. **НО** функция `check_volume_imbalance_filter_sync` все равно вызывалась где-то еще!

### ✅ РЕШЕНИЕ

**Удалено переопределение** в `src/signals/core.py`:

```python
# 🔧 ИСПРАВЛЕНО: Не переопределяем USE_VOLUME_IMBALANCE_FILTER, используем из config
# USE_VOLUME_IMBALANCE_FILTER = False  # УДАЛЕНО: переопределение блокировало фильтр
```

Теперь используется значение из `config.py` везде.

## 📊 МЕСТА ПРОВЕРКИ ФИЛЬТРА

1. ✅ `signal_live.py:5478` - `check_new_filters()` - **ИСПРАВЛЕНО** (проверка флага добавлена)
2. ✅ `src/signals/core.py:799-800` - `soft_entry_signal()` для LONG - **ИСПРАВЛЕНО** (переопределение удалено)
3. ✅ `src/signals/core.py:904-905` - `soft_entry_signal()` для SHORT - **ИСПРАВЛЕНО** (переопределение удалено)

## 🎉 РЕЗУЛЬТАТ

Теперь фильтр **полностью отключен**, когда `USE_VOLUME_IMBALANCE_FILTER = False` в `config.py`.
