"""
main.py — Punto de entrada del monitor.

Orquesta todos los procesos: recolector, analizadores, agregador, display.
Por ahora solo levanta el recolector como prueba de concepto.
"""

import time
from multiprocessing import Process, Queue

from recolector import recolector


def consumidor_prueba(cola_pids: Queue) -> None:
    """
    Consumidor de prueba: toma PIDs de la cola y los cuenta.
    Después reemplazamos este por los analizadores reales.
    """
    contador = 0
    while True:
        pid = cola_pids.get()   # bloquea hasta que haya algo
        contador += 1
        # Cada 100 PIDs, imprime un progreso
        if contador % 100 == 0:
            print(f"[Consumidor prueba] procesó {contador} PIDs (último: {pid})")


if __name__ == "__main__":
    print("[Main] arrancando monitor...")

    # 1. Cola compartida entre recolector y consumidor
    cola_pids = Queue()

    # 2. Lanzar recolector
    p_recolector = Process(
        target=recolector,
        args=(cola_pids, 2.0),
        name="recolector",
        daemon=True,   # muere si el padre muere
    )
    p_recolector.start()

    # 3. Lanzar consumidor de prueba
    p_consumidor = Process(
        target=consumidor_prueba,
        args=(cola_pids,),
        name="consumidor",
        daemon=True,
    )
    p_consumidor.start()

    # 4. El main se queda mostrando algo mientras los hijos trabajan
    try:
        while True:
            time.sleep(5)
            print(f"[Main] cola tiene ~{cola_pids.qsize()} PIDs pendientes")
    except KeyboardInterrupt:
        print("\n[Main] Ctrl+C recibido, terminando...")
        # Los daemons mueren solos al terminar el main