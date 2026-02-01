# Самовосстановление Mac Studio после перезагрузки

**Дата:** 2026-01-27  
**Статус:** ✅ Полная проверка и исправления

---

## 🎯 Цель

Система должна **полностью самовосстанавливаться** после перезагрузки Mac Studio без ручных действий. Все компоненты должны запускаться автоматически.

---

## 📊 ЧТО ДОЛЖНО РАБОТАТЬ ПОСЛЕ ПЕРЕЗАГРУЗКИ

### 1. Базовая инфраструктура
| Компонент | Порт | Автозапуск | Проверка |
|-----------|------|------------|----------|
| Docker Desktop | - | StartAtLogin | `defaults read com.docker.docker StartAtLogin` |
| atra-network | - | При старте Docker | `docker network inspect atra-network` |

### 2. Knowledge OS (Docker, restart: always/unless-stopped)
| Сервис | Порт | Restart | Контейнер |
|--------|------|---------|-----------|
| PostgreSQL | 5432 | always | knowledge_postgres |
| Redis | 6380→6379 | always | knowledge_redis |
| Victoria Agent | 8010 | always | victoria-agent |
| Veronica Agent | 8011 | always | veronica-agent |
| Knowledge OS Worker | - | unless-stopped | knowledge_os_worker |
| Nightly Learner | - | unless-stopped | knowledge_nightly |
| Orchestrator | - | unless-stopped | knowledge_os_orchestrator |
| Prometheus | 9092 | unless-stopped | atra-prometheus |
| Grafana | 3001 | unless-stopped | atra-grafana |
| Elasticsearch | 9200 | unless-stopped | atra-elasticsearch |
| Kibana | 5601 | unless-stopped | atra-kibana |
| Corporation Dashboard | 8501 | unless-stopped | corporation-dashboard |
| Knowledge REST API | 8002 | unless-stopped | knowledge_rest |

### 3. LLM и модели
| Сервис | Порт | Автозапуск | Проверка |
|--------|------|------------|----------|
| Ollama | 11434 | brew services | `brew services list \| grep ollama` |
| MLX API Server | 11435 | launchd | `launchctl list \| grep mlx` |

### 4. ATRA Web IDE (Docker)
| Сервис | Порт | Restart |
|--------|------|---------|
| Backend | 8080 | unless-stopped |
| Frontend | 3000 | unless-stopped |

### 4.1. Victoria Telegram Bot (процесс на хосте)
| Компонент | Автозапуск | Проверка |
|-----------|------------|----------|
| Victoria Telegram Bot | Вручную или LaunchAgent | `pgrep -f victoria_telegram_bot` |

После перезагрузки бот **не запускается автоматически** (это процесс на хосте, не в Docker). Запуск:
```bash
cd /path/to/atra-web-ide && python3 -m src.agents.bridge.victoria_telegram_bot
```
Для автозапуска при загрузке Mac см. `docs/TELEGRAM_VICTORIA_TROUBLESHOOTING.md` или настройте LaunchAgent по аналогии с Victoria MCP.

### 5. Самопроверка
| Компонент | Интервал | Описание |
|-----------|----------|----------|
| system_auto_recovery | 5 мин | Шаг 10: вызывает verify_mac_studio_self_recovery.sh |
| start_self_check | 5 мин | Запускает verify_mac_studio_self_recovery.sh (через start_autonomous_systems) |

### 6. Launchd (автозапуск при загрузке)
| Job | Скрипт | Интервал |
|-----|--------|----------|
| com.atra.auto-recovery | system_auto_recovery.sh | RunAtLoad + 5 мин |
| com.atra.mlx-monitor | monitor_mlx_api_server.sh | KeepAlive |
| com.atra.self-check | start_autonomous_systems.sh | RunAtLoad + 5 мин |
| com.atra.victoria-mcp | Victoria MCP Server | RunAtLoad |
| com.atra.mac-studio-startup | start_all_on_mac_studio.sh | RunAtLoad + 5 мин |

---

## 🔧 ОДНОРАЗОВАЯ НАСТРОЙКА

```bash
# 1. Полный автозапуск (Docker, Ollama, Victoria MCP, SSH Tunnel, Self-Check)
bash scripts/setup_complete_autostart.sh

# 2. Система самовосстановления (запуск каждые 5 мин, исправление сбоев)
bash scripts/setup_system_auto_recovery.sh

# 3. MLX API Server (если используете MLX модели)
bash scripts/setup_mlx_autostart.sh

# 4. LaunchAgent для Mac Studio (start_all каждые 5 мин)
bash scripts/create_mac_studio_autostart.sh
```

---

## 🔄 ПРОЦЕСС ПРИ ПЕРЕЗАГРУЗКЕ

```
1. Mac Studio загружается
   ↓
2. Docker Desktop запускается (StartAtLogin)
   ↓
3. launchd: com.atra.auto-recovery, com.atra.mlx-monitor, com.atra.victoria-mcp
   ↓
4. system_auto_recovery.sh: Docker, atra-network, knowledge_os compose, docker-compose
   ↓
5. Docker контейнеры: db, redis, victoria, veronica, worker, nightly, orchestrator
   ↓
6. Ollama (brew services), MLX (launchd)
   ↓
7. ATRA Web IDE (frontend, backend) — system_auto_recovery поднимает
   ↓
8. ✅ Система готова
```

---

## ✅ ВЕРИФИКАЦИЯ

```bash
# Быстрая проверка всех компонентов
bash scripts/verify_mac_studio_self_recovery.sh

# Ручная проверка
docker ps
curl http://localhost:8010/health  # Victoria
curl http://localhost:8011/health  # Veronica
curl http://localhost:8080/health  # Backend
curl http://localhost:11434/api/tags  # Ollama
launchctl list | grep atra
```

---

## 📋 ИСПРАВЛЕНИЯ (2026-01-27)

1. **db и redis в knowledge_os/docker-compose.yml** — добавлены для самовосстановления (ранее ожидались внешние контейнеры).
2. **system_auto_recovery.sh** — исправлены пути `docker-compose -f knowledge_os/docker-compose.yml` (не `cd knowledge_os`).
3. **start_full_corporation.sh** — обновлены имена контейнеров (knowledge_postgres вместо atra-knowledge-os-db), удалены устаревшие скрипты Orchestrator/Nightly (теперь в Docker).
4. **verify_mac_studio_self_recovery.sh** — новый скрипт верификации всех компонентов.

---

## 🌐 Мировые практики

- **12-Factor App**: Disposability — быстрый старт, graceful shutdown.
- **Docker Restart Policies**: `always` для критичных (db, victoria, veronica), `unless-stopped` для остальных.
- **Health Checks**: PostgreSQL `pg_isready`, Redis `redis-cli ping`.
- **Launchd**: RunAtLoad + StartInterval для периодической проверки и восстановления.

---

*Документация обновлена 2026-01-27*
