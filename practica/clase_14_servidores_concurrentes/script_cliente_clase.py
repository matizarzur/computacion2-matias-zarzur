#!/usr/bin/env python3
"""Lanza N clientes en paralelo contra el servidor eco (con demora de 10s)."""
import socket
import threading
import time

HOST, PORT = '127.0.0.1', 8080
N = 200
TIMEOUT = 15  # más que los 10s de demora del servidor

resultados = []
fallos = []
lock = threading.Lock()

def cliente(i):
    t0 = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((HOST, PORT))
            mensaje = f'hola-{i}'.encode()
            s.sendall(mensaje)
            eco = s.recv(4096)
            assert eco == mensaje
        dt = time.time() - t0
        with lock:
            resultados.append(dt)
    except OSError as e:
        with lock:
            fallos.append((i, str(e)))

t_inicio = time.time()
hilos = [threading.Thread(target=cliente, args=(i,)) for i in range(N)]
for h in hilos:
    h.start()
for h in hilos:
    h.join()
t_total = time.time() - t_inicio

print(f'N = {N} clientes')
print(f'Exitosos: {len(resultados)}  |  Fallidos: {len(fallos)}')
print(f'Tiempo total: {t_total:.4f}s')
if resultados:
    print(f'Tiempo promedio (exitosos): {sum(resultados)/len(resultados):.4f}s')
    print(f'Tiempo máximo (exitosos): {max(resultados):.4f}s')
if fallos:
    print(f'Ejemplo de fallo: cliente {fallos[0][0]} -> {fallos[0][1]}')