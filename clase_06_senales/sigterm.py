#!/usr/bin/env python3
"""Shutdown limpio con SIGTERM."""
import signal
import sys
import time
import os

class Aplicacion:
    def __init__(self):
        self.ejecutando = True
        self.recursos = []

        # Registrar manejadores
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, sig, frame):
        nombre_señal = signal.Signals(sig).name
        print(f"\nRecibí {nombre_señal}, cerrando...")
        self.ejecutando = False

    def adquirir_recurso(self, nombre):
        print(f"Adquiriendo recurso: {nombre}")
        self.recursos.append(nombre)

    def liberar_recursos(self):
        for recurso in reversed(self.recursos):
            print(f"Liberando recurso: {recurso}")
            time.sleep(0.3)
        self.recursos.clear()

    def run(self):
        print(f"PID: {os.getpid()}")
        print("Enviá 'kill <pid>' para terminar limpiamente")

        # Simular adquisición de recursos
        self.adquirir_recurso("base_de_datos")
        self.adquirir_recurso("archivo_log")
        self.adquirir_recurso("conexion_red")

        # Loop principal
        while self.ejecutando:
            print("Trabajando...")
            time.sleep(1)

        # Cleanup
        self.liberar_recursos()
        print("Aplicación terminada correctamente")

if __name__ == "__main__":
    app = Aplicacion()
    app.run()
