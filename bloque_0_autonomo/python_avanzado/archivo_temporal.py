#!/usr/bin/env python3
"""
Context manager para crear archivos temporales que se borran automáticamente.
"""
from contextlib import contextmanager
import os


@contextmanager
def archivo_temporal(nombre: str):
    """Crea un archivo temporal y lo borra al salir del contexto."""
    f = open(nombre, "w+")
    try:
        yield f
    finally:
        f.close()
        if os.path.exists(nombre):
            os.remove(nombre)


if __name__ == "__main__":
    with archivo_temporal("test.txt") as f:
        f.write("Datos de prueba\n")
        f.write("Más datos\n")
        f.seek(0)
        print(f.read())

    assert not os.path.exists("test.txt")
    print("El archivo fue borrado correctamente")