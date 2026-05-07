#!/usr/bin/env python3
"""Comunicación bidireccional con dos pipes."""
import os

p2h_read, p2h_write = os.pipe()
h2p_read, h2p_write = os.pipe()

pid = os.fork()

if pid == 0:
    os.close(p2h_write)
    os.close(h2p_read)

    pregunta = os.read(p2h_read, 1024).decode().strip()
    print(f"[HIJO] Recibí pregunta: {pregunta}")

    if pregunta.isdigit():
        respuesta = str(int(pregunta) ** 2)
    else:
        respuesta = "No es un número"

    os.write(h2p_write, respuesta.encode())
    print(f"[HIJO] Envié respuesta: {respuesta}")

    os.close(p2h_read)
    os.close(h2p_write)
    os._exit(0)

else:
    os.close(p2h_read)
    os.close(h2p_write)

    numero = "42"
    print(f"[PADRE] Enviando número: {numero}")
    os.write(p2h_write, numero.encode())
    os.close(p2h_write)

    respuesta = os.read(h2p_read, 1024).decode()
    print(f"[PADRE] Respuesta: {numero}² = {respuesta}")

    os.close(h2p_read)
    os.wait()