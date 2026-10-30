"""Configuración del servicio, leída de variables de entorno.

Los valores por defecto sirven para desarrollar; docker-compose.yml puede
pisarlos sin tocar el código.
"""
import os
from pathlib import Path

HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '8000'))

# Cantidad de corrutinas worker que consumen de la cola.
WORKERS = int(os.getenv('WORKERS', '4'))

# Capacidad de la cola. Si se llena, POST /tareas responde 503 en vez de
# esperar: el endpoint nunca debe bloquearse.
COLA_MAX = int(os.getenv('COLA_MAX', '100'))

# Timeout (segundos) de las tareas que no piden uno propio.
TIMEOUT_DEFECTO = float(os.getenv('TIMEOUT_DEFECTO', '30'))

# Timeout de cada pedido HTTP de la tarea "descargar".
HTTP_TIMEOUT = float(os.getenv('HTTP_TIMEOUT', '10'))

# Dónde corre el trabajo CPU-bound ("hashear"):
#   'executor' -> en procesos aparte, el event loop queda libre (correcto)
#   'loop'     -> dentro del event loop, que se bloquea (SOLO para mostrar el
#                 problema en la medición 2)
MODO_CPU = os.getenv('MODO_CPU', 'executor')
if MODO_CPU not in ('executor', 'loop'):
    raise ValueError(f"MODO_CPU debe ser 'executor' o 'loop', no {MODO_CPU!r}")

# Procesos del pool para las tareas CPU-bound.
EXECUTOR_WORKERS = int(os.getenv('EXECUTOR_WORKERS', os.cpu_count() or 1))

# "hashear" se manda al executor de a bloques de esta cantidad de vueltas.
# Un bloque ya enviado no se puede cancelar, así que el tamaño es lo máximo
# que un proceso sigue ocupado después de cancelar (~0.1 s con el valor por
# defecto en la máquina de desarrollo).
BLOQUE_HASH = int(os.getenv('BLOQUE_HASH', '100000'))

# Apagado ordenado: cuántos segundos se espera a las tareas en curso antes de
# cancelarlas. Tiene que ser menor que el tiempo que Docker espera antes de
# mandar SIGKILL (ver docker-compose.yml).
APAGADO_ESPERA = float(os.getenv('APAGADO_ESPERA', '5'))

# Dónde se escriben los volcados estado_<timestamp>.json.
DIR_ESTADO = Path(os.getenv('DIR_ESTADO',
                            Path(__file__).resolve().parent.parent / 'datos'))
