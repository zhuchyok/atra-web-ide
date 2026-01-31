## Agent Gym: оффлайн симуляции

### Назначение
- Анализировать работу агентов в безопасной песочнице.
- Повторно проигрывать сценарии (генерация сигналов, исполнение ордеров, защита позиций).
- Сравнивать метрики до/после обновлений, выявлять регрессии.

### Структура
- `agent_gym/scenarios.py` — определение сценариев (signal_throughput, execution_fallback, protection_health).
- `agent_gym/configs/sample_scenarios.json` — пример набора сценариев.
- `scripts/run_agent_gym.py` — запуск симуляций, запись отчёта в `agent_gym/reports/*.json`.

### Быстрый старт
```bash
python3 scripts/run_agent_gym.py --scenarios agent_gym/configs/sample_scenarios.json --print
```

Выход:
- JSON-отчёт с результатами по каждому сценарию.
- Логи в stdout с краткой статистикой.

### Расширение
- Добавляйте новые сценарии в JSON (указывайте `name`, `type`, `hours` или другие параметры).
- Для кастомного анализа создавайте новые классы в `scenarios.py`.

### Использование
- Интегрировать запуск в nightly cron/CI перед выкатом изменений.
- Сравнивать отчёты до/после изменений подсказок, инструментов, автофиксов.

### Nightly автоматизация
- `scripts/run_agent_gym_nightly.py` — запускает сценарии, сравнивает результат с baseline и формирует:
  - `agent_gym/reports/latest.json` — свежий отчёт.
  - `agent_gym/reports/nightly_diff.json` — сравнение с baseline, список регрессий/улучшений.
  - `metrics/agent_gym_regressions.prom` — Prometheus-метрики (`agent_gym_regressions_total`, `agent_gym_improvements_total`).
- `scripts/run_nightly_agent_gym.sh` — оболочка для cron, пишет статус в `logs/agent_gym_nightly.log`.
- `infrastructure/cron/nightly_agent_gym.cron` — пример записи: `30 1 * * * cd /root/atra && /bin/bash scripts/run_nightly_agent_gym.sh`.
- Для обновления baseline после одобренных изменений запустите:
  ```bash
  python3 scripts/run_agent_gym_nightly.py --update-baseline --print-summary
  ```

### Интерпретация diff
- `regressions` — метрики, которые упали ниже допустимого порога (по относительному и абсолютному изменению).
- `improvements` — показатели с ощутимым ростом.
- `missing_in_baseline` / `missing_in_new` — новые или удалённые сценарии.
- При необходимости включайте флаг `--fail-on-regression` (CI) для жёсткого стопа при ухудшении.

