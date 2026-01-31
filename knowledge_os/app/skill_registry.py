"""
Skill Registry - Реестр всех skills с метаданными
Основано на Agent Skills Framework (Anthropic) и Clawdbot patterns
Поддерживает SKILL.md формат с YAML frontmatter
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class SkillSource(Enum):
    """Источник skill"""
    BUILTIN = "builtin"  # Встроенные skills
    MANAGED = "managed"  # Установленные пользователем
    WORKSPACE = "workspace"  # Проектные skills
    DYNAMIC = "dynamic"  # Динамически созданные
    DISCOVERED = "discovered"  # Найденные через Skill Discovery


@dataclass
class SkillMetadata:
    """Метаданные skill (AgentSkills формат)"""
    name: str
    description: str
    category: Optional[str] = None
    version: str = "1.0.0"
    author: Optional[str] = None
    homepage: Optional[str] = None
    requires: Optional[Dict[str, Any]] = None  # bins, env, config
    emoji: Optional[str] = None
    user_invocable: bool = True
    disable_model_invocation: bool = False
    command_dispatch: Optional[str] = None
    command_tool: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Skill:
    """Skill в реестре"""
    name: str
    description: str
    category: str
    handler: Optional[Callable] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: SkillSource = SkillSource.BUILTIN
    metadata: SkillMetadata = field(default_factory=lambda: SkillMetadata(name="", description=""))
    skill_path: Optional[str] = None  # Путь к SKILL.md файлу
    instructions: str = ""  # Инструкции из SKILL.md
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для сериализации"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "source": self.source.value,
            "skill_path": self.skill_path,
            "metadata": self.metadata.to_dict(),
            "created_at": self.created_at.isoformat(),
            "parameters": self.parameters,
            "examples": self.examples
        }


class SkillRegistry:
    """
    Skill Registry - реестр всех skills
    
    Основано на:
    - Agent Skills Framework (Anthropic) - SKILL.md формат
    - Clawdbot patterns - локации skills, gating, metadata
    
    Локации skills (как в Clawdbot):
    1. Bundled skills: knowledge_os/app/skills/ (встроенные)
    2. Managed skills: ~/.atra/skills/ (установленные пользователем)
    3. Workspace skills: <workspace>/skills/ (проектные)
    4. Extra dirs: конфигурируемые дополнительные папки
    """
    
    def __init__(
        self,
        bundled_skills_dir: Optional[str] = None,
        managed_skills_dir: Optional[str] = None,
        workspace_skills_dir: Optional[str] = None,
        extra_dirs: Optional[List[str]] = None
    ):
        """
        Инициализация Skill Registry
        
        Args:
            bundled_skills_dir: Директория bundled skills
            managed_skills_dir: Директория managed skills
            workspace_skills_dir: Директория workspace skills
            extra_dirs: Дополнительные директории
        """
        # Определяем пути по умолчанию
        if bundled_skills_dir is None:
            # Путь относительно knowledge_os/app/skill_registry.py
            current_dir = os.path.dirname(__file__)
            bundled_skills_dir = os.path.join(current_dir, "skills")
        
        if managed_skills_dir is None:
            managed_skills_dir = os.path.expanduser("~/.atra/skills")
        
        self.bundled_skills_dir = Path(bundled_skills_dir)
        self.managed_skills_dir = Path(managed_skills_dir)
        self.workspace_skills_dir = Path(workspace_skills_dir) if workspace_skills_dir else None
        self.extra_dirs = [Path(d) for d in (extra_dirs or [])]
        
        self.skills: Dict[str, Skill] = {}
        self.skills_by_category: Dict[str, List[Skill]] = {}
        
        logger.info(f"✅ Skill Registry инициализирован")
        logger.info(f"   Bundled: {self.bundled_skills_dir}")
        logger.info(f"   Managed: {self.managed_skills_dir}")
        if self.workspace_skills_dir:
            logger.info(f"   Workspace: {self.workspace_skills_dir}")
    
    def _parse_skill_metadata(self, skill_path: Path) -> Optional[SkillMetadata]:
        """Парсить метаданные из SKILL.md (AgentSkills формат)"""
        skill_file = skill_path / "SKILL.md"
        if not skill_file.exists():
            return None
        
        try:
            content = skill_file.read_text(encoding="utf-8")
            
            # Парсим YAML frontmatter
            if not content.startswith("---"):
                logger.warning(f"⚠️ SKILL.md не начинается с YAML frontmatter: {skill_path}")
                return None
            
            # Извлекаем frontmatter
            parts = content.split("---", 2)
            if len(parts) < 3:
                logger.warning(f"⚠️ Неверный формат SKILL.md: {skill_path}")
                return None
            
            frontmatter = parts[1].strip()
            instructions = parts[2].strip()
            
            # Парсим YAML (простой парсинг, можно улучшить с помощью PyYAML)
            metadata_dict = {}
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    # Парсим metadata JSON если есть
                    if key == "metadata":
                        try:
                            metadata_dict["metadata_json"] = json.loads(value)
                        except:
                            pass
                    else:
                        metadata_dict[key] = value
            
            # Извлекаем данные
            name = metadata_dict.get("name", skill_path.name)
            description = metadata_dict.get("description", "")
            
            # Парсим metadata JSON если есть
            metadata_json = metadata_dict.get("metadata_json", {})
            clawdbot_meta = metadata_json.get("clawdbot", {})
            
            requires = clawdbot_meta.get("requires", {})
            
            return SkillMetadata(
                name=name,
                description=description,
                category=metadata_dict.get("category"),
                version=metadata_dict.get("version", "1.0.0"),
                author=metadata_dict.get("author"),
                homepage=clawdbot_meta.get("homepage") or metadata_dict.get("homepage"),
                requires=requires if requires else None,
                emoji=clawdbot_meta.get("emoji"),
                user_invocable=metadata_dict.get("user-invocable", "true").lower() == "true",
                disable_model_invocation=metadata_dict.get("disable-model-invocation", "false").lower() == "true",
                command_dispatch=metadata_dict.get("command-dispatch"),
                command_tool=metadata_dict.get("command-tool")
            )
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга SKILL.md {skill_path}: {e}")
            return None
    
    def _check_gating(self, metadata: SkillMetadata) -> bool:
        """Проверить gating на основе метаданных (Clawdbot pattern)"""
        if not metadata.requires:
            return True  # Нет требований - всегда eligible
        
        requires = metadata.requires
        
        # Проверка bins
        if "bins" in requires:
            bins = requires["bins"]
            if isinstance(bins, list):
                for bin_name in bins:
                    if not self._check_bin_exists(bin_name):
                        logger.debug(f"⚠️ Skill {metadata.name} требует bin: {bin_name} (не найден)")
                        return False
        
        # Проверка env
        if "env" in requires:
            env_vars = requires["env"]
            if isinstance(env_vars, list):
                for env_var in env_vars:
                    if not os.getenv(env_var):
                        logger.debug(f"⚠️ Skill {metadata.name} требует env: {env_var} (не установлен)")
                        return False
        
        # Проверка config (пока пропускаем, нужно интегрировать с config системой)
        
        return True
    
    def _check_bin_exists(self, bin_name: str) -> bool:
        """Проверить существование бинарника в PATH"""
        import shutil
        return shutil.which(bin_name) is not None
    
    def _load_skill_from_directory(self, skill_dir: Path, source: SkillSource) -> Optional[Skill]:
        """Загрузить skill из директории"""
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return None
        
        metadata = self._parse_skill_metadata(skill_dir)
        if not metadata:
            return None
        
        # Проверяем gating
        if not self._check_gating(metadata):
            logger.debug(f"⚠️ Skill {metadata.name} не прошел gating, пропускаем")
            return None
        
        # Читаем инструкции
        try:
            content = skill_file.read_text(encoding="utf-8")
            parts = content.split("---", 2)
            instructions = parts[2].strip() if len(parts) >= 3 else ""
        except Exception as e:
            logger.error(f"❌ Ошибка чтения инструкций: {e}")
            instructions = ""
        
        skill = Skill(
            name=metadata.name,
            description=metadata.description,
            category=metadata.category or "general",
            version=metadata.version,
            source=source,
            metadata=metadata,
            skill_path=str(skill_dir),
            instructions=instructions
        )
        
        return skill
    
    def load_skills(self):
        """Загрузить все skills из всех локаций"""
        self.skills.clear()
        self.skills_by_category.clear()
        
        # Загружаем из всех локаций (в порядке приоритета)
        locations = [
            (self.workspace_skills_dir, SkillSource.WORKSPACE),
            (self.managed_skills_dir, SkillSource.MANAGED),
            (self.bundled_skills_dir, SkillSource.BUILTIN),
        ]
        
        # Добавляем extra dirs
        for extra_dir in self.extra_dirs:
            locations.append((extra_dir, SkillSource.MANAGED))
        
        for skills_dir, source in locations:
            if not skills_dir or not skills_dir.exists():
                continue
            
            logger.info(f"📂 Загрузка skills из: {skills_dir}")
            
            # Ищем поддиректории с SKILL.md
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill = self._load_skill_from_directory(skill_dir, source)
                    if skill:
                        # Workspace skills имеют приоритет
                        if skill.name not in self.skills or source == SkillSource.WORKSPACE:
                            self.skills[skill.name] = skill
                            
                            # Добавляем в категории
                            category = skill.category
                            if category not in self.skills_by_category:
                                self.skills_by_category[category] = []
                            self.skills_by_category[category].append(skill)
                            
                            logger.info(f"✅ Skill загружен: {skill.name} ({source.value})")
        
        logger.info(f"📊 Всего загружено skills: {len(self.skills)}")
    
    def register_skill(self, skill: Skill):
        """Зарегистрировать skill вручную"""
        self.skills[skill.name] = skill
        
        # Добавляем в категории
        category = skill.category
        if category not in self.skills_by_category:
            self.skills_by_category[category] = []
        self.skills_by_category[category].append(skill)
        
        logger.info(f"✅ Skill зарегистрирован: {skill.name}")
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Получить skill по имени"""
        return self.skills.get(name)
    
    def get_skills_by_category(self, category: str) -> List[Skill]:
        """Получить skills по категории"""
        return self.skills_by_category.get(category, [])
    
    def list_skills(self, category: Optional[str] = None) -> List[Skill]:
        """Список всех skills"""
        if category:
            return self.get_skills_by_category(category)
        return list(self.skills.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику реестра"""
        return {
            "total_skills": len(self.skills),
            "by_source": {
                source.value: sum(1 for s in self.skills.values() if s.source == source)
                for source in SkillSource
            },
            "by_category": {
                cat: len(skills) for cat, skills in self.skills_by_category.items()
            }
        }


# Глобальный экземпляр Skill Registry
_global_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Получить глобальный Skill Registry"""
    global _global_skill_registry
    if _global_skill_registry is None:
        _global_skill_registry = SkillRegistry()
        _global_skill_registry.load_skills()
    return _global_skill_registry


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    registry = get_skill_registry()
    print(f"\n📊 Статистика: {registry.get_stats()}")
    print(f"\n📋 Skills:")
    for skill in registry.list_skills():
        print(f"  - {skill.name}: {skill.description} ({skill.source.value})")
