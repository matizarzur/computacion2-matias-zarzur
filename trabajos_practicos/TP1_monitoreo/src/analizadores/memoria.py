"""
memoria.py — Analizador de Memoria.

Lee /proc/<pid>/maps y extrae las regiones de memoria virtual del proceso.

Produce mensajes {"tipo": "memoria", "pid": <int>, "datos": list[MemoryRegion]}.
"""
from multiprocessing import Queue
from procfs import leer_maps
from analizadores.plantilla import analizador_por_pid


def analizador_memoria(cola_pids: Queue, cola_resultados: Queue) -> None:
    analizador_por_pid(
        nombre="Memoria",
        tipo="memoria",
            funcion_parseo=leer_maps,
            cola_pids=cola_pids,
            cola_resultados=cola_resultados,
    )