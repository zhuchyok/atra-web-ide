# 🔧 НАСТРОЙКА GATEWAYPORTS ДЛЯ SSH REVERSE TUNNEL

**Дата:** 2026-01-25  
**Проблема:** SSH Reverse Tunnel слушает только на localhost сервера, недоступен извне

---

## 🎯 ПРОБЛЕМА

SSH Reverse Tunnel создает порты на `127.0.0.1` (localhost) сервера, а не на внешнем интерфейсе. Это означает, что сервисы недоступны из интернета, только с самого сервера.

---

## ✅ РЕШЕНИЕ: Настройка GatewayPorts

### На сервере 185.177.216.15:

```bash
# 1. Подключитесь к серверу
ssh root@185.177.216.15

# 2. Создайте конфигурационный файл
echo "GatewayPorts yes" > /etc/ssh/sshd_config.d/gatewayports.conf

# 3. Перезагрузите SSH сервер
systemctl reload sshd

# 4. Проверьте
grep GatewayPorts /etc/ssh/sshd_config.d/gatewayports.conf
```

### После настройки GatewayPorts:

1. **Перезапустите туннели на Mac Studio:**

   ```bash
   bash scripts/setup_ssh_tunnel_for_headscale.sh
   ```

2. **Проверьте доступность:**
   ```bash
   curl http://185.177.216.15:8010/health
   curl http://185.177.216.15:8011/health
   ```

---

## ⚠️ БЕЗОПАСНОСТЬ

**GatewayPorts yes** открывает порты на всех интерфейсах сервера. Убедитесь, что:

- ✅ Файрвол настроен правильно
- ✅ Порты защищены (если нужно)
- ✅ Доступ ограничен (если нужно)

---

## 🔄 АЛЬТЕРНАТИВА: Nginx Reverse Proxy

Если GatewayPorts недоступен, можно использовать Nginx на сервере:

```nginx
# /etc/nginx/sites-available/mac-studio-tunnels
server {
    listen 8010;
    location / {
        proxy_pass http://127.0.0.1:8010;
    }
}

server {
    listen 8011;
    location / {
        proxy_pass http://127.0.0.1:8011;
    }
}
```

---

_Документ создан 2026-01-25_
