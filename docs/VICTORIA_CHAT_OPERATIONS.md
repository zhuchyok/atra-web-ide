# Victoria Chat — Операционные рекомендации

## Результаты проверки (31.01.2026)

### Прошедшие сценарии ✅
| Режим | Промпт | Результат | Время |
|-------|--------|-----------|-------|
| async | simple | pass | ~33 с |
| async | medium | pass | <1 с |
| async | complex | pass | ~231 с |
| sync | medium | pass | ~16 с |

### Известные ограничения
- **sync simple** может упираться в таймаут при высокой нагрузке Victoria — увеличен sync timeout до 600 с.
- **sync complex** требует 5–10 мин — используйте async для сложных запросов (рекомендация по best practices).

## Best Practices (мировые практики)

### Async vs Sync (RFC 6202, ML API)
- **Async (202 + poll):** предпочтителен для сложных задач; нет риска обрыва соединения.
- **Sync (POST, ждём ответ):** проще, но держит HTTP соединение открытым; таймаут 600 с по умолчанию.

### Таймауты
| Компонент | Переменная | По умолчанию |
|-----------|------------|--------------|
| Sync POST | VICTORIA_SYNC_TIMEOUT | 600 с |
| Async poll | VICTORIA_POLL_TIMEOUT_SEC | 900 с |
| Backend Victoria | VICTORIA_TIMEOUT | 600 с |

## Перезапуск после изменений

```bash
# Victoria agent (код, логи [VICTORIA_CYCLE])
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent

# Backend (fallback MLX/Ollama при недоступности Victoria)
docker-compose restart backend

# Telegram бот (localhost-first, дружественные ошибки)
pkill -f victoria_telegram_bot
python3 -m src.agents.bridge.victoria_telegram_bot
```

## Проверка

```bash
# Быстрый тест (simple async)
python3 scripts/test_victoria_chat_full_cycle.py --prompt simple --mode async

# Полный цикл (все сценарии)
python3 scripts/test_victoria_chat_full_cycle.py --poll-max-wait 600
```

## MLX/Ollama из Docker

Victoria в контейнере обращается к `host.docker.internal:11435` (MLX) и `host.docker.internal:11434` (Ollama). При 503/ConnectError проверьте:
- MLX API на хосте: `curl http://localhost:11435/health`
- Ollama на хосте: `curl http://localhost:11434/api/tags`
