---
name: docker-kubernetes
description: Docker та Kubernetes - контейнеризація та оркестрація. Build, deploy, scale контейнерів.
---

# Docker & Kubernetes Skill

## Когда использовать
- Контейнеризація додатків
- K8s deployment
- Docker Compose для локальної розробки
- Helm charts

## Docker Basics

### Dockerfile
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
    depends_on:
      - db
  db:
    image: postgres:15
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

## Kubernetes

### Basic Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: my-app
        image: my-app:latest
        ports:
        - containerPort: 3000
        resources:
          limits:
            memory: "256Mi"
            cpu: "500m"
```

### Service
```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app
spec:
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 3000
  type: LoadBalancer
```

### Ingress
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
spec:
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-app
            port:
              number: 80
```

## Helm Charts

```bash
# Create chart
helm create my-app

# Deploy
helm install my-app ./my-app

# Upgrade
helm upgrade my-app ./my-app

# Values
helm install my-app ./my-app --set image.tag=v1.0
```

## Commands

```bash
# Docker
docker build -t my-app .
docker run -p 3000:3000 my-app
docker-compose up -d

# Kubernetes
kubectl apply -f deployment.yaml
kubectl get pods
kubectl logs -f my-app-pod
kubectl scale deployment my-app --replicas=5
kubectl port-forward svc/my-app 8080:80
```

## Best Practices

- Multi-stage builds для мінімізації розміру
- .dockerignore для виключення файлів
- Health checks (HEALTHCHECK)
- Non-root user
- Secrets через K8s secrets