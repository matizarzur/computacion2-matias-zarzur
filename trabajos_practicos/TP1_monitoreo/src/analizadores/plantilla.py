"""
plantilla.py — Plantilla común para los analizadores por-PID.

Los analizadores por-PID comparten la misma lógica de loop:
  - tomar un PID de cola_pids
  - correr una función de parseo sobre él
  - publicar el resultado en cola_resultados

Esta función encapsula ese patrón. Cada analizador concreto
solo declara su nombre, su función de parseo, y su tipo de mensaje.
"""

import os
from typing import Callable
from multiprocessing import Queue


def analizador_por_pid(
    nombre: str,
    tipo: str,
    funcion_parseo: Callable[[int], object],
    cola_pids: Queue,
    cola_resultados: Queue,
) -> None:
    """
    Loop genérico para analizadores por-PID.

    Args:
        nombre: nombre para logs (ej: "Resumen", "Memoria").
        tipo: etiqueta para el mensaje al agregador (ej: "resumen").
        funcion_parseo: función de procfs que toma un pid y devuelve datos.
                        Debe devolver None si el proceso murió o falló la lectura.
        cola_pids: Queue de donde toma PIDs.
        cola_resultados: Queue donde publica los resultados.
    """
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