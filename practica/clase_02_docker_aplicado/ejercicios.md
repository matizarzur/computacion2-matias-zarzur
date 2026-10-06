# Clase 2: Docker Aplicado - Ejercicios

## Objetivo

Estos ejercicios te van a dar práctica con volúmenes, redes, Dockerfiles, y Docker Compose. Al terminar, vas a poder crear un entorno de desarrollo completo en Docker.

---

## Ejercicio 1: Volúmenes

### 1.1: Bind mount para desarrollo

Creá esta estructura en un directorio nuevo:

```
ejercicio-volumes/
├── contador.py
└── datos/
```

`contador.py`:
```python
import os
from datetime import datetime

ARCHIVO = '/datos/contador.txt'

def leer_contador():
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO) as f:
            return int(f.read().strip())
    return 0

def guardar_contador(n):
    os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
    with open(ARCHIVO, 'w') as f:
        f.write(str(n))

if __name__ == '__main__':
    n = leer_contador()
    n += 1
    guardar_contador(n)
    print(f"[{datetime.now().isoformat()}] Contador: {n}")
```

Ejecutá varias veces:
```bash
docker run -v $(pwd):/app -v $(pwd)/datos:/datos -w /app python python contador.py
```

**Preguntas:**
1. ¿El contador incrementa entre ejecuciones? ¿Por qué?
2. ¿Qué pasa si quitás el segundo `-v` (el de datos)?
3. Mirá el contenido de `datos/contador.txt` desde tu host.

### 1.2: Named volume

Ahora usá un named volume en lugar de bind mount para los datos:

```bash
docker volume create contador-data

docker run -v $(pwd):/app -v contador-data:/datos -w /app python python contador.py
# Ejecutá varias veces

# Ver información del volumen
docker volume inspect contador-data
```

**Pregunta:** ¿Podés ver el archivo `contador.txt` directamente desde tu host? ¿Por qué?

---

## Ejercicio 2: Redes

### 2.1: Comunicación entre contenedores

```bash
# Crear una red
docker network create ejercicio-red

# Levantar un servidor HTTP simple
docker run -d --name servidor --network ejercicio-red python:3.11 \
    python -m http.server 8000

# Desde otro contenedor, intentar conectar
docker run --rm --network ejercicio-red python:3.11 \
    python -c "import urllib.request; print(urllib.request.urlopen('http://servidor:8000').read()[:100])"

# Limpieza
docker stop servidor && docker rm servidor
docker network rm ejercicio-red
```

**Tarea:** Modificá el ejemplo para que el servidor sirva archivos de un directorio tuyo (usando un volumen).

### 2.2: Redis

```bash
# Crear red
docker network create redis-net

# Levantar Redis
docker run -d --name redis --network redis-net redis:alpine

# Conectar desde Python
docker run -it --rm --network redis-net python bash
```

Dentro del contenedor:
```bash
pip install redis
python
```

```python
import redis
r = redis.Redis(host='redis', port=6379)
r.set('nombre', 'Docker')
r.set('contador', 0)
r.incr('contador')
r.incr('contador')
print(f"Nombre: {r.get('nombre').decode()}")
print(f"Contador: {r.get('contador').decode()}")
```

**Tarea:** Salí del contenedor Python y volvé a entrar. ¿Los datos persisten en Redis? ¿Por qué?

```bash
# Limpieza al final
docker stop redis && docker rm redis
docker network rm redis-net
```

---

## Ejercicio 3: Dockerfile

### 3.1: Tu primera imagen

Creá esta estructura:

```
mi-imagen/
├── Dockerfile
├── requirements.txt
└── app.py
```

`requirements.txt`:
```
cowsay==6.1
```

`app.py`:
```python
import cowsay
import sys

mensaje = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else "Hola Docker!"
cowsay.cow(mensaje)
```

`Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["python", "app.py"]
```

```bash
cd mi-imagen
docker build -t mi-cowsay .
docker run mi-cowsay
docker run mi-cowsay "Docker es genial"
```

### 3.2: Inspeccionar la imagen

```bash
# Ver capas
docker history mi-cowsay

# Ver tamaño
docker images mi-cowsay

# Comparar con python:3.11-slim
docker images python:3.11-slim
```

**Pregunta:** ¿Cuánto "agregó" tu Dockerfile sobre la imagen base?

### 3.3: Optimización

Modificá `app.py` ligeramente (cambiá el mensaje default). Rebuild:

```bash
docker build -t mi-cowsay .
```

Observá que dice "Using cache" para los pasos que no cambiaron. Ahora modificá `requirements.txt` (agregá otro paquete). Rebuild.

**Pregunta:** ¿Qué pasos se re-ejecutaron? ¿Por qué?

---

## Ejercicio 4: Docker Compose

### 4.1: App con Redis

Creá esta estructura:

```
compose-app/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── app.py
```

`requirements.txt`:
```
redis==5.0.0
```

`app.py`:
```python
import redis
import os
import time

redis_host = os.getenv('REDIS_HOST', 'localhost')
r = redis.Redis(host=redis_host, port=6379)

print(f"Conectando a Redis en {redis_host}...")

while True:
    visitas = r.incr('visitas')
    print(f"Visitas: {visitas}")
    time.sleep(2)
```

`Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
CMD ["python", "-u", "app.py"]
```

`docker-compose.yml`:
```yaml
version: '3.8'

services:
  app:
    build: .
    environment:
      - REDIS_HOST=redis
    depends_on:
      - redis

  redis:
    image: redis:alpine
```

```bash
cd compose-app
docker-compose up
```

Observá cómo se levantan ambos servicios. El contador aumenta cada 2 segundos.

**Tareas:**
1. En otra terminal, ejecutá `docker-compose ps` para ver el estado
2. Ejecutá `docker-compose logs redis` para ver solo los logs de Redis
3. Detené con Ctrl+C y volvé a ejecutar. ¿El contador sigue desde donde estaba o empieza de 0?

### 4.2: Agregar persistencia

Modificá `docker-compose.yml` para que Redis persista datos:

```yaml
version: '3.8'

services:
  app:
    build: .
    environment:
      - REDIS_HOST=redis
    depends_on:
      - redis

  redis:
    image: redis:alpine
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

volumes:
  redis-data:
```

Ahora:
```bash
docker-compose down
docker-compose up -d
# Esperar unos segundos
docker-compose down
docker-compose up
```

**Pregunta:** ¿El contador continúa o reinicia? ¿Por qué?

### 4.3: Hot reload para desarrollo

Modificá `docker-compose.yml` para desarrollo:

```yaml
version: '3.8'

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

Ahora podés editar `app.py` localmente y los cambios se reflejan (tenés que reiniciar el contenedor para que Python recargue).

Para auto-reload, podés usar watchdog o similar, pero eso lo dejamos para más adelante.

---

## Ejercicio 5: Proyecto integrador

Creá un mini-sistema con 3 servicios:

1. **web**: Un servidor HTTP simple que responda con información del sistema
2. **redis**: Cache/almacenamiento
3. **worker**: Un proceso que haga algo en background

Estructura sugerida:
```
proyecto/
├── docker-compose.yml
├── web/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py
└── worker/
    ├── Dockerfile
    ├── requirements.txt
    └── worker.py
```

El worker podría incrementar un contador en Redis cada segundo. El web podría responder con el valor actual del contador cuando recibe una request.

Este ejercicio es abierto. Lo importante es practicar la coordinación de múltiples servicios.

---

## Checklist

Antes de la próxima clase, verificá que podés:

- [ ] Usar bind mounts para compartir código con contenedores
- [ ] Crear named volumes para persistencia
- [ ] Crear redes personalizadas
- [ ] Conectar contenedores por nombre en una red
- [ ] Escribir un Dockerfile básico
- [ ] Construir una imagen con `docker build`
- [ ] Escribir un `docker-compose.yml`
- [ ] Usar `docker-compose up/down/logs`

---

*Computación II - 2026 - Clase 2*
