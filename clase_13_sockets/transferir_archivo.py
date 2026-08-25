#!/usr/bin/env python3
"""Ejercicio adicional: transferencia de archivos con framing por longitud.

Uso:
    python3 transferir_archivo.py servidor <puerto> <ruta_destino>
    python3 transferir_archivo.py cliente <host> <puerto> <ruta_origen>
"""
import socket
import sys

from framing_propio import enviar_mensaje, recibir_mensaje


def servidor(puerto: int, destino: str):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', puerto))
        srv.listen(1)
        print(f'Esperando archivo en :{puerto}...')
        conn, direccion = srv.accept()
        with conn:
            datos = recibir_mensaje(conn)
            with open(destino, 'wb') as f:
                f.write(datos)
        print(f'Guardado en {destino}: {len(datos)} bytes')


def cliente(host: str, puerto: int, origen: str):
    with open(origen, 'rb') as f:
        datos = f.read()
    with socket.create_connection((host, puerto), timeout=10) as s:
        enviar_mensaje(s, datos)
    print(f'Enviados {len(datos)} bytes desde {origen}')


if __name__ == '__main__':
    modo = sys.argv[1]
    if modo == 'servidor':
        servidor(int(sys.argv[2]), sys.argv[3])
    else:
        cliente(sys.argv[2], int(sys.argv[3]), sys.argv[4])
