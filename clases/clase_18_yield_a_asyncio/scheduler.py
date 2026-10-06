#!/usr/bin/env python3
"""Un event loop hecho a mano, con generadores.

Muestra que la concurrencia cooperativa no necesita threads ni magia:
alcanza con generadores que ceden el control y una cola que los reanuda.

Uso:
    python3 scheduler.py            # intercalado simple
    python3 scheduler.py --tiempo   # con espera, como asyncio.sleep
"""
import sys
import time
from collections import deque


# ---------------------------------------------------------------
# Versión 1: intercalar tareas
# ---------------------------------------------------------------

def tarea(nombre, pasos):
    """Una tarea que cede el control en cada paso."""
    for i in range(1, pasos + 1):
        print(f'  [{nombre}] paso {i}/{pasos}')
        yield                      # me suspendo acá y cedo el control
    print(f'  [{nombre}] terminada')


def scheduler(tareas):
    """El event loop más simple posible: una cola y un next() por turno."""
    pendientes = deque(tareas)
    vueltas = 0
    while pendientes:
        t = pendientes.popleft()
        try:
            next(t)                # reanudar hasta el próximo yield
            pendientes.append(t)   # no terminó: vuelve al final de la cola
            vueltas += 1
        except StopIteration:
            # El generador se quedó sin código: la tarea terminó.
            pass
    return vueltas


# ---------------------------------------------------------------
# Versión 2: el scheduler entiende de tiempo
# ---------------------------------------------------------------

def dormir(segundos):
    """No duerme: cede el control diciendo cuándo quiere volver."""
    yield time.monotonic() + segundos


def tarea_lenta(nombre, veces, espera=0.15):
    for i in range(1, veces + 1):
        print(f'  [{nombre}] {i}/{veces}  (t={time.monotonic() - T0:.2f}s)')
        yield from dormir(espera)      # delega: los yield suben al scheduler
    print(f'  [{nombre}] terminada')


def scheduler_con_tiempo(tareas):
    """Igual que el anterior, pero respeta cuándo quiere volver cada tarea."""
    pendientes = deque((0.0, t) for t in tareas)
    while pendientes:
        despertar, t = pendientes.popleft()
        if time.monotonic() < despertar:
            pendientes.append((despertar, t))    # todavía no le toca
            continue
        try:
            cuando = next(t)                     # la tarea dice cuándo volver
            pendientes.append((cuando or 0.0, t))
        except StopIteration:
            pass


if __name__ == '__main__':
    T0 = time.monotonic()
    if '--tiempo' in sys.argv:
        print('=== Tres tareas que esperan, intercaladas en un hilo ===')
        t0 = time.monotonic()
        scheduler_con_tiempo([
            tarea_lenta('A', 3),
            tarea_lenta('B', 2),
            tarea_lenta('C', 4),
        ])
        print(f'\nTotal: {time.monotonic() - t0:.2f}s')
        print('Las esperas se solapan: no es la suma de todas.')
    else:
        print('=== Tres tareas intercaladas en UN solo hilo ===')
        v = scheduler([tarea('A', 3), tarea('B', 2), tarea('C', 4)])
        print(f'\nEl scheduler hizo {v} reanudaciones.')
        print('Sin threads, sin procesos: solo generadores y una cola.')
