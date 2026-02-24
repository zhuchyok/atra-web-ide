#!/bin/bash

# Полная очистка и перезапуск бота

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"

echo "🔄 Полная очистка и перезапуск бота"
echo "===================================="

expect << 'EOF'
spawn ssh -o StrictHostKeyChecking=no root@185.177.216.15
expect "password:"
send "u44Ww9NmtQj,XG\r"
expect "# "

# Останавливаем все процессы
send "pkill -9 -f 'main.py|rest_api|dashboard'\r"
expect "# "
send "sleep 2\r"
expect "# "

# Очищаем все локи и кэши
send "cd /root/atra\r"
expect "# "
send "rm -f atra.lock /tmp/atra_tg_poll_* /tmp/atra_*.lock\r"
expect "# "

# Очищаем Telegram offset через API
send "python3 << 'PYEND'\nimport requests\nfrom config import TOKEN\nurl = f\"https://api.telegram.org/bot{TOKEN}/deleteWebhook\"\nrequests.get(url, timeout=10)\nurl2 = f\"https://api.telegram.org/bot{TOKEN}/getUpdates\"\nr = requests.get(url2, timeout=10)\nif r.json().get(\"result\"):\n    last_id = r.json()[\"result\"][-1][\"update_id\"]\n    requests.get(url2, params={\"offset\": last_id + 1}, timeout=10)\n    print(f\"Offset cleared: {last_id + 1}\")\nelse:\n    print(\"No updates to clear\")\nPYEND\r"
expect "# "
send "sleep 2\r"
expect "# "

# Запускаем бота
send "nohup python3 main.py > bot_final.log 2>&1 &\r"
expect "# "
send "sleep 5\r"
expect "# "

# Проверяем статус
send "ps aux | grep python | grep main.py | grep -v grep\r"
expect "# "

send "echo '✅ Бот перезапущен с полной очисткой'\r"
expect "# "

send "exit\r"
expect eof
EOF

echo ""
echo "✅ Готово!"
echo ""
echo "Теперь отправьте /start боту @PiuX_Trade_bot"
