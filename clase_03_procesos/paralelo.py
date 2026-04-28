#!/usr/bin/env python3
"""
Ejecutor de comandos en paralelo.
Uso: python3 paralelo.py "cmd1" "cmd2" ...
"""
import os
import sys
import time


def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} comando1 [comando2 ...]")
        sys.exit(1)

    comandos = sys.argv[1:]
    pids = {}  # {pid: comando}
    inicio = time.time()

    # Lanzar todos los procesos en paralelo
    for cmd in comandos:
        partes = cmd.split()
        pid = os.fork()

        if pid == 0:
            try:
                os.execvp(partes[0], partes)
            except OSError as e:
                print(f"Error ejecutando '{cmd}': {e}", file=sys.stderr)
                os._exit(127)
        else:
            pids[pid] = cmd
            print(f"[{pid}] Iniciado: {cmd}")

    # Esperar a todos
    exitosos = 0
    fallidos = 0

    while pids:
        pid, status = os.wait()
        cmd = pids.pop(pid)
        codigo = os.WEXITSTATUS(status)
        print(f"[{pid}] Terminado: {cmd} (código: {codigo})")
        if codigo == 0:
            exitosos += 1
        else:
            fallidos += 1

    duracion = time.time() - inicio

    print(f"\nResumen:")
    print(f"- Comandos ejecutados: {len(comandos)}")
    print(f"- Exitosos: {exitosos}")
    print(f"- Fallidos: {fallidos}")
    print(f"- Tiempo total: {duracion:.2f}s")


if __name__ == "__main__":
    main()