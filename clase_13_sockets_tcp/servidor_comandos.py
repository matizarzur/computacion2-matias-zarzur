#!/usr/bin/env python3
"""Ejercicio adicional: servidor de comandos sobre framing por líneas.

TIME       -> devuelve la hora actual
ECHO texto -> devuelve el texto
QUIT       -> cierra la conexión

Estructura mínima de lo que hace SMTP: comandos de texto, uno por línea,
con una respuesta por comando.
"""
import datetime
import socket

from framing_propio import recibir_lineas

HOST, PUERTO = '0.0.0.0', 8080


def procesar(linea: bytes) -> bytes | None:
    texto = linea.decode('utf-8', errors='replace').strip()
    if texto == 'TIME':
        return datetime.datetime.now().isoformat().encode('utf-8')
    if texto.startswith('ECHO '):
        return texto[len('ECHO '):].encode('utf-8')
    if texto == 'QUIT':
        return None
    return b'ERROR: comando desconocido'


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PUERTO))
        srv.listen(5)
        print(f'Escuchando en {HOST}:{PUERTO}')
        while True:
            conn, direccion = srv.accept()
            print(f'Conexión de {direccion}')
            with conn:
                for linea in recibir_lineas(conn):
                    respuesta = procesar(linea)
                    if respuesta is None:
                        conn.sendall(b'BYE\n')
                        break
                    conn.sendall(respuesta + b'\n')


if __name__ == '__main__':
    main()
