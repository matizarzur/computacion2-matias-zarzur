#!/usr/bin/env python3
"""Servidor eco: un thread por cliente, con demora artificial de 10s."""
import socket
import threading
import time

def atender(conn, direccion, t_accept):
    print(f'[{direccion}] aceptado, procesando (10s)...')
    with conn:
        while True:
            datos = conn.recv(4096)
            if not datos:
                break
            time.sleep(10)  # demora artificial antes de responder
            conn.sendall(datos)
    print(f'[{direccion}] desconectado (atendido {time.time() - t_accept:.4f}s después de aceptar)')

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(('0.0.0.0', 8080))
    servidor.listen(128)
    print('Servidor escuchando en :8080')
    while True:
        conn, direccion = servidor.accept()
        t = time.time()
        print(f'[{direccion}] aceptado en {t:.4f}')
        hilo = threading.Thread(target=atender, args=(conn, direccion, t), daemon=True)
        hilo.start()