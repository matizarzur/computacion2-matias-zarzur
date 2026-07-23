"""
procfs.py — Helpers para leer /proc en Linux.

Este módulo centraliza el parseo del pseudo-filesystem /proc.
Cada función corresponde a una porción específica de /proc
(status, stat, task, fd, etc.) y devuelve estructuras Python
tipadas para que los analizadores no repitan lógica de parseo.
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROC = Path("/proc")


@dataclass
class ProcessStatus:
    pid: int
    ppid: int
    name: str
    state: str
    uid: int
    threads: int
    vm_rss: int | None   # None para procesos kernel (no tienen memoria de usuario)


def listar_pids() -> list[int]:
    """
    Devuelve la lista de PIDs de todos los procesos actualmente
    en ejecución en el sistema.

    Fuente: nombres de las subcarpetas de /proc cuyo nombre es
    enteramente numérico.
    """
    pids = []
    for entry in os.listdir(PROC):
        if entry.isdigit():
            pids.append(int(entry))
    return pids


def leer_status(pid: int) -> ProcessStatus | None:
    """
    Lee /proc/<pid>/status y devuelve un ProcessStatus con
    los campos relevantes para la vista Resumen.

    Devuelve None si:
      - el proceso desapareció entre el listado y esta lectura
      - no tenemos permisos para leerlo
    """
    ruta = PROC / str(pid) / "status"

    try:
        with open(ruta) as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    # Valores por default. vm_rss queda en None si el proceso no la tiene
    # (típicamente procesos kernel como kthreadd, PID 2)
    name = ""
    state = ""
    pid_leido = 0
    ppid = 0
    uid = 0
    threads = 0
    vm_rss = None

    for line in contenido.splitlines():
        partes = line.split(":", 1)
        if len(partes) != 2:
            continue
        clave = partes[0]
        valor = partes[1].strip()

        if clave == "Name":
            name = valor
        elif clave == "State":
            state = valor[0]   # ej: "S (sleeping)" -> "S"
        elif clave == "Pid":
            pid_leido = int(valor)
        elif clave == "PPid":
            ppid = int(valor)
        elif clave == "Uid":
            uid = int(valor.split()[0])   # el primero es el UID real
        elif clave == "Threads":
            threads = int(valor)
        elif clave == "VmRSS":
            vm_rss = int(valor.split()[0])   # "13548 kB" -> 13548

    return ProcessStatus(
        pid=pid_leido,
        ppid=ppid,
        name=name,
        state=state,
        uid=uid,
        threads=threads,
        vm_rss=vm_rss,
    )


if __name__ == "__main__":
    pids = listar_pids()
    print(f"Procesos detectados: {len(pids)}")
    print(f"Primeros 10 PIDs: {sorted(pids)[:10]}")

    print("\n--- Prueba leer_status(1) ---")
    print(leer_status(1))

    print("\n--- Prueba leer_status(2) (proceso kernel) ---")
    print(leer_status(2))