"""Las tres tareas, llamadas directamente (sin pool ni API)."""
import asyncio
import hashlib
import time
from concurrent.futures import ProcessPoolExecutor

import httpx
import pytest

from app import config, tareas
from app.tareas import Recursos


def referencia(texto, n):
    """SHA-256 iterado, de corrido: contra esto se compara el de bloques."""
    h = texto.encode()
    for _ in range(n):
        h = hashlib.sha256(h).digest()
    return h.hex()


# --- hashear --------------------------------------------------------------

@pytest.mark.parametrize('modo', ['executor', 'loop'])
@pytest.mark.parametrize('n', [1, 999, 1000, 2007])
async def test_hashear_da_lo_mismo_que_de_corrido(executor, monkeypatch,
                                                   modo, n):
    # Bloques chicos para cruzar varios bordes de bloque con pocas vueltas.
    monkeypatch.setattr(config, 'BLOQUE_HASH', 1000)
    recursos = Recursos(http=None, executor=executor, modo_cpu=modo)
    resultado = await tareas.hashear({'texto': 'hola', 'iteraciones': n},
                                     recursos)
    assert resultado == {'sha256': referencia('hola', n), 'iteraciones': n}


async def _peor_atraso_del_loop(trabajo):
    """Corre `trabajo` mientras un latido intenta despertarse cada 10 ms.
    Devuelve el mayor atraso del latido: si el loop se bloqueó, se nota."""
    atrasos, fin = [], asyncio.Event()

    async def latido():
        while not fin.is_set():
            t0 = time.perf_counter()
            await asyncio.sleep(0.01)
            atrasos.append(time.perf_counter() - t0 - 0.01)

    medidor = asyncio.create_task(latido())
    await asyncio.sleep(0.05)
    await trabajo
    fin.set()
    await medidor
    return max(atrasos)


async def test_hashear_en_executor_no_bloquea_el_loop(executor):
    recursos = Recursos(http=None, executor=executor, modo_cpu='executor')
    trabajo = tareas.hashear({'texto': 'x', 'iteraciones': 400_000}, recursos)
    assert await _peor_atraso_del_loop(trabajo) < 0.1


async def test_hashear_en_el_loop_lo_bloquea(executor):
    """Lo que la medición 2 muestra: sin executor, el loop se congela."""
    recursos = Recursos(http=None, executor=executor, modo_cpu='loop')
    trabajo = tareas.hashear({'texto': 'x', 'iteraciones': 400_000}, recursos)
    assert await _peor_atraso_del_loop(trabajo) > 0.2


async def test_cancelar_hashear_libera_el_proceso_enseguida():
    # Un solo proceso: si siguiera ocupado, el pedido siguiente esperaría.
    with ProcessPoolExecutor(max_workers=1) as ex:
        recursos = Recursos(http=None, executor=ex, modo_cpu='executor')
        largo = asyncio.create_task(tareas.hashear(
            {'texto': 'x', 'iteraciones': 30_000_000}, recursos))   # ~30 s
        await asyncio.sleep(0.3)
        largo.cancel()
        with pytest.raises(asyncio.CancelledError):
            await largo

        t0 = time.perf_counter()
        await asyncio.get_running_loop().run_in_executor(
            ex, tareas._hashear_bloque, b'y', 1)
        # Como mucho espera a que termine UN bloque (~0.1 s), no 30 s.
        assert time.perf_counter() - t0 < 0.5


# --- descargar ------------------------------------------------------------

def _recursos_con_red(manejador, executor=None):
    http = httpx.AsyncClient(transport=httpx.MockTransport(manejador))
    return Recursos(http=http, executor=executor, modo_cpu='executor')


async def test_descargar_es_concurrente_y_reporta_cada_url():
    async def red(request):
        await asyncio.sleep(0.2)
        return httpx.Response(200, content=b'x' * 10)

    recursos = _recursos_con_red(red)
    urls = [f'http://prueba/{i}' for i in range(5)]
    async with recursos.http:
        r = await tareas.descargar({'urls': urls}, recursos)

    assert r['tiempo_total_s'] < 0.4             # en secuencia, 1 s
    assert [d['url'] for d in r['descargas']] == urls   # mismo orden
    for d in r['descargas']:
        assert d['estado_http'] == 200 and d['bytes'] == 10
        assert d['tiempo_s'] >= 0.2


async def test_descargar_un_error_queda_en_su_url():
    async def red(request):
        if request.url.path == '/caida':
            raise httpx.ConnectError('conexión rechazada', request=request)
        if request.url.path == '/falta':
            return httpx.Response(404)
        return httpx.Response(200, content=b'ok')

    recursos = _recursos_con_red(red)
    urls = ['http://p/ok', 'http://p/caida', 'http://p/falta']
    async with recursos.http:
        r = await tareas.descargar({'urls': urls}, recursos)

    ok, caida, falta = r['descargas']
    assert ok['estado_http'] == 200
    assert caida['error'] == 'ConnectError: conexión rechazada'
    assert 'estado_http' not in caida
    assert falta['estado_http'] == 404           # un 404 no es un error de red


async def test_cancelar_descargar_corta_todas_las_descargas():
    cortadas = []

    async def red(request):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cortadas.append(request.url.path)
            raise
        return httpx.Response(200)

    recursos = _recursos_con_red(red)
    async with recursos.http:
        t = asyncio.create_task(tareas.descargar(
            {'urls': [f'http://p/{i}' for i in range(3)]}, recursos))
        await asyncio.sleep(0.1)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t

    assert sorted(cortadas) == ['/0', '/1', '/2']


# --- esperar --------------------------------------------------------------

async def test_esperar_cede_el_loop():
    recursos = Recursos(http=None, executor=None, modo_cpu='executor')
    t0 = time.perf_counter()
    await asyncio.gather(*(tareas.esperar({'segundos': 0.2}, recursos)
                           for _ in range(5)))
    assert time.perf_counter() - t0 < 0.4
