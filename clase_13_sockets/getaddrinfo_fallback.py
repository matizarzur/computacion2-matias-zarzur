#!/usr/bin/env python3
"""Ejercicio adicional: recorrer getaddrinfo() a mano, como create_connection().

create_connection() hace exactamente esto: prueba cada (familia, IP) que
devuelve getaddrinfo() en orden, hasta que una conecte.
"""
import socket
import sys


def conectar(host: str, puerto: int):
    errores = []
    for familia, tipo, proto, _, sockaddr in socket.getaddrinfo(
        host, puerto, type=socket.SOCK_STREAM
    ):
        nombre_familia = {socket.AF_INET: 'IPv4', socket.AF_INET6: 'IPv6'}.get(familia, familia)
        try:
            s = socket.socket(familia, tipo, proto)
            s.settimeout(3)
            s.connect(sockaddr)
            print(f'Conectado por {nombre_familia} a {sockaddr}')
            return s
        except OSError as e:
            print(f'Falló {nombre_familia} {sockaddr}: {e}')
            errores.append(e)
    raise ConnectionError(f'Ninguna dirección de {host}:{puerto} respondió: {errores}')


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else 'example.com'
    puerto = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    s = conectar(host, puerto)
    s.close()
