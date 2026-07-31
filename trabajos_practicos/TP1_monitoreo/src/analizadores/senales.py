"""
senales.py — Analizador de Señales.

Extrae las máscaras de señales del proceso (bloqueadas, ignoradas, capturadas).
"""

from multiprocessing import Queue

from procfs import leer_signals
from analizadores.plantilla import analizador_por_pid


def analizador_senales(cola_pids: Queue, cola_resultados: Queue) -> None:
    analizador_por_pid(
        nombre="Señales",
        tipo="senales",
        funcion_parseo=leer_signals,
        cola_pids=cola_pids,
        cola_resultados=cola_resultados,
    )