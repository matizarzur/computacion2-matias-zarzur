#!/usr/bin/env python3
"""Comunicación básica por pipe."""
import os

read_fd, write_fd = os.pipe()

pid = os.fork()

if pid == 0:
    os.close(read_fd)

    mensajes = ["Mensaje 1 del hijo", "Mensaje 2 del hijo", "Mensaje 3 del hijo", "FIN"]
    for msg in mensajes:
        os.write(write_fd, (msg + "\n").encode())
        print(f"[HIJO] Envié: {msg}")

    os.close(write_fd)
    os._exit(0)

else:
    os.close(write_fd)
    print("[PADRE] Esperando mensajes del hijo...\n")

    buffer = b""
    while True:
        datos = os.read(read_fd, 1024)
        if not datos:
            break
        buffer += datos

    mensajes = buffer.decode().strip().split("\n")
    for msg in mensajes:
        print(f"[PADRE] Recibí: {msg}")

    os.close(read_fd)
    os.wait()
    print("\n[PADRE] Hijo terminó")