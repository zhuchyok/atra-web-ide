# Быстрая настройка SSL для дилерских доменов Setki21

## 🚀 Инструкция (2-3 минуты)

### 1. Открыть NPM

```
http://45.10.43.248:81
```

- Логин: `zhuchyok@icloud.com`
- Пароль: `Bik6007OS`

### 2. Настроить SSL для доменов

Найти и настроить Proxy Hosts для:

#### Домен 1: сеткимоскитки.рф

- Найти: `xn--e1agaahbbnszfhh.xn--p1ai` или `www.xn--e1agaahbbnszfhh.xn--p1ai`
- Edit → SSL → Request a new SSL Certificate
- Email: `zhuchyok@icloud.com`
- Галочки: Force SSL, HTTP/2, HSTS Enabled, HSTS Subdomains
- Согласиться с Let's Encrypt → Save

#### Домен 2: setkimoskitki.ru

- Найти: `setkimoskitki.ru` или `www.setkimoskitki.ru`
- Повторить те же действия

### 3. Проверка (после каждого домена)

**В терминале:**

```bash
# Для сеткимоскитки.рф
curl -I https://сеткимоскитки.рф/

# Для setkimoskitki.ru
curl -I https://setkimoskitki.ru/
```

Ожидается: `HTTP/2 200` или `HTTP/1.1 200`

**В браузере (режим инкогнито):**

- Ввести: `сеткимоскитки.рф`
- Должен открыться сайт через HTTPS (замок в адресной строке)

---

## ✅ Чек-лист

- [ ] Открыл NPM (http://45.10.43.248:81)
- [ ] Настроил SSL для `xn--e1agaahbbnszfhh.xn--p1ai`
- [ ] Проверил HTTPS для сеткимоскитки.рф (работает)
- [ ] Настроил SSL для `setkimoskitki.ru`
- [ ] Проверил HTTPS для setkimoskitki.ru (работает)
- [ ] Открыл оба сайта в браузере (вводом домена без протокола)

---

## 🔧 Если не получается

### "Too many certificates already issued"

- Лимит Let's Encrypt (5 в неделю)
- Решение: подождать неделю или использовать существующий сертификат из списка

### "Connection timeout"

- Порт 80/443 закрыт
- Решение: `ssh root@45.10.43.248 "ufw allow 80/tcp && ufw allow 443/tcp"`

### "DNS resolution error"

- DNS не указывает на наш VDS
- Проверить: `dig +short xn--e1agaahbbnszfhh.xn--p1ai` → должно быть `45.10.43.248`

---

## 📊 После настройки

Проверить все домены:

```bash
bash scripts/check_setki21_ssl.sh
```

Должны увидеть ✅ для всех дилерских доменов.
