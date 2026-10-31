#!/usr/bin/env python3
"""Diagnóstico del techo de la medición 3: qué recurso se agota y por qué.

medir.py muestra DÓNDE se degradan los tiempos; esto junta la evidencia de
POR QUÉ, midiendo mientras corre la carga:

  A. CPU del proceso de la API (/proc/1/stat dentro del contenedor) y
     conexiones TCP abiertas contra el servidor lento (/proc/net/tcp),
     con 800 descargas y con 5000 esperas.
  B. CPU del propio cliente que genera la carga: si está al 100%, lo que se
     mide es el cliente y no el servicio.
  C. Ritmo de alta con 1, 2 y 4 clientes en paralelo.

Uso, desde TP2_tareas/ y con el venv:
    ./venv/bin/python medicion/diagnostico.py
"""
import asyncio
import json
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime

import httpx

if __package__ in (None, ''):              # ejecutado como script
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from medicion.medir import (API, RAIZ, _descargas, _entorno, _esperas,
                            correr_lote, reiniciar_api)

HOLGADO = {'WORKERS': 5000, 'COLA_MAX': 10000}
PUERTO_LENTO_HEX = ':1F41'          # 8001 en hexadecimal, como en /proc/net
ESTABLECIDA = '01'                  # estado TCP_ESTABLISHED en /proc/net/tcp


def _en(servicio: str, comando: str) -> str:
    return subprocess.run(
        ['docker', 'compose', 'exec', '-T', servicio, 'sh', '-c', comando],
        cwd=RAIZ, capture_output=True, text=True, check=True).stdout


def _ticks_api() -> int:
    """utime + stime del PID 1 del contenedor api (solo el proceso
    principal: ahí corren el event loop y las descargas)."""
    campos = _en('api', 'cat /proc/1/stat').rsplit(')', 1)[1].split()
    return int(campos[11]) + int(campos[12])


def _conexiones_a_lento() -> int:
    n = 0
    tabla = _en('lento', 'cat /proc/net/tcp /proc/net/tcp6')
    for linea in tabla.splitlines():
        partes = linea.split()
        if (len(partes) > 3 and partes[1].endswith(PUERTO_LENTO_HEX)
                and partes[3] == ESTABLECIDA):
            n += 1
    return n


def a_recursos_bajo_carga(tck: int) -> list[dict]:
    filas = []
    for nombre, pedidos in (('descargar n=800', _descargas(800)),
                            ('esperar n=5000', _esperas(5000))):
        reiniciar_api(**HOLGADO)
        cpu, conexiones, parar = [], [], threading.Event()

        def sondear():
            t_ant, c_ant = time.monotonic(), _ticks_api()
            while not parar.is_set():
                time.sleep(0.2)
                conexiones.append(_conexiones_a_lento())
                t, c = time.monotonic(), _ticks_api()
                cpu.append(100 * (c - c_ant) / tck / (t - t_ant))
                t_ant, c_ant = t, c

        hilo = threading.Thread(target=sondear)
        hilo.start()
        resumen = asyncio.run(correr_lote(pedidos))
        parar.set()
        hilo.join()
        fila = {'carga': nombre, 'total_s': resumen['total_s'],
                'alta_s': resumen['alta_s'],
                'duracion_media_s': resumen['duracion_media_s'],
                'cpu_api_mediana_pct': statistics.median(cpu),
                'cpu_api_max_pct': max(cpu),
                'conexiones_lento_max': max(conexiones),
                'conexiones_lento_mediana': statistics.median(conexiones)}
        filas.append(fila)
        print(f"  A. {nombre}: CPU API mediana "
              f"{fila['cpu_api_mediana_pct']:.0f}% | conexiones al lento "
              f"máx {fila['conexiones_lento_max']}", flush=True)
    return filas


async def _postear(n: int, en_vuelo: int) -> None:
    limite = asyncio.Semaphore(en_vuelo)
    async with httpx.AsyncClient(base_url=API, timeout=60) as cliente:
        async def uno():
            async with limite:
                r = await cliente.post('/tareas', json={
                    'tipo': 'esperar', 'segundos': 0.01})
                r.raise_for_status()
        await asyncio.gather(*(uno() for _ in range(n)))


def b_cpu_del_cliente(n: int = 2000) -> list[dict]:
    filas = []
    for en_vuelo in (1, 50):
        reiniciar_api(**HOLGADO)
        t0, c0 = time.perf_counter(), time.process_time()
        asyncio.run(_postear(n, en_vuelo))
        dt, dc = time.perf_counter() - t0, time.process_time() - c0
        filas.append({'en_vuelo': en_vuelo, 'post_por_s': n / dt,
                      'cpu_cliente_pct': 100 * dc / dt})
        print(f'  B. {en_vuelo} en vuelo: {n / dt:.0f} POST/s, '
              f'CPU del cliente {100 * dc / dt:.0f}%', flush=True)
    return filas


def c_varios_clientes(tck: int, por_cliente: int = 2000) -> list[dict]:
    filas = []
    for clientes in (1, 2, 4):
        reiniciar_api(**HOLGADO)
        c0, t0 = _ticks_api(), time.perf_counter()
        procesos = [subprocess.Popen(
            [sys.executable, __file__, '--cliente', str(por_cliente)])
            for _ in range(clientes)]
        if any(p.wait() != 0 for p in procesos):
            raise RuntimeError('falló un cliente de carga')
        dt = time.perf_counter() - t0
        cpu = 100 * (_ticks_api() - c0) / tck / dt
        filas.append({'clientes': clientes,
                      'post_por_s': clientes * por_cliente / dt,
                      'cpu_api_pct': cpu})
        print(f'  C. {clientes} cliente(s): '
              f'{clientes * por_cliente / dt:.0f} POST/s, CPU API {cpu:.0f}%',
              flush=True)
    return filas


def main() -> None:
    subprocess.run(['docker', 'compose', 'up', '-d', '--build'], cwd=RAIZ,
                   check=True, capture_output=True)
    reiniciar_api()
    tck = int(_en('api', 'getconf CLK_TCK').strip())
    resultados = {'entorno': _entorno(), 'clk_tck': tck,
                  'a_recursos_bajo_carga': a_recursos_bajo_carga(tck),
                  'b_cpu_del_cliente': b_cpu_del_cliente(),
                  'c_varios_clientes': c_varios_clientes(tck)}
    reiniciar_api()
    destino = RAIZ / 'medicion' / 'resultados'
    destino.mkdir(exist_ok=True)
    archivo = destino / f'diagnostico_{datetime.now():%Y%m%d_%H%M%S}.json'
    archivo.write_text(json.dumps(resultados, indent=2, ensure_ascii=False),
                       encoding='utf-8')
    print(f'\nresultados crudos: {archivo.relative_to(RAIZ)}')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--cliente':
        asyncio.run(_postear(int(sys.argv[2]), en_vuelo=50))  # un cliente C
    else:
        main()
