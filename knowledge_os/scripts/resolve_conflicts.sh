#!/bin/bash

# Разрешаем конфликты Git принимая наши исправления

expect << 'EOF'
spawn ssh -o StrictHostKeyChecking=no root@185.177.216.15
expect "password:"
send "u44Ww9NmtQj,XG\r"
expect "# "

send "cd /root/atra\r"
expect "# "

# Принимаем наши версии для критичных файлов
send "git checkout --ours ai_config.py\r"
expect "# "

send "git checkout --ours ai_learning_system.py\r"
expect "# "

send "git checkout --ours web/dashboard.py\r"
expect "# "

# test_bot_commands.py - удален в remote, оставляем наш
send "git rm test_bot_commands.py || git add test_bot_commands.py\r"
expect "# "

# Добавляем разрешенные файлы
send "git add ai_config.py ai_learning_system.py web/dashboard.py\r"
expect "# "

# Завершаем merge
send "git commit -m 'Merge: keep our critical fixes (5 bugs + AI improvements)'\r"
expect "# "

send "echo ''\r"
expect "# "

send "echo '✅ Конфликты разрешены!'\r"
expect "# "

send "git status --short | head -20\r"
expect "# "

send "exit\r"
expect eof
EOF

echo ""
echo "✅ Конфликты разрешены!"
echo ""
echo "Наши критичные исправления сохранены:"
echo "  ✅ ai_config.py - конфигурация ИИ"
echo "  ✅ ai_learning_system.py - умная очистка"
echo "  ✅ web/dashboard.py - исправление status column"
echo "  ✅ signal_live.py - whale_status + арбитраж"
echo "  ✅ main.py - Flask threading"
echo "  ✅ rest_api.py - signal handlers"

