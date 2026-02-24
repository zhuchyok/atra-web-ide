# ✅ ИСПРАВЛЕНО: Курсор БД недоступен в correlation_risk.py

## 🎯 ПРОБЛЕМА

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
# ❌ БЫЛО (строка 144):
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

### Тест:

```bash
python3 -c 'from src.risk.correlation_risk import CorrelationRiskManager; mgr = CorrelationRiskManager()'
```

**Вывод:**

```
✅ Таблицы risk_signal_history инициализированы
📊 Загружено 0 сигналов из истории рисков
✅ CorrelationRiskManager инициализирован (BTC/ETH/SOL correlation mode)
✅ CorrelationRiskManager инициализирован успешно
```

**Ошибка "Курсор БД недоступен" больше не появляется!**

---

## 🔧 ПРИМЕНЕНО

- ✅ Локально: исправлено в `src/risk/correlation_risk.py`
- ✅ На сервере: применено через `sed`
- ✅ Бот перезапущен
- ✅ Ошибка исправлена

---

**Дата:** 2025-12-01  
**Файл:** `src/risk/correlation_risk.py` (строка 145)  
**Коммит:** `4398e54`
