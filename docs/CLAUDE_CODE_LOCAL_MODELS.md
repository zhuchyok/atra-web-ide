# Подключение Claude Code к локальным моделям (Ollama, MLX) и к корпорации

Краткая инструкция: как настроить **Claude Code** (установленный через Homebrew) на использование локальных Ollama/MLX и как это соотносится с агентами и оркестраторами ATRA.

---

## 1. Claude Code → Ollama (рекомендуемый способ)

Ollama (v0.14.0+) поддерживает **Anthropic Messages API**, поэтому Claude Code может работать с локальными моделями через Ollama без облачного API.

### Переменные окружения

Перед запуском Claude Code задайте (в том же терминале или в `~/.zshrc`):

```bash
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:11434
```

Затем запускайте Claude Code из этого терминала (или перезапустите приложение, если оно читает env при старте).

### Быстрый запуск (Ollama 0.15+): одна команда

Ollama 0.15+ умеет сам запускать Claude Code с нужными настройками — переменные окружения не нужны:

```bash
cd /Users/bikos/Documents/OLL
ollama launch claude
```

Или из корня репозитория atra-web-ide:

```bash
./scripts/launch_claude_oll.sh
```

Скрипт переходит в OLL и выполняет `ollama launch claude`. Папку можно задать через `OLL_DIR`, например: `OLL_DIR=/path/to/project ./scripts/launch_claude_oll.sh`.

### Проверка

- Ollama должен быть запущен: `curl -s http://localhost:11434/api/tags`
- Модели в Ollama: `ollama list` (например, `qwen2.5-coder:32b`, `phi3.5:3.8b`, `deepseek-r1-distill-llama:70b`)

Подробнее: [Ollama — Claude Code](https://github.com/ollama/ollama/blob/main/docs/integrations/claude-code.md), [Anthropic compatibility](https://docs.ollama.com/docs/anthropic-compatibility).

---

## 2. Claude Code и MLX

**MLX** (порт 11435) по умолчанию не совместим с Anthropic API. Claude Code «из коробки» умеет указывать только один бэкенд (Ollama через `ANTHROPIC_BASE_URL`).

Варианты:

- **Использовать в Claude Code только Ollama** — все локальные модели тянуть в Ollama (часть моделей у вас уже там).
- **Оставить MLX для корпорации** — Victoria, воркер, оркестраторы продолжают использовать MLX (11435) и Ollama (11434) через LocalAIRouter; Claude Code при этом работает только с Ollama.

Единой «одной кнопкой» настройки Claude Code на MLX нет без своего прокси, который говорит Anthropic API и дергает MLX.

---

## 3. Агенты и оркестраторы (Victoria, Veronica, Knowledge OS)

Они работают **независимо** от Claude Code:

| Компонент        | Порт  | Роль |
|------------------|-------|------|
| **Victoria**     | 8010  | Team Lead, оркестрация, выбор между Ollama и MLX (LocalAIRouter). |
| **Veronica**     | 8011  | Local Developer, вызывается Victoria. |
| **Knowledge OS**| 8002  | REST API, оркестраторы, задачи, Совет Директоров. |
| **Ollama**       | 11434 | Локальные модели для Victoria/воркера и для Claude Code. |
| **MLX**          | 11435 | Локальные модели для Victoria/воркера. |

- **Claude Code** — это отдельный клиент (IDE/терминал), он подключается к **Ollama** (или к облаку Anthropic), а не к Victoria.
- **Victoria, воркер, оркестраторы** по-прежнему используют Ollama и MLX через свой роутер и логику; на них настройки Claude Code не влияют.

---

## 4. Claude Code → Victoria через прокси (эксперты и оркестраторы)

Реализован **прокси** в репозитории: **`proxy/`** (FastAPI). Он принимает запросы в формате Anthropic Messages API (`POST /v1/messages`) и переводит их в вызов Victoria `POST /run`. Ответ возвращается в формате Anthropic. Так Claude Code использует **экспертов и оркестраторы** корпорации.

### Запуск прокси

```bash
pip install -r proxy/requirements.txt
VICTORIA_URL=http://localhost:8010 uvicorn proxy.main:app --host 0.0.0.0 --port 8040
```

Прокси доступен на `http://localhost:8040`. На сервере 185: тот же запуск; снаружи — `http://185.177.216.15:8040` (если порт открыт).

### Настройка Claude Code под прокси

```bash
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:8040
# или для 185: export ANTHROPIC_BASE_URL=http://185.177.216.15:8040
```

Запускайте Claude Code из этого терминала. Запросы пойдут: Claude Code → прокси (8040) → Victoria (8010) → эксперты, оркестраторы, Ollama/MLX.

### Один скрипт: прокси + Claude Code (OLL)

Из корня репозитория:

```bash
./scripts/launch_claude_with_victoria.sh
```

Скрипт поднимает прокси на 8040, ждёт его готовности, переходит в папку OLL (`OLL_DIR`, по умолчанию `/Users/bikos/Documents/OLL`) и запускает `claude launch` с нужными переменными. После закрытия Claude Code прокси останавливается. Нужна запущенная Victoria на 8010.

Переменные (опционально): `OLL_DIR`, `PORT`, `VICTORIA_URL`.

Подробно: [proxy/README.md](../proxy/README.md).

---

## 5. Краткий чеклист

1. Запустить Ollama: `ollama serve` или `brew services start ollama` (от пользователя с моделями).
2. Выставить env для Claude Code: `ANTHROPIC_AUTH_TOKEN=ollama`, `ANTHROPIC_API_KEY=""`, `ANTHROPIC_BASE_URL=http://localhost:11434`.
3. Запустить Claude Code из того же терминала (или после перезагрузки env).
4. **С экспертами:** запустить прокси (`proxy/`), указать Claude Code `ANTHROPIC_BASE_URL=http://localhost:8040` (или 185:8040).

---

**См. также:** [PROJECT_ARCHITECTURE_AND_GUIDE.md](PROJECT_ARCHITECTURE_AND_GUIDE.md) (порты, компоненты), [MASTER_REFERENCE.md](MASTER_REFERENCE.md) (библия проекта).
