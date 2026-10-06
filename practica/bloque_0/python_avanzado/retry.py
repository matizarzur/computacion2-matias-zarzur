#!/usr/bin/env python3
"""Decorador que reintenta una función si falla."""
import time
import random
from functools import wraps


def retry(max_attempts=3, delay=1, exceptions=Exception):
    """Reintenta la función hasta max_attempts veces si lanza una excepción."""
    def decorador(funcion):
        @wraps(funcion)
        def wrapper(*args, **kwargs):
            for intento in range(1, max_attempts + 1):
                try:
                    return funcion(*args, **kwargs)
                except exceptions as e:
                    if intento == max_attempts:
                        print(f"Intento {intento}/{max_attempts} falló: {e}.")
                        raise
                    print(f"Intento {intento}/{max_attempts} falló: {e}. Esperando {delay}s...")
                    time.sleep(delay)
        return wrapper
    return decorador


if __name__ == "__main__":
    @retry(max_attempts=3, delay=1)
    def conectar_servidor():
        if random.random() < 0.7:
            raise ConnectionError("Servidor no disponible")
        return "Conectado exitosamente"

    try:
        resultado = conectar_servidor()
        print(resultado)
    except ConnectionError:
        print("Falló después de 3 intentos")