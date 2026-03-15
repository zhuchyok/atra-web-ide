🎯 ЦЕЛЬ: Реализовать External Docs Indexer в app/external_indexer.py.

1. Создай новый модуль `knowledge_os/app/external_indexer.py`.
2. Реализуй класс `ExternalIndexer`, который:
   - Принимает список URL.
   - Скачивает контент (через WebFetch или httpx).
   - Разбивает текст на чанки по 1000-2000 символов с перекрытием.
   - Генерирует эмбеддинги (через Ollama nomic-embed-text).
   - Сохраняет в таблицу `knowledge_nodes` с domain_id для 'AI Research'.
3. Добавь метод `index_url(url: str, domain: str = 'AI Research')`.
4. Проверь работу на примере документации (например, https://docs.anthropic.com/en/docs/welcome).

ВАЖНО: Используй ПЕРВЫЕ ПРИНЦИПЫ и БРИТВУ ОККАМА.
