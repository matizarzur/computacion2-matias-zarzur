"""
senales.py — Handlers de señales del monitor.

Los handlers son mínimos: solo levantan flags que el main revisa
en su loop. Esto garantiza async-signal-safety: no tocamos datos
compartidos ni tomamos locks dentro del handler.

Señales manejadas:
  SIGINT  (Ctrl+C)     -> shutdown limpio
  SIGTERM              -> igual que SIGINT
  SIGHUP               -> recargar config.json
  SIGUSR1              -> dump del snapshot a JSON
  SIGUSR2              -> toggle modo verbose
"""

import signal
from multiprocessing import Event


class Flags:
    """
    Banderas compartidas entre los handlers y el main.

    Todas son Event() de multiprocessing: thread-safe, simples,
    y visibles desde cualquier proceso (aunque los handlers
    corren solo en el main).
    """
    terminar = Event()      # SIGINT o SIGTERM
    recargar = Event()      # SIGHUP
    dump = Event()          # SIGUSR1
    toggle_verbose = Event()  # SIGUSR2


def _handler_terminar(signum, frame):
    """SIGINT / SIGTERM -> pedir shutdown."""
    Flags.terminar.set()


def _handler_recargar(signum, frame):
    """SIGHUP -> pedir reload de config."""
    Flags.recargar.set()


def _handler_dump(signum, frame):
    """SIGUSR1 -> pedir dump del snapshot."""
    Flags.dump.set()


def _handler_toggle_verbose(signum, frame):
    """SIGUSR2 -> pedir toggle de verbose."""
    Flags.toggle_verbose.set()


def registrar_handlers() -> None:
    """
    Registra los handlers de señales en el proceso actual.
    Debe llamarse una vez, desde el main, ANTES de crear los procesos hijos.
    """
    signal.signal(signal.SIGINT, _handler_terminar)
    signal.signal(signal.SIGTERM, _handler_terminar)
    signal.signal(signal.SIGHUP, _handler_recargar)
    signal.signal(signal.SIGUSR1, _handler_dump)
    signal.signal(signal.SIGUSR2, _handler_toggle_verbose)

def resetear_handlers_en_hijo() -> None:
    """
    Restaura los handlers de señales a los defaults del kernel.

    Debe llamarse al inicio de cada proceso hijo. Sin esto, los hijos
    heredan los handlers del padre y ignoran SIGTERM/SIGINT, lo que
    impide el shutdown ordenado del monitor.
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGHUP, signal.SIG_DFL)
    signal.signal(signal.SIGUSR1, signal.SIG_DFL)
    signal.signal(signal.SIGUSR2, signal.SIG_DFL)