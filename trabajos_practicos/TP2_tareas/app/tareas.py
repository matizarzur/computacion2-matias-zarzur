"""Lo que hace cada tipo de tarea.

Cada función recibe los parámetros (un dict) y los recursos compartidos del
servicio, y devuelve el resultado, que tiene que poder serializarse a JSON.
"""
import asyncio
import hashlib
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import httpx

from . import config


@dataclass
class Recursos:
    """Lo que las tareas comparten; se crea una vez al arrancar el servicio."""
    http: httpx.AsyncClient            # un solo cliente: reutiliza conexiones
    executor: ProcessPoolExecutor      # procesos para el trabajo CPU-bound
    modo_cpu: str                      # 'executor' o 'loop' (ver config)


async def esperar(parametros: dict, recursos: Recursos) -> dict:
    """I/O simulado: cede el control al loop mientras 'espera'."""
    segundos = parametros['segundos']
    await asyncio.sleep(segundos)
    return {'esperado_s': segundos}


async def _bajar(cliente: httpx.AsyncClient, url: str) -> dict:
    """Descarga una URL. Si falla, el error queda en SU resultado y no
    arrastra a las demás descargas de la misma tarea."""
    t0 = time.perf_counter()
    try:
        respuesta = await cliente.get(url)
    except httpx.HTTPError as exc:
        detalle = f': {exc}' if str(exc) else ''
        return {'url': url,
                'error': f'{type(exc).__name__}{detalle}',
                'tiempo_s': round(time.perf_counter() - t0, 4)}
    return {'url': url,
            'estado_http': respuesta.status_code,
            'bytes': len(respuesta.content),
            'tiempo_s': round(time.perf_counter() - t0, 4)}


async def descargar(parametros: dict, recursos: Recursos) -> dict:
    """I/O-bound: todas las URLs a la vez, en el mismo hilo."""
    t0 = time.perf_counter()
    # TaskGroup: si cancelan la tarea, cancela y espera a todas las
    # descargas hijas; ninguna queda corriendo suelta.
    async with asyncio.TaskGroup() as grupo:
        descargas = [grupo.create_task(_bajar(recursos.http, url))
                     for url in parametros['urls']]
    return {'tiempo_total_s': round(time.perf_counter() - t0, 4),
            'descargas': [d.result() for d in descargas]}


def _hashear_bloque(h: bytes, vueltas: int) -> bytes:
    """Trabajo CPU-bound puro. Corre en otro proceso (o, en MODO_CPU=loop,
    dentro del event loop). Va a nivel de módulo para poder enviarse a un
    proceso hijo."""
    for _ in range(vueltas):
        h = hashlib.sha256(h).digest()
    return h


async def hashear(parametros: dict, recursos: Recursos) -> dict:
    """CPU-bound: SHA-256 aplicado N veces sobre el texto."""
    h = parametros['texto'].encode()
    restantes = parametros['iteraciones']

    if recursos.modo_cpu == 'loop':
        # A propósito mal: sin ningún await, el event loop queda congelado
        # todo el cálculo y la tarea ni siquiera se puede cancelar.
        h = _hashear_bloque(h, restantes)
    else:
        loop = asyncio.get_running_loop()
        while restantes:
            vueltas = min(restantes, config.BLOQUE_HASH)
            # Entre bloque y bloque hay un await: ahí llega el CancelledError.
            h = await loop.run_in_executor(
                recursos.executor, _hashear_bloque, h, vueltas)
            restantes -= vueltas

    return {'sha256': h.hex(), 'iteraciones': parametros['iteraciones']}


EJECUTORES = {
    'esperar': esperar,
    'descargar': descargar,
    'hashear': hashear,
}
