---
name: codeprobe-audit
description: Мультиагентный аудит кода - 9 специализированных агентов для полного анализа codebase. Используй для комплексного code review.
---

# CodeProbe - Multi-Agent Code Audit

## Когда использовать
- Комплексный аудит PR
- Проверка безопасности
- Анализ архитектуры
- Performance review
- Security audit

## 9 Агентов

### 1. Security Agent (`/codeprobe security`)
- SQL injection
- XSS (cross-site scripting)
- Hardcoded secrets
- Auth уязвимости
- CSRF tokens

### 2. SOLID Agent (`/codeprobe solid`)
- Single Responsibility (SRP)
- Open/Closed (OCP)
- Liskov Substitution (LSP)
- Interface Segregation (ISP)
- Dependency Inversion (DIP)

### 3. Architecture Agent (`/codeprobe architecture`)
- Circular dependencies
- Layer violations
- God objects
- Modular structure

### 4. Performance Agent (`/codeprobe performance`)
- N+1 queries
- Memory leaks
- Rendering issues
- Index usage

### 5. Error Handling Agent (`/codeprobe error-handling`)
- Unhandled exceptions
- Missing error boundaries
- Retry logic

### 6. Test Quality Agent (`/codeprobe test-quality`)
- Coverage gaps
- Mock usage
- Test isolation

### 7. Code Smells Agent (`/codeprobe code-smells`)
- Dead code
- Duplication
- Deep nesting
- Long methods

### 8. Design Patterns Agent (`/codeprobe design-patterns`)
- Anti-patterns
- Pattern usage
- Appropriate patterns

### 9. Framework Agent (`/codeprobe framework`)
- Framework conventions
- Best practices
- Configuration issues

## Использование

```bash
/codeprobe audit .        # Full audit
/codeprobe security      # Security only
/codeprobe solid         # SOLID only
/codeprobe health       # Dashboard view
```

## Output format

```json
{
  "findings": [
    {
      "id": "SEC-001",
      "severity": "HIGH",
      "file": "auth.py",
      "line": 42,
      "description": "Hardcoded API key",
      "fix": "Use environment variable"
    }
  ],
  "score": {
    "security": 75,
    "solid": 90,
    "performance": 85
  }
}
```

## Priority Weights

| Category | Weight |
|----------|--------|
| Security | 20% |
| SOLID | 15% |
| Architecture | 15% |
| Error Handling | 12% |
| Performance | 12% |
| Test Quality | 10% |
| Code Smells | 8% |
| Design Patterns | 4% |
| Framework | 4% |