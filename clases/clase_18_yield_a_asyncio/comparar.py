#!/usr/bin/env python3
"""Cuándo asyncio ayuda y cuándo no sirve para nada.

Mide lo mismo de tres formas: secuencial, con asyncio, y con el error
clásico de usar time.sleep() adentro de una corrutina. Después repite
con trabajo de CPU, donde asyncio no puede hacer nada.

Uso:
    python3 comparar.py
"""
import asyncio
import hashlib
import time

TAREAS = 3
ESPERA = 1.0
VUELTAS_CPU = 2_000_000


# ---------------------------------------------------------------
# I/O-bound: esperar
# ---------------------------------------------------------------

def esperar_sync(n):
    time.sleep(ESPERA)
    return n


async def esperar_async(n):
    await asyncio.sleep(ESPERA)          # cede el control
    return n


async def esperar_mal(n):
    time.sleep(ESPERA)                   # BUG: bloquea el event loop
    return n


# ---------------------------------------------------------------
# CPU-bound: calcular
# ---------------------------------------------------------------

def hashear(n):
    h = b'x'
    for _ in range(VUELTAS_CPU):
        h = hashlib.sha256(h).digest()
    return n


async def hashear_async(n):
    return hashear(n)                    # no hay await: nunca cede


def medir(etiqueta, fn):
    t0 = time.perf_counter()
    fn()
    print(f'  {etiqueta:<42} {time.perf_counter() - t0:5.2f}s')


def main():
    print(f'=== I/O-bound: {TAREAS} tareas que esperan {ESPERA}s cada una ===\n')

    medir('secuencial (una tras otra)',
          lambda: [esperar_sync(i) for i in range(TAREAS)])

    medir('asyncio.gather con asyncio.sleep',
          lambda: asyncio.run(_juntas(esperar_async)))

    medir('asyncio.gather con time.sleep  <- el bug',
          lambda: asyncio.run(_juntas(esperar_mal)))

    print('\n  Las esperas se solapan solo si la corrutina CEDE el control.')
    print('  time.sleep() no cede: bloquea el hilo único y anula la ventaja.')

    print(f'\n=== CPU-bound: {TAREAS} tareas que calculan ===\n')

    medir('secuencial', lambda: [hashear(i) for i in range(TAREAS)])
    medir('asyncio.gather', lambda: asyncio.run(_juntas(hashear_async)))

    print('\n  Acá asyncio no cambia nada: el trabajo es real y hay un solo')
    print('  hilo. Para esto hacen falta procesos (clase 9) o un executor.')


async def _juntas(corrutina):
    await asyncio.gather(*(corrutina(i) for i in range(TAREAS)))


if __name__ == '__main__':
    main()
