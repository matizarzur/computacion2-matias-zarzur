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

# ============================================================
# Info global del sistema
# ============================================================

@dataclass
class MemInfo:
    """Memoria del sistema completo, en kB."""
    total: int
    free: int
    available: int
    buffers: int
    cached: int
    swap_total: int
    swap_free: int


@dataclass
class LoadAvg:
    """Load average del sistema."""
    load_1min: float
    load_5min: float
    load_15min: float
    procesos_corriendo: int      # los que están en estado R
    procesos_total: int          # total de procesos + threads
    ultimo_pid: int              # PID asignado más recientemente


@dataclass
class Uptime:
    """Tiempo desde el arranque del sistema."""
    uptime_segundos: float       # cuánto hace que arrancó la máquina
    idle_segundos: float         # tiempo idle sumado de todas las CPUs


def leer_meminfo() -> MemInfo | None:
    """
    Lee /proc/meminfo y devuelve un MemInfo con los campos principales.
    Los valores están en kB (kilobytes).

    Devuelve None si el archivo no se puede leer (raro, pero robusto por si acaso).
    """
    try:
        with open(PROC / "meminfo") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    # Valores por default en 0 (por si algún campo no existe en el kernel actual).
    campos = {
        "MemTotal": 0,
        "MemFree": 0,
        "MemAvailable": 0,
        "Buffers": 0,
        "Cached": 0,
        "SwapTotal": 0,
        "SwapFree": 0,
    }

    for line in contenido.splitlines():
        partes = line.split(":", 1)
        if len(partes) != 2:
            continue
        clave = partes[0]
        if clave in campos:
            # El valor viene como "16234000 kB". Nos quedamos con el número.
            campos[clave] = int(partes[1].split()[0])

    return MemInfo(
        total=campos["MemTotal"],
        free=campos["MemFree"],
        available=campos["MemAvailable"],
        buffers=campos["Buffers"],
        cached=campos["Cached"],
        swap_total=campos["SwapTotal"],
        swap_free=campos["SwapFree"],
    )


def leer_loadavg() -> LoadAvg | None:
    """
    Lee /proc/loadavg y devuelve un LoadAvg.

    Formato del archivo: "0.52 0.48 0.45 2/1234 5678"
    Los tres primeros son floats (1min, 5min, 15min).
    El cuarto tiene la forma "corriendo/total".
    El quinto es el último PID asignado.
    """
    try:
        with open(PROC / "loadavg") as f:
            contenido = f.read().strip()
    except (FileNotFoundError, PermissionError):
        return None

    partes = contenido.split()
    if len(partes) < 5:
        return None

    # El cuarto campo "corriendo/total" hay que separarlo aparte.
    corriendo_str, total_str = partes[3].split("/")

    return LoadAvg(
        load_1min=float(partes[0]),
        load_5min=float(partes[1]),
        load_15min=float(partes[2]),
        procesos_corriendo=int(corriendo_str),
        procesos_total=int(total_str),
        ultimo_pid=int(partes[4]),
    )


def leer_uptime() -> Uptime | None:
    """
    Lee /proc/uptime y devuelve un Uptime.

    Formato: "12345.67 98765.43"
    Primero: segundos desde el arranque.
    Segundo: suma del tiempo idle de todas las CPUs (por eso puede ser mayor
             que el uptime si tenés varios cores).
    """
    try:
        with open(PROC / "uptime") as f:
            contenido = f.read().strip()
    except (FileNotFoundError, PermissionError):
        return None

    partes = contenido.split()
    if len(partes) < 2:
        return None

    return Uptime(
        uptime_segundos=float(partes[0]),
        idle_segundos=float(partes[1]),
    )

if __name__ == "__main__":
    pids = listar_pids()
    print(f"Procesos detectados: {len(pids)}")
    print(f"Primeros 10 PIDs: {sorted(pids)[:10]}")

    print("\n--- leer_status(1) ---")
    print(leer_status(1))

    print("\n--- leer_status(2) ---")
    print(leer_status(2))

    print("\n--- leer_meminfo() ---")
    print(leer_meminfo())

    print("\n--- leer_loadavg() ---")
    print(leer_loadavg())

    print("\n--- leer_uptime() ---")
    print(leer_uptime())