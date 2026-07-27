"""
recolector.py — Proceso recolector del monitor.

Lista los PIDs de /proc periódicamente y los mete en una Queue
para que los analizadores los tomen y procesen.

Es el "productor" del patrón productor/consumidor.
"""

import time
import os
from multiprocessing import Queue

from procfs import listar_pids


def recolector(cola_pids: Queue, intervalo: float = 2.0) -> None:
    """
    Proceso recolector. Corre en un proceso hijo.

    Args:
        cola_pids: Queue donde se meten los PIDs para los analizadores.
        intervalo: cada cuántos segundos refrescar la lista.
    """
    print(f"[Recolector PID={os.getpid()}] arrancó, intervalo={intervalo}s")

    while True:
        pids = listar_pids()
        print(f"[Recolector] listó {len(pids)} PIDs, encolando...")

        for pid in pids:
            cola_pids.put(pid)

        time.sleep(intervalo)