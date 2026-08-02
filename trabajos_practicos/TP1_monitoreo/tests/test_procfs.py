"""
test_procfs.py — Tests unitarios de las funciones de parseo puras de procfs.

Se testean las funciones que transforman datos sin leer /proc directamente
(no dependen del sistema), así los tests son deterministas y reproducibles:

  - decodificar_senales : máscara de bits -> lista de nombres de señales
  - _inferir_tipo_fd    : destino de un symlink -> categoría del FD

Correr con:  python3 -m pytest tests/test_procfs.py -v
       o con: python3 tests/test_procfs.py   (usa asserts sueltos)
"""

import sys
import signal
from pathlib import Path

# Permitir importar procfs desde src/ cuando se corre desde la raíz del TP.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from procfs import decodificar_senales, _inferir_tipo_fd


# ============================================================
# decodificar_senales
# ============================================================

def test_decodificar_mascara_vacia():
    """Una máscara en 0 no tiene ninguna señal."""
    assert decodificar_senales(0) == []


def test_decodificar_una_senal():
    """SIGINT es la señal 2, o sea el bit 1 (valor 2)."""
    assert decodificar_senales(2) == ["SIGINT"]


def test_decodificar_sighup():
    """SIGHUP es la señal 1, o sea el bit 0 (valor 1)."""
    assert decodificar_senales(1) == ["SIGHUP"]


def test_decodificar_varias_senales():
    """SIGINT (2) + SIGTERM (15) = bits 1 y 14, en orden de número de señal."""
    mascara = (1 << 1) | (1 << 14)
    assert decodificar_senales(mascara) == ["SIGINT", "SIGTERM"]


def test_decodificar_sigkill():
    """SIGKILL es la señal 9, o sea el bit 8."""
    assert decodificar_senales(1 << 8) == ["SIGKILL"]


def test_decodificar_coincide_con_modulo_signal():
    """El nombre decodificado debe coincidir con el del módulo signal."""
    esperado = signal.Signals(17).name   # señal 17 = SIGCHLD en Linux
    assert decodificar_senales(1 << 16) == [esperado]


# ============================================================
# _inferir_tipo_fd
# ============================================================

def test_tipo_fd_socket():
    assert _inferir_tipo_fd("socket:[12345]") == "socket"


def test_tipo_fd_pipe():
    assert _inferir_tipo_fd("pipe:[67890]") == "pipe"


def test_tipo_fd_anon():
    assert _inferir_tipo_fd("anon_inode:[eventfd]") == "anon"


def test_tipo_fd_tty():
    assert _inferir_tipo_fd("/dev/pts/1") == "tty"


def test_tipo_fd_device():
    assert _inferir_tipo_fd("/dev/null") == "device"


def test_tipo_fd_file():
    assert _inferir_tipo_fd("/home/mati/archivo.txt") == "file"


def test_tipo_fd_desconocido():
    """Un destino que no empieza con / ni con un prefijo conocido."""
    assert _inferir_tipo_fd("algo-raro") == "desconocido"


# ============================================================
# Runner sin pytest (por si no está instalado)
# ============================================================

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fallos = 0
    for t in tests:
        try:
            t()
            print(f"  OK    {t.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"  FALLA {t.__name__}: {e}")
    print(f"\n{len(tests) - fallos}/{len(tests)} tests pasaron")
    sys.exit(1 if fallos else 0)
