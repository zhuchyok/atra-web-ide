# 🔧 НАСТРОЙКА АДМИНИСТРАТОРОВ НА СЕРВЕРЕ

## 📋 Быстрая настройка

### 1. Подключение к серверу

```bash
ssh your_user@your_server_ip
cd /path/to/atra
```

### 2. Назначение ролей администраторов

#### 🔥 Супер администратор (556251171)

```bash
python3 set_admin_roles.py 556251171 super_admin
```

#### 👑 Администратор (958930260)

```bash
python3 set_admin_roles.py 958930260 admin
```

### 3. Быстрая настройка (все сразу)

```bash
python3 quick_admin_setup.py
```

### 4. Проверка статуса

```bash
python3 quick_admin_setup.py status
```

## 🎯 Роли и права

### 🔥 Супер администратор (556251171)

- **Полные права доступа**
- Управление всеми пользователями
- Доступ к системным настройкам
- Управление администраторами
- Доступ к логам и статистике
- Управление торговыми параметрами

### 👑 Администратор (958930260)

- **Ограниченные административные права**
- Просмотр пользователей
- Доступ к базовой статистике
- Управление настройками торговли
- Нет доступа к системным настройкам

### 👤 Обычный пользователь

- Только торговые функции
- Личные настройки
- Просмотр своих позиций

## 📊 Проверка назначенных ролей

### Через базу данных

```bash
python3 -c "
from db import Database
db = Database()
user_ids = db.get_all_users()
for user_id in user_ids:
    user_data = db.get_user_data(user_id)
    if user_data:
        role = user_data.get('role', 'user')
        is_admin = user_data.get('is_admin', False)
        is_super_admin = user_data.get('is_super_admin', False)
        print(f'👤 {user_id}: {role} (admin: {is_admin}, super: {is_super_admin})')
"
```

### Через SQLite

```bash
sqlite3 trading.db "SELECT user_id, data FROM users_data WHERE user_id IN ('556251171', '958930260');"
```

## 🔄 Управление ролями

### Назначение новой роли

```bash
python3 set_admin_roles.py <user_id> <role>
```

### Доступные роли:

- `super_admin` - Супер администратор
- `admin` - Администратор
- `user` - Обычный пользователь

### Примеры:

```bash
# Назначить супер администратором
python3 set_admin_roles.py 123456789 super_admin

# Назначить администратором
python3 set_admin_roles.py 987654321 admin

# Сделать обычным пользователем
python3 set_admin_roles.py 555666777 user

# Показать всех пользователей
python3 set_admin_roles.py list
```

## 🛡️ Безопасность

### Рекомендации:

1. **Супер администратор** должен быть только один
2. Регулярно проверяйте список администраторов
3. Используйте сильные пароли для доступа к серверу
4. Ограничьте SSH доступ по IP адресам
5. Регулярно обновляйте систему

### Проверка безопасности:

```bash
# Проверить всех администраторов
python3 quick_admin_setup.py status

# Проверить права доступа к файлам
ls -la *.py
ls -la trading.db
ls -la user_data.json
```

## 📝 Логирование

### Проверка логов назначения ролей:

```bash
tail -f system_improved.log | grep -i admin
```

### Создание бэкапа перед изменениями:

```bash
cp trading.db backups/trading_$(date +%Y%m%d_%H%M%S).db
```

## 🆘 Восстановление доступа

### Если потеряли доступ к супер администратору:

1. Остановите бота
2. Создайте бэкап базы данных
3. Выполните быструю настройку:

```bash
python3 quick_admin_setup.py
```

4. Запустите бота заново

### Восстановление из бэкапа:

```bash
# Найдите нужный бэкап
ls -la backups/

# Восстановите из бэкапа
cp backups/trading_YYYYMMDD_HHMMSS.db trading.db

# Проверьте роли
python3 quick_admin_setup.py status
```

## ✅ Финальная проверка

После настройки выполните:

```bash
# 1. Проверьте роли
python3 quick_admin_setup.py status

# 2. Проверьте базу данных
sqlite3 trading.db "SELECT COUNT(*) FROM users_data;"

# 3. Запустите бота
python3 main.py
```

## 📞 Поддержка

При проблемах:

1. Проверьте логи: `tail -f system_improved.log`
2. Создайте бэкап: `cp trading.db trading_backup.db`
3. Обратитесь к документации или разработчику

---

**🎉 Готово! Администраторы настроены и готовы к работе!**
