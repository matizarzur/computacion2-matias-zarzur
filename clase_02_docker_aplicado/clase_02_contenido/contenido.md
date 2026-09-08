# Clase 2: Docker Aplicado

## Retomando

En la clase anterior aprendimos a correr contenedores básicos. Vimos que los contenedores son efímeros: todo lo que hacés dentro desaparece cuando el contenedor se elimina.

Hoy vamos a resolver ese problema y varios más:
- **Volúmenes**: para persistir datos y compartir archivos
- **Redes**: para que los contenedores se comuniquen
- **Dockerfile**: para crear nuestras propias imágenes
- **Docker Compose**: para manejar múltiples contenedores como una unidad

Al final de esta clase vas a poder crear un entorno de desarrollo completo en Docker.

---

## Volúmenes: persistencia y compartición

### El problema de la efímera

Recordá el experimento de la clase pasada: instalaste cowsay en un contenedor, saliste, y cuando volviste a entrar no estaba. Cada `docker run` crea un contenedor nuevo, limpio.

Esto es bueno para reproducibilidad, pero malo si querés:
- Guardar datos de una base de datos
- Editar código con tu editor favorito y correrlo en Docker
- Mantener logs entre reinicios

### Bind mounts: compartir con el host

Ya usamos esto brevemente:

```bash
docker run -v $(pwd):/app -w /app python python script.py
```

Esto es un **bind mount**: conecta un directorio del host con uno del contenedor. Los cambios en uno se reflejan en el otro instantáneamente.

Desglose:
- `-v $(pwd):/app` → `<path_host>:<path_contenedor>`
- `-w /app` → working directory dentro del contenedor

```bash
# Ejemplo: editar código localmente, correr en Docker
# Terminal 1: editor abierto en tu directorio
# Terminal 2:
docker run -it -v $(pwd):/app -w /app python bash

# Dentro del contenedor:
python script.py  # corre tu código
# Editás algo en tu editor
python script.py  # los cambios se reflejan inmediatamente
```

### Named volumes: datos persistentes

Para datos que querés que persistan pero no necesitás acceder desde el host directamente:

```bash
# Crear un volumen
docker volume create mis-datos

# Usar el volumen
docker run -v mis-datos:/data python python -c "
with open('/data/archivo.txt', 'w') as f:
    f.write('Datos persistentes')
print('Guardado')
"

# El contenedor terminó, pero los datos persisten
docker run -v mis-datos:/data python python -c "
with open('/data/archivo.txt') as f:
    print(f.read())
"
```

Los named volumes son la forma recomendada para bases de datos y otros datos que deben sobrevivir a los contenedores.

```bash
# Ver volúmenes
docker volume ls

# Inspeccionar un volumen
docker volume inspect mis-datos

# Eliminar un volumen
docker volume rm mis-datos
```

### Cuándo usar cada tipo

| Tipo | Uso típico |
|------|------------|
| Bind mount (`-v /path:/path`) | Código fuente, configuración |
| Named volume (`-v nombre:/path`) | Bases de datos, datos persistentes |

---

## Redes: comunicación entre contenedores

### El problema

Tenés una aplicación Python que necesita conectarse a una base de datos Redis. ¿Cómo hacés que se encuentren?

### Tipos de redes en Docker

Docker ofrece distintos tipos (drivers) de red, cada uno con un propósito diferente:

| Driver | Qué hace | Cuándo usarlo |
|--------|----------|---------------|
| `bridge` | Crea una red virtual interna donde los contenedores se comunican entre sí, aislados del host | Es el **default**. Ideal para comunicar contenedores en una misma máquina |
| `host` | El contenedor comparte directamente la red del host, sin aislamiento | Cuando necesitás máximo rendimiento de red y no te importa el aislamiento (ej: herramientas de monitoreo) |
| `none` | El contenedor no tiene red | Contenedores que no necesitan comunicación (ej: tareas de cómputo puro) |

En esta materia vamos a trabajar casi siempre con `bridge`, que es el driver por defecto y el más común.

```bash
# Ver redes
docker network ls

# Inspeccionar la red bridge
docker network inspect bridge
```

Cuando corrés contenedores sin especificar red, Docker los pone en la red bridge por defecto. Pero hay un problema: en esa red por defecto, los contenedores no se pueden encontrar por nombre, solo por IP. Y las IPs cambian.

### Redes personalizadas: la solución

Cuando creás tu propia red, Docker habilita **DNS automático**: los contenedores se pueden encontrar por nombre.

```bash
# Crear una red
docker network create mi-red

# Correr contenedores en esa red
docker run -d --name redis --network mi-red redis:alpine

docker run -it --network mi-red python bash
# Dentro del contenedor:
# ping redis  # funciona!
```

El contenedor `redis` es accesible por el nombre "redis" desde cualquier otro contenedor en `mi-red`.

### Ejemplo práctico: Python + Redis

```bash
# Crear la red
docker network create app-network

# Levantar Redis
docker run -d --name redis --network app-network redis:alpine

# Probar la conexión desde Python
docker run -it --network app-network python bash
```

Dentro del contenedor Python:

```bash
# Primero instalamos el cliente de Redis
pip install redis
```

```python
import socket

# Verificar que el nombre resuelve
print(socket.gethostbyname('redis'))

# Conectar con redis-py
import redis
r = redis.Redis(host='redis', port=6379)
r.set('clave', 'valor')
print(r.get('clave'))
```

### Exponiendo puertos: EXPOSE vs -p

Un contenedor Docker corre en su propia red aislada. Para que un servicio del contenedor sea accesible desde afuera, hay que **publicar** el puerto explícitamente. Esto es como abrir una puerta entre la red de Docker y tu máquina.

Hay una confusión frecuente entre dos conceptos:

| | `EXPOSE` (Dockerfile) | `-p` / `ports` (runtime) |
|-|----------------------|--------------------------|
| **Qué hace** | Documenta qué puerto usa la app internamente | Publica el puerto y lo hace accesible desde el host |
| **Abre el puerto?** | **No**. Es solo metadata, una nota para quien lea el Dockerfile | **Sí**. Crea un mapeo real entre host y contenedor |
| **Ejemplo** | `EXPOSE 8000` | `docker run -p 8000:8000` |

Es decir: `EXPOSE` es como poner un cartel que dice "esta app escucha en el puerto 8000". Pero sin `-p`, nadie de afuera puede conectarse.

```bash
# -p <puerto_host>:<puerto_contenedor>
docker run -d -p 6379:6379 --name redis redis:alpine
```

Ahora podés conectarte a `localhost:6379` desde tu máquina. El tráfico que llega al puerto 6379 del host se redirige al puerto 6379 del contenedor.

```bash
# Ver qué puertos están publicados
docker port redis

# Podés mapear a un puerto diferente del host
docker run -d -p 9999:6379 --name redis2 redis:alpine
# Ahora accedés desde localhost:9999
```

> **Importante**: entre contenedores de la misma red, no necesitás `-p`. Los contenedores se ven directamente por sus puertos internos. `-p` es solo para acceder **desde el host** o desde fuera de Docker.

---

## Dockerfile: crear tus propias imágenes

### ¿Por qué crear imágenes?

Hasta ahora usamos imágenes existentes. Pero:
- ¿Qué pasa si necesitás bibliotecas Python específicas?
- ¿Qué pasa si querés configuraciones particulares?
- ¿Cómo compartís tu entorno con otros?

### Anatomía de un Dockerfile

Un Dockerfile es un archivo de texto con instrucciones para construir una imagen:

```dockerfile
# Imagen base
FROM python:3.11-slim

# Configurar directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Comando por defecto
CMD ["python", "app.py"]
```

### Instrucciones principales

| Instrucción | Propósito |
|-------------|-----------|
| `FROM` | Imagen base (obligatorio, primero) |
| `WORKDIR` | Establecer directorio de trabajo |
| `COPY` | Copiar archivos del host a la imagen |
| `RUN` | Ejecutar comandos durante build |
| `CMD` | Comando por defecto al correr |
| `ENV` | Variables de entorno |
| `EXPOSE` | Documentar puertos (no los abre) |

### Construir y usar

```bash
# Estructura del proyecto
mi-proyecto/
├── Dockerfile
├── requirements.txt
└── app.py

# Construir la imagen
docker build -t mi-app .

# -t = tag (nombre de la imagen)
# . = contexto de build (directorio actual)

# Correr la imagen
docker run mi-app

# Correr interactivamente
docker run -it mi-app bash
```

### Ejemplo completo

`requirements.txt`:
```
requests==2.31.0
redis==5.0.0
```

`app.py`:
```python
import requests
import redis
import os

print("App iniciada")
print(f"Redis host: {os.getenv('REDIS_HOST', 'localhost')}")
```

`Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV REDIS_HOST=redis

CMD ["python", "app.py"]
```

```bash
docker build -t mi-app .
docker run mi-app
```

### .dockerignore

Igual que `.gitignore`, pero para el build de Docker:

```
# .dockerignore
__pycache__
*.pyc
.git
.env
venv
.vscode
```

Evita copiar archivos innecesarios a la imagen.

---

## Docker Compose: orquestar múltiples contenedores

### El problema

Para nuestra app Python + Redis necesitamos:
1. Crear una red
2. Levantar Redis con el nombre correcto
3. Levantar nuestra app con el volumen correcto

Son muchos comandos. Y si querés agregar más servicios, se vuelve inmanejable.

### La solución: docker-compose.yml

```yaml
services:
  app:
    build: .
    volumes:
      - .:/app
    environment:
      - REDIS_HOST=redis
    depends_on:
      - redis

  redis:
    image: redis:alpine
```

Eso es todo. Docker Compose se encarga de:
- Crear una red para estos servicios
- Levantar Redis antes que app (por `depends_on`)
- Nombrar todo consistentemente

### Comandos de Compose

> **Nota**: el comando actual es `docker compose` (sin guión, como subcomando de docker). En tutoriales y documentación más vieja vas a encontrar `docker-compose` (con guión), que era un binario separado. Ambos funcionan igual, pero el viejo está deprecado.

```bash
# Levantar todo (en foreground)
docker compose up

# Levantar en background
docker compose up -d

# Ver logs
docker compose logs
docker compose logs -f app  # seguir logs de un servicio

# Detener todo
docker compose down

# Detener y eliminar volúmenes
docker compose down -v

# Rebuild de imágenes
docker compose build
docker compose up --build
```

### Ejemplo completo de desarrollo

`docker-compose.yml`:
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - DEBUG=true
      - REDIS_HOST=redis
    depends_on:
      - redis
    command: python app.py  # override del CMD

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

Este setup:
- Monta tu código con hot-reload
- Expone puertos para debugging
- Persiste datos de Redis en un volumen
- Configura todo con variables de entorno

---

## Workflow de desarrollo con Docker

### Setup inicial (una vez)

1. Crear `Dockerfile` para tu app
2. Crear `docker-compose.yml`
3. Crear `.dockerignore`

### Desarrollo diario

```bash
# Levantar el entorno
docker compose up

# En otra terminal, si necesitás acceso al contenedor
docker compose exec app bash

# Ver logs
docker compose logs -f

# Cuando termines
docker compose down
```

### Cuando cambiás dependencias

```bash
# Rebuild de la imagen
docker compose build
docker compose up
```

---

## Tips y buenas prácticas

### 1. Usa imágenes slim para producción

```dockerfile
# Desarrollo: más herramientas
FROM python:3.11

# Producción: más liviano
FROM python:3.11-slim
```

### 2. Ordena las instrucciones por frecuencia de cambio

```dockerfile
# Cosas que cambian poco primero
FROM python:3.11-slim
WORKDIR /app

# Dependencias (cambian ocasionalmente)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Código (cambia seguido) al final
COPY . .
```

Docker cachea cada capa. Si cambiás solo el código, no reinstala dependencias.

### 3. Un proceso por contenedor

No metas la app + la base de datos + el cache en un contenedor. Usá uno para cada cosa y conectalos con redes.

### 4. No guardes secretos en la imagen

```dockerfile
# MAL
ENV DATABASE_PASSWORD=secreto123

# BIEN: pasar en runtime
docker run -e DATABASE_PASSWORD=$DB_PASS mi-app
```

---

## Resumen de comandos nuevos

| Comando | Propósito |
|---------|-----------|
| `docker volume create` | Crear volumen |
| `docker volume ls` | Listar volúmenes |
| `docker network create` | Crear red |
| `docker network ls` | Listar redes |
| `docker build -t nombre .` | Construir imagen |
| `docker compose up` | Levantar servicios |
| `docker compose down` | Detener servicios |
| `docker compose logs` | Ver logs |
| `docker compose exec` | Ejecutar en servicio |

---

## Lo que viene

La próxima clase entramos en el tema central de la materia: **procesos**. Vamos a usar Docker para experimentar con `fork()`, `exec()`, y `wait()` de forma segura y reproducible.

Asegurate de tener:
- Docker funcionando
- Entendido cómo crear un `docker-compose.yml` básico
- Completado el Bloque 0 autónomo (la evaluación es la próxima clase)

---

*Computación II - 2026 - Clase 2*
