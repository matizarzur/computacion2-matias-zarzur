"""
threads.py — Analizador de Threads.

Lista los TIDs del proceso (/proc/<pid>/task/).
"""

from multiprocessing import Queue

from procfs import listar_threads
from analizadores.plantilla import analizador_por_pid


def analizador_threads(cola_pids: Queue, cola_resultados: Queue) -> None:
    analizador_por_pid(
        nombre="Threads",
        tipo="threads",
        funcion_parseo=listar_threads,
        cola_pids=cola_pids,
        cola_resultados=cola_resultados,
    )