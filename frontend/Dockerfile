# ATRA Web IDE - Frontend
FROM node:20-alpine as build

WORKDIR /app

# Установка зависимостей
COPY package.json ./
RUN npm install

# Сборка
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Копирование собранного приложения
COPY --from=build /app/dist /usr/share/nginx/html

# Конфигурация nginx для SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
