## 1. Исходная ситуация
- **Описание стратегии**: Интрадей, фьючерсы Bitget (по умолчанию), 2 TP (частичный выход 50/50), защитный SL, трейлинг и перенос в безубыток после прогресса к TP1. Авто-режим способен автоматически открыть позицию, записать в БД и выставить TP1/TP2/SL как план-ордера.
- **Используемые данные и параметры**:
  - `auto_execution.py`: выставление лимит/маркет на вход, затем SL/TP план-ордера (50/50).
  - `exchange_adapter.py`: Bitget plan orders `pos_profit`/`pos_loss`, fallback — reduceOnly лимит.
  - `signal_live.py` + `trailing_stop_manager.py`: инициализация трейлинга и подтягивания к TP1.
  - БД: `accepted_signals`, `active_positions`, `signals_log`, `order_audit_log`.
- **Ограничения**: лимиты API Bitget, необходимость `hedged`/`posSide`, точная нормализация символов, комиссии/проскальзывание, sqlite локальная БД.
- **Целевые показатели**: корректная и быстрая постановка TP/SL, надёжная фиксация событий (audit_log), консистентность с `signals_log`, минимизация незакрытых/незащищённых позиций.

## 2. Выявленные слабые и узкие места
- **SL как create_order со `stopLossPrice`**: мог не работать стабильно через ccxt. Исправлено: унификация на `pos_loss` план-ордер.
- **Trailing к TP1**: в `signal_live.py` не передавался `tp1_price` в `setup_position`, из-за чего TP1-трейлинг мог не активироваться. Исправлено.
- **Скрипт для уже открытых позиций**: отсутствовало логирование в `order_audit_log`. Добавлено.

## 3. Анализ прибыльности
Текущий этап — инфраструктурный (качество исполнения). На метрики (Sharpe/Sortino/DD) влияет косвенно через снижение технических потерь. Рекомендация — прогнать 30-дневные и 90-дневные бэктесты после стабилизации исполнения и сравнить Net PnL с учётом комиссий.

| Метрика        | Значение   | Комментарий                                   |
| ----- | ---- | --- |
| Sharpe Ratio   | N/A        | Требуется повторный бэктест после фиксов      |
| Sortino Ratio  | N/A        | Аналогично                                    |
| Max Drawdown   | N/A        | Аналогично                                    |
| Средняя прибыль| N/A        | Аналогично                                    |

## 4. Точки роста и задачи для улучшения
1. [x] Унифицировать SL через `pos_loss` (Bitget) — цель: корректный SL; критерий: мок-тест проходит.
2. [x] Передать `tp1_price` в трейлинг — цель: активный TP1-трейлинг; критерий: логика активируется.
3. [x] Логировать TP/SL добавленные к открытым позициям — цель: прозрачность; критерий: записи в `order_audit_log`.
4. [ ] Расширить мониторинг исполнения (latency/ошибки план-ордеров) — метрики: доля ошибок < 1%.
5. [ ] Авто-перепостановка plan-ордеров при отмене/ошибке — устойчивость.

## 5. План работы/итераций
- Итерация 1 (выполнено): правки `exchange_adapter.py` (SL → `pos_loss`), `signal_live.py` (TP1 в трейлинг), логирование в `scripts/fix_open_positions_tp_sl.py`.
- Итерация 2: наблюдение в прод (24-72ч), сбор статистики по отказам API и таймингам.
- Итерация 3: бэктест 30/90 дней (Net, комиссии), сравнение до/после.

## 6. Приложения
- Ключевые места кода

```3868:3876:/Users/zhuchyok/Documents/GITHUB/atra/atra/signal_live.py
            if TRAILING_STOP_AVAILABLE and trailing_manager:
                trailing_manager.setup_position(
                    symbol=symbol,
                    entry_price=signal_price,
                    initial_sl=sl_price,
                    side=signal_type,
                    tp1_price=tp1_price
                )
```

```402:437:/Users/zhuchyok/Documents/GITHUB/atra/atra/exchange_adapter.py
            if self.exchange_name == "bitget" and self.trade_mode == "futures":
                # Используем единый механизм план-ордеров (pos_loss), аналогично TP (pos_profit)
                plan_client_oid = self._generate_client_oid("sl", symbol, pos_side)
                plan_order = await self.create_plan_order(
                    symbol=symbol,
                    side=sl_side,
                    size=position_amount,
                    trigger_price=stop_price,
                    plan_type="pos_loss",
                    trigger_type="market_price",
                    pos_side=pos_side,
                    reduce_only=reduce_only,
                    client_oid=plan_client_oid,
                )
```

```108:119:/Users/zhuchyok/Documents/GITHUB/atra/atra/scripts/fix_open_positions_tp_sl.py
            tp1_order = await adapter.place_take_profit_order(...)
            ...
            await audit.log_order(int(user_id), symbol, tp1_side, "plan_tp1", ...)
            ...
            tp2_order = await adapter.place_take_profit_order(...)
            ...
            await audit.log_order(int(user_id), symbol, tp2_side, "plan_tp2", ...)
```

--- 

Проверено: фиксация в `order_audit_log`, обновления `signals_log`/`active_positions` из `auto_execution.py` — в порядке. Для интеграции добавлен тест с моками ccxt, подтверждающий `pos_profit`/`pos_loss` для Bitget.


