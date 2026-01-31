# 🚀 Руководство по миграции на Mac Studio M4 Max

**Дата:** 2025-01-XX  
**Цель:** Перенос всей корпорации ATRA на Mac Studio M4 Max (128GB/2TB)

---

## 📋 ЧТО МИГРИРУЕТСЯ

### Знания и данные:
- ✅ 40+ экспертов (experts)
- ✅ Все знания (knowledge_nodes)
- ✅ Домены (domains)
- ✅ Задачи (tasks)
- ✅ Логи обучения (expert_learning_logs)
- ✅ Логи взаимодействий (interaction_logs)
- ✅ OKR (okrs)
- ✅ Аномалии (anomalies)
- ✅ Симуляции (simulations)
- ✅ AI кэш (semantic_ai_cache)

### Агенты:
- ✅ Victoria Agent (Team Lead)
- ✅ Veronica Agent (Web Researcher)
- ✅ Nightly Learner (обучение экспертов)

### Инфраструктура:
- ✅ MLX API Server (все модели)
- ✅ Knowledge OS (PostgreSQL + API + Worker)
- ✅ Мониторинг (Prometheus + Grafana)

---

## 🎯 ПОШАГОВАЯ ИНСТРУКЦИЯ

### Этап 1: Подготовка (Mac Studio M4 Max)

1. **Установите Docker Desktop:**
   ```bash
   # Скачайте и установите Docker Desktop для Mac
   # https://www.docker.com/products/docker-desktop
   ```

2. **Установите модели:**
   ```bash
   ./scripts/install_models_mac_studio.sh
   ```
   
   Или вручную:
   ```bash
   python3 scripts/setup_all_hf_models_mac_studio.py
   ```

3. **Настройте .env:**
   ```bash
   cp .env.example.mac-studio .env
   nano .env  # Заполните значения
   ```

### Этап 2: Запуск инфраструктуры

```bash
# Запуск всех сервисов
./scripts/start_mac_studio_full.sh

# Или вручную:
docker-compose up -d
```

### Этап 3: Миграция данных с сервера

```bash
# Убедитесь, что knowledge-os-db запущен
docker-compose ps knowledge-os-db

# Запустите миграцию
python3 scripts/migration/migrate_to_mac_studio.py
```

### Этап 4: Проверка

```bash
# Проверка всех сервисов
./scripts/check_all_services.sh

# Проверка MLX API
curl http://localhost:11434/

# Проверка Knowledge OS
curl http://localhost:8000/

# Проверка агентов
docker-compose logs -f victoria-agent veronica-agent
```

---

## 📊 АРХИТЕКТУРА

```
Mac Studio M4 Max
├── 🐳 Docker Network
│   ├── mlx-api-server:11434      # MLX API Server
│   ├── knowledge-os-db:5432       # PostgreSQL
│   ├── knowledge-os-api:8000      # Knowledge OS API
│   ├── victoria-agent             # Victoria Agent
│   ├── veronica-agent             # Veronica Agent
│   ├── nightly-learner            # Nightly Learner
│   ├── prometheus:9090            # Prometheus
│   └── grafana:3000               # Grafana
│
├── 📚 Knowledge OS
│   ├── 40+ экспертов
│   ├── Все знания
│   └── Все данные корпорации
│
└── 🤖 Агенты
    ├── Victoria (Team Lead) + облачные AI
    └── Veronica (Web Researcher) + облачные AI
```

---

## 🔧 УПРАВЛЕНИЕ

### Запуск всех сервисов:
```bash
docker-compose up -d
```

### Остановка:
```bash
docker-compose down
```

### Просмотр логов:
```bash
docker-compose logs -f [service_name]
```

### Перезапуск сервиса:
```bash
docker-compose restart [service_name]
```

---

## 🔍 МОНИТОРИНГ

- **Grafana:** http://localhost:3000 (admin/atra2025)
- **Prometheus:** http://localhost:9090
- **MLX API Server:** http://localhost:11434
- **Knowledge OS API:** http://localhost:8000

---

## ✅ ПРОВЕРКА РАБОТОСПОСОБНОСТИ

1. ✅ Все контейнеры запущены: `docker-compose ps`
2. ✅ MLX API отвечает: `curl http://localhost:11434/`
3. ✅ Knowledge OS доступна: `curl http://localhost:8000/`
4. ✅ Агенты работают: проверьте логи
5. ✅ Данные мигрированы: проверьте в Grafana

---

## 🐛 УСТРАНЕНИЕ ПРОБЛЕМ

### Docker daemon не запущен:
```bash
# Запустите Docker Desktop
open -a Docker
```

### Модели не найдены:
```bash
# Установите модели
./scripts/install_models_mac_studio.sh
```

### База данных не запускается:
```bash
# Проверьте логи
docker-compose logs knowledge-os-db

# Пересоздайте volume (ОСТОРОЖНО - потеряете данные!)
docker-compose down -v
docker-compose up -d knowledge-os-db
```

---

*Создано командой экспертов ATRA*

