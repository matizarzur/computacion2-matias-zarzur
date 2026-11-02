# Plataforma de Tareas Distribuidas

**Trabajo Práctico Nº 2 — Computación II — Universidad de Mendoza — 2026**

Autor: Matías Zarzur

---

## 1. Descripción general

> **[PENDIENTE]** Qué es el servicio en dos párrafos: una API HTTP (FastAPI)
> que recibe trabajos, los encola en una `asyncio.Queue` y los ejecuta un pool
> de workers (corrutinas) en un solo hilo; lo CPU-bound va a un
> `ProcessPoolExecutor`. Los tres tipos de tarea (`descargar`, `hashear`,
> `esperar`) y qué ejercita cada uno.

### Uso rápido

> **[PENDIENTE]** `docker compose up --build` y una secuencia de `curl` que se
> pueda copiar y pegar: crear cada tipo de tarea, consultar su estado,
> cancelarla, ver `/estadisticas`, y ver el volcado después de
> `docker compose stop`. Mencionar `http://127.0.0.1:8000/docs`.

---

## 2. Arquitectura

> **[PENDIENTE]** Diagrama de componentes (API, cola, workers, tarea interna,
> executor, cliente HTTP, servidor lento) y el recorrido de una tarea de punta
> a punta: `POST` → `put_nowait` → worker → tarea interna con timeout →
> estado final. Diagrama de estados: pendiente → ejecutando →
> completada / fallida / cancelada.

---

## 3. API

> **[PENDIENTE]** Tabla de endpoints con sus códigos de respuesta (202, 200,
> 404, 409, 422, 503), el formato de cada pedido y un ejemplo de respuesta.

---

## 4. Decisiones de diseño

### ¿Por qué `asyncio.Queue` y no `queue.Queue`?

> **[PENDIENTE]**

### ¿Cómo se evita que una tarea CPU-bound congele la API?

> **[PENDIENTE]** `run_in_executor` con procesos (y no threads: el GIL), el
> hash partido en bloques y su costo medido (+5%).

### ¿Cómo se implementó la cancelación, y qué pasa con los recursos a medio usar?

> **[PENDIENTE]** Los tres casos (pendiente, en ejecución, por timeout), la
> tarea interna esperada con `asyncio.wait`, el `TaskGroup` de las descargas y
> la evidencia: conexiones cortadas, ninguna tarea huérfana.

### ¿Qué pasa si un worker lanza una excepción no capturada?

> **[PENDIENTE]**

### Otras decisiones

> **[PENDIENTE]** Cola llena → 503 en vez de esperar; `httpx` y no `aiohttp`;
> un error de red queda en su URL y no tumba la tarea; el apagado ordenado en
> el `lifespan`; volumen con nombre para los volcados; la forma "exec" del
> `CMD` en el Dockerfile.

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

> **[PENDIENTE]** Cada concepto con la clase donde se vio y el lugar del
> código donde aparece (archivo:línea).

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

> **[PENDIENTE]** Con Docker (`docker compose up --build`), sin Docker (venv +
> `python -m app.main`), los tests (`requirements-dev.txt` + `pytest`), las
> mediciones (`medicion/medir.py` y `medicion/diagnostico.py`) y cómo ver los
> volcados (`docker compose exec api ls /app/datos`).

---

## 9. Configuración

> **[PENDIENTE]** Tabla de variables de entorno (`WORKERS`, `COLA_MAX`,
> `TIMEOUT_DEFECTO`, `HTTP_TIMEOUT`, `MODO_CPU`, `EXECUTOR_WORKERS`,
> `BLOQUE_HASH`, `APAGADO_ESPERA`, `DIR_ESTADO`, `TZ`) con su valor por
> defecto y para qué sirve cada una.

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
