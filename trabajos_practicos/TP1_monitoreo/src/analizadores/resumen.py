"""
resumen.py — Analizador de Resumen.

Lee /proc/<pid>/status y extrae los campos básicos: nombre, estado,
memoria, threads, uid.

Produce mensajes {"tipo": "resumen", "pid": <int>, "datos": ProcessStatus(...)}.
"""

from multiprocessing import Queue

from procfs import leer_status
from analizadores.plantilla import analizador_por_pid


def analizador_resumen(cola_pids: Queue, cola_resultados: Queue) -> None:
    analizador_por_pid(
        nombre="Resumen",
        tipo="resumen",
        funcion_parseo=leer_status,
        cola_pids=cola_pids,
        cola_resultados=cola_resultados,
    )