"""Volcado del estado al apagar y aviso al arrancar."""
import json
import logging
import os

from app import persistencia
from app.almacen import Almacen
from ayudas import esperar


def _instantanea_con_una_pendiente():
    almacen = Almacen()
    almacen.crear(esperar(1), timeout_defecto=30)
    return almacen.instantanea()


async def test_volcar_escribe_json_valido_sin_temporales(tmp_path):
    ruta = await persistencia.volcar(_instantanea_con_una_pendiente(),
                                     tmp_path)

    assert ruta.parent == tmp_path
    assert ruta.name.startswith('estado_') and ruta.suffix == '.json'
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    assert datos['resumen']['por_estado']['pendiente'] == 1
    assert datos['tareas'][0]['estado'] == 'pendiente'
    assert list(tmp_path.glob('*.tmp')) == []


async def test_volcar_crea_el_directorio_si_no_existe(tmp_path):
    destino = tmp_path / 'no' / 'existe'
    ruta = await persistencia.volcar(_instantanea_con_una_pendiente(), destino)
    assert ruta.exists()


async def test_arranque_sin_volcados(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger='tareas.persistencia'):
        await persistencia.reportar_previo(tmp_path)
    assert 'sin volcados previos' in caplog.text


async def test_arranque_reporta_el_ultimo_volcado(tmp_path, caplog):
    viejo = tmp_path / 'estado_20260101_000000.json'
    viejo.write_text(json.dumps({'resumen': {'total': 99}}))
    await persistencia.volcar(_instantanea_con_una_pendiente(), tmp_path)

    with caplog.at_level(logging.INFO, logger='tareas.persistencia'):
        await persistencia.reportar_previo(tmp_path)

    assert 'estado_20260101' not in caplog.text      # eligió el más nuevo
    assert "con 1 tareas {'pendiente': 1}" in caplog.text
    assert '1 tareas quedaron pendientes sin ejecutarse' in caplog.text


async def test_el_ultimo_es_el_mas_reciente_aunque_su_nombre_ordene_antes(
        tmp_path, caplog):
    # Pasa si cambia la zona horaria (TZ) entre dos volcados: el nuevo,
    # en hora local, tiene un nombre "menor" que el viejo, en UTC.
    viejo = tmp_path / 'estado_20261030_180000.json'
    nuevo = tmp_path / 'estado_20261030_150000.json'
    viejo.write_text(json.dumps({'resumen': {'total': 1}}))
    nuevo.write_text(json.dumps({'resumen': {'total': 2}}))
    os.utime(viejo, (1_000, 1_000))         # escrito antes
    os.utime(nuevo, (2_000, 2_000))         # escrito después

    with caplog.at_level(logging.INFO, logger='tareas.persistencia'):
        await persistencia.reportar_previo(tmp_path)

    assert nuevo.name in caplog.text
    assert viejo.name not in caplog.text


async def test_arranque_con_volcado_corrupto_no_se_cae(tmp_path, caplog):
    (tmp_path / 'estado_29991231_235959.json').write_text('{"cortado')
    with caplog.at_level(logging.INFO, logger='tareas.persistencia'):
        await persistencia.reportar_previo(tmp_path)
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert 'no se pudo leer el último volcado' in caplog.text
