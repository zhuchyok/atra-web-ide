# Setki21 Deploy Verification — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** После деплоя Setki21 автоматически проверять, что живой www.setki21.ru отдаёт ту же сборку, что на VDS; при провале — exit 1 и ссылка на runbook; runbook с указанием, где править NPM.

**Architecture:** В конец deploy_setki21_site_vds.sh добавлен шаг 5 (верификация): сравнение хэша entry.\*.css из index.html на VDS и из curl https://www.setki21.ru/. Переменная SKIP_SETKI21_VERIFY=1 отключает проверку. Runbook в docs/runbooks/ — короткие шаги и ссылка на SETKI21_SITE_DEPLOY_VDS §7.

**Tech Stack:** Bash, curl, SSH, grep. Документация: Markdown.

**Design doc:** docs/plans/2026-03-06-setki21-deploy-verify-design.md

---

### Task 1: Runbook при падении верификации

**Files:**

- Create: `docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md`

**Step 1:** Создать каталог `docs/runbooks/`, если его нет.

**Step 2:** Создать файл `docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md` с содержимым по дизайну §4: симптом, проверка NPM (URL http://45.10.43.248:81, путь Proxy Hosts → www.setki21.ru → Details, Forward setki21-site:80), DNS, CDN, повторная проверка, ссылка на SETKI21_SITE_DEPLOY_VDS §7.

**Step 3:** Убедиться, что в runbook явно указано «где править»: NPM → Proxy Hosts → www.setki21.ru → Details → Forward Hostname: setki21-site, Port: 80.

---

### Task 2: Шаг верификации в deploy_setki21_site_vds.sh

**Files:**

- Modify: `scripts/deploy_setki21_site_vds.sh`

**Step 1:** После блока «=== 4. Перезапуск setki21-site ===» и перед финальным echo "Готово..." добавить блок «=== 5. Верификация: живой сайт = сборка на VDS ===».

**Step 2:** В начале блока: если `[ -n "$SKIP_SETKI21_VERIFY" ]` и значение = 1 (или непустое), вывести «Верификация пропущена. Проверь вручную: docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md» и перейти к финальному echo (не выполнять проверку).

**Step 3:** Иначе: по SSH выполнить `grep -o 'entry\.[^"]*\.css' /home/atra/app/setki21_site/index.html | head -1`, сохранить вывод в переменную (например VDS_HASH).

**Step 4:** Выполнить `curl -sS --max-time 15 "https://www.setki21.ru/" | grep -o 'entry\.[^"]*\.css' | head -1`, сохранить в LIVE_HASH.

**Step 5:** Сравнить VDS_HASH и LIVE_HASH. Если равны — echo «Верификация OK: живой сайт отдаёт ту же сборку.» и выйти 0. Если не равны или одна из команд не вернула значение — echo сообщение об ошибке и «Runbook: docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md», exit 1.

**Step 6:** Проверить скрипт вручную: запуск с деплоем (или без, если уже задеплоено) и без SKIP_SETKI21_VERIFY; затем с SKIP_SETKI21_VERIFY=1 — верификация должна пропускаться.

---

### Task 3: Ссылка на runbook в документации деплоя

**Files:**

- Modify: `docs/SETKI21_SITE_DEPLOY_VDS.md`

**Step 1:** В §7 «Диагностика» после пункта 3 «Что проверить дальше» добавить абзац: «Пошаговый runbook при падении автоматической верификации деплоя: **docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md**.»

**Step 2:** В конце скрипта deploy (после «Готово. Проверь...») при успешной верификации можно не менять; при провале скрипт уже выводит ссылку на runbook (Task 2).

---

### Task 4: Обновить CHANGES и при необходимости MASTER_REFERENCE

**Files:**

- Modify: `docs/CHANGES_FROM_OTHER_CHATS.md`

**Step 1:** Добавить пункт § (следующий номер): Setki21 — автоверификация деплоя и runbook; шаг 5 в deploy_setki21_site_vds.sh (сравнение хэша CSS), SKIP_SETKI21_VERIFY, runbook docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md; в дизайне зафиксировано, где править маршрутизацию (NPM UI 45.10.43.248:81, Proxy Host www.setki21.ru → setki21-site:80).

---

## Checklist перед коммитом

- [ ] Runbook существует и содержит точный путь в NPM.
- [ ] Скрипт с SKIP_SETKI21_VERIFY=1 не падает и не выполняет проверку.
- [ ] Скрипт без флага при несовпадении хэшей выходит с кодом 1 и выводит ссылку на runbook.
- [ ] SETKI21_SITE_DEPLOY_VDS §7 ссылается на runbook.
