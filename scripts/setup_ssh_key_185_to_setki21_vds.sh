#!/usr/bin/env bash
# Настройка входа по ключу с 185 (msk-1-vm-pomm) на VDS Сетки 21 (45.10.43.248).
# Запускать НА СЕРВЕРЕ 185: скопировать скрипт и выполнить, либо с твоего Mac:
#   ssh root@185.177.216.15 'bash -s' < scripts/setup_ssh_key_185_to_setki21_vds.sh

set -e

SETKI21_VDS="45.10.43.248"
REMOTE_APP="/home/atra/app"

# Ключ на текущей машине (185)
mkdir -p ~/.ssh
chmod 700 ~/.ssh
if [ ! -f ~/.ssh/id_ed25519 ]; then
  ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -C "185-to-setki21-vds" -q
  echo "Создан новый ключ ~/.ssh/id_ed25519"
fi
PUBKEY=$(cat ~/.ssh/id_ed25519.pub)

# Проверяем, уже настроен ли вход без пароля
if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@${SETKI21_VDS} "echo OK" 2>/dev/null; then
  echo "Вход по ключу на ${SETKI21_VDS} уже работает."
  echo "Перезапуск setki21-orders-api..."
  ssh -o StrictHostKeyChecking=no root@${SETKI21_VDS} "cd ${REMOTE_APP}/setki21_orders_api && docker restart setki21-orders-api"
  echo "Готово."
  exit 0
fi

# Нужно один раз добавить ключ на 45.10.43.248
echo "=============================================="
echo "Ключ с 185 на 45.10.43.248 ещё не добавлен."
echo ""
echo "1) Зайди на VDS по паролю (один раз):"
echo "   ssh root@${SETKI21_VDS}"
echo ""
echo "2) Скопируй и выполни на 45.10.43.248 ЭТУ ОДНУ СТРОКУ (подставь ключ ниже):"
echo "   mkdir -p ~/.ssh; chmod 700 ~/.ssh; echo '${PUBKEY}' >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys"
echo ""
echo "3) Выйди с VDS (exit) и снова запусти этот скрипт — он перезапустит контейнер без пароля."
echo "=============================================="
