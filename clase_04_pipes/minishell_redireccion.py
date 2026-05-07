#!/usr/bin/env python3
"""Mini-shell con redirección."""
import os
import sys


def parsear_linea(linea):
    """
    Parsea una línea de comando.
    Retorna (comando, args, archivo_salida, archivo_entrada)
    """
    partes = linea.split()
    comando = partes[0] if partes else None
    args = []
    archivo_salida = None
    archivo_entrada = None

    i = 1
    while i < len(partes):
        if partes[i] == ">" and i + 1 < len(partes):
            archivo_salida = partes[i + 1]
            i += 2
        elif partes[i] == "<" and i + 1 < len(partes):
            archivo_entrada = partes[i + 1]
            i += 2
        else:
            args.append(partes[i])
            i += 1

    return comando, args, archivo_salida, archivo_entrada


def ejecutar(comando, args, archivo_salida=None, archivo_entrada=None):
    """Ejecuta un comando con redirección opcional."""
    pid = os.fork()

    if pid == 0:
        if archivo_salida:
            fd = os.open(archivo_salida, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
            os.dup2(fd, 1)
            os.close(fd)

        if archivo_entrada:
            fd = os.open(archivo_entrada, os.O_RDONLY)
            os.dup2(fd, 0)
            os.close(fd)

        try:
            os.execvp(comando, [comando] + args)
        except OSError as e:
            print(f"Error: {e}", file=sys.stderr)
            os._exit(127)
    else:
        _, status = os.wait()
        return os.WEXITSTATUS(status)


def main():
    while True:
        try:
            linea = input("minish$ ")
        except EOFError:
            print("\nChau!")
            break

        linea = linea.strip()
        if not linea:
            continue

        if linea == "exit":
            break

        comando, args, salida, entrada = parsear_linea(linea)
        if comando:
            ejecutar(comando, args, salida, entrada)


if __name__ == "__main__":
    main()