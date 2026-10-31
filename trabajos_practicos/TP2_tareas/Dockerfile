# Imagen base: Python 3.12 sobre Debian slim.
# - 3.12: la misma versión menor con la que corren los tests en desarrollo
#   (la consigna pide 3.11+; asyncio.timeout y TaskGroup existen desde 3.11).
# - slim: sin compiladores ni paquetes que la API no usa.
FROM python:3.12-slim

LABEL description="Plataforma de tareas distribuidas - TP2 Computacion II 2026"

# Sin .pyc dentro de la imagen, y logs sin buffer: se ven al instante en
# `docker compose logs`, no cuando se llena un buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero solo las dependencias: si cambia el código pero no
# requirements.txt, Docker reusa esta capa y no reinstala nada.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY medicion/ medicion/

# Usuario sin privilegios: la API no necesita root para nada.
# /app/datos se crea con su dueño para que el volumen de los volcados
# (ver docker-compose.yml) herede esos permisos.
RUN useradd --create-home --uid 10001 tareas \
    && mkdir -p /app/datos \
    && chown tareas:tareas /app/datos
USER tareas

# Dentro del contenedor hay que escuchar en todas las interfaces: en
# 127.0.0.1 la API sería inalcanzable desde el host.
ENV HOST=0.0.0.0 \
    DIR_ESTADO=/app/datos

EXPOSE 8000

# Forma "exec" (lista JSON), no "shell": así Python es el PID 1 y recibe
# directo el SIGTERM de `docker stop`. Con la forma shell, la señal le
# llegaría a /bin/sh, que no la reenvía, y no habría apagado ordenado.
CMD ["python", "-m", "app.main"]
