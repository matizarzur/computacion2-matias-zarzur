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
import signal
import pwd

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
    usuario: str         # nombre de usuario resuelto desde el UID
    cmdline: str         # comando completo con argumentos


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
    
    usuario = leer_usuario(uid)
    cmdline = leer_cmdline(pid_leido) or name

    return ProcessStatus(
        pid=pid_leido,
        ppid=ppid,
        name=name,
        state=state,
        uid=uid,
        threads=threads,
        vm_rss=vm_rss,
        usuario=usuario,
        cmdline=cmdline,
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

# ============================================================
# Info por proceso
# ============================================================

@dataclass
class ProcessStat:
    """
    Datos de /proc/<pid>/stat.
    Incluye tiempos de CPU, prioridad, política de scheduling.
    """
    pid: int
    comm: str                    # nombre del proceso (entre paréntesis en el archivo)
    state: str                   # letra: R/S/D/T/Z
    ppid: int
    utime: int                   # tiempo en modo usuario (jiffies)
    stime: int                   # tiempo en modo kernel (jiffies)
    priority: int                # prioridad de scheduling
    nice: int                    # valor nice
    num_threads: int             # cantidad de threads
    policy: int                  # 0=OTHER, 1=FIFO, 2=RR, etc.


def leer_comm(pid: int) -> str | None:
    """
    Lee /proc/<pid>/comm — nombre corto del proceso.
    Más liviano que leer_status si solo necesitás el nombre.
    """
    try:
        with open(PROC / str(pid) / "comm") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError):
        return None

def leer_cmdline(pid: int) -> str | None:
    """
    Lee /proc/<pid>/cmdline — el comando completo con sus argumentos.

    En el archivo los argumentos vienen separados por bytes nulos ('\\0').
    Los reemplazamos por espacios. Si el archivo está vacío (procesos kernel),
    devolvemos el nombre corto entre corchetes, igual que htop.
    """
    ruta = PROC / str(pid) / "cmdline"
    try:
        with open(ruta, "rb") as f:      # "rb" = leer en binario (son bytes crudos)
            crudo = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    if not crudo:
        # cmdline vacío = proceso kernel. Mostramos su comm entre corchetes.
        comm = leer_comm(pid)
        return f"[{comm}]" if comm else ""

    # Los argumentos vienen separados por \0. Los pasamos a espacios.
    texto = crudo.replace(b"\x00", b" ").decode("utf-8", errors="replace")
    return texto.strip()

def leer_usuario(uid: int) -> str:
    """
    Traduce un UID numérico al nombre de usuario (ej: 0 -> "root").

    Usa /etc/passwd a través del módulo pwd. Si el UID no existe en la
    base de usuarios, devuelve el número como string.
    """
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)

def leer_stat(pid: int) -> ProcessStat | None:
    """
    Lee /proc/<pid>/stat — datos de scheduling y tiempos de CPU.

    El archivo es una sola línea con campos separados por espacios.
    OJO: el campo 2 (comm) viene entre paréntesis y puede contener
    espacios, así que hay que parsearlo con cuidado.

    Formato (simplificado, campos 1-indexed):
      1  pid
      2  (comm)
      3  state
      4  ppid
      14 utime
      15 stime
      18 priority
      19 nice
      20 num_threads
      41 policy
    """
    try:
        with open(PROC / str(pid) / "stat") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    # El nombre viene entre paréntesis y puede tener espacios adentro.
    # Estrategia: buscar el ÚLTIMO ')' y partir ahí.
    # Ej: "1234 (mi proceso) S 1 ..." → antes=1234, comm=mi proceso, resto=S 1 ...
    inicio = contenido.index("(")
    fin = contenido.rindex(")")
    pid_str = contenido[:inicio].strip()
    comm = contenido[inicio + 1:fin]
    resto = contenido[fin + 1:].split()

    # A partir de acá los campos están indexados desde 0 pero corresponden
    # al campo 3 en adelante del archivo (state, ppid, ...).
    return ProcessStat(
        pid=int(pid_str),
        comm=comm,
        state=resto[0],
        ppid=int(resto[1]),
        utime=int(resto[11]),        # campo 14 del archivo → índice 11 del resto
        stime=int(resto[12]),        # campo 15
        priority=int(resto[15]),     # campo 18
        nice=int(resto[16]),         # campo 19
        num_threads=int(resto[17]),  # campo 20
        policy=int(resto[38]),       # campo 41
    )


def listar_threads(pid: int) -> list[int] | None:
    """
    Lista los TIDs (thread IDs) del proceso.
    Cada thread aparece como una carpeta en /proc/<pid>/task/.
    """
    try:
        entries = os.listdir(PROC / str(pid) / "task")
    except (FileNotFoundError, PermissionError):
        return None
    return [int(t) for t in entries if t.isdigit()]


def listar_fds(pid: int) -> list[int] | None:
    """
    Lista los file descriptors abiertos por el proceso.
    Cada FD es un symlink en /proc/<pid>/fd/.
    Requiere permisos suficientes (CAP_SYS_PTRACE para procesos ajenos).
    """
    try:
        entries = os.listdir(PROC / str(pid) / "fd")
    except (FileNotFoundError, PermissionError):
        return None
    return [int(fd) for fd in entries if fd.isdigit()]

@dataclass
class MemoryRegion:
    """
    Una región de memoria virtual del proceso.
    Corresponde a una línea de /proc/<pid>/maps.
    """
    addr_start: int          # dirección inicial (en bytes, ya convertida de hex)
    addr_end: int            # dirección final
    permisos: str            # "rwxp" o similar (r/w/x/p o s)
    offset: int              # offset dentro del archivo (si aplica)
    pathname: str            # ruta del archivo, [heap], [stack], [vdso], o "" (anónima)

    @property
    def size(self) -> int:
        """Tamaño de la región en bytes."""
        return self.addr_end - self.addr_start


@dataclass
class ProcessSignals:
    """
    Información de señales de un proceso, extraída de /proc/<pid>/status.
    Cada campo es una máscara donde cada bit representa una señal.
    Los guardamos como int (ya convertidos de hex) para facilitar el trabajo con bits.
    """
    sig_pnd: int    # señales pendientes para el thread
    shd_pnd: int    # señales pendientes para el proceso (shared)
    sig_blk: int    # señales bloqueadas
    sig_ign: int    # señales ignoradas
    sig_cgt: int    # señales con handler (caught)


@dataclass
class SistemaStat:
    """
    Info agregada del sistema, de /proc/stat.
    """
    cpu_user: int           # tiempo total (jiffies) en modo usuario
    cpu_nice: int           # tiempo total en modo usuario con nice
    cpu_system: int         # tiempo total en modo kernel
    cpu_idle: int           # tiempo total idle
    cpu_iowait: int         # tiempo esperando I/O
    procesos_creados: int   # total de procesos creados desde el arranque
    context_switches: int   # total de context switches desde el arranque
    procs_running: int      # procesos en estado R ahora mismo
    procs_blocked: int      # procesos bloqueados en I/O ahora mismo


def leer_maps(pid: int) -> list[MemoryRegion] | None:
    """
    Lee /proc/<pid>/maps y devuelve la lista de regiones de memoria virtual.

    Cada línea del archivo tiene el formato:
      addr_start-addr_end perms offset dev inode pathname

    Ejemplo:
      55d8f4a00000-55d8f4a02000 r--p 00000000 08:01 12345 /usr/bin/firefox
      7f8a12345000-7f8a12346000 rw-p 00000000 00:00 0     [heap]
    """
    try:
        with open(PROC / str(pid) / "maps") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    regiones = []
    for line in contenido.splitlines():
        # split con maxsplit=5 para que el pathname (que puede tener espacios) quede entero
        partes = line.split(maxsplit=5)
        if len(partes) < 5:
            continue

        # partes[0] es "addr_start-addr_end", lo separamos
        rango = partes[0].split("-")
        if len(rango) != 2:
            continue

        addr_start = int(rango[0], 16)   # base 16 → hexadecimal
        addr_end = int(rango[1], 16)
        permisos = partes[1]
        offset = int(partes[2], 16)
        # partes[3] es dev, partes[4] es inode — los ignoramos
        pathname = partes[5] if len(partes) == 6 else ""

        regiones.append(MemoryRegion(
            addr_start=addr_start,
            addr_end=addr_end,
            permisos=permisos,
            offset=offset,
            pathname=pathname,
        ))

    return regiones


def leer_signals(pid: int) -> ProcessSignals | None:
    """
    Lee las máscaras de señales de /proc/<pid>/status.
    Las máscaras vienen como hexadecimales (ej: "0000000180010000").
    Cada bit representa una señal: bit N = señal N+1.
    """
    ruta = PROC / str(pid) / "status"
    try:
        with open(ruta) as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    campos = {
        "SigPnd": 0,
        "ShdPnd": 0,
        "SigBlk": 0,
        "SigIgn": 0,
        "SigCgt": 0,
    }

    for line in contenido.splitlines():
        partes = line.split(":", 1)
        if len(partes) != 2:
            continue
        clave = partes[0]
        if clave in campos:
            # El valor viene en hex sin prefijo "0x", lo pasamos a int base 16.
            campos[clave] = int(partes[1].strip(), 16)

    return ProcessSignals(
        sig_pnd=campos["SigPnd"],
        shd_pnd=campos["ShdPnd"],
        sig_blk=campos["SigBlk"],
        sig_ign=campos["SigIgn"],
        sig_cgt=campos["SigCgt"],
    )

def decodificar_senales(mascara: int) -> list[str]:
    """
    Convierte una máscara de señales (int) a la lista de nombres legibles.

    Cada bit de la máscara representa una señal: el bit 0 es la señal 1
    (SIGHUP), el bit 1 la señal 2 (SIGINT), etc. Por eso el número de
    señal es siempre el número de bit + 1.

    Las señales real-time (34 en adelante) no tienen nombre en el módulo
    signal, así que las mostramos como "SIG<N>".
    """
    nombres = []
    for bit in range(64):                    # las máscaras son de 64 bits
        if mascara & (1 << bit):             # ¿está encendido el bit?
            numero = bit + 1                  # bit 0 -> señal 1
            try:
                nombres.append(signal.Signals(numero).name)
            except ValueError:
                nombres.append(f"SIG{numero}")   # señal sin nombre conocido
    return nombres

def leer_stat_sistema() -> SistemaStat | None:
    """
    Lee /proc/stat — info agregada del sistema.

    Formato (líneas relevantes):
      cpu  user nice system idle iowait irq softirq steal guest guest_nice
      ...
      ctxt <n>              → total de context switches
      processes <n>         → total de procesos creados
      procs_running <n>     → procesos en R ahora
      procs_blocked <n>     → procesos bloqueados en I/O ahora
    """
    try:
        with open(PROC / "stat") as f:
            contenido = f.read()
    except (FileNotFoundError, PermissionError):
        return None

    cpu_user = cpu_nice = cpu_system = cpu_idle = cpu_iowait = 0
    procesos_creados = context_switches = procs_running = procs_blocked = 0

    for line in contenido.splitlines():
        partes = line.split()
        if not partes:
            continue

        if partes[0] == "cpu":
            # Primera línea "cpu" (sin número) = agregado de todos los cores
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

    return SistemaStat(
        cpu_user=cpu_user,
        cpu_nice=cpu_nice,
        cpu_system=cpu_system,
        cpu_idle=cpu_idle,
        cpu_iowait=cpu_iowait,
        procesos_creados=procesos_creados,
        context_switches=context_switches,
        procs_running=procs_running,
        procs_blocked=procs_blocked,
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
    print("\n--- leer_comm(3246) ---")
    print(leer_comm(3246))

    print("\n--- leer_stat(3246) ---")
    print(leer_stat(3246))

    print("\n--- listar_threads(3246) — primeros 10 ---")
    threads = listar_threads(3246)
    print(f"Total threads: {len(threads) if threads else 0}")
    print(f"Primeros 10: {sorted(threads)[:10] if threads else None}")

    print("\n--- listar_fds(3246) — primeros 10 ---")
    fds = listar_fds(3246)
    print(f"Total FDs: {len(fds) if fds else 0}")
    print(f"Primeros 10: {sorted(fds)[:10] if fds else None}")
    print("\n--- leer_maps(3246) — primeras 3 regiones ---")
    regiones = leer_maps(3246)
    if regiones:
        print(f"Total regiones: {len(regiones)}")
        for r in regiones[:3]:
            print(f"  {hex(r.addr_start)}-{hex(r.addr_end)} {r.permisos} {r.pathname or '(anónima)'} — {r.size} bytes")

    print("\n--- leer_signals(3246) ---")
    print(leer_signals(3246))

    print("\n--- leer_stat_sistema() ---")
    print(leer_stat_sistema())