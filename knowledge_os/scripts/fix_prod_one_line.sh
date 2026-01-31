#!/bin/bash
# Однострочная команда для исправления PROD на сервере
# Выполните на сервере: bash <(curl -s https://raw.githubusercontent.com/.../fix_prod_one_line.sh)
# Или скопируйте и выполните на сервере

cd /root/atra && sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env && grep '^ATRA_ENV=' env && (systemctl restart atra 2>/dev/null || (pkill -f "python.*signal_live" 2>/dev/null; sleep 2; nohup python3 signal_live.py > /dev/null 2>&1 &)) && echo "✅ PROD установлен и система перезапущена"

