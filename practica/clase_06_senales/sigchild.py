#!/usr/bin/env python3
"""Usar SIGCHLD para detectar cuando terminan los hijos."""
import os
import signal
import time

hijos_activos = set()
resultados = {}

def sigchld_handler(sig, frame):
    """Recoger hijos terminados sin bloquear."""
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            hijos_activos.discard(pid)
            codigo = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
            resultados[pid] = codigo
            # Nota: print no es async-signal-safe, pero funciona en Python
            print(f"[SIGCHLD] Hijo {pid} terminó con código {codigo}")
        except ChildProcessError:
            break

signal.signal(signal.SIGCHLD, sigchld_handler)

# Crear 5 hijos con diferentes duraciones
print("Creando 5 hijos...")
for i in range(5):
    pid = os.fork()
    if pid == 0:
        # Hijo
        duracion = (i + 1) * 0.5
        time.sleep(duracion)
        os._exit(i)
    else:
        hijos_activos.add(pid)
        print(f"Creado hijo {pid}, durará {(i+1)*0.5}s")

# El padre hace otras cosas mientras los hijos trabajan
print("\n[PADRE] Trabajando mientras los hijos se ejecutan...")
for tick in range(10):
    print(f"[PADRE] Tick {tick}, hijos activos: {len(hijos_activos)}")
    time.sleep(0.5)
    if not hijos_activos:
        break

print(f"\n[PADRE] Todos terminaron. Resultados: {resultados}")
