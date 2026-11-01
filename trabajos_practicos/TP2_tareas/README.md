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

> **[PENDIENTE]** Hardware y fecha (Intel i5-6200U, 2 núcleos físicos / 4
> hilos, 7,6 GB de RAM, Docker 29.9.1, Python 3.12.16 en el contenedor;
> 31/10/2026), metodología (3 repeticiones con el contenedor recreado,
> mediana, tiempos tomados de las marcas del servidor) y cómo reproducirlas.
> Resultados crudos en `medicion/resultados/`.

### 5.1 Concurrencia de I/O: 20 descargas secuenciales contra concurrentes

> **[PENDIENTE]**

### 5.2 El event loop bloqueado

> **[PENDIENTE]**

### 5.3 El techo del pool

> **[PENDIENTE]**

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
  el máximo medido fue de unos 410 `POST`/s con la API al 67% de CPU, y con
  más clientes no sube porque se satura la máquina, no el servicio. Para medir
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
