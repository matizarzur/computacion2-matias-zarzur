"""
fds.py — Analizador de File Descriptors.

Lista los file descriptors abiertos por cada proceso, resolviendo el
destino de cada symlink (/proc/<pid>/fd/) e infiriendo su tipo.

Produce mensajes {"tipo": "fds", "pid": <int>, "datos": list[FileDescriptor]}.
"""

from multiprocessing import Queue

from procfs import resolver_fds
from analizadores.plantilla import analizador_por_pid


def analizador_fds(cola_pids: Queue, cola_resultados: Queue) -> None:
    analizador_por_pid(
        nombre="FDs",
        tipo="fds",
        funcion_parseo=resolver_fds,
        cola_pids=cola_pids,
        cola_resultados=cola_resultados,
    )