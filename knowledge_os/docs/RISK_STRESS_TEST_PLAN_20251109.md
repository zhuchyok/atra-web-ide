---
## 1. Цель документа
Разработать технический план стресс-тестов и внедрения circuit breakers для восстановления контроля рисков после превышения Max Drawdown (26.59 % > лимита 18 %) и отсутствия live-сигналов.

## 2. Текущие наблюдения
- MaxDD (совокупно) = 26.59 % при базовом капитале 1 000 USDT (по отчёту `scripts/export_performance_metrics.py`).
- Futures-поток отключён из-за отрицательных метрик (Sharpe −6.47 на 5 сделках).
- Live-сигналы отсутствуют; adaptive sizing возвращает `final_amount_usd = 0` (см. `docs/LIVE_RECOVERY_STATUS_20251109.md`).
- Действующие лимиты: `PORTFOLIO_MAX_RISK_PCT = 8 %`, дневной убыток 5 %, MaxDD-целевой 18 %.

## 3. Стресс-сценарии
### 3.1 Flash Crash
- **Описание:** цена базового актива (BTCUSDT или выбранного символа) падает на 15 % за 10 минут, ликвидность снижается на 50 %, спред расширяется в 3 раза.
- **Данные:** использовать исторические свечи (e.g. 2020-03-12, 2021-05-19) + synthetic симуляции.
- **Метрики:** влияние на MaxDD, SL/TP, время исполнения, отклонение от планового риска.
- **Скрипт:** создать `scripts/run_flash_crash_stress_test.py` (см. раздел 7) с параметрами: `--symbol`, `--drop-pct`, `--duration`, `--spread-mult`.

### 3.2 Liquidity Crisis
- **Описание:** объём падает на 70 %, order book depth сужается (e.g. 90 % заявок исчезают), спред увеличивается в 4 раза; исполнение DCA блокируется.
- **Метрики:** slippage, время исполнения, доля неисполненных сигналов, отклонение портфельного риска.
- **Скрипт:** `scripts/run_liquidity_crisis_test.py`, использовать исторические данные и мок-API (`SourcesHub`).

### 3.3 Correlated Sell-off
- **Описание:** падение всего набора (до 6 символов) на 12 % синхронно; проверка корреляционных фильтров.
- **Метрики:** эффект на `MAX_CONCURRENT_SYMBOLS`, портфельный drawdown, срабатывание повторных сигналов.

## 4. Circuit Breakers
### 4.1 Пороговые значения
- Предварительный порог: MaxDD ≥ 15 % → предупреждение (уведомление risk_manager, остановка новых сигналов на 1 час).
- Жёсткий порог: MaxDD ≥ 18 % → остановка генерации сигналов до ручного разрешения (флаг в БД).
- Дневной убыток ≥ 5 % → остановка сигналов до следующего UTC-дня.
- Количество обнулённых `final_amount_usd` ≥ 10 подряд → stop (проблема с депозитами/данными).

### 4.2 Техническая реализация
- Добавить таблицу `risk_flags` (fields: `flag`, `value`, `updated_at`, `reason`).
- В `signal_live` и `PortfolioRiskManager` внедрить проверку: если `risk_flags.emergency_stop = true`, сигналы не отправляются.
- Использовать `risk_flags_manager.py` и `scripts/manage_risk_flag.py` для ручного управления флагами.
- CRON (`scripts/run_risk_monitor.py`) рассчитывает MaxDD/дневной PnL и обновляет флаги. Интеграция с `scripts/export_performance_metrics.py`.
- Telegram-уведомления: отдельный канал /alert для risk_manager/devops.
- Пример cron (daily 04:15 UTC):  
  `15 4 * * * cd /Users/zhuchyok/Documents/GITHUB/atra/atra && /usr/bin/python3 scripts/run_risk_monitor.py >> logs/risk_monitor.log 2>&1`
- Оперативный отчёт `scripts/report_risk_status.py` – сводка risk_flags, MaxDD, дневного PnL и live-статуса пользователей.
- Автоматическая рассылка: `scripts/run_risk_status_report.sh` выполняет цикл (monitor + лог + Telegram) и может быть подключён к cron.
- Комбинированный отчёт `scripts/report_combined_status.py` объединяет quality (`daily_quality_report`) и risk-информацию для единой сводки.

## 5. Тестовая матрица
| Сценарий | Ожидаемое действие | Метрики контроля | Pass/Fail |
| --- | --- | --- | --- |
| Flash Crash (−15 %/10 мин) | Circuit breaker предупреждение при 15 %, стоп при 18 % | MaxDD, SL, время реакции |  |
| Liquidity Crisis | Stop инициируется после N неисполненных сигналов | slippage, final_amount_usd, latency |  |
| Correlated Sell-off | Корреляционный фильтр ограничивает новые позиции | MAX_CONCURRENT_SYMBOLS, risk pct |  |
| Zero deposit (WEAK_SETUP) | Stop при ≥10 событий подряд | final_amount_usd, adaptive_reason |  |

## 6. Roadmap внедрения
1. **Неделя 1:**  
   - Реализовать `scripts/export_performance_metrics.py` (готово).  
   - Создать `risk_flags` и обновить `PortfolioRiskManager`.  
   - Добавить Telegram-алерты (предупреждение/стоп).
2. **Неделя 2:**  
   - Разработать скрипты flash crash и liquidity crisis (см. раздел 7).  
   - Провести симуляции на исторических данных; задокументировать результаты.
3. **Неделя 3:**  
   - Внедрить автоматический стоп при нулевом депозите (≥10 WEAK_SETUP).  
   - Создать дашборд risk-monitoring (например, Grafana/Notebook).
4. **Неделя 4:**  
   - Выполнить полноценный регрессионный тест (all scenarios).  
   - Обновить документацию (`docs/RISK_MANAGEMENT_PLAYBOOK.md`) и согласовать с risk_manager.

## 7. Псевдокод для стресс-теста (пример)
```python
# scripts/run_flash_crash_stress_test.py
import argparse
from datetime import datetime, timedelta
# TODO: подключить реальный симулятор (см. scripts/run_flash_crash_stress_test.py)
```

## 8. Необходимые ресурсы
- Исторические данные с высокой частотой (1m/5m).
- Функция симуляции ордербука (можно использовать mock API в `SourcesHub`).
- Доступ risk_manager/devops к отчётам (`data/reports` + Telegram).

## 9. Ответственные
- Risk owner: **@risk_manager**.
- Техническая реализация: **@quant**, **@devops**, **@data_engineer**.
- Проверка и утверждение: **@system_architect**, **@risk_manager**.

---

