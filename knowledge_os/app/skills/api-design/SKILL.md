---
name: api-design
description: Проектирование RESTful и GraphQL API. Best practices для современного API design с безопасностью и документацией.
---

# API Design Skill

## Когда использовать

- Проектирование новых API
- Документация API
- API review
- Security audit

## RESTful Best Practices

### URL Structure

```
# Good
GET    /users              # List users
GET    /users/{id}        # Get user
POST   /users              # Create user
PUT    /users/{id}        # Update user
DELETE /users/{id}        # Delete user

# Nested resources
GET    /users/{id}/posts
POST   /users/{id}/posts
```

### HTTP Methods

| Method | Usage            | Idempotent |
| ------ | ---------------- | ---------- |
| GET    | Read             | Yes        |
| POST   | Create           | No         |
| PUT    | Update (full)    | Yes        |
| PATCH  | Update (partial) | No         |
| DELETE | Delete           | Yes        |

### Status Codes

```
200 OK
201 Created
204 No Content (delete success)
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
429 Too Many Requests
500 Internal Server Error
```

## Request/Response Format

### JSON API

```json
// Request
POST /users
{
  "data": {
    "type": "user",
    "attributes": {
      "name": "John",
      "email": "john@test.com"
    }
  }
}

// Response
{
  "data": {
    "id": "123",
    "type": "user",
    "attributes": {
      "name": "John",
      "email": "john@test.com",
      "created_at": "2026-01-01T00:00:00Z"
    }
  }
}
```

### Error Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "details": [{ "field": "email", "message": "Must be valid email" }]
  }
}
```

## Authentication

### API Keys

```python
# Header
X-API-Key: your-api-key

# Or Bearer
Authorization: Bearer <token>
```

### JWT

```python
# Token payload
{
  "sub": "user_id",
  "exp": 1699999999,
  "roles": ["admin", "user"]
}
```

### OAuth 2.0

```
Authorization URL: /oauth/authorize
Token URL: /oauth/token
```

## Rate Limiting

### Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

### Implementation

```python
from fastapi import FastAPI
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@limiter.limit("10/minute")
@app.get("/api/resource")
async def resource():
    return {"data": "response"}
```

## Documentation (OpenAPI)

### Example

```yaml
openapi: 3.0.0
info:
  title: User API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
      responses:
        "200":
          description: User list
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/User"
```

## GraphQL

### Schema

```graphql
type User {
  id: ID!
  name: String!
  email: String!
  posts: [Post!]!
}

type Query {
  user(id: ID!): User
  users(limit: Int): [User!]!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
  updateUser(id: ID!, input: UpdateUserInput!): User
  deleteUser(id: ID!): Boolean!
}

input CreateUserInput {
  name: String!
  email: String!
}
```

## Commands

```bash
/api design <spec>      # Generate design
/api docs              # Generate docs
/api validate          # Validate spec
/api client <lang>    # Generate client
/api server <framework> # Generate server
```

## Security Checklist

- [ ] HTTPS only
- [ ] Rate limiting
- [ ] Input validation
- [ ] Output encoding
- [ ] CORS configured
- [ ] API keys rotated
- [ ] JWT expiration
- [ ] Sensitive data encrypted
