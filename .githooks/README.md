# Git hooks

- **pre-commit:** при коммите изменённого `configs/experts/employees.json` автоматически запускается `scripts/sync_employees.py` и в коммит добавляются обновлённые `_known_names_generated.py`, `seed_experts.json`, `employees.md`.

Включение (если ещё не включено): из корня репозитория выполнить **`./scripts/install_git_hooks.sh`**.
