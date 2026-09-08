#!/usr/bin/env python3
"""Ejercicio 5.1: cliente TCP con reintentos y backoff.

Reintenta conectar con espera creciente si el servidor todavía no
levantó. Pensado para lanzarse antes que el servidor y probar que
espera en vez de morir con ConnectionRefusedError.

Uso:
    python3 cliente_reintentos.py [host] [puerto] [intentos]
"""
import socket
import sys
import time


def conectar_con_reintentos(host, puerto, intentos=5):
    for intento in range(1, intentos + 1):
        try:
            return socket.create_connection((host, puerto), timeout=2)
        except (ConnectionRefusedError, TimeoutError) as e:
            if intento == intentos:
                raise ConnectionError(
                    f'No se pudo conectar a {host}:{puerto} tras {intentos} intentos'
                ) from e
            espera = 0.5 * intento
            print(f'Intento {intento} falló ({e}). Reintento en {espera}s')
            time.sleep(espera)


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    puerto = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    intentos = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    s = conectar_con_reintentos(host, puerto, intentos)
    print(f'Conectado a {host}:{puerto}')
    s.close()
