# Холодный запуск моделей: ориентиры из интернета (Ollama, MLX)

**Назначение:** сводка найденных в открытом доступе данных по времени развёртывания (холодная загрузка в RAM) и первому ответу. Точных таблиц «каждая модель — секунды» мало; ниже — ориентиры по размеру и конкретные примеры из бенчмарков.

---

## Runbook: при добавлении новой модели (Ollama или MLX)

**Цель:** чтобы время загрузки и обработки моделью учитывалось при выполнении задач (таймауты, очереди, мониторинг).

1. **Добавить модель:** Ollama — `ollama pull <model>`; MLX — добавить в MODEL_PATHS / OLLAMA_TO_MLX_MAP в `knowledge_os/app/mlx_api_server.py` (учесть лимиты Metal: ~75% RAM, ~27 GB на буфер, см. [MASTER_REFERENCE.md](MASTER_REFERENCE.md) §4 и [MLX_PYTHON_CRASH_CAUSE.md](MLX_PYTHON_CRASH_CAUSE.md)).
2. **Запустить замер холодного старта:**  
   - Ollama: `MEASURE_SOURCE=ollama OLLAMA_BASE_URL=http://localhost:11434 python scripts/measure_cold_start_all_models.py`  
   - MLX: `MEASURE_SOURCE=mlx MLX_BASE_URL=http://localhost:11435 python scripts/measure_cold_start_all_models.py`  
   Скрипт обновит **configs/ollama_model_timings.json** или **configs/mlx_model_timings.json** (deploy_estimate_sec, cold_total_sec, warm_response_sec, recommended_timeout_sec).
3. **Обновить библию:** при необходимости скопировать новые строки в таблицы §4 / §4.2 этого документа (для людей). Данные для кода уже в configs/*.json.
4. **Учесть таймауты:** при настройке OLLAMA_EXECUTOR_TIMEOUT, Victoria, backend и MLX (MODEL_TIME_ESTIMATES или чтение из справочника) использовать **recommended_timeout_sec** из соответствующего configs/*_model_timings.json по имени модели.

См. также [MASTER_REFERENCE.md](MASTER_REFERENCE.md) §4 «При добавлении новой модели».

---

**Своя таблица с выгрузкой модели:** `scripts/measure_cold_start_all_models.py` — перед замером модель выгружается (Ollama), таймаут 30 мин, выход: tmp/cold_start_timings.*. Без выгрузки: `scripts/measure_all_models_ollama_mlx.py` → tmp/model_timings_ollama_mlx.*.

**Связанные документы:** [MODEL_TIMING_REFERENCE.md](MODEL_TIMING_REFERENCE.md), [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md).

---

## 1. Ориентиры по размеру (холодная загрузка + первый ответ)

Собрано из: Apple ML Research (MLX, M4/M5), бенчмарки MLX vs llama.cpp, документация Ollama, обзоры «LLM load time».

| Размер модели | Холодная загрузка в RAM (ориентир) | Первый ответ / TTFT (ориентир) | Источники |
|---------------|------------------------------------|---------------------------------|-----------|
| **1–4B**      | 5–15 с                             | 2–5 с                           | Оценки по объёму весов; MLX 1.7B — TTFT ~3.5 с (Apple ML). |
| **7B**        | 2–25 с                             | 2–10 с                          | MLX: Llama-2 7B fp16 ~4 с, 4-bit ~1.7 с; 8B <10 с (бенчмарки MLX vs llama.cpp). Ollama: зависит от SSD/HDD. |
| **8–11B**     | 10–30 с                            | 3–15 с                          | Apple ML: Qwen3-8B MLX TTFT 3.6–4 с на M4/M5. |
| **13–20B**    | 15–60 с                            | 5–20 с                          | Ollama: 13 GB на HDD — «several minutes»; на SSD быстрее. |
| **30–33B**    | 30–90 с                            | 10–45 с                         | Apple ML: Qwen3-30B-A3B 4-bit TTFT ~3.5 с (M5). MLX 30B 4-bit ~20 GB RAM. |
| **70B**       | 1–3 мин                            | 30 с – 2 мин                    | Объём весов ~40 GB; загрузка с диска — минуты. |
| **104B**      | 2–5 мин                            | 1–3 мин                        | Оценки по объёму и памяти. |

- **Холодная загрузка** — загрузка весов с диска в RAM/VRAM при первом запросе.
- **TTFT (time to first token)** — время до первого токена ответа (уже после загрузки или вместе с ней в одном измерении).
- Реальные значения зависят от: SSD/HDD, объёма RAM, квантования (4-bit быстрее и меньше памяти).

---

## 2. Конкретные данные из интернета (по моделям/бенчмаркам)

| Модель / конфиг | Холодная загрузка / TTFT | Источник |
|------------------|---------------------------|----------|
| **MLX:** Llama-2 7B fp16 | ~4 с (load/TTFT) | Бенчмарк MLX vs llama.cpp (Apple Silicon). |
| **MLX:** Llama-2 7B 4-bit | ~1.7 с | Там же; 4-bit быстрее. |
| **MLX:** 8B модель | <10 с загрузка | Там же; llama.cpp ~30 с для 8B. |
| **MLX:** Qwen3-1.7B, 8B, 8B-4bit, 14B-4bit, 20B, 30B-A3B | TTFT 3.3–4.1 с (M4/M5) | Apple Machine Learning Research, «Exploring LLMs with MLX and the Neural Accelerators in the M5 GPU». |
| **Ollama:** первый запрос к модели | Задержка «cold-start»: загрузка с диска, декомпрессия, перенос в GPU | Ollama docs / Medium «Speed Up Ollama: Preload». |
| **Ollama:** 13 GB модель (gpt-oss:20b) на HDD | «Several minutes» | GitHub issue ollama/ollama (I/O contention). |
| **Ollama:** SSD | Рекомендуется; нагрузка на диск уменьшает время загрузки | Hardware guides, FAQ. |

Точных таблиц «каждая модель Ollama/MLX — N секунд холодный запуск» в открытом доступе нет; выше — то, что удаётся найти по бенчмаркам и документации.

---

## 3. Своя таблица: выгрузка модели + замер (холодный запуск и ответ)

Скрипт **`scripts/measure_cold_start_all_models.py`** строит таблицу по каждой модели на вашей машине:

- **Перед холодным замером:** модель выгружается (Ollama — через API `keep_alive=0`; MLX — выгрузка через API не поддерживается, замер идёт «как есть»).
- **Таймаут на ответ:** 30 минут по умолчанию (`MEASURE_REQUEST_TIMEOUT=1800`); для тяжёлых/vision-моделей можно увеличить.
- Для каждой модели: холодный запрос (развёртывание + ответ) → тёплый запрос (только ответ). В таблице: развёртывание (с), ответ (с), холодный итого (с).

Запуск:
```bash
OLLAMA_BASE_URL=http://localhost:11434 MLX_BASE_URL=http://localhost:11435 python scripts/measure_cold_start_all_models.py
```

Выход: **tmp/cold_start_timings.json**, **tmp/cold_start_timings.txt**, таблица в консоль (колонки: Модель, Источник, Развёртывание (с), Ответ (с), Холодный итого (с), Статус).

---

## 4. Зафиксированные замеры по нашим моделям Ollama (для учёта в таймаутах)

Данные двух прогонов `measure_cold_start_all_models.py` сведены в один справочник. **Использовать при настройке:** OLLAMA_EXECUTOR_TIMEOUT, SERVICE_MONITOR_INITIAL_DELAY, таймауты Victoria/backend под выбранную модель.

| Модель | Развёртывание (с) | Ответ тёплый (с) | Холодный итого (с) | Рекоменд. таймаут (с) |
|--------|-------------------|-------------------|--------------------|------------------------|
| qwen3-coder:30b | 1.55 | 0.57 | 2.12 | 65 |
| qwq:32b | 43.25 | 58.12 | 101.37 | 165 |
| qwen2.5-coder:32b | 0 | 123.13 | 119.08 | 180 |
| glm-4.7-flash:q8_0 | 0 | 23.66 | 16.47 | 80 |
| llava:7b | 0.72 | 0.44 | 1.16 | 65 |
| phi3.5:3.8b | 0 | 224.72 | 125.70 | 190 |
| moondream:latest | 198.89 | 0.94 | 199.83 | 265 |
| tinyllama:1.1b-chat | 3.76 | 2.68 | 6.44 | 70 |

- **Машиночитаемый справочник:** **`configs/ollama_model_timings.json`** — те же поля по каждой модели плюс `recommended_timeout_sec` (холодный + буфер 60 с). Подключать в конфигах/скриптах при выборе таймаутов по имени модели.
- При добавлении новых моделей или смене железа — перезапустить `scripts/measure_cold_start_all_models.py` и обновить этот раздел и `configs/ollama_model_timings.json`.

### 4.2. Замеры по моделям MLX (для учёта в таймаутах)

У MLX нет API выгрузки модели; замер — холодный запрос (если модель уже в кэше, будет быстрее) и тёплый запрос. Справочник заполняется скриптом при запущенном MLX-сервере.

**Как получить данные:** запустить MLX (например, knowledge_os или mlx-server; на этой машине порт 11435 может быть закрыт — тогда запускать на той машине, где крутится MLX, или указать `MLX_BASE_URL=http://host:port`), затем:
```bash
MEASURE_SOURCE=mlx MLX_BASE_URL=http://localhost:11435 python scripts/measure_cold_start_all_models.py
```
Результат попадёт в **tmp/cold_start_timings.json** и в **configs/mlx_model_timings.json** (скрипт сам обновит справочник).

- **Машиночитаемый справочник:** **`configs/mlx_model_timings.json`** — структура как у Ollama: `deploy_estimate_sec`, `warm_response_sec`, `cold_total_sec`, `recommended_timeout_sec`. Использовать для таймаутов при выборе MLX-модели.

**Замеренные значения (наш стенд, 2026-02-09, 8 моделей):**

| Модель | Развёртывание (с) | Ответ тёплый (с) | Холодный итого (с) | Рекоменд. таймаут (с) |
|--------|-------------------|------------------|--------------------|------------------------|
| reasoning | 9.17 | 6.56 | 15.73 | 76 |
| coding | 14.92 | 3.96 | 18.88 | 79 |
| fast | 1.49 | 0.33 | 1.82 | 62 |
| tiny | 0.5 | 0.08 | 0.58 | 61 |
| qwen_3b | 1.06 | 0.35 | 1.41 | 61 |
| phi3_mini | 0.45 | 0.36 | 0.81 | 61 |
| default | 2.75 | 4.05 | 6.80 | 67 |
| command-r-plus:104b | 21.9 | 7.48 | 29.38 | 89 |

Остальные (deepseek-r1-distill-llama:70b, llama3.3:70b, qwen2.5-coder:32b, phi3.5:3.8b, phi3:mini-4k, qwen2.5:3b, tinyllama:1.1b-chat) не замерены в этом прогоне: сервер упал при загрузке 70B. Перезапустить MLX и прогнать по одной модели (MEASURE_MODELS=...) при необходимости.

---

## 5. Итог: как получить и использовать данные по каждой модели

- **Своя таблица с выгрузкой:** `scripts/measure_cold_start_all_models.py` — выгрузка (Ollama) → холодный запрос → тёплый запрос, таймаут 30 мин. Результат: tmp/cold_start_timings.*.

- **Своя таблица без выгрузки:** `scripts/measure_all_models_ollama_mlx.py` — два запроса на модель (холодный + тёплый), таймауты по размеру. Результат: tmp/model_timings_ollama_mlx.*.

- **Ориентиры из интернета** — в таблицах §1–§2 выше.

- **Единый справочник по размерам и таймаутам** — [MODEL_TIMING_REFERENCE.md](MODEL_TIMING_REFERENCE.md).
