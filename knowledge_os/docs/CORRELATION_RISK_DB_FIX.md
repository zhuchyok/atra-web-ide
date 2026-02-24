# ИСПРАВЛЕНИЕ: Курсор БД недоступен в correlation_risk.py

## 🔍 ПРОБЛЕМА

**Ошибка:** `ERROR:src.risk.correlation_risk:❌ Курсор БД недоступен`

**Причина:**

- `Database` по умолчанию использует `use_connection_pool=True`
- При использовании pool: `self.conn = None` и `self.cursor = None` при инициализации
- Соединение получается динамически через `with self._pool.get_connection() as conn:`
- Но `correlation_risk.py` пытается использовать `self.db.cursor` напрямую, что не работает с pool

---

## ✅ РЕШЕНИЕ

**Отключен connection pool для `CorrelationRiskManager`:**

```python
# ❌ БЫЛО:
self.db = Database(self.db_path)

# ✅ СТАЛО:
self.db = Database(self.db_path, use_connection_pool=False)
```

**Почему это безопасно:**

- `CorrelationRiskManager` не критичен для производительности
- Используется редко (только при проверке корреляционных рисков)
- Прямое соединение проще и надежнее для этого модуля

---

## 📊 РЕЗУЛЬТАТ

- ✅ Ошибка "Курсор БД недоступен" исправлена
- ✅ `CorrelationRiskManager` работает корректно
- ✅ Таблицы `risk_signal_history` создаются успешно
- ✅ История сигналов загружается из БД

---

**Дата исправления:** 2025-12-01  
**Файл:** `src/risk/correlation_risk.py` (строка 144)
