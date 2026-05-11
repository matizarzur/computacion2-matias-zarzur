#!/usr/bin/env python3
"""Timer periódico con setitimer."""
import signal
import time
import os

class TimerPeriodico:
    def __init__(self, intervalo, callback):
        self.intervalo = intervalo
        self.callback = callback
        self.activo = False

    def _handler(self, sig, frame):
        if self.activo:
            self.callback()

    def iniciar(self):
        self.activo = True
        signal.signal(signal.SIGALRM, self._handler)
        signal.setitimer(signal.ITIMER_REAL, self.intervalo, self.intervalo)
        print(f"Timer iniciado (cada {self.intervalo}s)")

    def detener(self):
        self.activo = False
        signal.setitimer(signal.ITIMER_REAL, 0)
        print("Timer detenido")

# Uso
stats = {"operaciones": 0}

def mostrar_stats():
    print(f"[STATS] Operaciones hasta ahora: {stats['operaciones']}")

timer = TimerPeriodico(2.0, mostrar_stats)
timer.iniciar()

print("Simulando trabajo...")
print("Ctrl+C para terminar")

try:
    for i in range(20):
        stats["operaciones"] += 1
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    timer.detener()
    print(f"\nTotal de operaciones: {stats['operaciones']}")
