"""Funciones auxiliares de los tests (no son fixtures)."""
import asyncio

from app.modelos import Estado, PedidoEsperar, PedidoHashear

FINALES = {Estado.COMPLETADA, Estado.FALLIDA, Estado.CANCELADA}


def esperar(segundos, **extra):
    return PedidoEsperar(tipo='esperar', segundos=segundos, **extra)


def hashear(texto, iteraciones, **extra):
    return PedidoHashear(tipo='hashear', texto=texto,
                         iteraciones=iteraciones, **extra)


def encolar(almacen, pool, pedido, timeout_defecto=30.0):
    tarea = almacen.crear(pedido, timeout_defecto)
    pool.encolar(tarea.id)
    return tarea


async def hasta(condicion, tope=5.0):
    """Espera (sin bloquear el loop) a que `condicion()` sea verdadera."""
    async with asyncio.timeout(tope):
        while not condicion():
            await asyncio.sleep(0.005)


async def terminar(*tareas, tope=5.0):
    await hasta(lambda: all(t.estado in FINALES for t in tareas), tope)


def tareas_vivas():
    """Las asyncio.Task que siguen existiendo, salvo la del propio test."""
    return {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}
