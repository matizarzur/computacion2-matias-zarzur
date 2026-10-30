"""Fixtures compartidas.

Los tests no usan la red real: el cliente HTTP de las tareas lleva un
httpx.MockTransport, cuyo manejador decide qué responde y cuánto tarda.
"""
from concurrent.futures import ProcessPoolExecutor

import httpx
import pytest

from app.almacen import Almacen
from app.pool import Pool
from app.tareas import Recursos


async def _red_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b'ok')


@pytest.fixture(scope='session')
def executor():
    """Un pool de procesos para toda la sesión: arrancarlo cuesta."""
    with ProcessPoolExecutor(max_workers=2) as ex:
        yield ex


@pytest.fixture
async def crear_pool(executor):
    """Fábrica de pools ya iniciados. Al terminar el test los detiene."""
    creados = []

    async def _crear(n_workers=2, cola_max=10, red=_red_ok,
                     modo_cpu='executor', ex=None):
        http = httpx.AsyncClient(transport=httpx.MockTransport(red))
        almacen = Almacen()
        pool = Pool(almacen, Recursos(http, ex or executor, modo_cpu),
                    n_workers, cola_max)
        pool.iniciar()
        creados.append((pool, http))
        return almacen, pool

    yield _crear
    for pool, http in creados:
        await pool.detener(0)
        await http.aclose()
