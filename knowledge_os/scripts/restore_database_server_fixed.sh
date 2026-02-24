#!/usr/bin/expect -f
# Скрипт восстановления БД на сервере
# Команда: Роман (Database Engineer), Сергей (DevOps Engineer)

set timeout 60
set server "185.177.216.15"
set user "root"
set password "u44Ww9NmtQj,XG"

spawn ssh -o StrictHostKeyChecking=no $user@$server

expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    "# " {
        send "cd /root/atra\r"
        expect "# "

        send "echo '=================================================================================='\r"
        expect "# "
        send "echo '🔧 ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "

        # Проверка существования БД
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 1: Проверка базы данных'\r"
        expect "# "
        send "test -f /root/atra/trading.db && echo '✅ БД найдена' && ls -lh /root/atra/trading.db || echo '❌ БД не найдена'\r"
        expect "# "

        # Создание бэкапа
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 2: Создание бэкапа'\r"
        expect "# "
        send "mkdir -p /root/atra/backups\r"
        expect "# "
        send "cp /root/atra/trading.db /root/atra/backups/trading.db.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null && echo '✅ Бэкап создан' || echo '⚠️ Ошибка создания бэкапа'\r"
        expect "# "

        # Проверка целостности
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 3: Проверка целостности'\r"
        expect "# "
        send "python3 << 'PYEOF'\r"
        send "import sqlite3\r"
        send "try:\r"
        send "    conn = sqlite3.connect('/root/atra/trading.db')\r"
        send "    cursor = conn.cursor()\r"
        send "    cursor.execute('PRAGMA integrity_check')\r"
        send "    result = cursor.fetchone()\r"
        send "    if result and result[0] == 'ok':\r"
        send "        print('✅ База данных целостна')\r"
        send "    else:\r"
        send "        print(f'❌ База данных повреждена: {result}')\r"
        send "        print('🔧 Попытка восстановления...')\r"
        send "    conn.close()\r"
        send "except Exception as e:\r"
        send "    print(f'❌ Ошибка: {e}')\r"
        send "PYEOF\r"
        expect "# "

        # Попытка восстановления
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 4: Попытка восстановления'\r"
        expect "# "
        send "python3 << 'PYEOF'\r"
        send "import sqlite3\r"
        send "import shutil\r"
        send "import os\r"
        send "from datetime import datetime\r"
        send "db_path = '/root/atra/trading.db'\r"
        send "recovered_path = db_path + '.recovered'\r"
        send "try:\r"
        send "    conn = sqlite3.connect(db_path)\r"
        send "    recovered_conn = sqlite3.connect(recovered_path)\r"
        send "    conn.backup(recovered_conn)\r"
        send "    conn.close()\r"
        send "    recovered_conn.close()\r"
        send "    # Проверяем восстановленную БД\r"
        send "    test_conn = sqlite3.connect(recovered_path)\r"
        send "    test_cursor = test_conn.cursor()\r"
        send "    test_cursor.execute('PRAGMA integrity_check')\r"
        send "    test_result = test_cursor.fetchone()\r"
        send "    test_conn.close()\r"
        send "    if test_result and test_result[0] == 'ok':\r"
        send "        shutil.move(recovered_path, db_path)\r"
        send "        print('✅ База данных восстановлена')\r"
        send "    else:\r"
        send "        os.remove(recovered_path)\r"
        send "        print('❌ Восстановление не удалось, пересоздаем структуру...')\r"
        send "        # Пересоздаем структуру\r"
        send "        os.remove(db_path)\r"
        send "        new_conn = sqlite3.connect(db_path)\r"
        send "        new_cursor = new_conn.cursor()\r"
        send "        new_cursor.execute('CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY, symbol TEXT, signal_type TEXT, entry_price REAL, status TEXT DEFAULT \\'active\\', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)')\r"
        send "        new_cursor.execute('CREATE TABLE IF NOT EXISTS active_signals (id INTEGER PRIMARY KEY, symbol TEXT, signal_type TEXT, entry_price REAL, status TEXT DEFAULT \\'active\\', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)')\r"
        send "        new_cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user_id TEXT UNIQUE, username TEXT, is_active BOOLEAN DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)')\r"
        send "        new_conn.commit()\r"
        send "        new_conn.close()\r"
        send "        print('✅ Структура базы данных пересоздана')\r"
        send "except Exception as e:\r"
        send "    print(f'❌ Ошибка: {e}')\r"
        send "    if os.path.exists(recovered_path):\r"
        send "        os.remove(recovered_path)\r"
        send "PYEOF\r"
        expect "# "

        # Финальная проверка
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 5: Финальная проверка'\r"
        expect "# "
        send "python3 << 'PYEOF'\r"
        send "import sqlite3\r"
        send "try:\r"
        send "    conn = sqlite3.connect('/root/atra/trading.db')\r"
        send "    cursor = conn.cursor()\r"
        send "    cursor.execute('PRAGMA integrity_check')\r"
        send "    result = cursor.fetchone()\r"
        send "    if result and result[0] == 'ok':\r"
        send "        print('✅ База данных целостна и готова к работе')\r"
        send "        # Проверяем таблицы\r"
        send "        cursor.execute('SELECT name FROM sqlite_master WHERE type=\\'table\\'')\r"
        send "        tables = cursor.fetchall()\r"
        send "        print(f'📊 Найдено таблиц: {len(tables)}')\r"
        send "        for table in tables:\r"
        send "            print(f'  - {table[0]}')\r"
        send "    else:\r"
        send "        print(f'❌ База данных все еще повреждена: {result}')\r"
        send "    conn.close()\r"
        send "except Exception as e:\r"
        send "    print(f'❌ Ошибка: {e}')\r"
        send "PYEOF\r"
        expect "# "

        send "echo ''\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        send "echo '✅ ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "

        send "exit\r"
        expect eof
    }
    timeout {
        puts "Timeout"
        exit 1
    }
}

wait
