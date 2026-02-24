"""
Documentation Generator: Автогенерация документации

Функционал:
- Автогенерация документации из кода (docstrings)
- Автогенерация API документации
- Автогенерация примеров использования
- Интерактивные туториалы
"""

import ast
import importlib
import inspect
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodeDocumentationExtractor:
    """Извлечение документации из кода"""

    def __init__(self, base_path: str = "knowledge_os/app"):
        self.base_path = Path(base_path)

    def extract_module_docs(self, module_path: str) -> Dict[str, Any]:
        """Извлечение документации из модуля"""
        try:
            module_file = self.base_path / module_path
            if not module_file.exists():
                return {}

            with open(module_file, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            module_doc = ast.get_docstring(tree) or ""

            classes = []
            functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_doc = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node) or "",
                        "methods": [],
                    }

                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_doc = {
                                "name": item.name,
                                "docstring": ast.get_docstring(item) or "",
                                "args": [arg.arg for arg in item.args.args],
                            }
                            class_doc["methods"].append(method_doc)

                    classes.append(class_doc)

            # Топ-уровневые функции (не внутри классов)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    func_doc = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node) or "",
                        "args": [arg.arg for arg in node.args.args],
                    }
                    functions.append(func_doc)

            return {
                "module": module_path,
                "module_doc": module_doc,
                "classes": classes,
                "functions": functions,
            }
        except Exception as e:
            logger.error(f"Error extracting docs from {module_path}: {e}")
            return {}

    def extract_all_modules(self) -> List[Dict[str, Any]]:
        """Извлечение документации из всех модулей"""
        modules = []

        for py_file in self.base_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue

            module_docs = self.extract_module_docs(py_file.name)
            if module_docs:
                modules.append(module_docs)

        return modules


class APIDocumentationGenerator:
    """Генерация API документации"""

    def __init__(self, api_file: str = "knowledge_os/app/rest_api.py"):
        self.api_file = api_file

    def generate_openapi_spec(self) -> Dict[str, Any]:
        """Генерация OpenAPI спецификации"""
        # FastAPI автоматически генерирует OpenAPI
        # Но мы можем создать расширенную версию
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "Knowledge OS REST API",
                "version": "1.0.0",
                "description": "REST API для интеграции с Knowledge OS",
            },
            "servers": [{"url": "http://localhost:8002", "description": "Development server"}],
            "paths": {
                "/": {
                    "get": {
                        "summary": "Root endpoint",
                        "responses": {"200": {"description": "API information"}},
                    }
                },
                "/health": {
                    "get": {
                        "summary": "Health check",
                        "responses": {"200": {"description": "System health status"}},
                    }
                },
                "/auth/login": {
                    "post": {
                        "summary": "User authentication",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "username": {"type": "string"},
                                            "password": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "Authentication successful",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "access_token": {"type": "string"},
                                                "token_type": {"type": "string"},
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    }
                },
            },
        }

    def generate_api_docs_markdown(self) -> str:
        """Генерация Markdown документации API"""
        spec = self.generate_openapi_spec()

        md = f"""# Knowledge OS REST API Documentation

**Версия:** {spec["info"]["version"]}
**Дата генерации:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Обзор

{spec["info"]["description"]}

## Базовый URL

- Development: `{spec["servers"][0]["url"]}`

## Аутентификация

Все защищенные endpoints требуют JWT токен в заголовке:

```
Authorization: Bearer <your_jwt_token>
```

## Endpoints

"""

        for path, methods in spec["paths"].items():
            for method, details in methods.items():
                md += f"### {method.upper()} {path}\n\n"
                md += f"**Описание:** {details.get('summary', 'N/A')}\n\n"

                if "requestBody" in details:
                    md += "**Request Body:**\n\n"
                    md += "```json\n"
                    md += json.dumps(details["requestBody"], indent=2)
                    md += "\n```\n\n"

                if "responses" in details:
                    md += "**Responses:**\n\n"
                    for status, response in details["responses"].items():
                        md += f"- `{status}`: {response.get('description', 'N/A')}\n"
                    md += "\n"

        return md


class UsageExamplesGenerator:
    """Генерация примеров использования"""

    def generate_python_examples(self) -> str:
        """Генерация примеров на Python"""
        return """# Примеры использования Knowledge OS

## 1. Аутентификация

```python
import httpx

async def login(username: str, password: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/auth/login",
            json={"username": username, "password": password}
        )
        return response.json()

# Использование
token_data = await login("user", "password")
token = token_data["access_token"]
```

## 2. Создание знания

```python
async def create_knowledge(content: str, domain: str, token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/knowledge",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": content,
                "domain": domain,
                "confidence_score": 0.95
            }
        )
        return response.json()
```

## 3. Поиск знаний

```python
async def search_knowledge(query: str, token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query, "limit": 10}
        )
        return response.json()
```

## 4. Использование MCP инструментов

```python
# В Cursor через MCP
from mcp import Client

client = Client("knowledge_os")

# Поиск знаний
results = await client.call_tool(
    "search_knowledge",
    {"query": "Python async", "limit": 5}
)

# Создание знания
await client.call_tool(
    "capture_knowledge",
    {
        "content": "Python async/await best practices",
        "domain": "python"
    }
)
```

## 5. Работа с графом знаний

```python
# Создание связи
await client.call_tool(
    "create_knowledge_link",
    {
        "source_id": "uuid-1",
        "target_id": "uuid-2",
        "link_type": "depends_on",
        "strength": 0.9
    }
)

# Получение связанных знаний
related = await client.call_tool(
    "get_related_knowledge",
    {
        "node_id": "uuid-1",
        "max_depth": 2
    }
)
```
"""

    def generate_curl_examples(self) -> str:
        """Генерация примеров с curl"""
        return """# Примеры использования через curl

## 1. Аутентификация

```bash
curl -X POST "http://localhost:8002/auth/login" \\
  -H "Content-Type: application/json" \\
  -d '{
    "username": "user",
    "password": "password"
  }'
```

## 2. Создание знания

```bash
curl -X POST "http://localhost:8002/knowledge" \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "Python async/await best practices",
    "domain": "python",
    "confidence_score": 0.95
  }'
```

## 3. Поиск знаний

```bash
curl -X POST "http://localhost:8002/search" \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "Python async",
    "limit": 10
  }'
```

## 4. Получение статистики

```bash
curl -X GET "http://localhost:8002/stats" \\
  -H "Authorization: Bearer <token>"
```
"""


class TutorialGenerator:
    """Генерация интерактивных туториалов"""

    def generate_tutorials(self) -> str:
        """Генерация туториалов"""
        return """# Интерактивные туториалы Knowledge OS

## Туториал 1: Первые шаги

### Шаг 1: Регистрация

```python
import httpx

async def register():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/auth/register",
            json={
                "username": "newuser",
                "password": "securepassword",
                "email": "user@example.com"
            }
        )
        print(response.json())
```

### Шаг 2: Вход

```python
async def login():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/auth/login",
            json={
                "username": "newuser",
                "password": "securepassword"
            }
        )
        token = response.json()["access_token"]
        return token
```

### Шаг 3: Создание первого знания

```python
async def create_first_knowledge(token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8002/knowledge",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": "Мое первое знание",
                "domain": "general",
                "confidence_score": 1.0
            }
        )
        print(response.json())
```

## Туториал 2: Работа с графом знаний

### Шаг 1: Создание знаний

```python
# Создаем несколько связанных знаний
knowledge1 = await create_knowledge(
    "Python основы",
    "python",
    token
)

knowledge2 = await create_knowledge(
    "Python async/await",
    "python",
    token
)
```

### Шаг 2: Создание связей

```python
# Связываем знания
await client.call_tool(
    "create_knowledge_link",
    {
        "source_id": knowledge2["id"],
        "target_id": knowledge1["id"],
        "link_type": "depends_on",
        "strength": 0.9
    }
)
```

### Шаг 3: Навигация по графу

```python
# Находим связанные знания
related = await client.call_tool(
    "get_related_knowledge",
    {
        "node_id": knowledge1["id"],
        "max_depth": 2
    }
)
```

## Туториал 3: Использование контекстной памяти

### Шаг 1: Поиск похожих паттернов

```python
patterns = await client.call_tool(
    "find_similar_patterns",
    {
        "query": "Как оптимизировать ML модель?",
        "pattern_type": "query_pattern",
        "min_success": 0.7
    }
)
```

### Шаг 2: Получение предпочтений пользователя

```python
preferences = await client.call_tool(
    "get_user_preferences",
    {
        "user_identifier": "user123"
    }
)
```

### Шаг 3: Прогнозирование потребностей

```python
predictions = await client.call_tool(
    "predict_user_needs",
    {
        "user_identifier": "user123",
        "recent_interactions": 10
    }
)
```
"""


class DocumentationGenerator:
    """Главный класс для генерации документации"""

    def __init__(self, output_dir: str = "docs/auto_generated"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.code_extractor = CodeDocumentationExtractor()
        self.api_generator = APIDocumentationGenerator()
        self.examples_generator = UsageExamplesGenerator()
        self.tutorial_generator = TutorialGenerator()

    def generate_all_docs(self) -> Dict[str, str]:
        """Генерация всей документации"""
        generated_files = {}

        # 1. Документация из кода
        logger.info("📝 Generating code documentation...")
        modules_docs = self.code_extractor.extract_all_modules()
        code_docs_path = self.output_dir / "code_documentation.md"
        with open(code_docs_path, "w", encoding="utf-8") as f:
            f.write(self._format_code_docs(modules_docs))
        generated_files["code_docs"] = str(code_docs_path)

        # 2. API документация
        logger.info("📝 Generating API documentation...")
        api_docs_path = self.output_dir / "api_documentation.md"
        with open(api_docs_path, "w", encoding="utf-8") as f:
            f.write(self.api_generator.generate_api_docs_markdown())
        generated_files["api_docs"] = str(api_docs_path)

        # 3. Примеры использования
        logger.info("📝 Generating usage examples...")
        examples_path = self.output_dir / "usage_examples.md"
        with open(examples_path, "w", encoding="utf-8") as f:
            f.write(self.examples_generator.generate_python_examples())
            f.write("\n\n")
            f.write(self.examples_generator.generate_curl_examples())
        generated_files["examples"] = str(examples_path)

        # 4. Туториалы
        logger.info("📝 Generating tutorials...")
        tutorials_path = self.output_dir / "tutorials.md"
        with open(tutorials_path, "w", encoding="utf-8") as f:
            f.write(self.tutorial_generator.generate_tutorials())
        generated_files["tutorials"] = str(tutorials_path)

        # 5. Индекс документации
        index_path = self.output_dir / "README.md"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(self._generate_index(generated_files))
        generated_files["index"] = str(index_path)

        logger.info(f"✅ Generated {len(generated_files)} documentation files")
        return generated_files

    def _format_code_docs(self, modules: List[Dict[str, Any]]) -> str:
        """Форматирование документации кода"""
        md = "# Документация кода Knowledge OS\n\n"
        md += f"**Дата генерации:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        for module in modules:
            md += f"## {module['module']}\n\n"

            if module["module_doc"]:
                md += f"{module['module_doc']}\n\n"

            if module["classes"]:
                md += "### Классы\n\n"
                for cls in module["classes"]:
                    md += f"#### {cls['name']}\n\n"
                    if cls["docstring"]:
                        md += f"{cls['docstring']}\n\n"

                    if cls["methods"]:
                        md += "**Методы:**\n\n"
                        for method in cls["methods"]:
                            md += f"- `{method['name']}({', '.join(method['args'])})`\n"
                            if method["docstring"]:
                                md += f"  - {method['docstring'][:100]}...\n"
                        md += "\n"

            if module["functions"]:
                md += "### Функции\n\n"
                for func in module["functions"]:
                    md += f"#### {func['name']}\n\n"
                    if func["docstring"]:
                        md += f"{func['docstring']}\n\n"
                    md += f"**Параметры:** `{', '.join(func['args'])}`\n\n"

        return md

    def _generate_index(self, files: Dict[str, str]) -> str:
        """Генерация индекса документации"""
        md = "# Knowledge OS - Автогенерированная документация\n\n"
        md += f"**Дата генерации:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += "## Содержание\n\n"

        md += "- [Документация кода](code_documentation.md)\n"
        md += "- [API документация](api_documentation.md)\n"
        md += "- [Примеры использования](usage_examples.md)\n"
        md += "- [Туториалы](tutorials.md)\n"

        md += "\n## Быстрый старт\n\n"
        md += "1. Прочитайте [Туториалы](tutorials.md) для начала работы\n"
        md += "2. Изучите [Примеры использования](usage_examples.md)\n"
        md += "3. Ознакомьтесь с [API документацией](api_documentation.md)\n"
        md += "4. Изучите [Документацию кода](code_documentation.md) для деталей реализации\n"

        return md


if __name__ == "__main__":
    generator = DocumentationGenerator()
    files = generator.generate_all_docs()
    print(f"✅ Documentation generated in {len(files)} files:")
    for name, path in files.items():
        print(f"  - {name}: {path}")
