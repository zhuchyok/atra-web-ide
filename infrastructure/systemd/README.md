# systemd units for ATRA

## Установка `atra.service`

1. Скопируйте unit на сервер:
   ```bash
   sudo cp infrastructure/systemd/atra.service /etc/systemd/system/atra.service
   ```
2. Обновите пути в `ExecStart`, `WorkingDirectory`, `StandardOutput` при необходимости.
3. Создайте лог-директорию:
   ```bash
   mkdir -p /root/atra/logs
   ```
4. Перечитайте unit и включите автозапуск:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable atra.service
   sudo systemctl start atra.service
   sudo systemctl status atra.service
   ```
5. Логи:
   ```bash
   tail -f /root/atra/logs/systemd_atra.log
   ```

## Стоп / рестарт
```bash
sudo systemctl stop atra.service
sudo systemctl restart atra.service
```

