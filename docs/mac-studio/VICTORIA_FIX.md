# Victoria Agent — что было не так и что сделано

## Проблемы

1. **Контейнер `victoria-agent` запускал код Вероники**  
   В `docker-compose` был `command: python -m src.agents.bridge.server`. В `server.py` реализован только **VeronicaAgent**, так что под именем Victoria работала Вероника.

2. **Контейнер `veronica-agent` не был HTTP-сервисом**  
   Запускался `knowledge_os.app.veronica_web_researcher` — скрипт с `asyncio.run(test_...)`, который один раз выполнял тест и завершался, а не долгоживущий API.

3. **Ollama/MLX только на localhost**  
   `OllamaExecutor` использовал `http://localhost:11434`. В Docker `localhost` — это сам контейнер, а MLX/Ollama крутятся на хосте (Mac Studio). Из контейнера до них не было доступа.

4. **Нет портов и /health**  
   У агентов не было проброса портов (8010/8011), а в bridge не было эндпоинта `/health`, нужного для проверок.

## Исправления

1. **Отдельный Victoria-сервер**  
   Добавлен `src/agents/bridge/victoria_server.py` с **VictoriaAgent** (Team Lead, planner + executor).  
   Контейнер `victoria-agent` теперь стартует через:
   ```bash
   python -m src.agents.bridge.victoria_server
   ```

2. **Veronica снова через bridge**  
   Контейнер `veronica-agent` переведён на `src.agents.bridge.server` (VeronicaAgent).  
   Оба агента работают как FastAPI-сервисы с `/run`, `/status`, `/health`.

3. **Ollama/MLX по env**  
   - В `OllamaExecutor` добавлена `_ollama_base_url()`: читает `OLLAMA_BASE_URL` или `MAC_STUDIO_LLM_URL`, иначе `http://localhost:11434`.  
   - В docker-compose для обоих агентов задано:
     ```yaml
     OLLAMA_BASE_URL: http://host.docker.internal:11434
     ```
   В Mac Studio MLX API слушает 11434 на хосте, контейнеры ходят туда через `host.docker.internal`.

4. **Порты и /health**  
   - Victoria: `8010:8000`, Veronica: `8011:8000`.  
   - В bridge и в victoria_server добавлен `GET /health`.

## Проверка

```bash
curl -s http://localhost:8010/health   # Victoria
curl -s http://localhost:8011/health   # Veronica
curl -s http://localhost:8010/status
curl -s -X POST http://localhost:8010/run -H "Content-Type: application/json" -d '{"goal": "列出根目录文件"}'
```

Перед этим должны быть подняты Docker-стек Knowledge OS и MLX API (или Ollama) на хосте на порту 11434.
