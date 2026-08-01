"""
plantilla.py — Plantilla común para los analizadores por-PID.

Encapsula el loop compartido: tomar un PID de la cola, parsearlo con
una función de procfs, y publicar el resultado en cola_resultados.
Cada analizador concreto solo declara su nombre, tipo y función de parseo.
"""

import os
from typing import Callable
from multiprocessing import Queue

from senales import resetear_handlers_en_hijo


def analizador_por_pid(
    nombre: str,
    tipo: str,
    funcion_parseo: Callable[[int], object],
    cola_pids: Queue,
    cola_resultados: Queue,
) -> None:
    """
    Loop genérico para analizadores por-PID.
    """
    resetear_handlers_en_hijo()
    print(f"[Analizador {nombre} PID={os.getpid()}] arrancó")

    while True:
        pid = cola_pids.get()

        datos = funcion_parseo(pid)
        if datos is None:
            continue

        cola_resultados.put({
            "tipo": tipo,
            "pid": pid,
            "datos": datos,
        })