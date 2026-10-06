# Clase 18: De yield a asyncio - Autoevaluación

> Completá esta autoevaluación **después** de leer el contenido y hacer los ejercicios.
> No mires las respuestas antes de intentarlo.

---

## Parte 1: Generadores

**Pregunta 1.** ¿Qué distingue a un generador de una función común?

a) Es más rápido
b) Se suspende en cada `yield` y conserva su estado
c) No puede recibir argumentos
d) Corre en otro hilo

**Pregunta 2.** Un generador está suspendido en un `yield`. ¿Qué pasa con sus variables locales?

a) Se pierden
b) Siguen vivas: el generador retoma exactamente donde iba
c) Se copian a una variable global
d) Se guardan en disco

**Pregunta 3.** ¿Qué hace `.send(valor)`?

a) Manda el generador a otro proceso
b) Reanuda el generador e inyecta `valor` como resultado de la expresión `yield`
c) Agrega un elemento a la secuencia
d) Termina el generador

**Pregunta 4.** ¿Por qué hay que llamar a `next()` antes del primer `send()`?

a) Por convención
b) Porque un generador recién creado no ejecutó nada: hay que llevarlo hasta el primer `yield`
c) Para inicializar la memoria
d) No hace falta

**Pregunta 5.** ¿Qué pasa si hacés `send()` sobre un generador recién creado?

a) Funciona igual
b) Lanza `TypeError`
c) Devuelve `None`
d) Lanza `StopIteration`

**Pregunta 6.** Un generador hace `return 'listo'`. ¿Cómo se obtiene ese valor?

a) Como valor de retorno de `next()`
b) En el atributo `.value` de la excepción `StopIteration`
c) No se puede obtener
d) Con un `yield` final

**Pregunta 7.** ¿Qué hace `yield from otro_generador()`?

a) Copia los valores a una lista
b) Delega en el otro generador: sus `yield` suben al llamador
c) Ejecuta el otro generador en paralelo
d) Es solo azúcar para un `for`

---

## Parte 2: El scheduler cooperativo

**Pregunta 8.** En el scheduler de la clase, ¿qué representa cada elemento de la cola?

a) Un thread
b) Un generador suspendido, o sea una tarea
c) Un socket
d) Un proceso

**Pregunta 9.** ¿Cómo sabe el scheduler que una tarea terminó?

a) La tarea devuelve `False`
b) El generador lanza `StopIteration`
c) La cola queda vacía
d) Con un timeout

**Pregunta 10.** ¿Qué significa que la concurrencia sea **cooperativa**?

a) Que las tareas se comunican entre sí
b) Que cada tarea decide cuándo ceder el control, escribiendo `yield`
c) Que el sistema operativo reparte el tiempo
d) Que se usan varios procesadores

**Pregunta 11.** ¿Cuál es la diferencia con los threads del sistema operativo?

a) Ninguna
b) Los threads son preventivos: el kernel los interrumpe sin pedir permiso
c) Los threads son más lentos
d) Los threads no pueden suspenderse

**Pregunta 12.** Una tarea se pone a calcular durante tres segundos sin ceder. ¿Qué pasa con las demás?

a) Siguen corriendo en paralelo
b) Quedan congeladas esos tres segundos
c) Pasan a otro hilo automáticamente
d) El scheduler las cancela

**Pregunta 13.** En el scheduler con tiempo, ¿qué hace la función `dormir()`?

a) Llama a `time.sleep()`
b) Cede el control informando en qué instante quiere ser reanudada
c) Bloquea el hilo por N segundos
d) Cancela la tarea

**Pregunta 14.** ¿Por qué `dormir()` no puede usar `time.sleep()`?

a) Porque es impreciso
b) Porque bloquearía el hilo único y ninguna otra tarea podría correr
c) Porque no funciona en generadores
d) Porque consume mucha memoria

---

## Parte 3: async y await

**Pregunta 15.** ¿Qué relación hay entre `async def` y los generadores?

a) Ninguna, son mecanismos independientes
b) `async def` es sintaxis propia para lo que antes se hacía con generadores y `yield from`
c) `async def` usa threads por debajo
d) Los generadores son más modernos

**Pregunta 16.** ¿A qué equivale `await algo`?

a) A `time.sleep()`
b) A `yield from algo` en la sintaxis vieja
c) A un `return`
d) A lanzar un thread

**Pregunta 17.** ¿Qué devuelve llamar a una función `async def`?

a) El resultado de su cuerpo
b) Un objeto corrutina, sin ejecutar nada todavía
c) Un generador
d) `None`

**Pregunta 18.** ¿Tiene `.send()` una corrutina?

a) No, eso es solo de generadores
b) Sí: es el mismo mecanismo de suspensión
c) Solo si se la decora
d) Solo en Python 2

**Pregunta 19.** ¿Cómo devuelve su resultado una corrutina cuando se la maneja a mano?

a) Con `return` normal
b) En `StopIteration.value`, igual que un generador
c) Por una variable global
d) No se puede

**Pregunta 20.** ¿Por qué Python introdujo `async`/`await` si `yield from` ya servía?

a) Por moda
b) Porque `yield from` era ambiguo y era fácil olvidarlo sin que fallara ruidosamente
c) Porque `yield from` era lento
d) Para copiar a JavaScript

**Pregunta 21.** ¿Qué pasa si llamás una corrutina y no la esperás con `await`?

a) Se ejecuta igual
b) No se ejecuta, y Python avisa con `coroutine ... was never awaited`
c) Lanza una excepción inmediata
d) Se ejecuta en otro hilo

---

## Parte 4: asyncio

**Pregunta 22.** ¿Qué hace `asyncio.run(main())`?

a) Crea un thread por corrutina
b) Crea el event loop, corre la corrutina hasta terminar, y cierra todo
c) Registra la corrutina para después
d) Es equivalente a `await`

**Pregunta 23.** ¿Cuántas veces debería aparecer `asyncio.run()` en un programa?

a) Una por corrutina
b) Una sola, como punto de entrada
c) Ninguna
d) Las que hagan falta

**Pregunta 24.** ¿Qué hace `asyncio.gather(a(), b(), c())`?

a) Las corre una después de otra
b) Lanza las tres y espera a que todas terminen, permitiendo que se intercalen
c) Devuelve la primera que termine
d) Crea tres threads

**Pregunta 25.** Tres corrutinas duermen 0.3, 0.1 y 0.2 segundos. ¿En qué orden devuelve los resultados `gather`?

a) En el orden en que terminaron
b) En el orden de los argumentos
c) Al azar
d) Ordenados por duración

**Pregunta 26.** ¿Por qué `time.sleep(1)` dentro de una corrutina es un bug?

a) Porque es impreciso
b) Porque no cede el control: bloquea el hilo único y congela todas las tareas
c) Porque lanza excepción
d) No es un bug

**Pregunta 27.** ¿Qué hay que usar en su lugar?

a) `asyncio.sleep(1)` con `await`
b) `threading.sleep(1)`
c) Un `for` vacío
d) `os.wait()`

**Pregunta 28.** ¿Qué pasa si llamás `asyncio.run()` dentro de una corrutina que ya está corriendo?

a) Funciona normalmente
b) Lanza `RuntimeError`: no se puede desde un loop en marcha
c) Crea un segundo loop
d) Se ignora

---

## Parte 5: Cuándo sirve

**Pregunta 29.** ¿Para qué tipo de trabajo sirve asyncio?

a) CPU-bound
b) I/O-bound: cuando el programa pasa el tiempo esperando
c) Los dos por igual
d) Ninguno, es solo sintaxis

**Pregunta 30.** Tres tareas que esperan un segundo cada una, con `asyncio.gather`. ¿Cuánto tarda?

a) ~3 segundos
b) ~1 segundo
c) ~0.3 segundos
d) Depende de los cores

**Pregunta 31.** Las mismas tres tareas, pero calculando un segundo cada una. ¿Cuánto tarda con asyncio?

a) ~1 segundo
b) ~3 segundos o un poco más
c) Menos que secuencial
d) Depende de los cores

**Pregunta 32.** ¿Por qué en CPU-bound asyncio puede ser incluso un poco más lento?

a) Por el GIL
b) Por el overhead del event loop, sin ninguna ventaja que lo compense
c) Porque usa más memoria
d) No es más lento

**Pregunta 33.** ¿Con qué distinción de la clase 10 se corresponde este criterio?

a) Con procesos contra threads
b) Con I/O-bound contra CPU-bound, la misma que decide si el GIL importa
c) Con locks contra semáforos
d) Con TCP contra UDP

**Pregunta 34.** Este código usa `urllib.request.urlopen()` dentro de una corrutina. ¿Qué pasa?

a) Las descargas se solapan normalmente
b) No se solapan: `urlopen` es bloqueante y congela el loop
c) Lanza excepción
d) Se ejecuta en otro thread automáticamente

---

## Respuestas

<details>
<summary>Ver respuestas (intentá primero)</summary>

| # | Respuesta | Comentario |
|---|-----------|------------|
| 1 | b | Se suspende y recuerda dónde iba |
| 2 | b | Por eso sirve como tarea suspendible |
| 3 | b | `yield` funciona en las dos direcciones |
| 4 | b | Hay que llevarlo hasta el primer `yield` |
| 5 | b | `TypeError`, verificado en el ejercicio |
| 6 | b | `StopIteration.value` |
| 7 | b | Delega, y permite componer tareas |
| 8 | b | Un generador suspendido |
| 9 | b | `StopIteration` |
| 10 | b | Cada tarea decide cuándo ceder |
| 11 | b | Preventivo contra cooperativo |
| 12 | b | La regla de oro del event loop |
| 13 | b | Informa cuándo volver, no duerme |
| 14 | b | Bloquearía el hilo único |
| 15 | b | Es azúcar sintáctica sobre lo mismo |
| 16 | b | `await` es `yield from` |
| 17 | b | Crear no es ejecutar |
| 18 | b | Verificable con `hasattr(c, 'send')` |
| 19 | b | El mismo mecanismo del scheduler |
| 20 | b | Ambigüedad y olvidos silenciosos |
| 21 | b | `coroutine ... was never awaited` |
| 22 | b | Crea el loop, corre y cierra |
| 23 | b | Una sola, como punto de entrada |
| 24 | b | Las intercala y espera a todas |
| 25 | b | Orden de argumentos, no de terminación |
| 26 | b | No cede el control |
| 27 | a | `await asyncio.sleep(1)` |
| 28 | b | `RuntimeError`, verificado |
| 29 | b | I/O-bound |
| 30 | b | Las esperas se solapan |
| 31 | b | El trabajo es real: no hay ganancia |
| 32 | b | Overhead sin contrapartida |
| 33 | b | La misma distinción del GIL |
| 34 | b | Bloqueante adentro de una corrutina |

</details>

---

## Resultado de la autoevaluación

| Puntaje | Diagnóstico |
|---------|-------------|
| 30-34 correctas | Excelente. Avanzá a la clase 19 (HTTP + FastAPI) |
| 24-29 | Buen nivel. Repasá los temas donde fallaste |
| 17-23 | Nivel intermedio. Rehacé el ejercicio 2 (el scheduler) |
| < 17 | Repasá el contenido completo. Consultá con el docente antes de la próxima clase |

> Las preguntas 12, 26 y 29 son las que más importan para el TP2: describen el error que más cuesta diagnosticar —una corrutina que bloquea el loop— y el criterio para saber si asyncio es la herramienta adecuada.

---

*Computación II - 2026 - Clase 18*
