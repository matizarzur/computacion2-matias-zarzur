"""
display.py — Proceso de display (TUI) del monitor.

Renderiza el snapshot compartido usando rich, con 7 vistas alternables.
Corre en el proceso PRINCIPAL (necesita la terminal real para leer el
teclado con termios). Un thread separado escucha el teclado, única
excepción permitida al modelo multiproceso.

Vistas:
  1/r resumen | 2/m memoria | 3/f fds | 4/t threads
  5/s senales | 6/p scheduling | 7/g sistema
Teclas:
  1-7 o r/m/f/t/s/p/g : cambiar vista
  arriba / abajo      : navegar por la lista (vista Resumen)
  Enter               : pin/unpin del proceso seleccionado
  c                   : cambiar orden (PID / RSS / Threads)
  /                   : filtrar por nombre de comando
  u                   : filtrar por usuario (UID)
  + / -               : ajustar el intervalo de refresco de la vista activa
  h / ?               : mostrar/ocultar ayuda
  q                   : salir
"""

import sys
import time
import select
import termios
import tty
import threading

from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text


TECLAS_VISTAS = {
    "1": "resumen", "r": "resumen",
    "2": "memoria", "m": "memoria",
    "3": "fds", "f": "fds",
    "4": "threads", "t": "threads",
    "5": "senales", "s": "senales",
    "6": "scheduling", "p": "scheduling",
    "7": "sistema", "g": "sistema",
}

# Límites para el ajuste de intervalo (segundos).
INTERVALO_MIN = 0.5
INTERVALO_MAX = 30.0
INTERVALO_PASO = 0.5

# Criterios de ordenamiento que cicla la tecla 'c'.
ORDENES = ["pid", "rss", "threads"]

# Cuántas filas mostrar por vista.
MAX_FILAS = 25


class EstadoDisplay:
    """Estado mutable compartido entre el thread de teclado y el loop de render."""
    def __init__(self, intervalos):
        self.vista_activa = "resumen"
        self.salir = False
        self.intervalos = intervalos      # dict: "recolector"/"sistema" -> Value

        # Ordenamiento (tecla c)
        self.orden = "pid"                 # pid / rss / threads

        # Navegación y pin (flechas + Enter)
        self.seleccion = 0                 # índice de fila seleccionada
        self.pin_pid = None                # PID pineado (o None)

        # Filtros (/ y u)
        self.filtro_nombre = ""            # subcadena a buscar en el comando
        self.filtro_uid = None             # UID a filtrar (o None)

        # Modo de entrada de texto (cuando se está tipeando un filtro)
        self.modo_input = None             # None / "nombre" / "uid"
        self.buffer_input = ""

        # Ayuda
        self.mostrar_ayuda = False


def _ajustar_intervalo(estado: EstadoDisplay, delta: float) -> None:
    """Ajusta el intervalo de la vista activa (con límites)."""
    if estado.vista_activa == "sistema":
        val = estado.intervalos["sistema"]
    else:
        val = estado.intervalos["recolector"]
    nuevo = val.value + delta
    nuevo = max(INTERVALO_MIN, min(INTERVALO_MAX, nuevo))
    val.value = nuevo


def _ciclar_orden(estado: EstadoDisplay) -> None:
    """Pasa al siguiente criterio de ordenamiento."""
    idx = ORDENES.index(estado.orden)
    estado.orden = ORDENES[(idx + 1) % len(ORDENES)]


def _procesar_tecla_normal(estado: EstadoDisplay, ch: str) -> None:
    """Maneja una tecla cuando NO se está escribiendo un filtro."""
    if ch == "q":
        estado.salir = True
    elif ch in TECLAS_VISTAS:
        estado.vista_activa = TECLAS_VISTAS[ch]
        estado.seleccion = 0
    elif ch == "+":
        _ajustar_intervalo(estado, +INTERVALO_PASO)
    elif ch == "-":
        _ajustar_intervalo(estado, -INTERVALO_PASO)
    elif ch == "c":
        _ciclar_orden(estado)
    elif ch in ("h", "?"):
        estado.mostrar_ayuda = not estado.mostrar_ayuda
    elif ch == "/":
        estado.modo_input = "nombre"
        estado.buffer_input = ""
    elif ch == "u":
        estado.modo_input = "uid"
        estado.buffer_input = ""
    elif ch == "\n" or ch == "\r":
        # Enter: pin/unpin de la fila seleccionada se resuelve en el render
        # (necesita la lista actual). Acá marcamos la intención con un flag.
        estado._toggle_pin = True
    elif ch == "\x1b":
        # Secuencia de escape (flechas): vienen como \x1b[A (arriba) o \x1b[B (abajo)
        seq = sys.stdin.read(2)
        if seq == "[A":       # flecha arriba
            estado.seleccion = max(0, estado.seleccion - 1)
        elif seq == "[B":     # flecha abajo
            estado.seleccion += 1


def _procesar_tecla_input(estado: EstadoDisplay, ch: str) -> None:
    """Maneja una tecla mientras se escribe un filtro (/ o u)."""
    if ch == "\n" or ch == "\r":
        # Confirmar el filtro
        if estado.modo_input == "nombre":
            estado.filtro_nombre = estado.buffer_input.strip()
        elif estado.modo_input == "uid":
            texto = estado.buffer_input.strip()
            estado.filtro_uid = int(texto) if texto.isdigit() else None
        estado.modo_input = None
        estado.buffer_input = ""
    elif ch == "\x1b":
        # Escape: cancelar el filtro
        estado.modo_input = None
        estado.buffer_input = ""
    elif ch in ("\x7f", "\b"):
        # Backspace
        estado.buffer_input = estado.buffer_input[:-1]
    elif ch.isprintable():
        estado.buffer_input += ch


def leer_teclado(estado: EstadoDisplay) -> None:
    """
    Thread que lee el teclado sin bloquear, usando select().
    Corre en paralelo al loop de render.
    """
    fd = sys.stdin.fileno()
    viejo = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while not estado.salir:
            listo, _, _ = select.select([sys.stdin], [], [], 0.2)
            if not listo:
                continue
            ch = sys.stdin.read(1)
            if estado.modo_input:
                _procesar_tecla_input(estado, ch)
            else:
                _procesar_tecla_normal(estado, ch)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, viejo)


# ============================================================
# Filtrado y ordenamiento de la lista de Resumen
# ============================================================

def _filtrar_y_ordenar(procesos: dict, estado: EstadoDisplay) -> list:
    """
    Aplica los filtros activos y el criterio de orden a los procesos
    de la vista Resumen. Devuelve una lista ordenada de ProcessStatus.
    """
    items = list(procesos.values())

    # Filtro por nombre de comando
    if estado.filtro_nombre:
        f = estado.filtro_nombre.lower()
        items = [p for p in items if f in p.name.lower()]

    # Filtro por UID
    if estado.filtro_uid is not None:
        items = [p for p in items if p.uid == estado.filtro_uid]

    # Ordenamiento
    if estado.orden == "rss":
        items.sort(key=lambda p: p.vm_rss or 0, reverse=True)
    elif estado.orden == "threads":
        items.sort(key=lambda p: p.threads, reverse=True)
    else:  # pid
        items.sort(key=lambda p: p.pid)

    return items


def _tabla_resumen(procesos: dict, estado: EstadoDisplay) -> Table:
    tabla = Table(title="Resumen de procesos", expand=True)
    tabla.add_column("", width=2)   # marcador de selección/pin
    tabla.add_column("PID", justify="right", style="cyan")
    tabla.add_column("Nombre", style="white")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("RSS (MB)", justify="right", style="green")
    tabla.add_column("Threads", justify="right")
    tabla.add_column("UID", justify="right")

    items = _filtrar_y_ordenar(procesos, estado)

    # Resolver pin/unpin si se apretó Enter en la última tecla
    if getattr(estado, "_toggle_pin", False):
        estado._toggle_pin = False
        if 0 <= estado.seleccion < len(items):
            pid_sel = items[estado.seleccion].pid
            estado.pin_pid = None if estado.pin_pid == pid_sel else pid_sel

    # Acotar la selección al tamaño de la lista
    if estado.seleccion >= len(items):
        estado.seleccion = max(0, len(items) - 1)

    for i, st in enumerate(items[:MAX_FILAS]):
        rss_mb = (st.vm_rss // 1024) if st.vm_rss else 0

        # Marcador: '>' si es la fila seleccionada, '*' si está pineada
        marca = ""
        if i == estado.seleccion:
            marca = ">"
        if st.pid == estado.pin_pid:
            marca = "*" + marca

        # Resaltar la fila seleccionada
        estilo = "reverse" if i == estado.seleccion else ""

        tabla.add_row(
            marca, str(st.pid), st.name, st.state,
            str(rss_mb), str(st.threads), str(st.uid),
            style=estilo,
        )
    return tabla


def _tabla_generica(procesos: dict, titulo: str) -> Table:
    tabla = Table(title=titulo, expand=True)
    tabla.add_column("PID", justify="right", style="cyan")
    tabla.add_column("Datos", style="white", overflow="fold")
    for pid in sorted(procesos.keys())[:MAX_FILAS]:
        tabla.add_row(str(pid), str(procesos[pid])[:120])
    return tabla


def _formatear_sistema(datos: dict) -> Panel:
    if not datos:
        return Panel("Sin datos del sistema todavia", title="Sistema")

    meminfo = datos.get("meminfo")
    loadavg = datos.get("loadavg")
    uptime = datos.get("uptime")

    lineas = []
    if loadavg:
        lineas.append(
            f"Load: {loadavg.load_1min} {loadavg.load_5min} {loadavg.load_15min}"
            f"  |  Procesos: {loadavg.procesos_total}"
            f"  |  Corriendo: {loadavg.procesos_corriendo}"
        )
    if meminfo:
        usada = meminfo.total - meminfo.available
        pct = (usada / meminfo.total * 100) if meminfo.total else 0
        lineas.append(
            f"RAM: {usada // 1024} MB / {meminfo.total // 1024} MB ({pct:.0f}%)"
            f"  |  Swap libre: {meminfo.swap_free // 1024} MB"
        )
    if uptime:
        horas = int(uptime.uptime_segundos // 3600)
        minutos = int((uptime.uptime_segundos % 3600) // 60)
        lineas.append(f"Uptime: {horas}h {minutos}m")

    return Panel("\n".join(lineas), title="Sistema", border_style="cyan")


def _panel_ayuda() -> Panel:
    texto = Text()
    texto.append("Teclas del monitor\n\n", style="bold cyan")
    filas = [
        ("1-7 / r m f t s p g", "cambiar de vista"),
        ("flechas arriba/abajo", "navegar por la lista (Resumen)"),
        ("Enter", "pin / unpin del proceso seleccionado"),
        ("c", "cambiar orden (PID / RSS / Threads)"),
        ("/", "filtrar por nombre de comando"),
        ("u", "filtrar por UID"),
        ("+  /  -", "ajustar intervalo de la vista"),
        ("h  /  ?", "mostrar / ocultar esta ayuda"),
        ("q", "salir"),
    ]
    for tecla, desc in filas:
        texto.append(f"  {tecla:22}", style="bold yellow")
        texto.append(f"{desc}\n", style="white")
    texto.append("\nApreta h o ? para volver.", style="dim")
    return Panel(texto, title="Ayuda", border_style="green")


def _render(snapshot: dict, estado: EstadoDisplay) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=6),
    )

    sistema = snapshot.get("sistema", {})
    layout["header"].update(_formatear_sistema(sistema))

    vista = estado.vista_activa
    procesos = snapshot.get(vista, {})

    # Si la ayuda está activa, ocupa el cuerpo
    if estado.mostrar_ayuda:
        layout["body"].update(_panel_ayuda())
    elif vista == "resumen":
        layout["body"].update(_tabla_resumen(procesos, estado))
    elif vista == "sistema":
        layout["body"].update(Panel(str(sistema), title="Sistema (detalle)"))
    else:
        layout["body"].update(_tabla_generica(procesos, f"Vista: {vista}"))

    # Intervalo actual de la vista
    if vista == "sistema":
        intervalo_actual = estado.intervalos["sistema"].value
    else:
        intervalo_actual = estado.intervalos["recolector"].value

    # Footer: ayuda de teclas + estado (orden, filtros, intervalo)
    ayuda = Text(
        "1/r resumen  2/m memoria  3/f fds  4/t threads  "
        "5/s senales  6/p scheduling  7/g sistema\n"
        "flechas navegar  Enter pin  c orden  / nombre  u uid  +/- intervalo  "
        "h ayuda  q salir",
        style="dim",
    )

    # Línea de estado / input
    if estado.modo_input == "nombre":
        estado_txt = f"\nFiltro nombre: {estado.buffer_input}_  (Enter confirma, Esc cancela)"
    elif estado.modo_input == "uid":
        estado_txt = f"\nFiltro UID: {estado.buffer_input}_  (Enter confirma, Esc cancela)"
    else:
        filtros = []
        if estado.filtro_nombre:
            filtros.append(f"nombre~'{estado.filtro_nombre}'")
        if estado.filtro_uid is not None:
            filtros.append(f"uid={estado.filtro_uid}")
        filtro_str = " ".join(filtros) if filtros else "ninguno"
        pin_str = str(estado.pin_pid) if estado.pin_pid else "-"
        estado_txt = (
            f"\nVista: {vista}  |  orden: {estado.orden}  |  "
            f"filtros: {filtro_str}  |  pin: {pin_str}  |  "
            f"intervalo: {intervalo_actual:.1f}s"
        )

    ayuda.append(estado_txt, style="bold yellow")
    layout["footer"].update(Panel(ayuda, border_style="dim"))

    return layout


def display(snapshot, flags, cargar_config, dump_snapshot, verbose,
            intervalos, intervalo=1.0):
    """
    Loop del display. Corre en el proceso PRINCIPAL (necesita la terminal
    real para leer el teclado con termios).
    """
    estado = EstadoDisplay(intervalos)

    hilo_teclado = threading.Thread(target=leer_teclado, args=(estado,), daemon=True)
    hilo_teclado.start()

    with Live(_render(snapshot, estado), refresh_per_second=4, screen=True) as live:
        while not estado.salir and not flags.terminar.is_set():
            time.sleep(intervalo)

            if flags.recargar.is_set():
                flags.recargar.clear()
                cargar_config()

            if flags.dump.is_set():
                flags.dump.clear()
                dump_snapshot(snapshot)

            if flags.toggle_verbose.is_set():
                flags.toggle_verbose.clear()
                verbose.value = 1 - verbose.value

            live.update(_render(snapshot, estado))

    flags.terminar.set()