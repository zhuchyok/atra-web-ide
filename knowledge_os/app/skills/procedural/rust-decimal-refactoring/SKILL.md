---
name: Rust Decimal Refactoring
description: Процедура перевода финансовых полей с f64 на Decimal в Rust проектах с использованием sqlx
category: rust
version: 1.0.0
author: Victoria AI
---

# Rust Decimal Refactoring

## Когда использовать

Процедура перевода финансовых полей с f64 на Decimal в Rust проектах с использованием sqlx

## Процедура

1. Добавить rust_decimal в Cargo.toml.
2. Включить feature rust_decimal в sqlx.
3. Заменить f64 на Decimal в структурах.
4. Использовать dec!() макрос для литералов.
5. Обновить SQL запросы, убрав лишние касты.

## Грабли (Pitfalls)

Несоответствие типов при декодировании из БД, если не включена feature в sqlx.

## Проверка (Verification)

Запуск cargo check должен возвращать Exit code 0.
