"""Cola, workers, cancelación, timeouts y apagado ordenado."""
import asyncio
import time

import pytest

from app import tareas
from app.modelos import Estado
from ayudas import encolar, esperar, hasta, tareas_vivas, terminar


async def test_una_tarea_pasa_por_todos_sus_estados(crear_pool):
    almacen, pool = await crear_pool()
    t = encolar(almacen, pool, esperar(0.1))
    assert t.estado == Estado.PENDIENTE

    await hasta(lambda: t.estado == Estado.EJECUTANDO)
    await terminar(t)

    assert t.estado == Estado.COMPLETADA
    assert t.resultado == {'esperado_s': 0.1}
    assert 0.1 <= t.duracion_s < 0.3


async def test_los_workers_ejecutan_a_la_vez(crear_pool):
    almacen, pool = await crear_pool(n_workers=4)
    t0 = time.perf_counter()
    ts = [encolar(almacen, pool, esperar(0.3)) for _ in range(4)]
    await terminar(*ts)
    # En secuencia serían 1.2 s; concurrentes, lo que tarda una.
    assert time.perf_counter() - t0 < 0.6


async def test_no_hay_mas_tareas_a_la_vez_que_workers(crear_pool):
    almacen, pool = await crear_pool(n_workers=2)
    t0 = time.perf_counter()
    ts = [encolar(almacen, pool, esperar(0.2)) for _ in range(4)]
    await hasta(lambda: pool.ocupados == 2)
    assert sum(t.estado == Estado.PENDIENTE for t in ts) == 2
    await terminar(*ts)
    assert time.perf_counter() - t0 >= 0.4      # dos tandas de 0.2 s


async def test_cola_llena_lanza_queuefull_sin_esperar(crear_pool):
    almacen, pool = await crear_pool(n_workers=1, cola_max=1)
    # Sin ningún await en el medio, el worker todavía no sacó la primera.
    encolar(almacen, pool, esperar(0.1))
    with pytest.raises(asyncio.QueueFull):
        encolar(almacen, pool, esperar(0.1))


async def test_cancelar_pendiente_no_llega_a_ejecutarse(crear_pool):
    almacen, pool = await crear_pool(n_workers=1)
    ocupa = encolar(almacen, pool, esperar(5))
    espera = encolar(almacen, pool, esperar(0.1))
    await hasta(lambda: ocupa.estado == Estado.EJECUTANDO)

    assert await pool.cancelar(espera) is True
    assert espera.estado == Estado.CANCELADA

    await pool.cancelar(ocupa)                  # libera al único worker...
    await hasta(lambda: pool.cola.qsize() == 0)
    await asyncio.sleep(0.05)
    assert espera.iniciada is None      # ...que la descartó sin correrla


async def test_cancelar_en_ejecucion_libera_al_worker(crear_pool):
    almacen, pool = await crear_pool(n_workers=1)
    larga = encolar(almacen, pool, esperar(5))
    await hasta(lambda: larga.estado == Estado.EJECUTANDO)

    t0 = time.perf_counter()
    assert await pool.cancelar(larga) is True
    assert time.perf_counter() - t0 < 0.1
    assert larga.estado == Estado.CANCELADA
    assert larga.error is None          # la canceló un DELETE, no el apagado
    assert pool.ocupados == 0

    siguiente = encolar(almacen, pool, esperar(0.05))
    await terminar(siguiente)
    assert siguiente.estado == Estado.COMPLETADA


async def test_cancelar_terminada_devuelve_false(crear_pool):
    almacen, pool = await crear_pool()
    t = encolar(almacen, pool, esperar(0.01))
    await terminar(t)
    assert await pool.cancelar(t) is False
    assert t.estado == Estado.COMPLETADA


async def test_timeout_deja_la_tarea_fallida_con_motivo(crear_pool):
    almacen, pool = await crear_pool()
    t = encolar(almacen, pool, esperar(5, timeout=0.2))
    await terminar(t)
    assert t.estado == Estado.FALLIDA
    assert t.error.startswith('timeout: superó el límite de 0.2 s')
    assert t.duracion_s < 0.4


async def test_timeouterror_de_adentro_no_se_confunde_con_el_nuestro(
        crear_pool, monkeypatch):
    async def falla(parametros, recursos):
        raise TimeoutError('el servidor no respondió')
    monkeypatch.setitem(tareas.EJECUTORES, 'esperar', falla)

    almacen, pool = await crear_pool()
    t = encolar(almacen, pool, esperar(1))
    await terminar(t)
    assert t.estado == Estado.FALLIDA
    assert t.error == 'TimeoutError: el servidor no respondió'


async def test_una_excepcion_no_mata_al_worker(crear_pool, monkeypatch):
    original = tareas.EJECUTORES['esperar']

    async def a_veces_falla(parametros, recursos):
        if parametros['segundos'] == 0.01:
            raise ValueError('roto')
        return await original(parametros, recursos)
    monkeypatch.setitem(tareas.EJECUTORES, 'esperar', a_veces_falla)

    almacen, pool = await crear_pool(n_workers=1)   # un solo worker
    rota = encolar(almacen, pool, esperar(0.01))
    sana = encolar(almacen, pool, esperar(0.02))
    await terminar(rota, sana)

    assert rota.estado == Estado.FALLIDA
    assert rota.error == 'ValueError: roto'
    assert sana.estado == Estado.COMPLETADA     # el mismo worker siguió


async def test_no_quedan_tareas_huerfanas(crear_pool):
    antes = tareas_vivas()
    almacen, pool = await crear_pool(n_workers=2)
    cancelada = encolar(almacen, pool, esperar(5))
    vencida = encolar(almacen, pool, esperar(5, timeout=0.1))
    corriendo = encolar(almacen, pool, esperar(5))
    await hasta(lambda: cancelada.estado == Estado.EJECUTANDO)
    await pool.cancelar(cancelada)
    await terminar(vencida)
    await hasta(lambda: corriendo.estado == Estado.EJECUTANDO)

    await pool.detener(0)

    assert tareas_vivas() == antes
    assert corriendo.estado == Estado.CANCELADA


async def test_apagado_ordenado(crear_pool):
    almacen, pool = await crear_pool(n_workers=2)
    corta = encolar(almacen, pool, esperar(0.2))
    larga = encolar(almacen, pool, esperar(5))
    en_cola = encolar(almacen, pool, esperar(0.01))
    await hasta(lambda: pool.ocupados == 2)

    t0 = time.perf_counter()
    await pool.detener(espera=0.5)

    assert 0.5 <= time.perf_counter() - t0 < 1.0
    assert corta.estado == Estado.COMPLETADA     # terminó dentro de la espera
    assert larga.estado == Estado.CANCELADA      # no llegó: se cancela
    assert larga.error == 'apagado del servicio'
    assert en_cola.estado == Estado.PENDIENTE    # no se arranca nada nuevo,
    assert en_cola.iniciada is None              # aunque se libere un worker
