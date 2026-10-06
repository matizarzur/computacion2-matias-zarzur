#!/usr/bin/env python3
"""Escribe a un named pipe."""
import os
import time

FIFO = "/tmp/mi_canal"

if not os.path.exists(FIFO):
    os.mkfifo(FIFO)

print(f"Escribiendo a {FIFO}...")
print("(Ejecutá lector_fifo.py en otra terminal)")

with open(FIFO, 'w') as f:
    for i in range(10):
        mensaje = f"Mensaje {i}: {time.ctime()}"
        print(f"Enviando: {mensaje}")
        f.write(mensaje + "\n")
        f.flush()
        time.sleep(1)

print("Escritura completada")
