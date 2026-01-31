# Почему автопроверка не запускает MLX API Server

## Причины

1. **Окружение launchd**  
   При запуске по расписанию (launchd) скрипт получает **минимальный PATH**. В нём может не быть `/opt/homebrew/bin` или `/usr/local/bin`, поэтому находится системный `python3` без `uvicorn` и зависимостей — запуск MLX падает с ошибкой в логе.

2. **Скрипт не доходит до шага MLX**  
   Автопроверка выполняется по шагам (Wi‑Fi, интернет, Docker, Knowledge OS, Web IDE, **потом** MLX). Если на раннем шаге происходит выход (например, Docker не поднялся за 60 секунд и скрипт делает `exit 1`), до запуска MLX выполнение не доходит.

3. **Неверный путь в plist**  
   В `~/Library/LaunchAgents/com.atra.auto-recovery.plist` записан `WorkingDirectory` и путь к скрипту. Если проект переносили, в plist мог остаться старый путь — тогда скрипт либо не находится, либо выполняется не из корня проекта.

## Что сделано в коде

- В **plist** добавлен **PATH** для launchd:  
  `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`
- В **system_auto_recovery.sh** в начале задаётся тот же **PATH** и он передаётся дочернему скрипту.
- При наличии **venv** автопроверка передаёт его в MLX:  
  `knowledge_os/.venv/bin/python` или `backend/.venv/bin/python` (переменная **MLX_PYTHON**).
- **start_mlx_api_server.sh** использует **MLX_PYTHON**, если задана, иначе `python3`.

## Что сделать у себя

1. **Пересоздать launchd (чтобы подхватить PATH и пути):**
   ```bash
   cd /path/to/atra-web-ide
   bash scripts/setup_system_auto_recovery.sh
   ```

2. **Проверить логи автопроверки при следующем запуске MLX:**
   ```bash
   tail -f ~/Library/Logs/atra-auto-recovery.log
   tail -f ~/Library/Logs/atra-auto-recovery.error.log
   ```
   В `error.log` будут сообщения от `start_mlx_api_server.sh` (например, «No module named 'uvicorn'»).

3. **Если используешь venv** — создать его в `knowledge_os` или `backend` и установить зависимости:
   ```bash
   cd knowledge_os && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   ```
   После этого автопроверка будет подставлять этот Python при запуске MLX.

4. **Проверить вручную, что MLX стартует так же, как из автопроверки:**
   ```bash
   PATH=/opt/homebrew/bin:/usr/local/bin:$PATH bash scripts/start_mlx_api_server.sh
   ```

## Полезные команды

- Статус автопроверки: `launchctl list | grep auto-recovery`
- Ручной запуск автопроверки: `bash scripts/system_auto_recovery.sh`
- Ручной запуск MLX: `bash scripts/start_mlx_api_server.sh`
