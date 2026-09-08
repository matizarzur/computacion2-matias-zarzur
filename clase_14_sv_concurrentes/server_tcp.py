#!/usr/bin/env python3
"""Servidor eco: un thread por cliente."""
import socket
import threading

def atender(conn, direccion):
    """Corre en su propio thread, uno por cliente."""
    with conn:
        while True:
            datos = conn.recv(4096)
            if not datos:
                break
            conn.sendall(datos)
    print(f'[{direccion}] desconectado')

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(('0.0.0.0', 8080))
    servidor.listen(128)

    while True:
        conn, direccion = servidor.accept()
        hilo = threading.Thread(target=atender, args=(conn, direccion),
                                daemon=True)
        hilo.start()
        # El bucle vuelve INMEDIATAMENTE a accept()