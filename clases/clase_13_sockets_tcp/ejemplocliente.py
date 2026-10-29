#!/usr/bin/env python3
"""Cliente TCP mínimo."""
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect(('localhost', 8080))      # handshake de tres vías
    s.sendall(b'hola mundo\n')
    respuesta = s.recv(4096)
    print(f'Recibido: {respuesta!r}')