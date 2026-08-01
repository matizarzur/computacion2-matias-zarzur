"""
main.py — Punto de entrada del monitor.

Orquesta todos los procesos: recolector, 7 analizadores, agregador.
El display corre en el proceso principal (necesita la terminal real
para leer el teclado con termios).

Registra los handlers de señales; el display atiende las flags
(shutdown, reload, dump, toggle verbose) en su loop.

Los intervalos del recolector y del analizador de sistema son Value
compartidos, ajustables en tiempo real con +/- desde el display.
"""

import json
from datetime import datetime
from multiprocessing import Process, Queue, Manager

from recolector import recolector
from agregador import agregador
from display import display
from senales import registrar_handlers, Flags
from analizadores.resumen import analizador_resumen
from analizadores.memoria import analizador_memoria
from analizadores.fds import analizador_fds
from analizadores.threads import analizador_threads
from analizadores.senales import analizador_senales
from analizadores.scheduling import analizador_scheduling
from analizadores.sistema import analizador_sistema


CONFIG_PATH = "config.json"


def cargar_config() -> dict:
    """Lee config.json. Si no existe o es inválido, devuelve defaults."""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"intervalo_recolector": 2.0, "intervalo_sistema": 2.0}


def dump_snapshot(snapshot: dict) -> None:
    """Vuelca el snapshot a un archivo dump_<timestamp>.json."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dump_{timestamp}.json"
    try:
        data = {}
        for tipo in snapshot.keys():
            valor = snapshot[tipo]
            data[tipo] = str(valor)
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Main] error al hacer dump: {e}")


if __name__ == "__main__":
    print("[Main] arrancando monitor...")

    registrar_handlers()

    config = cargar_config()
    intervalo_recolector = config.get("intervalo_recolector", 2.0)
    intervalo_sistema = config.get("intervalo_sistema", 2.0)

    with Manager() as manager:
        cola_resultados = Queue()

        cola_resumen = Queue()
        cola_memoria = Queue()
        cola_fds = Queue()
        cola_threads = Queue()
        cola_senales = Queue()
        cola_scheduling = Queue()

        colas_analizadores = [
            cola_resumen, cola_memoria, cola_fds,
            cola_threads, cola_senales, cola_scheduling,
        ]

        snapshot = manager.dict()
        verbose = manager.Value("i", 0)

        # NUEVO: Value compartidos para los intervalos ajustables.
        # "d" = double (float). El display los modifica con +/-, y el
        # recolector/sistema los leen en cada vuelta de su loop.
        intervalo_recolector_val = manager.Value("d", intervalo_recolector)
        intervalo_sistema_val = manager.Value("d", intervalo_sistema)

        # Recolector (ahora recibe el Value, no un float)
        p_recolector = Process(
            target=recolector,
            args=(colas_analizadores, cola_resultados, intervalo_recolector_val),
            name="recolector",
            daemon=True,
        )
        p_recolector.start()

        # Analizadores por-PID
        analizadores_config = [
            (analizador_resumen, cola_resumen, "analizador_resumen"),
            (analizador_memoria, cola_memoria, "analizador_memoria"),
            (analizador_fds, cola_fds, "analizador_fds"),
            (analizador_threads, cola_threads, "analizador_threads"),
            (analizador_senales, cola_senales, "analizador_senales"),
            (analizador_scheduling, cola_scheduling, "analizador_scheduling"),
        ]

        procesos_analizadores = []
        for funcion, cola, nombre in analizadores_config:
            p = Process(target=funcion, args=(cola, cola_resultados),
                        name=nombre, daemon=True)
            p.start()
            procesos_analizadores.append(p)

        # Analizador de Sistema (ahora recibe el Value, no un float)
        p_sistema = Process(
            target=analizador_sistema,
            args=(cola_resultados, intervalo_sistema_val),
            name="analizador_sistema",
            daemon=True,
        )
        p_sistema.start()

        # Agregador
        p_agregador = Process(
            target=agregador,
            args=(cola_resultados, snapshot),
            name="agregador",
            daemon=True,
        )
        p_agregador.start()

        # Los intervalos ajustables van al display en un dict, para que
        # sepa cuál ajustar según la vista activa.
        intervalos = {
            "recolector": intervalo_recolector_val,
            "sistema": intervalo_sistema_val,
        }

        # El display corre en el proceso PRINCIPAL (necesita la terminal real
        # para leer el teclado con termios). Bloquea hasta que el usuario
        # sale con 'q' o llega SIGINT/SIGTERM.
        display(snapshot, Flags, cargar_config, dump_snapshot, verbose,
                intervalos, intervalo=1.0)

        # Salida limpia (se llega acá cuando el display retorna)
        print("[Main] terminando procesos hijos...")
        todos = [p_recolector, p_agregador, p_sistema] + procesos_analizadores
        for p in todos:
            p.terminate()
        for p in todos:
            p.join(timeout=1)
            if p.is_alive():
                p.kill()
                p.join(timeout=1)
        print("[Main] adiós")