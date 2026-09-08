#!/usr/bin/env python3
"""Ejercicio adicional: cliente HTTP mínimo, sin requests ni http.client.

Repite a mano en Python lo que se hizo con nc en la clase 12.
"""
import socket
import sys


def get(host: str, path: str = '/', puerto: int = 80) -> tuple[str, dict, bytes]:
    peticion = (
        f'GET {path} HTTP/1.1\r\n'
        f'Host: {host}\r\n'
        f'Connection: close\r\n'
        f'\r\n'
    ).encode('ascii')

    with socket.create_connection((host, puerto), timeout=10) as s:
        s.sendall(peticion)
        crudo = b''
        while True:
            pedazo = s.recv(4096)
            if not pedazo:
                break
            crudo += pedazo

    cabeceras_crudas, _, cuerpo = crudo.partition(b'\r\n\r\n')
    lineas = cabeceras_crudas.decode('iso-8859-1').split('\r\n')
    estado = lineas[0]
    headers = {}
    for linea in lineas[1:]:
        if ':' in linea:
            clave, _, valor = linea.partition(':')
            headers[clave.strip()] = valor.strip()
    return estado, headers, cuerpo


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else 'example.com'
    path = sys.argv[2] if len(sys.argv) > 2 else '/'
    estado, headers, cuerpo = get(host, path)
    print(f'Estado: {estado}')
    for k, v in headers.items():
        print(f'  {k}: {v}')
    print(f'Cuerpo: {len(cuerpo)} bytes')
