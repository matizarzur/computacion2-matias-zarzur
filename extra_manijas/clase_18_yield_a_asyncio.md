# Clase 18: De yield a asyncio - Extra Manijas

Material opcional para profundizar.

---

## La historia, en orden

El camino de `yield` a `async` tomó quince años y cuatro PEPs. Vale la pena verlo porque cada paso resolvió una limitación concreta del anterior.

**PEP 255 (2001) — generadores.** Aparece `yield`. Son iteradores perezosos: producen valores de a uno sin calcular todo. No pueden recibir nada.

**PEP 342 (2005) — `send()`.** `yield` pasa a ser una expresión que devuelve lo que le mandan. El título del PEP es explícito: *"Coroutines via Enhanced Generators"*. Ya se podían escribir corrutinas, pero a mano y con mucha ceremonia.

**PEP 380 (2009) — `yield from`.** Permite delegar en otro generador sin escribir el bucle de reenvío, y propaga correctamente excepciones y valores de retorno. Sin esto, componer tareas era impracticable.

**PEP 3156 (2012) — asyncio.** Guido escribe la biblioteca, apoyada en generadores y `yield from`. Su nombre en desarrollo era *Tulip*.

**PEP 492 (2015) — `async`/`await`.** Sintaxis propia. No agrega capacidades: agrega claridad, y convierte los olvidos silenciosos en errores visibles.

Cuando leas código de 2014 con `@asyncio.coroutine` y `yield from`, estás viendo la etapa previa. Funciona igual, pero está deprecado desde 3.8 y se eliminó en 3.11.

---

## Qué es un awaitable

`await` no funciona sobre cualquier cosa. Necesita un **awaitable**, que es uno de estos tres:

**Una corrutina**, lo que devuelve llamar a una `async def`.

**Un objeto con `__await__()`** que devuelva un iterador. Así se integran bibliotecas propias con asyncio:

```python
class MiEspera:
    def __await__(self):
        yield 'lo que el loop reciba'
        return 'resultado'

async def usar():
    r = await MiEspera()
```

**Un `Future` o `Task`**, que son los objetos con los que asyncio representa "algo que va a tener un resultado".

Ese `yield` adentro de `__await__` es el mismo mecanismo de siempre: lo que se cede sube hasta el event loop, y lo que el loop manda con `send()` vuelve como valor de la expresión.

---

## Task contra corrutina

Una distinción que confunde y que importa en el TP2:

```python
async def trabajo():
    await asyncio.sleep(1)
    return 'listo'

# Esto NO empieza a correr todavía
c = trabajo()

# Esto SÍ: la programa en el loop
t = asyncio.create_task(trabajo())
```

Una **corrutina** es una descripción de trabajo, inerte hasta que alguien la ejecute. Una **Task** es una corrutina ya entregada al event loop, que empieza a avanzar en cuanto el loop tenga un turno libre.

De ahí sale una diferencia práctica:

```python
# Secuencial: cada await espera a que termine
await trabajo()
await trabajo()                # total: 2 segundos

# Concurrente: las dos ya están corriendo
t1 = asyncio.create_task(trabajo())
t2 = asyncio.create_task(trabajo())
await t1
await t2                       # total: 1 segundo
```

`gather()` hace esto por vos: envuelve cada corrutina en una Task antes de esperar.

**Y un peligro:** si creás una Task y no guardás la referencia, el recolector de basura puede llevársela antes de que termine. La documentación recomienda guardarlas en un conjunto:

```python
tareas = set()

t = asyncio.create_task(trabajo())
tareas.add(t)
t.add_done_callback(tareas.discard)
```

---

## Cancelación

Asyncio puede cancelar una tarea en curso, y el mecanismo es elegante: **inyecta una excepción en el punto de suspensión**.

```python
t = asyncio.create_task(trabajo())
await asyncio.sleep(0.5)
t.cancel()

try:
    await t
except asyncio.CancelledError:
    print('cancelada')
```

Lo que ocurre por dentro es que, en el próximo `await`, en vez de recibir un resultado la corrutina recibe un `CancelledError`. Por eso la cancelación **solo puede ocurrir en un punto de suspensión**: una corrutina que se puso a calcular sin ceder no se puede cancelar hasta que llegue a su próximo `await`.

Eso permite limpiar con `try/finally`:

```python
async def trabajo():
    recurso = abrir()
    try:
        await algo_largo()
    finally:
        recurso.close()        # corre aunque la cancelen
```

Desde Python 3.8, `CancelledError` hereda de `BaseException` y no de `Exception`, justamente para que un `except Exception:` distraído no se la coma sin querer.

El TP2 pide cancelación limpia, así que este mecanismo es el que van a necesitar.

---

## TaskGroup: lo moderno

Desde Python 3.11 hay una forma mejor que `gather()`:

```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(trabajo('a'))
    tg.create_task(trabajo('b'))
# al salir del with, todas terminaron
```

La ventaja sobre `gather()` es el manejo de errores. Con `gather()`, si una corrutina falla las demás siguen corriendo huérfanas salvo que pidas `return_exceptions`. Con `TaskGroup`, si una falla **se cancelan todas las hermanas** y el error se propaga.

Es un patrón que se llama *structured concurrency*: las tareas viven dentro de un bloque y no lo sobreviven, igual que las variables locales viven dentro de una función. Lo popularizó la biblioteca Trio y asyncio lo adoptó.

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(puede_fallar())
        tg.create_task(otra())
except* ValueError as eg:            # sintaxis de grupos de excepciones
    print('falló alguna:', eg.exceptions)
```

Ese `except*` es para `ExceptionGroup`, porque pueden fallar varias a la vez.

---

## El loop por dentro

Se puede espiar lo que hace asyncio:

```python
import asyncio

async def main():
    loop = asyncio.get_running_loop()
    print(type(loop).__name__)              # _UnixSelectorEventLoop en Linux
    print(loop.time())                      # su reloj monotónico

asyncio.run(main())
```

Ese nombre —`_UnixSelectorEventLoop`— delata la conexión con la clase 17: usa el módulo `selectors` —o sea `epoll` en Linux— para dormir hasta que algún descriptor esté listo. Es literalmente el bucle que escribimos ahí, con corrutinas encima en vez de callbacks.

El modo debug avisa de corrutinas que tardan demasiado sin ceder:

```python
asyncio.run(main(), debug=True)
```

```
Executing <Task ...> took 0.512 seconds
```

Es la instrumentación que en la clase 17 escribimos a mano midiendo cada vuelta del bucle.

---

## Corrutinas antes de asyncio: el pipeline

`send()` habilitó un patrón que se usó mucho antes de que existiera asyncio: pipelines de procesamiento donde cada etapa recibe del anterior.

```python
def coroutine(fn):
    """Decorador que hace el next() inicial por vos."""
    def arrancar(*args, **kwargs):
        g = fn(*args, **kwargs)
        next(g)
        return g
    return arrancar

@coroutine
def imprimir():
    while True:
        item = yield
        print(f'  -> {item}')

@coroutine
def filtrar(patron, destino):
    while True:
        item = yield
        if patron in item:
            destino.send(item)

@coroutine
def normalizar(destino):
    while True:
        item = yield
        destino.send(item.strip().lower())

# Se arma al revés: del final hacia el principio
pipeline = normalizar(filtrar('error', imprimir()))

for linea in ['  ERROR: falló  ', 'info: ok', 'Error en disco']:
    pipeline.send(linea)
```

Cada etapa es un generador suspendido esperando datos, y `send()` los empuja por la cadena. Es *push* en vez de *pull*: al revés de un `for` sobre generadores encadenados.

David Beazley dio una charla célebre sobre esto en 2009 (*A Curious Course on Coroutines and Concurrency*) que vale la pena si el tema les interesó.

---

## Lecturas

- [PEP 492](https://peps.python.org/pep-0492/) - `async`/`await`, con la justificación completa
- [PEP 342](https://peps.python.org/pep-0342/) - `send()`, el que empezó todo
- [PEP 380](https://peps.python.org/pep-0380/) - `yield from`
- [How the heck does async/await work in Python?](https://snarky.ca/how-the-heck-does-async-await-work-in-python-3-5/) - Brett Cannon
- [A Curious Course on Coroutines and Concurrency](http://www.dabeaz.com/coroutines/) - David Beazley, 2009
- [Trio](https://trio.readthedocs.io/) - la biblioteca que popularizó la concurrencia estructurada
- [`asyncio`](https://docs.python.org/3/library/asyncio.html) - documentación oficial

---

*Computación II - 2026 - Clase 18*
