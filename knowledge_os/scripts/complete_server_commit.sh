#!/bin/bash

# Полный коммит всех изменений на сервере

expect << 'EOF'
spawn ssh -o StrictHostKeyChecking=no root@185.177.216.15
expect "password:"
send "u44Ww9NmtQj,XG\r"
expect "# "

send "cd /root/atra\r"
expect "# "

# Коммитим оставшиеся измененные файлы
send "git add check_database_structure.py fix_server_complete.py telegram_utils.py test_bot_commands.py\r"
expect "# "

send "git commit -m 'Update: server utilities and database checks'\r"
expect "# "

# Добавляем все новые утилиты в gitignore (чтобы не мешали)
send "cat >> .gitignore << 'GITIGNORE'\n# Temporary utility scripts\nanalyze_dashboard_data.py\ncheck_bot_updates.py\ncheck_dashboard_data.py\nclear_telegram_queue.py\ncompare_users.py\ncreate_*_dashboard.py\nfix_dashboard_*.py\nreset_telegram_offset.py\nrestore_and_fix_dashboard.py\nshow_token.py\ntest_dashboard_direct.py\ndashboard_*_backup_*/\nsignal_live_backup_before_optimization_*.py\n*.backup_*\nGITIGNORE\r"
expect "# "

send "git add .gitignore\r"
expect "# "

send "git commit -m 'Add: gitignore for utility scripts' || true\r"
expect "# "

# Теперь pull с merge
send "git pull origin worker_v2\r"
expect -re "(conflict|CONFLICT|Merge made|Already up to date)" 
send "\r"
expect "# "

send "echo ''\r"
expect "# "
send "echo '✅ Git статус:'\r"
expect "# "

send "git status --short\r"
expect "# "

send "exit\r"
expect eof
EOF

echo ""
echo "✅ Готово!"

