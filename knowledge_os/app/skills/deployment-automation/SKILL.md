---
name: deployment-automation
description: CI/CD автоматизация для AI агентів. Використовуй для налаштування deployment pipelines, перевірки якості та безпечного мерджу.
---

# Deployment Automation Skill

## Когда использовать

- Настройка CI/CD pipelines
- Automated deployment
- Quality gates в CI
- Rollback procedures
- Blue-green deployments

## Typical CI Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: npm test

  security:
    runs-on: ubuntu-latest
    steps:
      - name: Security scan
        run: |
          npm audit
          pip audit

  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Lint
        run: npm run lint

  deploy-staging:
    needs: [test, security, lint]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: npm run deploy:staging
```

## Quality Gates

### 1. Test Gate

- Unit tests > 80%
- Integration tests pass
- E2E tests pass

### 2. Security Gate

- SAST pass
- Dependency audit pass
- Secret scan pass
- Vulnerability scan pass

### 3. Lint Gate

- ESLint pass
- TypeScript pass
- Formatting pass

### 4. Review Gate

- PR review approved
- CI/CD checks pass
- Documentation updated

## Deployment Strategies

### Blue-Green

```python
# Switch traffic instant
new_version = "v2.0"
old_version = "v1.9"

# Deploy new
deploy(new_version)

# Test
if health_check(new_version):
    switch_traffic(new_version)
    rollback(old_version)
```

### Canary

```python
# Gradual rollout
traffic_percent = 10

for i in range(100):
    deploy(f"v2.{i}%")
    if error_rate > 1%:
        rollback()
        alert()
```

### Rollback

```python
def rollback():
    # Quick rollback
    git revert last-commit
    deploy previous-version
    notify_team("ROLLBACK")
```

## Environment Variables Best Practice

```bash
# NEVER commit these:
SECRET_KEY=sk-xxx
DATABASE_URL=postgres://...
API_KEY=xxx

# Use secrets manager:
import secretmanager
secret = secretmanager.get('api-key')
```

## Pre-commit Checks

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit
    rev: v4.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: detect-private-key
```

## Commands

```bash
/deploy staging   # Deploy to staging
/deploy prod       # Deploy to production
/health         # Check health
/rollback        # Rollback last
/status         # Deployment status
```
