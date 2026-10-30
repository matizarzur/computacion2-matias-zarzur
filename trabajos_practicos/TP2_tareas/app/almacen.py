"""Estado de las tareas, en memoria.

No hay Lock: todo el acceso ocurre dentro del event loop, que es un solo
hilo y solo cambia de corrutina en un `await`. Ninguno de los métodos de
esta clase hace `await`, así que cada uno es atómico para el resto del
programa.
"""
import uuid
from collections import defaultdict

from .modelos import Estado, Pedido, Tarea, ahora


class Almacen:
    def __init__(self) -> None:
        self._tareas: dict[str, Tarea] = {}

    def crear(self, pedido: Pedido, timeout_defecto: float) -> Tarea:
        id_ = uuid.uuid4().hex[:8]
        while id_ in self._tareas:      # 8 hex: improbable, pero se chequea
            id_ = uuid.uuid4().hex[:8]
        tarea = Tarea(
            id=id_,
            tipo=pedido.tipo,
            parametros=pedido.model_dump(mode='json',
                                         exclude={'tipo', 'timeout'}),
            timeout=pedido.timeout or timeout_defecto,
        )
        self._tareas[id_] = tarea
        return tarea

    def descartar(self, id_: str) -> None:
        """Olvida una tarea que nunca llegó a encolarse."""
        self._tareas.pop(id_, None)

    def obtener(self, id_: str) -> Tarea | None:
        return self._tareas.get(id_)

    def listar(self, estado: Estado | None = None) -> list[Tarea]:
        return [t for t in self._tareas.values()
                if estado is None or t.estado == estado]

    def instantanea(self) -> dict:
        """Todo el estado, listo para json.dumps (ver persistencia.volcar)."""
        return {
            'volcado': ahora().isoformat(),
            'resumen': self.resumen(),
            'tareas': [t.model_dump(mode='json')
                       for t in self._tareas.values()],
        }

    def resumen(self) -> dict:
        """Totales por estado y tiempos promedio de las tareas completadas."""
        por_estado = {e.value: 0 for e in Estado}
        esperas: dict[str, list[float]] = defaultdict(list)
        duraciones: dict[str, list[float]] = defaultdict(list)

        for t in self._tareas.values():
            por_estado[t.estado.value] += 1
            if t.estado == Estado.COMPLETADA:
                esperas[t.tipo].append(t.espera_s)
                duraciones[t.tipo].append(t.duracion_s)

        def promedio(valores: dict[str, list[float]]) -> dict[str, float]:
            return {tipo: round(sum(v) / len(v), 4)
                    for tipo, v in valores.items()}

        return {
            'total': len(self._tareas),
            'por_estado': por_estado,
            'espera_promedio_s': promedio(esperas),
            'duracion_promedio_s': promedio(duraciones),
        }
