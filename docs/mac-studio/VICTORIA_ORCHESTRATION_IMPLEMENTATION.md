# 🎯 Реализация: Victoria как Главный Оркестратор

**Дата:** 2026-01-25  
**Статус:** 📋 **ПЛАН РЕАЛИЗАЦИИ**

---

## 🎯 ЦЕЛЬ

Превратить Victoria в главного оркестратора корпорации, который:

- ✅ Координирует все задачи через иерархическую структуру
- ✅ Собирает ответы от нескольких экспертов
- ✅ Синтезирует финальные решения
- ✅ Интегрируется с существующими оркестраторами
- ✅ Развивается как живой организм

---

## 📊 ТЕКУЩАЯ СИТУАЦИЯ

### **Как сейчас работает:**

1. **Задачи создаются** (Telegram, API, автономно через Curiosity Engine)
2. **Orchestrator находит** задачи без исполнителя (`enhanced_orchestrator.py`)
3. **Выбирает эксперта** по домену/роли/загрузке (`assign_task_to_best_expert`)
4. **Назначает задачу** эксперту в БД
5. **Smart Worker** обрабатывает задачи (`smart_worker_autonomous.py`)
6. **Результат сохраняется** в Knowledge OS

### **Проблемы:**

❌ **Victoria не участвует** в распределении (только в Swarm для консенсуса)  
❌ **Нет иерархии** - все эксперты на одном уровне  
❌ **Нет сбора ответов** от нескольких экспертов для сложных задач  
❌ **Нет синтеза** - каждый эксперт работает изолированно  
❌ **Нет координации** между экспертами

---

## 🏗️ ПРЕДЛАГАЕМАЯ АРХИТЕКТУРА

### **Иерархическая структура:**

```
┌─────────────────────────────────────┐
│      Victoria (Team Lead)          │
│  - Главный оркестратор              │
│  - Анализ задачи                    │
│  - Выбор стратегии                  │
│  - Координация                      │
│  - Синтез результатов               │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
   ┌───▼───┐      ┌─────▼─────┐
   │Simple │      │  Complex  │
   │Task   │      │   Task    │
   └───┬───┘      └─────┬─────┘
       │                │
   ┌───▼───┐      ┌─────▼─────┐
   │Expert │      │   Swarm   │
   │(1)    │      │  (3-5)    │
   └───┬───┘      └─────┬─────┘
       │                │
   ┌───▼────────────────▼───┐
   │   Collect Responses    │
   └───────────┬────────────┘
               │
        ┌──────▼──────┐
        │  Synthesize │
        │   (Victoria)│
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │ Final Result  │
        └───────────────┘
```

### **Иерархия отделов:**

```
Victoria (Team Lead)
│
├── Backend Department
│   └── Игорь (Head) → [Игорь, Даниил, Роман]
│
├── ML Department
│   └── Дмитрий (Head) → [Дмитрий, Александр Нейман, Максим]
│
├── DevOps Department
│   └── Сергей (Head) → [Сергей, Елена]
│
└── ...
```

---

## 🔄 ПРОЦЕСС ОРКЕСТРАЦИИ

### **1. Анализ задачи (Victoria)**

```python
async def analyze_task(goal: str) -> TaskAnalysis:
    """Victoria анализирует задачу"""
    category = categorize_task(goal)
    complexity = assess_complexity(goal)
    departments = identify_departments(goal)

    return TaskAnalysis(
        category=category,
        complexity=complexity,  # simple, complex, multi_department
        departments=departments,
        estimated_experts_needed=calculate_experts(complexity)
    )
```

### **2. Выбор стратегии**

#### **Simple Task** (простая задача)

- Один эксперт
- Прямое выполнение
- Быстрый ответ

#### **Complex Task** (сложная задача)

- Swarm подход
- 3-5 экспертов параллельно
- Синтез консенсуса

#### **Multi-Department Task** (межотдельная задача)

- Иерархический подход
- Department Heads координируют
- Сбор результатов от отделов
- Финальный синтез

### **3. Сбор ответов**

```python
async def collect_responses(experts: List[Expert], goal: str) -> List[Response]:
    """Сбор ответов от экспертов параллельно"""
    tasks = []
    for expert in experts:
        task = expert.execute(goal)
        tasks.append(task)

    responses = await asyncio.gather(*tasks)
    return responses
```

### **4. Синтез результатов**

```python
async def synthesize_responses(responses: List[Response], goal: str) -> str:
    """Victoria синтезирует финальный ответ"""
    synthesis_prompt = f"""
    ВЫ - ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA.

    ЗАДАЧА: {goal}

    ОТВЕТЫ ЭКСПЕРТОВ:
    {format_responses(responses)}

    ЗАДАЧА: Сформируйте финальное, идеальное решение на основе мнений экспертов.
    Учтите все точки зрения, устраните противоречия, создайте единое решение.
    """

    final_result = await victoria.planner.ask(synthesis_prompt)
    return final_result
```

---

## 🧬 КАК ЖИВОЙ ОРГАНИЗМ

### **Компоненты саморазвития:**

1. **Curiosity Engine** ✅
   - Находит "голодные" области
   - Генерирует исследовательские задачи
   - Автономный рост знаний

2. **Nightly Learner** ✅
   - Ежедневное обучение
   - Обновление экспертов
   - Эволюция знаний

3. **Expert Evolution** ✅
   - Эволюция эффективных экспертов
   - Специализация
   - Адаптация к новым задачам

4. **Knowledge Growth** ✅
   - Автоматическое создание знаний
   - Связи между знаниями
   - Рост базы (50,955 → больше)

5. **Team Formation** ✅
   - Автоматическое формирование команд
   - Адаптация к новым типам задач
   - Оптимизация состава

---

## 📊 МЕТРИКИ РАЗВИТИЯ

### **Отслеживание роста:**

- 📈 **Команда:** 58 экспертов → растет
- 📈 **Знания:** 50,955 узлов → растет
- 📈 **Домены:** 35 доменов → растет
- 📈 **Отделы:** 27 отделов → растет
- 📈 **Эффективность:** улучшается
- 📈 **Качество решений:** улучшается

---

## 🚀 ПЛАН РЕАЛИЗАЦИИ

### **Этап 1: Интеграция Victoria в оркестрацию**

**Задачи:**

- [ ] Добавить метод `orchestrate_task()` в Victoria
- [ ] Интеграция с существующими оркестраторами
- [ ] Использование улучшенной логики выбора экспертов

**Код:**

```python
async def orchestrate_task(self, goal: str) -> str:
    """Victoria как главный оркестратор"""
    # 1. Анализ задачи
    analysis = await self.analyze_task(goal)

    # 2. Выбор стратегии
    if analysis.complexity == "simple":
        expert = await self.select_expert_for_task(goal)
        result = await expert.execute(goal)
        return result

    elif analysis.complexity == "complex":
        # Swarm подход
        experts = await self.select_expert_team(goal, count=3)
        responses = await self.collect_responses(experts, goal)
        consensus = await self.synthesize_responses(responses, goal)
        return consensus

    elif analysis.complexity == "multi_department":
        # Иерархический подход
        departments = analysis.departments
        department_results = {}
        for dept in departments:
            dept_head = await self.get_department_head(dept)
            dept_result = await dept_head.coordinate(goal)
            department_results[dept] = dept_result
        final_result = await self.synthesize_department_results(department_results, goal)
        return final_result
```

---

### **Этап 2: Иерархическая структура**

**Задачи:**

- [ ] Определение Department Heads
- [ ] Реализация иерархического распределения
- [ ] Делегирование через отделы

**Код:**

```python
async def get_department_head(self, department: str) -> Optional[Expert]:
    """Получить главу отдела"""
    pool = await self._get_db_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        # Ищем главу отдела (Head, Lead, Director)
        head = await conn.fetchrow("""
            SELECT id, name, role, system_prompt, department
            FROM experts
            WHERE department = $1
            AND (role ILIKE '%Head%' OR role ILIKE '%Lead%' OR role ILIKE '%Director%')
            LIMIT 1
        """, department)

        if head:
            return Expert(head['name'], head['system_prompt'], head['role'])
        return None

async def coordinate_department(self, department: str, goal: str) -> str:
    """Координация через отдел"""
    head = await self.get_department_head(department)
    if not head:
        # Если нет главы, выбираем лучшего эксперта отдела
        expert = await self.select_expert_for_department(department, goal)
        return await expert.execute(goal)

    # Глава координирует экспертов отдела
    experts = await self.get_department_experts(department)
    responses = await self.collect_responses(experts, goal)
    department_result = await head.synthesize(responses, goal)
    return department_result
```

---

### **Этап 3: Сбор и синтез ответов**

**Задачи:**

- [ ] Механизм сбора ответов от нескольких экспертов
- [ ] Синтез консенсуса через Victoria
- [ ] Обработка конфликтов

**Код:**

```python
async def collect_responses(self, experts: List[Tuple[str, Dict]], goal: str) -> List[Response]:
    """Сбор ответов от экспертов параллельно"""
    tasks = []
    for expert_name, expert_data in experts:
        # Создаем задачу для эксперта
        task = self._execute_expert_task(expert_name, expert_data, goal)
        tasks.append(task)

    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Фильтруем ошибки
    valid_responses = []
    for i, response in enumerate(responses):
        if isinstance(response, Exception):
            logger.error(f"Ошибка от эксперта {experts[i][0]}: {response}")
        else:
            valid_responses.append(Response(
                expert=experts[i][0],
                response=response,
                timestamp=datetime.now(timezone.utc)
            ))

    return valid_responses

async def synthesize_responses(self, responses: List[Response], goal: str) -> str:
    """Victoria синтезирует финальный ответ"""
    if not responses:
        return "Нет ответов от экспертов"

    if len(responses) == 1:
        return responses[0].response

    # Формируем промпт для синтеза
    responses_text = "\n\n".join([
        f"--- {r.expert} ---\n{r.response}"
        for r in responses
    ])

    synthesis_prompt = f"""
    ВЫ - ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA.

    ЗАДАЧА: {goal}

    ОТВЕТЫ ЭКСПЕРТОВ:
    {responses_text}

    ЗАДАЧА: Сформируйте финальное, идеальное решение на основе мнений экспертов.

    ИНСТРУКЦИИ:
    1. Учтите все точки зрения
    2. Устраните противоречия
    3. Создайте единое решение
    4. Сохраните стиль ATRA
    5. Выделите ключевые инсайты

    ФИНАЛЬНОЕ РЕШЕНИЕ:
    """

    final_result = await self.planner.ask(synthesis_prompt, raw_response=True)
    return final_result
```

---

### **Этап 4: Интеграция с существующими оркестраторами**

**Задачи:**

- [ ] Victoria как главный оркестратор для новых задач
- [ ] Интеграция с `enhanced_orchestrator.py`
- [ ] Использование `swarm_orchestrator.py` для сложных задач

**Код:**

```python
# В enhanced_orchestrator.py
async def assign_task_to_victoria_or_expert(conn, task_id: str):
    """Назначение задачи через Victoria или напрямую эксперту"""
    task = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)

    # Простые задачи - напрямую эксперту (как сейчас)
    if is_simple_task(task):
        await assign_task_to_best_expert(conn, task_id, task['domain_id'])
        return

    # Сложные задачи - через Victoria
    # Создаем задачу для Victoria
    victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")

    # Victoria обработает задачу через свой orchestrate_task()
    # Это можно сделать через API вызов или напрямую
    await conn.execute("""
        UPDATE tasks
        SET assignee_expert_id = $1,
            status = 'in_progress',
            metadata = metadata || '{"orchestrated_by": "victoria"}'::jsonb
        WHERE id = $2
    """, victoria_id, task_id)
```

---

## 🔄 ИНТЕГРАЦИЯ С СУЩЕСТВУЮЩИМИ СИСТЕМАМИ

### **1. Enhanced Orchestrator**

**Текущая логика:**

- Находит задачи без исполнителя
- Назначает лучшего эксперта
- Учитывает загрузку

**Новая логика:**

- Простые задачи → как сейчас (напрямую эксперту)
- Сложные задачи → через Victoria
- Victoria анализирует и выбирает стратегию

### **2. Swarm Orchestrator**

**Текущая логика:**

- Используется для критических проблем
- Собирает мнения экспертов
- Синтезирует через Victoria

**Новая логика:**

- Интегрирован в Victoria
- Автоматически используется для сложных задач
- Victoria сама выбирает экспертов для Swarm

### **3. Smart Worker**

**Текущая логика:**

- Обрабатывает задачи из БД
- Вызывает экспертов через `ai_core`

**Новая логика:**

- Если задача назначена Victoria → вызывает Victoria API
- Victoria координирует выполнение
- Результат сохраняется в БД

---

## 🧬 РАЗВИТИЕ КАК ЖИВОЙ ОРГАНИЗМ

### **Компоненты саморазвития:**

1. **Curiosity Engine** ✅
   - Находит "голодные" области
   - Генерирует исследовательские задачи
   - Автономный рост знаний

2. **Nightly Learner** ✅
   - Ежедневное обучение на основе опыта
   - Обновление экспертов
   - Эволюция знаний

3. **Expert Evolution** ✅
   - Эволюция эффективных экспертов
   - Специализация
   - Адаптация к новым задачам

4. **Knowledge Growth** ✅
   - Автоматическое создание знаний
   - Связи между знаниями
   - Рост базы (50,955 → больше)

5. **Team Formation** ✅
   - Автоматическое формирование команд
   - Адаптация к новым типам задач
   - Оптимизация состава

### **Метрики роста:**

- 📈 **Команда:** 58 экспертов → растет
- 📈 **Знания:** 50,955 узлов → растет
- 📈 **Домены:** 35 доменов → растет
- 📈 **Отделы:** 27 отделов → растет
- 📈 **Эффективность:** улучшается
- 📈 **Качество решений:** улучшается

---

## 📋 ДЕТАЛЬНЫЙ ПЛАН РЕАЛИЗАЦИИ

### **Шаг 1: Добавить orchestrate_task() в Victoria**

```python
# В src/agents/bridge/victoria_server.py

async def orchestrate_task(self, goal: str) -> str:
    """Victoria как главный оркестратор"""
    # 1. Анализ задачи
    category = self._categorize_task(goal)
    complexity = self._assess_complexity(goal)
    departments = self._identify_departments(goal)

    # 2. Выбор стратегии
    if complexity == "simple":
        # Простая задача - один эксперт
        expert_name, expert_data, _ = await self.select_expert_for_task(goal)
        if expert_name:
            # Выполняем через эксперта
            result = await self._execute_via_expert(expert_name, expert_data, goal)
            return result
        else:
            # Fallback - выполняем сами
            return await super().run(goal)

    elif complexity == "complex":
        # Сложная задача - Swarm
        expert_name, expert_data, additional_experts = await self.select_expert_for_task(goal, use_multiple=True)

        experts = [(expert_name, expert_data)]
        if additional_experts:
            experts.extend(additional_experts)

        # Собираем ответы
        responses = await self._collect_expert_responses(experts, goal)

        # Синтезируем
        final_result = await self._synthesize_responses(responses, goal)
        return final_result

    elif complexity == "multi_department":
        # Межотдельная задача - иерархия
        department_results = {}
        for dept in departments:
            dept_result = await self._coordinate_department(dept, goal)
            department_results[dept] = dept_result

        # Финальный синтез
        final_result = await self._synthesize_department_results(department_results, goal)
        return final_result

    else:
        # Fallback
        return await super().run(goal)
```

### **Шаг 2: Методы анализа и координации**

```python
def _assess_complexity(self, goal: str) -> str:
    """Оценить сложность задачи"""
    goal_lower = goal.lower()

    # Простые задачи
    simple_keywords = ["скажи", "привет", "покажи", "выведи", "список"]
    if any(kw in goal_lower for kw in simple_keywords) and len(goal.split()) <= 10:
        return "simple"

    # Межотдельные задачи
    multi_dept_keywords = ["комплексное", "полное решение", "несколько отделов", "межотдельная"]
    if any(kw in goal_lower for kw in multi_dept_keywords):
        return "multi_department"

    # Сложные задачи
    complex_keywords = ["проанализируй", "оптимизируй", "разработай стратегию", "создай архитектуру"]
    if any(kw in goal_lower for kw in complex_keywords):
        return "complex"

    return "simple"

def _identify_departments(self, goal: str) -> List[str]:
    """Определить задействованные отделы"""
    goal_lower = goal.lower()
    departments = []

    dept_keywords = {
        "Backend": ["api", "сервер", "backend", "база данных"],
        "ML": ["модель", "обучение", "ml", "ai", "нейросеть"],
        "DevOps": ["развертывание", "deploy", "мониторинг", "docker"],
        "Security": ["безопасность", "security", "уязвимость"],
    }

    for dept, keywords in dept_keywords.items():
        if any(kw in goal_lower for kw in keywords):
            departments.append(dept)

    return departments if departments else ["General"]

async def _execute_via_expert(self, expert_name: str, expert_data: Dict, goal: str) -> str:
    """Выполнить задачу через эксперта"""
    # Используем ai_core для выполнения через эксперта
    try:
        from knowledge_os.app.ai_core import run_smart_agent_async

        prompt = f"""{expert_data.get('system_prompt', '')}

ЗАДАЧА: {goal}

Выполни задачу профессионально и качественно.
"""

        result = await run_smart_agent_async(
            prompt,
            expert_name=expert_name,
            category="expert_task"
        )

        if isinstance(result, dict):
            return result.get('response', str(result))
        return str(result)
    except Exception as e:
        logger.error(f"Ошибка выполнения через эксперта {expert_name}: {e}")
        return f"Ошибка: {e}"

async def _collect_expert_responses(self, experts: List[Tuple[str, Dict]], goal: str) -> List[Dict]:
    """Собрать ответы от экспертов параллельно"""
    tasks = []
    for expert_name, expert_data in experts:
        task = self._execute_via_expert(expert_name, expert_data, goal)
        tasks.append(task)

    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # Формируем список ответов
    result = []
    for i, response in enumerate(responses):
        if isinstance(response, Exception):
            logger.error(f"Ошибка от эксперта {experts[i][0]}: {response}")
            result.append({
                "expert": experts[i][0],
                "response": f"Ошибка: {response}",
                "error": True
            })
        else:
            result.append({
                "expert": experts[i][0],
                "response": str(response),
                "error": False
            })

    return result

async def _synthesize_responses(self, responses: List[Dict], goal: str) -> str:
    """Синтезировать ответы от экспертов"""
    if not responses:
        return "Нет ответов от экспертов"

    if len(responses) == 1:
        return responses[0]['response']

    # Формируем промпт для синтеза
    responses_text = "\n\n".join([
        f"--- {r['expert']} ---\n{r['response']}"
        for r in responses if not r.get('error')
    ])

    synthesis_prompt = f"""
ВЫ - ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA.

ЗАДАЧА: {goal}

ОТВЕТЫ ЭКСПЕРТОВ:
{responses_text}

ЗАДАЧА: Сформируйте финальное, идеальное решение на основе мнений экспертов.

ИНСТРУКЦИИ:
1. Учтите все точки зрения
2. Устраните противоречия
3. Создайте единое решение
4. Сохраните стиль ATRA
5. Выделите ключевые инсайты

ФИНАЛЬНОЕ РЕШЕНИЕ:
"""

    final_result = await self.planner.ask(synthesis_prompt, raw_response=True)
    return final_result

async def _coordinate_department(self, department: str, goal: str) -> str:
    """Координировать через отдел"""
    pool = await self._get_db_pool()
    if not pool:
        return f"Не удалось подключиться к БД для координации отдела {department}"

    try:
        async with pool.acquire() as conn:
            # Ищем главу отдела
            head = await conn.fetchrow("""
                SELECT id, name, role, system_prompt, department
                FROM experts
                WHERE department = $1
                AND (role ILIKE '%Head%' OR role ILIKE '%Lead%' OR role ILIKE '%Director%')
                LIMIT 1
            """, department)

            if head:
                # Глава координирует
                experts = await conn.fetch("""
                    SELECT name, role, system_prompt
                    FROM experts
                    WHERE department = $1
                    LIMIT 3
                """, department)

                # Собираем ответы от экспертов отдела
                expert_list = [(e['name'], {
                    'role': e['role'],
                    'system_prompt': e['system_prompt']
                }) for e in experts]

                responses = await self._collect_expert_responses(expert_list, goal)

                # Глава синтезирует
                head_prompt = f"""{head['system_prompt']}

ЗАДАЧА: {goal}

ОТВЕТЫ ЭКСПЕРТОВ ОТДЕЛА:
{self._format_responses(responses)}

Сформируйте финальное решение отдела.
"""

                result = await self._execute_via_expert(head['name'], {
                    'system_prompt': head['system_prompt'],
                    'role': head['role']
                }, head_prompt)

                return result
            else:
                # Нет главы - выбираем лучшего эксперта отдела
                expert = await self.select_expert_for_department(department, goal)
                if expert:
                    return await self._execute_via_expert(expert[0], expert[1], goal)
                return f"Не найден эксперт для отдела {department}"
    except Exception as e:
        logger.error(f"Ошибка координации отдела {department}: {e}")
        return f"Ошибка: {e}"

async def select_expert_for_department(self, department: str, goal: str) -> Optional[Tuple[str, Dict]]:
    """Выбрать лучшего эксперта отдела"""
    pool = await self._get_db_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            experts = await conn.fetch("""
                SELECT name, role, system_prompt, department
                FROM experts
                WHERE department = $1
            """, department)

            if not experts:
                return None

            # Оцениваем каждого эксперта отдела
            best_expert = None
            best_score = -1

            for expert in experts:
                score = 0.0

                # Релевантность роли
                role = expert['role'].lower()
                goal_lower = goal.lower()
                if any(kw in role for kw in goal_lower.split()[:3]):
                    score += 10.0

                # Опыт (если есть статистика)
                expert_id = expert.get('id')
                if expert_id:
                    completed = await conn.fetchval("""
                        SELECT COUNT(*) FROM tasks
                        WHERE assignee_expert_id = $1 AND status = 'completed'
                    """, expert_id) or 0
                    score += completed * 0.5

                if score > best_score:
                    best_score = score
                    best_expert = (expert['name'], {
                        'role': expert['role'],
                        'system_prompt': expert['system_prompt'],
                        'department': expert['department']
                    })

            return best_expert
    except Exception as e:
        logger.error(f"Ошибка выбора эксперта отдела {department}: {e}")
        return None

async def _synthesize_department_results(self, department_results: Dict[str, str], goal: str) -> str:
    """Синтезировать результаты от отделов"""
    if not department_results:
        return "Нет результатов от отделов"

    results_text = "\n\n".join([
        f"--- {dept} ---\n{result}"
        for dept, result in department_results.items()
    ])

    synthesis_prompt = f"""
ВЫ - ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA.

ЗАДАЧА: {goal}

РЕЗУЛЬТАТЫ ОТДЕЛОВ:
{results_text}

ЗАДАЧА: Сформируйте финальное, комплексное решение на основе результатов всех отделов.

ИНСТРУКЦИИ:
1. Объедините результаты всех отделов
2. Устраните противоречия
3. Создайте единое решение
4. Сохраните стиль ATRA

ФИНАЛЬНОЕ РЕШЕНИЕ:
"""

    final_result = await self.planner.ask(synthesis_prompt, raw_response=True)
    return final_result

def _format_responses(self, responses: List[Dict]) -> str:
    """Форматировать ответы для промпта"""
    return "\n\n".join([
        f"--- {r['expert']} ---\n{r['response']}"
        for r in responses if not r.get('error')
    ])
```

### **Шаг 3: Интеграция в run() метод**

```python
async def run(self, goal: str, max_steps: int = 30) -> str:
    """Выполнить задачу с оркестрацией"""
    # Проверка кэша
    cached_result = self._get_cached_result(goal)
    if cached_result:
        return cached_result

    # Простые задачи - как раньше
    simple_tasks = ["скажи", "привет", "покажи файлы", "выведи список", "список файлов"]
    goal_lower = goal.lower()

    if any(task in goal_lower for task in simple_tasks) and len(goal.split()) <= 10:
        # Простые задачи не требуют оркестрации
        enhanced = f"ВЫПОЛНИ ЗАДАЧУ: {goal}\n\nВАЖНО: Выполняй ТОЧНО то что просят, ничего лишнего!"
        result = await super().run(enhanced, max_steps)
        self._save_to_cache(goal, result)
        return result

    # Сложные задачи - через оркестрацию
    result = await self.orchestrate_task(goal)

    # Сохраняем в кэш и обучаемся
    self._save_to_cache(goal, result)
    if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE and result:
        await self._learn_from_task(goal, result)

    return result
```

---

## 🔄 ИНТЕГРАЦИЯ С СУЩЕСТВУЮЩИМИ ОРКЕСТРАТОРАМИ

### **1. Enhanced Orchestrator**

**Модификация:**

```python
# В enhanced_orchestrator.py

async def assign_task_to_best_expert_or_victoria(
    conn,
    task_id: str,
    domain_id: Optional[str] = None,
    required_role: Optional[str] = None
) -> Optional[str]:
    """Назначение задачи через Victoria или напрямую эксперту"""
    task = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)

    # Анализируем сложность задачи
    complexity = assess_task_complexity(task['title'], task['description'])

    if complexity == "simple":
        # Простые задачи - напрямую эксперту (как сейчас)
        return await assign_task_to_best_expert(conn, task_id, domain_id, required_role)
    else:
        # Сложные задачи - через Victoria
        victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")

        await conn.execute("""
            UPDATE tasks
            SET assignee_expert_id = $1,
                status = 'pending',
                metadata = metadata || '{"orchestrated_by": "victoria", "complexity": $2}'::jsonb
            WHERE id = $3
        """, victoria_id, complexity, task_id)

        logger.info(f"✅ Задача {task_id} назначена Victoria для оркестрации")
        return victoria_id
```

### **2. Smart Worker**

**Модификация:**

```python
# В smart_worker_autonomous.py

async def process_task(pool, task):
    """Обработать задачу"""
    expert_name = task['assignee']

    # Если задача назначена Victoria
    if expert_name == 'Виктория':
        # Вызываем Victoria API для оркестрации
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://victoria-agent:8010/run",
                json={"goal": f"{task['title']}\n\n{task['description']}"},
                timeout=300.0
            )
            result = response.json().get('output', '')
    else:
        # Обычная обработка через эксперта
        result = await process_expert_task(expert_name)

    # Сохраняем результат
    await pool.execute("""
        UPDATE tasks
        SET status = 'completed',
            result = $1,
            completed_at = NOW()
        WHERE id = $2
    """, result, task['id'])
```

---

## 📊 МЕТРИКИ И МОНИТОРИНГ

### **Метрики оркестрации:**

- 📈 Количество задач, обработанных через Victoria
- 📈 Количество задач, обработанных через Swarm
- 📈 Количество задач, обработанных через иерархию
- 📈 Среднее время выполнения
- 📈 Качество решений (consensus score)
- 📈 Эффективность распределения

### **Метрики роста:**

- 📈 Рост команды (новые эксперты)
- 📈 Рост знаний (новые узлы)
- 📈 Рост доменов
- 📈 Адаптация к новым типам задач

---

_Документ создан 2026-01-25_
