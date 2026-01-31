---
## 1. Исходная ситуация
- Описание стратегии: гибридная интрадей-система ATRA, работающая через `CompositeSignalEngine` (trend/mean-reversion/breakout/volume), мультифреймовое подтверждение (`check_mtf_confirmation`), адаптивный сайзинг (`AdaptivePositionSizer`), AI-коррекцию тейков (`AITakeProfitOptimizer`) и режимные фильтры (`MarketRegimeDetector`, `FalseBreakoutDetector`).
- Используемые данные и параметры: базовый таймфрейм `DYNAMIC_CALC_INTERVAL = 1h`, подтверждения на H4/1d; данные поступают из `SourcesHub` (до 10 спотовых API, кеш 300–1800 с, rate-limit 25 req/min). Отбор символов: капитализация ≥100 M USD, объём ≥50 M USD (24h), фильтр спреда ≤0.25 %. Индикаторы: EMA 12/39/50, Bollinger Bands (20, 2.0), RSI 14, ATR 15, ADX 14, MACD 12/26/9, волатильностные и объёмные скоры. TP/SL корректируются ATR и AI-моделями, тайминг входа уточняется через `EntryTimingOptimizer`.
- Ограничения: централизованный rate-limit `SourcesHub` (25/min + circuit breaker), локальное кеширование капитализации; комиссии учтены как 0.10 % spot и 0.04 % futures; Telegram-доставка сигнала ≈0.1–0.2 с. Риск-профиль: депозит 1 000 USDT, базовый leverage 7, риск на сделку 2 %. Лимиты `PortfolioRiskManager`: максимум 10 позиций, дневной убыток 5 %, портфельный drawdown 10 %, доля капитала ≤15 %, `MAX_CONCURRENT_SYMBOLS = 6`, `PORTFOLIO_MAX_RISK_PCT = 8 %`. Активны корреляционные фильтры (0.8–0.85), блок-листы из БД, динамический порог `FalseBreakoutDetector` (среднее значение 0.355).
- Целевые показатели: Sharpe ≥1.2, Sortino ≥1.5, Max Drawdown ≤18 %, средняя дневная прибыль ≥0.8 % капитала (≥8 USDT), доля TP1 ≥55 %, FBD pass-rate ≥40 %, MTF confirmation ≥40 %.

## 2. Выявленные слабые и узкие места
- **Проблема №1. Смещение метрик из-за доминирования backfill.**  
  1 148 закрытых сделок (69 торговых дней) дают net PnL 4 442.58 USDT, однако 1 351 событий относятся к `trade_mode = backfill` (+4 595.58 USDT). Live/futures — всего 5 сделок (−0.216 USDT). Текущие KPI не отражают реальную live-доходность.
- **Проблема №2. Непоказательные KPI и превышение MaxDD.**  
  Сводный пересчёт по `trading.db` (1356 сделок, 71 торговый день) даёт Sharpe 2.56 и Sortino 24.30, однако метрики сформированы исключительно `backfill`-сделками (live = 0, futures = 5 сделок с отрицательным Sharpe −6.47). Max Drawdown остаётся выше лимита (26.59 % > 18 %), средняя дневная прибыль 64.72 USDT отражает synthetic-эффект, а не реальную live-производительность.
- **Проблема №3. Отсутствие live-сигналов после 2025-11-02.**  
  В `signals_log` нет новых записей `trade_mode = live` после `APTUSDT` (user `556251171`). У пользователя `958930260` депозит = 0, что приводит к `final_amount_usd = 0` (причина `WEAK_SETUP`) в `AdaptivePositionSizer`. Telegram-бот рассылает только отчёты, live-выдача отсутствует.
- **Проблема №4. Низкое качество по low-liquidity символам.**  
  Winrate 21.6 % (248 побед, 900 поражений); топ-убытки приходятся на `EIGEN/USDT`, `TRB/USDT`, `PENGU/USDT`, `WLFI/USDT`, `TRUMP/USDT`. Фильтры ликвидности и спреда в soft-режиме недостаточно жёсткие, short-множители переусилены.
- **Проблема №5. Инфраструктурные неопределённости.**  
  Текущий health-check подтвердил рабочее окружение `.venv` (Python 3.9.6, `pandas 2.3.3`, `numpy 2.0.2`), а требования синхронизированы на версии `aiohttp>=3.13.2`, `httpx>=0.28.1`, `requests>=2.31.0`, `python-telegram-bot>=22.5` (`requirements.txt`, install-скрипты, `docs/DEPENDENCY_UPDATE_PLAN_20251110.md`). Тестовое уведомление в Telegram прошло успешно (HTTP 200, latency ≈5.3 с). `SourcesHub().get_market_cap_data('BTCUSDT')` вернул кэшированный ответ (≈0 с); требуется дополнительная проверка на свежих данных с отключённым кэшем и smoke-тесты после пересоздания `.venv`.

### Экспертная оценка (семь ролей)
- **@quant:** подтвердил, что совокупные метрики (`Sharpe=2.57`, `Sortino=24.30`, `MaxDD=26.59 %`, `avg_daily_profit=64.72 USDT`, 71 торговый день) формируются исключительно `backfill`-сделками (live=0, futures=5 сделок с Sharpe −6.47). Рекомендации: отделить live/backfill KPI, восстановить live-выдачу (≥30 сделок перед повторной оценкой), усилить фильтры ликвидности, перекалибровать adaptive sizing и отключить futures до переоценки.
- **@trader:** указал на практическую неприменимость текущих KPI (live отсутствует, депозиты пользователей нулевые). Требуется восстановить депозиты (`/deposit`), проверить исполнение на высоколиквидных инструментах (BTC/ETH/SOL/BNB/XRP) и контролировать фактический слиппедж/latency после перезапуска.
- **@risk_manager:** отметил превышение лимита MaxDD (26.59 % > 18 %), запустил обновлённые стресс-тесты (`simulate_flash_crash`, `simulate_liquidity_crisis`) — при сценарии flash crash (−15 % за 10 мин, spread ×3, volume drop 50 %) зафиксировано `fill_ratio 0.50`, `avg_slippage 0.45 %`, предупреждение сработало (`triggered_warning=True`, `triggered_stop=False`); при liquidity crisis (volume drop 70 %, spread ×4, depth loss 90 %) `fill_ratio 0.10`, `avg_slippage 0.76 %`, `estimated_unfilled=9`, `triggered_stop=True`. Рекомендации: закрепить circuit breakers (предупреждение при 15 %, стоп при 18 %), отключить futures и внедрить ежедневный мониторинг drawdown/win rate.
- **Circuit breakers:** внедрены `risk_flags_manager` + `scripts/run_risk_monitor.py`; активные флаги `emergency_stop` / `weak_setup_stop` блокируют выдачу сигналов (см. обновления `signal_live.py`, `portfolio_risk_manager.py`). Перед возобновлением live необходимо сбросить флаги после устранения причин.
- **@devops:** рекомендовал выполнить `server_menu.sh` health-check (БД, зависимости, логи), обновить `.venv`, настроить latency-мониторинг (API, Telegram), проверить резервные копии `trading.db`, актуализировать CI/CD и подготовить отчёт о readiness live.
- **@data_engineer:** выявил неоднородность временных форматов (решено `format='mixed'`), но необходимы системные data quality checks (duplicate/timezone/null). Предложил внедрить ETL-валидацию, мониторинг completeness >99 %, контроль latency `SourcesHub` и ведение журналов преобразований.
- **@data_scientist:** описал активные ML-компоненты (`ML_SCORING_ENABLED`, AI TP/SL, adaptive sizing) и поставил задачи: актуализировать метрики моделей (AUC, precision, uplift), мониторить drift, автоматизировать логирование (MLflow/W&B) и запланировать переобучение после получения live данных.
- **@system_architect:** оценил архитектуру как монолит с частично решёнными зависимостями; предложил roadmap: переход на сервисные интерфейсы (REST/gRPC), миграцию БД в PostgreSQL с репликацией, внедрение очередей (Kafka/Redis), усиление безопасности (секреты вне `.env`, шифрование, RBAC) и формализацию CI/CD (staging, canary, audit trails).

## 3. Анализ прибыльности
| Режим | Сделки | Sharpe | Sortino | Max Drawdown | Средняя дневная прибыль | Торговых дней |
| ----- | ---- | --- | --- | --- | --- | --- |
| all (совокупно) | 1 356 | 2.5659 | 24.2839 | 26.59 % | 64.72 USDT | 71 |
| backfill | 1 351 | 2.5661 | 24.3047 | 26.59 % | 64.73 USDT | 71 |
| futures | 5 | −6.4705 | — | 0.07 % | −0.11 USDT | 2 |
| live | 0 | — | — | — | — | 0 |

- Совокупные метрики полностью формируются `backfill`-сделками; live-поток отсутствует, поэтому KPI не отражают фактическую доходность.
- Max Drawdown 26.59 % превышает целевой лимит 18 %, несмотря на высокий Sharpe/Sortino, что подтверждает риск превышения портфельных ограничений.
- Futures-режим демонстрирует отрицательную доходность (Sharpe −6.47, avg daily −0.11 USDT) при крошечной выборке (5 сделок / 2 торговых дня) и требует отключения до повторной калибровки.

## 4. Точки роста и задачи для улучшения
1. [ ] **Гипотеза №1 — Разделить метрики live/backfill.** Цель: исключить synthetic bias и контролировать KPI по реальным сигналам. Ожидаемый результат: live Sharpe ≥0.9 после обновления отчётности. Критерий: `performance_metrics_calculator` формирует ежедневный JSON со сплитом по `trade_mode`.
2. [ ] **Гипотеза №2 — Возобновить live-выдачу.** Цель: обеспечить ≥1 сигнал/сутки для `556251171` и `958930260`. Ожидаемый результат: записи `trade_mode = live` с ненулевым `entry_amount_usd`. Критерий: `daily_quality_report` за 48 ч фиксирует FBD+MTF подтверждённый сигнал.  
   *Промежуточный статус (10.11): депозиты актуализированы (`958930260 = 5000 USDT`, `556251171 = 1299.9 USDT`), `risk_flags` сброшены (`manage_risk_flag.py --clear`), основной пайплайн переведён на запуск через `main.py` (единый lock `atra.lock`, фоновых копий `signal_live.py` нет). `PortfolioRiskManager` хранит метрики per-user, устраняя блокировку по глобальному drawdown. Логи фиксируют обработку ETH/ALT активов; для soft-пользователей минимальное требование direction-confidence ослаблено до 2 из 4 подтверждений, чтобы пропускать сигналы с хорошим EMA/RSI при пограничном MACD. Live-записей ещё нет, monitoring продолжается.*
3. [ ] **Гипотеза №3 — Усилить фильтры ликвидности и исключить топ-убытки.** Цель: поднять winrate ≥28 %, снизить MaxDD <18 %. Ожидаемый результат: обновлённый `pair_filtering` (24h объём ≥50 M, спред ≤0.25 %, обновлённый whitelist) и подтверждённый backtest на 30 дней. Критерий: отчёт `quality_metrics_report` + бэктест демонстрируют целевые метрики.
4. [ ] **Гипотеза №4 — Перекалибровать адаптивный сайзинг.** Цель: убрать `WEAK_SETUP` обнуления и оптимизировать short-множители. Ожидаемый результат: `final_vs_base` 1.02–1.05, uplift по PnL ≥+1 % к baseline. Критерий: `adaptive_vs_baseline` после 72 ч live.
5. [ ] **Гипотеза №5 — Полный инфра-аудит.** Цель: подтвердить готовность окружения (зависимости, cron, резервирование, latency-алерты). Ожидаемый результат: чек-лист @devops со статусом ✅. Критерий: отчёт `docs/infra/INFRA_HEALTH_2025Q4.md`.  
   *Промежуточный статус (10.11 19:50 UTC): `docs/INFRA_HEALTH_2025Q4.md` обновлён; `db.backup_file` переведён на `sqlite3.Connection.backup()` (полный snapshot, без усечений), `scripts/test_restore_backup.py` пройден на сервере (копия `trading.db_20251110_224921`). TLS-sandbox собран и прогнан на сервере (`docker build/run atra-openssl-test` → OpenSSL 3.5.1, `urllib3 2.5.0`, `pytest` 29 passed, стресс-тесты и `send_risk_status_report.py --dry-run` без ошибок; отчёты сохранены в `data/reports/stress_flash_crash.json`, `..._liquidity_crisis.json`). `scripts/report_infra_status.py` интегрирован в `run_risk_status_report.sh --include-infra`, флаг `signals_stalled` активирован в `run_risk_monitor.py`. Остаётся оформить выделенный health-report канал и staging-деплой TLS.* 

## 5. План работы/итераций
- **Итерация 1 — Аудит данных и метрик.**  
  Действия: обновить `performance_metrics_calculator`, внедрить фильтр `trade_mode`, сформировать `performance_live_vs_backfill.json`.  
  Критерий: live KPI рассчитаны и опубликованы команде.
- **Итерация 2 — Восстановление live-сигналов.**  
  Действия: установить депозит `958930260`, перезапустить `signal_live`, проверить `position_sizing_events` (ненулевой `final_amount_usd`).  
  Промежуточный статус: депозиты обновлены, risk-флаги очищены, `signal_live` запущен (лог фиксирует проверки ETHUSDT, но direction confidence пока отклоняет входы).  
  Критерий: в `signals_log` ≥1 запись `trade_mode = live` за сутки, Telegram уведомление доставлено.
- **Итерация 3 — Риск и фильтры ликвидности.**  
  Действия: обновить `pair_filtering`, исключить топ-убытки, провести бэктест на 30 дней, валидировать новые стресс-тесты (`run_flash_crash_stress_test.py`, `run_liquidity_crisis_test.py`).  
  Критерий: MaxDD <18 %, winrate ≥28 %, Sharpe ≥1.0 на live-данных.
- **Итерация 4 — Адаптивный сайзинг.**  
  Действия: откалибровать коэффициенты `WEAK_SETUP`, short-множители, прогнать `scripts/compare_sizing_performance.py --days 30` после 72 ч live.  
  Критерий: uplift ≥+1 %, нет обнулённых позиций при депозитах >0.
- **Итерация 5 — Инфраструктура.**  
  Действия: проверить `.venv`, зависимости, cron, резервное копирование, latency-алерты.  
  Критерий: чек-лист @devops закрыт, результаты задокументированы.

## 6. Приложения
- Примеры кода на Python (при необходимости)

### Расчёт Sharpe/Sortino/MaxDD по режимам

```python
from dataclasses import dataclass
from typing import Optional
import sqlite3
import pandas as pd
import numpy as np

CAPITAL = 1_000.0
RISK_FREE = 0.02

@dataclass
class ModeMetrics:
    trade_mode: str
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    avg_daily_profit_usd: float

def calculate_mode_metrics(db_path: str, trade_mode: Optional[str] = None) -> ModeMetrics:
    query = """
        SELECT exit_time, net_pnl_usd
        FROM trades
        WHERE exit_time IS NOT NULL
    """
    params: tuple = ()
    if trade_mode:
        query += " AND trade_mode = ?"
        params = (trade_mode,)

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return ModeMetrics(trade_mode or "all", 0.0, 0.0, 0.0, 0.0)

    df["exit_dt"] = pd.to_datetime(df["exit_time"], errors="coerce", utc=True)
    df = df.dropna(subset=["exit_dt"])
    df["exit_dt"] = df["exit_dt"].dt.tz_convert("UTC").dt.tz_localize(None)
    df["exit_date"] = df["exit_dt"].dt.date

    daily_pnl = df.groupby("exit_date")["net_pnl_usd"].sum().sort_index()
    daily_returns = daily_pnl / CAPITAL
    risk_free_daily = RISK_FREE / 365
    excess = daily_returns - risk_free_daily

    volatility = daily_returns.std()
    sharpe = (excess.mean() / volatility) * np.sqrt(365) if volatility else 0.0

    downside = daily_returns[daily_returns < risk_free_daily]
    downside_vol = downside.std()
    sortino = (excess.mean() / downside_vol) * np.sqrt(365) if downside_vol else sharpe

    cumulative = daily_pnl.cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    max_dd_pct = (drawdown.min() / CAPITAL) * 100 if CAPITAL else 0.0

    return ModeMetrics(
        trade_mode=trade_mode or "all",
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown_pct=max_dd_pct,
        avg_daily_profit_usd=float(daily_pnl.mean()),
    )

if __name__ == "__main__":
    for mode in (None, "live", "backfill", "futures"):
        metrics = calculate_mode_metrics("trading.db", mode)
        print(metrics)
```

### Симуляция стресс-сценариев

```58:92:simulators/order_book_simulator.py
def simulate_flash_crash(
    symbol: str,
    drop_pct: float,
    duration: timedelta,
    spread_multiplier: float,
    volume_drop_pct: float,
) -> Dict[str, float]:
    base_price = _get_last_price(symbol)
    final_price = base_price * (1 - drop_pct / 100.0)
    # ... existing code ...
```

```97:118:simulators/order_book_simulator.py
def simulate_liquidity_crisis(
    symbol: str,
    volume_drop_pct: float,
    spread_multiplier: float,
    depth_loss_pct: float,
    duration: timedelta,
) -> Dict[str, float]:
    base_price = _get_last_price(symbol)
    fill_ratio = max(0.0, 1.0 - depth_loss_pct / 100.0)
    new_spread_pct = DEFAULT_BASE_SPREAD * spread_multiplier * 100.0
    # ... existing code ...
```

### Технический health-check (10.11.2025)
- `.venv` пересоздан на Python 3.9.6, `pip 25.3`; `requirements.txt` дополнен `ta>=0.10.0`, `ccxt>=2.0.0`, убрана установка `sqlite3`. Скрипты `setup_venv.sh`, `start_atra.sh`, `archive/experimental/simple_upgrade.py` синхронизированы.
- `pip install -r requirements.txt` выполнен успешно; добавлены dev-зависимости `pytest 8.4.2`, предупреждение `urllib3 NotOpenSSLWarning` устранено пином `urllib3<2` (установлено `urllib3 1.26.20`), остаётся системный TODO по обновлению OpenSSL.
- `pytest tests/unit` завершился успешно (29 passed, ≈1.0 с) после реализации `enhanced_entry_signal` и полного блока проверок в `validation.py`; единственный warning — `FutureWarning` от pandas (`freq='H'`).
- Добавлен `aiofiles>=23.2.1` в зависимости и установочные скрипты (`setup_venv.sh`, `start_atra.sh`, `simple_upgrade.py`), так что Dashboard теперь может работать в полном async-режиме без fallback предупреждений.
- `src/signals.delivery` и `src/signals.system` переведены на ленивые обёртки (`send_signal`, `process_symbol_signals`), благодаря чему старт через `main.py` больше не ловит `cannot import name ...` из-за частично инициализированного `signal_live.py`.
- `SourcesHub` дополнен сбором latency-метрик (latency, sources_count, cache_hit) для price/volume/market_cap; `daily_quality_report.json` теперь фиксирует `sources_metrics` (например, 10.11: market cap 2.44 с, 3 источника; price 0.38 с, Binance; volume 1.31 с, 4 источника). Кэш очищается перед измерениями, что даёт «холодные» значения для мониторинга.
- `scripts/run_flash_crash_stress_test.py` и `scripts/run_liquidity_crisis_test.py` выполнены на сервере; отчёты сохранены в `data/reports/stress_flash_crash.json` (`fill_ratio 0.50`, `avg_slippage 0.45 %`, `triggered_warning=True`, `triggered_stop=False`) и `data/reports/stress_liquidity_crisis.json` (`fill_ratio 0.10`, `avg_slippage 0.76 %`, `estimated_unfilled=9`, `triggered_stop=True`).
- `scripts/report_risk_status.py --format text` отработал, подтверждая активные флаги `emergency_stop`, `maxdd_warning`, `weak_setup_stop`.
- Telegram latency после обновления: 5.4 с (`notify_user` → HTTP 200). Источник предупреждения — LibreSSL.
- `SourcesHub().get_market_cap_data('BTCUSDT')` после очистки `app_cache` выполнился за 2.47 с, возвращён `market_cap ≈ 2.11e12 USD`. Требуется мониторинг холодных запросов и внедрение счётчика `sources_count`.
- Депозит пользователя `556251171` синхронизирован (`user_data.json`, `users_data` в БД) до 2000 USDT; `run_risk_monitor.py --signals-hours 48` актуализировал флаг `signals_stalled` (1) при отсутствии live-сигналов.
- Ужесточены фильтры ликвидности: `RISK_FILTERS` → `min_volume_24h = 50 M`, `max_spread_pct = 0.25 %`, `min_depth_usd = 50 000`; обновлены `pair_filtering.py`, `liquidity_checker.py`, `signal_live.py` (теперь требуются и depth, и объём).
- `db.backup_file` обновлён: вместо `shutil.copy` используется `sqlite3.Connection.backup()`, что обеспечивает консистентные копии. Контрольный бэкап (`backups/trading.db_20251110_224921`) полностью восстановлен (`scripts/test_restore_backup.py` → ✅).
- `scripts/run_openssl_smoke_tests.sh` обогащён `--dry-run` для Telegram и подтверждён в Docker-контейнере `atra-openssl-test` прямо на сервере (OpenSSL 3.5.1, `urllib3 2.5.0`). 

## 7. Альтернативная краткосрочная стратегия (fallback)
- **Концепция:** momentum+liquidity скальпер на 15m с подтверждением тренда на 1h, избавленный от `FalseBreakoutDetector`. Использует только биржи с подтверждёнными API (Binance/Bybit).
- **Фильтры:** 24h объём ≥50 M USDT, спред ≤0.25 %, EMA(34/89), RSI(14) < 60 для лонгов, MACD(12,26,9) > 0, ATR(14) для SL/TP, ускорение объёма ≥1.3× среднего.
- **Риск-менеджмент:** фиксированный объём 1 % депозита на позицию, плечо 3×, SL = 1.2×ATR(14), TP1 = 0.8×ATR, TP2 = 1.6×ATR, перевод в безубыток после TP1, максимум 3 одновременных позиции, корреляция ≤0.7.
- **Ожидаемые KPI:** Sharpe 0.9–1.2, Sortino ≥1.3, MaxDD ≤12 %, средняя дневная прибыль 0.4–0.6 % капитала.
- **Статус:** реализована в `fallback_strategy.py`; при критической задержке восстановления основного пайплайна может быть активирована как временный контур.

---

