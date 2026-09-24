🎯 ЦЕЛЬ: Реализовать Hybrid Search v2 в enhanced_search.py.

1. Изучи текущую реализацию в `knowledge_os/app/enhanced_search.py`.
2. Добавь поддержку PostgreSQL `tsvector` и `ts_rank` для полнотекстового поиска (BM25).
3. Реализуй комбинированный скоринг в `hybrid_search`: Score = (Vector*Similarity * 0.7) + (BM25*Score * 0.3).
4. Убедись, что поиск корректно работает с доменными фильтрами.
5. Проверь результат на тестовых запросах.

ВАЖНО: Следуй чеклисту BRAINSTORMING и DEBUBGING если возникнут ошибки.
