#!/usr/bin/env python3
"""Las tres mediciones obligatorias del TP2, contra el servicio en Docker.

Para cada escenario levanta la API con la configuración que corresponde y
la recrea antes de cada repetición, así cada corrida arranca sin estado
acumulado. Los tiempos salen de las marcas del propio servidor (`creada` y
`terminada` de cada tarea), no del cronómetro del cliente.

Uso, desde TP2_tareas/ y con el venv (necesita httpx):
    ./venv/bin/python medicion/medir.py              # las tres
    ./venv/bin/python medicion/medir.py --solo 2     # solo una
    ./venv/bin/python medicion/medir.py --reps 1     # más rápido

Los resultados crudos quedan en medicion/resultados/medicion_<fecha>.json
"""
import argparse
import asyncio
import json
import os
import platform
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
API = 'http://127.0.0.1:8000'
LENTO = 'http://lento:8001'         # visto desde el contenedor de la API
FINALES = {'completada', 'fallida', 'cancelada'}

# Vueltas de SHA-256: ~4 s y ~0.5 s en la máquina de desarrollo.
HASH_PESADO = 4_000_000
HASH_MEDIANO = 500_000

# Cuántos POST tiene el cliente en vuelo a la vez. Medido al dar de alta
# 1000 tareas: con un gather de las 1000 juntas el cliente httpx se traba
# en su propio pool de conexiones y baja a 23 POST/s (el servidor, al 17%
# de CPU, quedaba esperando); con 50 en vuelo da 303 POST/s, igual que en
# secuencia (319). Sin este límite se mediría al cliente, no al servicio.
EN_VUELO = 50


# --- cálculos (funciones puras, cubiertas por tests/test_medicion.py) ------

def _instante(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def resumir_tareas(tareas: list[dict]) -> dict:
    """Métricas de un lote, a partir de los registros que da GET /tareas."""
    por_estado: dict[str, int] = {}
    for t in tareas:
        por_estado[t['estado']] = por_estado.get(t['estado'], 0) + 1

    terminadas = [t for t in tareas if t['terminada']]
    esperas = [t['espera_s'] for t in terminadas if t['espera_s'] is not None]
    duraciones = [t['duracion_s'] for t in terminadas
                  if t['duracion_s'] is not None]
    altas = [_instante(t['creada']) for t in tareas]

    total = None
    if terminadas:
        fin = max(_instante(t['terminada']) for t in terminadas)
        total = (fin - min(altas)).total_seconds()

    def media(xs):
        return statistics.fmean(xs) if xs else None

    return {
        'n': len(tareas),
        'por_estado': por_estado,
        'total_s': total,                    # del primer alta al último fin
        'alta_s': (max(altas) - min(altas)).total_seconds() if altas else None,
        'espera_media_s': media(esperas),    # tiempo en la cola
        'espera_max_s': max(esperas, default=None),
        'duracion_media_s': media(duraciones),   # tiempo ejecutándose
        'duracion_max_s': max(duraciones, default=None),
    }


def resumir_latencias(ms: list[float]) -> dict:
    if len(ms) >= 2:
        p95 = statistics.quantiles(ms, n=20, method='inclusive')[-1]
    else:
        p95 = ms[0]
    return {'n': len(ms), 'mediana_ms': statistics.median(ms),
            'max_ms': max(ms), 'p95_ms': p95}


# --- Docker ---------------------------------------------------------------

def _compose(*args: str, env: dict | None = None) -> str:
    resultado = subprocess.run(
        ['docker', 'compose', *args], cwd=RAIZ, check=True,
        capture_output=True, text=True,
        env={**os.environ, **{k: str(v) for k, v in (env or {}).items()}})
    return resultado.stdout


def _esperar_api(tope: float = 30.0) -> None:
    limite = time.monotonic() + tope
    while time.monotonic() < limite:
        try:
            httpx.get(f'{API}/estadisticas', timeout=1).raise_for_status()
            return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError('la API no respondió a tiempo')


def reiniciar_api(**config) -> None:
    """Recrea SOLO el contenedor de la API con esa configuración."""
    _compose('up', '-d', '--force-recreate', '--no-deps', 'api', env=config)
    _esperar_api()


# --- cliente --------------------------------------------------------------

async def _esperar_lote(cliente: httpx.AsyncClient, tope: float) -> None:
    limite = time.monotonic() + tope
    while time.monotonic() < limite:
        e = (await cliente.get('/estadisticas')).json()['por_estado']
        if e['pendiente'] + e['ejecutando'] == 0:
            return
        await asyncio.sleep(0.05)
    raise RuntimeError(f'el lote no terminó en {tope} s')


async def correr_lote(pedidos: list[dict], tope: float = 180.0) -> dict:
    """Manda los pedidos (EN_VUELO a la vez), espera a que terminen y
    resume."""
    limite = asyncio.Semaphore(EN_VUELO)

    async def enviar(cliente, pedido):
        async with limite:
            return await cliente.post('/tareas', json=pedido)

    async with httpx.AsyncClient(base_url=API, timeout=60) as cliente:
        respuestas = await asyncio.gather(
            *(enviar(cliente, p) for p in pedidos), return_exceptions=True)
        await _esperar_lote(cliente, tope)
        tareas = (await cliente.get('/tareas')).json()

    resumen = resumir_tareas(tareas)
    resumen['rechazadas_503'] = sum(
        isinstance(r, httpx.Response) and r.status_code == 503
        for r in respuestas)
    # Un POST que ni siquiera obtuvo respuesta (timeout, conexión) se cuenta
    # en vez de abortar toda la corrida.
    resumen['post_fallidos'] = sum(
        isinstance(r, Exception) for r in respuestas)
    # Una descarga que falla queda como error dentro de su tarea (que sigue
    # "completada"): se cuentan aparte para ver si apareció un techo.
    resumen['descargas_con_error'] = sum(
        'error' in d for t in tareas if t['tipo'] == 'descargar'
        and t['resultado'] for d in t['resultado']['descargas'])
    return resumen


def _descargas(n: int, demora: float = 1) -> list[dict]:
    """n tareas de UNA url cada una."""
    return [{'tipo': 'descargar', 'urls': [f'{LENTO}/demora/{demora}?i={i}']}
            for i in range(n)]


# --- medición 1: concurrencia de I/O --------------------------------------

def medicion_1(reps: int) -> dict:
    una_tarea_20_urls = [{'tipo': 'descargar', 'urls': [
        f'{LENTO}/demora/1?i={i}' for i in range(20)]}]
    escenarios = [
        ('secuencial: 20 tareas, 1 worker', {'WORKERS': 1}, _descargas(20)),
        ('20 tareas, 4 workers (por defecto)', {'WORKERS': 4},
         _descargas(20)),
        ('20 tareas, 20 workers', {'WORKERS': 20}, _descargas(20)),
        ('1 tarea con 20 URLs, 1 worker', {'WORKERS': 1}, una_tarea_20_urls),
    ]
    filas = []
    for nombre, config, pedidos in escenarios:
        corridas = []
        for rep in range(reps):
            reiniciar_api(**config)
            corridas.append(asyncio.run(correr_lote(pedidos)))
            print(f'  [1] {nombre} | rep {rep + 1}: '
                  f'{corridas[-1]["total_s"]:.2f} s', flush=True)
        filas.append({'escenario': nombre, 'config': config,
                      'mediana_total_s': statistics.median(
                          c['total_s'] for c in corridas),
                      'corridas': corridas})
    base = filas[0]['mediana_total_s']
    for f in filas:
        f['speedup'] = base / f['mediana_total_s']
    return {'filas': filas}


# --- medición 2: el event loop bloqueado ----------------------------------

async def _latencias_durante_hash() -> dict:
    async with httpx.AsyncClient(base_url=API, timeout=60) as cliente:
        reposo = []
        for _ in range(20):
            t0 = time.perf_counter()
            await cliente.get('/tareas')
            reposo.append((time.perf_counter() - t0) * 1000)
            await asyncio.sleep(0.05)

        r = await cliente.post('/tareas', json={
            'tipo': 'hashear', 'texto': 'x', 'iteraciones': HASH_PESADO})
        id_ = r.json()['id']
        durante = []
        while True:
            t0 = time.perf_counter()
            respuesta = await cliente.get('/tareas')
            durante.append((time.perf_counter() - t0) * 1000)
            tarea = next(t for t in respuesta.json() if t['id'] == id_)
            if tarea['estado'] in FINALES:
                break
            await asyncio.sleep(0.1)

    return {'reposo': resumir_latencias(reposo),
            'durante': resumir_latencias(durante),
            'hashear_estado': tarea['estado'],
            'hashear_duracion_s': tarea['duracion_s']}


def medicion_2(reps: int) -> dict:
    filas = []
    for modo in ('loop', 'executor'):
        corridas = []
        for rep in range(reps):
            reiniciar_api(MODO_CPU=modo)
            corridas.append(asyncio.run(_latencias_durante_hash()))
            c = corridas[-1]
            print(f'  [2] MODO_CPU={modo} | rep {rep + 1}: GET máx '
                  f'{c["durante"]["max_ms"]:.0f} ms, hash '
                  f'{c["hashear_duracion_s"]:.2f} s', flush=True)
        filas.append({
            'modo': modo,
            'mediana_get_max_ms': statistics.median(
                c['durante']['max_ms'] for c in corridas),
            'mediana_get_mediana_ms': statistics.median(
                c['durante']['mediana_ms'] for c in corridas),
            'mediana_reposo_ms': statistics.median(
                c['reposo']['mediana_ms'] for c in corridas),
            'mediana_hash_s': statistics.median(
                c['hashear_duracion_s'] for c in corridas),
            'corridas': corridas})
    return {'iteraciones': HASH_PESADO, 'filas': filas}


# --- medición 3: el techo del pool ----------------------------------------

def _hashes(n: int) -> list[dict]:
    return [{'tipo': 'hashear', 'texto': f'x{i}',
             'iteraciones': HASH_MEDIANO} for i in range(n)]


def _esperas(n: int) -> list[dict]:
    return [{'tipo': 'esperar', 'segundos': 1} for _ in range(n)]


def medicion_3(reps: int) -> dict:
    # Workers y cola de sobra, para que el límite sea otro: lo que se busca
    # es qué recurso se agota primero según el tipo de tarea.
    holgado = {'WORKERS': 5000, 'COLA_MAX': 10000}
    series = [
        ('hashear (CPU)', _hashes, [1, 2, 3, 4, 6, 8, 12, 16]),
        ('descargar (I/O de red)', _descargas, [50, 100, 200, 400, 800, 1200]),
        ('esperar (I/O sin red)', _esperas, [100, 1000, 5000]),
    ]
    resultado = []
    for nombre, fabrica, ns in series:
        puntos = []
        for n in ns:
            corridas = []
            for rep in range(reps):
                reiniciar_api(**holgado)
                corridas.append(asyncio.run(correr_lote(fabrica(n))))
            med = {k: statistics.median(c[k] for c in corridas)
                   for k in ('total_s', 'alta_s', 'espera_media_s',
                             'duracion_media_s', 'duracion_max_s')}
            for contador in ('descargas_con_error', 'rechazadas_503',
                             'post_fallidos'):
                med[contador] = max(c[contador] for c in corridas)
            puntos.append({'n': n, **med, 'corridas': corridas})
            print(f'  [3] {nombre} n={n}: total {med["total_s"]:.2f} s, '
                  f'alta {med["alta_s"]:.2f} s, '
                  f'duración media {med["duracion_media_s"]:.2f} s, '
                  f'errores {med["descargas_con_error"]}, '
                  f'503 {med["rechazadas_503"]}, '
                  f'POST fallidos {med["post_fallidos"]}', flush=True)
        resultado.append({'serie': nombre, 'puntos': puntos})
    return {'config': holgado, 'series': resultado}


# --- entorno y tablas -----------------------------------------------------

def _entorno() -> dict:
    def leer(ruta, clave):
        try:
            for linea in Path(ruta).read_text().splitlines():
                if linea.startswith(clave):
                    return linea.split(':', 1)[1].strip()
        except OSError:
            return None
    return {
        'fecha': datetime.now().astimezone().isoformat(timespec='seconds'),
        'cpu': leer('/proc/cpuinfo', 'model name') or platform.processor(),
        'cpus_logicas': os.cpu_count(),
        'ram': leer('/proc/meminfo', 'MemTotal'),
        'so': platform.platform(),
        'docker': subprocess.run(['docker', '--version'], text=True,
                                 capture_output=True).stdout.strip(),
        'python_contenedor': _compose('exec', 'api', 'python',
                                      '--version').strip(),
    }


def imprimir_tablas(r: dict) -> None:
    if 'medicion_1' in r:
        print('\n### Medición 1: concurrencia de I/O (20 descargas de 1 s)')
        print('| Escenario | Tiempo (mediana) | Speedup |\n|---|---|---|')
        for f in r['medicion_1']['filas']:
            print(f"| {f['escenario']} | {f['mediana_total_s']:.2f} s "
                  f"| {f['speedup']:.1f}x |")
    if 'medicion_2' in r:
        print('\n### Medición 2: GET /tareas durante un hashear pesado')
        print('| MODO_CPU | GET máx | GET mediana | En reposo | Hash |')
        print('|---|---|---|---|---|')
        for f in r['medicion_2']['filas']:
            print(f"| {f['modo']} | {f['mediana_get_max_ms']:.0f} ms "
                  f"| {f['mediana_get_mediana_ms']:.1f} ms "
                  f"| {f['mediana_reposo_ms']:.1f} ms "
                  f"| {f['mediana_hash_s']:.2f} s |")
    if 'medicion_3' in r:
        print('\n### Medición 3: techo del pool')
        for s in r['medicion_3']['series']:
            print(f"\n**{s['serie']}**\n")
            print('| N | Total | Alta de N | Espera media | Duración media '
                  '| Duración máx | Errores |')
            print('|---|---|---|---|---|---|---|')
            for p in s['puntos']:
                print(f"| {p['n']} | {p['total_s']:.2f} s "
                      f"| {p['alta_s']:.2f} s "
                      f"| {p['espera_media_s']:.3f} s "
                      f"| {p['duracion_media_s']:.2f} s "
                      f"| {p['duracion_max_s']:.2f} s "
                      f"| {p['descargas_con_error']} |")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--solo', type=int, choices=(1, 2, 3),
                        help='correr una sola medición')
    parser.add_argument('--reps', type=int, default=3,
                        help='repeticiones por escenario (por defecto 3)')
    args = parser.parse_args()

    print('levantando docker compose...', flush=True)
    _compose('up', '-d', '--build')
    _esperar_api()
    resultados = {'entorno': _entorno(), 'reps': args.reps,
                  'en_vuelo': EN_VUELO}
    print(json.dumps(resultados['entorno'], indent=2, ensure_ascii=False))

    destino = RAIZ / 'medicion' / 'resultados'
    destino.mkdir(exist_ok=True)
    archivo = destino / f'medicion_{datetime.now():%Y%m%d_%H%M%S}.json'

    def guardar():
        archivo.write_text(json.dumps(resultados, indent=2,
                                      ensure_ascii=False), encoding='utf-8')

    for numero, medir in ((1, medicion_1), (2, medicion_2), (3, medicion_3)):
        if args.solo in (None, numero):
            print(f'\n== medición {numero} ==', flush=True)
            resultados[f'medicion_{numero}'] = medir(args.reps)
            guardar()                # tras cada una: un fallo no pierde todo

    reiniciar_api()                  # dejar la API con la config por defecto
    imprimir_tablas(resultados)
    print(f'\nresultados crudos: {archivo.relative_to(RAIZ)}')


if __name__ == '__main__':
    main()
