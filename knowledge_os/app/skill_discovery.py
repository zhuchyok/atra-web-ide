"""
Skill Discovery - Поиск библиотек/API и генерация новых skills
Основано на ClawdHub и Agent Skills Framework
Интегрируется с базой знаний для сохранения найденных skills
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from app.event_bus import Event, EventType, get_event_bus
except ImportError:
    from event_bus import Event, EventType, get_event_bus
from app.skill_registry import Skill, SkillMetadata, SkillRegistry, SkillSource, get_skill_registry

logger = logging.getLogger(__name__)


class SkillDiscovery:
    """
    Skill Discovery - поиск и создание новых skills

    Основано на:
    - ClawdHub patterns - поиск библиотек и API
    - Agent Skills Framework - генерация SKILL.md
    - Интеграция с базой знаний - сохранение найденных skills
    """

    def __init__(self, skill_registry: Optional[SkillRegistry] = None):
        """
        Инициализация Skill Discovery

        Args:
            skill_registry: Экземпляр Skill Registry
        """
        self.skill_registry = skill_registry or get_skill_registry()
        self.event_bus = get_event_bus()
        self.db_connection = None

        logger.info("✅ Skill Discovery инициализирован")

    async def _get_db_connection(self):
        """Получить подключение к БД для сохранения skills"""
        if self.db_connection is None:
            try:
                import asyncpg

                db_url = os.getenv(
                    "DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os"
                )
                self.db_connection = await asyncpg.connect(db_url)
            except ImportError:
                logger.debug(
                    "ℹ️ asyncpg не установлен, skills не будут сохраняться в БД (используем fallback)"
                )
                return None
            except Exception as e:
                logger.warning(f"⚠️ Ошибка подключения к БД: {e}")
                return None

        return self.db_connection

    async def _search_pypi(self, query: str) -> List[Dict[str, Any]]:
        """Поиск библиотек в PyPI"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://pypi.org/pypi/{query}/json", follow_redirects=True
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {
                            "name": data.get("info", {}).get("name"),
                            "version": data.get("info", {}).get("version"),
                            "description": data.get("info", {}).get("summary", ""),
                            "home_page": data.get("info", {}).get("home_page"),
                            "project_urls": data.get("info", {}).get("project_urls", {}),
                        }
                    ]
        except httpx.HTTPStatusError:
            # Пробуем поиск через поисковый API PyPI
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"https://pypi.org/search/?q={query}", follow_redirects=True
                    )
                    # Парсим результаты поиска (упрощенный вариант)
                    # В реальности нужен более сложный парсинг
                    pass
            except Exception as e:
                logger.debug(f"Ошибка поиска в PyPI: {e}")
        except Exception as e:
            logger.debug(f"Ошибка поиска в PyPI: {e}")

        return []

    async def _search_api_docs(self, api_name: str) -> Optional[Dict[str, Any]]:
        """Поиск документации API"""
        # Популярные API для поиска
        api_patterns = {
            "gmail": {
                "docs_url": "https://developers.google.com/gmail/api",
                "library": "google-api-python-client",
            },
            "github": {"docs_url": "https://docs.github.com/en/rest", "library": "PyGithub"},
            "slack": {"docs_url": "https://api.slack.com", "library": "slack-sdk"},
            "discord": {"docs_url": "https://discord.com/developers/docs", "library": "discord.py"},
        }

        api_name_lower = api_name.lower()
        for key, info in api_patterns.items():
            if key in api_name_lower:
                return info

        return None

    async def _generate_skill_md(
        self,
        skill_name: str,
        description: str,
        library_info: Dict[str, Any],
        api_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Генерировать SKILL.md файл в формате AgentSkills"""
        # Определяем зависимости
        requires = {}
        if library_info.get("library"):
            requires["bins"] = ["python", "pip"]

        if api_info and api_info.get("library"):
            requires["bins"] = requires.get("bins", []) + ["pip"]
            requires["env"] = [f"{skill_name.upper().replace('-', '_')}_API_KEY"]

        metadata_json = json.dumps(
            {
                "clawdbot": {
                    "requires": requires if requires else None,
                    "homepage": library_info.get("home_page")
                    or (api_info.get("docs_url") if api_info else None),
                }
            }
        )

        # Генерируем инструкции
        instructions = f"""# {skill_name}

{description}

## Использование

Этот skill позволяет работать с {library_info.get("name", skill_name)}.

"""

        if api_info:
            instructions += f"""
## API Документация

- Документация: {api_info.get("docs_url", "N/A")}
- Библиотека: {api_info.get("library", "N/A")}

## Настройка

1. Установите библиотеку: `pip install {api_info.get("library", "")}`
2. Получите API ключ
3. Установите переменную окружения: `{skill_name.upper().replace("-", "_")}_API_KEY=your_key`

"""
        else:
            instructions += f"""
## Установка

```bash
pip install {library_info.get("name", skill_name)}
```

"""

        instructions += """
## Примеры использования

[Добавьте примеры использования skill]

"""

        # Формируем полный SKILL.md
        skill_md = f"""---
name: {skill_name}
description: {description}
version: 1.0.0
metadata: {metadata_json}
---

{instructions}
"""

        return skill_md

    async def _generate_skill_handler(
        self,
        skill_name: str,
        library_info: Dict[str, Any],
        api_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Генерировать Python код для skill handler"""
        library_name = library_info.get("library") or library_info.get("name", skill_name)
        # Инжект вызова библиотеки при наличии api_info.function (реализация логики skill)
        injected_logic = ""
        if api_info and api_info.get("function"):
            func_name = api_info.get("function")
            lib_mod = (api_info.get("library") or library_name).replace("-", "_")
            injected_logic = f'''
        import importlib
        import asyncio
        mod = importlib.import_module("{lib_mod}")
        fn = getattr(mod, "{func_name}", None)
        if callable(fn):
            result = await fn(**kwargs) if asyncio.iscoroutinefunction(fn) else fn(**kwargs)
            return {{"success": True, "result": result}}
        return {{"success": False, "error": "Функция {func_name} не найдена или не callable", "skill": "{skill_name}"}}
'''
        # Страховка: при отсутствии api_info.function — ищем стандартные точки входа (run/execute/skill_handler)
        lib_mod = (api_info.get("library") if api_info else None) or library_name
        lib_mod = lib_mod.replace("-", "_")
        fallback_logic = f'''
        import importlib
        import asyncio
        _mod = importlib.import_module("{lib_mod}")
        for _entry in ("skill_handler", "run", "execute"):
            _fn = getattr(_mod, _entry, None)
            if callable(_fn):
                _res = await _fn(**kwargs) if asyncio.iscoroutinefunction(_fn) else _fn(**kwargs)
                return {{"success": True, "result": _res}}
        return {{"success": False, "error": "Нет точки входа (skill_handler/run/execute). Задайте api_info.function при генерации.", "skill": "{skill_name}"}}
'''
        handler_code = f'''"""
Skill Handler для {skill_name}
Автоматически сгенерирован Skill Discovery
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Импорт библиотеки
try:
'''

        if api_info and api_info.get("library"):
            handler_code += f"    import {api_info['library'].replace('-', '_')}\n"
        else:
            handler_code += f"    import {library_name.replace('-', '_')}\n"

        handler_code += '''    LIBRARY_AVAILABLE = True
except ImportError:
    LIBRARY_AVAILABLE = False
    logger.warning(f"⚠️ Библиотека {library_name} не установлена")


async def skill_handler(**kwargs) -> Dict[str, Any]:
    """
    Обработчик skill {skill_name}

    Args:
        **kwargs: Параметры skill

    Returns:
        Результат выполнения
    """
    if not LIBRARY_AVAILABLE:
        return {{
            "success": False,
            "error": f"Библиотека {library_name} не установлена. Установите: pip install {library_name}"
        }}

    try:
        # Логика: api_info.function → вызов указанной функции; иначе — поиск стандартных точек входа (run/execute/skill_handler)
        {injected_logic if injected_logic else fallback_logic}
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения skill {skill_name}: {{e}}")
        return {{
            "success": False,
            "error": str(e)
        }}
'''

        return handler_code

    async def _save_skill_to_db(self, skill: Skill):
        """Сохранить skill в базу знаний"""
        conn = await self._get_db_connection()
        if not conn:
            return

        try:
            # Сохраняем информацию о skill в knowledge_nodes
            skill_content = f"""
Skill: {skill.name}
Description: {skill.description}
Category: {skill.category}
Version: {skill.version}
Source: {skill.source.value}
Path: {skill.skill_path}

Instructions:
{skill.instructions[:1000]}

Metadata:
{json.dumps(skill.metadata.to_dict(), indent=2)}
"""

            # Ищем или создаем domain для skills
            domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'skills' LIMIT 1")

            if not domain_id:
                domain_id = await conn.fetchval(
                    "INSERT INTO domains (name, description) VALUES ('skills', 'Skills registry') RETURNING id"
                )

            # Сохраняем в knowledge_nodes (по возможности с embedding — VERIFICATION §5)
            meta_kn = json.dumps(
                {
                    "type": "skill",
                    "skill_name": skill.name,
                    "skill_version": skill.version,
                    "skill_source": skill.source.value,
                    "skill_path": skill.skill_path,
                }
            )
            embedding = None
            try:
                from semantic_cache import get_embedding

                embedding = await get_embedding(skill_content[:8000])
            except Exception:
                pass
            if embedding is not None:
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (content, domain_id, metadata, confidence_score, embedding)
                    VALUES ($1, $2, $3, 0.9, $4::vector)
                    ON CONFLICT DO NOTHING
                """,
                    skill_content,
                    domain_id,
                    meta_kn,
                    str(embedding),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (content, domain_id, metadata, confidence_score)
                    VALUES ($1, $2, $3, 0.9)
                    ON CONFLICT DO NOTHING
                """,
                    skill_content,
                    domain_id,
                    meta_kn,
                )

            logger.info(f"💾 Skill сохранен в базу знаний: {skill.name}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения skill в БД: {e}")

    async def discover_skill(
        self, skill_description: str, task_context: Optional[str] = None
    ) -> Optional[Skill]:
        """
        Найти и создать skill на основе описания

        Args:
            skill_description: Описание нужного skill
            task_context: Контекст задачи

        Returns:
            Созданный skill или None
        """
        logger.info(f"🔍 Поиск skill: {skill_description}")

        # Извлекаем ключевые слова для поиска
        keywords = self._extract_keywords(skill_description)

        # Ищем библиотеку в PyPI
        library_info = None
        for keyword in keywords:
            results = await self._search_pypi(keyword)
            if results:
                library_info = results[0]
                break

        # Ищем API документацию
        api_info = None
        for keyword in keywords:
            api_info = await self._search_api_docs(keyword)
            if api_info:
                break

        if not library_info and not api_info:
            logger.warning(f"⚠️ Не найдено библиотек/API для: {skill_description}")
            return None

        # Генерируем имя skill
        skill_name = self._generate_skill_name(skill_description, library_info, api_info)

        # Генерируем описание
        description = skill_description
        if library_info:
            description = library_info.get("description", description)

        # Генерируем SKILL.md
        skill_md = await self._generate_skill_md(
            skill_name, description, library_info or {}, api_info
        )

        # Генерируем handler
        handler_code = await self._generate_skill_handler(skill_name, library_info or {}, api_info)

        # Создаем директорию skill
        skill_dir = Path(self.skill_registry.managed_skills_dir) / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Сохраняем SKILL.md
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

        # Сохраняем handler
        (skill_dir / "handler.py").write_text(handler_code, encoding="utf-8")

        logger.info(f"✅ Skill создан: {skill_name} в {skill_dir}")

        # Загружаем skill в реестр
        skill = self.skill_registry._load_skill_from_directory(skill_dir, SkillSource.DISCOVERED)

        if skill:
            # Регистрируем skill
            self.skill_registry.register_skill(skill)

            # Сохраняем в базу знаний
            await self._save_skill_to_db(skill)

            # Публикуем событие
            event = Event(
                event_id=f"skill_discovered_{skill_name}",
                event_type=EventType.SKILL_ADDED,
                payload={
                    "skill_name": skill.name,
                    "skill_description": skill.description,
                    "skill_source": "discovered",
                    "skill_path": str(skill_dir),
                },
                source="skill_discovery",
            )
            await self.event_bus.publish(event)

            logger.info(f"🎉 Skill обнаружен и добавлен: {skill_name}")
            return skill

        return None

    def _extract_keywords(self, description: str) -> List[str]:
        """Извлечь ключевые слова из описания"""
        # Удаляем стоп-слова
        stop_words = {"для", "через", "с", "используя", "api", "библиотека", "skill"}

        words = re.findall(r"\b\w+\b", description.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 3]

        return keywords[:5]  # Берем первые 5 ключевых слов

    def _generate_skill_name(
        self, description: str, library_info: Optional[Dict], api_info: Optional[Dict]
    ) -> str:
        """Генерировать имя skill"""
        if api_info and api_info.get("library"):
            # Используем имя библиотеки
            name = api_info["library"].replace("_", "-").lower()
        elif library_info and library_info.get("name"):
            name = library_info["name"].replace("_", "-").lower()
        else:
            # Генерируем из описания
            keywords = self._extract_keywords(description)
            name = "-".join(keywords[:2]) if keywords else "custom-skill"

        # Очищаем имя
        name = re.sub(r"[^a-z0-9-]", "", name)
        return name

    async def handle_skill_needed_event(self, event: Event):
        """Обработчик события SKILL_NEEDED"""
        skill_description = event.payload.get("skill_description") or event.payload.get(
            "skill_name", ""
        )
        task_context = event.payload.get("task_context")

        if not skill_description:
            logger.warning("⚠️ Событие SKILL_NEEDED без описания skill")
            return

        # Запускаем discovery
        skill = await self.discover_skill(skill_description, task_context)

        if skill:
            logger.info(f"✅ Skill успешно создан: {skill.name}")
        else:
            logger.warning(f"⚠️ Не удалось создать skill для: {skill_description}")


async def main():
    """Пример использования"""
    import logging

    logging.basicConfig(level=logging.INFO)

    # Инициализируем Event Bus
    event_bus = get_event_bus()
    await event_bus.start()

    # Создаем Skill Discovery
    discovery = SkillDiscovery()

    # Подписываемся на события
    event_bus.subscribe(EventType.SKILL_NEEDED, discovery.handle_skill_needed_event)

    # Пример: поиск skill для Gmail API
    skill = await discovery.discover_skill("отправка email через Gmail API")

    if skill:
        print(f"✅ Skill создан: {skill.name}")
        print(f"   Описание: {skill.description}")
        print(f"   Путь: {skill.skill_path}")

    await event_bus.stop()


if __name__ == "__main__":
    asyncio.run(main())
