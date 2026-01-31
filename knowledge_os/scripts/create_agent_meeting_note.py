#!/usr/bin/env python3
import os
import logging
from datetime import datetime

from src.shared.utils.datetime_utils import get_utc_now

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_meeting")

TEMPLATE = """# Протокол совещания 7-спец команды
Дата/время: {ts}

## 1. Контекст запроса
- ...

## 2. Вклад агентов
- signal_live: ...
- auto_execution: ...
- risk_monitor: ...
- execution_quality: ...
- data_pipeline: ...
- strategy_research: ...
- incident_response: ...

## 3. Консолидация выводов
- ...

## 4. План действий (приоритеты)
1) ...

## 5. Риски и меры снижения
- ...

## 6. Результаты выполнения
- ...
"""


def main() -> None:
    ts = get_utc_now().strftime("%Y%m%d_%H%M%S")
    docs_dir = os.path.join("docs", "AGENT_MEETINGS")
    os.makedirs(docs_dir, exist_ok=True)
    path = os.path.join(docs_dir, f"{ts}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(ts=ts))
    logger.info("✅ Создан протокол: %s", path)


if __name__ == "__main__":
    main()


