#!/usr/bin/env bash
# Генерация TypeScript типов из OpenAPI schema
# Использует openapi-typescript для type-safe frontend

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
OUTPUT_FILE="frontend/src/types/api-generated.ts"

echo "🔧 Генерация TypeScript типов из OpenAPI..."
echo "   Backend: $BACKEND_URL"
echo "   Output: $OUTPUT_FILE"

# Проверка доступности backend
if ! curl -s -f "$BACKEND_URL/health" > /dev/null 2>&1; then
    echo "❌ Backend недоступен на $BACKEND_URL"
    echo "   Запустите: cd backend && uvicorn app.main:app --reload"
    exit 1
fi

# Установка openapi-typescript если нужно
if ! command -v openapi-typescript &> /dev/null; then
    echo "📦 Установка openapi-typescript..."
    npm install -g openapi-typescript
fi

# Генерация
npx openapi-typescript "$BACKEND_URL/openapi.json" -o "$OUTPUT_FILE"

echo "✅ TypeScript типы сгенерированы: $OUTPUT_FILE"
echo ""
echo "Использование в frontend:"
echo '  import type { paths } from "./types/api-generated";'
echo '  type ChatResponse = paths["/api/chat/send"]["post"]["responses"]["200"]["content"]["application/json"];'
