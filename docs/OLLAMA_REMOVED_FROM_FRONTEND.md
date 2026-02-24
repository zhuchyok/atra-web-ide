# Удаление Ollama из Frontend

**Дата:** 26.01.2026  
**Изменение:** Ollama полностью удален из frontend, показывается только Victoria и MLX

---

## ✅ Что изменилось

### Frontend (`frontend/src/App.svelte`)

**Было:**

- Проверял статус Ollama
- Показывал "AI: Ollama (Fallback)" или "AI: Ollama (Victoria Offline)"

**Стало:**

- Проверяет только Victoria и MLX
- Показывает "Victoria: Online" или "AI: MLX (Victoria Offline)"

---

## 🔧 Изменения в коде

### 1. Убрана проверка Ollama

**Было:**

```javascript
if (
  data.victoria?.status === "unhealthy" &&
  data.ollama?.status === "healthy"
) {
  victoriaStatus = "fallback";
}
```

**Стало:**

```javascript
victoriaStatus = data.victoria?.status || "unknown";
mlxStatus = data.mlx?.status || "unknown";
```

### 2. Обновлено отображение статуса

**Было:**

- "AI: Ollama (Fallback)"
- "AI: Ollama (Victoria Offline)"

**Стало:**

- "Victoria: Online" (если Victoria доступна)
- "AI: MLX (Victoria Offline)" (если Victoria недоступна, но MLX доступен)
- "Victoria: Offline" (если оба недоступны)

---

## 📊 Новая логика статуса

1. **Victoria: Online** - Victoria доступна
2. **AI: MLX (Victoria Offline)** - Victoria недоступна, но MLX доступен
3. **Victoria: Offline** - Оба недоступны

---

## 🎯 Преимущества

1. **Консистентность:**
   - Frontend соответствует backend логике
   - Нет упоминаний Ollama

2. **Ясность:**
   - Понятно, какой сервис используется
   - MLX показывается как fallback

3. **Простота:**
   - Меньше проверок
   - Проще логика

---

_Изменения применены: 26.01.2026_
