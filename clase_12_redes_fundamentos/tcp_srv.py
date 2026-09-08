#!/usr/bin/env python3
"""Receptor TCP para el ejercicio 6 parte A.

Contrapartida de udp_srv.py: cuenta cuántas veces devuelve datos recv()
frente a los tres send() del cliente.

Se usa un receptor propio en vez de `nc -l 8080 | od -c` porque od
bufferea su salida: si los tres envíos llegan separados igual se ven
pegados en pantalla, y la prueba no demostraría nada.

Uso:
    python3 tcp_srv.py

Y desde otra terminal (los tres send() sin pausa):
    python3 -c "
    import socket
    s = socket.create_connection(('localhost', 8080))
    s.send(b'HOLA'); s.send(b'COMO'); s.send(b'ESTAS')
    s.close()
    "

Salida observada: un solo recv() con b'HOLACOMOESTAS'.
Agregando time.sleep(1) entre los send() salen tres recv() separados,
pero eso depende del timing, no del protocolo: TCP nunca prometió
respetar los límites entre send().
"""
import socket

HOST, PUERTO = 'localhost', 8080

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Permite re-bindear el puerto mientras la conexión anterior está en TIME_WAIT.
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind((HOST, PUERTO))
srv.listen(1)

print(f"Escuchando en {HOST}:{PUERTO}...")
conn, origen = srv.accept()
print(f"Conectado con {origen}")

n = 0
try:
    while True:
        datos = conn.recv(4096)
        if not datos:          # b'' = el otro extremo cerró su lado
            break
        n += 1
        print(f"recv #{n}: {datos!r}")
    print(f"=> {n} recv() con datos para los 3 send() del cliente")
finally:
    conn.close()
    srv.close()
