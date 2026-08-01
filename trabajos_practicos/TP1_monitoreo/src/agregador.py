"""
agregador.py — Proceso agregador del monitor.

Recibe resultados de los analizadores y del recolector por una Queue,
y consolida un snapshot compartido (Manager.dict) que el display lee.

Maneja dos tipos de mensajes:
  - "nueva_pasada": limpia del snapshot los PIDs que ya no están vivos.
  - cualquier otro tipo: guarda el dato en el snapshot.
"""

import os
from multiprocessing import Queue

from senales import resetear_handlers_en_hijo


def agregador(cola_resultados: Queue, snapshot: dict) -> None:
    """
    Proceso agregador. Corre en un proceso hijo.
    """
    resetear_handlers_en_hijo()
    print(f"[Agregador PID={os.getpid()}] arrancó")

    while True:
        mensaje = cola_resultados.get()

        tipo = mensaje["tipo"]
        pid = mensaje["pid"]
        datos = mensaje["datos"]

        if tipo == "nueva_pasada":
            # datos = lista de PIDs vivos
            pids_vivos = set(datos)
            _limpiar_snapshot(snapshot, pids_vivos)

        elif pid is None:
            # Info global (ej: SistemaStat). Se guarda directo bajo el tipo.
            snapshot[tipo] = datos

        else:
            # Info por proceso. Acumular en sub-dict indexado por PID.
            if tipo not in snapshot:
                snapshot[tipo] = {}

            sub_dict = snapshot[tipo]
            sub_dict[pid] = datos
            snapshot[tipo] = sub_dict


def _limpiar_snapshot(snapshot: dict, pids_vivos: set) -> None:
    """
    Recorre las sub-estructuras del snapshot indexadas por PID
    y borra los PIDs que ya no están vivos.

    Saltea "sistema" porque es un dict con claves fijas (meminfo, loadavg, ...)
    y no está indexado por PID.
    """
    for tipo in list(snapshot.keys()):
        if tipo == "sistema":
            continue

        valor = snapshot[tipo]
        if isinstance(valor, dict):
            filtrado = {pid: v for pid, v in valor.items() if pid in pids_vivos}
            snapshot[tipo] = filtrado