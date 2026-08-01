"""
main.py — Punto de entrada del monitor.

Orquesta todos los procesos: recolector, 7 analizadores, agregador.
Registra los handlers de señales y coordina las acciones
(shutdown, reload, dump, toggle verbose) desde su loop principal.
"""

import json
import time
from datetime import datetime
from multiprocessing import Process, Queue, Manager

from recolector import recolector
from agregador import agregador
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
        # Convertir snapshot a dict serializable
        data = {}
        for tipo in snapshot.keys():
            valor = snapshot[tipo]
            data[tipo] = str(valor)   # str() a lo bruto para evitar problemas
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[Main] snapshot volcado a {filename}")
    except Exception as e:
        print(f"[Main] error al hacer dump: {e}")


if __name__ == "__main__":
    print("[Main] arrancando monitor...")

    # Registrar handlers ANTES de crear los procesos hijos
    registrar_handlers()

    # Config inicial
    config = cargar_config()
    intervalo_recolector = config.get("intervalo_recolector", 2.0)
    intervalo_sistema = config.get("intervalo_sistema", 2.0)

    with Manager() as manager:
        # Cola de resultados
        cola_resultados = Queue()

        # Colas por analizador
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
        verbose = manager.Value("i", 0)  # 0 = normal, 1 = verbose (SIGUSR2 lo alterna)

        # Recolector
        p_recolector = Process(
            target=recolector,
            args=(colas_analizadores, cola_resultados, intervalo_recolector),
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

        # Analizador de Sistema
        p_sistema = Process(
            target=analizador_sistema,
            args=(cola_resultados, intervalo_sistema),
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

        print("[Main] todos los procesos arrancados. Enviame señales:")
        print(f"  kill -HUP  {__import__('os').getpid()}   # recargar config")
        print(f"  kill -USR1 {__import__('os').getpid()}   # dump snapshot")
        print(f"  kill -USR2 {__import__('os').getpid()}   # toggle verbose")
        print("  Ctrl+C o SIGTERM para salir\n")

        # Loop principal: revisa flags y muestra estado
        while not Flags.terminar.is_set():
            time.sleep(1)

            # Chequeo de flags de señales
            if Flags.recargar.is_set():
                Flags.recargar.clear()
                config = cargar_config()
                print(f"[Main] SIGHUP -> config recargada: {config}")

            if Flags.dump.is_set():
                Flags.dump.clear()
                dump_snapshot(snapshot)

            if Flags.toggle_verbose.is_set():
                Flags.toggle_verbose.clear()
                verbose.value = 1 - verbose.value
                print(f"[Main] SIGUSR2 -> verbose = {verbose.value}")

            # Estado del snapshot (temporal, hasta que hagamos la TUI)
            tipos = list(snapshot.keys())
            if tipos:
                resumenes = []
                for tipo in tipos:
                    valor = snapshot[tipo]
                    if isinstance(valor, dict):
                        resumenes.append(f"{tipo}={len(valor)}")
                    else:
                        resumenes.append(tipo)
                print(f"[Main] {' | '.join(resumenes)}")

# Salida limpia
        print("[Main] señal de terminación recibida. Terminando procesos hijos...")
        todos = [p_recolector, p_agregador, p_sistema] + procesos_analizadores

        print("[Main] enviando SIGTERM a todos los hijos...")
        for p in todos:
            print(f"  terminate {p.name}")
            p.terminate()

        print("[Main] esperando que terminen...")
        for p in todos:
            print(f"  join {p.name}...", end=" ", flush=True)
            p.join(timeout=1)
            if p.is_alive():
                print(f"vivo aún, kill -9", flush=True)
                p.kill()
                p.join(timeout=1)
            else:
                print("ok", flush=True)

        print("[Main] adiós")