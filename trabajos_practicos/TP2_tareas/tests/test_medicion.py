"""Los cálculos de las mediciones (medicion/medir.py), sin Docker ni red."""
import pytest

from medicion.medir import resumir_latencias, resumir_tareas


def _tarea(estado, creada, iniciada=None, terminada=None,
           espera_s=None, duracion_s=None):
    return {'estado': estado, 'creada': creada, 'iniciada': iniciada,
            'terminada': terminada, 'espera_s': espera_s,
            'duracion_s': duracion_s}


def test_resumir_tareas_mide_del_primer_alta_al_ultimo_fin():
    tareas = [
        _tarea('completada', '2026-10-31T10:00:00.000-03:00',
               '2026-10-31T10:00:00.100-03:00',
               '2026-10-31T10:00:01.100-03:00', 0.1, 1.0),
        _tarea('completada', '2026-10-31T10:00:00.500-03:00',
               '2026-10-31T10:00:01.500-03:00',
               '2026-10-31T10:00:03.000-03:00', 1.0, 1.5),
    ]
    r = resumir_tareas(tareas)
    assert r['n'] == 2
    assert r['por_estado'] == {'completada': 2}
    assert r['total_s'] == pytest.approx(3.0)       # 10:00:00 -> 10:00:03
    assert r['espera_media_s'] == pytest.approx(0.55)
    assert r['espera_max_s'] == pytest.approx(1.0)
    assert r['duracion_media_s'] == pytest.approx(1.25)
    assert r['duracion_max_s'] == pytest.approx(1.5)


def test_resumir_tareas_ignora_las_no_terminadas_en_los_tiempos():
    tareas = [
        _tarea('completada', '2026-10-31T10:00:00-03:00',
               '2026-10-31T10:00:00-03:00', '2026-10-31T10:00:02-03:00',
               0.0, 2.0),
        _tarea('pendiente', '2026-10-31T10:00:01-03:00'),
    ]
    r = resumir_tareas(tareas)
    assert r['por_estado'] == {'completada': 1, 'pendiente': 1}
    assert r['total_s'] == pytest.approx(2.0)
    assert r['duracion_media_s'] == pytest.approx(2.0)


def test_resumir_latencias():
    r = resumir_latencias([10.0, 20.0, 30.0, 40.0, 1000.0])
    assert r == {'n': 5, 'mediana_ms': 30.0, 'max_ms': 1000.0,
                 'p95_ms': pytest.approx(1000.0, rel=0.5)}


def test_resumir_latencias_con_una_sola_muestra():
    assert resumir_latencias([7.0]) == {'n': 1, 'mediana_ms': 7.0,
                                        'max_ms': 7.0, 'p95_ms': 7.0}
