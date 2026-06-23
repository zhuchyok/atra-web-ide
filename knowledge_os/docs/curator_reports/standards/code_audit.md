# Стандарт проверки кода: code_audit

## Описание

Данный стандарт проверяет наличие запрещенных практик установки пакетов во время выполнения программы (runtime).

## Правило

Запрещено использование `pip install` через `subprocess` или `os.system` внутри кода приложения.

## Примеры нарушения

```python
import subprocess
subprocess.check_call(["pip", "install", "some_package"])

import os
os.system("pip install some_package")
```

## Ожидаемый ответ при проверке

- **ОК**: Если `pip install` отсутствует или используется только в скриптах сборки/Dockerfile.
- **ПРОБЛЕМА**: Если найден вызов `pip install` через `subprocess` или `os.system` в коде приложения.
