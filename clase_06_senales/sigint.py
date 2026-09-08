#!/usr/bin/env python3
"""Capturar SIGINT (Ctrl+C)."""
import signal
import time

contador_ctrl_c = 0

def manejador_sigint(sig, frame):
    global contador_ctrl_c
    contador_ctrl_c += 1
    print(f"\n¡Ctrl+C detectado! (vez #{contador_ctrl_c})")

    if contador_ctrl_c >= 3:
        print("OK, OK, me voy...")
        raise SystemExit(0)
    else:
        print(f"Presioná {3 - contador_ctrl_c} veces más para salir")

signal.signal(signal.SIGINT, manejador_sigint)

print("Presioná Ctrl+C (3 veces para salir)")
print("Observá cómo el programa no termina la primera vez")

while True:
    print(".", end="", flush=True)
    time.sleep(0.5)