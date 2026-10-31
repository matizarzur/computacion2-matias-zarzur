"""La API HTTP con el ciclo de vida real (workers, pool de procesos, volcado).

Se habla con la aplicación por httpx.ASGITransport: sin sockets, pero con
el mismo FastAPI, el mismo lifespan y los mismos workers que en producción.
"""
import asyncio
import json
import logging
import time

import httpx
import pytest

from app import config
from app.main import app, ciclo
from ayudas import hasta

FINALES = {'completada', 'fallida', 'cancelada'}


@pytest.fixture
async def api(tmp_path, monkeypatch):
    for nombre, valor in {'WORKERS': 2, 'COLA_MAX': 3,
                          'EXECUTOR_WORKERS': 1, 'APAGADO_ESPERA': 0.5,
                          'DIR_ESTADO': tmp_path}.items():
        monkeypatch.setattr(config, nombre, valor)
    async with ciclo(app):
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte,
                                     base_url='http://test') as cliente:
            yield cliente


async def _crear(api, **pedido):
    r = await api.post('/tareas', json=pedido)
    assert r.status_code == 202, r.text
    return r.json()['id']


async def _hasta_estado(api, id_, estados, tope=5.0):
    async with asyncio.timeout(tope):
        while True:
            tarea = (await api.get(f'/tareas/{id_}')).json()
            if tarea['estado'] in estados:
                return tarea
            await asyncio.sleep(0.01)


async def test_post_responde_al_instante_y_la_tarea_avanza(api):
    t0 = time.perf_counter()
    r = await api.post('/tareas', json={'tipo': 'esperar', 'segundos': 0.2})
    assert time.perf_counter() - t0 < 0.1        # no espera a la tarea
    assert r.status_code == 202
    assert r.json()['estado'] == 'pendiente'

    tarea = await _hasta_estado(api, r.json()['id'], FINALES)
    assert tarea['estado'] == 'completada'
    assert tarea['resultado'] == {'esperado_s': 0.2}


async def test_hashear_por_la_api(api):
    id_ = await _crear(api, tipo='hashear', texto='hola', iteraciones=3)
    tarea = await _hasta_estado(api, id_, FINALES)
    assert tarea['estado'] == 'completada'
    assert tarea['resultado']['iteraciones'] == 3


@pytest.mark.parametrize('pedido', [
    {'tipo': 'esperar', 'segundos': -1},
    {'tipo': 'esperar'},
    {'tipo': 'volar'},
    {'tipo': 'descargar', 'urls': []},
    {'tipo': 'descargar', 'urls': ['no es una url']},
    {'tipo': 'hashear', 'texto': 'x', 'iteraciones': 0},
    {'tipo': 'esperar', 'segundos': 1, 'timeout': 0},
])
async def test_pedidos_invalidos_dan_422(api, pedido):
    r = await api.post('/tareas', json=pedido)
    assert r.status_code == 422


async def test_tarea_inexistente_da_404(api):
    assert (await api.get('/tareas/noexiste')).status_code == 404
    assert (await api.delete('/tareas/noexiste')).status_code == 404


async def test_delete_cancela_y_un_segundo_delete_da_409(api):
    id_ = await _crear(api, tipo='esperar', segundos=5)
    await _hasta_estado(api, id_, {'ejecutando'})

    r = await api.delete(f'/tareas/{id_}')
    assert r.status_code == 200
    assert r.json()['estado'] == 'cancelada'

    r = await api.delete(f'/tareas/{id_}')
    assert r.status_code == 409


async def test_cola_llena_da_503(api):
    # 2 workers ocupados + 3 lugares en la cola = 5 aceptadas; la 6ta no.
    for _ in range(2):
        await _crear(api, tipo='esperar', segundos=5)
    await hasta(lambda: app.state.pool.ocupados == 2)
    for _ in range(3):
        await _crear(api, tipo='esperar', segundos=5)

    r = await api.post('/tareas', json={'tipo': 'esperar', 'segundos': 5})
    assert r.status_code == 503
    assert len((await api.get('/tareas')).json()) == 5   # la 6ta no quedó


async def test_filtro_por_estado(api):
    id_ = await _crear(api, tipo='esperar', segundos=0.01)
    await _hasta_estado(api, id_, FINALES)
    await _crear(api, tipo='esperar', segundos=5)

    completadas = (await api.get('/tareas?estado=completada')).json()
    assert [t['id'] for t in completadas] == [id_]
    assert (await api.get('/tareas?estado=raro')).status_code == 422


async def test_estadisticas(api):
    id_ = await _crear(api, tipo='esperar', segundos=0.01)
    await _hasta_estado(api, id_, FINALES)
    await _crear(api, tipo='esperar', segundos=5)
    await hasta(lambda: app.state.pool.ocupados == 1)

    e = (await api.get('/estadisticas')).json()
    assert e['total'] == 2
    assert e['por_estado']['completada'] == 1
    assert e['por_estado']['ejecutando'] == 1
    assert e['workers'] == {'total': 2, 'ocupados': 1}
    assert e['cola'] == {'en_espera': 0, 'capacidad': 3}
    assert 'esperar' in e['duracion_promedio_s']


async def test_apagar_la_aplicacion_vuelca_el_estado(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DIR_ESTADO', tmp_path)
    monkeypatch.setattr(config, 'APAGADO_ESPERA', 0.2)
    async with ciclo(app):
        transporte = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transporte,
                                     base_url='http://test') as api:
            id_ = await _crear(api, tipo='esperar', segundos=5)
            await _hasta_estado(api, id_, {'ejecutando'})
    # Al salir del `async with ciclo(app)` corrió el apagado ordenado.

    volcados = list(tmp_path.glob('estado_*.json'))
    assert len(volcados) == 1
    tareas = json.loads(volcados[0].read_text())['tareas']
    assert tareas[0]['id'] == id_
    assert tareas[0]['estado'] == 'cancelada'
    assert tareas[0]['error'] == 'apagado del servicio'


async def test_si_el_volcado_falla_el_apagado_termina_igual(
        tmp_path, monkeypatch, caplog):
    # DIR_ESTADO apunta a un archivo: crear el directorio va a fallar,
    # como pasaría sin permisos de escritura o con el disco lleno.
    no_es_directorio = tmp_path / 'archivo'
    no_es_directorio.write_text('x')
    monkeypatch.setattr(config, 'DIR_ESTADO', no_es_directorio)

    with caplog.at_level(logging.ERROR, logger='tareas'):
        async with ciclo(app):
            pass                    # el apagado no debe lanzar excepción

    assert 'no se pudo volcar el estado' in caplog.text
