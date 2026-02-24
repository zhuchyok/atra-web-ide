# 🔧 Решение проблемы с Docker Daemon

**Проблема:** `Cannot connect to the Docker daemon at unix:///Users/bikos/.docker/run/docker.sock`

---

## 🔍 ДИАГНОСТИКА

### 1. Проверьте Docker Desktop

```bash
# Проверьте, запущен ли Docker Desktop
ps aux | grep -i "docker desktop" | grep -v grep

# Проверьте сокет
ls -la /Users/bikos/.docker/run/docker.sock
```

### 2. Если Docker Desktop запущен, но сокет недоступен:

**Решение 1: Перезапустить Docker Desktop**

1. Закройте Docker Desktop полностью (Quit из меню)
2. Подождите 10 секунд
3. Запустите Docker Desktop заново
4. Дождитесь полного запуска (иконка в меню должна быть зеленая)

**Решение 2: Проверить права доступа**

```bash
# Проверить права на сокет
ls -la /Users/bikos/.docker/run/docker.sock

# Если нужно, исправить права
sudo chmod 666 /Users/bikos/.docker/run/docker.sock
```

**Решение 3: Использовать альтернативный путь**

```bash
# Попробовать через /var/run/docker.sock (если доступен)
export DOCKER_HOST=unix:///var/run/docker.sock
docker ps
```

---

## ✅ БЫСТРОЕ РЕШЕНИЕ

### Шаг 1: Полностью перезапустить Docker Desktop

1. **Закрыть Docker Desktop:**
   - Нажмите на иконку Docker в меню (верхняя панель)
   - Выберите "Quit Docker Desktop"
   - Подождите 10-15 секунд

2. **Запустить Docker Desktop:**
   - Откройте Docker Desktop из Applications
   - Дождитесь полного запуска (30-60 секунд)
   - Иконка должна стать зеленой

3. **Проверить подключение:**

   ```bash
   docker ps
   ```

4. **Если работает, перезапустить Victoria:**
   ```bash
   cd /Users/bikos/Documents/atra-web-ide
   docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent
   ```

---

## 🔧 АЛЬТЕРНАТИВНЫЕ РЕШЕНИЯ

### Если Docker Desktop не запускается:

**Вариант 1: Переустановить Docker Desktop**

- Скачайте последнюю версию с docker.com
- Установите заново

**Вариант 2: Использовать Docker через Colima (альтернатива)**

```bash
# Установить Colima
brew install colima docker docker-compose

# Запустить Colima
colima start

# Проверить
docker ps
```

**Вариант 3: Использовать Podman (альтернатива)**

```bash
brew install podman
podman machine start
```

---

## 📋 ПРОВЕРКА ПОСЛЕ РЕШЕНИЯ

После того, как Docker заработает:

```bash
# 1. Проверить Docker
docker ps

# 2. Перезапустить Victoria
cd /Users/bikos/Documents/atra-web-ide
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent

# 3. Проверить логи (должно быть подключение к БД)
docker logs victoria-agent | grep -i "database\|эксперты\|fallback"

# 4. Проверить health
curl http://localhost:8010/health
```

---

## 🚨 ЕСЛИ НИЧЕГО НЕ ПОМОГАЕТ

1. **Перезагрузите Mac Studio:**

   ```bash
   sudo reboot
   ```

2. **После перезагрузки:**
   - Запустите Docker Desktop
   - Дождитесь полного запуска
   - Выполните команду перезапуска Victoria

---

## ✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После успешного перезапуска Victoria:

- ✅ Подключение к БД `knowledge_postgres`
- ✅ В логах: `🔌 Использую DATABASE_URL для подключения к экспертам корпорации`
- ✅ НЕ должно быть: `⚠️ DATABASE_URL не настроен` или `fallback`
