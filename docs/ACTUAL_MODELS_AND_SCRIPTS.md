# Актуальные модели Ollama/MLX и скрипты

**Дата:** 2026-01-29

**Источник истины по спискам моделей:** Скрипт/модуль сканирования при каждом запуске (или по TTL) получает списки Ollama и MLX **раздельно** и не смешивает их. Все актуальные модели получают и используют для дальнейшей работы только оттуда. В коде: `knowledge_os/app/available_models_scanner.py`; скрипт: `scripts/scan_available_models.py`. Компоненты (Victoria, Veronica, Nightly Learner и др.) должны брать модели через сканер: Ollama (11434) — только из ollama_list, MLX (11435) — только из mlx_list.

---

## Модели Ollama (порт 11434)

### Конфиг в коде (`knowledge_os/app/local_router.py` — OLLAMA_MODELS)

| Категория | Модель |
|-----------|--------|
| fast | `phi3.5:3.8b` |
| default | `phi3.5:3.8b` |
| vision | `moondream` |
| vision_pdf | `llava:7b` |
| coding | `glm-4.7-flash:q8_0` |
| reasoning | `glm-4.7-flash:q8_0` |

### Приоритеты по категориям (`knowledge_os/app/available_models_scanner.py` — OLLAMA_PRIORITY_BY_CATEGORY)

- **fast:** phi3.5:3.8b, tinyllama:1.1b-chat, qwen2.5:3b, moondream:latest, qwen2.5-coder:32b  
- **default:** phi3.5:3.8b, tinyllama:1.1b-chat, qwen2.5-coder:32b  
- **general:** qwen2.5-coder:32b, phi3.5:3.8b, qwq:32b, glm-4.7-flash:q8_0, tinyllama:1.1b-chat  
- **coding:** qwen2.5-coder:32b, phi3.5:3.8b, qwq:32b, tinyllama:1.1b-chat  
- **reasoning:** qwen2.5-coder:32b, qwq:32b, glm-4.7-flash:q8_0, phi3.5:3.8b  
- **complex:** qwen2.5-coder:32b, qwq:32b, glm-4.7-flash:q8_0  

### Документированный список (CURRENT_MODELS_LIST.md)

- `qwq:32b`, `qwen2.5-coder:32b`, `glm-4.7-flash:q8_0`, `llava:7b`, `phi3.5:3.8b`, `moondream:latest`

---

## Модели MLX (порт 11435)

### Конфиг в коде (`knowledge_os/app/local_router.py` — MODEL_MAP, env overrides)

| Категория | Модель по умолчанию | Переменная окружения |
|-----------|----------------------|-----------------------|
| coding | `qwen2.5-coder:32b` | MODEL_CODING |
| reasoning | `deepseek-r1-distill-llama:70b` | MODEL_REASONING |
| fast | `phi3.5:3.8b` | MODEL_FAST |
| default | `phi3.5:3.8b` | MODEL_DEFAULT |
| vision | `moondream` | — |
| vision_pdf | `llava:7b` | — |

### Victoria «лучшая сначала» (`available_models_scanner.py` — VICTORIA_BEST_FIRST)

1. command-r-plus:104b  
2. deepseek-r1-distill-llama:70b  
3. llama3.3:70b  
4. qwen2.5-coder:32b  
5. phi3.5:3.8b  
6. qwen2.5:3b  
7. phi3:mini-4k  
8. tinyllama:1.1b-chat  

### Спецификации MLX (docs/MLX_MODELS_SPECIFICATIONS.md)

| Модель | Размер | RAM | Назначение |
|--------|--------|-----|------------|
| command-r-plus:104b | ~65GB | 70–75GB | Максимальная мощность |
| deepseek-r1-distill-llama:70b | ~40GB | 45–50GB | Reasoning |
| llama3.3:70b | ~40GB | 45–50GB | Complex/General |
| qwen2.5-coder:32b | ~20GB | 22–25GB | Default, coding |
| phi3.5:3.8b | ~2.5GB | 3–4GB | Fast |
| phi3:mini-4k | ~2GB | 2.5–3GB | Fast (lightweight) |
| qwen2.5:3b | ~2GB | 2.5–3GB | Fast/Tiny |
| tinyllama:1.1b-chat | ~700MB | 1–1.5GB | Tiny |

Алиасы MLX API: `reasoning`, `coding`, `fast`, `tiny`, `default`, `qwen_3b`, `phi3_mini`.

---

## Переменные окружения (.env и config)

| Переменная | Значение по умолчанию | Описание |
|------------|------------------------|----------|
| OLLAMA_URL | http://localhost:11434 | URL Ollama |
| MLX_API_URL / MAC_LLM_URL | http://localhost:11435 | URL MLX API Server |
| VICTORIA_MODEL | qwen2.5-coder:32b | Модель для Victoria |
| VICTORIA_PLANNER_MODEL | phi3.5:3.8b | Модель для планирования |
| DEFAULT_MODEL (backend) | qwen2.5-coder:32b | Модель по умолчанию в backend |
| MODEL_CODING | qwen2.5-coder:32b | Категория coding (local_router) |
| MODEL_REASONING | deepseek-r1-distill-llama:70b | Категория reasoning |
| MODEL_FAST | phi3.5:3.8b | Категория fast |
| MODEL_DEFAULT | phi3.5:3.8b | Модель по умолчанию (local_router) |
| MLX_PRELOAD_MODELS | fast | Предзагрузка при старте MLX (fast ≈2.5GB; default+fast ≈22GB; пусто = без предзагрузки) |
| MLX_MAX_CACHED_MODELS | 2 | Макс. моделей в кэше MLX API; лишние выгружаются по LRU (снижает пик RAM) |
| MLX_CACHE_CLEANUP_INTERVAL_SEC | 600 | Интервал фоновой очистки кэша (с); 0 = отключить |

---

## Скрипты (модели / Ollama / MLX)

### Запуск и мониторинг MLX

| Скрипт | Назначение |
|--------|------------|
| `scripts/start_mlx_api_server.sh` | Запуск MLX API Server (порт 11435) |
| `scripts/start_mlx_server.sh` | Запуск MLX-сервера |
| `scripts/start_mlx_with_supervisor.py` | Запуск MLX с супервизором |
| `scripts/AUTO_START_MLX.sh` | Автозапуск MLX |
| `scripts/setup_mlx_autostart.sh` | Настройка автозапуска MLX |
| `scripts/check_mlx_status.sh` | Проверка статуса MLX |
| `scripts/check_mlx_status_simple.sh` | Упрощённая проверка MLX |
| `scripts/monitor_mlx_api_server.sh` | Мониторинг MLX API Server |
| `scripts/mlx_api_server.py` | Python-обёртка/запуск MLX API |

### Сканирование и отчёт по моделям

| Скрипт | Назначение |
|--------|------------|
| `scripts/scan_available_models.py` | Сканирование MLX + Ollama, вывод/обновление списка моделей |
| `scripts/check_local_models.sh` | Проверка доступных локальных моделей |
| `scripts/scan_models_mac_studio.sh` | Сканирование моделей на Mac Studio |
| `scripts/scan_mac_studio_models.sh` | То же (альт.) |
| `scripts/scan_models_mac_studio_python.py` | Сканирование моделей на Mac Studio (Python) |
| `scripts/auto_detect_new_models.sh` | Автоопределение новых моделей |
| `scripts/model_usage_report.py` | Отчёт по использованию моделей |
| `scripts/monitor_models.sh` | Мониторинг моделей |

### Ollama и переход на MLX

| Скрипт | Назначение |
|--------|------------|
| `scripts/setup_ollama_for_docker.sh` | Настройка Ollama для Docker |
| `scripts/setup_mlx_instead_ollama.sh` | Настройка MLX вместо Ollama |

### Остальное (трекер, тесты, Mac Studio)

| Скрипт | Назначение |
|--------|------------|
| `scripts/start_model_tracker.sh` | Запуск трекера моделей |
| `scripts/test_mlx_queue_and_routing.py` | Тест очереди и маршрутизации MLX |
| `scripts/install_models_mac_studio.sh` | Установка моделей на Mac Studio |
| `scripts/monitor_glm_download.sh` | Мониторинг загрузки GLM |
| `scripts/check_glm_download.sh` | Проверка загрузки GLM |
| `scripts/warm_up_models.py` | Прогрев моделей (knowledge_os тоже есть) |
| `scripts/finetune_model.sh` | Файнтюнинг модели |

---

## Ключевые файлы конфигурации

| Файл | Содержание |
|------|------------|
| `knowledge_os/app/local_router.py` | MODEL_MAP, OLLAMA_MODELS, узлы (MLX/Ollama/Server) |
| `knowledge_os/app/available_models_scanner.py` | OLLAMA_PRIORITY_BY_CATEGORY, VICTORIA_BEST_FIRST, сканирование /api/tags |
| `backend/app/config.py` | ollama_url, default_model, таймауты |
| `.env` | OLLAMA_URL, VICTORIA_MODEL, VICTORIA_PLANNER_MODEL |
| `docs/CURRENT_MODELS_LIST.md` | Актуальный список моделей Ollama/MLX |
| `docs/MLX_MODELS_SPECIFICATIONS.md` | Спеки MLX (размеры, RAM, предзагрузка) |

---

## Порты

| Сервис | Порт | Переменная |
|--------|------|------------|
| Ollama | 11434 | OLLAMA_URL |
| MLX API Server | 11435 | MLX_API_PORT / MAC_LLM_URL |

---

*Документ собран из кода и docs на 2026-01-29.*
