# Проверка фото "Наши работы" на сайтах Setki21

**Дата проверки:** 9 марта 2026, 20:59 UTC  
**Проверено:** Виктория (ATRA Team Lead)

---

## 📋 Задача

Проверить наличие и отображение 4 фотографий в разделе "Наши работы" на трёх сайтах:

1. Основной сайт: https://www.setki21.ru/
2. Дилерский сайт: https://setkimoskitki.ru/
3. Punycode-домен: https://xn--e1agaahbbnszfhh.xn--p1ai/ (сеткимоскитки.рф)

---

## ✅ Результаты проверки

### 1. **Основной сайт: https://www.setki21.ru/** ✅

**Статус:** ✅ Работает корректно  
**HTTP-статус:** 200 OK

#### Фотографии в разделе "Наши работы":

- ✅ `/images/works/work-1.jpg` — **200 OK** (доступна)
- ✅ `/images/works/work-2.jpg` — **200 OK** (доступна)
- ✅ `/images/works/work-3.jpg` — **200 OK** (доступна)
- ✅ `/images/works/work-4.jpg` — **200 OK** (доступна)

**HTML-структура:**

```html
<h2
  class="text-3xl font-black mb-12 uppercase tracking-widest text-center text-white"
>
  Наши работы
</h2>
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
  <div
    class="aspect-square rounded-2xl overflow-hidden border-2 border-white/10 hover:border-brand-blue transition-colors cursor-zoom-in"
  >
    <img
      src="/images/works/work-1.jpg"
      alt="Пример установки москитной сетки в"
      class="w-full h-full object-cover hover:scale-110 transition-transform duration-500"
      loading="lazy"
    />
  </div>
  <!-- work-2.jpg, work-3.jpg, work-4.jpg аналогично -->
</div>
```

**Вывод:** Все 4 фотографии присутствуют и доступны.

---

### 2. **Дилерский сайт: https://setkimoskitki.ru/** ✅

**Статус:** ✅ Работает корректно  
**HTTP-статус:** 200 OK

#### Фотографии в разделе "Наши работы":

- ✅ `/images/works/work-1.jpg` — **200 OK** (доступна)
- ✅ `/images/works/work-2.jpg` — **200 OK** (доступна)
- ✅ `/images/works/work-3.jpg` — **200 OK** (доступна)
- ✅ `/images/works/work-4.jpg` — **200 OK** (доступна)

**HTML-структура:** Идентична основному сайту (используется та же система Nuxt.js, одинаковый шаблон).

**Вывод:** Все 4 фотографии присутствуют и доступны.

---

### 3. **Punycode-домен: https://xn--e1agaahbbnszfhh.xn--p1ai/ (сеткимоскитки.рф)** ❌

**Статус:** ❌ **Сайт недоступен (502 Bad Gateway)**  
**HTTP-статус:** 502 Bad Gateway

#### Детали проблемы:

- DNS-резолюция работает: `xn--e1agaahbbnszfhh.xn--p1ai` → `45.10.43.248`
- Сервер OpenResty возвращает 502 ошибку
- Проверка проводилась 3 раза с интервалом 2 секунды — результат стабильный: **502**

```
HTTP/2 502
server: openresty
date: Mon, 09 Mar 2026 20:59:48 GMT
content-type: text/html
content-length: 154
strict-transport-security: max-age=63072000;includeSubDomains; preload
```

**Вывод:** Невозможно проверить наличие фотографий из-за недоступности backend-сервера.

---

## 🔍 Техническая информация

### Структура фотографий в Schema.org (обе работающие сайта):

```json
{
  "@context": "https://schema.org",
  "@type": "ImageGallery",
  "name": "Наши работы — москитные сетки в",
  "description": "Фотографии установленных москитных сеток компанией в",
  "image": [
    {
      "@type": "ImageObject",
      "contentUrl": "https://www.setki21.ru/images/works/work-1.jpg",
      "name": "Установка москитной сетки в",
      "author": ""
    },
    {
      "@type": "ImageObject",
      "contentUrl": "https://www.setki21.ru/images/works/work-2.jpg",
      "name": "Установка москитной сетки в",
      "author": ""
    },
    {
      "@type": "ImageObject",
      "contentUrl": "https://www.setki21.ru/images/works/work-3.jpg",
      "name": "Установка москитной сетки в",
      "author": ""
    },
    {
      "@type": "ImageObject",
      "contentUrl": "https://www.setki21.ru/images/works/work-4.jpg",
      "name": "Установка москитной сетки в",
      "author": ""
    }
  ]
}
```

### Особенности отображения:

- Адаптивная сетка: 2 колонки на мобильных, 4 колонки на десктопе
- Lazy loading для оптимизации загрузки
- Hover-эффекты: увеличение при наведении (scale-110), изменение цвета border
- Все изображения имеют aspect-ratio 1:1 (квадратные)
- Border: 2px белая полупрозрачная рамка с переходом в синий при наведении

---

## 🚨 Проблемы и рекомендации

### ❌ Критическая проблема: сеткимоскитки.рф (Punycode-домен)

**Проблема:** Backend-сервер возвращает 502 Bad Gateway

**Возможные причины:**

1. Backend-приложение (Nuxt.js SSR) не запущено или упало
2. Проблема с проксированием в OpenResty/Nginx
3. Upstream-сервер не отвечает
4. Ошибка в конфигурации виртуального хоста для этого домена

**Рекомендации по устранению:**

#### 1. Проверить статус backend-процесса на сервере

```bash
ssh root@45.10.43.248
pm2 list
# или
systemctl status setki-backend
docker ps | grep setki
```

#### 2. Проверить логи OpenResty/Nginx

```bash
tail -f /var/log/nginx/error.log
tail -f /var/log/openresty/error.log
```

#### 3. Проверить конфигурацию для Punycode-домена

```bash
cat /etc/nginx/sites-enabled/xn--e1agaahbbnszfhh.xn--p1ai.conf
# или
cat /usr/local/openresty/nginx/conf/vhosts/xn--e1agaahbbnszfhh.xn--p1ai.conf
```

#### 4. Проверить upstream в конфигурации

```nginx
upstream setki_backend {
    server 127.0.0.1:3000;  # Nuxt.js SSR
    # или
    server unix:/var/run/setki.sock;
}
```

#### 5. Перезапустить backend-приложение

```bash
pm2 restart setki-app
# или
systemctl restart setki-backend
```

#### 6. Проверить доступность порта backend

```bash
netstat -tlnp | grep 3000
# или
ss -tlnp | grep 3000
```

---

## 📊 Сводная таблица

| Сайт                 | Статус    | work-1.jpg | work-2.jpg | work-3.jpg | work-4.jpg | Примечание            |
| -------------------- | --------- | ---------- | ---------- | ---------- | ---------- | --------------------- |
| **www.setki21.ru**   | ✅ 200 OK | ✅ 200     | ✅ 200     | ✅ 200     | ✅ 200     | Все фото отображаются |
| **setkimoskitki.ru** | ✅ 200 OK | ✅ 200     | ✅ 200     | ✅ 200     | ✅ 200     | Все фото отображаются |
| **сеткимоскитки.рф** | ❌ 502    | ❌ N/A     | ❌ N/A     | ❌ N/A     | ❌ N/A     | Backend недоступен    |

---

## 📝 Заключение

### Работает корректно:

- ✅ **www.setki21.ru** — 4 фотографии присутствуют и загружаются
- ✅ **setkimoskitki.ru** — 4 фотографии присутствуют и загружаются

### Требует исправления:

- ❌ **сеткимоскитки.рф (xn--e1agaahbbnszfhh.xn--p1ai)** — сайт недоступен (502 Bad Gateway)

**Приоритет:** Высокий — пользователи не могут получить доступ к сайту.

**Следующие шаги:**

1. Немедленно проверить статус backend-процесса на сервере 45.10.43.248
2. Изучить логи для выявления причины сбоя
3. Перезапустить backend-приложение при необходимости
4. После восстановления сервиса повторить проверку фотографий

---

**Отчёт составлен:** Виктория, Team Lead ATRA Core  
**Дата:** 9 марта 2026, 20:59 UTC  
**Инструменты:** curl, WebFetch, DNS host lookup
