"""
memoria.py — Analizador de Memoria.

Lee los campos Vm* de /proc/<pid>/status y los page faults de /proc/<pid>/stat,
que dan el desglose de uso de memoria del proceso.

Produce mensajes {"tipo": "memoria", "pid": <int>, "datos": ProcessMemoria}.
"""

from multiprocessing import Queue

from procfs import leer_memoria
from analizadores.plantilla import analizador_por_pid


def analizador_memoria(cola_pids: Queue, cola_resultados: Queue) -> None:
    analizador_por_pid(
        nombre="Memoria",
        tipo="memoria",
        funcion_parseo=leer_memoria,
        cola_pids=cola_pids,
        cola_resultados=cola_resultados,
    )