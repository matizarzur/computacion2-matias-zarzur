#!/usr/bin/env python3
"""Generador de la secuencia de Fibonacci."""


def fibonacci(limite=None):
    """Genera la secuencia de Fibonacci, opcionalmente hasta un límite."""
    a, b = 0, 1
    while True:
        if limite is not None and a > limite:
            return
        yield a
        a, b = b, a + b


if __name__ == "__main__":
    fib = fibonacci()
    print("Primeros 10:", [next(fib) for _ in range(10)])

    print("Hasta 100:", list(fibonacci(limite=100)))