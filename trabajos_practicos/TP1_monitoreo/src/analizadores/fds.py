"""
fds.py — Analizador de File Descriptors.

Lista los file descriptors abiertos por cada proceso (/proc/<pid>/fd/).

Produce mensajes {"tipo": "fds", "pid": <int>, "datos": list[int]}.
"""
from multiprocessing import Queue
from procfs import listar_fds
from analizadores.plantilla import analizador_por_pid


def analizador_fds(cola_pids: Queue, cola_resultados: Queue) -> None:
    analizador_por_pid(
        nombre="FDs",
        tipo="fds",
        funcion_parseo=listar_fds,
        cola_pids=cola_pids,
        cola_resultados=cola_resultados,
    )