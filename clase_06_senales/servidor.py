#!/usr/bin/env python3
"""
Servidor que responde a señales.
Uso:
    python3 servidor_signals.py

Señales:
    kill -HUP <pid>   -> Recargar config
    kill -USR1 <pid>  -> Mostrar stats
    kill -USR2 <pid>  -> Rotar logs
    kill <pid>        -> Shutdown limpio
"""
import signal
import sys
import time
import os

class Servidor:
    def __init__(self):
        self.ejecutando = True
        self.config = {"max_conexiones": 100, "timeout": 30}
        self.stats = {"requests": 0, "errores": 0, "inicio": time.time()}

        self._registrar_manejadores()

    def _registrar_manejadores(self):
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGHUP, self._reload_config)
        signal.signal(signal.SIGUSR1, self._mostrar_stats)
        signal.signal(signal.SIGUSR2, self._rotar_logs)

    def _shutdown(self, sig, frame):
        nombre = signal.Signals(sig).name
        print(f"\n[{nombre}] Iniciando shutdown...")
        self.ejecutando = False

    def _reload_config(self, sig, frame):
        print("\n[SIGHUP] Recargando configuración...")
        # Simular lectura de archivo de config
        self.config["max_conexiones"] += 10
        self.config["recargado"] = time.ctime()
        print(f"[SIGHUP] Nueva config: {self.config}")

    def _mostrar_stats(self, sig, frame):
        uptime = time.time() - self.stats["inicio"]
        print(f"\n[SIGUSR1] === Estadísticas ===")
        print(f"  Uptime: {uptime:.1f}s")
        print(f"  Requests: {self.stats['requests']}")
        print(f"  Errores: {self.stats['errores']}")
        print(f"  Config: {self.config}")

    def _rotar_logs(self, sig, frame):
        print(f"\n[SIGUSR2] Rotando logs...")
        # Simular rotación de logs
        print(f"[SIGUSR2] Logs rotados a server.log.{int(time.time())}")

    def procesar_request(self):
        """Simula procesamiento de una request."""
        self.stats["requests"] += 1
        # Simular trabajo
        time.sleep(0.1)
        # Simular errores ocasionales
        if self.stats["requests"] % 10 == 0:
            self.stats["errores"] += 1

    def run(self):
        print(f"Servidor iniciado (PID {os.getpid()})")
        print("Comandos disponibles:")
        print(f"  kill -HUP {os.getpid()}   -> Recargar config")
        print(f"  kill -USR1 {os.getpid()}  -> Ver stats")
        print(f"  kill -USR2 {os.getpid()}  -> Rotar logs")
        print(f"  kill {os.getpid()}        -> Shutdown")
        print()

        while self.ejecutando:
            self.procesar_request()

        # Cleanup
        print("Realizando cleanup...")
        time.sleep(0.5)
        print(f"Servidor terminado. Requests procesadas: {self.stats['requests']}")

if __name__ == "__main__":
    servidor = Servidor()
    servidor.run()
