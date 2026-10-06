#!/usr/bin/env python3
"""Múltiples hijos."""
import os
import time

def trabajo_hijo(numero, duracion):
    """Trabajo que hace cada hijo."""
    print(f"Hijo {numero} (PID {os.getpid()}): iniciando, durará {duracion}s")
    time.sleep(duracion)
    print(f"Hijo {numero}: terminando")
    os._exit(numero)

hijos_config = [2, 1, 3]
hijos_pids = []

for i, duracion in enumerate(hijos_config):
    pid = os.fork()
    if pid == 0:
        trabajo_hijo(i, duracion)
    else:
        hijos_pids.append(pid)
        print(f"Padre: creado hijo {i} con PID {pid}")

print(f"\nPadre: esperando a {len(hijos_pids)} hijos...")
while hijos_pids:
    pid, status = os.wait()
    codigo = os.WEXITSTATUS(status)
    hijos_pids.remove(pid)
    print(f"Padre: hijo PID {pid} terminó con código {codigo}")

print("Padre: todos los hijos terminaron")
