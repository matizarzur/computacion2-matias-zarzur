#!/usr/bin/env python3
"""Timeout usando SIGALRM."""
import signal

class Timeout(Exception):
    pass

def timeout_handler(sig, frame):
    raise Timeout("Operación excedió el tiempo límite")

def con_timeout(segundos):
    """Decorador para agregar timeout a una función."""
    def decorador(func):
        def wrapper(*args, **kwargs):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(segundos)
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        return wrapper
    return decorador

# Uso
@con_timeout(3)
def operacion_lenta():
    import time
    print("Iniciando operación...")
    time.sleep(5)
    return "Completado"

@con_timeout(3)
def operacion_rapida():
    import time
    print("Iniciando operación...")
    time.sleep(1)
    return "Completado"

print("=== Operación rápida ===")
try:
    resultado = operacion_rapida()
    print(f"Resultado: {resultado}")
except Timeout as e:
    print(f"Timeout: {e}")

print("\n=== Operación lenta ===")
try:
    resultado = operacion_lenta()
    print(f"Resultado: {resultado}")
except Timeout as e:
    print(f"Timeout: {e}")
