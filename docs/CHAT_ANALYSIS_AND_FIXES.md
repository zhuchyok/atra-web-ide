# Анализ диалога с Victoria и исправления

## Что видно из вывода чата (терминал)

### 1. Запрос «привет»
- **Ответ:** «Надо ответить на приветственное запрос»
- **Проблема:** «модель: не указана» — в ответе не отображается используемая модель.

### 2. Запрос «изучи и сиправь найденные проблеммы в http://localhost:8501/...»
- **Ответ:** Очень длинный сырой вывод:
  - JSON с инструментами **web_search**, **swarm_intelligence**, **consensus**, **tree_of_thoughts** (этих инструментов нет в ALLOWED_TOOLS).
  - Блок «Врачебная задача», «СЕДАРДАН», «CMP», **psych_assessment**, **patient_interview**, **therapy_technique**, **ethical_dilemma** и т.д. — типичные галлюцинации модели.
- **Проблемы:**
  1. Пользователю показывается сырой «мусорный» вывод вместо короткого нормализованного ответа или сообщения об ошибке.
  2. Модель снова «не указана».

## Причины (по коду)

1. **Путь Victoria Enhanced (async_mode=202)**  
   В `_run_task_background` для Enhanced результат пишется как есть:
   `store["output"] = enhanced_result.get("result") or ""`  
   Нормализация `_normalize_output_for_user` для этого пути не вызывается при записи. В `get_run_status` нормализация вызывается при отдаче, но маркеров мусора не хватает для такого текста.

2. **Недостаточно маркеров мусора**  
   В `_normalize_output_for_user` и в `scripts/victoria_chat.py` список `garbage_markers` не содержал «Врачебная задача», «psych_assessment», «patient_interview», «web_search», «swarm_intelligence», «consensus», «tree_of_thoughts», «СЕДАРДАН», «CMP» и т.д., поэтому длинный галлюцинированный вывод не распознавался как мусор.

3. **Модель не указана**  
   В `get_run_status` для `knowledge.metadata` уже выставляется `model_used` при отсутствии. Если в чате всё равно «модель: не указана», возможны старый билд сервера или иная ветка ответа (например, другой формат `knowledge`). Имеет смысл гарантировать подстановку `model_used` и в ответе Enhanced.

## Вносимые исправления

1. **Нормализовать вывод Enhanced при записи в store**  
   В `_run_task_background` для Enhanced:
   `store["output"] = _normalize_output_for_user(enhanced_result.get("result") or "")`

2. **Расширить garbage_markers** (и в `victoria_server.py`, и в `scripts/victoria_chat.py`):
   - «Врачебная задача», «СЕДАРДАН», «CMP», «ЗАПИТАНЯ», «ОБРАТУРЫ»
   - «psych_assessment», «patient_interview», «therapy_technique», «ethical_dilemma», «empathetic_communication»
   - «web_search», «swarm_intelligence», «consensus», «tree_of_thoughts»

3. **Жёсткое ограничение длины в get_run_status**  
   После нормализации: если длина `output` всё ещё > 2000 символов, обрезать до 2000 и дописать «[... ответ обрезан ...]».

4. **Гарантировать model_used в ответе**  
   Уже делается в `get_run_status`; при необходимости явно выставить `metadata["model_used"]` и для Enhanced при формировании `knowledge` в `_run_task_background`.

После этих правок:
- длинные галлюцинированные ответы должны заменяться коротким сообщением или обрезаться;
- в чате должна стабильно отображаться модель (или «local» по умолчанию).
