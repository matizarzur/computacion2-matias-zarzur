"""Lo que hace cada tipo de tarea.

Cada función recibe los parámetros (un dict) y devuelve el resultado, que
tiene que poder serializarse a JSON.
"""
import asyncio


async def esperar(parametros: dict) -> dict:
    """I/O simulado: cede el control al loop mientras 'espera'."""
    segundos = parametros['segundos']
    await asyncio.sleep(segundos)
    return {'esperado_s': segundos}


async def descargar(parametros: dict) -> dict:
    raise NotImplementedError('la tarea "descargar" todavía no está implementada')


async def hashear(parametros: dict) -> dict:
    raise NotImplementedError('la tarea "hashear" todavía no está implementada')


EJECUTORES = {
    'esperar': esperar,
    'descargar': descargar,
    'hashear': hashear,
}
