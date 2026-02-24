# Knowledge OS: Centralized Intelligence Platform

Система централизованного управления знаниями и агентами для Cursor через MCP (Model Context Protocol).

## 🚀 Быстрый старт (Deployment on VDS)

1.  **Скопируйте папку** `knowledge_os` на ваш VDS (например, через SCP или SFTP).
2.  **Установите Docker** (если еще не установлен):
    ```bash
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    ```
3.  **Запустите систему**:
    ```bash
    cd knowledge_os
    docker-compose up -d
    ```

## 🔌 Подключение к Cursor

1. Откройте **Settings** в Cursor -> **Features** -> **MCP**.
2. Нажмите **+ Add New MCP Server**.
3. Введите данные:
   - **Name**: KnowledgeOS
   - **Type**: SSE (или stdio, если запускаете локально)
   - **URL**: `http://YOUR_VDS_IP:8000/sse`

## 🧠 Основные функции (Tools)

- `search_knowledge`: Поиск по всей базе знаний (включая опыт ATRA).
- `capture_knowledge`: Сохранение нового правила или фикса прямо из чата.
- `get_expert_config`: Получение роли любого из 22 экспертов.

## 📷 Работа с картинками (Pillow)

Vision через Moondream Station API работает без Pillow. Для локальной обработки изображений один раз выполните из корня репо:

```bash
bash knowledge_os/scripts/install_pillow.sh
```

При ошибке сборки Pillow нужен libjpeg: **macOS** — при необходимости сначала исправить права: `sudo chown -R $(whoami) /opt/homebrew`, затем `brew install jpeg`; **Linux** — `sudo apt install libjpeg-dev`.

## 📁 Структура

- `/app`: Исходный код API на FastAPI.
- `/db`: Схема БД и файлы инициализации (seed).
- `/scripts`: Скрипты для миграции и обслуживания.

---

_Created by ATRA Experts Team._
