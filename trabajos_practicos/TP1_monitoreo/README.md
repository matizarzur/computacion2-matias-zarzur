# Monitor de Procesos y Threads de Linux

**Trabajo Práctico Nº 1 — Computación II — Universidad de Mendoza — 2026**

Autor: Matías Zarzur

---

## 1. Descripción general

Este proyecto es un monitor del sistema en tiempo real, parecido a `htop`, con
énfasis en mostrar la anatomía interna de cada proceso y sus threads. Toda la
información se extrae leyendo el pseudo-filesystem `/proc` directamente, sin usar
`psutil` ni herramientas externas como `ps` o `top`.

El monitor es un sistema multiproceso: un recolector central lista los procesos,
distribuye el trabajo entre siete analizadores especializados que corren en
paralelo, un agregador consolida los resultados en un snapshot compartido, y una
interfaz de texto (TUI) muestra los datos con siete vistas alternables.

Se ejecuta dentro de un contenedor Docker configurado para poder leer los
procesos del host.

### Uso rápido

```bash
docker compose up --build -d
docker compose exec -it monitor bash
cd /app
python3 src/main.py
```

Una vez dentro de la TUI, se cambia de vista con las teclas `1`-`7` (o las
letras `r/m/f/t/s/p/g`) y se sale con `q`. Con `h` o `?` se muestra la ayuda
con todas las teclas disponibles.

---

## 2. Arquitectura

El sistema está compuesto por 10 procesos que colaboran:

```
                       ┌─────────────────────────────┐
                       │      RECOLECTOR             │
                       │  lista PIDs de /proc y los  │
                       │  reparte a todas las colas  │
                       └──────────────┬──────────────┘
                                      │ (un PID en cada cola)
        ┌──────────┬──────────┬───────┼───────┬──────────┬──────────┐
        ▼          ▼          ▼       ▼       ▼          ▼          │
   ┌─────────┐┌─────────┐┌────────┐┌───────┐┌────────┐┌──────────┐ │
   │Resumen  ││Memoria  ││FDs     ││Threads││Señales ││Scheduling│ │
   │(status) ││(status) ││(fd/)   ││(task/)││(status)││(stat)    │ │
   └────┬────┘└────┬────┘└───┬────┘└───┬───┘└───┬────┘└────┬─────┘ │
        │          │         │         │        │          │       │
        └──────────┴─────────┴────┬────┴────────┴──────────┘       │
                                  │                                 │
                          ┌───────▼────────┐   ┌────────────────────▼──┐
                          │ cola_resultados│◄──│ SISTEMA               │
                          └───────┬────────┘   │ (info global, no PID) │
                                  │            └───────────────────────┘
                          ┌───────▼────────┐
                          │   AGREGADOR    │
                          │ consolida el   │
                          │   snapshot     │
                          └───────┬────────┘
                                  │
                          ┌───────▼────────────────┐
                          │  snapshot (Manager.dict)│
                          └───────┬────────────────┘
                                  │ lee
                          ┌───────▼────────┐
                          │   DISPLAY TUI  │
                          │ (proceso main) │
                          └────────────────┘
```

Componentes:

- **Recolector**: lista los PIDs de `/proc` cada N segundos y los encola en la
  cola de cada analizador por-PID. Antes de cada pasada envía un mensaje
  `nueva_pasada` al agregador para que limpie los procesos que murieron.
- **6 analizadores por-PID**: cada uno toma un PID de su cola, lee una dimensión
  específica de `/proc/<pid>/*`, y publica el resultado en `cola_resultados`.
  Comparten la misma plantilla común (`analizadores/plantilla.py`).
- **1 analizador de Sistema**: no procesa PIDs; tiene su propio loop temporal y
  lee los archivos globales de `/proc` (`meminfo`, `loadavg`, `uptime`, `stat`).
- **Agregador**: consumidor único de `cola_resultados`. Consolida los datos en el
  snapshot compartido.
- **Display**: corre en el proceso principal, lee el snapshot y lo renderiza con
  `rich`. Un thread separado escucha el teclado.

Total: main (que corre el display) + recolector + 6 analizadores por-PID +
analizador de sistema + agregador + el proceso interno del Manager = 10 procesos.

La comunicación usa dos mecanismos de `multiprocessing`:
- **`Queue`** para pasar trabajo (PIDs) y resultados entre procesos.
- **`Manager.dict`** como snapshot compartido que el display lee.

---

## 3. Las siete vistas

El monitor tiene siete vistas alternables, cada una alimentada por su analizador:

1. **Resumen** (`1`/`r`): PID, usuario (resuelto desde el UID), estado, RSS,
   threads y comando completo (`cmdline`). Es la vista central: soporta
   navegación, filtros, orden y pin (ver sección 4).
2. **Memoria** (`2`/`m`): desglose de memoria por proceso en MB — VmSize, RSS,
   HWM (pico histórico), Data, Stk, Lib, Swap — más los page faults menores y
   mayores.
3. **FDs** (`3`/`f`): file descriptors por proceso, con la cantidad total, el
   desglose por tipo (file, socket, pipe, tty, anon, device) y ejemplos de
   destinos resueltos con `readlink`.
4. **Threads** (`4`/`t`): los threads (LWPs) de cada proceso leídos de
   `/proc/<pid>/task/`.
5. **Señales** (`5`/`s`): las cinco máscaras de señales de cada proceso
   (pendientes, pendientes compartidas, bloqueadas, ignoradas, con handler),
   mostradas como cantidad. Al pinear un proceso (Enter en Resumen) se ve el
   detalle completo con los nombres de señales decodificados.
6. **Scheduling** (`6`/`p`): prioridad, nice, política de scheduling, tiempos de
   CPU (utime/stime) de `/proc/<pid>/stat`.
7. **Sistema** (`7`/`g`): información global — CPU acumulada, memoria, load
   average, uptime, context switches y contadores de `/proc/stat`.

---

## 4. Interacción con el teclado

El monitor se controla enteramente por teclado. Las teclas se leen en un thread
separado con `select()` para no bloquear el refresco:

- **`1`-`7`** o `r/m/f/t/s/p/g`: cambiar de vista.
- **Flechas arriba/abajo**: navegar por la lista de procesos (vista Resumen).
- **`Enter`**: fijar (pin) o soltar el proceso seleccionado. El proceso pineado
  se resalta y, en la vista Señales, se muestra su detalle completo.
- **`c`**: cambiar el criterio de orden de la vista Resumen (PID / RSS / Threads).
- **`/`**: filtrar la vista Resumen por nombre de comando.
- **`u`**: filtrar la vista Resumen por UID.
- **`+` / `-`**: ajustar en tiempo real el intervalo de refresco de la vista
  activa (ver la nota sobre `Value` en la sección 5).
- **`h` / `?`**: mostrar u ocultar el panel de ayuda.
- **`q`**: salir (shutdown limpio).

---

## 5. Decisiones de diseño

### ¿Por qué una cola por analizador y no una cola compartida?

Al principio todos los analizadores tomaban PIDs de una única cola compartida.
El problema es que en una cola compartida cada ítem lo consume **un solo**
proceso: si el recolector encolaba el PID 1234, lo agarraba Resumen O Memoria,
pero no ambos. El resultado eran vistas incompletas.

La solución fue darle a cada analizador **su propia cola**. El recolector encola
cada PID en todas las colas, de modo que todos los analizadores ven todos los
procesos y los analizan en paralelo, a su propio ritmo.

### ¿Por qué `Manager.dict` y no `Value`/`Array`?

El snapshot es una estructura de datos compleja y anidada: un diccionario de
tipos (`resumen`, `memoria`, ...), cada uno conteniendo un diccionario indexado
por PID, con dataclasses adentro. `Value` y `Array` solo sirven para tipos
simples (un entero, un float, un array de tipo fijo). Para una estructura
dinámica y anidada como esta, `Manager.dict` es la herramienta adecuada: expone
un diccionario compartido entre procesos, aunque a costa de ser más lento (cada
acceso pasa por un proceso servidor y se serializa).

### ¿Por qué `Value` para los intervalos ajustables?

Los intervalos de refresco del recolector y del analizador de sistema son
`multiprocessing.Value` compartidos. Cuando el usuario aprieta `+`/`-` en el
display, este modifica el `Value`, y el proceso correspondiente lee el nuevo
valor en cada vuelta de su loop. Se usa `Value` (y no pasar un número) porque un
número se copia al crear el proceso hijo, quedando como variables independientes;
el `Value` vive en memoria compartida, así que ambos procesos ven el mismo dato.
Es el mecanismo correcto para un dato simple (un float) que se comparte entre dos
procesos. También se usa `Value` para el flag de modo verbose.

### ¿Cómo se manejan las race conditions?

La escritura al snapshot está **centralizada en un único proceso**: el agregador.
Ningún analizador escribe directo al snapshot; todos publican en `cola_resultados`
y el agregador es el único que consume esa cola y escribe. Al haber un solo
escritor, no hay dos procesos compitiendo por escribir la misma clave al mismo
tiempo.

Hay un detalle técnico con `Manager.dict`: las modificaciones a sub-estructuras
anidadas no se propagan automáticamente. Si uno hace
`snapshot["resumen"][pid] = datos`, el cambio en el sub-diccionario no se
detecta. Por eso el agregador usa un patrón de leer-modificar-reasignar: toma el
sub-diccionario, lo modifica localmente, y lo reasigna completo
(`snapshot["resumen"] = sub_dict`), lo que sí dispara la propagación.

### ¿Por qué el ordenamiento y los filtros solo en Resumen?

La navegación, el ordenamiento configurable y los filtros operan solo sobre la
vista Resumen, que es la vista "central" con una fila por proceso. Las otras
vistas muestran datos de dimensiones distintas (memoria, señales, FDs) donde
ordenar por "threads" o filtrar no tiene el mismo sentido, así que se mantienen
con orden estable por PID. Es una decisión de coherencia: la vista Resumen es la
de exploración, las demás son de inspección.

### ¿Por qué los intervalos por defecto de 2 segundos?

El recolector y el analizador de sistema refrescan cada 2 segundos por defecto,
configurable desde `config.json` y ajustable en runtime con `+`/`-`. Dos segundos
es un equilibrio entre ver cambios razonablemente rápido y no saturar la CPU
releyendo `/proc` constantemente.

---

## 6. Conceptos del curso aplicados

- **`/proc` como pseudo-filesystem (clase 3)**: todo el proyecto se basa en que
  `/proc` es virtual, generado por el kernel al vuelo. Las funciones de
  `procfs.py` leen `/proc/<pid>/status`, `/stat`, `/maps`, `/fd/`, `/task/`, etc.

- **PID vs TID / threads como LWPs (clase 10)**: la vista Threads lista los TIDs
  leyendo `/proc/<pid>/task/`, donde cada subcarpeta es un thread (Light Weight
  Process). El TID del primer thread coincide con el PID del proceso.

- **Señales y máscaras (clase 6)**: la vista Señales decodifica las máscaras de
  bits de `/proc/<pid>/status` (SigBlk, SigIgn, SigCgt, etc.) a nombres legibles.
  Cada bit de la máscara representa una señal: el bit N corresponde a la señal
  N+1. Se recorren los bits con operaciones AND (`mascara & (1 << bit)`) y se
  traduce el número al nombre con el módulo `signal`.

- **File descriptors como symlinks (clase 3)**: la vista FDs usa `os.readlink`
  sobre `/proc/<pid>/fd/<n>` para leer a dónde apunta cada descriptor sin abrir
  el destino, y clasifica el tipo según el prefijo (socket:, pipe:, /dev/...).

- **cmdline y bytes nulos**: el comando completo se lee de `/proc/<pid>/cmdline`,
  donde los argumentos vienen separados por bytes nulos (`\0`) que se reemplazan
  por espacios. Los procesos kernel tienen cmdline vacío y se muestran con el
  nombre entre corchetes.

- **Señales y async-signal-safety (clase 6)**: el monitor maneja SIGINT, SIGTERM,
  SIGHUP, SIGUSR1 y SIGUSR2. Los handlers son mínimos: solo levantan un flag
  (`Event`), y el loop principal actúa sobre ese flag en un punto seguro. Esto
  evita corromper estado o generar deadlocks al ser interrumpido en cualquier
  instrucción.

- **Pipes / IPC (clase 5) y Multiprocessing (clases 8-9)**: la comunicación entre
  procesos usa `Queue` (buffer sincronizado con locks internos), `Manager.dict`
  (memoria compartida cliente-servidor) y `Value` (memoria compartida para tipos
  simples).

- **TOCTOU (time-of-check-to-time-of-use)**: un proceso puede morir entre el
  momento en que el recolector lo lista y el momento en que un analizador intenta
  leer su `/proc/<pid>/*`. Por eso todas las funciones de lectura por-PID capturan
  `FileNotFoundError` y `PermissionError`. En la resolución de FDs, un descriptor
  puede cerrarse entre el listado y el `readlink`, y se saltea individualmente sin
  descartar el resto.

- **Herencia de handlers en fork (clase 4 + 6)**: los procesos hijos heredan los
  handlers de señales del padre. Como esto impedía que los hijos murieran ante
  SIGTERM en el shutdown, cada hijo restaura los handlers a `SIG_DFL` al arrancar
  (`resetear_handlers_en_hijo`).

---

## 7. Limitaciones conocidas

- **CPU% por proceso**: no se calcula el porcentaje de CPU instantáneo de cada
  proceso. Hacerlo requiere comparar dos lecturas consecutivas de los jiffies
  acumulados (`utime + stime` de `/proc/<pid>/stat`), dividiendo el delta por el
  tiempo transcurrido y por `CLK_TCK`. Eso obliga a mantener estado entre pasadas
  (un historial `{pid: (jiffies, timestamp)}`). Todos los analizadores del monitor
  son deliberadamente **sin estado** —leen `/proc` y publican el dato—, y meter
  estado en uno solo rompía esa consistencia. Se documenta como mejora futura; el
  mecanismo está entendido y la vista Sistema sí muestra los tiempos de CPU
  globales acumulados.

- **Info detallada por thread**: la vista Threads lista los TIDs pero no expande
  el estado, tiempos de CPU ni context switches individuales de cada thread.

- **Top 3 y zombies en Sistema**: la vista Sistema muestra los contadores globales
  pero no calcula el top 3 de procesos por CPU/memoria ni el conteo de zombies.

- **Límite de filas**: cada vista muestra los primeros 25 procesos para que entre
  en pantalla. Los filtros de la vista Resumen permiten acotar la lista.

---

## 8. Cómo correr y testear

### Requisitos

- Docker y Docker Compose.
- El host debe ser Linux para poder leer sus procesos (el `pid: host` del
  compose usa el namespace de PIDs del host).

### Levantar el monitor

```bash
# Desde la carpeta TP1_monitoreo/
docker compose up --build -d
docker compose exec -it monitor bash

# Ya dentro del contenedor:
cd /app
python3 src/main.py
```

El `-it` en el `exec` es importante: el display lee el teclado con `termios`, que
necesita una terminal interactiva real.

### Probar las señales

Con el monitor corriendo, desde otra terminal entrar al contenedor y mandarle
señales (reemplazar `<PID>` por el que imprime el monitor al arrancar):

```bash
docker compose exec -it monitor bash
kill -HUP  <PID>    # recarga config.json
kill -USR1 <PID>    # vuelca el snapshot a dump_<timestamp>.json
kill -USR2 <PID>    # alterna modo verbose
kill -TERM <PID>    # shutdown limpio (equivale a Ctrl+C)
```

### Verificar el dump

Después de mandar SIGUSR1:

```bash
ls /app/dump_*.json
cat /app/dump_*.json
```

---

## 9. Decisiones sobre la TUI

Se eligió **`rich`** sobre `curses` por dos razones: produce tablas y paneles
con muy poco código, y su clase `Live` maneja el refresco de pantalla
automáticamente.

Hay un detalle importante en el diseño: el display **no corre como subproceso**,
sino en el proceso principal. La razón es que la lectura de teclado usa `termios`,
que solo funciona sobre una terminal real (TTY). Cuando el display corría como
proceso hijo de `multiprocessing`, no heredaba un stdin conectado a la terminal
y `termios.tcgetattr` fallaba con "Inappropriate ioctl for device". Al mover el
display al proceso principal, tiene acceso a la terminal real y el teclado
funciona. El teclado se lee en un thread aparte usando `select()` para no
bloquear el loop de renderizado.

Un detalle de `rich`: los corchetes tienen significado especial (markup de
estilos), así que el comando de los procesos kernel —que se muestra como
`[kthreadd]`— se escapa con `rich.markup.escape` para que se vea literal.

---

## 10. Configuración de Docker

El `docker-compose.yml` incluye tres opciones clave para poder leer los procesos
del host desde dentro del contenedor:

- **`pid: "host"`**: rompe el namespace de PIDs del contenedor y usa el del host,
  de modo que el monitor ve todos los procesos de la máquina y no solo los del
  contenedor.
- **`cap_add: SYS_PTRACE`**: da el permiso (capability) mínimo necesario para leer
  `/proc/<pid>/maps` y `/proc/<pid>/fd` de procesos ajenos. Se eligió esta
  capability puntual en vez de `privileged` por ser el permiso mínimo.
- **`security_opt: apparmor:unconfined`**: el perfil AppArmor por defecto de
  Docker bloquea el acceso a `/proc/<pid>/maps` y `/fd` incluso teniendo
  `SYS_PTRACE`, así que hay que desactivarlo.

Además usa un bind mount (`.:/app`) para editar el código fuera del contenedor y
que se refleje adentro sin rebuildear, y `tty: true` + `stdin_open: true` para
que la TUI sea interactiva.

---

## 11. Lo que aprendí

Lo que más me marcó de este TP fue entender de verdad qué significa que los
procesos no comparten memoria. Venía pensando en variables globales como algo
que "está ahí para todos", y acá tuve que aceptar que cada proceso vive en su
propio espacio y que compartir un dato implica serializarlo y mandarlo por un
canal. El `Manager.dict` me hizo click cuando entendí que es literalmente otro
proceso haciendo de servidor de datos, y el `Value` cuando vi que un número
copiado a un hijo deja de estar conectado con el del padre.

El otro gran aprendizaje fueron las señales. Al principio no entendía por qué el
handler tenía que ser tan corto, hasta que vi el problema del deadlock: si el
handler intenta tomar un lock que el main ya tenía tomado justo cuando lo
interrumpió, el programa se cuelga para siempre. Eso me hizo entender por qué el
patrón correcto es que el handler solo levante una bandera y el trabajo real lo
haga el loop principal en un punto seguro. Decodificar las máscaras de señales a
nombres también me obligó a pensar en binario: cada bit de un número es una señal.

Por último, pelear con los permisos de Docker para leer `/proc` me enseñó que en
Linux hay varias capas de seguridad independientes (namespaces, capabilities,
AppArmor) y que un acceso puede estar bloqueado por cualquiera de ellas. Cada
"operación no permitida" era una capa distinta que había que entender y destrabar.