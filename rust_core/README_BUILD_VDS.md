# Сборка atra-core для VDS (linux/amd64)

## Проблема

На Mac (arm64) образ собирается под arm64. На VDS (x86_64/amd64) такой образ даёт **exec format error**.

Кросс-сборка через `docker build --platform linux/amd64` на Mac падает: rustc под QEMU падает с SIGSEGV.

## Решение: собирать на VDS

1. Синхронизировать исходники на сервер:

   ```bash
   rsync -az --exclude target ./rust_core/ root@45.10.43.248:/home/atra/app/rust_core/
   ```

2. Собрать образ на VDS (нативная amd64):

   ```bash
   ssh root@45.10.43.248 "cd /home/atra/app/rust_core && docker build -t atra-core:latest ."
   ```

3. Запустить/перезапустить контейнер:

   ```bash
   ssh root@45.10.43.248 "docker rm -f atra-kernel 2>/dev/null; cd /home/atra/app && docker-compose up -d atra-core"
   ```

4. Проверить:
   ```bash
   ssh root@45.10.43.248 "curl -s http://127.0.0.1:8081/health"
   ```

## Альтернатива (позже)

- GitHub Actions: job с `runs-on: ubuntu-latest` (amd64), `docker build` и push в registry; на VDS — `docker pull` и запуск.
