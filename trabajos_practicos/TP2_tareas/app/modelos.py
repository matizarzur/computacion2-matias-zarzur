"""Contrato de la API y registro de una tarea."""
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, HttpUrl, computed_field


class Estado(StrEnum):
    PENDIENTE = 'pendiente'
    EJECUTANDO = 'ejecutando'
    COMPLETADA = 'completada'
    FALLIDA = 'fallida'
    CANCELADA = 'cancelada'


# --- Lo que el cliente manda en POST /tareas ------------------------------

class _PedidoBase(BaseModel):
    timeout: float | None = Field(
        default=None, gt=0,
        description='Segundos máximos de ejecución. Si se omite, se usa el '
                    'timeout por defecto del servicio.')


class PedidoEsperar(_PedidoBase):
    tipo: Literal['esperar']
    segundos: float = Field(gt=0)


class PedidoDescargar(_PedidoBase):
    tipo: Literal['descargar']
    urls: list[HttpUrl] = Field(min_length=1)


class PedidoHashear(_PedidoBase):
    tipo: Literal['hashear']
    texto: str
    iteraciones: int = Field(ge=1)


# El campo 'tipo' decide qué modelo se aplica a cada pedido.
Pedido = Annotated[PedidoEsperar | PedidoDescargar | PedidoHashear,
                   Field(discriminator='tipo')]


# --- Lo que el servicio guarda y devuelve ---------------------------------

def ahora() -> datetime:
    return datetime.now().astimezone()


class Tarea(BaseModel):
    """Registro de una tarea. Solo lo modifica el event loop (ver Almacen)."""
    id: str
    tipo: str
    parametros: dict[str, Any]
    timeout: float
    estado: Estado = Estado.PENDIENTE
    resultado: Any = None
    error: str | None = None
    creada: datetime = Field(default_factory=ahora)
    iniciada: datetime | None = None
    terminada: datetime | None = None

    @computed_field
    @property
    def espera_s(self) -> float | None:
        """Cuánto estuvo en la cola antes de que un worker la tomara."""
        if self.iniciada is None:
            return None
        return (self.iniciada - self.creada).total_seconds()

    @computed_field
    @property
    def duracion_s(self) -> float | None:
        """Cuánto tardó en ejecutarse (sin contar la espera)."""
        if self.iniciada is None or self.terminada is None:
            return None
        return (self.terminada - self.iniciada).total_seconds()

    # Cada transición de estado vive acá, para que no haya dos formas de
    # dejar una tarea "completada" o "cancelada".
    def iniciar(self) -> None:
        self.estado = Estado.EJECUTANDO
        self.iniciada = ahora()

    def completar(self, resultado: Any) -> None:
        self.estado = Estado.COMPLETADA
        self.resultado = resultado
        self.terminada = ahora()

    def fallar(self, motivo: str) -> None:
        self.estado = Estado.FALLIDA
        self.error = motivo
        self.terminada = ahora()

    def cancelar(self, motivo: str | None = None) -> None:
        self.estado = Estado.CANCELADA
        self.error = motivo
        self.terminada = ahora()


class TareaCreada(BaseModel):
    id: str
    estado: Estado
