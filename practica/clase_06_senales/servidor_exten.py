#!/usr/bin/env python3
"""
Servidor con múltiples acciones via SIGUSR1.
1x SIGUSR1 = mostrar stats
2x SIGUSR1 = recargar config
3x SIGUSR1 = rotar logs
"""
import signal
import time
import os

class Servidor:
    def __init__(self):
        self.ejecutando = True
        self.config = {"max_conexiones": 100, "timeout": 30}
        self.stats = {"requests": 0, "errores": 0, "inicio": time.time()}
        self.contador_usr1 = 0

        self._registrar_manejadores()

    def _registrar_manejadores(self):
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGHUP, self._reload_config)
        signal.signal(signal.SIGUSR1, self._contar_usr1)
        signal.signal(signal.SIGUSR2, self._rotar_logs)
        signal.signal(signal.SIGALRM, self._ejecutar_accion)

    def _shutdown(self, sig, frame):
        nombre = signal.Signals(sig).name
        print(f"\n[{nombre}] Iniciando shutdown...")
        self.ejecutando = False

    def _reload_config(self, sig, frame):
        print("\n[SIGHUP] Recargando configuración...")
        self.config["max_conexiones"] += 10
        self.config["recargado"] = time.ctime()
        print(f"[SIGHUP] Nueva config: {self.config}")

    def _mostrar_stats(self):
        uptime = time.time() - self.stats["inicio"]
        print(f"\n[SIGUSR1 x1] === Estadísticas ===")
        print(f"  Uptime: {uptime:.1f}s")
        print(f"  Requests: {self.stats['requests']}")
        print(f"  Errores: {self.stats['errores']}")
        print(f"  Config: {self.config}")

    def _rotar_logs(self, sig=None, frame=None):
        print(f"\n[SIGUSR2] Rotando logs...")
        print(f"[SIGUSR2] Logs rotados a server.log.{int(time.time())}")

    def _contar_usr1(self, sig, frame):
        self.contador_usr1 += 1
        print(f"\n[SIGUSR1] Recibido ({self.contador_usr1} en la ventana actual)")
        # Reiniciar el timer cada vez que llega una señal
        signal.alarm(1)

    def _ejecutar_accion(self, sig, frame):
        count = self.contador_usr1
        self.contador_usr1 = 0  # resetear

        if count == 1:
            self._mostrar_stats()
        elif count == 2:
            self._reload_config(signal.SIGHUP, frame)
        elif count == 3:
            self._rotar_logs()
        else:
            print(f"\n[SIGALRM] {count} señales no corresponden a ninguna acción")

    def procesar_request(self):
        self.stats["requests"] += 1
        time.sleep(0.1)
        if self.stats["requests"] % 10 == 0:
            self.stats["errores"] += 1

    def run(self):
        print(f"Servidor iniciado (PID {os.getpid()})")
        print("Comandos disponibles:")
        print(f"  kill -USR1 {os.getpid()}              -> Mostrar stats")
        print(f"  kill -USR1 {os.getpid()} (x2 rápido) -> Recargar config")
        print(f"  kill -USR1 {os.getpid()} (x3 rápido) -> Rotar logs")
        print(f"  kill {os.getpid()}                    -> Shutdown")
        print()

        while self.ejecutando:
            self.procesar_request()

        print("Realizando cleanup...")
        time.sleep(0.5)
        print(f"Servidor terminado. Requests procesadas: {self.stats['requests']}")

if __name__ == "__main__":
    servidor = Servidor()
    servidor.run()
