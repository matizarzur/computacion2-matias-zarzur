"""
agregador.py — Proceso agregador del monitor.

Recibe resultados de todos los analizadores por una Queue, y los
consolida en un snapshot compartido (Manager.dict) que el display lee.

Es el "punto de encuentro" entre productores (analizadores) y
consumidor (display).
"""

import os
from multiprocessing import Queue


def agregador(cola_resultados: Queue, snapshot: dict) -> None:
    """
    Proceso agregador. Corre en un proceso hijo.

    Args:
        cola_resultados: Queue con mensajes de los analizadores.
                         Formato: {"tipo": str, "pid": int|None, "datos": Any}
        snapshot: dict compartido (Manager.dict) donde escribir el estado.
    """
    print(f"[Agregador PID={os.getpid()}] arrancó")

    while True:
        mensaje = cola_resultados.get()   # bloquea hasta que haya algo

        tipo = mensaje["tipo"]
        pid = mensaje["pid"]
        datos = mensaje["datos"]

        if pid is None:
            # Info global del sistema: guardamos directo bajo el tipo.
            # Ej: snapshot["sistema"] = SistemaStat(...)
            snapshot[tipo] = datos
        else:
            # Info por proceso: acumulamos en un sub-dict indexado por PID.
            # Necesitamos asegurarnos de que el sub-dict exista primero.
            if tipo not in snapshot:
                snapshot[tipo] = {}

            # OJO: acá hay un truquito que quiero que veas más abajo.
            sub_dict = snapshot[tipo]
            sub_dict[pid] = datos
            snapshot[tipo] = sub_dict