"""
Organizational Structure System - Динамическая организационная структура
Отделы → Департаменты → Сотрудники
Все уровни знают структуру, количество сотрудников может меняться
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OrganizationalUnit:
    """Организационная единица (отдел, департамент, команда)"""

    id: int
    name: str
    level: str  # 'department', 'subdepartment', 'team'
    parent_id: Optional[int]
    manager_id: Optional[int]
    manager_name: Optional[str] = None
    children: List["OrganizationalUnit"] = None
    employees: List[Dict] = None  # Сотрудники этой единицы

    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.employees is None:
            self.employees = []


@dataclass
class Employee:
    """Сотрудник"""

    id: int
    name: str
    role: str
    department: str
    organizational_unit_id: Optional[int]
    is_manager: bool
    manages_unit_id: Optional[int]
    system_prompt: Optional[str] = None


class OrganizationalStructure:
    """
    Система организационной структуры
    Динамически получает структуру из БД, все уровни знают структуру
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url
        self._structure_cache: Optional[Dict] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 60  # 1 минута - корпорация растет, нужны актуальные данные
        self._last_expert_count: Optional[int] = None
        self._last_department_count: Optional[int] = None

    async def get_full_structure(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Получить полную структуру организации
        Автоматически отслеживает изменения в БД (корпорация растет и развивается)
        Кэшируется на 1 минуту, но проверяет изменения в БД

        Returns:
            Структура: {
                "departments": [
                    {
                        "id": 1,
                        "name": "Backend",
                        "manager": {"id": 1, "name": "Игорь"},
                        "subdepartments": [
                            {
                                "id": 2,
                                "name": "API Development",
                                "manager": {"id": 1, "name": "Игорь"},
                                "employees": [...]
                            }
                        ],
                        "employees": [...]
                    }
                ]
            }
        """
        # Проверяем изменения в БД (корпорация растет!)
        if not force_refresh and self._structure_cache and ASYNCPG_AVAILABLE and self.db_url:
            try:
                # Быстрая проверка: изменилось ли количество экспертов или отделов?
                # Используем пул соединений вместо прямого подключения
                if not hasattr(self, "_quick_check_pool") or self._quick_check_pool is None:
                    self._quick_check_pool = await asyncpg.create_pool(
                        self.db_url,
                        min_size=1,
                        max_size=2,
                        max_inactive_connection_lifetime=60,
                        command_timeout=10,
                    )
                try:
                    async with self._quick_check_pool.acquire() as conn:
                        current_expert_count = await conn.fetchval("SELECT COUNT(*) FROM experts")
                        current_dept_count = await conn.fetchval(
                            "SELECT COUNT(DISTINCT COALESCE(department, 'General')) FROM experts"
                        )
                except Exception as pool_error:
                    logger.debug(f"Ошибка пула быстрой проверки: {pool_error}, используем кэш")
                    return self._structure_cache

                # Если количество изменилось - принудительно обновляем
                if self._last_expert_count is not None and (
                    current_expert_count != self._last_expert_count
                    or current_dept_count != self._last_department_count
                ):
                    logger.info(
                        f"🔄 Обнаружены изменения в структуре: экспертов {self._last_expert_count} → {current_expert_count}, отделов {self._last_department_count} → {current_dept_count}"
                    )
                    force_refresh = True

                # Сохраняем текущие значения для следующей проверки
                self._last_expert_count = current_expert_count
                self._last_department_count = current_dept_count
            except Exception as e:
                logger.debug(f"ℹ️ Не удалось проверить изменения в БД: {e}, используем кэш")

        # Проверяем кэш (только если не было изменений)
        if not force_refresh and self._structure_cache:
            if self._cache_timestamp:
                age = (datetime.now() - self._cache_timestamp).total_seconds()
                if age < self._cache_ttl:
                    logger.debug(f"✅ Используем кэшированную структуру (возраст: {age:.1f}с)")
                    return self._structure_cache

        if not ASYNCPG_AVAILABLE or not self.db_url:
            # Логируем только один раз при первом использовании
            if not hasattr(self, "_db_warning_logged"):
                logger.debug("ℹ️ asyncpg или DATABASE_URL недоступны, используем fallback структуру")
                self._db_warning_logged = True
            return self._get_fallback_structure()

        try:
            logger.info("🔍 Получаю полную структуру организации из БД...")
            # Используем пул соединений вместо прямого подключения
            if not hasattr(self, "_structure_pool") or self._structure_pool is None:
                self._structure_pool = await asyncpg.create_pool(
                    self.db_url,
                    min_size=1,
                    max_size=3,
                    max_inactive_connection_lifetime=300,
                    command_timeout=30,
                )
            try:
                async with self._structure_pool.acquire() as conn:
                    # Получаем все отделы/департаменты из experts
                    # ВАЖНО: Включаем экспертов без отдела в отдел "General"
                    departments_query = """
                        SELECT DISTINCT COALESCE(department, 'General') as department
                        FROM experts
                        ORDER BY department
                    """
                    departments = await conn.fetch(departments_query)

                    structure = {
                        "departments": [],
                        "total_employees": 0,
                        "total_departments": 0,
                        "updated_at": datetime.now().isoformat(),
                    }

                    for dept_row in departments:
                        dept_name = dept_row["department"]

                        # Получаем сотрудников отдела (колонки organizational_unit_id, is_manager, manages_unit_id — из миграции add_experts_organizational_columns.sql)
                        if dept_name == "General":
                            employees_query = """
                                SELECT id, name, role, department, system_prompt,
                                       COALESCE(organizational_unit_id, 0) as organizational_unit_id,
                                       COALESCE(is_manager, FALSE) as is_manager,
                                       COALESCE(manages_unit_id, 0) as manages_unit_id
                                FROM experts
                                WHERE department IS NULL
                                ORDER BY is_manager DESC, name
                            """
                            employees = await conn.fetch(employees_query)
                        else:
                            employees_query = """
                                SELECT id, name, role, department, system_prompt,
                                       COALESCE(organizational_unit_id, 0) as organizational_unit_id,
                                       COALESCE(is_manager, FALSE) as is_manager,
                                       COALESCE(manages_unit_id, 0) as manages_unit_id
                                FROM experts
                                WHERE department = $1
                                ORDER BY is_manager DESC, name
                            """
                            employees = await conn.fetch(employees_query, dept_name)
                        employees = [dict(r) for r in employees]

                        # Находим управляющего (Department Head)
                        manager = None
                        for emp in employees:
                            if emp["is_manager"] or emp["name"] in [
                                "Игорь",
                                "Дмитрий",
                                "Сергей",
                                "Мария",
                                "Максим",
                            ]:
                                manager = {
                                    "id": emp["id"],
                                    "name": emp["name"],
                                    "role": emp["role"],
                                }
                                break

                        # Если нет явного менеджера, берем первого
                        if not manager and employees:
                            first_emp = employees[0]
                            manager = {
                                "id": first_emp["id"],
                                "name": first_emp["name"],
                                "role": first_emp["role"],
                            }

                        # Группируем сотрудников по подразделениям
                        employees_list = [
                            {
                                "id": emp["id"],
                                "name": emp["name"],
                                "role": emp["role"],
                                "is_manager": emp["is_manager"],
                                "organizational_unit_id": emp["organizational_unit_id"],
                                "system_prompt": emp["system_prompt"],
                            }
                            for emp in employees
                        ]

                        dept_structure = {
                            "id": dept_name,  # Используем имя как ID
                            "name": dept_name,
                            "manager": manager,
                            "employees": employees_list,
                            "employee_count": len(employees_list),
                            "subdepartments": [],  # Пока не используем, но структура готова
                        }

                        structure["departments"].append(dept_structure)
                        structure["total_employees"] += len(employees_list)

                    structure["total_departments"] = len(structure["departments"])

                    # Обновляем кэш и счетчики
                    self._structure_cache = structure
                    self._cache_timestamp = datetime.now()
                    self._last_expert_count = structure["total_employees"]
                    self._last_department_count = structure["total_departments"]

                    logger.info(
                        f"✅ Структура обновлена: {structure['total_departments']} отделов, {structure['total_employees']} сотрудников (корпорация растет!)"
                    )
                    return structure
            except Exception as pool_error:
                err_msg = str(pool_error)
                if (
                    "organizational_unit_id" in err_msg
                    or "is_manager" in err_msg
                    or "manages_unit_id" in err_msg
                ):
                    logger.error(
                        "❌ В таблице experts отсутствуют колонки организационной структуры. "
                        "Примените миграцию: db/migrations/add_experts_organizational_columns.sql "
                        "или запустите Enhanced Orchestrator один раз (он применит все миграции)."
                    )
                    raise RuntimeError(
                        "Схема experts устарела: нужны колонки organizational_unit_id, is_manager, manages_unit_id. "
                        "Выполните: psql -f knowledge_os/db/migrations/add_experts_organizational_columns.sql "
                        "или запустите Enhanced Orchestrator."
                    ) from pool_error
                logger.warning(f"⚠️ Ошибка пула структуры: {pool_error}, используем fallback")
                return self._get_fallback_structure()
        except Exception as e:
            logger.error(f"❌ Ошибка получения структуры: {e}", exc_info=True)
            return self._get_fallback_structure()

    def _get_fallback_structure(self) -> Dict[str, Any]:
        """
        Fallback структура если БД недоступна
        ВАЖНО: Это минимальная структура. Полная структура с 58 экспертами должна быть в БД!
        Для получения полной структуры нужно:
        1. Импортировать данные из ~/migration/server2/knowledge_os_dump.sql
        2. Или запустить миграцию: python3 scripts/migration/corporation_full_migration.py
        """
        # Расширенный fallback с основными отделами и экспертами
        # Полный список из 58 экспертов должен быть в БД!
        return {
            "departments": [
                {
                    "id": "Backend",
                    "name": "Backend",
                    "manager": {"id": 1, "name": "Игорь", "role": "Backend Developer"},
                    "employees": [
                        {
                            "id": 1,
                            "name": "Игорь",
                            "role": "Backend Developer",
                            "is_manager": True,
                            "department": "Backend",
                        },
                        {
                            "id": 2,
                            "name": "Даниил",
                            "role": "Principal Backend Architect",
                            "is_manager": False,
                            "department": "Backend",
                        },
                        {
                            "id": 11,
                            "name": "Роман",
                            "role": "Database Engineer",
                            "is_manager": False,
                            "department": "Backend",
                        },
                        {
                            "id": 17,
                            "name": "Никита",
                            "role": "Full-stack Developer",
                            "is_manager": False,
                            "department": "Backend",
                        },
                    ],
                    "employee_count": 4,
                    "subdepartments": [],
                },
                {
                    "id": "ML/AI",
                    "name": "ML/AI",
                    "manager": {"id": 3, "name": "Дмитрий", "role": "ML Engineer"},
                    "employees": [
                        {
                            "id": 3,
                            "name": "Дмитрий",
                            "role": "ML Engineer",
                            "is_manager": True,
                            "department": "ML/AI",
                        },
                        {
                            "id": 6,
                            "name": "Максим",
                            "role": "Data Analyst",
                            "is_manager": False,
                            "department": "ML/AI",
                        },
                    ],
                    "employee_count": 2,
                    "subdepartments": [],
                },
                {
                    "id": "Frontend",
                    "name": "Frontend",
                    "manager": {"id": 4, "name": "Андрей", "role": "Frontend Developer"},
                    "employees": [
                        {
                            "id": 4,
                            "name": "Андрей",
                            "role": "Frontend Developer",
                            "is_manager": True,
                            "department": "Frontend",
                        },
                        {
                            "id": 5,
                            "name": "София",
                            "role": "UI/UX Designer",
                            "is_manager": False,
                            "department": "Frontend",
                        },
                    ],
                    "employee_count": 2,
                    "subdepartments": [],
                },
                {
                    "id": "DevOps/Infra",
                    "name": "DevOps/Infra",
                    "manager": {"id": 7, "name": "Сергей", "role": "DevOps Engineer"},
                    "employees": [
                        {
                            "id": 7,
                            "name": "Сергей",
                            "role": "DevOps Engineer",
                            "is_manager": True,
                            "department": "DevOps/Infra",
                        },
                        {
                            "id": 8,
                            "name": "Елена",
                            "role": "Monitor",
                            "is_manager": False,
                            "department": "DevOps/Infra",
                        },
                    ],
                    "employee_count": 2,
                    "subdepartments": [],
                },
                {
                    "id": "QA",
                    "name": "QA",
                    "manager": {"id": 5, "name": "Анна", "role": "QA Engineer"},
                    "employees": [
                        {
                            "id": 5,
                            "name": "Анна",
                            "role": "QA Engineer",
                            "is_manager": True,
                            "department": "QA",
                        },
                        {
                            "id": 21,
                            "name": "Артем",
                            "role": "Code Reviewer",
                            "is_manager": False,
                            "department": "QA",
                        },
                    ],
                    "employee_count": 2,
                    "subdepartments": [],
                },
                {
                    "id": "Security",
                    "name": "Security",
                    "manager": {"id": 9, "name": "Алексей", "role": "Security Engineer"},
                    "employees": [
                        {
                            "id": 9,
                            "name": "Алексей",
                            "role": "Security Engineer",
                            "is_manager": True,
                            "department": "Security",
                        }
                    ],
                    "employee_count": 1,
                    "subdepartments": [],
                },
                {
                    "id": "Risk Management",
                    "name": "Risk Management",
                    "manager": {"id": 10, "name": "Мария", "role": "Risk Manager"},
                    "employees": [
                        {
                            "id": 10,
                            "name": "Мария",
                            "role": "Risk Manager",
                            "is_manager": True,
                            "department": "Risk Management",
                        }
                    ],
                    "employee_count": 1,
                    "subdepartments": [],
                },
                {
                    "id": "Performance",
                    "name": "Performance",
                    "manager": {"id": 12, "name": "Ольга", "role": "Performance Engineer"},
                    "employees": [
                        {
                            "id": 12,
                            "name": "Ольга",
                            "role": "Performance Engineer",
                            "is_manager": True,
                            "department": "Performance",
                        }
                    ],
                    "employee_count": 1,
                    "subdepartments": [],
                },
                {
                    "id": "Documentation",
                    "name": "Documentation",
                    "manager": {"id": 13, "name": "Татьяна", "role": "Technical Writer"},
                    "employees": [
                        {
                            "id": 13,
                            "name": "Татьяна",
                            "role": "Technical Writer",
                            "is_manager": True,
                            "department": "Documentation",
                        }
                    ],
                    "employee_count": 1,
                    "subdepartments": [],
                },
                {
                    "id": "Marketing",
                    "name": "Marketing",
                    "manager": {
                        "id": 18,
                        "name": "Дарья",
                        "role": "SEO & AI Visibility Specialist",
                    },
                    "employees": [
                        {
                            "id": 18,
                            "name": "Дарья",
                            "role": "SEO & AI Visibility Specialist",
                            "is_manager": True,
                            "department": "Marketing",
                        },
                        {
                            "id": 19,
                            "name": "Марина",
                            "role": "Content Manager",
                            "is_manager": False,
                            "department": "Marketing",
                        },
                    ],
                    "employee_count": 2,
                    "subdepartments": [],
                },
                {
                    "id": "Trading",
                    "name": "Trading",
                    "manager": {"id": 9, "name": "Павел", "role": "Trading Strategy Developer"},
                    "employees": [
                        {
                            "id": 9,
                            "name": "Павел",
                            "role": "Trading Strategy Developer",
                            "is_manager": True,
                            "department": "Trading",
                        },
                        {
                            "id": 14,
                            "name": "Екатерина",
                            "role": "Financial Analyst",
                            "is_manager": False,
                            "department": "Trading",
                        },
                    ],
                    "employee_count": 2,
                    "subdepartments": [],
                },
                {
                    "id": "Product",
                    "name": "Product",
                    "manager": {"id": 22, "name": "Анастасия", "role": "Product Manager"},
                    "employees": [
                        {
                            "id": 22,
                            "name": "Анастасия",
                            "role": "Product Manager",
                            "is_manager": True,
                            "department": "Product",
                        }
                    ],
                    "employee_count": 1,
                    "subdepartments": [],
                },
                {
                    "id": "Legal",
                    "name": "Legal",
                    "manager": {"id": 20, "name": "Юлия", "role": "Legal Counsel"},
                    "employees": [
                        {
                            "id": 20,
                            "name": "Юлия",
                            "role": "Legal Counsel",
                            "is_manager": True,
                            "department": "Legal",
                        }
                    ],
                    "employee_count": 1,
                    "subdepartments": [],
                },
            ],
            "total_employees": 22,  # Только основные эксперты из seed
            "total_departments": 13,
            "updated_at": datetime.now().isoformat(),
            "note": "⚠️ Это fallback структура с основными экспертами. Полная структура с 58 экспертами должна быть в БД! Импортируйте данные из ~/migration/server2/knowledge_os_dump.sql",
        }

    async def get_department_structure(self, department_name: str) -> Optional[Dict[str, Any]]:
        """
        Получить структуру конкретного отдела

        Args:
            department_name: Название отдела

        Returns:
            Структура отдела или None
        """
        full_structure = await self.get_full_structure()

        for dept in full_structure.get("departments", []):
            if dept["name"] == department_name:
                return dept

        return None

    async def get_employees_in_department(self, department_name: str) -> List[Dict]:
        """
        Получить список сотрудников отдела

        Args:
            department_name: Название отдела

        Returns:
            Список сотрудников
        """
        dept_structure = await self.get_department_structure(department_name)
        if dept_structure:
            return dept_structure.get("employees", [])
        return []

    async def get_manager_of_department(self, department_name: str) -> Optional[Dict]:
        """
        Получить управляющего отдела

        Args:
            department_name: Название отдела

        Returns:
            Информация о управляющем или None
        """
        dept_structure = await self.get_department_structure(department_name)
        if dept_structure:
            return dept_structure.get("manager")
        return None

    async def refresh_structure(self):
        """Принудительно обновить структуру (сбросить кэш)"""
        logger.info("🔄 Принудительное обновление структуры...")
        self._structure_cache = None
        self._cache_timestamp = None
        await self.get_full_structure(force_refresh=True)

    def get_structure_summary(self, structure: Dict) -> str:
        """
        Получить текстовое описание структуры для промптов

        Args:
            structure: Структура организации

        Returns:
            Текстовое описание
        """
        summary = "СТРУКТУРА ОРГАНИЗАЦИИ:\n\n"

        for dept in structure.get("departments", []):
            summary += f"📁 {dept['name']}\n"
            if dept.get("manager"):
                summary += f"   👔 Управляющий: {dept['manager']['name']} ({dept['manager'].get('role', 'N/A')})\n"
            summary += f"   👥 Сотрудников: {dept['employee_count']}\n"

            if dept.get("employees"):
                summary += "   Сотрудники:\n"
                for emp in dept["employees"][:10]:  # Первые 10 для краткости
                    role_marker = "👔" if emp.get("is_manager") else "👤"
                    summary += f"      {role_marker} {emp['name']} - {emp['role']}\n"
                if len(dept["employees"]) > 10:
                    summary += f"      ... и еще {len(dept['employees']) - 10} сотрудников\n"
            summary += "\n"

        summary += f"Всего: {structure.get('total_departments', 0)} отделов, {structure.get('total_employees', 0)} сотрудников\n"

        return summary


# Глобальный экземпляр
_organizational_structure: Optional[OrganizationalStructure] = None


def get_organizational_structure(db_url: Optional[str] = None) -> OrganizationalStructure:
    """
    Получить глобальный экземпляр Organizational Structure
    ВАЖНО: Если db_url не передан, использует DATABASE_URL из окружения
    Система автоматически отслеживает изменения (корпорация растет!)
    """
    global _organizational_structure
    import os

    # Если db_url не передан, используем переменную окружения
    if db_url is None:
        db_url = os.getenv("DATABASE_URL")
    # Если все еще None, используем дефолтное значение для Docker
    if db_url is None:
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
    # Создаем новый экземпляр, если его нет или db_url изменился
    if _organizational_structure is None or _organizational_structure.db_url != db_url:
        _organizational_structure = OrganizationalStructure(db_url)
    return _organizational_structure
