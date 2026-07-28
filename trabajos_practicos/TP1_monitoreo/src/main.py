"""
main.py — Punto de entrada del monitor.

Orquesta todos los procesos: recolector, analizadores, agregador, display.
Por ahora tenemos: recolector, agregador, y dos analizadores (Resumen y Memoria).
"""

import time
from multiprocessing import Process, Queue, Manager

from recolector import recolector
from agregador import agregador
from analizadores.resumen import analizador_resumen
from analizadores.memoria import analizador_memoria


if __name__ == "__main__":
    print("[Main] arrancando monitor...")

    with Manager() as manager:
        # Estructuras compartidas
        cola_pids = Queue()
        cola_resultados = Queue()
        snapshot = manager.dict()

        # Lanzar recolector
        p_recolector = Process(
            target=recolector,
            args=(cola_pids, cola_resultados, 2.0),
            name="recolector",
            daemon=True,
        )
        p_recolector.start()

        # Lanzar analizador de Resumen
        p_resumen = Process(
            target=analizador_resumen,
            args=(cola_pids, cola_resultados),
            name="analizador_resumen",
            daemon=True,
        )
        p_resumen.start()

        # Lanzar analizador de Memoria
        p_memoria = Process(
            target=analizador_memoria,
            args=(cola_pids, cola_resultados),
            name="analizador_memoria",
            daemon=True,
        )
        p_memoria.start()

        # Lanzar agregador
        p_agregador = Process(
            target=agregador,
            args=(cola_resultados, snapshot),
            name="agregador",
            daemon=True,
        )
        p_agregador.start()

        # Loop del main: cada 3 seg, muestra estado del snapshot
        try:
            while True:
                time.sleep(3)
                print(f"[Main] snapshot tiene tipos: {list(snapshot.keys())}")

                if "resumen" in snapshot:
                    print(f"  resumen: {len(snapshot['resumen'])} procesos")

                if "memoria" in snapshot:
                    print(f"  memoria: {len(snapshot['memoria'])} procesos")
        except KeyboardInterrupt:
            print("\n[Main] Ctrl+C recibido, terminando...")