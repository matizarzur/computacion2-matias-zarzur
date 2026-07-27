"""
recolector.py — Proceso recolector del monitor.

Lista los PIDs de /proc periódicamente y los reparte a los analizadores.
Antes de cada pasada, envía un mensaje "nueva_pasada" al agregador
con la lista de PIDs vivos, para que limpie los muertos del snapshot.
"""

import time
import os
from multiprocessing import Queue

from procfs import listar_pids


def recolector(
    cola_pids: Queue,
    cola_resultados: Queue,
    intervalo: float = 2.0,
) -> None:
    """
    Proceso recolector. Corre en un proceso hijo.

    Args:
        cola_pids: Queue donde se meten los PIDs para los analizadores.
        cola_resultados: Queue del agregador (para el mensaje "nueva_pasada").
        intervalo: cada cuántos segundos refrescar la lista.
    """
    print(f"[Recolector PID={os.getpid()}] arrancó, intervalo={intervalo}s")

    while True:
        pids = listar_pids()
        print(f"[Recolector] listó {len(pids)} PIDs")

        # 1. Avisar al agregador ANTES de encolar los PIDs,
        #    para que limpie los procesos muertos del snapshot.
        cola_resultados.put({
            "tipo": "nueva_pasada",
            "pid": None,
            "datos": pids,   # lista de PIDs vivos
        })

        # 2. Ahora sí, encolar los PIDs para los analizadores.
        for pid in pids:
            cola_pids.put(pid)

        time.sleep(intervalo)