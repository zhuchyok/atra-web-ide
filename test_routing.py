from corporation_data_tool import is_data_question

query = "Отрефактори дашборд knowledge_os/dashboard/app.py: раздели его на модули в папке tabs/. Делегируй написание кода Веронике, а аудит БД Роману."
print(f"Query: {query}")
print(f"is_data_question: {is_data_question(query)}")

# Check keywords
q = query.lower()
corp_keywords = ["корпораци", "corporation", "компани", "команд", "отдел", "department"]
for kw in corp_keywords:
    if kw in q:
        print(f"Matched corp keyword: {kw}")

data_keywords = [
    "сколько", "количество", "число", "count", "how many",
    "список", "покажи", "выведи", "show", "list",
    "статистика", "метрик", "статус", "stats",
    "кто", "какие", "какой", "what", "which", "who",
    "топ", "лучш", "худш", "top", "best", "worst",
    "последн", "recent", "latest", "новы",
    "всего", "total", "sum", "итого",
    "средн", "average", "avg",
    "подтверди", "повтори", "напомни",
]
for kw in data_keywords:
    if kw in q:
        print(f"Matched data keyword: {kw}")

entity_keywords = [
    "сотрудник", "эксперт", "expert", "employee",
    "задач", "task", "задани",
    "знани", "knowledge", "узл", "node",
    "домен", "domain", "област",
    "kpi", "okr", "цел", "goal",
    "бюджет", "budget", "рейтинг", "score",
    "лог", "log", "взаимодейств", "interaction",
]
for kw in entity_keywords:
    if kw in q:
        print(f"Matched entity keyword: {kw}")
