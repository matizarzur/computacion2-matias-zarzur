"""
scheduling.py — Analizador de Scheduling.

Extrae prioridad, nice, política y tiempos de CPU del proceso.
"""

from multiprocessing import Queue

from procfs import leer_stat
from analizadores.plantilla import analizador_por_pid


def analizador_scheduling(cola_pids: Queue, cola_resultados: Queue) -> None:
    analizador_por_pid(
        nombre="Scheduling",
        tipo="scheduling",
        funcion_parseo=leer_stat,
        cola_pids=cola_pids,
        cola_resultados=cola_resultados,
    )