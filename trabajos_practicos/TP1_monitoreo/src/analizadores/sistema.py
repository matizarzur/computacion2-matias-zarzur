"""
sistema.py — Analizador de Sistema (info global).

A diferencia de los otros analizadores, este NO procesa PIDs.
Se refresca solo cada X segundos leyendo los archivos globales de /proc.

El intervalo llega como un Value compartido, ajustable en tiempo real
con +/- desde el display cuando la vista Sistema está activa.

Produce mensajes {"tipo": "sistema", "pid": None, "datos": dict(...)}.
"""

import os
import time
from multiprocessing import Queue

from procfs import leer_meminfo, leer_loadavg, leer_uptime, leer_stat_sistema
from senales import resetear_handlers_en_hijo


def analizador_sistema(cola_resultados: Queue, intervalo_val) -> None:
    """
    Proceso analizador de Sistema. Corre en un proceso hijo.

    Args:
        cola_resultados: Queue donde publica los resultados para el agregador.
        intervalo_val: Value compartido (double) con el intervalo en segundos.
    """
    resetear_handlers_en_hijo()
    print(f"[Analizador Sistema PID={os.getpid()}] arrancó, intervalo={intervalo_val.value}s")

    while True:
        meminfo = leer_meminfo()
        loadavg = leer_loadavg()
        uptime = leer_uptime()
        stat_sistema = leer_stat_sistema()

        datos = {
            "meminfo": meminfo,
            "loadavg": loadavg,
            "uptime": uptime,
            "stat_sistema": stat_sistema,
        }

        cola_resultados.put({
            "tipo": "sistema",
            "pid": None,
            "datos": datos,
        })

        # Leer el intervalo actual del Value compartido (puede haber cambiado).
        time.sleep(intervalo_val.value)