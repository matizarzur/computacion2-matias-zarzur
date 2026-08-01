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
  q : salir
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


class EstadoDisplay:
    """Estado mutable compartido entre el thread de teclado y el loop de render."""
    def __init__(self):
        self.vista_activa = "resumen"
        self.salir = False


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
            # Esperar hasta 0.2s a que haya una tecla lista
            listo, _, _ = select.select([sys.stdin], [], [], 0.2)
            if not listo:
                continue
            ch = sys.stdin.read(1)
            if ch == "q":
                estado.salir = True
            elif ch in TECLAS_VISTAS:
                estado.vista_activa = TECLAS_VISTAS[ch]
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, viejo)


def _formatear_sistema(datos: dict) -> Panel:
    """Arma el panel superior con info global del sistema."""
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


def _tabla_resumen(procesos: dict) -> Table:
    tabla = Table(title="Resumen de procesos", expand=True)
    tabla.add_column("PID", justify="right", style="cyan")
    tabla.add_column("Nombre", style="white")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("RSS (MB)", justify="right", style="green")
    tabla.add_column("Threads", justify="right")
    tabla.add_column("UID", justify="right")

    for pid in sorted(procesos.keys())[:25]:
        st = procesos[pid]
        rss_mb = (st.vm_rss // 1024) if st.vm_rss else 0
        tabla.add_row(
            str(pid), st.name, st.state,
            str(rss_mb), str(st.threads), str(st.uid),
        )
    return tabla


def _tabla_generica(procesos: dict, titulo: str) -> Table:
    """Vista simple para tipos que aun no tienen tabla dedicada."""
    tabla = Table(title=titulo, expand=True)
    tabla.add_column("PID", justify="right", style="cyan")
    tabla.add_column("Datos", style="white", overflow="fold")

    for pid in sorted(procesos.keys())[:25]:
        tabla.add_row(str(pid), str(procesos[pid])[:120])
    return tabla


def _render(snapshot: dict, estado: EstadoDisplay) -> Layout:
    """Arma el layout completo: sistema arriba, tabla de la vista abajo, ayuda al pie."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )

    sistema = snapshot.get("sistema", {})
    layout["header"].update(_formatear_sistema(sistema))

    vista = estado.vista_activa
    procesos = snapshot.get(vista, {})

    if vista == "resumen":
        layout["body"].update(_tabla_resumen(procesos))
    elif vista == "sistema":
        layout["body"].update(Panel(str(sistema), title="Sistema (detalle)"))
    else:
        layout["body"].update(_tabla_generica(procesos, f"Vista: {vista}"))

    ayuda = Text(
        "1/r resumen  2/m memoria  3/f fds  4/t threads  "
        "5/s senales  6/p scheduling  7/g sistema  |  q salir",
        style="dim",
    )
    ayuda.append(f"\nVista activa: {vista}", style="bold yellow")
    layout["footer"].update(Panel(ayuda, border_style="dim"))

    return layout


def display(snapshot, flags, cargar_config, dump_snapshot, verbose, intervalo=1.0):
    """
    Loop del display. Corre en el proceso PRINCIPAL (necesita la terminal
    real para leer el teclado con termios).

    Ademas de renderizar, atiende las flags de senales:
      recargar (SIGHUP), dump (SIGUSR1), toggle_verbose (SIGUSR2),
      terminar (SIGINT/SIGTERM).
    """
    estado = EstadoDisplay()

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

    # Si salimos por 'q', avisar al main que hay que terminar
    flags.terminar.set()