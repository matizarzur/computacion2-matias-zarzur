"""Persistencia mínima: volcado del estado al apagar y aviso al arrancar.

El estado vive en memoria; esto solo deja constancia en disco de cómo quedó
cada tarea cuando se apagó el servicio. No se recarga al arrancar.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger('tareas.persistencia')

PATRON = 'estado_*.json'


def _escribir_atomico(ruta: Path, texto: str) -> None:
    """Escribe a un temporal y lo renombra: si el proceso muere a mitad,
    no queda un JSON cortado con el nombre definitivo."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix('.json.tmp')
    temporal.write_text(texto, encoding='utf-8')
    os.replace(temporal, ruta)


async def volcar(instantanea: dict, directorio: Path) -> Path:
    """Escribe estado_<timestamp>.json. Recibe los datos ya serializados en
    el loop; solo la escritura a disco (bloqueante) va a un thread."""
    nombre = f'estado_{datetime.now():%Y%m%d_%H%M%S}.json'
    ruta = directorio / nombre
    texto = json.dumps(instantanea, ensure_ascii=False, indent=2)
    await asyncio.to_thread(_escribir_atomico, ruta, texto)
    return ruta


def _leer_ultimo(directorio: Path) -> tuple[Path, dict] | None:
    volcados = list(directorio.glob(PATRON))
    if not volcados:
        return None
    # Por fecha de modificación y no por nombre: el nombre lleva la hora
    # local, y si cambia la zona horaria (TZ) deja de ordenar en el tiempo.
    ultimo = max(volcados, key=lambda ruta: ruta.stat().st_mtime)
    return ultimo, json.loads(ultimo.read_text(encoding='utf-8'))


async def reportar_previo(directorio: Path) -> None:
    """Al arrancar: si hay un volcado anterior, lo informa por log."""
    try:
        encontrado = await asyncio.to_thread(_leer_ultimo, directorio)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning('no se pudo leer el último volcado: %s', exc)
        return
    if encontrado is None:
        log.info('sin volcados previos en %s', directorio)
        return

    ruta, datos = encontrado
    resumen = datos.get('resumen', {})
    por_estado = {e: n for e, n in resumen.get('por_estado', {}).items() if n}
    log.info('volcado previo: %s (del %s) con %s tareas %s',
             ruta.name, datos.get('volcado', '?'),
             resumen.get('total', '?'), por_estado)
    sin_ejecutar = por_estado.get('pendiente', 0)
    if sin_ejecutar:
        log.info('%d tareas quedaron pendientes sin ejecutarse '
                 '(no se re-encolan: el estado no se recarga)', sin_ejecutar)
