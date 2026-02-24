# 🚀 Выполнить на Mac Studio

**Дата:** 2026-01-25

---

## ⚡ БЫСТРЫЙ СТАРТ

### На Mac Studio (в терминале Cursor) выполните:

```bash
cd ~/Documents/atra-web-ide
bash RUN_ON_MAC_STUDIO.sh
```

Или напрямую:

```bash
cd ~/Documents/atra-web-ide
bash scripts/start_all_on_mac_studio.sh
```

---

## 📋 ЧТО БУДЕТ СДЕЛАНО

1. ✅ Проверка Docker Desktop
2. ✅ Создание сети atra-network
3. ✅ Проверка MLX/Ollama API Server
4. ✅ Импорт данных с Mac Studio (если есть бэкап)
5. ✅ Запуск всех Docker контейнеров
6. ✅ Проверка доступности всех сервисов

---

## ⏱️ ВРЕМЯ ВЫПОЛНЕНИЯ

~1-2 минуты

---

## ✅ ПОСЛЕ ЗАПУСКА

Все сервисы будут доступны:

- Локально: `http://localhost:8010` (Victoria), `http://localhost:8011` (Veronica)
- С Mac Studio: `http://192.168.1.64:8010`, `http://192.168.1.64:8011`
- Из интернета: `http://185.177.216.15:8010` (через SSH туннель)

---

_Документ создан 2026-01-25_
