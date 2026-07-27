"""
main.py — Punto de entrada del monitor.

Orquesta todos los procesos: recolector, analizadores, agregador, display.
Por ahora tenemos: recolector, agregador, y un "analizador de prueba".
"""

import time
from multiprocessing import Process, Queue, Manager

from recolector import recolector
from agregador import agregador
from analizadores.resumen import analizador_resumen


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
        
        # Lanzar 1 analizador de prueba
        p_resumen = Process(
            target=analizador_resumen,
            args=(cola_pids, cola_resultados),
            name="analizador_resumen",
            daemon=True,
        )
        p_resumen.start()

        # Lanzar agregador
        p_agregador = Process(
            target=agregador,
            args=(cola_resultados, snapshot),
            name="agregador",
            daemon=True,
        )
        p_agregador.start()

        # Loop del main: cada 3 seg, imprime resumen del snapshot
        try:
            while True:
                time.sleep(3)
                if "resumen" in snapshot:
                    procesos = snapshot["resumen"]
                    print(f"[Main] snapshot tiene {len(procesos)} procesos en 'resumen'")
                    # Mostrar los primeros 3
                    for pid, status in list(procesos.items())[:3]:
                        print(f"  PID={pid}: {status.name} (state={status.state})")
                else:
                    print("[Main] snapshot vacío todavía")
        except KeyboardInterrupt:
            print("\n[Main] Ctrl+C recibido, terminando...")