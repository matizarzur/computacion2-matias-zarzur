"""Configuración del servicio, leída de variables de entorno.

Los valores por defecto sirven para desarrollar; docker-compose.yml puede
pisarlos sin tocar el código.
"""
import os

HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '8000'))

# Cantidad de corrutinas worker que consumen de la cola.
WORKERS = int(os.getenv('WORKERS', '4'))

# Capacidad de la cola. Si se llena, POST /tareas responde 503 en vez de
# esperar: el endpoint nunca debe bloquearse.
COLA_MAX = int(os.getenv('COLA_MAX', '100'))

# Timeout (segundos) de las tareas que no piden uno propio.
TIMEOUT_DEFECTO = float(os.getenv('TIMEOUT_DEFECTO', '30'))
