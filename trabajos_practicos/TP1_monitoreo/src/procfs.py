"""
procfs.py — Helpers para leer /proc en Linux.

Este módulo centraliza el parseo del pseudo-filesystem /proc.
Cada función corresponde a una porción específica de /proc
(status, stat, task, fd, etc.) y devuelve estructuras Python
tipadas para que los analizadores no repitan lógica de parseo.
"""

import os
import pwd
import signal
from dataclasses import dataclass
from pathlib import Path


PROC = Path("/proc")


# ============================================================
# Vista Resumen
# ============================================================

@dataclass
class ProcessStatus:
    pid: int
    ppid: int
    name: str
    state: str
    uid: int
    gid: int
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

    name = ""
    state = ""
    pid_leido = 0
    ppid = 0
    uid = 0
    gid = 0
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
            state = valor[0]
        elif clave == "Pid":
            pid_leido = int(valor)
        elif clave == "PPid":
            ppid = int(valor)
        elif clave == "Uid":
            uid = int(valor.split()[0])   # el primero es el UID real
        elif clave == "Gid":
            gid = int(valor.split()[0])   # el primero es el GID real
        elif clave == "Threads":
            threads = int(valor)
        elif clave == "VmRSS":
            vm_rss = int(valor.split()[0])

    return ProcessStatus(
        pid=pid_leido, ppid=ppid, name=name, state=state,
        uid=uid, gid=gid, threads=threads, vm_rss=vm_rss,
    )


def leer_cmdline(pid: int) -> str | None:
    """
    Lee /proc/<pid>/cmdline — el comando completo con sus argumentos.

    En el archivo los argumentos vienen separados por bytes nulos ('\\0').
    Los reemplazamos por espacios. Si está vacío (procesos kernel), se
    devuelve el nombre entre corchetes para distinguirlos.
    """
    ruta = PROC / str(pid) / "cmdline"
    try:
        with open(ruta, "rb") as f:
            crudo = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    if not crudo:
        # cmdline vacío: es un proceso kernel. Devolvemos su comm entre corchetes.
        comm = leer_comm(pid)
        return f"[{comm}]" if comm else ""

    # Los argumentos están separados por \0. Convertimos a texto legible.
    texto = crudo.replace(b"\x00", b" ").decode("utf-8", errors="replace")
    return texto.strip()


def leer_usuario(uid: int) -> str:
    """
    Traduce un UID numérico al nombre de usuario (ej: 0 -> "root").

    Si el UID no existe en la base de usuarios, devuelve el número como string.
    """
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


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
    procesos_corriendo: int
    procesos_total: int
    ultimo_pid: int


@dataclass
class Uptime:
    """Tiempo desde el arranque del sistema."""
    uptime_segundos: float
    idle_segundos: float


def leer_meminfo() -> MemInfo | None:
    """
    Lee /proc/meminfo y devuelve un MemInfo con los campos principales.
    Los valores están en kB.
    """
    try:
        with open(PROC / "meminfo") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    campos = {
        "MemTotal": 0, "MemFree": 0, "MemAvailable": 0, "Buffers": 0,
        "Cached": 0, "SwapTotal": 0, "SwapFree": 0,
    }
    for line in contenido.splitlines():
        partes = line.split(":", 1)
        if len(partes) != 2:
            continue
        clave = partes[0]
        if clave in campos:
            campos[clave] = int(partes[1].split()[0])

    return MemInfo(
        total=campos["MemTotal"], free=campos["MemFree"],
        available=campos["MemAvailable"], buffers=campos["Buffers"],
        cached=campos["Cached"], swap_total=campos["SwapTotal"],
        swap_free=campos["SwapFree"],
    )


def leer_loadavg() -> LoadAvg | None:
    """
    Lee /proc/loadavg. Formato: "0.52 0.48 0.45 2/1234 5678"
    """
    try:
        with open(PROC / "loadavg") as f:
            contenido = f.read().strip()
    except (FileNotFoundError, PermissionError):
        return None

    partes = contenido.split()
    if len(partes) < 5:
        return None

    corriendo_str, total_str = partes[3].split("/")
    return LoadAvg(
        load_1min=float(partes[0]), load_5min=float(partes[1]),
        load_15min=float(partes[2]), procesos_corriendo=int(corriendo_str),
        procesos_total=int(total_str), ultimo_pid=int(partes[4]),
    )


def leer_uptime() -> Uptime | None:
    """
    Lee /proc/uptime. Formato: "12345.67 98765.43"
    """
    try:
        with open(PROC / "uptime") as f:
            contenido = f.read().strip()
    except (FileNotFoundError, PermissionError):
        return None

    partes = contenido.split()
    if len(partes) < 2:
        return None

    return Uptime(uptime_segundos=float(partes[0]), idle_segundos=float(partes[1]))


# ============================================================
# Vista Scheduling — /proc/<pid>/stat + status
# ============================================================

@dataclass
class ProcessStat:
    """
    Datos de /proc/<pid>/stat y campos de scheduling de /proc/<pid>/status.
    """
    pid: int
    comm: str
    state: str
    ppid: int
    pgid: int                       # process group id (campo 5)
    sid: int                        # session id (campo 6)
    utime: int                      # tiempo en modo usuario (jiffies)
    stime: int                      # tiempo en modo kernel (jiffies)
    priority: int                   # prioridad de scheduling
    nice: int                       # valor nice
    num_threads: int                # cantidad de threads
    rt_priority: int                # prioridad de tiempo real (campo 40)
    policy: int                     # 0=OTHER, 1=FIFO, 2=RR, etc.
    cpus_allowed: str               # CPU affinity (de status: Cpus_allowed_list)
    vol_ctxt: int                   # context switches voluntarios (de status)
    nonvol_ctxt: int                # context switches involuntarios (de status)


# Nombres legibles de las políticas de scheduling.
POLITICAS_SCHED = {
    0: "OTHER", 1: "FIFO", 2: "RR", 3: "BATCH", 5: "IDLE", 6: "DEADLINE",
}


def leer_comm(pid: int) -> str | None:
    """
    Lee /proc/<pid>/comm — nombre corto del proceso.
    """
    try:
        with open(PROC / str(pid) / "comm") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError):
        return None


def leer_stat(pid: int) -> ProcessStat | None:
    """
    Lee /proc/<pid>/stat (scheduling y tiempos de CPU) y complementa con
    los campos de context switches y affinity de /proc/<pid>/status.

    El campo 2 (comm) viene entre paréntesis y puede contener espacios,
    por eso se parsea buscando el ÚLTIMO ')'.

    Campos de stat usados (1-indexed):
      1 pid | 2 (comm) | 3 state | 4 ppid | 5 pgrp | 6 session
      14 utime | 15 stime | 18 priority | 19 nice | 20 num_threads
      40 rt_priority | 41 policy
    """
    try:
        with open(PROC / str(pid) / "stat") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    try:
        inicio = contenido.index("(")
        fin = contenido.rindex(")")
    except ValueError:
        return None

    pid_str = contenido[:inicio].strip()
    comm = contenido[inicio + 1:fin]
    resto = contenido[fin + 1:].split()
    # resto[0] = campo 3 (state). Para el campo N del archivo -> resto[N-3].

    try:
        stat_data = {
            "pid": int(pid_str),
            "comm": comm,
            "state": resto[0],          # campo 3
            "ppid": int(resto[1]),      # campo 4
            "pgid": int(resto[2]),      # campo 5
            "sid": int(resto[3]),       # campo 6
            "utime": int(resto[11]),    # campo 14
            "stime": int(resto[12]),    # campo 15
            "priority": int(resto[15]), # campo 18
            "nice": int(resto[16]),     # campo 19
            "num_threads": int(resto[17]),  # campo 20
            "rt_priority": int(resto[37]),  # campo 40
            "policy": int(resto[38]),   # campo 41
        }
    except (IndexError, ValueError):
        return None

    # Campos extra de /proc/<pid>/status: affinity y context switches.
    cpus_allowed = ""
    vol_ctxt = 0
    nonvol_ctxt = 0
    try:
        with open(PROC / str(pid) / "status") as f:
            for line in f:
                if line.startswith("Cpus_allowed_list:"):
                    cpus_allowed = line.split(":", 1)[1].strip()
                elif line.startswith("voluntary_ctxt_switches:"):
                    vol_ctxt = int(line.split(":", 1)[1].strip())
                elif line.startswith("nonvoluntary_ctxt_switches:"):
                    nonvol_ctxt = int(line.split(":", 1)[1].strip())
    except (FileNotFoundError, PermissionError):
        pass

    return ProcessStat(
        cpus_allowed=cpus_allowed, vol_ctxt=vol_ctxt, nonvol_ctxt=nonvol_ctxt,
        **stat_data,
    )


def nombre_politica(policy: int) -> str:
    """Traduce el número de política de scheduling a su nombre."""
    return POLITICAS_SCHED.get(policy, f"?({policy})")


# ============================================================
# Vista Memoria — /proc/<pid>/status, /stat y /maps
# ============================================================

@dataclass
class ProcessMemoria:
    """
    Datos de memoria de un proceso. Los Vm* están en kB y pueden ser None
    en procesos kernel. Los page faults son contadores acumulados.
    """
    vm_size: int | None
    vm_rss: int | None
    vm_data: int | None
    vm_stk: int | None
    vm_exe: int | None
    vm_lib: int | None
    vm_hwm: int | None
    vm_swap: int | None
    minor_faults: int
    major_faults: int


@dataclass
class MemoryRegion:
    """Una región de memoria virtual del proceso (una línea de /proc/<pid>/maps)."""
    addr_start: int
    addr_end: int
    permisos: str
    offset: int
    pathname: str

    @property
    def size(self) -> int:
        return self.addr_end - self.addr_start


def leer_memoria(pid: int) -> ProcessMemoria | None:
    """
    Lee los campos de memoria de /proc/<pid>/status y los page faults
    de /proc/<pid>/stat.
    """
    ruta_status = PROC / str(pid) / "status"
    try:
        with open(ruta_status) as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    vm = {
        "VmSize": None, "VmRSS": None, "VmData": None, "VmStk": None,
        "VmExe": None, "VmLib": None, "VmHWM": None, "VmSwap": None,
    }
    for line in contenido.splitlines():
        partes = line.split(":", 1)
        if len(partes) != 2:
            continue
        clave = partes[0]
        if clave in vm:
            vm[clave] = int(partes[1].split()[0])

    # Page faults de /proc/<pid>/stat (campos 10 y 12).
    minor_faults = 0
    major_faults = 0
    try:
        with open(PROC / str(pid) / "stat") as f:
            contenido_stat = f.read()
        fin = contenido_stat.rindex(")")
        resto = contenido_stat[fin + 1:].split()
        # resto[0] = campo 3. minflt = campo 10 -> resto[7], majflt = campo 12 -> resto[9].
        minor_faults = int(resto[7])
        major_faults = int(resto[9])
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        pass

    return ProcessMemoria(
        vm_size=vm["VmSize"], vm_rss=vm["VmRSS"], vm_data=vm["VmData"],
        vm_stk=vm["VmStk"], vm_exe=vm["VmExe"], vm_lib=vm["VmLib"],
        vm_hwm=vm["VmHWM"], vm_swap=vm["VmSwap"],
        minor_faults=minor_faults, major_faults=major_faults,
    )


def leer_maps(pid: int) -> list[MemoryRegion] | None:
    """
    Lee /proc/<pid>/maps y devuelve la lista de regiones de memoria virtual.

    Formato de cada línea:
      addr_start-addr_end perms offset dev inode pathname
    """
    try:
        with open(PROC / str(pid) / "maps") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    regiones = []
    for line in contenido.splitlines():
        partes = line.split(maxsplit=5)
        if len(partes) < 5:
            continue
        rango = partes[0].split("-")
        if len(rango) != 2:
            continue
        regiones.append(MemoryRegion(
            addr_start=int(rango[0], 16),
            addr_end=int(rango[1], 16),
            permisos=partes[1],
            offset=int(partes[2], 16),
            pathname=partes[5] if len(partes) == 6 else "",
        ))
    return regiones


def agrupar_regiones(regiones: list[MemoryRegion]) -> dict:
    """
    Agrupa las regiones de memoria por tipo y suma sus tamaños (en bytes).

    Categorías:
      heap, stack, text (código ejecutable), data (datos con escritura),
      shared (librerías), anon (anónimas sin nombre).
    """
    grupos = {
        "heap": 0, "stack": 0, "text": 0,
        "data": 0, "shared": 0, "anon": 0,
    }
    for r in regiones:
        if r.pathname == "[heap]":
            grupos["heap"] += r.size
        elif r.pathname == "[stack]":
            grupos["stack"] += r.size
        elif "x" in r.permisos:
            grupos["text"] += r.size        # ejecutable = código
        elif r.pathname and r.pathname.startswith("/"):
            grupos["shared"] += r.size       # mapeada desde un archivo (librería)
        elif "w" in r.permisos:
            grupos["data"] += r.size         # escribible con nombre = datos
        else:
            grupos["anon"] += r.size
    return grupos


# ============================================================
# Vista File Descriptors — /proc/<pid>/fd
# ============================================================

@dataclass
class FileDescriptor:
    """Un file descriptor abierto por el proceso."""
    numero: int
    destino: str        # a dónde apunta el symlink
    tipo: str           # file / socket / pipe / tty / anon / desconocido


def listar_fds(pid: int) -> list[int] | None:
    """Lista los números de file descriptors abiertos por el proceso."""
    try:
        entries = os.listdir(PROC / str(pid) / "fd")
    except (FileNotFoundError, PermissionError):
        return None
    return [int(fd) for fd in entries if fd.isdigit()]


def _inferir_tipo_fd(destino: str) -> str:
    """Infiere el tipo de un FD a partir del destino de su symlink."""
    if destino.startswith("socket:"):
        return "socket"
    if destino.startswith("pipe:"):
        return "pipe"
    if destino.startswith("anon_inode:"):
        return "anon"
    if destino.startswith("/dev/pts/") or destino.startswith("/dev/tty"):
        return "tty"
    if destino.startswith("/"):
        return "file"
    return "desconocido"


def resolver_fds(pid: int) -> list[FileDescriptor] | None:
    """
    Lista los FDs del proceso resolviendo el destino de cada symlink
    y clasificando su tipo.
    """
    base = PROC / str(pid) / "fd"
    try:
        entries = os.listdir(base)
    except (FileNotFoundError, PermissionError):
        return None

    resultado = []
    for entry in entries:
        if not entry.isdigit():
            continue
        numero = int(entry)
        try:
            destino = os.readlink(base / entry)
        except (FileNotFoundError, PermissionError, OSError):
            # El FD pudo cerrarse entre el listado y el readlink (TOCTOU).
            continue
        resultado.append(FileDescriptor(
            numero=numero, destino=destino, tipo=_inferir_tipo_fd(destino),
        ))
    return resultado


# ============================================================
# Vista Threads — /proc/<pid>/task
# ============================================================

@dataclass
class ThreadInfo:
    """Información de un thread (LWP) individual."""
    tid: int
    comm: str
    state: str
    utime: int              # jiffies en modo usuario
    stime: int              # jiffies en modo kernel
    vol_ctxt: int           # context switches voluntarios
    nonvol_ctxt: int        # context switches involuntarios


def listar_threads(pid: int) -> list[int] | None:
    """Lista los TIDs del proceso (subcarpetas de /proc/<pid>/task/)."""
    try:
        entries = os.listdir(PROC / str(pid) / "task")
    except (FileNotFoundError, PermissionError):
        return None
    return [int(t) for t in entries if t.isdigit()]


def leer_threads_detalle(pid: int) -> list[ThreadInfo] | None:
    """
    Lee el detalle de cada thread del proceso: estado, comm, tiempos de CPU
    y context switches. Datos de /proc/<pid>/task/<tid>/stat y /status.
    """
    base = PROC / str(pid) / "task"
    try:
        entries = os.listdir(base)
    except (FileNotFoundError, PermissionError):
        return None

    threads = []
    for entry in entries:
        if not entry.isdigit():
            continue
        tid = int(entry)

        # stat del thread: estado y tiempos de CPU.
        comm = ""
        state = ""
        utime = 0
        stime = 0
        try:
            with open(base / entry / "stat") as f:
                contenido = f.read()
            inicio = contenido.index("(")
            fin = contenido.rindex(")")
            comm = contenido[inicio + 1:fin]
            resto = contenido[fin + 1:].split()
            state = resto[0]
            utime = int(resto[11])
            stime = int(resto[12])
        except (FileNotFoundError, PermissionError, ValueError, IndexError):
            continue

        # status del thread: context switches.
        vol_ctxt = 0
        nonvol_ctxt = 0
        try:
            with open(base / entry / "status") as f:
                for line in f:
                    if line.startswith("voluntary_ctxt_switches:"):
                        vol_ctxt = int(line.split(":", 1)[1].strip())
                    elif line.startswith("nonvoluntary_ctxt_switches:"):
                        nonvol_ctxt = int(line.split(":", 1)[1].strip())
        except (FileNotFoundError, PermissionError):
            pass

        threads.append(ThreadInfo(
            tid=tid, comm=comm, state=state, utime=utime, stime=stime,
            vol_ctxt=vol_ctxt, nonvol_ctxt=nonvol_ctxt,
        ))
    return threads


# ============================================================
# Vista Señales — /proc/<pid>/status
# ============================================================

@dataclass
class ProcessSignals:
    """
    Máscaras de señales de /proc/<pid>/status. Cada campo es una máscara
    donde cada bit representa una señal (bit N = señal N+1).
    Se guardan como int (convertidos de hex) para trabajar con bits.
    """
    sig_pnd: int
    shd_pnd: int
    sig_blk: int
    sig_ign: int
    sig_cgt: int


def leer_signals(pid: int) -> ProcessSignals | None:
    """
    Lee las máscaras de señales de /proc/<pid>/status.
    Vienen en hexadecimal (ej: "0000000180010000").
    """
    ruta = PROC / str(pid) / "status"
    try:
        with open(ruta) as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    campos = {"SigPnd": 0, "ShdPnd": 0, "SigBlk": 0, "SigIgn": 0, "SigCgt": 0}
    for line in contenido.splitlines():
        partes = line.split(":", 1)
        if len(partes) != 2:
            continue
        clave = partes[0]
        if clave in campos:
            campos[clave] = int(partes[1].strip(), 16)

    return ProcessSignals(
        sig_pnd=campos["SigPnd"], shd_pnd=campos["ShdPnd"],
        sig_blk=campos["SigBlk"], sig_ign=campos["SigIgn"],
        sig_cgt=campos["SigCgt"],
    )


def decodificar_senales(mascara: int) -> list[str]:
    """
    Convierte una máscara de señales a la lista de nombres legibles.

    Cada bit de la máscara representa una señal: el bit 0 es la señal 1
    (SIGHUP), el bit 1 la señal 2 (SIGINT), etc. Usamos el módulo signal
    para traducir el número al nombre.
    """
    nombres = []
    for bit in range(64):
        if mascara & (1 << bit):
            numero = bit + 1          # el bit 0 corresponde a la señal 1
            try:
                nombres.append(signal.Signals(numero).name)
            except ValueError:
                nombres.append(f"SIG{numero}")   # señal sin nombre conocido
    return nombres


# ============================================================
# Vista Sistema — /proc/stat
# ============================================================

@dataclass
class SistemaStat:
    """Info agregada del sistema, de /proc/stat."""
    cpu_user: int
    cpu_nice: int
    cpu_system: int
    cpu_idle: int
    cpu_iowait: int
    procesos_creados: int
    context_switches: int
    procs_running: int
    procs_blocked: int
    btime: int                # boot time (segundos desde epoch)


def leer_stat_sistema() -> SistemaStat | None:
    """
    Lee /proc/stat — info agregada del sistema (CPU total, context switches,
    procesos creados, corriendo, bloqueados y boot time).
    """
    try:
        with open(PROC / "stat") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    cpu_user = cpu_nice = cpu_system = cpu_idle = cpu_iowait = 0
    procesos_creados = context_switches = procs_running = procs_blocked = 0
    btime = 0

    for line in contenido.splitlines():
        partes = line.split()
        if not partes:
            continue
        if partes[0] == "cpu":
            cpu_user = int(partes[1])
            cpu_nice = int(partes[2])
            cpu_system = int(partes[3])
            cpu_idle = int(partes[4])
            cpu_iowait = int(partes[5]) if len(partes) > 5 else 0
        elif partes[0] == "ctxt":
            context_switches = int(partes[1])
        elif partes[0] == "processes":
            procesos_creados = int(partes[1])
        elif partes[0] == "procs_running":
            procs_running = int(partes[1])
        elif partes[0] == "procs_blocked":
            procs_blocked = int(partes[1])
        elif partes[0] == "btime":
            btime = int(partes[1])

    return SistemaStat(
        cpu_user=cpu_user, cpu_nice=cpu_nice, cpu_system=cpu_system,
        cpu_idle=cpu_idle, cpu_iowait=cpu_iowait,
        procesos_creados=procesos_creados, context_switches=context_switches,
        procs_running=procs_running, procs_blocked=procs_blocked, btime=btime,
    )


# ============================================================
# Prueba manual del módulo
# ============================================================

if __name__ == "__main__":
    pids = listar_pids()
    print(f"Procesos detectados: {len(pids)}")

    pid_prueba = os.getpid()   # nos analizamos a nosotros mismos
    print(f"\n=== Analizando el propio proceso (PID {pid_prueba}) ===")

    print("\n--- leer_status ---")
    print(leer_status(pid_prueba))

    print("\n--- leer_cmdline ---")
    print(leer_cmdline(pid_prueba))

    print("\n--- leer_usuario(0) y leer_usuario(uid propio) ---")
    st = leer_status(pid_prueba)
    print("uid 0 ->", leer_usuario(0))
    print(f"uid {st.uid} ->", leer_usuario(st.uid))

    print("\n--- leer_memoria ---")
    print(leer_memoria(pid_prueba))

    print("\n--- leer_stat (scheduling) ---")
    stat = leer_stat(pid_prueba)
    print(stat)
    if stat:
        print("politica:", nombre_politica(stat.policy))

    print("\n--- agrupar_regiones ---")
    regiones = leer_maps(pid_prueba)
    if regiones:
        grupos = agrupar_regiones(regiones)
        for tipo, tam in grupos.items():
            print(f"  {tipo}: {tam // 1024} kB")

    print("\n--- resolver_fds (primeros 5) ---")
    fds = resolver_fds(pid_prueba)
    if fds:
        for fd in fds[:5]:
            print(f"  fd {fd.numero}: {fd.tipo} -> {fd.destino}")

    print("\n--- leer_threads_detalle ---")
    threads = leer_threads_detalle(pid_prueba)
    if threads:
        print(f"Total threads: {len(threads)}")
        for t in threads[:3]:
            print(f"  tid {t.tid} ({t.comm}) estado={t.state} ctxt={t.vol_ctxt}/{t.nonvol_ctxt}")

    print("\n--- decodificar_senales ---")
    sig = leer_signals(pid_prueba)
    if sig:
        print("bloqueadas (SigBlk):", decodificar_senales(sig.sig_blk))
        print("ignoradas  (SigIgn):", decodificar_senales(sig.sig_ign))
        print("con handler(SigCgt):", decodificar_senales(sig.sig_cgt))

    print("\n--- leer_stat_sistema ---")
    print(leer_stat_sistema())