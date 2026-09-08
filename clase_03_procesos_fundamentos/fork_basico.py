#!/usr/bin/env python3
"""Fork con wait."""
import os

print(f"Proceso original: PID={os.getpid()}")

pid = os.fork()

if pid == 0:
    print(f"Hijo trabajando...")
    for i in range(3):
        print(f"  Hijo: paso {i+1}")
    print(f"Hijo terminando con código 42")
    os._exit(42)
else:
    print(f"Padre esperando al hijo {pid}...")
    _, status = os.wait()

    if os.WIFEXITED(status):
        codigo = os.WEXITSTATUS(status)
        print(f"Padre: hijo terminó con código {codigo}")