#!/usr/bin/env python3
"""Context manager para medir el tiempo de ejecución de un bloque."""
import time
from contextlib import contextmanager


class Timer:
    """Mide el tiempo de ejecución de un bloque with."""
    def __init__(self, nombre=None):
        self.nombre = nombre
        self.inicio = None
        self._fin = None

    @property
    def elapsed(self):
        if self._fin:
            return self._fin - self.inicio
        return time.time() - self.inicio

    def __enter__(self):
        self.inicio = time.time()
        return self

    def __exit__(self, *args):
        self._fin = time.time()
        if self.nombre:
            print(f"[Timer] {self.nombre}: {self.elapsed:.3f}s")
        return False


@contextmanager
def timer(nombre=None):
    """Version con @contextmanager del Timer."""
    inicio = time.time()
    try:
        yield
    finally:
        duracion = time.time() - inicio
        if nombre:
            print(f"[Timer] {nombre}: {duracion:.3f}s")


if __name__ == "__main__":
    with Timer("Procesamiento") as t:
        datos = [x**2 for x in range(1000000)]
    print(f"Tardó {t.elapsed:.3f}s")

    with timer("Con contextmanager"):
        datos = [x**2 for x in range(1000000)]