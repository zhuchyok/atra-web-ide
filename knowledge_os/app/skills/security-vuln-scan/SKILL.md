---
name: security-vuln-scan
description: Сканування безпеки AI-згенерованого коду. Особливо важливо для коду від AI агентів - вони часто роблять типові помилки безпеки.
---

# AI Security Vulnerability Scanner

## Когда использовать
- Проверка AI-сгенерированного кода
- Аудит PR от AI агентов
- Security review перед мерджем

## Типовые уязвимости AI кода (2026)

### Top 5 AI Agent Vulnerabilities

1. **Broken Auth** - AI часто забывает auth middleware
```python
# BAD
@app.route('/admin')
def admin_panel():
    return admin_html()

# GOOD  
@app.route('/admin')
@require_auth
def admin_panel():
    return admin_html()
```

2. **SQL Injection** - AI строит динамические запросы
```python
# BAD
query = f"SELECT * FROM users WHERE id = {user_id}"

# GOOD
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

3. **Hardcoded Secrets** - AI любит hardcode API keys
```python
# BAD
API_KEY = "sk-1234567890"

# GOOD
import os
API_KEY = os.environ.get('API_KEY')
```

4. **XSS** - AI забывает экранирование
```python
# BAD
return f"<h1>{user_input}</h1>"

# GOOD
from markupsafe import escape
return Markup(f"<h1>{escape(user_input)}</h1>")
```

5. **Broken Access Control** - AI не проверяет permissions
```python
# GOOD - explicit checks
@require_role('admin')
def delete_user(user_id):
    ...
```

## Check Process

### Level 1: Fast Scan (30 сек)
- Hardcoded secrets (regex)
- SQL injection patterns
- Auth decorators presence

### Level 2: Deep Scan (2 мин)
- All OWASP Top 10
- Auth flow analysis
- Input validation

### Level 3: Full Scan (10 мин)
- DAST integration
- Dependency audit
- CVEs check

## Quick Check Command
```bash
grep -rn "password\|secret\|key\|token" --include="*.py" .
```

## CI Integration
```yaml
# .github/workflows/security.yml
- name: AI Security Scan
  run: |
    echo "Running security scan..."
    # Run vuln scan
```

## Output

```json
{
  "level": 2,
  "issues_found": 3,
  "severity": {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 0
  },
  "recommendation": "Block merge - HIGH severity found"
}
```

## Fix Patterns

### Auth Fix
```python
# Always add auth decorator
@require_auth
@app.route(...)
```

### Secrets Fix
```python
# Use env vars
import os
SECRET = os.environ.get('SECRET')
# Never commit .env
```

### SQL Fix
```python
# Use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### Input Validation
```python
from pydantic import BaseModel
class UserInput(BaseModel):
    name: str
    email: EmailStr
```