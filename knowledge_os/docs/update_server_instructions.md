# Инструкции по обновлению файла signal_live.py на сервере

## 🎯 Цель

Обновить файл `signal_live.py` на сервере исправленной версией, которая содержит:

- ✅ Исправления CONF (confidence) сигналов
- ✅ Исправления форматов времени
- ✅ Исправления синтаксических ошибок

## 📋 Шаги обновления

### 1. Создайте резервную копию текущего файла на сервере:

```bash
ssh user@your-server "cp /root/atra/signal_live.py /root/atra/signal_live.py.backup.$(date +%Y%m%d_%H%M%S)"
```

### 2. Скопируйте исправленный файл на сервер:

```bash
scp signal_live.py user@your-server:/root/atra/
```

### 3. Проверьте синтаксис на сервере:

```bash
ssh user@your-server "cd /root/atra && python3 -m py_compile signal_live.py"
```

### 4. Перезапустите сервис:

```bash
ssh user@your-server "sudo systemctl restart myproject.service"
```

### 5. Проверьте статус сервиса:

```bash
ssh user@your-server "sudo systemctl status myproject.service"
```

## 🔧 Альтернативный способ (если у вас есть доступ к серверу):

### Через веб-интерфейс или файловый менеджер:

1. Загрузите файл `signal_live.py` из локальной папки
2. Замените файл `/root/atra/signal_live.py` на сервере
3. Перезапустите сервис

## ✅ Проверка успешности обновления:

После обновления проверьте логи:

```bash
ssh user@your-server "sudo journalctl -u myproject.service -f --no-pager"
```

Должны исчезнуть ошибки:

- ❌ `SyntaxError: invalid syntax` на строке 6946
- ❌ `TypeError: unsupported operand type(s) for |: 'type' and 'type'`

## 🚨 В случае проблем:

Если что-то пошло не так, восстановите из резервной копии:

```bash
ssh user@your-server "cp /root/atra/signal_live.py.backup.* /root/atra/signal_live.py"
```

## 📊 Что исправлено в новой версии:

1. **CONF сигналы теперь работают правильно** - показывают 🟢 БЫЧИЙ/🔴 МЕДВЕЖИЙ вместо ⚪ НЕЙТРАЛЬНО
2. **Исправлены форматы времени** - нет больше "Данные сигнала не найдены"
3. **Исправлены синтаксические ошибки** - файл компилируется без ошибок
4. **Совместимость с Python 3.9** - используется Union вместо | для типов
