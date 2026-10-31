"""API HTTP de la plataforma de tareas distribuidas."""
import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request

from . import config, persistencia
from .almacen import Almacen
from .modelos import Estado, Pedido, Tarea, TareaCreada
from .pool import Pool
from .tareas import Recursos

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)-7s %(name)s: %(message)s')
log = logging.getLogger('tareas')


@asynccontextmanager
async def ciclo(app: FastAPI):
    """Arranque y apagado: los workers viven mientras viva la aplicación.

    uvicorn ejecuta el bloque posterior al `yield` cuando recibe SIGTERM o
    SIGINT, después de cerrar el socket: es el lugar del apagado ordenado.
    """
    await persistencia.reportar_previo(config.DIR_ESTADO)
    almacen = Almacen()
    # Un solo cliente HTTP y un solo pool de procesos para toda la vida del
    # servicio: crearlos por tarea sería caro (conexiones, procesos).
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as http:
        executor = ProcessPoolExecutor(max_workers=config.EXECUTOR_WORKERS)
        recursos = Recursos(http, executor, config.MODO_CPU)
        pool = Pool(almacen, recursos, config.WORKERS, config.COLA_MAX)
        app.state.almacen = almacen
        app.state.pool = pool
        log.info('hashear corre en: %s (%d procesos)',
                 config.MODO_CPU, config.EXECUTOR_WORKERS)
        pool.iniciar()
        try:
            yield
        finally:
            await pool.detener(config.APAGADO_ESPERA)
            # shutdown(wait=True) bloquea: se hace en un thread para no
            # congelar el loop mientras termina el bloque en curso.
            await asyncio.to_thread(executor.shutdown, wait=True,
                                    cancel_futures=True)
            # Último paso: todas las tareas ya están en su estado final.
            # Si el disco falla, se avisa y el apagado termina igual: los
            # recursos ya se liberaron y no hay nada más que hacer.
            try:
                ruta = await persistencia.volcar(almacen.instantanea(),
                                                 config.DIR_ESTADO)
            except OSError:
                log.exception('no se pudo volcar el estado en %s',
                              config.DIR_ESTADO)
            else:
                log.info('estado volcado en %s', ruta)


app = FastAPI(title='Plataforma de tareas distribuidas', lifespan=ciclo)


def _tarea_o_404(request: Request, id_: str) -> Tarea:
    tarea = request.app.state.almacen.obtener(id_)
    if tarea is None:
        raise HTTPException(404, f'no existe la tarea {id_}')
    return tarea


@app.post('/tareas', status_code=202)
async def crear_tarea(pedido: Pedido, request: Request) -> TareaCreada:
    almacen: Almacen = request.app.state.almacen
    pool: Pool = request.app.state.pool

    tarea = almacen.crear(pedido, config.TIMEOUT_DEFECTO)
    try:
        pool.encolar(tarea.id)
    except asyncio.QueueFull:
        almacen.descartar(tarea.id)
        raise HTTPException(503, 'la cola está llena, reintentá más tarde')
    return TareaCreada(id=tarea.id, estado=tarea.estado)


@app.get('/tareas')
async def listar_tareas(request: Request,
                        estado: Estado | None = None) -> list[Tarea]:
    return request.app.state.almacen.listar(estado)


@app.get('/tareas/{id_}')
async def ver_tarea(id_: str, request: Request) -> Tarea:
    return _tarea_o_404(request, id_)


@app.delete('/tareas/{id_}')
async def cancelar_tarea(id_: str, request: Request) -> Tarea:
    tarea = _tarea_o_404(request, id_)
    pool: Pool = request.app.state.pool
    if not await pool.cancelar(tarea):
        raise HTTPException(409, f'la tarea ya está {tarea.estado.value}')
    return tarea


@app.get('/estadisticas')
async def estadisticas(request: Request) -> dict:
    pool: Pool = request.app.state.pool
    resumen = request.app.state.almacen.resumen()
    resumen['workers'] = {'total': pool.n_workers, 'ocupados': pool.ocupados}
    resumen['cola'] = {'en_espera': pool.cola.qsize(),
                       'capacidad': pool.cola.maxsize}
    return resumen


if __name__ == '__main__':
    # La guarda es necesaria: ProcessPoolExecutor re-importa este módulo en
    # macOS/Windows (spawn) y sin ella se entraría en un bucle.
    uvicorn.run(app, host=config.HOST, port=config.PORT)
