# Knowledge OS REST API Documentation

**Версия:** 1.0.0  
**Дата генерации:** 2026-01-09 22:17:31

## Обзор

REST API для интеграции с Knowledge OS

## Базовый URL

- Development: `http://localhost:8002`

## Аутентификация

Все защищенные endpoints требуют JWT токен в заголовке:

```
Authorization: Bearer <your_jwt_token>
```

## Endpoints

### GET /

**Описание:** Root endpoint

**Responses:**

- `200`: API information

### GET /health

**Описание:** Health check

**Responses:**

- `200`: System health status

### POST /auth/login

**Описание:** User authentication

**Request Body:**

```json
{
  "required": true,
  "content": {
    "application/json": {
      "schema": {
        "type": "object",
        "properties": {
          "username": {
            "type": "string"
          },
          "password": {
            "type": "string"
          }
        }
      }
    }
  }
}
```

**Responses:**

- `200`: Authentication successful

