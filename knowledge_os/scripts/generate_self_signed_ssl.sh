#!/bin/bash
# Скрипт для генерации self-signed SSL сертификата для HTTPS

# Создаем директорию для SSL сертификатов
mkdir -p ssl

# Генерируем self-signed сертификат (действителен 365 дней)
openssl req -x509 -newkey rsa:4096 -nodes \
    -keyout ssl/key.pem \
    -out ssl/cert.pem \
    -days 365 \
    -subj "/C=RU/ST=State/L=City/O=ATRA/CN=localhost"

echo "✅ SSL сертификаты созданы в директории ssl/"
echo "   Key: ssl/key.pem"
echo "   Cert: ssl/cert.pem"
echo ""
echo "⚠️  ВНИМАНИЕ: Это self-signed сертификат, браузеры будут показывать предупреждение."
echo "   Для продакшена используйте Let's Encrypt или коммерческий сертификат."

