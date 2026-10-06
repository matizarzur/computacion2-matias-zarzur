#!/usr/bin/env python3
"""Mini-shell: paso 3 - comandos internos."""
import os

def cmd_cd(args):
    """Implementación del comando cd."""
    if not args:
        destino = os.environ.get("HOME", "/")
    else:
        destino = args[0]

    try:
        os.chdir(destino)
    except OSError as e:
        print(f"cd: {e}")

def main():
    internos = {
        "cd": cmd_cd,
    }

    while True:
        cwd = os.getcwd()
        try:
            linea = input(f"minish:{cwd}$ ")
        except EOFError:
            print("\nChau!")
            break

        linea = linea.strip()
        if not linea:
            continue

        if linea == "exit":
            break

        partes = linea.split()
        comando = partes[0]
        args = partes[1:]

        if comando in internos:
            internos[comando](args)
            continue

        pid = os.fork()

        if pid == 0:
            try:
                os.execvp(comando, [comando] + args)
            except OSError as e:
                print(f"minish: {comando}: {e}")
                os._exit(127)
        else:
            _, status = os.wait()
            codigo = os.WEXITSTATUS(status)
            if codigo != 0:
                print(f"[código {codigo}]")

if __name__ == "__main__":
    main()