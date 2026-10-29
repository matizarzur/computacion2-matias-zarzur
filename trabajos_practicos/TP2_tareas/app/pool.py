"""Cola de tareas y pool de workers.

Cada worker es una corrutina que consume ids de una asyncio.Queue. El
trabajo de cada tarea corre en una Task propia (la "tarea interna"): así
cancelar una tarea no es lo mismo que cancelar al worker que la atiende.
"""
import asyncio
import logging

from .almacen import Almacen
from .modelos import Estado, Tarea
from .tareas import EJECUTORES, Recursos

log = logging.getLogger('tareas.pool')


class Pool:
    def __init__(self, almacen: Almacen, recursos: Recursos,
                 n_workers: int, cola_max: int):
        self._almacen = almacen
        self._recursos = recursos
        self._n_workers = n_workers
        self.cola: asyncio.Queue[str] = asyncio.Queue(maxsize=cola_max)
        self._workers: list[asyncio.Task] = []
        self._en_curso: dict[str, asyncio.Task] = {}   # id -> tarea interna

    @property
    def ocupados(self) -> int:
        return len(self._en_curso)

    @property
    def n_workers(self) -> int:
        return self._n_workers

    def iniciar(self) -> None:
        self._workers = [
            asyncio.create_task(self._worker(n), name=f'worker-{n}')
            for n in range(self._n_workers)
        ]
        log.info('%d workers iniciados (cola de hasta %d)',
                 self._n_workers, self.cola.maxsize)

    def encolar(self, id_: str) -> None:
        """Pone una tarea en la cola SIN esperar. Lanza QueueFull si no hay
        lugar: el endpoint decide qué responder, nunca se queda bloqueado."""
        self.cola.put_nowait(id_)

    async def cancelar(self, tarea: Tarea) -> bool:
        """Cancela una tarea pendiente o en ejecución.

        Devuelve False si no había nada que cancelar (ya había terminado).
        """
        if tarea.estado == Estado.PENDIENTE:
            # La cola no permite sacar un elemento del medio: se marca y el
            # worker la descarta cuando le toque.
            tarea.cancelar()
            return True

        if tarea.estado == Estado.EJECUTANDO:
            interna = self._en_curso[tarea.id]
            interna.cancel()
            await asyncio.wait({interna})   # no volver hasta que termine
            return tarea.estado == Estado.CANCELADA

        return False

    async def detener(self) -> None:
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        log.info('workers detenidos')

    # --- internos ---------------------------------------------------------

    async def _worker(self, n: int) -> None:
        while True:
            id_ = await self.cola.get()
            try:
                await self._atender(id_)
            except Exception:
                # Un fallo inesperado no debe matar al worker.
                log.exception('worker-%d: error atendiendo %s', n, id_)
            finally:
                self.cola.task_done()   # siempre, o join() esperaría de más

    async def _atender(self, id_: str) -> None:
        tarea = self._almacen.obtener(id_)
        if tarea is None or tarea.estado != Estado.PENDIENTE:
            return                      # la cancelaron mientras esperaba

        tarea.iniciar()
        # Entre iniciar() y registrar la tarea interna no hay ningún await:
        # ningún DELETE puede ver "ejecutando" sin encontrarla en _en_curso.
        interna = asyncio.create_task(self._correr(tarea),
                                      name=f'tarea-{tarea.id}')
        self._en_curso[tarea.id] = interna
        try:
            # asyncio.wait no relanza lo que le pase a `interna` (ni su
            # cancelación): lo único que puede lanzar acá es CancelledError
            # del PROPIO worker, o sea, el apagado del servicio.
            await asyncio.wait({interna})
        except asyncio.CancelledError:
            interna.cancel()            # el trabajo se va con el worker...
            await asyncio.wait({interna})   # ...y no queda huérfano
            raise
        finally:
            del self._en_curso[tarea.id]

    async def _correr(self, tarea: Tarea) -> None:
        """El trabajo en sí, con su timeout. Deja la tarea en un estado final."""
        limite = asyncio.timeout(tarea.timeout)
        try:
            async with limite:
                resultado = await EJECUTORES[tarea.tipo](tarea.parametros,
                                                         self._recursos)
        except asyncio.CancelledError:
            tarea.cancelar()
            log.info('%s cancelada', tarea.id)
            raise
        except TimeoutError as exc:
            # Puede ser nuestro límite o un TimeoutError que viene de adentro.
            if limite.expired():
                tarea.fallar(f'timeout: superó el límite de {tarea.timeout} s')
            else:
                tarea.fallar(f'TimeoutError: {exc}')
            log.info('%s fallida: %s', tarea.id, tarea.error)
        except Exception as exc:
            tarea.fallar(f'{type(exc).__name__}: {exc}')
            log.info('%s fallida: %s', tarea.id, tarea.error)
        else:
            tarea.completar(resultado)
            log.info('%s completada en %.3f s', tarea.id, tarea.duracion_s)
