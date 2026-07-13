# Setki21: Исправление автоматического получения SSL-сертификатов

**Дата:** 2026-03-09  
**Проблема:** При активации домена дилера через админку создаётся Proxy Host в NPM, но SSL-сертификат от Let's Encrypt не запрашивается автоматически.

---

## Симптомы

1. Пользователь вводит кириллический домен (например, `сеткимоскитки.рф`) в браузер
2. Браузер конвертирует его в Punycode (`xn--e1agaahbbnszfhh.xn--p1ai`)
3. Браузер пытается открыть **HTTPS** (по умолчанию)
4. HTTPS не работает (SSL handshake failed)
5. Браузер перенаправляет запрос в поисковую систему вместо открытия сайта

**HTTP работает**, но браузеры современные по умолчанию пытаются HTTPS, и при его отсутствии считают строку поисковым запросом.

---

## Корневая причина

В файле `moskit-api/src/npm.rs` функция `create_proxy_host()`:

- ✅ **Создаёт Proxy Host** в NPM
- ✅ **Конвертирует кириллицу в Punycode** (работает корректно)
- ❌ **НЕ запрашивает SSL-сертификат** от Let's Encrypt

Старый код использовал `"certificate_id": 0`, что означает "без сертификата". NPM API требует **отдельный запрос** для получения сертификата.

---

## Решение

### Что изменено в `moskit-api/src/npm.rs`:

1. **Добавлена структура `CertificateResponse`** для парсинга ответа NPM API
2. **Добавлен метод `request_ssl_certificate()`** - запрашивает сертификат от Let's Encrypt
3. **Добавлен метод `update_proxy_host_certificate()`** - привязывает полученный сертификат к Proxy Host
4. **Обновлён метод `create_proxy_host()`**:
   - Сначала создаёт Proxy Host без SSL
   - Затем запрашивает SSL-сертификат для обоих доменов (с www и без)
   - Привязывает сертификат к Proxy Host
   - Логирует все этапы для отладки

### Логика работы:

```
1. Создать/обновить Proxy Host (без SSL)
   ↓
2. Запросить SSL-сертификат от Let's Encrypt
   ↓ (успех)
3. Привязать сертификат к Proxy Host
   ↓
4. ✅ Домен доступен через HTTPS
```

### Обработка ошибок:

- Если SSL-запрос не удался → Proxy Host остаётся (HTTP работает), логируется предупреждение
- Если привязка сертификата не удалась → сертификат получен, но нужна ручная привязка в NPM UI
- Все ошибки логируются с уровнем `warn`, чтобы не блокировать активацию домена

---

## Деплой исправления

### 1. Перейти в проект setki-21:

```bash
cd /Users/bikos/Documents/dev/setki-21
```

### 2. Проверить изменения:

```bash
git diff moskit-api/src/npm.rs
```

### 3. Пересобрать Docker-образ:

```bash
# Для VDS (x86_64)
docker buildx build --platform linux/amd64 -t moskit-api:latest -f moskit-api/Dockerfile .
```

### 4. Сохранить образ и передать на VDS:

```bash
# Сохранить образ
docker save moskit-api:latest | gzip > /tmp/moskit-api-latest.tar.gz

# Передать на VDS
scp /tmp/moskit-api-latest.tar.gz root@45.10.43.248:/tmp/

# На VDS: загрузить образ
ssh root@45.10.43.248 "docker load < /tmp/moskit-api-latest.tar.gz"
```

### 5. Обновить docker-compose на VDS:

```bash
# Убедиться, что в docker-compose.yml используется правильный образ
ssh root@45.10.43.248 "cd /home/atra/app/setki21_src && docker-compose pull && docker-compose up -d --force-recreate setki21-api-new"
```

### 6. Проверить логи:

```bash
ssh root@45.10.43.248 "docker logs -f setki21-api-new"
```

---

## Тестирование

### 1. Активировать домен через админку:

```bash
# Через API (замените DEALER_ID на реальный UUID)
curl -X POST https://www.setki21.ru/api/v1/admin/dealers/DEALER_ID/activate_domain \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. Проверить логи на VDS:

```bash
ssh root@45.10.43.248 "docker logs setki21-api-new --tail 50 | grep -E 'SSL|certificate|xn--'"
```

Ожидаемые строки:

```
Domain сеткимоскитки.рф sent to NPM as punycode: xn--e1agaahbbnszfhh.xn--p1ai
Requesting SSL certificate for domains: ["xn--e1agaahbbnszfhh.xn--p1ai", "www.xn--e1agaahbbnszfhh.xn--p1ai"]
Successfully obtained SSL certificate, ID: 123
Updating Proxy Host 456 with certificate 123
Successfully updated Proxy Host 456 with certificate 123
✅ Domain сеткимоскитки.рф fully configured with HTTPS (Proxy Host: 456, Certificate: 123)
```

### 3. Проверить HTTPS:

```bash
curl -I https://сеткимоскитки.рф/
```

Ожидается: `HTTP/2 200` или `HTTP/1.1 200` с корректным SSL-сертификатом.

### 4. Проверить в браузере:

Открыть `сеткимоскитки.рф` (без протокола) → должен открыться сайт через HTTPS.

---

## Для существующего домена сеткимоскитки.рф

Домен уже создан в NPM, но без SSL. **Два варианта:**

### Вариант A: Вручную через NPM UI (быстрее):

1. Открыть http://45.10.43.248:81
2. **Proxy Hosts** → найти `xn--e1agaahbbnszfhh.xn--p1ai`
3. Вкладка **SSL** → Request a new SSL Certificate
4. Выбрать **Let's Encrypt**
5. Включить **Force SSL**
6. Сохранить

### Вариант B: Через API (после деплоя):

```bash
# В админке setki21 найти дилера "Сетки Москитки"
# Нажать кнопку "Активировать домен" (повторно)
# API обновит Proxy Host и запросит SSL
```

---

## Переменные окружения

Убедиться, что в `.env` проекта setki-21 или в docker-compose на VDS заданы:

```env
NPM_URL=http://atra-nginx-proxy:81/api
NPM_IDENTITY=zhuchyok@icloud.com
NPM_SECRET=Bik6007OS
NPM_FORWARD_API_HOST=setki21-api-new
```

Если их нет → добавить в `docker-compose.yml` для сервиса `setki21-api-new`.

---

## Связанные документы

- **Единый источник истины по NPM:** `docs/SETKI21_NPM_SOURCE_OF_TRUTH.md`
- **Runbook белого экрана:** `docs/runbooks/SETKI21_WHITE_SCREEN.md`
- **Деплой сайта:** `docs/SETKI21_SITE_DEPLOY_VDS.md`
- **Разбор API:** `docs/SETKI21_API_RAZBOR.md`

---

## Обновление Библии

После успешного деплоя добавить в:

1. **`docs/CHANGES_FROM_OTHER_CHATS.md`** (новый раздел):

   ```markdown
   ## XX. Автоматическое получение SSL-сертификатов для дилерских доменов (2026-03-09)

   - **Проблема:** При активации домена через админку создавался Proxy Host, но SSL не запрашивался.
   - **Решение:** В `moskit-api/src/npm.rs` добавлены методы автоматического запроса Let's Encrypt сертификата.
   - **Файлы:** `moskit-api/src/npm.rs`
   - **Документация:** `docs/SETKI21_AUTO_SSL_FIX.md`
   ```

2. **`docs/MASTER_REFERENCE.md`** (раздел Setki21 → NPM):

   ```markdown
   ### Автоматическая настройка SSL

   При активации домена дилера API автоматически:

   1. Создаёт Proxy Host в NPM (Punycode для кириллических доменов)
   2. Запрашивает SSL-сертификат от Let's Encrypt
   3. Привязывает сертификат к Proxy Host
      Подробно: `docs/SETKI21_AUTO_SSL_FIX.md`
   ```

---

## Чек-лист внедрения

- [ ] Изменения в `npm.rs` применены
- [ ] Docker-образ пересобран для x86_64
- [ ] Образ передан на VDS и загружен
- [ ] Контейнер `setki21-api-new` перезапущен с новым образом
- [ ] Протестирована активация нового домена (логи содержат "Successfully obtained SSL certificate")
- [ ] Для `сеткимоскитки.рф` SSL настроен вручную или через повторную активацию
- [ ] HTTPS работает в браузере (вводим домен без протокола → открывается сайт)
- [ ] Обновлены `CHANGES_FROM_OTHER_CHATS.md` и `MASTER_REFERENCE.md`

---

**Статус:** Исправление готово, требуется деплой на VDS.
