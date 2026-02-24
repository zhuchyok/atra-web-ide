# Mac Studio — документация и скрипты

**Проект:** atra-web-ide. Здесь всё по Mac Studio: настройки, серверы, сотрудники, Victoria, туннели.

## Главный справочник

👉 **[MAC_STUDIO_AND_SERVERS_KNOWLEDGE.md](./MAC_STUDIO_AND_SERVERS_KNOWLEDGE.md)** — серверы, SSH, туннель, Local Router, Victoria, иерархия сотрудников, скрипты.

## Быстрый старт

1. **Конфиг:** скопировать `.env.mac-studio.example` → `.env.mac-studio`, подставить пароли.
2. **Запуск на Mac Studio:** `./scripts/start_mac_studio_full.sh` или см. `START_MAC_STUDIO_INSTRUCTIONS.md`.
3. **Victoria + Cursor:** `bash scripts/victoria/victoria_auto_connect.sh` (поддерживает atra-web-ide).
4. **Синк экспертов с сервера:** `knowledge_os/scripts/server_knowledge_sync.py` (см. справочник).

## Документы в этой папке

| Файл                                 | Описание                                    |
| ------------------------------------ | ------------------------------------------- |
| MAC_STUDIO_AND_SERVERS_KNOWLEDGE     | Сводка по серверам, Mac Studio, сотрудникам |
| VICTORIA_CURSOR_SETUP                | Подключение Victoria к Cursor               |
| MAC_STUDIO_M4_MODELS_GUIDE           | Модели для M4 Max                           |
| MAC_STUDIO_MIGRATION_GUIDE           | Миграция на Mac Studio                      |
| DOCKER*AFTER_MIGRATION, MIGRATION*\* | Миграция, агенты, Docker                    |

## Скрипты (корень / scripts)

- `start_mac_studio_full.sh` — полный старт инфраструктуры
- `copy_mlx_server_to_macstudio.py` — копирование MLX API server
- `scan_mac_studio_models.sh`, `scan_models_mac_studio.sh` — скан моделей
- `install_models_mac_studio.sh` — установка моделей
- `migration/*` — миграция на Mac Studio
- `victoria/victoria_auto_connect.sh` — автоподключение Victoria (в т.ч. atra-web-ide)
