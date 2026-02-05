# VictoriaATRA: как правильно вызывать

VictoriaATRA — это MCP-сервер, который даёт Cursor доступ к Victoria (Team Lead ATRA). В Cursor доступны **4 инструмента**.

---

## 1. В чате Cursor

Пишите запрос **своими словами**, Cursor сам выберет инструмент:

| Что хотите | Пример фразы в чате |
|------------|---------------------|
| Запустить задачу через Викторию | «Вызови Викторию с задачей: проанализируй структуру backend и предложи улучшения» |
| Просто спросить / поболтать | «Спроси Викторию: какие эксперты есть в корпорации?» |
| Проверить, что Victoria жива | «Проверь victoria_health» или «Вызови victoria_status» |

Можно явно называть инструмент:

- «Вызови **victoria_run** с goal: добавь в README раздел про запуск»
- «Вызови **victoria_chat** с сообщением: привет, какой контекст проекта сейчас?»
- «Вызови **victoria_health**»
- «Вызови **victoria_status**»

---

## 2. Инструменты (что под капотом)

### victoria_run

Запускает **задачу** через Victoria (оркестратор → эксперты).

- **goal** (обязательно) — текст задачи, например: «Добавь в .env.example переменную VICTORIA_URL».
- **max_steps** (необязательно, по умолчанию 500) — лимит шагов.

**Пример в чате:**  
«Вызови victoria_run с goal: проверь, что в backend есть эндпоинт /health»

---

### victoria_chat

**Диалог** с Викторией (вопрос–ответ).

- **message** (обязательно) — ваше сообщение.
- **history_json** (необязательно) — история диалога в JSON.
- **project_context** (необязательно, по умолчанию `atra-web-ide`) — контекст проекта.

**Пример в чате:**  
«Вызови victoria_chat с сообщением: кто такой Артём и чем он занимается?»

---

### victoria_status

Краткий **статус** Victoria (онлайн/офлайн, размер базы знаний и т.п.).

**Пример в чате:**  
«Вызови victoria_status»

---

### victoria_health

Проверка **доступности** Victoria (health check).

**Пример в чате:**  
«Вызови victoria_health»

---

## 3. Через MCP в Cursor (если есть панель Tools)

Если в Cursor открыта панель MCP / Tools:

1. Выберите сервер **VictoriaATRA**.
2. Выберите инструмент: `victoria_run`, `victoria_chat`, `victoria_status` или `victoria_health`.
3. Заполните параметры (для `victoria_run` — поле goal, для `victoria_chat` — message) и выполните вызов.

---

## 4. Что должно быть запущено

Чтобы вызовы работали:

1. **Victoria Agent** — порт 8010 (например, `docker-compose -f knowledge_os/docker-compose.yml up -d`).
2. **Victoria MCP Server** — порт 8012:
   ```bash
   VICTORIA_URL=http://localhost:8010 python3 -m src.agents.bridge.victoria_mcp_server
   ```
3. В настройках Cursor MCP указан **VictoriaATRA** с URL `http://localhost:8012/sse` (или ваш туннель/хост).

После этого «вызывать VictoriaATRA» = писать в чат Cursor фразы из таблицы выше или вызывать инструменты через панель MCP.
