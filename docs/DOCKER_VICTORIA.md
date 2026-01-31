# Victoria в Docker — почему не запускается и как исправить

## Почему в Docker не запущено

1. **Docker daemon не запущен**  
   Ошибка: `Cannot connect to the Docker daemon at unix:///.../docker.sock. Is the docker daemon running?`  
   **Решение:** Запустите **Docker Desktop** (или `sudo systemctl start docker` на Linux). Дождитесь, пока Docker полностью поднимется, затем повторите запуск.

2. **Сеть `atra-network` не существовала (исправлено)**  
   Раньше в `knowledge_os/docker-compose.yml` было `atra-network: external: true` — сеть нужно было создавать вручную.  
   **Сейчас:** Сеть создаётся автоматически (`name: atra-network`, без `external`). Дополнительные действия не нужны.

3. **Устаревший атрибут `version` (исправлено)**  
   Предупреждение: `the attribute 'version' is obsolete`.  
   **Сейчас:** Атрибут `version` удалён из `knowledge_os/docker-compose.yml`.

4. **Порт Victoria внутри контейнера (исправлено)**  
   В контейнере маппинг **8010:8000** — внутри должен слушаться порт **8000**.  
   **Сейчас:** В compose для `victoria-agent` задано `VICTORIA_PORT: "8000"`. Локально по умолчанию используется порт **8010** (`VICTORIA_PORT` не задан или 8010).

---

## Как запустить Victoria в Docker

1. Запустите Docker Desktop (или демон Docker).
2. Выполните из корня репо:

```bash
cd ~/Documents/atra-web-ide
bash scripts/start_victoria_docker.sh
```

Скрипт проверит доступность Docker, при необходимости создаст сеть и поднимет контейнер `victoria-agent`.  
Проверка: `curl -s http://localhost:8010/health` → `{"status":"ok","agent":"Виктория"}`.

Запуск ещё и Veronica:

```bash
bash scripts/start_victoria_docker.sh veronica
```

---

## Если Docker не используете

Запуск Victoria локально (без Docker):

```bash
bash START_VICTORIA_LOCAL.sh
```

или:

```bash
export PYTHONPATH="$PWD:$PWD/knowledge_os:$PWD/src"
export USE_VICTORIA_ENHANCED=true
python3 -m src.agents.bridge.victoria_server
```

Victoria будет на http://localhost:8010.
