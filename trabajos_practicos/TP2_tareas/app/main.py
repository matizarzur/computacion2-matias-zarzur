"""API HTTP de la plataforma de tareas distribuidas."""
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request

from . import config
from .almacen import Almacen
from .modelos import Estado, Pedido, Tarea, TareaCreada
from .pool import Pool

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)-7s %(name)s: %(message)s')
log = logging.getLogger('tareas')


@asynccontextmanager
async def ciclo(app: FastAPI):
    """Arranque y apagado: los workers viven mientras viva la aplicación."""
    almacen = Almacen()
    pool = Pool(almacen, config.WORKERS, config.COLA_MAX)
    app.state.almacen = almacen
    app.state.pool = pool
    pool.iniciar()
    yield
    await pool.detener()


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
