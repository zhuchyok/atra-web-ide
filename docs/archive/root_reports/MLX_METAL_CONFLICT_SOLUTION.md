# Решение проблемы Metal Command Buffer Conflict в MLX API Server

## Проблема

MLX Server падал с ошибкой:
```
-[AGXG16XFamilyCommandBuffer tryCoalescingPreviousComputeCommandEncoderWithConfig:nextEncoderClass:]:1090: 
failed assertion 'A command encoder is already encoding to this command buffer'
```

### Причина

Metal (Apple GPU framework) **не поддерживает одновременные операции** с одним command buffer. Когда несколько потоков пытаются выполнить `generate()` для одной модели одновременно через `run_in_executor()`, они конфликтуют на уровне Metal command buffer.

## Решение (Мировые практики Metal)

Согласно [Apple Metal Programming Guide](https://developer.apple.com/library/archive/documentation/Miscellaneous/Conceptual/MetalProgrammingGuide/Cmd-Submiss/Cmd-Submiss.html):

> **"At any point in time, only a single command encoder can be active and append commands into a command buffer. Each command encoder must be ended before another command encoder can be created for use with the same command buffer."**

### Реализация

1. **Сериализация генерации для одной модели** через `model_lock`
2. **Разные модели могут работать параллельно** (у каждой своя блокировка)
3. **Одна модель обрабатывает запросы последовательно** (защита от Metal конфликтов)

### Код решения

```python
# В mlx_api_server.py уже есть блокировки для каждой модели:
_model_locks = defaultdict(threading.Lock)  # Блокировки для каждой модели

# При генерации используем блокировку:
model_lock = _model_locks[model_key]

def generate_with_lock():
    """Генерация с блокировкой модели для защиты от Metal конфликтов"""
    with model_lock:
        return generate(model, tokenizer, prompt=request.prompt, max_tokens=request.max_tokens)

response_text = await asyncio.wait_for(
    loop.run_in_executor(None, generate_with_lock),
    timeout=300.0
)
```

## Преимущества

✅ **Защита от Metal конфликтов**: Только одна генерация для модели одновременно  
✅ **Параллелизм для разных моделей**: Разные модели могут работать параллельно  
✅ **Соответствие мировым практикам**: Следует рекомендациям Apple Metal  
✅ **Минимальные изменения**: Использует существующую инфраструктуру блокировок  

## Результат

- ✅ Нет ошибок Metal command buffer
- ✅ Стабильная работа при множественных запросах
- ✅ Поддержка параллельной работы разных моделей
- ✅ Последовательная обработка для одной модели (безопасно для Metal)

## Дата применения

2026-01-26
