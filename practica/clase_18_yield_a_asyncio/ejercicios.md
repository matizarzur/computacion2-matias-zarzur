# Clase 18: De yield a asyncio - Ejercicios Prácticos

Los archivos `scheduler.py`, `puente.py` y `comparar.py` acompañan la clase.

---

## Ejercicio 1: Generadores que reciben

Repaso del bloque 0, con lo que hace falta para lo que sigue.

### 1.1 send()

```python
def acumulador():
    total = 0
    while True:
        n = yield total
        total += n

a = acumulador()
```

1. ¿Qué pasa si hacés `a.send(10)` sin llamar antes a `next(a)`? Probalo y leé el error.
2. Después del `next(a)` inicial, ¿qué devuelve? ¿Por qué ese valor?
3. Hacé tres `send()` seguidos y explicá de dónde sale cada resultado.

### 1.2 El estado sobrevive

```python
def contador():
    n = 0
    while True:
        print(f'  voy por {n}')
        yield
        n += 1
```

4. Creá dos generadores de `contador()` y alterná `next()` entre ellos. ¿Comparten el `n`?
5. ¿Dónde vive ese `n` mientras el generador está suspendido? Compará con una variable local de una función común.

### 1.3 StopIteration lleva el resultado

```python
def tarea():
    yield 'trabajando'
    return 'resultado final'

t = tarea()
next(t)
try:
    next(t)
except StopIteration as e:
    print(e.value)
```

6. ¿Qué imprime? ¿Por qué el `return` de un generador no se obtiene como en una función normal?
7. ¿Cómo usó nuestro scheduler esta excepción?

---

## Ejercicio 2: Construir el scheduler (obligatorio)

### Objetivo

Escribir un event loop cooperativo desde cero, y entender qué garantiza y qué no.

### Parte A: el intercalado

Escribí **vos** el scheduler de la clase, sin copiarlo:

```python
from collections import deque

def tarea(nombre, pasos):
    # TODO: imprimir cada paso y ceder el control

def scheduler(tareas):
    pendientes = deque(tareas)
    while pendientes:
        # TODO: sacar una, reanudarla, y decidir si vuelve a la cola
```

1. Corrélo con tres tareas de distinta cantidad de pasos. ¿En qué orden salen?
2. ¿Cuántas veces llamó a `next()` en total? Agregá un contador.
3. ¿Qué pasa si una tarea no tiene ningún `yield`? Probalo.

### Parte B: la cooperación es obligatoria

Agregá una tarea que no ceda nunca:

```python
def tarea_egoista(nombre):
    print(f'  [{nombre}] me pongo a calcular')
    import time
    time.sleep(3)              # no cede el control
    print(f'  [{nombre}] listo')
    yield
```

4. Metela entre las otras y corré el scheduler. ¿Qué les pasa a las demás durante esos 3 segundos?
5. Con threads (clase 10), ¿habría pasado lo mismo? Explicá la diferencia entre concurrencia cooperativa y preventiva.
6. ¿Cómo se llama esta regla? Relacionalo con lo que vimos en la clase 17 sobre el event loop.

### Parte C: agregar tiempo

Extendé el scheduler para que entienda esperas, como en `scheduler.py --tiempo`.

7. Implementá `dormir(segundos)` que ceda informando cuándo quiere volver.
8. ¿Por qué `dormir()` no puede simplemente llamar a `time.sleep()`?
9. Corré tres tareas que esperen 0.15s cada una, varias veces. ¿El total es la suma de las esperas o menos? ¿Por qué?

### Parte D: yield from

10. En `tarea_lenta`, ¿qué hace `yield from dormir(espera)`? ¿Por qué no alcanza con llamar `dormir(espera)` a secas?
11. Probá cambiarlo por `dormir(espera)` sin el `yield from`. ¿Qué pasa y por qué no falla ruidosamente?

---

## Ejercicio 3: El puente a async/await

```bash
python3 puente.py
```

1. En la parte 2, ¿qué tipo de objeto devuelve una función `async def` al llamarla? ¿Se ejecutó algo de su cuerpo?
2. Verificá vos mismo que una corrutina tiene `.send()`:

```python
async def f():
    return 99

c = f()
print(hasattr(c, 'send'))
try:
    c.send(None)
except StopIteration as e:
    print(e.value)
```

3. ¿Qué relación tiene eso con el `StopIteration` del ejercicio 1.3?
4. En la parte 3, un `await` opera sobre un generador decorado con `@types.coroutine`. ¿Qué demuestra eso sobre la relación entre las dos sintaxis?
5. Traducí este código viejo a sintaxis moderna:

```python
@asyncio.coroutine
def buscar(id):
    conn = yield from abrir()
    datos = yield from leer(conn, id)
    return datos
```

6. ¿Por qué Python introdujo `async`/`await` si `yield from` ya funcionaba? Nombrá los dos problemas que resolvió.

---

## Ejercicio 4: asyncio de verdad

### 4.1 El equivalente

Reescribí el scheduler de la parte A usando asyncio:

```python
import asyncio

async def tarea(nombre, pasos):
    # TODO

async def main():
    await asyncio.gather(...)

asyncio.run(main())
```

1. ¿Qué reemplaza a tu `deque`? ¿Y a tu `while pendientes`?
2. ¿Qué pasa si te olvidás el `await` delante de `gather`? Probalo.
3. ¿Qué pasa si llamás `asyncio.run()` dos veces seguidas en el mismo programa? (Probalo antes de responder: el resultado puede sorprenderte.) ¿Y si lo llamás *adentro* de una corrutina que ya está corriendo?

### 4.2 Crear no es ejecutar

```python
async def saludar():
    print('hola')

saludar()                     # ¿imprime algo?
asyncio.run(saludar())        # ¿y ahora?
```

4. ¿Qué diferencia hay? ¿Qué aviso da Python en el primer caso?
5. Relacionalo con los generadores: ¿qué pasaba al crear uno sin llamar a `next()`?

### 4.3 gather

6. ¿En qué orden terminan tres corrutinas que duermen 0.3, 0.1 y 0.2 segundos?
7. ¿En qué orden devuelve los resultados `gather`? Verificalo.
8. ¿Cuál es la diferencia entre estos dos?

```python
await asyncio.gather(a(), b(), c())
for f in (a, b, c): await f()
```

Medí los dos con tres corrutinas que duerman 1 segundo.

---

## Ejercicio 5: Cuándo sirve y cuándo no

```bash
python3 comparar.py
```

1. Copiá los números que te dio. ¿Cuánto mejora asyncio en I/O-bound?
2. La versión con `time.sleep()` adentro de una corrutina, ¿cuánto tarda? ¿Por qué no mejora nada?
3. En CPU-bound, ¿asyncio mejora, empeora o da igual? Explicá el resultado.
4. Si asyncio no ayuda con CPU, ¿por qué el overhead lo hace incluso un poco más lento?
5. Escribí la regla en una frase: ¿cuándo conviene asyncio?
6. Relacionalo con el GIL de la clase 10. ¿Es el mismo criterio de decisión?

### 5.1 Encontrar el bloqueo

Este código parece asíncrono pero no lo es:

```python
import asyncio, urllib.request

async def bajar(url):
    return urllib.request.urlopen(url).read()      # ¿dónde está el problema?

async def main():
    await asyncio.gather(*(bajar('http://example.com') for _ in range(5)))
```

7. ¿Por qué las cinco descargas no se solapan?
8. ¿Qué habría que usar en lugar de `urllib.request`?
9. Enumerá tres llamadas bloqueantes comunes que no hay que usar adentro de una corrutina.

---

## Verificación del ejercicio obligatorio

### Ejercicio 2: Construir el scheduler

- [ ] Scheduler que intercala tareas, escrito por vos
- [ ] Contador de reanudaciones
- [ ] Probaste qué pasa con una tarea que no cede, y lo explicaste
- [ ] Explicaste la diferencia entre concurrencia cooperativa y preventiva
- [ ] Implementaste `dormir()` cediendo el control, sin `time.sleep()`
- [ ] Mediste que las esperas se solapan
- [ ] Explicaste qué hace `yield from` y qué pasa si se omite

---

## Ejercicios adicionales

### Scheduler con prioridades

Modificá el scheduler para que algunas tareas se reanuden más seguido que otras. ¿Qué estructura conviene en lugar de la `deque`?

### Detectar tareas egoístas

Agregale al scheduler una medición: cuánto tardó cada reanudación. Si una tarea tarda más de cierto umbral sin ceder, avisar por pantalla. Es lo que hace `loop.set_debug(True)` en asyncio.

### El pipeline de generadores

Armá una cadena de tres generadores donde cada uno procese lo que le manda el anterior con `send()`: uno que lea líneas, uno que filtre, uno que cuente. Es el patrón de *coroutine pipeline* previo a asyncio.

### Leer el fuente

Buscá `types.coroutine` en la biblioteca estándar y mirá dónde lo usa asyncio. ¿Por qué la propia biblioteca necesita ese puente?
