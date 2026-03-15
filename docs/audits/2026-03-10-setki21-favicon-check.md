# Проверка фавиконов на сайтах setki21 — 10 марта 2026

**Дата:** 2026-03-10  
**Проверяющий:** Victoria (ATRA Core)  
**Цель:** Убедиться, что каждый сайт отдает свой уникальный фавикон без 404 ошибок

---

## Проверенные сайты

1. https://www.setki21.ru/
2. https://setkimoskitki.ru/
3. https://xn--e1agaahbbnszfhh.xn--p1ai/ (сетки-москитки.рф)

---

## Результаты проверки

### 1. HTML-код страниц

Все три сайта возвращают **идентичный HTML-код** с одинаковыми фавиконами:

```html
<link
  rel="icon"
  type="image/x-icon"
  href="/favicon.ico?v=default&h="
  data-hid="favicon"
/>
<link
  rel="shortcut icon"
  href="/favicon.ico?v=default&h="
  data-hid="shortcut"
/>
<link
  rel="apple-touch-icon"
  href="/favicon.ico?v=default&h="
  data-hid="apple"
/>
```

**Вывод:** Все три сайта ссылаются на один и тот же путь `/favicon.ico`.

---

### 2. HTTP-заголовки фавиконов

#### www.setki21.ru/favicon.ico

```
HTTP/2 200
content-type: image/vnd.microsoft.icon
content-length: 4286
etag: "10be-uq/2yXzQYyL5aAU8hfjqluarOmA"
last-modified: Mon, 09 Mar 2026 22:00:51 GMT
```

#### setkimoskitki.ru/favicon.ico

```
HTTP/2 200
content-type: image/vnd.microsoft.icon
content-length: 4286
etag: "10be-uq/2yXzQYyL5aAU8hfjqluarOmA"
last-modified: Mon, 09 Mar 2026 22:00:51 GMT
```

#### xn--e1agaahbbnszfhh.xn--p1ai/favicon.ico

```
HTTP/2 200
content-type: image/vnd.microsoft.icon
content-length: 4286
etag: "10be-uq/2yXzQYyL5aAU8hfjqluarOmA"
last-modified: Mon, 09 Mar 2026 22:00:51 GMT
```

**Вывод:**

- ✅ Все фавиконы отдаются с кодом **200** (нет 404 ошибок)
- ✅ Content-Type правильный: `image/vnd.microsoft.icon`
- ❌ Все три файла имеют **одинаковый ETag** и размер (4286 байт)

---

### 3. MD5-хеш файлов

```bash
www.setki21.ru/favicon.ico:            086ce7acee9ebdbd3be7db7b6e51beae
setkimoskitki.ru/favicon.ico:          086ce7acee9ebdbd3be7db7b6e51beae
xn--e1agaahbbnszfhh.xn--p1ai/favicon.ico: 086ce7acee9ebdbd3be7db7b6e51beae
```

**Вывод:** Все три сайта отдают **побайтово идентичный файл**.

---

### 4. Open Graph изображения

Все три сайта ссылаются на **один и тот же логотип**:

```html
<meta
  property="og:image"
  content="https://www.setki21.ru/images/logo_final_v58.png"
/>
```

**Проблема:** Даже в Open Graph meta-тегах URL жестко прописан на `www.setki21.ru`, а не на соответствующий домен.

---

## Итоговые выводы

### ❌ Критические проблемы

1. **Все три сайта используют ОДИН И ТОТ ЖЕ фавикон**
   - Файлы идентичны (MD5: `086ce7acee9ebdbd3be7db7b6e51beae`)
   - ETag совпадает: `"10be-uq/2yXzQYyL5aAU8hfjqluarOmA"`
   - Размер одинаковый: 4286 байт

2. **Open Graph изображения всех сайтов ссылаются на www.setki21.ru**
   - При шаринге в соцсетях все три сайта будут показывать логотип основного домена

3. **HTML-код страниц полностью идентичен**
   - Нет tenant-специфичной логики для фавиконов
   - Параметр `?v=default&h=` не влияет на различие

### ✅ Что работает

- Все фавиконы отдаются без 404 ошибок
- Content-Type корректный для всех файлов
- HTTP-статус 200 для всех запросов

---

## Рекомендации для исправления

### 1. Добавить tenant-специфичные фавиконы

В коде Nuxt-приложения нужно динамически подставлять фавиконы по tenant_id:

```javascript
// nuxt.config.ts или composable для head
const tenantConfig = useTenantConfig();

head: {
  link: [
    {
      rel: "icon",
      type: "image/x-icon",
      href: tenantConfig.value.branding?.favicon_url || "/favicon.ico",
    },
  ];
}
```

### 2. Загрузить уникальные фавиконы в БД

Для каждого tenant (dealer) загрузить свой фавикон в `/uploads/` и прописать путь в таблице `dealers`:

```sql
UPDATE dealers
SET branding = jsonb_set(
  COALESCE(branding, '{}'),
  '{favicon_url}',
  '"/uploads/setkimoskitki-favicon.ico"'
)
WHERE dealer_name = 'setkimoskitki';
```

### 3. Исправить Open Graph изображения

Использовать полный URL текущего домена:

```javascript
const siteUrl = useRequestURL().origin;
const ogImage = tenantConfig.value.branding?.logo_url
  ? `${siteUrl}${tenantConfig.value.branding.logo_url}`
  : `${siteUrl}/images/logo_final_v58.png`;
```

### 4. Добавить кеш-бастинг для фавиконов

Использовать hash фавикона вместо generic `?v=default&h=`:

```javascript
const faviconUrl = tenantConfig.value.branding?.favicon_url;
const faviconHash = tenantConfig.value.branding?.favicon_hash || "default";
href: `${faviconUrl}?v=${faviconHash}`;
```

---

## Связанные документы

- `docs/SETKI21_NPM_SOURCE_OF_TRUTH.md` — настройка Nginx Proxy Manager для multi-tenant
- `docs/audits/2026-03-10-setki21-logo-favicon-check.md` — проверка логотипов
- `docs/plans/2026-03-06-setki21-deploy-verify-design.md` — дизайн multi-tenant системы

---

**Дата создания:** 2026-03-10 01:13 MSK  
**Статус:** Проблема подтверждена — требуется исправление
