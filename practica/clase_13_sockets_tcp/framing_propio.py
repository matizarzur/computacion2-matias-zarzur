#!/usr/bin/env python3
"""Ejercicio 3 (obligatorio) de la clase 13: framing sobre TCP.

Implementación propia de las dos estrategias de delimitación de mensajes,
más un servidor por cada una para probarlas a mano con `nc` o con un
cliente propio.

Parte B: framing por delimitador (`\\n`), servidor que responde en mayúsculas.
Parte C: framing por prefijo de longitud (4 bytes, big-endian).

Uso:
    python3 framing_propio.py lineas [puerto]      # servidor por delimitador
    python3 framing_propio.py longitud [puerto]    # servidor por longitud
    python3 framing_propio.py demo                 # corre la demo de las dos
"""
import socket
import struct
import sys
import threading


# ------------------------------------------------------------------
# Parte B: framing por delimitador
# ------------------------------------------------------------------

def recibir_lineas(sock):
    """Generador de mensajes completos separados por '\\n'.

    Hace falta un buffer que sobreviva entre llamadas a recv(): un solo
    recv() puede traer media línea, o varias líneas juntas.
    """
    buffer = b''
    while True:
        pedazo = sock.recv(4096)
        if not pedazo:
            if buffer:
                print(f'  [lineas] conexión cerrada con datos sin terminar: {buffer!r}')
            return
        buffer += pedazo
        # Ojo con el while (no if): puede haber más de una línea junta.
        while b'\n' in buffer:
            linea, buffer = buffer.split(b'\n', 1)
            yield linea


def servidor_lineas(puerto):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', puerto))
        srv.listen(5)
        print(f'[lineas] escuchando en :{puerto}')
        while True:
            conn, direccion = srv.accept()
            print(f'[lineas] conexión de {direccion}')
            with conn:
                for linea in recibir_lineas(conn):
                    print(f'[lineas] recibido: {linea!r}')
                    conn.sendall(linea.upper() + b'\n')


# ------------------------------------------------------------------
# Parte C: framing por prefijo de longitud
# ------------------------------------------------------------------

def recibir_exacto(sock, n):
    """Lee exactamente n bytes, o None si el otro lado cerró antes de completar.

    No alcanza con un solo recv(n): recv() puede devolver menos de lo
    pedido aunque el otro lado siga mandando datos. Sin este bucle el
    protocolo se desincroniza para siempre.
    """
    partes = []
    faltan = n
    while faltan > 0:
        pedazo = sock.recv(faltan)
        if not pedazo:
            return None
        partes.append(pedazo)
        faltan -= len(pedazo)
    return b''.join(partes)


def enviar_mensaje(sock, payload: bytes):
    """Manda longitud (4 bytes, orden de red) seguida del contenido."""
    cabecera = struct.pack('!I', len(payload))
    sock.sendall(cabecera + payload)


def recibir_mensaje(sock):
    """Recibe un mensaje con prefijo de longitud. None si cerraron antes."""
    cabecera = recibir_exacto(sock, 4)
    if cabecera is None:
        return None
    (longitud,) = struct.unpack('!I', cabecera)
    return recibir_exacto(sock, longitud)


def servidor_longitud(puerto):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', puerto))
        srv.listen(5)
        print(f'[longitud] escuchando en :{puerto}')
        while True:
            conn, direccion = srv.accept()
            print(f'[longitud] conexión de {direccion}')
            with conn:
                while True:
                    msg = recibir_mensaje(conn)
                    if msg is None:
                        print('[longitud] conexión cerrada')
                        break
                    print(f'[longitud] recibido ({len(msg)} bytes): {msg[:60]!r}')
                    enviar_mensaje(conn, msg.upper())


# ------------------------------------------------------------------
# Demo: probar las dos estrategias contra los dos casos extremos
# (todo junto en un solo sendall, y todo separado byte a byte)
# ------------------------------------------------------------------

def _correr_servidor_lineas(puerto, resultados, listo):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('localhost', puerto))
        srv.listen(1)
        listo.set()
        conn, _ = srv.accept()
        with conn:
            resultados.extend(recibir_lineas(conn))


def _correr_servidor_longitud(puerto, resultados, listo):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('localhost', puerto))
        srv.listen(1)
        listo.set()
        conn, _ = srv.accept()
        with conn:
            while (m := recibir_mensaje(conn)) is not None:
                resultados.append(m)


def demo():
    mensajes = [b'HOLA', b'COMO', b'ESTAS', b'un mensaje mas largo que el resto']

    for modo, correr, enviar_todo in [
        ('lineas', _correr_servidor_lineas,
         lambda s: s.sendall(b''.join(m + b'\n' for m in mensajes))),
        ('longitud', _correr_servidor_longitud,
         lambda s: [enviar_mensaje(s, m) for m in mensajes]),
    ]:
        puerto = 8190 if modo == 'lineas' else 8191
        resultados = []
        listo = threading.Event()
        hilo = threading.Thread(target=correr, args=(puerto, resultados, listo))
        hilo.start()
        listo.wait()
        with socket.create_connection(('localhost', puerto), timeout=5) as s:
            enviar_todo(s)
        hilo.join(timeout=5)
        estado = 'OK' if resultados == mensajes else 'ERROR'
        print(f'--- {modo}: todo en un sendall -> {estado} ---')
        print(f'    enviados:  {mensajes}')
        print(f'    recibidos: {resultados}')


if __name__ == '__main__':
    modo = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    puerto = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    if modo == 'lineas':
        servidor_lineas(puerto)
    elif modo == 'longitud':
        servidor_longitud(puerto)
    else:
        demo()
