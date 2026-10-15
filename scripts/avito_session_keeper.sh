#!/bin/bash
# Сторож сессии Авито: если CDP 9222 не отвечает — поднимает браузер заново.
# Профиль персистентный, логин сохраняется. Запуск launchd каждые 5 минут.
if curl -s --max-time 3 http://127.0.0.1:9222/json/version > /dev/null 2>&1; then
    exit 0
fi
cd /Users/bikos/Documents/atra-web-ide
nohup .venv/bin/python scripts/avito_session.py >> /Users/bikos/Library/Logs/atra-avito-session.log 2>&1 &
echo "[$(date '+%m-%d %H:%M')] CDP мёртв — браузер перезапущен" >> /Users/bikos/Library/Logs/atra-avito-session.log
