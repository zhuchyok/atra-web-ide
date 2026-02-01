# Условия повторного включения отключённых фич (signals/database)

Документ фиксирует причины отключения и условия для включения обратно (мировые практики: явные критерии приёмки, не «просто включить»).

---

## 1. Correlation Risk (GROUP_LIMIT_EXCEEDED)

**Где:** `src/database/signal_live.py` — блок «ПРОВЕРКА КОРРЕЛЯЦИОННЫХ РИСКОВ» в `send_signal`.

**Сейчас:** `USE_CORRELATION_RISK = False` — проверка отключена.

**Причина отключения:** Ошибка/лимит `GROUP_LIMIT_EXCEEDED` при вызове `correlation_manager.check_correlation_risk_async`.

**Включить обратно когда:**
- Ошибка GROUP_LIMIT_EXCEEDED устранена (проверить лимиты БД/API, размер групп, запросы).
- Есть тест или ручная проверка: отправка сигнала с включённым Correlation Risk не падает и блокирует только при реальном превышении риска.

**Действие:** Установить `USE_CORRELATION_RISK = True` в указанном блоке после выполнения условий выше.

---

## 2. ML фильтр (prob=0.01%)

**Где:**
- `src/database/signal_live.py` — `check_ml_filter`, флаг `USE_ML_FILTER = False`.
- `src/signals/signal_live.py` — тот же контекст, флаг `USE_ML_FILTER = True` (включён для объяснимости).

**Причина отключения в database:** Проблемы с частыми предсказаниями `prob=0.01%` (модель/фичи/пороги).

**Включить обратно в database когда:**
- Диагностика prob=0.01% завершена: исправлены фичи, пороги или модель; есть проверка, что доля экстремально низких prob в норме.
- Пороги берутся из AIFilterOptimizer (уже подключено в коде после исправления TODO).

**Действие:** В `src/database/signal_live.py` в `check_ml_filter` установить `USE_ML_FILTER = True` после выполнения условий.

---

## Ссылки

- Correlation Manager: поиск по `check_correlation_risk_async`, `GROUP_LIMIT`.
- ML пороги: `src/ai/filter_optimizer.py` — `optimize_ml_filter_thresholds`.
- Логи: `[ML ZERO PROB]`, `[ML_THRESHOLDS]`, `correlation_block`.
