# Runbook: Setki21 Deploy Verification Failed

## Симптом

После `./scripts/deploy_setki21_site_vds.sh` деплой завершился ошибкой верификации, либо вручную видно, что `https://www.setki21.ru/` отдаёт старую сборку.

> **Текущий продакшен-стек:** Сейчас в продакшене используются **setki21-web-new:3000** и **setki21-api-new:8080**. Для этого стека в NPM должно быть **Forward: setki21-web-new, Port: 3000**. Если на всех сайтах белый экран — см. **docs/runbooks/SETKI21_WHITE_SCREEN.md** и **docs/SETKI21_NPM_SOURCE_OF_TRUTH.md**. Ниже описан вариант со статикой **setki21-site:80** (альтернативный/старый).

## Быстрая причина

Чаще всего живая маршрутизация `www.setki21.ru` в NPM смотрит не туда. Для стека со статикой — на **setki21-site:80**; для текущего Nuxt-стека — на **setki21-web-new:3000** (см. SETKI21_NPM_SOURCE_OF_TRUTH.md).

## Что проверить

1. Открой NPM: `http://45.10.43.248:81`
2. Перейди: `Proxy Hosts` -> `www.setki21.ru`
3. На вкладке `Details` проверь:
   - `Forward Hostname / IP`: `setki21-site`
   - `Forward Port`: `80`
4. Если указано что-то другое, исправь и нажми `Save`.

## DNS

Проверь, что домен указывает на нужный VDS:

```bash
dig +short www.setki21.ru
```

Ожидается: `45.10.43.248`

## CDN

Если перед сайтом стоит Cloudflare или другой CDN, сделай `Purge Cache` для `www.setki21.ru`, затем повтори проверку.

## Ручная сверка сборки

Проверь хэш CSS на VDS:

```bash
ssh root@45.10.43.248 "grep -o 'entry\.[^\"]*\.css' /home/atra/app/setki21_site/index.html | head -1"
```

Проверь хэш CSS у живого сайта:

```bash
curl -sS "https://www.setki21.ru/" | grep -o 'entry\.[^\"]*\.css' | head -1
```

Если хэши различаются, живой трафик по-прежнему идёт не в `setki21-site`.

## Полный чеклист

Подробная диагностика: `docs/SETKI21_SITE_DEPLOY_VDS.md` (§7).
