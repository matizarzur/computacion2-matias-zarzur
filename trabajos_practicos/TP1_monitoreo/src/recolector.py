"""
recolector.py — Proceso recolector del monitor.

Lista los PIDs de /proc periódicamente y los reparte a los analizadores.
Antes de cada pasada, envía un mensaje "nueva_pasada" al agregador
con la lista de PIDs vivos, para que limpie los muertos del snapshot.

El intervalo llega como un Value compartido: el display puede ajustarlo
en tiempo real con +/- y el recolector lee el nuevo valor en cada vuelta.
"""

import time
import os
from multiprocessing import Queue

from procfs import listar_pids
from senales import resetear_handlers_en_hijo


def recolector(
    colas_analizadores: list[Queue],
    cola_resultados: Queue,
    intervalo_val,
) -> None:
    """
    Proceso recolector. Corre en un proceso hijo.

    Args:
        colas_analizadores: lista de Queues, una por cada analizador.
        cola_resultados: Queue del agregador (para el mensaje "nueva_pasada").
        intervalo_val: Value compartido (double) con el intervalo en segundos.
                       El display lo modifica; el recolector lo lee cada vuelta.
    """
    resetear_handlers_en_hijo()
    print(f"[Recolector PID={os.getpid()}] arrancó, intervalo={intervalo_val.value}s")

    while True:
        pids = listar_pids()

        # Avisar al agregador antes de encolar los PIDs.
        cola_resultados.put({
            "tipo": "nueva_pasada",
            "pid": None,
            "datos": pids,
        })

        # Encolar cada PID en TODAS las colas de analizadores.
        for pid in pids:
            for cola in colas_analizadores:
                cola.put(pid)

        # Leer el intervalo actual del Value compartido (puede haber cambiado).
        time.sleep(intervalo_val.value)