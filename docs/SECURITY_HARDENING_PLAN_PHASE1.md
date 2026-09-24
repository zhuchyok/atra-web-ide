# План усиления безопасности ATRA Corporation

## Фаза 1: Security Hardening

---

## 1.1 Исправление SQL Injection

### Файл: `src/agents/bridge/victoria_server.py`

### Проблема 1 — Строка 1414

Текущий код:

```python
rows = await conn.fetch(
    """
    SELECT content, confidence_score
    FROM knowledge_nodes
    WHERE confidence_score > 0.3
    AND content ILIKE $1
    ORDER BY confidence_score DESC NULLS LAST, usage_count DESC NULLS LAST, created_at DESC
    LIMIT $2
    """,
    f"%{goal[:50]}%",  # ❌ Прямая интерполяция
    limit,
)
```

**Проблема**: Хотя psycopg2 автоматически экранирует параметры, использование `ILIKE` с подстановкой `%` может позволить экранирование through LIKE escape sequences. Также `goal[:50]` ограничение insufficient для полной защиты.

**Исправление** — Предварительная валидация + sanitize:

```python
# Добавить функцию валидации в начало файла
def _sanitize_sql_like_pattern(text: str, max_len: int = 100) -> str:
    """Удалить SQL wildcard characters для предотвращения LIKE injection"""
    if not text or not isinstance(text, str):
        return ""
    # Удалить % и _ (SQL LIKE wildcards)
    sanitized = text.replace("%", "").replace("_", "").strip()
    # Ограничить длину
    sanitized = sanitized[:max_len]
    # Экранировать оставшиеся спецсимволы LIKE
    sanitized = sanitized.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    return sanitized

def _validate_limit(limit: Any) -> int:
    """Валидировать и привести LIMIT к безопасному целому"""
    try:
        lim = int(limit)
        return max(1, min(lim, 100))  # Ограничить 1-100
    except (ValueError, TypeError):
        return 10

# Исправленный код (строка ~1414)
safe_goal = _sanitize_sql_like_pattern(goal, max_len=50)
safe_limit = _validate_limit(limit)
rows = await conn.fetch(
    """
    SELECT content, confidence_score
    FROM knowledge_nodes
    WHERE confidence_score > 0.3
    AND content ILIKE $1 ESCAPE '\\'
    ORDER BY confidence_score DESC NULLS LAST, usage_count DESC NULLS LAST, created_at DESC
    LIMIT $2
    """,
    f"%{safe_goal}%",
    safe_limit,
)
```

### Проблема 2 — Строка 3538

Текущий код:

```python
prompt = f'''Пользователь просит: "{goal[:300]}"
Переформулировка системы: "{restated[:200]}"
Задача неоднозначна. Дай 2–3 кратких уточняющих вопроса (на русском).
Ответь СТРОГО JSON: {{"questions": ["Вопрос 1?", "Вопрос 2?"]}}'''
```

**Проблема**: String interpolation into LLM prompt — indirect injection risk. Злоумышленник может inject prompt injection через goal.

**Исправление**:

````python
def _sanitize_prompt_input(text: str, max_len: int = 500) -> str:
    """Удалить потенциальные prompt injection паттерны"""
    if not text or not isinstance(text, str):
        return ""
    sanitized = text[:max_len]
    # Удалить common prompt injection patterns
    injection_patterns = [
        r"^ignore\s+previous",
        r"^disregard\s+instructions",
        r"^forget\s+all",
        r"^{{-?\s*",
        r"^```system",
        r"^<\|system\|>",
        r"^SYSTEM:",
        r"^AI\s+assistant:",
        r"\|\s*endos",
    ]
    import re
    for pattern in injection_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
    # Удалить null bytes и control characters
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", sanitized)
    return sanitized.strip()

# Исправленный код (строка ~3536)
safe_goal = _sanitize_prompt_input(goal, max_len=300)
safe_restated = _sanitize_prompt_input(restated, max_len=200)
prompt = f'''Пользователь просит: "{safe_goal[:300]}"
Переформулировка системы: "{safe_restated[:200]}"
Задача неоднозначна. Дай 2–3 кратких уточняющих вопроса (на русском).
Ответь СТРОГО JSON: {{"questions": ["Вопрос 1?", "Вопрос 2?"]}}'''
````

### Стратегия тестирования SQL Injection

| Тест               | Ожидаемый результат | Команда                                                              |
| ------------------ | ------------------- | -------------------------------------------------------------------- |
| Normal query       | Работает как раньше | `curl -X POST /api/victoria/query -d '{"goal": "найди информацию"}'` |
| LIKE injection `%` | Фильтруется         | `goal="test% DROP TABLE--"` — `%` удаляется                          |
| SQL wildcard `_`   | Фильтруется         | `goal="test_"` — `_` удаляется                                       |
| Prompt injection   | Фильтруется         | `goal="ignore previous instructions"` — паттерн удаляется            |
| Oversized input    | Усекается           | `goal="a"*1000` — до max_len                                         |

**Автоматизированные тесты:**

```bash
# Установить sqlmap для дополнительного тестирования (только в dev!)
pip install sqlmap
# ВНИМАНИЕ: Только на тестовой БД!
sqlmap -u "http://victoria:8000/api/search" --data="goal=test" --level=5
```

---

## 1.2 Исправление Command Injection

### Файл: `src/agents/bridge/victoria_mcp_server.py`

**Текущий код (строки 230-233)**:

```python
elif action == "run":
    command = step.get("command", "")
    result_text = f"[Выполнена команда: {command}]"
    results.append(f"✅ Шаг {i}: {action} - {result_text}")
```

**Проблемы**:

1. `command` выполняется напрямую без валидации — command injection
2. `workspace_path` может содержать `/Users/bikos` — захардкоженный путь
3. Нет allowlist разрешенных команд

**Исправление — Allowlist подход**:

```python
# Добавить константы после импортов (строка ~50)
ALLOWED_COMMANDS = frozenset({
    "python3", "python", "pip", "pip3", "npm", "node",
    "git", "curl", "wget", "ls", "cat", "echo", "pwd",
    "mkdir", "touch", "cp", "mv", "rm", "chmod", "chown",
    "docker", "docker-compose", "poetry", "uv",
})

ALLOWED_EXTENSIONS = frozenset({".py", ".js", ".ts", ".json", ".yml", ".yaml", ".md", ".txt", ".sh"})

# Добавить функции валидации
def _validate_command(command: str) -> Tuple[bool, str]:
    """Валидировать ��оманду по allowlist"""
    if not command or not isinstance(command, str):
        return False, "Пустая команда"
    parts = command.strip().split()
    if not parts:
        return False, "Пустая команда"
    cmd_name = parts[0]
    # Normalize command name
    cmd_name = os.path.basename(cmd_name)
    if cmd_name not in ALLOWED_COMMANDS:
        return False, f"Команда '{cmd_name}' не разрешена. Разрешены: {', '.join(sorted(ALLOWED_COMMANDS))}"
    return True, ""

def _validate_path(path: str, workspace_root: str = "/workspace") -> Tuple[bool, str]:
    """Валидировать и нормализовать путь"""
    if not path or not isinstance(path, str):
        return False, "Пустой путь"
    # Разрешить только workspace и /tmp
    allowed_roots = {workspace_root, "/tmp", "/app"}
    # Normalize и resolve
    try:
        abs_path = os.path.abspath(os.path.expanduser(path))
    except Exception:
        return False, "Некорректный путь"
    # Проверить что путь в allowed area
    for root in allowed_roots:
        if abs_path.startswith(root):
            return True, abs_path
    return False, f"Путь должен начинаться с: {', '.join(allowed_roots)}"

def _sanitize_args(args: str) -> str:
    """Удалить опасные аргументы shell"""
    if not args:
        return ""
    # Block common dangerous patterns
    dangerous = r";\s*\w|\|\s*\w|\&&\s*\w|\|\||\s*rm\s+-rf|>|;|&&|\|\|"
    import re
    sanitized = re.sub(dangerous, "", args)
    # Limit length
    return sanitized[:500]

# Исправленный код (строки ~230-233)
elif action == "run":
    command = step.get("command", "")
    # Dry-run: проверить валидацию без выполнения
    is_valid, error_msg = _validate_command(command)
    if not is_valid:
        results.append(f"❌ Шаг {i}: {action} - Ошибка валидации: {error_msg}")
        continue
    safe_command = _sanitize_args(command)
    result_text = f"[Выполнена команда: {safe_command}]"
    results.append(f"✅ Шаг {i}: {action} - {result_text}")
```

### Исправление Workspace Path

**Проблема**: Строки 73-74 в docker-compose.yml содержат `/Users/bikos`.

**Исправление docker-compose.yml**:

```yaml
# Вместо:
- /Users/bikos/Documents/dev/setki-21:/workspace/setki-21
- /Users/bikos/Documents/dev/atra:/workspace/atra

# Использовать:
- ${DEV_SETKI_PATH:-./dev/setki-21}:/workspace/setki-21
- ${DEV_ATRA_PATH:-./dev/atra}:/workspace/atra

# Добавить в .env:
DEV_SETKI_PATH=/Users/bikos/Documents/dev/setki-21
DEV_ATRA_PATH=/Users/bikos/Documents/dev/atra
```

**Исправление кода**:

```python
# В victoria_mcp_server.py вместо захардкоженного пути:
WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", "/workspace")
# Удалить: /Users/bikos
```

### Стратегия тестирования Command Injection

| Тест                        | Ожидаемый результат            |
| --------------------------- | ------------------------------ |
| `python3 script.py`         | ✅ Выполняется                 |
| `cat /etc/passwd`           | ❌ Отклонено                   |
| `rm -rf /`                  | ❌ Отклонено                   |
| `echo "test" > /etc/passwd` | ❌ Отклонено                   |
| `; cat /etc/passwd`         | ❌ Отклонено (sanitized)       |
| `ls /Users/bikos`           | ❌ Отклонено (path validation) |

**Сканеры**:

```bash
# Bandit — static analysis для Python
pip install bandit
bandit -r src/agents/bridge/victoria_mcp_server.py

# Semi-automated payload testing
# Запустить и попробовать: curl -X POST /api/mcp/run -d '{"command": "cat /etc/passwd"}'
```

---

## 1.3 Исправление CORS

### Файлы с Wildcard CORS

| Файл                                 | Строка | Проблема              |
| ------------------------------------ | ------ | --------------------- |
| `src/utils/rest_api.py`              | 47     | `allow_origins=["*"]` |
| `knowledge_os/app/rest_api.py`       | 59     | `allow_origins=["*"]` |
| `knowledge_os/app/mlx_api_server.py` | 132    | `allow_origins=["*"]` |

### Список разрешенных источников

```python
ALLOWED_ORIGINS = frozenset([
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
    "https://localhost:3000",
    "https://localhost:8080",
    "tauri://localhost",          # Tauri desktop app
    "tauri://127.0.0.1",          # Tauri desktop app
    "http://web-ide.local:3000",  # Local network
    "http://192.168.1.100:3000",  # Adjust for local network
])
```

### Исправление

**`src/utils/rest_api.py`**:

```python
# Строка 44-50 — заменить:
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)
```

**`knowledge_os/app/rest_api.py`**:

```python
# Строка 56-63 — заменить:
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)
```

**`knowledge_os/app/mlx_api_server.py`**:

```python
# Строка ~132 — заменить:
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)
```

### Стратегия тестирования CORS

```bash
# Тест 1: Разрешенный origin
curl -H "Origin: http://localhost:3000" -H "Content-Type: application/json" \
  -X OPTIONS http://localhost:8080/api/health -v 2>&1 | grep -i "access-control"

# Ожидается: Access-Control-Allow-Origin: http://localhost:3000

# Тест 2: Запрещенный origin
curl -H "Origin: http://evil.com" -H "Content-Type: application/json" \
  -X OPTIONS http://localhost:8080/api/health -v 2>&1 | grep -i "access-control"

# Ожидается: НЕТ Access-Control-Allow-Origin header или ошибка

# Тест 3: credentials с wildcard
# Проверить что allow_credentials=True и allow_origins=["*"] не работают вместе
```

---

## 1.4 Управление Секретами

### Файл: `docker-compose.yml`

**Текущие проблемы** (строки 23, 67, 84, 148):

- `admin:secret` — hardcoded credentials
- `GF_SECURITY_ADMIN_PASSWORD=admin` — default password

### Исправление

**Шаг 1: Создать .env файл**

```bash
# Создать .env (НЕ ДОБАВЛЯТЬ В GIT!)
cat > .env << 'EOF'
# Database
POSTGRES_USER=atra_db_user
POSTGRES_PASSWORD=<generate-strong-password>
POSTGRES_DB=knowledge_os

# API Keys — генерировать через: openssl rand -hex 32
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@knowledge_postgres:5432/${POSTGRES_DB}
API_KEY=<generate-strong-password>

# Telegram
TELEGRAM_BOT_TOKEN=<your-token>
TELEGRAM_CHAT_ID=<your-chat-id>

# Ollama
OLLAMA_API_KEY=

# Grafana
GF_SECURITY_ADMIN_PASSWORD=<generate-strong-password>
GF_SECURITY_ADMIN_USER=admin

# Victoria
VICTORIA_API_KEY=<generate-strong-password>
EOF
chmod 600 .env
```

**Шаг 2: Изменить docker-compose.yml**

```yaml
# Строка 23 — удалить hardcoded:
# - DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os
# Заменить на:
environment:
  - DATABASE_URL=${DATABASE_URL}
  - API_KEY=${API_KEY}
  # ... другие переменные

env_file: .env  # Добавить после volumes для service

# Строка 67:
env_file: .env

# Строка 84:
- DATABASE_URL=${DATABASE_URL}

# Строка 148:
- GF_SECURITY_ADMIN_PASSWORD=${GF_SECURITY_ADMIN_PASSWORD}
```

### knowledge_os/app/rest_api.py

```python
# Строка 65-66 — изменить:
DB_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

# Добавить валидацию при старте
if not API_KEY or API_KEY == "your-secret-api-key":
    raise ValueError("API_KEY must be set in environment")
```

### Secrets Rotation Script

```python
#!/usr/bin/env python3
"""Скрипт ротации секретов"""
import os
import secrets
import json
from pathlib import Path

def rotate_api_key(env_file: str = ".env", key_name: str = "API_KEY"):
    """Ротация API ключа"""
    env_path = Path(env_file)
    if not env_path.exists():
        print(f"Создаю {env_file}")
        env_path.touch()

    new_key = secrets.token_urlsafe(32)
    # Читать существующий .env
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key_name}="):
            new_lines.append(f"{key_name}={new_key}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key_name}={new_key}")

    env_path.write_text("\n".join(new_lines) + "\n")
    print(f"✅ {key_name} обновлен")
    print(f"🔐 Новый ключ: {new_key[:8]}...")
    print("⚠️  Перезапустите сервисы: docker-compose restart")
    return new_key

if __name__ == "__main__":
    rotate_api_key()
```

### Стратегия тестирования secrets

```bash
# Тест 1: Проверить что secrets не в коде
grep -r "password.*=" --include="*.py" src/ | grep -v "os.getenv"
# Ожидается: ничего

# Тест 2: Проверить .env не в git
git check-ignore .env && echo "✅ .env в gitignore" || echo "❌ .env НЕ в gitignore!"

# Тест 3: Hard-coded passwords
grep -rE "(secret|admin|password).*=.*['\"][^'\"]{4,}['\"]" --include="*.yml" .
# Ожидается: ничего (кроме демо/тестовых значений)

# Тест 4: scan for secrets
pip install detect-secrets
detect-secrets-scan .
```

---

## 1.5 Ротация API Keys

### Архитектура ротации

```
┌─────────────────────────────────────────────────────────┐
│                    API Key Rotation                     │
├─────────────────────────────────────────────────────────┤
│  1. Старт: API_KEY_v1 = "old_key"                      │
│  2. День N: Сгенерировать API_KEY_v2                 │
│  3. День N: Акcept both v1 and v2                     │
│  4. День N+grace: Invalidate v1                       │
│  5. День N+grace+1: Only v2 accepted                  │
└─────────────────────────────────────────────────────────┘
Grace period: 7 дней (конфигурируемо)
```

### Реализация

```python
# utils/api_key_rotation.py
import os
import time
import hashlib
from typing import Dict, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class RotatingAPIKey:
    key_hash: str
    created_at: float
    expires_at: Optional[float] = None
    is_active: bool = True

class APIKeyRotationManager:
    """Менеджер ротации API ключей с grace period"""

    def __init__(self, grace_period_days: int = 7):
        self.grace_period_seconds = grace_period_days * 24 * 3600
        self._keys: Dict[str, RotatingAPIKey] = {}
        self._current_key_hash: Optional[str] = None
        self._storage_file = os.getenv("API_KEYS_STORAGE", "/app/data/api_keys.json")

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def add_key(self, key: str, grace_period_override: Optional[int] = None) -> bool:
        """Добавить новый ключ (автоматически делает предыдущий неактивным через grace period)"""
        key_hash = self._hash_key(key)
        grace = grace_period_override or self.grace_period_seconds

        # Деактивировать старый ключ если есть новый
        if self._current_key_hash and self._current_key_hash != key_hash:
            old_key = self._keys.get(self._current_key_hash)
            if old_key and old_key.is_active:
                old_key.is_active = False
                old_key.expires_at = time.time() + grace
                print(f"⏳ Старый ключ деактивирован, grace period до {datetime.fromtimestamp(old_key.expires_at)}")

        self._keys[key_hash] = RotatingAPIKey(
            key_hash=key_hash,
            created_at=time.time(),
            is_active=True
        )
        self._current_key_hash = key_hash
        return True

    def validate_key(self, key: str) -> bool:
        """Проверить ключ — принимает активные и keys в grace period"""
        key_hash = self._hash_key(key)
        key_data = self._keys.get(key_hash)

        if not key_data:
            return False

        # Активный ключ
        if key_data.is_active:
            return True

        # Ключ в grace period — еще принимаем
        if key_data.expires_at and time.time() < key_data.expires_at:
            print(f"⚠️  Ключ в grace period, истекает {datetime.fromtimestamp(key_data.expires_at)}")
            return True

        # Ключ истек
        return False

    def rotate(self) -> str:
        """Сгенерировать и добавить новый ключ"""
        import secrets
        new_key = secrets.token_urlsafe(32)
        self.add_key(new_key)
        return new_key

    def revoke_old(self) -> None:
        """Принудительно отозвать старые ключи"""
        if self._current_key_hash:
            for key_hash, key_data in self._keys.items():
                if key_hash != self._current_key_hash:
                    key_data.is_active = False
                    key_data.expires_at = time.time()

# Глобальный экземпляр
_api_key_manager: Optional[APIKeyRotationManager] = None

def get_api_key_manager() -> APIKeyRotationManager:
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyRotationManager(
            grace_period_days=int(os.getenv("API_KEY_GRACE_DAYS", "7"))
        )
    return _api_key_manager
```

### Интеграция с endpoints

```python
# knowledge_os/app/rest_api.py — добавить
from utils.api_key_rotation import get_api_key_manager

async def verify_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Расширенная верификация с ротацией"""
    manager = get_api_key_manager()
    if not manager.validate_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    return api_key

@app.post("/api/admin/rotate-key", dependencies=[Depends(verify_api_key)])
async def rotate_api_key():
    """Ротация API ключа — только для админов"""
    manager = get_api_key_manager()
    new_key = manager.rotate()
    return {"new_key": new_key, "grace_period_days": 7}
```

### Стратегия тестирования

```python
# test_api_key_rotation.py
import pytest
from utils.api_key_rotation import APIKeyRotationManager

def test_key_rotation():
    manager = APIKeyRotationManager(grace_period_days=0)  # instant для теста

    # Добавить первый ключ
    key1 = manager.add_key("test_key_1")
    assert manager.validate_key("test_key_1") == True

    # Добавить второй ключ — первый должен перейти в grace
    key2 = manager.rotate()  # генерирует новый
    assert manager.validate_key("test_key_1") == True  # still in grace
    assert manager.validate_key(key2) == True

    # После истечения grace — первый невалиден
    import time
    time.sleep(0.1)
    assert manager.validate_key("test_key_1") == False
```

---

## 2. Порядок Реализации

### Зависимости между исправлениями

```
Priority 1 (День 1-2) — Критические
├── 1.3 CORS Fix ( quickest win)              ────┐
│   └── 1.4 Secrets Management                ─┤
│       └── 1.1 SQL Injection Fix             ─┤
│           └── 1.2 Command Injection Fix        ─┘
│
Priority 2 (День 3-4) — Важные
├── 1.5 API Key Rotation
└── Input Validation (расширенная)
```

### Rollback Plan для каждого исправления

| Исправление       | Rollback Command                                                    |
| ----------------- | ------------------------------------------------------------------- |
| CORS              | `git checkout -- src/utils/rest_api.py` + restart                   |
| SQL Injection     | `git diff` + `python -c "print('test%_')"` — проверить OLD behavior |
| Command Injection | Docker container logs, `docker-compose logs victoria`               |
| Secrets           | Восстановить из backup: `cp .env.backup .env`                       |

---

## 3. Верификация

### Quick Security Scan

```bash
#!/bin/bash
# security-scan.sh

echo "=== ATRA Security Scan ==="

# 1. CORS check
echo -e "\n[1] CORS Wildcard Check"
grep -rn 'allow_origins=\["\*"\]' --include="*.py" .

# 2. Hardcoded secrets
echo -e "\n[2] Hardcoded Secrets"
grep -rnE '(password|secret|key).*=.*{4,}' --include="*.py" --include="*.yml" . | grep -v "os.getenv" | grep -v ".env"

# 3. SQL Injection vectors
echo -e "\n[3] SQL Parameterization"
grep -n '\.format\|f".*SELECT\|\$.*\$' src/agents/bridge/victoria_server.py | head -20

# 4. Command execution
echo -e "\n[4] Command Execution"
grep -n 'subprocess\|os.system\|exec(' src/agents/bridge/victoria_mcp_server.py | head -10

# 5. Bandit scan
echo -e "\n[5] Bandit Scan"
bandit -r src/agents/bridge/victoria_mcp_server.py -f txt 2>/dev/null | grep -i "subprocess\|shell" | head -10

# 6. Git secrets scan
echo -e "\n[6] Git Secrets Scan"
if command -v detect-secrets-scan &> /dev/null; then
    detect-secrets-scan .
else
    git log -p --all -S 'password=' | head -20
fi

echo -e "\n=== Scan Complete ==="
```

### Integration Tests

```python
# tests/test_security_phase1.py
import pytest
from fastapi.testclient import TestClient
from src.utils.rest_api import app

client = TestClient(app)

def test_cors_allowed():
    """CORS: разрешенный origin"""
    r = client.options("/api/health", headers={"Origin": "http://localhost:3000"})
    assert "Access-Control-Allow-Origin" in r.headers

def test_cors_blocked():
    """CORS: запрещенный origin"""
    r = client.options("/api/health", headers={"Origin": "http://evil.com"})
    assert "Access-Control-Allow-Origin" not in r.headers

def test_sql_injection_sanitize():
    """SQL: LIKE injection sanitized"""
    from src.agents.bridge.victoria_server import _sanitize_sql_like_pattern
    result = _sanitize_sql_like_pattern("test% DROP TABLE")
    assert "%" not in result
    assert "DROP" not in result

def test_command_blocked():
    """Command: запрещенная команда отклонена"""
    from src.agents.bridge.victoria_mcp_server import _validate_command
    valid, _ = _validate_command("python3 script.py")
    assert valid == True
    valid, _ = _validate_command("rm -rf /")
    assert valid == False
```

---

## 4. Checklist Реализации

- [ ] **CORS Fix**
  - [ ] `src/utils/rest_api.py` — строки 44-50
  - [ ] `knowledge_os/app/rest_api.py` — строки 56-63
  - [ ] `knowledge_os/app/mlx_api_server.py` — строка 132
  - [ ] Добавить `tauri://localhost` в allow_origins

- [ ] **Secrets Management**
  - [ ] Создать `.env` файл сstrong passwords
  - [ ] Удалить hardcoded из `docker-compose.yml`
  - [ ] Обновить `knowledge_os/app/rest_api.py` — валидация при старте
  - [ ] Добавить `.env` в `.gitignore`

- [ ] **SQL Injection**
  - [ ] Добавить функцию `_sanitize_sql_like_pattern`
  - [ ] Добавить функцию `_validate_limit`
  - [ ] Обновить код строки 1403-1415
  - [ ] Добавить функцию `_sanitize_prompt_input`
  - [ ] Обновить код строка 3536-3539
  - [ ] Написать unit тесты

- [ ] **Command Injection**
  - [ ] Добавить `ALLOWED_COMMANDS` set
  - [ ] Добавить функцию `_validate_command`
  - [ ] Добавить функцию `_validate_path`
  - [ ] Добавить функцию `_sanitize_args`
  - [ ] Обновить код строки 230-233
  - [ ] Исправить workspace path в docker-compose

- [ ] **API Key Rotation**
  - [ ] Создать `utils/api_key_rotation.py`
  - [ ] Интегрировать в `rest_api.py`
  - [ ] Добавить endpoint `/api/admin/rotate-key`
  - [ ] Написать тесты

- [ ] **Security Scan**
  - [ ] Запустить `bandit`
  - [ ] Запустить custom `security-scan.sh`
  - [ ] Проверить `.env` не в git

---

## 5. Дополнительные Рекомендации

### Defense in Depth

```
┌────────────────────────────────────────────┐
│           Security Layers                  │
├────────────────────────────────────────────┤
│ Layer 1: Input Validation                 │
│ Layer 2: Allowlist                        │
│ Layer 3: Rate Limiting                    │
│ Layer 4: Authentication/Authorization     │
│ Layer 5: Logging/Monitoring               │
└────────────────────────────────────────────┘
```

### Zero Trust Principles

1. **Never trust, always verify** — каждая проверка должна быть explicit
2. **Least privilege** — минимумpermissions для каждой операции
3. **Assume breach** — логировать все подозрительные попытки

### Logging

```python
import logging
security_logger = logging.getLogger("security")

def log_security_event(event_type: str, details: dict):
    security_logger.warning(
        f"Security event: {event_type}",
        extra={"event": event_type, **details}
    )

# Использовать:
log_security_event("command_blocked", {"command": command[:50], "reason": error_msg})
log_security_event("sql_injection_attempt", {"input": goal[:100]})
```

---

## Contacts

- Telegram: `@atra_security`
- Email: `security@atra.corp`
- On-call: `+7 999 000-SEC`
