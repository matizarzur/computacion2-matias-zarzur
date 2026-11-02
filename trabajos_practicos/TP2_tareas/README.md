# Plataforma de Tareas Distribuidas

**Trabajo Práctico Nº 2 — Computación II — Universidad de Mendoza — 2026**

Autor: Matías Zarzur

---

## 1. Descripción general

Una plataforma de tareas distribuidas: un servicio al que se le encargan
trabajos por HTTP, que los ejecuta de forma concurrente y permite consultar su
estado y su resultado, o cancelarlos.

La API (FastAPI sobre uvicorn) responde a cada `POST` en el acto con un `id`, y
deja la tarea en una `asyncio.Queue`. Un pool de workers, que son corrutinas y
no threads, la toma de la cola y la ejecuta. Todo eso ocurre en **un solo
proceso con un solo hilo**: mientras una tarea espera la red, el event loop
atiende a las demás. Lo único que sale de ese hilo es el cálculo de CPU, que
va a un `ProcessPoolExecutor`. Al apagarse con `SIGTERM` o `SIGINT`, el
servicio deja de tomar tareas, espera con un límite a las que están en curso y
vuelca el estado a `estado_<fecha>.json`.

Hay tres tipos de tarea, porque cada uno ejercita algo distinto:

| Tarea | Naturaleza | Qué hace | Qué ejercita |
|---|---|---|---|
| `descargar` | I/O de red | Descarga una lista de URLs **a la vez** y devuelve, por cada una, el código HTTP, el tamaño y el tiempo | Concurrencia real en un solo hilo |
| `hashear` | CPU | Aplica SHA-256 N veces sobre un texto | Que asyncio **no** sirve para esto: va a otro proceso |
| `esperar` | I/O simulado | Duerme N segundos | Cancelación, timeouts y estados en vivo |

Además de lo obligatorio, el proyecto tiene **53 tests con
`pytest-asyncio`**, con foco en la cancelación (extensión opcional 6).

### Uso rápido

Desde esta carpeta (`trabajos_practicos/TP2_tareas/`):

```bash
docker compose up --build
```

Eso levanta dos servicios: `api`, en `http://localhost:8000`, y `lento`, un
servidor de prueba que responde con la demora que se le pida y que sirve de
destino para las descargas. La documentación interactiva de la API queda en
`http://localhost:8000/docs`.

Desde otra terminal, crear una tarea. La respuesta llega en el acto, con el
`id` y el estado inicial:

```bash
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
     -d '{"tipo": "esperar", "segundos": 5}'
```

```json
{"id":"0496ccc8","estado":"pendiente"}
```

Consultarla con ese `id`: primero va a estar `ejecutando` y a los 5 segundos,
`completada`.

```bash
curl -s localhost:8000/tareas/0496ccc8
```

Los otros dos tipos. Desde la API, el servidor de prueba se llama por su
nombre de servicio, `lento`:

```bash
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
     -d '{"tipo": "descargar", "urls": ["http://lento:8001/demora/1", "http://lento:8001/demora/1", "http://lento:8001/demora/1"]}'

curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
     -d '{"tipo": "hashear", "texto": "hola", "iteraciones": 1000000}'
```

Las tres descargas de 1 segundo terminan en ~1 segundo, no en 3.

Una tarea larga, cancelada mientras corre:

```bash
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
     -d '{"tipo": "esperar", "segundos": 60}'
curl -s -X DELETE localhost:8000/tareas/<id>
```

Con un timeout propio, más corto que la tarea. Queda `fallida`, con el motivo:

```bash
curl -s -X POST localhost:8000/tareas -H 'Content-Type: application/json' \
     -d '{"tipo": "esperar", "segundos": 10, "timeout": 1}'
```

Listar (todas, o filtradas por estado) y ver las estadísticas:

```bash
curl -s localhost:8000/tareas
curl -s 'localhost:8000/tareas?estado=completada'
curl -s localhost:8000/estadisticas
```

El apagado ordenado y el volcado:

```bash
docker compose stop api                    # manda SIGTERM: apagado ordenado
docker compose logs api | tail -5          # "workers detenidos...", "estado volcado en ..."
docker compose start api
docker compose logs api | grep "volcado previo"
docker compose exec api ls /app/datos      # los estado_<fecha>.json
```

Para bajar todo: `docker compose down`. Los volcados se conservan en un
volumen de Docker; `docker compose down -v` también los borra.

---

## 2. Arquitectura

### Componentes

```
  Cliente HTTP (curl, medicion/medir.py)
        │
        │  POST /tareas · GET /tareas · GET /tareas/{id}
        │  DELETE /tareas/{id} · GET /estadisticas
        ▼
┌─ contenedor api: UN proceso, UN hilo, UN event loop (uvloop) ──────────────┐
│                                                                            │
│   FastAPI ─────── crea, consulta y cancela ───────▶  Almacén               │
│      │                                              (dict id → Tarea)      │
│      │ put_nowait(id)                                      ▲               │
│      │ (cola llena → 503)                                  │ cada cambio   │
│      ▼                                                     │ de estado     │
│   asyncio.Queue(maxsize=COLA_MAX)                          │               │
│      │ await get()                                         │               │
│      ▼                                                     │               │
│   N workers (corrutinas) ── create_task ──▶ tarea interna ─┘               │
│                                             (asyncio.timeout)              │
│                                                    │                       │
│              ┌─────────────────────────────────────┼─────────────────┐     │
│              ▼                                     ▼                 ▼     │
│          esperar                              descargar           hashear  │
│    await asyncio.sleep()             TaskGroup + un único   run_in_executor│
│                                       httpx.AsyncClient       de a bloques │
│                                                │                     │     │
│                                                │                     ▼     │
│                                                │       ProcessPoolExecutor │
│                                                │       (procesos hijos)    │
└────────────────────────────────────────────────┼───────────────────────────┘
                                                 ▼
                         contenedor lento: servidor de prueba (demora a pedido)
```

- **FastAPI** valida cada pedido, crea la tarea en el **almacén** y deja su
  `id` en la **cola**.
- Cada **worker** es una corrutina que hace `await cola.get()` en un bucle.
  Por cada tarea crea una **tarea interna**, una `asyncio.Task` propia que
  ejecuta el trabajo con su timeout. Cancelar una tarea es cancelar esa
  `Task`, y no al worker.
- El **almacén** es un diccionario en memoria. No necesita lock porque solo
  lo toca el event loop (ver 4).
- El **`ProcessPoolExecutor`** y el **cliente `httpx`** se crean una sola vez,
  al arrancar, y los comparten todas las tareas.

### El ciclo de vida del servicio

Lo maneja el `lifespan` de FastAPI (`app/main.py:23`):

| Al arrancar | Al apagar (`SIGTERM` o `SIGINT`) |
|---|---|
| 1. Informa por log el último volcado, si hay. | 1. uvicorn cierra el socket: no entran pedidos nuevos. |
| 2. Crea el cliente `httpx` y el `ProcessPoolExecutor`. | 2. Los workers dejan de tomar tareas de la cola. |
| 3. Lanza los N workers. | 3. Espera hasta `APAGADO_ESPERA` a las tareas en curso. |
| | 4. Cancela las que no terminaron (motivo: `apagado del servicio`). |
| | 5. Cierra el executor. |
| | 6. Vuelca el estado a `estado_<fecha>.json`. |

### El recorrido de una tarea

1. `POST /tareas` con `{"tipo": "descargar", "urls": [...]}`. Pydantic valida
   el pedido según su `tipo`; si está mal formado, responde **422**.
2. El almacén crea la tarea en estado `pendiente`, con un `id` de 8
   caracteres.
3. `put_nowait(id)` la deja en la cola, sin esperar. Si la cola está llena, la
   tarea se descarta y se responde **503**. Si no, se responde **202** con el
   `id`. Hasta acá no hubo ningún `await` que dependa de la tarea: el `POST`
   tarda milisegundos.
4. Un worker libre la saca de la cola, la marca `ejecutando` y crea su tarea
   interna.
5. La tarea interna corre el trabajo dentro de `asyncio.timeout()`. En
   `descargar`, un `TaskGroup` lanza todas las URLs a la vez y el loop atiende
   a otros mientras esperan la red.
6. Al terminar, la propia tarea interna deja el estado final: `completada`
   con el resultado, `fallida` con el motivo, o `cancelada`.
7. El worker vuelve al paso 4 con la siguiente.

### Estados

```
                  POST
                   │
                   ▼
              pendiente ─────────── DELETE ──────────────▶ cancelada
                   │                                          ▲
      un worker    │                                          │  DELETE, o el
      la toma      │                                          │  apagado del
                   ▼                                          │  servicio
              ejecutando ─────────────────────────────────────┘
               │       │
  terminó bien │       │ lanzó una excepción
               │       │ o venció su timeout
               ▼       ▼
        completada   fallida
```

Si el servicio se apaga, las tareas que siguen en la cola quedan `pendiente`
en el volcado.

---

## 3. API

| Método | Ruta | Qué hace | Respuestas |
|---|---|---|---|
| `POST` | `/tareas` | Encola una tarea y devuelve su `id` y su estado | **202**; 422 si el pedido es inválido; 503 si la cola está llena |
| `GET` | `/tareas` | Lista las tareas; `?estado=` filtra por estado | 200; 422 si el estado no existe |
| `GET` | `/tareas/{id}` | Estado y resultado de una tarea | 200; 404 |
| `DELETE` | `/tareas/{id}` | Cancela una tarea pendiente o en ejecución y la devuelve ya cancelada | 200; 404; 409 si ya había terminado |
| `GET` | `/estadisticas` | Totales por estado, tiempos promedio, workers ocupados y cola | 200 |

Estados posibles: `pendiente`, `ejecutando`, `completada`, `fallida` y
`cancelada`.

**Pedidos.** El campo `tipo` decide qué campos lleva. `timeout` es opcional
en los tres (en segundos; si no se da, 30):

```json
{"tipo": "esperar",   "segundos": 5}
{"tipo": "descargar", "urls": ["http://lento:8001/demora/1", "https://example.com"]}
{"tipo": "hashear",   "texto": "hola", "iteraciones": 1000000, "timeout": 10}
```

**Una tarea terminada.** Esta respuesta es real, de un `descargar` con una
URL inexistente:

```json
{
    "id": "85d881df",
    "tipo": "descargar",
    "parametros": {
        "urls": [
            "http://lento:8001/demora/1",
            "http://lento:8001/demora/0.5",
            "http://no-existe/"
        ]
    },
    "timeout": 30.0,
    "estado": "completada",
    "resultado": {
        "tiempo_total_s": 1.0706,
        "descargas": [
            {"url": "http://lento:8001/demora/1", "estado_http": 200, "bytes": 1000, "tiempo_s": 1.0705},
            {"url": "http://lento:8001/demora/0.5", "estado_http": 200, "bytes": 1000, "tiempo_s": 0.5185},
            {"url": "http://no-existe/", "error": "ConnectError: [Errno -3] Temporary failure in name resolution", "tiempo_s": 0.0048}
        ]
    },
    "error": null,
    "creada": "2026-11-01T21:56:35.914791-03:00",
    "iniciada": "2026-11-01T21:56:35.915774-03:00",
    "terminada": "2026-11-01T21:56:36.986882-03:00",
    "espera_s": 0.000983,
    "duracion_s": 1.071108
}
```

- `espera_s` es el tiempo que pasó en la cola y `duracion_s` el que tardó en
  ejecutarse.
- Una tarea `fallida` lleva el motivo en `error`, por ejemplo `"timeout: superó
  el límite de 1.0 s"` o `"ValueError: ..."`.
- Las URLs que fallan no tumban la tarea: el error queda en su propia entrada.

**`/estadisticas`:**

```json
{
    "total": 5,
    "por_estado": {"pendiente": 0, "ejecutando": 0, "completada": 3, "fallida": 1, "cancelada": 1},
    "espera_promedio_s": {"esperar": 0.0006, "descargar": 0.0005, "hashear": 0.0004},
    "duracion_promedio_s": {"esperar": 1.9995, "descargar": 1.0535, "hashear": 0.9676},
    "workers": {"total": 4, "ocupados": 0},
    "cola": {"en_espera": 0, "capacidad": 100}
}
```

Los promedios son por tipo de tarea y solo cuentan las tareas completadas.

---

## 4. Decisiones de diseño

### ¿Por qué `asyncio.Queue` y no `queue.Queue`?

**Porque los workers son corrutinas que corren en el mismo hilo que la API, y
`queue.Queue` bloquea ese hilo.**

`queue.Queue` está hecha para threads. Cuando un consumidor hace `get()` y la
cola está vacía, el thread se duerme hasta que llegue algo. Dentro de una
corrutina eso duerme **el único hilo del event loop**, así que se congela todo
el servicio: la API, los otros workers y los timeouts. `asyncio.Queue`, en
cambio, tiene un `get()` que es una corrutina. Con `await cola.get()`, el
worker se suspende y le devuelve el control al loop hasta que haya trabajo.
Lo comprobé con un consumidor que espera 1 segundo a que llegue un elemento,
mientras otra corrutina intenta despertarse cada 10 ms:

| Consumidor | Peor atraso del event loop |
|---|---|
| `queue.Queue.get()` dentro de una corrutina | **949 ms** |
| `await asyncio.Queue.get()` | 0,3 ms |

**¿Y por qué no hace falta un `Lock`?** `queue.Queue` lleva un lock de threads
por dentro porque un thread puede ser interrumpido en cualquier instrucción,
incluso a mitad de modificar la cola. Acá no hay varios threads tocando el
estado: todo corre en el hilo del event loop, y el control solo cambia de una
corrutina a otra en un `await`. Ningún método del almacén hace `await`, así
que cada uno corre de principio a fin sin que nadie se meta en el medio. Es
el mismo patrón productor-consumidor de la clase 11, pero con corrutinas en
vez de threads. El único lugar delicado es el paso de una tarea de
`pendiente` a `ejecutando`: entre marcarla y registrar su tarea interna no hay
ningún `await`, así que un `DELETE` nunca puede ver una tarea `ejecutando` que
todavía no se pueda cancelar.

**La cola tiene un tamaño máximo (`COLA_MAX`) y el `POST` nunca la espera.**
El `POST` encola con `put_nowait()`, no con `await put()`. Si la cola está
llena, responde **503** en el acto en vez de quedarse esperando lugar. La
consigna pide que el `POST` responda inmediatamente, y además así la memoria
no crece sin control (*backpressure*). Cada `get()` tiene su `task_done()` en
un `finally`, para que la cuenta de la cola nunca se desarme.

- **En el código:**
  - la cola: `app/pool.py:23`;
  - `put_nowait`: `app/pool.py:47`;
  - el 503: `app/main.py:81`;
  - `task_done`: `app/pool.py:107`;
  - por qué no hay `Lock`: `app/almacen.py:3` y `app/pool.py:117`.
- **Lo prueban:** `test_cola_llena_lanza_queuefull_sin_esperar`,
  `test_cola_llena_da_503` y `test_los_workers_ejecutan_a_la_vez`.

### ¿Cómo se evita que una tarea CPU-bound congele la API?

**Mandando el cálculo a otro proceso con `run_in_executor`: el event loop
solo espera el resultado con `await`.**

Un cálculo de CPU no tiene ningún punto donde ceder el control. Si corre
dentro del event loop, lo ocupa entero hasta terminar, y la medición 5.2 lo
muestra: un `GET` tardó 3.703 ms en vez de 3 ms. Por eso `hashear` usa
`loop.run_in_executor()` con un `ProcessPoolExecutor`. El executor se crea
**una sola vez** al arrancar el servicio, porque crear procesos por pedido
sería caro, y se comparte entre todas las tareas.

- **Procesos y no threads (`asyncio.to_thread`).** Por el GIL, solo un
  thread ejecuta bytecode de Python a la vez. Un thread calculando le
  competiría al event loop por el intérprete. Cada proceso tiene su propio
  intérprete, y el cálculo corre de verdad en paralelo, en otro núcleo.
- **El hash se manda de a bloques.** En vez de un solo envío de N vueltas,
  la corrutina manda bloques de 100.000 (`BLOQUE_HASH`) uno por uno, con un
  `await` entre cada uno.
  - **Por qué:** cancelar el `await` de `run_in_executor` **no detiene un
    cálculo que ya empezó**. El proceso sigue ocupado hasta terminarlo, aunque
    ya nadie espere el resultado. Lo medí durante el desarrollo con un pool de
    un solo proceso: después de cancelar un hash largo, un hash chico pedido a
    continuación esperó **3,22 s** sin bloques y **0,048 s** con bloques.
  - **Cuánto cuesta:** un 5% de tiempo (3,89 s contra 3,70 s, ver 5.2).
  - **De yapa:** varias tareas de CPU avanzan juntas en vez de en tandas
    (ver 5.3).
- **`MODO_CPU=loop`** corre el cálculo dentro del loop, mal a propósito. Existe
  solo para poder hacer la medición 5.2.
- **El cierre del executor también se cuida.** `executor.shutdown(wait=True)`
  es bloqueante, así que el apagado lo llama con `asyncio.to_thread()` para no
  congelar el loop mientras termina el último bloque.

- **En el código:**
  - el executor: `app/main.py:34`;
  - el bucle de bloques: `app/tareas.py:82`;
  - el modo `loop`: `app/tareas.py:75`;
  - el cierre: `app/main.py:48`.
- **Lo prueban:** `test_hashear_en_executor_no_bloquea_el_loop`,
  `test_hashear_en_el_loop_lo_bloquea`,
  `test_cancelar_hashear_libera_el_proceso_enseguida` y
  `test_hashear_da_lo_mismo_que_de_corrido`. Este último comprueba que el hash
  por bloques da exactamente lo mismo que de corrido, incluso cuando N no es
  múltiplo del bloque.

### ¿Cómo se implementó la cancelación, y qué pasa con los recursos a medio usar?

**Cada tarea corre en su propia `asyncio.Task` (la "tarea interna"), separada
del worker que la atiende. Cancelar una tarea es cancelar esa `Task`, y no al
worker.**

`task.cancel()` no mata nada en el acto: inyecta un `CancelledError` en el
próximo `await` de la tarea (clase 20). Desde ahí hay tres casos:

1. **Pendiente (en la cola).** Una `asyncio.Queue` no deja sacar un elemento
   del medio. Entonces la tarea se marca `cancelada` y, cuando un worker la
   saca de la cola, ve que ya no está pendiente y la descarta sin
   ejecutarla.
2. **En ejecución.** El `DELETE` cancela la tarea interna y **espera a que
   termine de verdad** antes de responder. Por eso la respuesta ya trae el
   estado `cancelada`, y no un "cancelando". La propia tarea interna se marca
   `cancelada` cuando recibe el `CancelledError` y lo vuelve a lanzar, que es
   lo que pide la clase 20: si se lo tragara, la tarea seguiría viva.
3. **Por timeout.** El trabajo corre dentro de `asyncio.timeout()`, que
   cuando vence cancela la tarea y lanza `TimeoutError`. La tarea queda
   `fallida` con el motivo. Con `expired()` se distingue el timeout propio de
   un `TimeoutError` que venga de adentro, por ejemplo de un servidor que no
   responde, para no informar un motivo falso.

**El detalle más fino está en cómo el worker espera a la tarea interna:** con
`await asyncio.wait({interna})`, y no con `await interna`.
- `asyncio.wait` **no relanza** lo que le pase a la tarea interna. Si un
  `DELETE` la cancela, el worker sigue vivo y toma la próxima.
- Lo único que puede interrumpir al worker en ese `await` es su **propia**
  cancelación, que solo ocurre al apagar el servicio. En ese caso cancela la
  tarea interna y espera a que termine antes de salir, para que no quede
  huérfana.

Para comprobarlo cambié a propósito `asyncio.wait({interna})` por
`await interna`: un `DELETE` pasó a **matar al worker**, y dos tests lo
detectaron.

**Los recursos a medio usar:**
- **Descargas:** `descargar` lanza las URLs dentro de un `asyncio.TaskGroup`.
  Si cancelan la tarea, el `TaskGroup` cancela y espera a todas las descargas
  hijas, y `httpx` cierra cada conexión. Medido: al cancelar 3 descargas de
  5 s a los 0,7 s, el servidor de prueba registró **las 3 desconexiones** a
  los 0,71 s.
- **`hashear`:** el bloque que ya estaba en el executor termina solo, en
  ~0,1 s, y el proceso queda libre. No se manda ningún bloque más.
- **`esperar`:** `asyncio.sleep()` se cancela al instante.
- **Al apagar** se usa el mismo mecanismo, así que tampoco ahí queda nada
  suelto. Un test cuenta las `asyncio.Task` vivas después de cancelar,
  vencer un timeout y apagar: vuelven a ser exactamente las de antes.

Si la tarea ya terminó, `DELETE` responde **409**. Si termina sola justo en
el mismo instante en que se la cancela, el código también responde 409 con
su estado real, en vez de mentir que se canceló. (Este caso límite surge de
leer el código: no está cubierto por un test.)

- **En el código:**
  - los tres casos: `app/pool.py:49`;
  - la tarea interna: `app/pool.py:119`;
  - la espera del worker: `app/pool.py:126`;
  - el timeout: `app/pool.py:136` y `app/pool.py:147`;
  - el `TaskGroup`: `app/tareas.py:54`;
  - el 409: `app/main.py:103`.
- **Lo prueban:** `test_cancelar_pendiente_no_llega_a_ejecutarse`,
  `test_cancelar_en_ejecucion_libera_al_worker`,
  `test_timeout_deja_la_tarea_fallida_con_motivo`,
  `test_timeouterror_de_adentro_no_se_confunde_con_el_nuestro`,
  `test_cancelar_descargar_corta_todas_las_descargas` y
  `test_no_quedan_tareas_huerfanas`.

### ¿Qué pasa si un worker lanza una excepción no capturada?

**No puede pasar: hay dos redes que la atajan, y la tarea queda `fallida`
con el motivo.**

1. **La primera red está en la tarea interna.** Cualquier `Exception` que
   lance el trabajo se convierte en estado `fallida`, con el tipo y el
   mensaje (por ejemplo `ValueError: roto`), y la tarea interna termina
   normalmente.
2. **La segunda red está en el bucle del worker.** Si algo fallara *fuera*
   del trabajo, por ejemplo al buscar la tarea, el worker lo registra con
   `log.exception` y sigue con la siguiente. El `task_done()` va en un
   `finally`, para que la cola no pierda la cuenta.

Ninguna de las dos se traga una cancelación: `CancelledError` hereda de
`BaseException` y no de `Exception` (comprobado), así que un
`except Exception` no la atrapa y cancelar sigue funcionando.

**Para qué sirve cada red:**
- **Sin la primera**, el worker sobreviviría, porque `asyncio.wait` no
  relanza lo que le pasa a la tarea interna, pero la tarea quedaría
  `ejecutando` para siempre, con un estado falso. Lo comprobé rompiendo el
  código a propósito: el test que lo cubre falla.
- **Sin la segunda**, un error fuera del trabajo terminaría la `asyncio.Task`
  del worker. El pool perdería ese worker sin que nadie se enterara, y con
  suficientes errores dejaría de procesar.

- **En el código:**
  - la primera red: `app/pool.py:153`;
  - la segunda: `app/pool.py:103`.
- **Lo prueban:** `test_una_excepcion_no_mata_al_worker`, donde un mismo
  worker atiende una tarea que falla y después una sana que se completa, y
  `test_timeouterror_de_adentro_no_se_confunde_con_el_nuestro`.

### Otras decisiones

- **`httpx` (async) y no `aiohttp`.** Las dos son clientes HTTP asíncronos y
  cualquiera cumple la consigna. Elegí `httpx` por dos motivos:
  - tiene la misma interfaz que `requests` y es el que usa la clase 20;
  - trae `MockTransport`, que permitió testear las descargas sin red, con
    demoras y fallas controladas.
  
  Hay **un solo** `AsyncClient` para todo el servicio, que reutiliza
  conexiones en vez de abrir una por pedido. No medí `aiohttp` contra `httpx`
  en rendimiento. (`app/main.py:33`)
- **Un error de red queda en su URL, no tumba la tarea.** Si una de las URLs
  de `descargar` falla (conexión rechazada, host inexistente), su resultado
  lleva el error y las demás siguen. La tarea queda `completada` con el
  detalle por URL. Un 404 no es un error de red: se informa como respuesta.
  (`app/tareas.py:38`, `test_descargar_un_error_queda_en_su_url`)
- **El apagado ordenado vive en el `lifespan`.** uvicorn atiende `SIGTERM` y
  `SIGINT`: primero cierra el socket y después ejecuta el cierre del
  `lifespan`. Lo comprobé: un `curl` un segundo después de la señal no pudo ni
  conectarse. Por eso "dejar de aceptar tareas nuevas" no necesitó código
  propio. Lo que hace el servicio es esto:
  1. los workers dejan de tomar de la cola;
  2. espera a las tareas en curso hasta `APAGADO_ESPERA` (5 s);
  3. cancela las que no terminaron, con motivo `apagado del servicio`;
  4. cierra el executor;
  5. vuelca el estado.
  
  Las que seguían en la cola quedan `pendiente` en el volcado.
  (`app/main.py:23`, `app/pool.py:68`, `test_apagado_ordenado`)
- **El volcado se escribe de forma atómica**: primero a un temporal y después
  `os.replace()`. Si el proceso muere a mitad, no queda un JSON cortado con el
  nombre definitivo. Si el disco falla, se registra el error y el apagado
  termina igual. (`app/persistencia.py:18`, `app/main.py:56`,
  `test_si_el_volcado_falla_el_apagado_termina_igual`)
- **La espera del apagado (5 s) es menor que el plazo de Docker (15 s).**
  `docker stop` manda `SIGKILL` si el proceso no termina a tiempo. Medí que
  por defecto espera 10 s, y lo dejé explícito en 15 s
  (`stop_grace_period`) para que el volcado siempre llegue a escribirse.
  (`docker-compose.yml:27`)
- **El `CMD` del Dockerfile va en forma "exec"** (`["python", "-m",
  "app.main"]`), para que Python sea el PID 1 y reciba el `SIGTERM` de
  `docker stop`. Con la forma "shell", la señal le llegaría a `/bin/sh`, que
  no la reenvía. El contenedor corre con un usuario sin privilegios
  (`tareas`). (`Dockerfile:42`, `Dockerfile:30`)
- **Los volcados van a un volumen con nombre**, no a una carpeta del host.
  Sobreviven a `docker compose down` y no dependen de los permisos del
  usuario que clone el repo. (`docker-compose.yml:23`)
- **El tipo de tarea decide qué campos se validan.** Los tres pedidos son una
  unión de modelos de Pydantic que se distinguen por el campo `tipo`. FastAPI
  rechaza con **422** un pedido mal formado antes de que llegue al código:
  segundos negativos, URLs inválidas, cero iteraciones, un tipo que no
  existe. (`app/modelos.py:44`, `test_pedidos_invalidos_dan_422`)

---

## 5. Mediciones

Todos los números de esta sección son medidos, no estimados.

| | |
|-|-|
| **Fecha** | 31/10/2026 |
| **CPU** | Intel Core i5-6200U @ 2,30 GHz: **2 núcleos físicos, 4 hilos** (hyperthreading) |
| **RAM** | 7,6 GB |
| **Software** | Linux 7.0, Docker 29.9.1, Python 3.12.16 dentro del contenedor |

**Cómo se midió.**

- Todo corre en Docker, con el `docker-compose.yml` del proyecto. Las
  descargas van contra el servicio `lento` (`medicion/servidor_lento.py`), que
  responde 1.000 bytes después de la demora pedida. Así los tiempos no
  dependen de internet y se pueden repetir.
- Cada escenario se corrió **3 veces**, recreando el contenedor de la API
  antes de cada corrida para que arranque sin tareas acumuladas. Se informa
  la **mediana**.
- Los tiempos salen de las marcas que el propio servidor guarda en cada tarea,
  no del cronómetro del cliente:
  - **total**: desde que se creó la primera tarea hasta que terminó la última;
  - **alta**: cuánto tardó el servidor en recibir todos los `POST`;
  - **espera**: cuánto estuvo cada tarea en la cola antes de que la tomara un
    worker;
  - **duración**: cuánto tardó cada tarea en ejecutarse.
- El cliente que genera la carga tiene como mucho 50 `POST` en vuelo. Sin ese
  límite, el que se trababa era el propio cliente (ver 5.3).

**Para reproducirlo**, desde `TP2_tareas/` y con el entorno virtual creado
(ver sección 8):

```bash
./venv/bin/python medicion/medir.py        # las tres mediciones, ~10 min
./venv/bin/python medicion/diagnostico.py  # la evidencia de 5.3, ~3 min
```

Los resultados crudos de las corridas de esta sección están en
`medicion/resultados/medicion_20261031_010838.json` y
`medicion/resultados/diagnostico_20261031_012443.json`.

### 5.1 Concurrencia de I/O: 20 descargas secuenciales contra concurrentes

Veinte descargas de una URL que tarda 1 segundo en responder, en cuatro
configuraciones:

| Escenario | Configuración | Tiempo (mediana) | Speedup |
|---|---|---|---|
| Secuencial: 20 tareas de 1 URL | `WORKERS=1` | **20,43 s** | 1,0x |
| 20 tareas de 1 URL | `WORKERS=4` (por defecto) | 5,15 s | 4,0x |
| 20 tareas de 1 URL | `WORKERS=20` | **1,10 s** | **18,6x** |
| **1 tarea** con 20 URLs | `WORKERS=1` | **1,09 s** | **18,7x** |

Las tres corridas de cada escenario difieren como mucho en 0,06 s, y las 20
descargas terminaron bien en todos los casos.

**Interpretación.**

- **En secuencia, el tiempo es la suma de las demoras.** Con un solo worker,
  cada tarea espera a que termine la anterior: 20 × 1 s más un poco de
  overhead. Es lo que pasaría con un `for` que hace `await` de cada descarga
  una por una.
- **Con 4 workers, el límite es el pool.** El speedup es exactamente 4: las
  tareas salen en 5 tandas de 4.
- **Concurrentes, el tiempo es el de la más lenta.** Con 20 workers, las 20
  descargas esperan la respuesta a la vez, en un solo hilo: mientras una
  espera la red, el event loop atiende a las otras. El speedup no llega a 20
  por unos 0,1 s fijos de overhead: recibir los `POST`, abrir las conexiones y
  repartir las tareas.
- **Una sola tarea logra lo mismo que 20 workers.** Dentro de `descargar`, el
  `asyncio.TaskGroup` lanza las 20 descargas a la vez. La concurrencia no
  depende de cuántos workers haya, sino de que nadie bloquee el loop mientras
  espera. La diferencia entre las dos filas de abajo es de granularidad: con
  20 tareas, cada descarga tiene su propio estado, su timeout y se puede
  cancelar por separado; con 1 tarea, hay un único resultado y se cancelan
  todas juntas.

### 5.2 El event loop bloqueado

Un `hashear` de 4.000.000 vueltas (unos 4 segundos de CPU) y, mientras corre,
un `GET /tareas` cada 100 ms para medir cuánto tarda en responder la API.
`MODO_CPU=loop` ejecuta el cálculo dentro del event loop (mal a propósito);
`MODO_CPU=executor`, en un `ProcessPoolExecutor`.

| `MODO_CPU` | `GET` pudo hacerse | `GET` más lento | `GET` típico (mediana) | `GET` en reposo | Duración del hash |
|---|---|---|---|---|---|
| `loop` | **1 vez** | **3.703 ms** | 3.703 ms | 2,8 ms | 3,70 s |
| `executor` | 39 veces | **18 ms** | 3,0 ms | 2,8 ms | 3,89 s |

**Interpretación.**

- **Sin executor, la API queda congelada todo el cálculo.** En las tres
  corridas, el único `GET` que se llegó a mandar tardó lo mismo que el hash
  entero (3,70 s contra 3,70 s). El servidor ni siquiera podía leer el pedido:
  el event loop es un solo hilo y estaba ocupado calculando, sin ningún `await`
  donde ceder el control. Durante esos 3,7 segundos tampoco avanza ninguna
  otra tarea, no vence ningún timeout y no se puede cancelar nada. Es
  exactamente lo que hace un `time.sleep()` dentro de una corrutina.
- **Con executor, la API ni se entera.** Los 39 `GET` respondieron en una
  mediana de 3,0 ms, prácticamente igual que en reposo (2,8 ms). El peor fue
  de 18 ms: **unas 200 veces menos** que sin executor. El cálculo corre en
  otro proceso, y el loop solo espera el resultado con `await`.
- **Por qué procesos y no threads.** Un thread no alcanza para trabajo de CPU
  en Python: por el GIL, solo un thread ejecuta bytecode a la vez, y el
  cálculo le competiría al event loop por el intérprete. Un proceso tiene su
  propio intérprete y su propio GIL. (Esta comparación es de la clase 21; no
  se repitió en este TP.)
- **Lo que cuesta partir el cálculo en bloques.** Con executor, el hash se
  manda de a bloques de 100.000 vueltas para poder cancelarlo entre bloque y
  bloque (ver sección 4). Eso cuesta un **5%** de tiempo: 3,89 s contra 3,70 s
  de corrido, por pasar cada bloque entre procesos 40 veces.

### 5.3 El techo del pool

Se subió la cantidad de tareas simultáneas hasta ver dónde se degradan los
tiempos, con workers y cola de sobra (`WORKERS=5000`, `COLA_MAX=10000`) para
que el límite apareciera en otro lado. Se hizo con los tres tipos de tarea,
porque cada uno agota un recurso distinto.

**`hashear` (CPU), 500.000 vueltas por tarea:**

| Tareas a la vez | Total | Duración media por tarea | Hashes por segundo |
|---|---|---|---|
| 1 | 0,50 s | 0,50 s | 2,0 |
| 2 | 0,60 s | 0,60 s | 3,3 |
| 3 | 0,77 s | 0,72 s | 3,9 |
| 4 | 0,99 s | 0,96 s | 4,0 |
| 6 | 1,47 s | 1,39 s | 4,1 |
| 8 | 1,94 s | 1,81 s | 4,1 |
| 12 | 2,90 s | 2,66 s | 4,1 |
| 16 | 3,82 s | 3,50 s | 4,2 |

**`descargar` (I/O de red), una URL de 1 s por tarea:**

| Tareas a la vez | Total | Alta de todas | Duración media | Duración máxima |
|---|---|---|---|---|
| 50 | 1,21 s | 0,04 s | 1,17 s | 1,18 s |
| 100 | 1,39 s | 0,35 s | 1,14 s | 1,23 s |
| 200 | 2,85 s | 1,01 s | 1,83 s | 2,43 s |
| 400 | 6,27 s | 4,09 s | 2,54 s | 3,87 s |
| 800 | 13,91 s | 11,69 s | 3,33 s | 5,05 s |
| 1.200 | 21,45 s | 19,16 s | 3,58 s | 5,13 s |

**`esperar` (I/O sin red), 1 s por tarea:**

| Tareas a la vez | Total | Alta de todas | Duración media | Duración máxima |
|---|---|---|---|---|
| 100 | 1,19 s | 0,18 s | 1,01 s | 1,03 s |
| 1.000 | 4,13 s | 3,13 s | 1,00 s | 1,04 s |
| 5.000 | 17,39 s | 16,37 s | 1,00 s | 1,07 s |

En ninguna corrida hubo descargas con error, pedidos rechazados (503) ni
`POST` fallidos. La espera media en la cola fue de menos de 0,02 s en todos
los casos: con 5000 workers, la cola nunca fue el límite.

Para saber **por qué** se degradan, `medicion/diagnostico.py` repite las
cargas más altas midiendo mientras corren: la CPU del proceso de la API
(leída de `/proc/1/stat` dentro del contenedor), las conexiones TCP abiertas
contra el servidor de prueba (de `/proc/net/tcp`) y la CPU del propio cliente
que genera la carga.

| Carga | CPU del proceso de la API | Conexiones abiertas al servidor de prueba |
|---|---|---|
| 800 descargas | **95%** de un núcleo (mediana) | **100** (máximo y mediana) |
| 5000 esperas | 41% de un núcleo | 0 |

| Cómo se generó la carga | `POST` por segundo | CPU del cliente | CPU de la API |
|---|---|---|---|
| 1 cliente, de a un pedido | 302 | 75% | — |
| 1 cliente, 50 pedidos en vuelo | 278 | **95%** | — |
| 1 cliente | 256 | — | 39% |
| 2 clientes en paralelo | **412** | — | 67% |
| 4 clientes en paralelo | **412** | — | 69% |

**Dónde está el límite y por qué.**

| Tipo de tarea | Desde dónde se degrada | Qué se agota | Evidencia |
|---|---|---|---|
| `hashear` | 2 a 4 tareas | **Los núcleos de la CPU** | Tope de ~4,1 hashes/s |
| `descargar` | ~200 tareas | **Las 100 conexiones de `httpx`** y **el event loop de la API** | 100 conexiones abiertas; API al 95% |
| `esperar` | No se degrada hasta 5000 | Nada del servicio: el límite es el generador de carga | Duración 1,00 s; API al 41% |

- **CPU: el techo son los núcleos.** Una tarea tarda 0,50 s. Dos tardan casi
  lo mismo (0,60 s), porque cada una usa un núcleo físico. Con 4, el
  hyperthreading aporta apenas un 21% más (de 3,3 a 4,0 hashes/s). A partir de
  ahí el rendimiento queda clavado en ~4,1 hashes/s y el tiempo crece en línea
  recta con la cantidad de tareas. Agregar workers o procesos no ayuda: no hay
  más CPU para repartir. La duración media es casi igual al total (3,50 s
  contra 3,82 s con 16 tareas) porque, al estar partidas en bloques, todas las
  tareas avanzan juntas y terminan casi a la vez, en vez de salir en tandas.
- **Red: dos topes que se suman.** Hasta 100 descargas, cada una tarda lo
  que la red (1,14 s). Desde 200 la duración sube, porque el cliente `httpx`
  compartido abre **como mucho 100 conexiones** (medido: exactamente 100) y las
  demás descargas esperan una conexión libre *dentro* de la tarea. Por eso la
  espera en la cola sigue siendo casi cero y lo que crece es la duración. Al
  mismo tiempo, **el event loop de la API se satura** (95% de un núcleo):
  atiende en un solo hilo los `POST` que llegan y cientos de descargas que
  salen. Eso se ve en el alta, que baja de unos 300 tareas/s con `esperar` a
  63 tareas/s con 1200 descargas.
- **Sin red: el event loop no fue el límite.** Con 5000 tareas esperando a la
  vez, cada una sigue durando 1,00 s: tener miles de corrutinas suspendidas
  cuesta muy poco. El total lo marca el alta, y el alta la limita **el
  generador de carga**, no el servicio. Un solo cliente queda al 95% de CPU
  mientras la API está al 41%. Con 2 clientes en paralelo se llega a 412
  `POST`/s, y con 4 ya no sube: la API se queda en 69% porque se satura **la
  máquina**, cuyos 2 núcleos comparten los clientes y el servidor. El techo
  propio del servicio para tareas livianas no se pudo aislar en este
  hardware.
- **Una lección de la medición.** La primera versión de `medir.py` mandaba
  los 1000 `POST` juntos. El cliente se trababa en su propio pool de
  conexiones y bajaba a 23 `POST`/s, mientras la API estaba al 17% de CPU:
  parecía un techo del servicio y era un problema de la herramienta. Por eso
  el cliente tiene como mucho 50 pedidos en vuelo, y por eso existe
  `diagnostico.py`.

**¿Qué pasa con 10.000 tareas de golpe?** Con la configuración por defecto,
el primer límite es deliberado: la cola acepta 100 tareas (`COLA_MAX`) y los
4 workers toman otras 4, así que las siguientes reciben **503** en el acto,
en vez de quedar acumulándose en memoria (lo cubre
`test_cola_llena_da_503`). Si se agranda la cola, lo que se agota primero
depende del tipo de tarea, como muestran las tablas de arriba.

---

## 6. Conceptos del curso aplicados

- **Productor-consumidor (clase 11), con corrutinas en vez de threads.** El
  `POST` es el productor y los workers son los consumidores de una
  `asyncio.Queue` compartida (`app/pool.py:23`). No hace falta `Lock`, porque
  el event loop no interrumpe entre `await`s. El único punto delicado, una
  posible race condition entre marcar una tarea `ejecutando` y registrarla
  para poder cancelarla, se evita no poniendo ningún `await` en el medio
  (`app/pool.py:117`).
- **Backpressure con `maxsize` (clase 21).** La cola tiene capacidad
  limitada. El `POST` usa `put_nowait()` y responde 503 en vez de esperar
  lugar (`app/main.py:81`).
- **Corrutinas y el `await` como punto de cesión (clase 18).** Cada `await`
  es el lugar donde una corrutina le devuelve el control al loop. `esperar`
  es el caso más puro: `await asyncio.sleep()` deja correr a las demás
  mientras tanto (`app/tareas.py:25`). La medición 5.2 muestra el caso
  contrario, un tramo sin `await` que congela todo.
- **El event loop sobre epoll (clases 17 y 18).** El servicio corre en un
  solo hilo, que atiende a muchos clientes a la vez: el problema C10K de las
  clases 14 y 17. uvicorn usa `uvloop`, y los tests usan el loop de
  selectores de asyncio. Comprobé que los dos tienen un descriptor epoll
  (`anon_inode:[eventpoll]` en `/proc/<pid>/fd`). La medición 5.3 lo muestra
  funcionando: 5000 tareas esperando a la vez, cada una tardando 1,00 s.
- **HTTP y FastAPI (clase 19).**
  - Los métodos y los códigos de estado: 202, 404, 409, 422 y 503
    (`app/main.py:73`).
  - La validación con Pydantic, con una unión de modelos que se distingue por
    `tipo` (`app/modelos.py:44`).
  - ASGI: uvicorn es el servidor y FastAPI la aplicación.
  - Keep-alive: un único `httpx.AsyncClient` reutiliza las conexiones
    (`app/main.py:33`).
- **El `lifespan` de FastAPI (manijas de la clase 19, clase 21).** El
  arranque y el apagado del pool, del executor y del cliente HTTP. Además es
  un generador con `yield` convertido en context manager con
  `@asynccontextmanager` (Bloque 0) (`app/main.py:23`).
- **Timeouts y cancelación (clase 20).**
  - `asyncio.timeout()`, que por dentro cancela la tarea al vencer
    (`app/pool.py:136`).
  - `cancel()`, que inyecta un `CancelledError` en el próximo `await`.
  - El `CancelledError` se vuelve a lanzar siempre después de registrar el
    estado (`app/pool.py:144`), y nunca se lo traga un `except Exception`,
    porque hereda de `BaseException`.
- **`TaskGroup` contra `gather` (clase 21).** Las descargas de una tarea van
  en un `TaskGroup` (`app/tareas.py:54`): al salir del bloque, todas las
  hijas terminaron, y si se cancela la tarea se cancelan y se esperan todas.
  La diferencia con `gather` aparece cuando una hija **falla**: `gather`
  devuelve el error y deja a las demás corriendo sueltas, mientras que
  `TaskGroup` las cancela. Es lo que muestra `grupos.py` de la clase 21. Acá
  `_bajar` atrapa sus propios errores de red, pero si alguno se escapara, no
  quedarían descargas huérfanas.
- **`run_in_executor` y `ProcessPoolExecutor` (clases 21 y 22).** El cálculo
  de CPU va a otros procesos y el loop espera el `Future` con `await`
  (`app/tareas.py:84`). Lo bloqueante que no es CPU, como escribir el volcado
  o cerrar el executor, va a un thread con `asyncio.to_thread()`
  (`app/persistencia.py:33`, `app/main.py:48`).
- **El GIL (clase 10).** Es el motivo de usar procesos y no threads para
  `hashear`: un thread calculando le competiría al event loop por el
  intérprete.
- **Procesos, `fork` y `spawn` (clases 4 y 8).** El executor crea procesos
  hijos dentro del contenedor. En Linux usa `fork`; en macOS y Windows usa
  `spawn`, que vuelve a importar el módulo principal. Por eso el arranque va
  protegido con `if __name__ == '__main__'` (`app/main.py:117`).
- **Señales (clase 6), igual que en el TP1.** El apagado se dispara con
  `SIGTERM` o `SIGINT`. uvicorn instala los manejadores con `signal.signal()`,
  y lo único que hace su manejador es **levantar una bandera**
  (`should_exit = True`). El bucle principal de uvicorn la mira cada 0,1 s y,
  al verla, cierra el socket y ejecuta el cierre del `lifespan`. Es el patrón
  de la clase 6: el handler no hace trabajo, solo avisa, y el trabajo lo hace
  el programa en un punto seguro. `SIGKILL` no se puede atrapar: por eso la
  espera del apagado tiene que ser menor que el plazo de Docker.
- **Docker (clases 1 y 2).**
  - La imagen se arma en capas, con las dependencias antes que el código.
  - Compose levanta dos servicios que se encuentran por nombre (`lento`).
  - Un volumen con nombre guarda los volcados.
  - La forma "exec" del `CMD` hace que Python sea el PID 1 y reciba las
    señales (`Dockerfile:42`).
- **Clientes concurrentes con un límite (clase 20).** El generador de carga
  de las mediciones acota los pedidos en vuelo con un `asyncio.Semaphore`
  (`medicion/medir.py:135`).
- **Leer `/proc` (TP1, clase 3).** El diagnóstico de 5.3 mide la CPU del
  proceso con `utime + stime` de `/proc/1/stat` y cuenta conexiones TCP en
  `/proc/net/tcp` (`medicion/diagnostico.py:44`).
- **`argparse` (Bloque 0).** Las opciones `--solo` y `--reps` de
  `medicion/medir.py` (`medicion/medir.py:355`).

---

## 7. Limitaciones conocidas

- **`GET /tareas` y `GET /estadisticas` crecen con las tareas guardadas, y
  bloquean el event loop mientras tanto.** Las dos recorren todo el almacén
  y arman la respuesta sin ningún `await` en el medio, así que mientras lo
  hacen ninguna otra corrutina avanza. Medido en proceso, sin Docker:

  | Tareas guardadas | `GET /tareas` | Tamaño de la respuesta | `GET /estadisticas` |
  |---|---|---|---|
  | 100 | 1,5 ms | 0,03 MB | 1,1 ms |
  | 1.000 | 8,8 ms | 0,33 MB | 4,1 ms |
  | 5.000 | 41,4 ms | 1,64 MB | 13,1 ms |
  | 10.000 | 82,9 ms | 3,29 MB | 27,2 ms |

  El crecimiento es lineal (unos 8 ms cada 1.000 tareas) y no tiene techo,
  porque **las tareas terminadas nunca se borran de memoria**. Las mejoras
  serían paginar la lista (`?limite=` y `?desde=`), llevar los totales de
  `/estadisticas` como contadores que se actualizan en cada cambio de estado
  en vez de recalcularlos, y descartar las tareas terminadas después de un
  tiempo.

- **Un solo proceso.** El estado vive en la memoria de un proceso, así que no
  se puede levantar uvicorn con `--workers 2`: cada proceso tendría su propio
  almacén y una tarea creada en uno sería invisible para el otro. Además, el
  mismo event loop atiende los pedidos HTTP entrantes y las descargas
  salientes: con 800 descargas simultáneas el proceso de la API llega al 95%
  de un núcleo y el ritmo de alta de tareas baja (ver 5.3).

- **Como mucho 100 descargas a la vez.** El cliente `httpx` compartido usa su
  límite por defecto de 100 conexiones (medido: exactamente 100 abiertas
  contra el servidor de prueba). Las descargas que pasan de ese número
  esperan una conexión libre: la duración media por tarea sube de 1,14 s con
  100 tareas a 3,58 s con 1.200. El límite no se puede configurar todavía.

- **Cancelar un `hashear` no es instantáneo.** Un bloque ya enviado al
  executor no se puede interrumpir: el proceso sigue ocupado hasta terminarlo,
  como mucho un bloque (`BLOQUE_HASH`, ~0,1 s). Partir el cálculo en bloques
  cuesta un 5% de tiempo (3,89 s contra 3,70 s de corrido). Con
  `MODO_CPU=loop`, que existe solo para la medición 5.2, la tarea directamente
  no se puede cancelar porque nunca llega a un `await`.

- **El estado no se recarga al arrancar.** El volcado es un registro de cómo
  quedó todo al apagar: al arrancar se informa por log, pero las tareas que
  habían quedado pendientes no se vuelven a encolar.

- **Sin volcado si el proceso muere de golpe.** Si llega un `SIGKILL` (por
  ejemplo, porque el apagado tarda más que el `stop_grace_period` de Docker) o
  se cae la máquina, no hay apagado ordenado y no se escribe nada.

- **Las duraciones se miden con la hora del sistema.** `espera_s` y
  `duracion_s` salen de restar marcas de `datetime.now()`, mientras que
  `asyncio.sleep` y los timeouts usan un reloj monotónico. Por eso una
  espera de 2 s puede figurar con `duracion_s: 1.999489`, y un ajuste del
  reloj del sistema (por ejemplo, por NTP) a mitad de una tarea distorsionaría
  su duración. Lo correcto sería guardar también una marca de
  `time.monotonic()` para calcular las duraciones.

- **Sin topes en los parámetros.** `iteraciones`, `segundos` y la cantidad de
  URLs no tienen máximo; lo único que acota a una tarea es su timeout (30 s
  por defecto).

- **El techo de alta de tareas livianas no quedó aislado.** En esta máquina
  el generador de carga y el servidor comparten los mismos 2 núcleos físicos:
  el máximo medido fue de 412 `POST`/s, con la API entre el 67% y el 69% de
  CPU, y con más clientes no sube porque se satura la máquina, no el
  servicio. Para medir
  el techo propio del servidor habría que generar la carga desde otra
  máquina.

---

## 8. Cómo correr y testear

### Con Docker (lo que pide la consigna)

Hace falta Docker con Compose. Desde `trabajos_practicos/TP2_tareas/`:

```bash
docker compose up --build        # api en localhost:8000, y el servidor lento
docker compose logs -f api       # los logs: cada tarea, el apagado, el volcado
docker compose down              # bajar todo (los volcados quedan en el volumen)
```

### Tests y mediciones (en la máquina, con un entorno virtual)

Hace falta Python 3.11 o más nuevo; se probó con 3.12. En Debian y Ubuntu
puede hacer falta instalar el paquete `python3-venv`.

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/pytest
```

`pytest` corre los 53 tests en unos 7 segundos. No usan la red ni Docker: las
descargas van contra un `httpx.MockTransport` y la API se ejercita con su
`lifespan` real a través de `httpx.ASGITransport`.

| Archivo | Qué cubre |
|---|---|
| `tests/test_pool.py` | Cola, concurrencia, los tres casos de cancelación, timeouts, excepciones, tareas huérfanas y apagado ordenado |
| `tests/test_tareas.py` | Las tres tareas: hash por bloques igual al de corrido, loop libre contra loop bloqueado, descargas concurrentes y cancelación de descargas |
| `tests/test_api.py` | Endpoints y códigos de respuesta, cola llena y volcado al apagar |
| `tests/test_persistencia.py` | Escritura del volcado y aviso al arrancar, incluido un volcado corrupto |
| `tests/test_medicion.py` | Los cálculos de las mediciones |

Las mediciones de la sección 5 levantan el compose solas:

```bash
./venv/bin/python medicion/medir.py              # las tres, ~10 min
./venv/bin/python medicion/medir.py --solo 2     # solo una
./venv/bin/python medicion/diagnostico.py        # la evidencia de 5.3
```

### Sin Docker

También se puede correr directo en la máquina, con el mismo entorno virtual.
En ese caso escucha en `127.0.0.1` y los volcados van a `datos/`:

```bash
./venv/bin/python -m app.main                    # la API en 127.0.0.1:8000
./venv/bin/python medicion/servidor_lento.py     # el servidor de prueba en 127.0.0.1:8001
```

Sin Docker, las URLs del servidor de prueba son
`http://127.0.0.1:8001/demora/1`, en vez de `http://lento:8001/...`.

### Estructura

```
TP2_tareas/
├── app/
│   ├── main.py          API, lifespan (arranque y apagado)
│   ├── pool.py          cola, workers, cancelación, apagado ordenado
│   ├── tareas.py        esperar, descargar, hashear
│   ├── almacen.py       estado de las tareas en memoria
│   ├── modelos.py       pedidos (Pydantic) y registro de una tarea
│   ├── persistencia.py  volcado al apagar y aviso al arrancar
│   └── config.py        variables de entorno
├── medicion/            medir.py, diagnostico.py, servidor_lento.py, resultados/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt     lo que usa el servicio (fastapi, uvicorn, httpx)
└── requirements-dev.txt lo anterior más pytest y pytest-asyncio
```

---

## 9. Configuración

Todo se configura con variables de entorno (`app/config.py`). Con Docker,
las que están en `docker-compose.yml` se pueden cambiar al levantar, por
ejemplo:

```bash
MODO_CPU=loop WORKERS=1 docker compose up --build
```

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `WORKERS` | `4` | Cantidad de workers (corrutinas) que consumen de la cola. **(compose)** |
| `COLA_MAX` | `100` | Capacidad de la cola. Si se llena, `POST` responde 503. **(compose)** |
| `TIMEOUT_DEFECTO` | `30` | Timeout en segundos de las tareas que no piden uno propio. **(compose)** |
| `MODO_CPU` | `executor` | Dónde corre `hashear`: `executor` (otro proceso) o `loop` (dentro del event loop; mal a propósito, solo para la medición 5.2). **(compose)** |
| `APAGADO_ESPERA` | `5` | Segundos que el apagado espera a las tareas en curso. Tiene que ser menor que `stop_grace_period` (15 s). **(compose)** |
| `TZ` | `America/Argentina/Mendoza` | Zona horaria de los logs y de los nombres de los volcados. Solo en el contenedor. **(compose)** |
| `EXECUTOR_WORKERS` | cantidad de CPUs | Procesos del `ProcessPoolExecutor` |
| `BLOQUE_HASH` | `100000` | Vueltas de cada bloque de `hashear`: lo máximo que un proceso sigue ocupado después de cancelar |
| `HTTP_TIMEOUT` | `10` | Timeout de cada pedido HTTP de `descargar` |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Dónde escucha la API. En el contenedor, `HOST=0.0.0.0` (lo fija el `Dockerfile`) |
| `DIR_ESTADO` | `datos/` | Dónde se escriben los volcados. En el contenedor, `/app/datos`, que es el volumen |

Las marcadas **(compose)** se pasan desde `docker-compose.yml`. Para cambiar
las demás dentro del contenedor hay que agregarlas ahí, en `environment`.

---

## 10. Lo que aprendí

<!-- BORRADOR: revisar y reescribir con mis palabras antes de entregar. -->

Lo primero que me llevo es que un sistema puede funcionar bien y aun así
tener límites que no se ven hasta que uno los busca. Al auditar el trabajo
medí cuánto tardaba `GET /tareas` con miles de tareas guardadas y vi que
crece sin techo, porque las tareas terminadas nunca se borran y la respuesta
se arma de corrido, sin ningún `await`. Ahí entendí que no alcanza con que un
programa sea asíncrono: cualquier tramo de código que no cede el control
bloquea el event loop igual que un `time.sleep()`, aunque no lo parezca. Algo
parecido pasó con las descargas: el límite de 100 conexiones no estaba en mi
código sino en el cliente HTTP. Aprendí a escribir las limitaciones con
números en vez de esconderlas.

Lo que más me costó entender fueron las mediciones. Al principio pensaba que
medir era cronometrar y anotar el resultado, pero la primera vez que medí el
techo del pool los números decían que el servicio aceptaba apenas 23 tareas
por segundo, y no era cierto: el que estaba trabado era el propio programa
que mandaba los pedidos, mientras el servidor estaba casi sin trabajo. Recién
lo entendí cuando medí la CPU de cada lado por separado. De ahí saqué que una
medición también puede estar midiendo la herramienta y no el sistema, que
conviene tomar los tiempos del servidor y no del cliente, y que hay que
repetir cada prueba y mirar la mediana antes de sacar una conclusión.

El apagado ordenado también se me hizo difícil, sobre todo entender que "dejar
de aceptar tareas", "esperar a las que están corriendo" y "volcar el estado"
son pasos distintos que pasan en un orden. Me ayudó ver que el primero ya lo
resuelve uvicorn, que cierra el socket antes de llamar al cierre del
`lifespan`, y que lo mío era otra cosa: que los workers no tomaran nada nuevo
de la cola, esperar con un límite a las tareas en curso y cancelar las que no
llegaran. Lo terminé de entender cuando vi que una tarea quedaba `pendiente`
en el volcado aunque hubiera un worker libre, y cuando medí que Docker manda
un `SIGKILL` a los 10 segundos: por eso la espera tiene que ser más corta que
ese plazo, o el estado nunca llega a escribirse.
