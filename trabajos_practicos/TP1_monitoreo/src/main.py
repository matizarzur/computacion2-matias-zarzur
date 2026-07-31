"""
main.py — Punto de entrada del monitor.

Orquesta todos los procesos: recolector, 6 analizadores por-PID, agregador.
"""

import time
from multiprocessing import Process, Queue, Manager

from recolector import recolector
from agregador import agregador
from analizadores.resumen import analizador_resumen
from analizadores.memoria import analizador_memoria
from analizadores.fds import analizador_fds
from analizadores.threads import analizador_threads
from analizadores.senales import analizador_senales
from analizadores.scheduling import analizador_scheduling


if __name__ == "__main__":
    print("[Main] arrancando monitor...")

    with Manager() as manager:
        # Cola compartida para resultados hacia el agregador
        cola_resultados = Queue()

        # Una cola por cada analizador
        cola_resumen = Queue()
        cola_memoria = Queue()
        cola_fds = Queue()
        cola_threads = Queue()
        cola_senales = Queue()
        cola_scheduling = Queue()

        colas_analizadores = [
            cola_resumen,
            cola_memoria,
            cola_fds,
            cola_threads,
            cola_senales,
            cola_scheduling,
        ]

        snapshot = manager.dict()

        # Recolector
        p_recolector = Process(
            target=recolector,
            args=(colas_analizadores, cola_resultados, 2.0),
            name="recolector",
            daemon=True,
        )
        p_recolector.start()

        # Analizadores (uno por vista)
        analizadores = [
            (analizador_resumen, cola_resumen, "analizador_resumen"),
            (analizador_memoria, cola_memoria, "analizador_memoria"),
            (analizador_fds, cola_fds, "analizador_fds"),
            (analizador_threads, cola_threads, "analizador_threads"),
            (analizador_senales, cola_senales, "analizador_senales"),
            (analizador_scheduling, cola_scheduling, "analizador_scheduling"),
        ]

        procesos_analizadores = []
        for funcion, cola, nombre in analizadores:
            p = Process(
                target=funcion,
                args=(cola, cola_resultados),
                name=nombre,
                daemon=True,
            )
            p.start()
            procesos_analizadores.append(p)

        # Agregador
        p_agregador = Process(
            target=agregador,
            args=(cola_resultados, snapshot),
            name="agregador",
            daemon=True,
        )
        p_agregador.start()

        # Loop del main: muestra el estado del snapshot cada 3 segundos
        try:
            while True:
                time.sleep(3)
                tipos = list(snapshot.keys())
                print(f"\n[Main] snapshot tiene tipos: {tipos}")
                for tipo in tipos:
                    valor = snapshot[tipo]
                    if isinstance(valor, dict):
                        print(f"  {tipo}: {len(valor)} procesos")
                    else:
                        print(f"  {tipo}: {valor}")
        except KeyboardInterrupt:
            print("\n[Main] Ctrl+C recibido, terminando...")