# Mac Studio, серверы и сотрудники — сводный справочник

**Проект:** atra-web-ide (всё по Mac Studio)  
**Дата:** 2025-01

---

## 1. Серверы

| Сервер | IP | Роль | SSH |
|--------|-----|------|-----|
| **Сервер 1** | `185.177.216.15` | Основной: Knowledge OS, агенты, Ollama | `ssh root@185.177.216.15` |
| **Сервер 2** | `46.149.66.170` | Миграция (brain) | `ssh root@46.149.66.170` |

- **Пароль** (не коммитить): хранится в `.env`, `SSH_REMOTE_PASS` / `SERVER_PASS`.
- **Путь к проекту на сервере:** `/root/atra`.
- **sshpass:** `brew install hudochenkov/sshpass/sshpass` (для автоматизации).

---

## 2. Mac Studio (M4 Max)

- **MLX API / Ollama:** `http://localhost:11434`
- **MLX API (альт. порт):** `http://localhost:11435` (часто через туннель)
- **Victoria Agent:** `http://localhost:8010` (Docker)
- **Victoria MCP:** `http://localhost:8012` (Cursor MCP, SSE: `/sse`)
- **Knowledge OS API:** `http://localhost:8000`
- **Grafana:** `http://localhost:3000`, **Prometheus:** `http://localhost:9090`

**Модели:** см. `docs/MAC_STUDIO_M4_MODELS_GUIDE.md`, `docs/mac-studio/`.

---

## 3. SSH-туннель (Mac Studio ↔ сервер, Ollama)

- **Назначение:** доступ к Ollama на Mac Studio с сервера (reverse) или с Mac Studio к Ollama на сервере.
- **Порты:** `11435` (туннель) ↔ `11434` (Ollama).
- **Модуль:** `knowledge_os/app/tunnel_manager.py`
  - `get_tunnel_status()` — статус (`активен` / `неактивен`)
  - `ensure_tunnel()` — проверить и при необходимости поднять туннель
  - `TunnelManager(remote_host, remote_pass, tunnel_port=11435, local_port=11434)`
- **Env:** `SSH_REMOTE_HOST`, `SSH_REMOTE_PASS` (иначе дефолт `root@185.177.216.15`).

**Важно:**  
- На Mac Studio при работе с локальным Ollama туннель может не требоваться.  
- При работе **с сервера** к Ollama на Mac Studio — reverse (`-R 11435:localhost:11434`).

---

## 4. Local Router, MLX, Ollama

- **Файл:** `knowledge_os/app/local_router.py`
- **Env:** `MAC_LLM_URL` (default `http://localhost:11435`), `SERVER_LLM_URL` (`http://185.177.216.15:11434`), `USE_LOCAL_LLM`.
- **Ноды:** Mac Studio (MLX) → Mac Studio (Ollama) → Server (Light).
- При `MAC_LLM_URL` с `localhost:11435` перед запросами вызывается `ensure_tunnel()` (один раз за сессию).

---

## 5. Victoria Agent и MCP

- **Victoria:** Team Lead ATRA, HTTP API `localhost:8010`, endpoints `/run`, `/status`, `/health`.
- **Victoria MCP Server:** `src/agents.bridge.victoria_mcp_server`
  - Cursor MCP: SSE `http://localhost:8012/sse`
  - Tools: `victoria_run`, `victoria_status`, `victoria_health`
- **Victoria URL на Mac Studio (по IP):** `http://192.168.1.64:8010` (в MCP при необходимости).
- **Автоподключение:** `scripts/victoria/victoria_auto_connect.sh` — поддерживает **atra-web-ide** (приоритет) и atra.

---

## 6. Сотрудники (эксперты) и иерархия

**Источник:** `knowledge_os/scripts/server_knowledge_sync.py`  
Синхронизация с сервера: эксперты из SQL (`knowledge_os/db/seed_experts.sql`) и MD (`*_program.md` в `learning_programs`).

### Иерархия (уровень 0 — верх)

| Имя | Уровень | Родитель | Отдел |
|-----|---------|----------|--------|
| **Виктория** | 0 | — | Management |
| Дмитрий | 1 | Виктория | ML/AI |
| Мария | 1 | Виктория | Risk Management |
| Сергей | 1 | Виктория | DevOps/Infra |
| Игорь | 1 | Виктория | Backend |
| Анна | 1 | Виктория | QA |
| Роман | 1 | Виктория | Database |
| Ольга | 1 | Виктория | Performance |
| Павел | 1 | Виктория | Strategy |
| Максим | 1 | Виктория | Analysis |
| Андрей | 1 | Виктория | Architecture |
| Татьяна | 1 | Виктория | Documentation |
| Артем | 2 | Виктория | Review |
| Елена | 2 | Сергей | Monitoring |
| Алексей | 2 | Мария | Security |
| София | 2 | Игорь | Web/Frontend |
| Никита | 2 | Игорь | Web/Frontend |
| Дарья | 2 | Татьяна | SEO |
| Марина | 2 | Татьяна | SEO |
| Юлия | 2 | Виктория | Legal |
| Екатерина | 2 | Максим | Finance |
| Глаз | 2 | Дмитрий | Vision/ML |

Остальные эксперты из seed/MD: `level=2`, `parent=Виктория` по умолчанию.

### Запуск синка

```bash
cd knowledge_os/scripts
python3 -c "
import asyncio
from server_knowledge_sync import ServerKnowledgeSync
s = ServerKnowledgeSync()
asyncio.run(s.sync_experts())
asyncio.run(s.sync_reports(limit=50))
"
```

---

## 7. Файлы и скрипты (atra-web-ide)

| Файл | Назначение |
|------|------------|
| `START_MAC_STUDIO_INSTRUCTIONS.md` | Запуск Mac Studio как сервера |
| `COMMAND_FOR_MAC_STUDIO.txt` | Команды для скана моделей на Mac Studio |
| `.env.mac-studio.example` | Пример env для Mac Studio и серверов |
| `scripts/start_mac_studio_full.sh` | Старт всей инфраструктуры на Mac Studio |
| `scripts/copy_mlx_server_to_macstudio.py` | Копирование MLX API server на Mac Studio |
| `scripts/scan_mac_studio_models.sh` | Скан моделей (Ollama, MLX, HF) |
| `scripts/scan_models_mac_studio.sh` | Другой вариант скана моделей |
| `scripts/scan_models_mac_studio_python.py` | Скан моделей (Python) |
| `scripts/install_models_mac_studio.sh` | Установка моделей на Mac Studio |
| `scripts/migration/*` | Миграция на Mac Studio, агенты, верификация |
| `scripts/victoria/victoria_auto_connect.sh` | Автоподключение Victoria (в т.ч. atra-web-ide) |
| `knowledge_os/app/tunnel_manager.py` | SSH-туннель |
| `knowledge_os/app/local_router.py` | Роутинг локальных LLM |
| `knowledge_os/scripts/server_knowledge_sync.py` | Синк экспертов и отчётов с сервера |
| `src/agents/bridge/victoria_mcp_server.py` | Victoria MCP для Cursor |

---

## 8. Документация Mac Studio

- `docs/MAC_STUDIO_M4_MODELS_GUIDE.md` — модели для M4 Max
- `docs/mac-studio/` — миграция, Victoria, MLX, Ollama, Docker и т.д.

---

*Собрано из atra и скопировано в atra-web-ide для работы по Mac Studio.*
