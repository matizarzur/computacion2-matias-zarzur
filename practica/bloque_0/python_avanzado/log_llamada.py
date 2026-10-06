#!/usr/bin/env python3
"""Decorador que loguea cada llamada a una función."""
from functools import wraps
from datetime import datetime


def log_llamada(funcion):
    """Loguea argumentos, retorno y timestamp de cada llamada."""
    @wraps(funcion)
    def wrapper(*args, **kwargs):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        args_str = ", ".join(repr(a) for a in args)
        kwargs_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())
        todos = ", ".join(filter(None, [args_str, kwargs_str]))
        print(f"[{timestamp}] Llamando a {funcion.__name__}({todos})")
        resultado = funcion(*args, **kwargs)
        print(f"[{timestamp}] {funcion.__name__} retornó {repr(resultado)}")
        return resultado
    return wrapper


if __name__ == "__main__":
    @log_llamada
    def sumar(a, b):
        return a + b

    @log_llamada
    def saludar(nombre, entusiasta=False):
        sufijo = "!" if entusiasta else "."
        return f"Hola, {nombre}{sufijo}"

    sumar(3, 5)
    saludar("Ana", entusiasta=True)