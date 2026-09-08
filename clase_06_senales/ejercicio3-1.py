#!/usr/bin/env python3
"""Padre envía comandos al hijo vía señales."""
import os
import signal
import time

pid = os.fork()

if pid == 0:
    # === HIJO ===
    contador = 0

    def incrementar(sig, frame):
        global contador
        contador += 1
        print(f"[HIJO] Contador incrementado: {contador}")

    def mostrar(sig, frame):
        print(f"[HIJO] Valor actual: {contador}")

    signal.signal(signal.SIGUSR1, incrementar)
    signal.signal(signal.SIGUSR2, mostrar)

    print(f"[HIJO] PID={os.getpid()}, esperando señales...")

    while True:
        signal.pause()  # Esperar señales

else:
    # === PADRE ===
    time.sleep(0.5)  # Dar tiempo al hijo

    print("[PADRE] Enviando SIGUSR1 (incrementar) x3")
    for _ in range(3):
        os.kill(pid, signal.SIGUSR1)
        time.sleep(0.3)

    print("[PADRE] Enviando SIGUSR2 (mostrar)")
    os.kill(pid, signal.SIGUSR2)
    time.sleep(0.3)

    print("[PADRE] Enviando SIGUSR1 x2")
    for _ in range(2):
        os.kill(pid, signal.SIGUSR1)
        time.sleep(0.3)

    print("[PADRE] Enviando SIGUSR2 (mostrar)")
    os.kill(pid, signal.SIGUSR2)
    time.sleep(0.3)

    print("[PADRE] Terminando hijo")
    os.kill(pid, signal.SIGTERM)
    os.wait()
