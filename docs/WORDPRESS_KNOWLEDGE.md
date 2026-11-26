# WordPress — operational knowledge (curator bible)

Изучено по официальным handbook’ам developer.wordpress.org / wordpress.org/documentation (срез 2026-11).  
Плюс боевые выводы с 100kna.ru (Reboot + Yoast + Clearfy + Gutenberg).

Цель: агент не «угадывает WP», а опирается на контракты ядра и известные ловушки тем/плагинов.

---

## 1. Карта документации (куда смотреть)

| Тема                      | Канон                                                                                    |
| ------------------------- | ---------------------------------------------------------------------------------------- |
| Пользователь / публикация | https://wordpress.org/documentation/                                                     |
| REST API                  | https://developer.wordpress.org/rest-api/                                                |
| Auth REST                 | https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/              |
| Global REST params        | https://developer.wordpress.org/rest-api/using-the-rest-api/global-parameters/           |
| Endpoints                 | https://developer.wordpress.org/rest-api/reference/                                      |
| Nonces                    | https://developer.wordpress.org/apis/security/nonces/                                    |
| Roles / caps              | https://developer.wordpress.org/apis/security/roles-and-capabilities/ (связанный раздел) |
| Meta boxes                | https://developer.wordpress.org/plugins/metadata/custom-meta/                            |
| Template hierarchy        | https://developer.wordpress.org/themes/basics/template-hierarchy/                        |
| Block Editor              | https://developer.wordpress.org/block-editor/                                            |
| Themes                    | https://developer.wordpress.org/themes/                                                  |
| Plugins                   | https://developer.wordpress.org/plugins/                                                 |

«Всё о WordPress» = эти handbook’и + Codex/Reference functions. Ниже — сжатый рабочий слой.

---

## 2. Модель данных (ядро)

- **Post types:** `post`, `page`, `attachment`, `revision`, `nav_menu_item`, плюс CPT плагинов.
- **Контент страницы/поста** в БД: `post_content` (HTML или block markup `<!-- wp:... -->`).
- **Meta:** `wp_postmeta` — тема/плагины (Yoast, Reboot hide_elements, thumbnail flags).
- **Taxonomies:** categories/tags + custom.
- **Media:** attachment post type; файл в `uploads/`; REST `/wp/v2/media`.
- **Users + capabilities:** права через `current_user_can()`, не через nonce.

Иерархия шаблонов темы решает, _какой PHP/HTML-файл_ рисует URL (page → `page-{slug}.php` → `page.php` → `singular.php` → `index.php`). Контент при этом всё равно из `post_content` + meta темы.

---

## 3. Два редактора = два канала сохранения

### A. Gutenberg (Block Editor) + REST

- UI пишет через `wp.data` → REST `POST /wp-json/wp/v2/pages/{id}` (или posts).
- Заголовок: `title` (raw в `context=edit`).
- Контент: `content` — **serialized blocks**, не «голый HTML без комментариев», если хотите сохранить блоки.
- Auth в админке: cookie + header **`X-WP-Nonce: wpApiSettings.nonce`** (action `wp_rest`).
- Без nonce REST считает пользователя гостем (user 0), даже если cookie есть.
- `context=edit` нужен для raw content / editable fields.
- Global: `_fields`, `_embed`, `_method` / `X-HTTP-Method-Override`.

**Application Passwords** (WP ≥ 5.6): Basic Auth по HTTPS для внешних скриптов (`curl --user "user:app_password"`). Предпочтительнее старых basic-auth плагинов.

### B. Classic `post.php` + meta boxes

- Meta boxes живут _внутри_ формы Update/Publish.
- Сохранение: `action=editpost` → `save_post` → тема/плагин читает `$_POST`.
- У чекбоксов: **неотмеченный чекбокс в POST не приходит**. Чтобы «снять» флаг, нужен механизм theme/plugin (`fields_to_save` + nonce), иначе старое значение может остаться или не обновиться.
- Gutenberg грузит meta boxes отдельным запросом `meta-box-loader=1&meta-box-loader-nonce=...`.
- **REST `content` update не сохраняет произвольные theme meta boxes**, если они не зарегистрированы в REST `register_post_meta` / не пишутся через `meta`.

### Боевой урок 100kna (Reboot)

Поле «скрыть элементы» (`hide_elements[title_h1]` и т.д.):

1. Нужны **`pages_hide_nonce`** + **`pages_hide_fields_to_save`** из meta-box-loader.
2. `hide_elements[title_h1]=checked` в FormData.
3. После toggle — **всегда пересчитать H1 на live** (`?nocache=`):
   - hide theme title + H1 в контенте = 1 H1;
   - hide theme title + в контенте только H2 = **0 H1** (сломали `/tseny/`).

Yoast title/description: отдельный канал (Yoast REST / bulk editor / `yoast_head_json`). Смена `post_content` ≠ автозаполнение SEO title.

---

## 4. REST — шпаргалка endpoints

| Ресурс            | Route                             |
| ----------------- | --------------------------------- |
| Pages             | `/wp/v2/pages`                    |
| Posts             | `/wp/v2/posts`                    |
| Media             | `/wp/v2/media`                    |
| Users             | `/wp/v2/users`                    |
| Search            | `/wp/v2/search`                   |
| Types/Statuses    | `/wp/v2/types`, `/wp/v2/statuses` |
| Revisions         | `/wp/v2/pages/{id}/revisions`     |
| Index / discovery | `/wp-json/`                       |

Типичный апдейт страницы из залогиненной админки (JS):

```js
fetch("/wp-json/wp/v2/pages/" + id, {
  method: "POST",
  credentials: "same-origin",
  headers: {
    "Content-Type": "application/json",
    "X-WP-Nonce": wpApiSettings.nonce,
  },
  body: JSON.stringify({ content: blockMarkup }),
});
```

`document.cookie` **не отдаёт HttpOnly** `wordpress_logged_in_*` — внешний curl с «куками из document.cookie» обычно **не** авторизован. Писать контент надо из браузерного контекста админки или через Application Password.

---

## 5. Nonces (безопасность)

- Не «один раз»: lifetime ~12–24ч (два тика).
- Не замена auth: всегда `current_user_can()`.
- Admin forms: `_wpnonce` + `check_admin_referer()`.
- REST cookie: nonce action **`wp_rest`**, header `X-WP-Nonce`.
- Theme custom boxes: свой `*_nonce` (как `pages_hide_nonce` у Reboot) — без него POST «тихо» не сохранит meta.

---

## 6. Gutenberg content — формат

Минимальный блок:

```html
<!-- wp:heading {"level":1} -->
<h1 class="wp-block-heading">Заголовок</h1>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Текст</p>
<!-- /wp:paragraph -->

<!-- wp:html -->
<div class="custom">...</div>
<!-- /wp:html -->
```

Картинка: блок `wp:image` с `id` медиатеки + `src` из uploads.

SEO-наполнение ≠ только Yoast: нужен **body** (лид, цена «от», FAQ, внутренние ссылки, CTA) + title/description. Конкуренты по окнам выигрывают таблицами комплектаций и ценой изделия — витрина «от ₽/м²» должна быть честной.

---

## 7. Тема vs контент (Reboot / классические темы)

- Theme title (H1 из `the_title`) и H1 в `post_content` легко дают **dual H1**.
- Решение: hide theme title **или** один H1 только в теме (без H1 в контенте).
- Thumbnail / hero: часто meta темы (`thumbnail_type` full/wide/fullscreen), не блок Cover.
- Customizer CSS / Additional CSS — отдельно от `post_content`.
- Clearfy и security-плагины могут закрывать `wp-login.php` и резать endpoints — проверять live, не по доке «чистого» WP.

---

## 8. SEO-слой (Yoast)

- Title / meta description / focus keyphrase хранятся в post meta Yoast.
- На фронте: `<title>`, `meta[name=description]`, `yoast_head_json` в REST.
- Bulk: Yoast admin / REST namespace плагина (если доступен).
- Оценка «OK» в админбаре ≠ позиция в Яндексе; проверять сниппет `view-source` / nocache.

---

## 9. Кэш и проверка «готово»

После правок всегда:

1. `?nocache=` или инкогнито.
2. Count `<h1>`, title, description, длина `.entry-content`.
3. Не верить только REST `ok:200` без live HTML.
4. После hide_elements — отдельный проход H1.

---

## 10. Роли (минимум)

| Capability (пример)            | Смысл                          |
| ------------------------------ | ------------------------------ |
| `edit_pages` / `publish_pages` | Править/публиковать страницы   |
| `upload_files`                 | Медиа                          |
| `manage_options`               | Настройки / многие SEO-плагины |

Application Password наследует caps пользователя.

---

## 11. Чеклист агента на WP-сайте

1. Залогинен ли браузер в `wp-admin`? Есть ли `wpApiSettings.nonce`?
2. Меняем **content** (REST) или **theme meta** (classic POST + theme nonce)?
3. Gutenberg markup или классический HTML?
4. Не затираем ли контент пустым `content` в classic `editpost`?
5. Yoast отдельно от body.
6. Live smoke: H1=1, meta, CTA, длина текста, картинки.
7. Clearfy/login-hide не ломаем массово.

---

## 12. Источники обновлять

При смене мажорной версии WP перечитывать:

- REST Authentication
- Block Editor «What’s new in Gutenberg»
- Template hierarchy (classic vs block themes)

Первый проход документации зафиксирован: 2026-11-22.  
Практика: 100kna.ru (Reboot + Yoast SEO + Clearfy Pro).
