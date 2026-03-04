#!/usr/bin/env bash
# 1. Добавить ключ на MacBook (один раз)
# 2. Запустить поиск
# Запускать на Mac Studio

set -e
MACBOOK_IP="${MACBOOK_IP:-192.168.1.38}"

echo "=== Шаг 1: Добавьте ключ на MacBook ==="
echo ""
echo "В терминале Mac Studio выполните (потребуется пароль MacBook):"
echo ""
echo "  ssh-copy-id -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519.pub bikos@$MACBOOK_IP"
echo ""
echo "Или на MacBook выполните:"
echo "  mkdir -p ~/.ssh"
echo "  echo '$(cat ~/.ssh/id_ed25519.pub 2>/dev/null)' >> ~/.ssh/authorized_keys"
echo "  chmod 600 ~/.ssh/authorized_keys"
echo ""
read -p "Ключ добавлен? (y/n): " ok
if [ "$ok" != "y" ]; then
  echo "Добавьте ключ и запустите снова."
  exit 0
fi

echo ""
echo "=== Шаг 2: Поиск на MacBook ==="
bash "$(dirname "$0")/run_search_on_macbook.sh"
