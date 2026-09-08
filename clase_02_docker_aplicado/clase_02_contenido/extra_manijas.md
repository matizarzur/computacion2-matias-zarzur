# Clase 2: Docker Aplicado - Extra Manijas

Material opcional para profundizar.

---

## Multi-stage builds

Cuando tu aplicación necesita compilar algo, la imagen final puede quedar enorme con herramientas que no necesitás en runtime.

### El problema

```dockerfile
FROM python:3.11
WORKDIR /app
RUN apt-get update && apt-get install -y gcc
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

Esta imagen incluye gcc, headers de desarrollo, y un montón de cosas innecesarias.

### La solución: multi-stage

```dockerfile
# Etapa de build
FROM python:3.11 AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Etapa final
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
CMD ["python", "app.py"]
```

La imagen final solo tiene lo necesario para correr, no para compilar.

---

## BuildKit y mejoras de performance

Docker BuildKit es el nuevo sistema de build con mejoras significativas:

```bash
# Habilitar BuildKit
export DOCKER_BUILDKIT=1
docker build .

# O para docker-compose
export COMPOSE_DOCKER_CLI_BUILD=1
docker-compose build
```

### Ventajas

**Cache de capas mejorado:**
```dockerfile
# syntax=docker/dockerfile:1.4
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
COPY . .
```

El cache de pip persiste entre builds, haciendo instalaciones mucho más rápidas.

**Secrets sin exponerlos:**
```dockerfile
RUN --mount=type=secret,id=my_secret \
    cat /run/secrets/my_secret
```

```bash
docker build --secret id=my_secret,src=./my_secret.txt .
```

---

## Healthchecks

Para saber si un servicio está realmente listo:

```dockerfile
FROM python:3.11-slim
# ...
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

En docker-compose:

```yaml
services:
  web:
    build: .
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
```

```bash
# Ver estado de salud
docker ps  # muestra (healthy), (unhealthy), (starting)
docker inspect --format='{{.State.Health.Status}}' container_name
```

---

## Docker Compose profiles

Para tener configuraciones opcionales:

```yaml
version: '3.8'

services:
  app:
    build: .

  redis:
    image: redis:alpine

  debug:
    image: busybox
    profiles: ["debug"]
    command: sleep infinity
```

```bash
# Solo app y redis
docker-compose up

# Incluyendo debug
docker-compose --profile debug up
```

---

## Compose para múltiples ambientes

```yaml
# docker-compose.yml (base)
version: '3.8'
services:
  app:
    build: .
    environment:
      - ENV=production
```

```yaml
# docker-compose.override.yml (desarrollo, se aplica automáticamente)
version: '3.8'
services:
  app:
    volumes:
      - .:/app
    environment:
      - ENV=development
      - DEBUG=true
```

```yaml
# docker-compose.prod.yml (producción, se especifica explícitamente)
version: '3.8'
services:
  app:
    restart: always
    deploy:
      replicas: 3
```

```bash
# Desarrollo (usa override automáticamente)
docker-compose up

# Producción
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```

---

## Logging avanzado

### Drivers de logging

```yaml
services:
  app:
    image: my-app
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Otros drivers: `syslog`, `journald`, `gelf`, `fluentd`.

### Centralizar logs

```yaml
services:
  app:
    logging:
      driver: fluentd
      options:
        fluentd-address: "localhost:24224"
        tag: "docker.{{.Name}}"
```

---

## Optimización de imágenes

### Reducir capas

```dockerfile
# Mal: muchas capas
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y git
RUN apt-get clean

# Bien: una capa
RUN apt-get update && \
    apt-get install -y curl git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
```

### Orden de instrucciones

Lo que cambia menos va primero:

```dockerfile
# Cambios raros
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl

# Cambios ocasionales
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cambios frecuentes
COPY . .
CMD ["python", "app.py"]
```

### Analizar imágenes

```bash
# Ver capas y tamaños
docker history mi-imagen

# Herramienta dive (instalar aparte)
dive mi-imagen
```

---

## Seguridad

### Usuario no-root

```dockerfile
FROM python:3.11-slim

# Crear usuario
RUN useradd -m -s /bin/bash appuser

WORKDIR /app
COPY --chown=appuser:appuser . .

USER appuser
CMD ["python", "app.py"]
```

### Read-only filesystem

```yaml
services:
  app:
    image: my-app
    read_only: true
    tmpfs:
      - /tmp
```

### Escaneo de vulnerabilidades

```bash
# Docker Scout (integrado)
docker scout cves mi-imagen

# Trivy (herramienta externa popular)
trivy image mi-imagen
```

---

## Docker en CI/CD

### GitHub Actions

```yaml
name: Build and Push

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build image
        run: docker build -t mi-app .

      - name: Run tests
        run: docker run mi-app pytest

      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push mi-app
```

---

## Recursos adicionales

- [Dockerfile best practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Docker Compose specification](https://docs.docker.com/compose/compose-file/)
- [Docker security](https://docs.docker.com/engine/security/)
- [Awesome Docker](https://github.com/veggiemonk/awesome-docker)

---

*Computación II - 2026 - Clase 2 - Material opcional*
