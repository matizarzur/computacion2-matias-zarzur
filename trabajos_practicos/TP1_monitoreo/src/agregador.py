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


def agregador(cola_resultados: Queue, snapshot: dict) -> None:
    """
    Proceso agregador. Corre en un proceso hijo.
    """
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
    Recorre las sub-estructuras del snapshot que están indexadas por PID
    y borra los PIDs que ya no están vivos.

    Solo toca dicts (los tipos por proceso). Los valores que no son dict
    (info global como "sistema") se dejan intactos.
    """
    for tipo in list(snapshot.keys()):
        valor = snapshot[tipo]
        if isinstance(valor, dict):
            # Filtrar: quedarse solo con los PIDs vivos
            filtrado = {pid: v for pid, v in valor.items() if pid in pids_vivos}
            snapshot[tipo] = filtrado