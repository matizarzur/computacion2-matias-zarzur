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
docker compose exec monitor bash
cd /app
python3 src/main.py
```

Una vez dentro de la TUI, se cambia de vista con las teclas `1`–`7` (o las
letras `r/m/f/t/s/p/g`) y se sale con `q`.

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
   │(status) ││(maps)   ││(fd/)   ││(task/)││(status)││(stat)    │ │
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

## 3. Decisiones de diseño

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

Se usa `Value` en un caso puntual: el flag de modo verbose (`manager.Value("i", 0)`),
que es un simple entero 0/1. Ahí `Value` es lo correcto por ser un tipo simple.

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

### ¿Por qué los intervalos por defecto?

El recolector y el analizador de sistema refrescan cada 2 segundos por defecto,
configurable desde `config.json`. Dos segundos es un equilibrio entre ver cambios
razonablemente rápido y no saturar la CPU releyendo `/proc` constantemente. Las
vistas más pesadas de leer (como Memoria, que abre `/proc/<pid>/maps` con miles
de líneas por proceso) toleran bien este intervalo porque cada analizador corre
en su propio proceso y no bloquea a los demás.

---

## 4. Conceptos del curso aplicados

- **`/proc` como pseudo-filesystem (clase 3)**: todo el proyecto se basa en que
  `/proc` es virtual, generado por el kernel al vuelo. Las funciones de
  `procfs.py` leen `/proc/<pid>/status`, `/stat`, `/maps`, etc.

- **PID vs TID / threads como LWPs (clase 10)**: la vista Threads lista los TIDs
  leyendo `/proc/<pid>/task/`, donde cada subcarpeta es un thread (Light Weight
  Process). El TID del primer thread coincide con el PID del proceso.

- **Zombies y estados de proceso (clase 4)**: el estado de cada proceso sale del
  campo State de `/proc/<pid>/status`. Un zombie (estado Z) es un proceso
  terminado cuyo padre todavía no llamó a `wait()`, concepto visto en la clase de
  fork/exec/wait.

- **Señales y async-signal-safety (clase 6)**: el monitor maneja SIGINT, SIGTERM,
  SIGHUP, SIGUSR1 y SIGUSR2. Los handlers son mínimos: solo levantan un flag
  (`Event`), y el loop principal actúa sobre ese flag en un punto seguro. Esto
  evita corromper estado o generar deadlocks al ser interrumpido en cualquier
  instrucción.

- **Pipes / IPC (clase 5) y Multiprocessing (clases 8-9)**: la comunicación entre
  procesos usa `Queue` (buffer sincronizado con locks internos) y `Manager.dict`
  (memoria compartida cliente-servidor).

- **TOCTOU (time-of-check-to-time-of-use)**: un proceso puede morir entre el
  momento en que el recolector lo lista y el momento en que un analizador intenta
  leer su `/proc/<pid>/*`. Por eso todas las funciones de lectura por-PID capturan
  `FileNotFoundError` y `PermissionError`.

- **Herencia de handlers en fork (clase 4 + 6)**: los procesos hijos heredan los
  handlers de señales del padre. Como esto impedía que los hijos murieran ante
  SIGTERM en el shutdown, cada hijo restaura los handlers a `SIG_DFL` al arrancar
  (`resetear_handlers_en_hijo`).

---

## 5. Limitaciones conocidas

Este proyecto prioriza una arquitectura multiproceso sólida y las señales sobre
la completitud de cada vista. Las siguientes funcionalidades no están
implementadas y se conocen como pendientes:

**Navegación de la TUI:**
- No hay navegación con flechas `↑`/`↓` por la lista de procesos.
- No está implementado el pin de un proceso con `Enter`.
- No hay filtros por nombre (`/`) ni por usuario (`u`).
- No hay ordenamiento configurable (`c`).
- No está el ajuste de intervalo en runtime con `+`/`-`.

**Datos de `/proc`:**
- No se calcula CPU% (requiere delta de jiffies entre dos lecturas).
- No se lee `cmdline` (comando completo con argumentos).
- Del status solo se extrae VmRSS; faltan VmSize, VmData, VmStk, VmExe, VmLib,
  VmHWM, VmSwap.
- No se resuelven los destinos de los FDs con `readlink` (solo se listan los
  números).
- Las máscaras de señales se muestran como enteros crudos, sin decodificar a
  nombres legibles (SIGTERM, SIGINT, etc.).
- No se leen context switches voluntarios/involuntarios, RT priority, CPU
  affinity ni SID/PGID.
- No se calcula el top 3 por CPU/memoria ni el conteo de zombies.

**Presentación:**
- Las vistas de Memoria, FDs, Threads, Señales y Scheduling muestran los datos
  crudos (el `str()` de cada estructura). Solo Resumen y Sistema tienen formato
  con columnas dedicadas.
- La lista de procesos se limita a los primeros 25 por vista, para que entre en
  pantalla.

---

## 6. Cómo correr y testear

### Requisitos

- Docker y Docker Compose.
- El host debe ser Linux para poder leer sus procesos (el `pid: host` del
  compose usa el namespace de PIDs del host).

### Levantar el monitor

```bash
# Desde la carpeta TP1_monitoreo/
docker compose up --build -d
docker compose exec monitor bash

# Ya dentro del contenedor:
cd /app
python3 src/main.py
```

### Probar las señales

Con el monitor corriendo, desde otra terminal entrar al contenedor y mandarle
señales (reemplazar `<PID>` por el que imprime el monitor al arrancar):

```bash
docker compose exec monitor bash
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

## 7. Decisiones sobre la TUI

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

---

## 8. Configuración de Docker

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

## 9. Lo que aprendí

Lo que más me marcó de este TP fue entender de verdad qué significa que los
procesos no comparten memoria. Venía pensando en variables globales como algo
que "está ahí para todos", y acá tuve que aceptar que cada proceso vive en su
propio espacio y que compartir un dato implica serializarlo y mandarlo por un
canal. El `Manager.dict` me hizo click cuando entendí que es literalmente otro
proceso haciendo de servidor de datos.

El otro gran aprendizaje fueron las señales. Al principio no entendía por qué el
handler tenía que ser tan corto, hasta que vi el problema del deadlock: si el
handler intenta tomar un lock que el main ya tenía tomado justo cuando lo
interrumpió, el programa se cuelga para siempre. Eso me hizo entender por qué el
patrón correcto es que el handler solo levante una bandera y el trabajo real lo
haga el loop principal en un punto seguro.

Por último, pelear con los permisos de Docker para leer `/proc` me enseñó que en
Linux hay varias capas de seguridad independientes (namespaces, capabilities,
AppArmor) y que un acceso puede estar bloqueado por cualquiera de ellas. Cada
"operación no permitida" era una capa distinta que había que entender y destrabar.