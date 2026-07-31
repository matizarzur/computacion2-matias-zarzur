"""
sistema.py — Analizador de Sistema (info global).

A diferencia de los otros analizadores, este NO procesa PIDs.
Se refresca solo cada X segundos leyendo los archivos globales de /proc.

Produce mensajes {"tipo": "sistema", "pid": None, "datos": dict(...)}.
"""

import os
import time
from multiprocessing import Queue

from procfs import leer_meminfo, leer_loadavg, leer_uptime, leer_stat_sistema


def analizador_sistema(cola_resultados: Queue, intervalo: float = 2.0) -> None:
    """
    Proceso analizador de Sistema. Corre en un proceso hijo.

    Args:
        cola_resultados: Queue donde publica los resultados para el agregador.
        intervalo: cada cuántos segundos refrescar la info.
    """
    print(f"[Analizador Sistema PID={os.getpid()}] arrancó, intervalo={intervalo}s")

    while True:
        # Leer los cuatro archivos globales
        meminfo = leer_meminfo()
        loadavg = leer_loadavg()
        uptime = leer_uptime()
        stat_sistema = leer_stat_sistema()

        # Empaquetar todo junto en un solo mensaje
        datos = {
            "meminfo": meminfo,
            "loadavg": loadavg,
            "uptime": uptime,
            "stat_sistema": stat_sistema,
        }

        cola_resultados.put({
            "tipo": "sistema",
            "pid": None,      # None indica "info global, no por PID"
            "datos": datos,
        })

        time.sleep(intervalo)